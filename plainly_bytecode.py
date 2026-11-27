#!/usr/bin/env python3
"""Plainly's versioned binary bytecode compiler and virtual machine.

The bytecode compiler first runs the normal Plainly parser/type checker, then
translates its generated Python syntax tree into a small, non-Python VM program.
It never executes the generated Python source.
"""
import ast
import hashlib
import math
import os
import struct

import plainly

MAGIC = b"PLNYBC\r\n"
FORMAT_VERSION = 1
MAX_FILE_SIZE = 16 * 1024 * 1024
MAX_STEPS = 1_000_000
MAX_CALL_DEPTH = 100

# Instruction numbers are part of the on-disk format. Never reuse a number.
OPS = {
    "HALT": 0, "PUSH_NUMBER": 1, "PUSH_TEXT": 2, "PUSH_BOOL": 3,
    "PUSH_NONE": 4, "LOAD": 5, "STORE": 6, "POP": 7, "SAY": 8,
    "ADD": 9, "SUB": 10, "MUL": 11, "DIV": 12, "MOD": 13,
    "EQ": 14, "NE": 15, "LT": 16, "LE": 17, "GT": 18, "GE": 19,
    "NOT": 20, "JUMP": 21, "JUMP_FALSE": 22, "JUMP_TRUE": 23,
    "DUP": 24, "BUILD_LIST": 25, "APPEND": 26, "BUILTIN": 27,
    "CALL": 28, "RETURN": 29, "ITER_PREP": 30, "ITER_NEXT": 31,
}
OP_NAMES = {v: k for k, v in OPS.items()}

class BytecodeError(Exception):
    """A compilation, bytecode-format, or VM error."""

def _str(value):
    raw = value.encode("utf-8")
    if len(raw) > 65535:
        raise BytecodeError("a bytecode name or string is too long")
    return struct.pack(">H", len(raw)) + raw

def _read_string(data, pos):
    if pos + 2 > len(data):
        raise BytecodeError("the bytecode file is truncated")
    size = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    if pos + size > len(data):
        raise BytecodeError("the bytecode file is truncated")
    try:
        value = bytes(data[pos:pos + size]).decode("utf-8")
    except UnicodeDecodeError:
        raise BytecodeError("the bytecode file contains invalid text")
    return value, pos + size

def _encode_code(code):
    out = bytearray()
    for opname, args in code:
        if opname not in OPS:
            raise BytecodeError("unknown bytecode instruction: " + str(opname))
        out.append(OPS[opname])
        if opname == "PUSH_NUMBER":
            out.extend(struct.pack(">d", float(args[0])))
        elif opname == "PUSH_TEXT":
            raw = args[0].encode("utf-8")
            out.extend(struct.pack(">I", len(raw)))
            out.extend(raw)
        elif opname == "PUSH_BOOL":
            out.append(1 if args[0] else 0)
        elif opname in ("LOAD", "STORE", "CALL"):
            out.extend(_str(args[0]))
            if opname == "CALL":
                out.append(args[1])
        elif opname == "BUILTIN":
            out.extend(_str(args[0]))
            out.append(args[1])
        elif opname == "BUILD_LIST":
            out.extend(struct.pack(">H", args[0]))
        elif opname in ("JUMP", "JUMP_FALSE", "JUMP_TRUE"):
            out.extend(struct.pack(">I", args[0]))
        elif opname == "ITER_NEXT":
            out.extend(_str(args[0]))
            out.extend(struct.pack(">I", args[1]))
    return bytes(out)

def _decode_code(data, pos, count):
    code = []
    for _ in range(count):
        if pos >= len(data):
            raise BytecodeError("the bytecode instructions are truncated")
        opcode = data[pos]
        pos += 1
        name = OP_NAMES.get(opcode)
        if name is None:
            raise BytecodeError("the bytecode contains an unknown instruction")
        args = ()
        if name == "PUSH_NUMBER":
            if pos + 8 > len(data): raise BytecodeError("the bytecode is truncated")
            args = (struct.unpack_from(">d", data, pos)[0],); pos += 8
        elif name == "PUSH_TEXT":
            if pos + 4 > len(data): raise BytecodeError("the bytecode is truncated")
            size = struct.unpack_from(">I", data, pos)[0]; pos += 4
            if size > MAX_FILE_SIZE or pos + size > len(data): raise BytecodeError("the bytecode text is truncated or too large")
            try: value = bytes(data[pos:pos + size]).decode("utf-8")
            except UnicodeDecodeError: raise BytecodeError("the bytecode contains invalid text")
            args = (value,); pos += size
        elif name == "PUSH_BOOL":
            if pos >= len(data) or data[pos] not in (0, 1): raise BytecodeError("invalid boolean bytecode value")
            args = (bool(data[pos]),); pos += 1
        elif name in ("LOAD", "STORE", "CALL", "BUILTIN"):
            value, pos = _read_string(data, pos)
            if name in ("CALL", "BUILTIN"):
                if pos >= len(data): raise BytecodeError("the bytecode is truncated")
                argc = data[pos]; pos += 1
                args = (value, argc)
            else:
                args = (value,)
        elif name == "BUILD_LIST":
            if pos + 2 > len(data): raise BytecodeError("the bytecode is truncated")
            args = (struct.unpack_from(">H", data, pos)[0],); pos += 2
        elif name in ("JUMP", "JUMP_FALSE", "JUMP_TRUE"):
            if pos + 4 > len(data): raise BytecodeError("the bytecode is truncated")
            args = (struct.unpack_from(">I", data, pos)[0],); pos += 4
        elif name == "ITER_NEXT":
            value, pos = _read_string(data, pos)
            if pos + 4 > len(data): raise BytecodeError("the bytecode is truncated")
            target = struct.unpack_from(">I", data, pos)[0]; pos += 4
            args = (value, target)
        code.append((name, args))
    for name, args in code:
        if name in ("JUMP", "JUMP_FALSE", "JUMP_TRUE") and args[0] > len(code):
            raise BytecodeError("a bytecode jump points outside the program")
        if name == "ITER_NEXT" and args[1] > len(code):
            raise BytecodeError("a bytecode loop points outside the program")
    return code, pos

def dumps(program):
    """Serialize a compiled program to a checksummed binary .pbc container."""
    functions = program["functions"]
    payload = bytearray(struct.pack(">H", len(functions)))
    for name, meta in functions.items():
        payload.extend(_str(name))
        payload.extend(struct.pack(">H", len(meta["params"])))
        for param in meta["params"]:
            payload.extend(_str(param))
        code = _encode_code(meta["code"])
        payload.extend(struct.pack(">I", len(meta["code"])))
        payload.extend(code)
    main_code = _encode_code(program["main"])
    payload.extend(struct.pack(">I", len(program["main"])))
    payload.extend(main_code)
    if len(payload) > MAX_FILE_SIZE:
        raise BytecodeError("the compiled program is too large")
    header = MAGIC + struct.pack(">HI", FORMAT_VERSION, len(payload))
    return header + hashlib.sha256(payload).digest() + bytes(payload)

def loads(blob):
    """Validate and decode a .pbc file; never evaluate its contents as Python."""
    if not isinstance(blob, (bytes, bytearray)) or len(blob) < 46 or len(blob) > MAX_FILE_SIZE:
        raise BytecodeError("this is not a valid Plainly bytecode file")
    if bytes(blob[:8]) != MAGIC:
        raise BytecodeError("this file is not a Plainly .pbc bytecode file")
    version, size = struct.unpack_from(">HI", blob, 8)
    if version != FORMAT_VERSION:
        raise BytecodeError("unsupported Plainly bytecode version %d" % version)
    if size != len(blob) - 46:
        raise BytecodeError("the bytecode file has an invalid length")
    digest = bytes(blob[14:46])
    payload = memoryview(blob)[46:]
    if not hashlib.sha256(payload).digest() == digest:
        raise BytecodeError("the bytecode checksum does not match; the file may be damaged")
    pos = 0
    if pos + 2 > len(payload): raise BytecodeError("the bytecode file is truncated")
    fn_count = struct.unpack_from(">H", payload, pos)[0]; pos += 2
    if fn_count > 4096: raise BytecodeError("the bytecode has too many functions")
    functions = {}
    for _ in range(fn_count):
        name, pos = _read_string(payload, pos)
        if name in functions: raise BytecodeError("the bytecode contains a duplicate function")
        if pos + 2 > len(payload): raise BytecodeError("the bytecode file is truncated")
        nparams = struct.unpack_from(">H", payload, pos)[0]; pos += 2
        if nparams > 255: raise BytecodeError("a bytecode function has too many inputs")
        params = []
        for _ in range(nparams):
            param, pos = _read_string(payload, pos); params.append(param)
        if pos + 4 > len(payload): raise BytecodeError("the bytecode file is truncated")
        count = struct.unpack_from(">I", payload, pos)[0]; pos += 4
        if count > 1_000_000: raise BytecodeError("the bytecode function is too large")
        code, pos = _decode_code(payload, pos, count)
        functions[name] = {"params": params, "code": code}
    if pos + 4 > len(payload): raise BytecodeError("the bytecode file is truncated")
    count = struct.unpack_from(">I", payload, pos)[0]; pos += 4
    if count > 1_000_000: raise BytecodeError("the bytecode program is too large")
    main, pos = _decode_code(payload, pos, count)
    if pos != len(payload): raise BytecodeError("the bytecode file has unexpected trailing data")
    return {"functions": functions, "main": main}

class _Compiler:
    def __init__(self):
        self.code = []
        self.functions = {}
        self.in_function = False

    def emit(self, name, *args):
        self.code.append((name, args))
        return len(self.code) - 1

    def patch(self, index, *args):
        name, _ = self.code[index]
        self.code[index] = (name, args)

    def compile_expr(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool): self.emit("PUSH_BOOL", node.value)
            elif isinstance(node.value, (int, float)): self.emit("PUSH_NUMBER", node.value)
            elif isinstance(node.value, str): self.emit("PUSH_TEXT", node.value)
            elif node.value is None: self.emit("PUSH_NONE")
            else: self.fail(node, "this constant is not supported by bytecode")
        elif isinstance(node, ast.Name):
            self.emit("LOAD", node.id)
        elif isinstance(node, ast.List):
            for item in node.elts: self.compile_expr(item)
            self.emit("BUILD_LIST", len(node.elts))
        elif isinstance(node, ast.BinOp):
            ops = {ast.Add: "ADD", ast.Sub: "SUB", ast.Mult: "MUL", ast.Div: "DIV", ast.Mod: "MOD"}
            opname = ops.get(type(node.op))
            if not opname: self.fail(node, "this arithmetic operation is not supported by bytecode")
            self.compile_expr(node.left); self.compile_expr(node.right); self.emit(opname)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            self.compile_expr(node.operand); self.emit("NOT")
        elif isinstance(node, ast.BoolOp):
            exits = []
            for value in node.values[:-1]:
                self.compile_expr(value)
                self.emit("DUP")
                exits.append(self.emit("JUMP_FALSE" if isinstance(node.op, ast.And) else "JUMP_TRUE", 0))
                self.emit("POP")
            self.compile_expr(node.values[-1])
            for jump in exits: self.patch(jump, len(self.code))
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            ops = {ast.Eq: "EQ", ast.NotEq: "NE", ast.Lt: "LT", ast.LtE: "LE", ast.Gt: "GT", ast.GtE: "GE"}
            opname = ops.get(type(node.ops[0]))
            if not opname: self.fail(node, "this comparison is not supported by bytecode")
            self.compile_expr(node.left); self.compile_expr(node.comparators[0]); self.emit(opname)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if node.keywords: self.fail(node, "named function inputs are not supported in bytecode")
            for arg in node.args: self.compile_expr(arg)
            if name.startswith("f_"):
                self.emit("CALL", name, len(node.args))
            else:
                self.emit("BUILTIN", name, len(node.args))
        else:
            self.fail(node, "this expression is not supported by the current bytecode version")

    def compile_block(self, statements):
        for node in statements: self.compile_stmt(node)

    def compile_stmt(self, node):
        if isinstance(node, ast.Pass):
            return
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and \
                    node.value.func.attr == "append" and len(node.value.args) == 1 and isinstance(node.value.func.value, ast.Name):
                self.emit("LOAD", node.value.func.value.id)
                self.compile_expr(node.value.args[0])
                self.emit("APPEND")
            else:
                self.compile_expr(node.value)
                self.emit("POP")
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self.compile_expr(node.value); self.emit("STORE", node.targets[0].id)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            ops = {ast.Add: "ADD", ast.Sub: "SUB"}
            opname = ops.get(type(node.op))
            if not opname: self.fail(node, "this update operation is not supported by bytecode")
            self.emit("LOAD", node.target.id); self.compile_expr(node.value); self.emit(opname); self.emit("STORE", node.target.id)
        elif isinstance(node, ast.If):
            self.compile_expr(node.test)
            otherwise = self.emit("JUMP_FALSE", 0)
            self.compile_block(node.body)
            if node.orelse:
                done = self.emit("JUMP", 0)
                self.patch(otherwise, len(self.code))
                self.compile_block(node.orelse)
                self.patch(done, len(self.code))
            else:
                self.patch(otherwise, len(self.code))
        elif isinstance(node, ast.While):
            start = len(self.code)
            self.compile_expr(node.test)
            done = self.emit("JUMP_FALSE", 0)
            self.compile_block(node.body)
            self.emit("JUMP", start)
            self.patch(done, len(self.code))
            if node.orelse: self.fail(node, "loop else clauses are not supported by bytecode")
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            self.compile_expr(node.iter)
            self.emit("ITER_PREP")
            start = len(self.code)
            nxt = self.emit("ITER_NEXT", node.target.id, 0)
            self.compile_block(node.body)
            self.emit("JUMP", start)
            self.patch(nxt, node.target.id, len(self.code))
            if node.orelse: self.fail(node, "loop else clauses are not supported by bytecode")
        elif isinstance(node, ast.Return):
            if node.value is None: self.emit("PUSH_NONE")
            else: self.compile_expr(node.value)
            self.emit("RETURN")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.fail(node, "nested functions are not supported by bytecode")
        else:
            self.fail(node, "this statement is not supported by the current bytecode version")

    def fail(self, node, message):
        raise BytecodeError("%s (generated line %s)" % (message, getattr(node, "lineno", "?")))

    def build(self, source):
        # Plainly's own compiler remains the source of truth for syntax, types,
        # names, and file permissions. The generated Python is parsed, never run.
        generated, _ = plainly.compile_source(source)
        try:
            tree = ast.parse(generated)
        except SyntaxError as exc:
            raise BytecodeError("Plainly could not prepare this program for bytecode: %s" % exc.msg)
        main_nodes = []
        function_nodes = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                function_nodes.append(node)
            else:
                main_nodes.append(node)
        for fn in function_nodes:
            self.code = []
            self.in_function = True
            self.compile_block(fn.body)
            if not self.code or self.code[-1][0] != "RETURN":
                self.emit("PUSH_NONE"); self.emit("RETURN")
            self.functions[fn.name] = {
                "params": [arg.arg for arg in fn.args.args],
                "code": self.code,
            }
        self.code = []
        self.in_function = False
        self.compile_block(main_nodes)
        self.emit("HALT")
        return {"functions": self.functions, "main": self.code}

def compile_source(source):
    """Compile Plainly source to a Python-free binary bytecode blob."""
    program = _Compiler().build(source)
    return dumps(program)

def compile_file(source_path, output_path=None):
    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    blob = compile_source(source)
    if output_path is None:
        output_path = os.path.splitext(source_path)[0] + ".pbc"
    with open(output_path, "wb") as handle:
        handle.write(blob)
    return output_path

def _builtin(name, args, input_fn):
    if name == "_say" and len(args) == 1:
        print(plainly._show(args[0])); return None
    if name == "_cat" and len(args) == 3:
        return plainly._cat(args[0], args[1], bool(args[2]))
    builtins = {
        "_count": plainly._count, "_length": plainly._length,
        "_sqrt": plainly._sqrt, "_abs": plainly._abs,
        "_rounded": plainly._rounded, "_largest": plainly._largest,
        "_smallest": plainly._smallest, "_at": plainly._at,
        "_parsed": plainly._parsed, "_orelse": plainly._orelse,
    }
    if name == "_ask" and not args:
        try: return input_fn()
        except EOFError: return ""
    if name == "range" and len(args) == 1:
        count = args[0]
        return range(plainly._count(count))
    fn = builtins.get(name)
    if fn is None:
        raise BytecodeError("the bytecode uses a feature that is not supported yet: " + name)
    try:
        return fn(*args)
    except (TypeError, ValueError, OverflowError) as exc:
        raise BytecodeError("invalid value passed to " + name + ": " + str(exc))

def run_program(program, input_fn=input, step_limit=MAX_STEPS):
    """Execute decoded bytecode in the Plainly VM."""
    functions = program["functions"]
    steps = [0]

    def execute(code, env, depth):
        if depth > MAX_CALL_DEPTH:
            raise BytecodeError("the function call limit was reached")
        stack = []
        iterators = []
        ip = 0
        while ip < len(code):
            steps[0] += 1
            if steps[0] > step_limit:
                raise BytecodeError("the program reached the bytecode instruction limit")
            name, args = code[ip]
            ip += 1
            if name == "HALT":
                return None
            if name == "PUSH_NUMBER" or name == "PUSH_TEXT" or name == "PUSH_BOOL":
                stack.append(args[0])
            elif name == "PUSH_NONE":
                stack.append(None)
            elif name == "LOAD":
                if args[0] not in env: raise BytecodeError("unknown runtime name: " + args[0])
                stack.append(env[args[0]])
            elif name == "STORE":
                env[args[0]] = stack.pop()
            elif name == "POP":
                if not stack: raise BytecodeError("invalid bytecode stack operation")
                stack.pop()
            elif name == "DUP":
                if not stack: raise BytecodeError("invalid bytecode stack operation")
                stack.append(stack[-1])
            elif name == "SAY":
                if not stack: raise BytecodeError("invalid bytecode stack operation")
                print(plainly._show(stack.pop()))
            elif name == "BUILD_LIST":
                count = args[0]
                if count > len(stack): raise BytecodeError("invalid bytecode list operation")
                values = stack[-count:] if count else []
                if count: del stack[-count:]
                stack.append(list(values))
            elif name == "APPEND":
                value = stack.pop(); target = stack.pop()
                if not isinstance(target, list): raise BytecodeError("bytecode tried to append to a non-list")
                target.append(value)
            elif name in ("ADD", "SUB", "MUL", "DIV", "MOD", "EQ", "NE", "LT", "LE", "GT", "GE"):
                right = stack.pop(); left = stack.pop()
                if name == "ADD": result = left + right
                elif name == "SUB": result = left - right
                elif name == "MUL": result = left * right
                elif name == "DIV":
                    if right == 0: raise BytecodeError("cannot divide by zero")
                    result = left / right
                elif name == "MOD":
                    if right == 0: raise BytecodeError("cannot divide by zero")
                    result = left % right
                elif name == "EQ": result = left == right
                elif name == "NE": result = left != right
                elif name == "LT": result = left < right
                elif name == "LE": result = left <= right
                elif name == "GT": result = left > right
                else: result = left >= right
                stack.append(result)
            elif name == "NOT":
                stack.append(not stack.pop())
            elif name == "JUMP":
                ip = args[0]
            elif name == "JUMP_FALSE":
                if not stack.pop(): ip = args[0]
            elif name == "JUMP_TRUE":
                if stack.pop(): ip = args[0]
            elif name == "ITER_PREP":
                value = stack.pop()
                try: iterator = iter(value)
                except TypeError: raise BytecodeError("bytecode tried to loop over a value that is not a list")
                iterators.append(iterator)
            elif name == "ITER_NEXT":
                if not iterators: raise BytecodeError("invalid bytecode loop")
                try: env[args[0]] = next(iterators[-1])
                except StopIteration:
                    iterators.pop()
                    ip = args[1]
            elif name == "BUILTIN":
                argc = args[1]
                if argc > len(stack): raise BytecodeError("invalid bytecode function call")
                values = stack[-argc:] if argc else []
                if argc: del stack[-argc:]
                stack.append(_builtin(args[0], values, input_fn))
            elif name == "CALL":
                argc = args[1]
                if argc > len(stack): raise BytecodeError("invalid bytecode function call")
                values = stack[-argc:] if argc else []
                if argc: del stack[-argc:]
                fn = functions.get(args[0])
                if fn is None or len(fn["params"]) != argc:
                    raise BytecodeError("unknown bytecode function: " + args[0])
                local = dict(zip(fn["params"], values))
                stack.append(execute(fn["code"], local, depth + 1))
            elif name == "RETURN":
                return stack.pop() if stack else None
            else:
                raise BytecodeError("unsupported bytecode instruction: " + name)
        return None

    execute(program["main"], {}, 0)

def run_bytes(blob, input_fn=input, step_limit=MAX_STEPS):
    run_program(loads(blob), input_fn=input_fn, step_limit=step_limit)

def run_file(path, input_fn=input, step_limit=MAX_STEPS):
    with open(path, "rb") as handle:
        blob = handle.read(MAX_FILE_SIZE + 1)
    if len(blob) > MAX_FILE_SIZE:
        raise BytecodeError("the bytecode file is too large")
    run_bytes(blob, input_fn=input_fn, step_limit=step_limit)

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "compile":
        print(compile_file(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "execute":
        run_file(sys.argv[2])
    else:
        print("Usage: python plainly_bytecode.py compile program.plain | execute program.pbc")
        raise SystemExit(2)
