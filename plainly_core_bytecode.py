#!/usr/bin/env python3
"""Independent Plainly AST-to-bytecode compiler and bounded virtual machine.

This backend consumes plainly_core's own AST. It never imports the legacy
compiler, Python ast, generated Python, JavaScript, or native code.
"""
import hashlib
import json
import math
import os
import struct

import plainly_core as core

MAGIC = b"PLNYCORE"
VERSION = 1
MAX_BLOB = 16 * 1024 * 1024
MAX_INSTRUCTIONS = 500000
MAX_STACK = 100000
MAX_VARIABLES = core.MAX_VARIABLES

OPS = {
    "CONST": 1, "LOAD": 2, "DECLARE": 3, "STORE": 4, "SAY": 5,
    "POP": 6, "DUP": 17, "BOOL_CHECK": 18, "UNARY": 7, "BINARY": 8, "CALL": 9, "BUILD_LIST": 10,
    "JUMP": 11, "JUMP_FALSE": 12, "JUMP_TRUE": 13,
    "REPEAT_START": 14, "REPEAT_NEXT": 15, "HALT": 16,
}
_ALLOWED_BINARY = {"+", "-", "*", "/", "//", "%", "**", "==", "!=", "<", "<=", ">", ">="}
_ALLOWED_CALLS = {"length", "sqrt", "absolute", "largest", "smallest"}


class CoreBytecodeError(Exception):
    """Invalid source, bytecode, or VM execution."""


def _instruction(op, *args):
    if op not in OPS:
        raise CoreBytecodeError("compiler emitted an unknown instruction")
    return [op, *args]


class Compiler:
    def __init__(self):
        self.code = []

    def emit(self, op, *args):
        if len(self.code) >= MAX_INSTRUCTIONS:
            raise CoreBytecodeError("compiled program contains too many instructions")
        self.code.append(_instruction(op, *args))
        return len(self.code) - 1

    def patch(self, index, target):
        if type(index) is not int or not 0 <= index < len(self.code):
            raise CoreBytecodeError("invalid compiler patch location")
        if type(target) is not int or target < 0:
            raise CoreBytecodeError("invalid compiler jump target")
        instruction = self.code[index]
        if instruction[0] not in ("JUMP", "JUMP_FALSE", "JUMP_TRUE", "REPEAT_START", "REPEAT_NEXT"):
            raise CoreBytecodeError("compiler patch target is not a jump instruction")
        # Jump instructions store their target at operand 1 and source line
        # metadata at operand 2. Never overwrite the source-line field.
        instruction[1] = target

    def expression(self, expr):
        kind, value = expr.kind, expr.value
        if kind == "literal":
            self.emit("CONST", value, expr.line)
        elif kind == "name":
            self.emit("LOAD", value, expr.line)
        elif kind == "list":
            for item in expr.children:
                self.expression(item)
            self.emit("BUILD_LIST", len(expr.children), expr.line)
        elif kind == "unary":
            self.expression(expr.children[0])
            self.emit("UNARY", value, expr.line)
        elif kind == "call":
            if value not in _ALLOWED_CALLS:
                raise CoreBytecodeError("unsupported core function: " + str(value))
            for item in expr.children:
                self.expression(item)
            self.emit("CALL", value, len(expr.children), expr.line)
        elif kind == "binary":
            left, right = expr.children
            if value == "and":
                self.expression(left)
                self.emit("DUP", expr.line)
                jump = self.emit("JUMP_FALSE", -1, expr.line)
                self.emit("POP", expr.line)
                self.expression(right)
                self.emit("BOOL_CHECK", expr.line)
                self.patch(jump, len(self.code))
            elif value == "or":
                self.expression(left)
                self.emit("DUP", expr.line)
                jump = self.emit("JUMP_TRUE", -1, expr.line)
                self.emit("POP", expr.line)
                self.expression(right)
                self.emit("BOOL_CHECK", expr.line)
                self.patch(jump, len(self.code))
            else:
                if value not in _ALLOWED_BINARY:
                    raise CoreBytecodeError("unsupported core operator: " + str(value))
                self.expression(left)
                self.expression(right)
                self.emit("BINARY", value, expr.line)
        else:
            raise CoreBytecodeError("unsupported expression node: " + str(kind))

    def block(self, statements):
        for statement in statements:
            line = statement.line
            kind = statement.kind
            if kind == "let":
                self.expression(statement.expression)
                self.emit("DECLARE", statement.value, line)
            elif kind == "set":
                self.expression(statement.expression)
                self.emit("STORE", statement.value, line)
            elif kind == "say":
                self.expression(statement.expression)
                self.emit("SAY", line)
            elif kind == "if":
                self.expression(statement.expression)
                branch = self.emit("JUMP_FALSE", -1, line)
                self.block(statement.body)
                if statement.alternate:
                    finish = self.emit("JUMP", -1, line)
                    self.patch(branch, len(self.code))
                    self.block(statement.alternate)
                    self.patch(finish, len(self.code))
                else:
                    self.patch(branch, len(self.code))
            elif kind == "while":
                start = len(self.code)
                self.expression(statement.expression)
                finish = self.emit("JUMP_FALSE", -1, line)
                self.block(statement.body)
                self.emit("JUMP", start, line)
                self.patch(finish, len(self.code))
            elif kind == "repeat":
                self.expression(statement.expression)
                start = self.emit("REPEAT_START", -1, line)
                body_start = len(self.code)
                self.block(statement.body)
                self.emit("REPEAT_NEXT", body_start, line)
                self.patch(start, len(self.code))
            else:
                raise CoreBytecodeError("unsupported statement node: " + str(kind))

    def compile(self, program):
        self.block(program.statements)
        self.emit("HALT")
        return {"format": VERSION, "code": self.code}


def _validate_program(program):
    if not isinstance(program, dict) or set(program) != {"format", "code"}:
        raise CoreBytecodeError("invalid Plainly core bytecode program")
    if type(program["format"]) is not int or program["format"] != VERSION:
        raise CoreBytecodeError("unsupported Plainly core bytecode version")
    code = program["code"]
    if not isinstance(code, list) or not 1 <= len(code) <= MAX_INSTRUCTIONS:
        raise CoreBytecodeError("invalid instruction sequence")
    valid_lines = range(0, core.MAX_SOURCE_LINES + 1)
    for index, item in enumerate(code):
        if not isinstance(item, list) or not item or not isinstance(item[0], str) or item[0] not in OPS:
            raise CoreBytecodeError("invalid instruction at index %d" % index)
        op = item[0]
        expected = {
            "CONST": 3, "LOAD": 3, "DECLARE": 3, "STORE": 3, "SAY": 2,
            "POP": 2, "DUP": 2, "BOOL_CHECK": 2, "UNARY": 3, "BINARY": 3, "CALL": 4,
            "BUILD_LIST": 3, "JUMP": 3, "JUMP_FALSE": 3, "JUMP_TRUE": 3,
            "REPEAT_START": 3, "REPEAT_NEXT": 3, "HALT": 1,
        }[op]
        if len(item) != expected:
            raise CoreBytecodeError("invalid operands for instruction %d" % index)
        if op in ("LOAD", "DECLARE", "STORE"):
            if not isinstance(item[1], str) or not item[1].isidentifier():
                raise CoreBytecodeError("invalid variable name in bytecode")
        if op == "CONST":
            value = item[1]
            if type(value) not in (bool, int, float, str):
                raise CoreBytecodeError("invalid constant type")
            if isinstance(value, str):
                try:
                    text_size = len(value.encode("utf-8"))
                except UnicodeEncodeError:
                    raise CoreBytecodeError("bytecode contains invalid Unicode text") from None
                if text_size > core.MAX_TEXT_LENGTH:
                    raise CoreBytecodeError("bytecode text constant is too large")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                try:
                    if not math.isfinite(float(value)) or abs(value) > core.MAX_NUMBER_MAGNITUDE:
                        raise CoreBytecodeError("numeric constant is outside the supported range")
                except OverflowError:
                    raise CoreBytecodeError("numeric constant is outside the supported range")
        if op == "UNARY" and (not isinstance(item[1], str) or item[1] not in ("not", "-")):
            raise CoreBytecodeError("invalid unary operator")
        if op == "BINARY" and (not isinstance(item[1], str) or item[1] not in _ALLOWED_BINARY):
            raise CoreBytecodeError("invalid binary operator")
        if op == "CALL" and (not isinstance(item[1], str) or item[1] not in _ALLOWED_CALLS or type(item[2]) is not int or not 0 <= item[2] <= 16):
            raise CoreBytecodeError("invalid builtin call")
        if op == "BUILD_LIST" and (type(item[1]) is not int or not 0 <= item[1] <= core.MAX_COLLECTION_ITEMS):
            raise CoreBytecodeError("invalid list size")
        if op in ("JUMP", "JUMP_FALSE", "JUMP_TRUE", "REPEAT_START", "REPEAT_NEXT"):
            target = item[1]
            if type(target) is not int or not 0 <= target < len(code):
                raise CoreBytecodeError("bytecode jump is outside the program")
        line = item[-1] if op not in ("HALT",) else 0
        if type(line) is not int or line not in valid_lines:
            raise CoreBytecodeError("invalid source line metadata")
    if code[-1][0] != "HALT":
        raise CoreBytecodeError("bytecode program has no final HALT")
    if any(item[0] == "HALT" for item in code[:-1]):
        raise CoreBytecodeError("bytecode contains an early HALT instruction")
    return program


def dumps(program):
    _validate_program(program)
    try:
        payload = json.dumps(program, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise CoreBytecodeError("program cannot be serialized as Plainly bytecode") from None
    if len(payload) > MAX_BLOB:
        raise CoreBytecodeError("compiled program is too large")
    return MAGIC + struct.pack(">HI", VERSION, len(payload)) + hashlib.sha256(payload).digest() + payload


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def loads(blob):
    if not isinstance(blob, (bytes, bytearray)) or len(blob) < 46 or len(blob) > MAX_BLOB + 46:
        raise CoreBytecodeError("invalid Plainly core bytecode file")
    blob = bytes(blob)
    if blob[:8] != MAGIC:
        raise CoreBytecodeError("not a Plainly core bytecode file")
    version, size = struct.unpack_from(">HI", blob, 8)
    if version != VERSION or size > MAX_BLOB or len(blob) != 46 + size:
        raise CoreBytecodeError("invalid or unsupported bytecode header")
    digest = blob[14:46]
    payload = blob[46:]
    if not hashlib.sha256(payload).digest() == digest:
        raise CoreBytecodeError("bytecode checksum mismatch")
    try:
        program = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except UnicodeDecodeError:
        raise CoreBytecodeError("bytecode payload is not valid UTF-8") from None
    except RecursionError:
        raise CoreBytecodeError("bytecode JSON nesting is too deep") from None
    except ValueError as exc:
        if "duplicate JSON object key" in str(exc):
            raise CoreBytecodeError("bytecode contains duplicate JSON object keys") from None
        raise CoreBytecodeError("bytecode payload is not valid JSON") from None
    return _validate_program(program)


class VirtualMachine:
    def __init__(self, max_steps=core.MAX_STEPS):
        if type(max_steps) is not int or not 1 <= max_steps <= core.MAX_STEPS:
            raise CoreBytecodeError("execution budget must be from 1 to %d" % core.MAX_STEPS)
        self.budget = max_steps
        self.stack = []
        self.variables = {}
        self.output = []
        self.output_bytes = 0
        self.repeats = []

    def tick(self, line):
        self.budget -= 1
        if self.budget < 0:
            raise core.PlainlyCoreError("execution step limit exceeded", line)

    def pop(self, line):
        if not self.stack:
            raise CoreBytecodeError("bytecode stack underflow at line %d" % line)
        return self.stack.pop()

    def push(self, value, line):
        if len(self.stack) >= MAX_STACK:
            raise core.PlainlyCoreError("runtime stack limit exceeded", line)
        self.stack.append(value)

    def binary(self, op, left, right, line):
        checker = core.Interpreter(max_steps=core.MAX_STEPS)
        if op in ("==", "!="):
            equal = (type(left) is type(right) or (core._is_number(left) and core._is_number(right))) and left == right
            return equal if op == "==" else not equal
        if op in ("<", "<=", ">", ">="):
            if type(left) is not type(right) and not (core._is_number(left) and core._is_number(right)):
                raise core.PlainlyCoreError("comparison values must have matching types", line)
            if not (core._is_number(left) or isinstance(left, str)):
                raise core.PlainlyCoreError("these values cannot be ordered", line)
            return {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[op]
        if op == "+" and isinstance(left, str) and isinstance(right, str):
            result = left + right
            if len(result.encode("utf-8")) > core.MAX_TEXT_LENGTH:
                raise core.PlainlyCoreError("text result is too large", line)
            return result
        a = checker.checked_number(left, line)
        b = checker.checked_number(right, line)
        if op in ("/", "//", "%") and b == 0:
            raise core.PlainlyCoreError("division by zero", line)
        try:
            if op == "+": result = a + b
            elif op == "-": result = a - b
            elif op == "*":
                if abs(a) > 1e50 or abs(b) > 1e50:
                    raise core.PlainlyCoreError("multiplication inputs are too large", line)
                result = a * b
            elif op == "/": result = a / b
            elif op == "//": result = a // b
            elif op == "%": result = a % b
            elif op == "**":
                if abs(b) > 10000:
                    raise core.PlainlyCoreError("exponent is too large", line)
                result = a ** b
            else: raise CoreBytecodeError("unsupported operator")
        except (OverflowError, ValueError, ZeroDivisionError):
            raise core.PlainlyCoreError("the calculation is outside the supported range", line) from None
        return checker.checked_number(result, line)

    def builtin(self, name, args, line):
        if name == "length" and len(args) == 1 and isinstance(args[0], (str, list)):
            return len(args[0])
        if name == "sqrt" and len(args) == 1:
            n = core.Interpreter().checked_number(args[0], line)
            if n < 0: raise core.PlainlyCoreError("square root needs a non-negative number", line)
            return math.sqrt(n)
        if name == "absolute" and len(args) == 1:
            return abs(core.Interpreter().checked_number(args[0], line))
        if name in ("largest", "smallest") and len(args) == 1 and isinstance(args[0], list):
            if not args[0]: raise core.PlainlyCoreError(name + " needs a non-empty list", line)
            if not all(core._is_number(x) for x in args[0]):
                raise core.PlainlyCoreError(name + " needs a list of numbers", line)
            return (max if name == "largest" else min)(args[0])
        raise core.PlainlyCoreError("unknown function or wrong inputs for %r" % name, line)

    def run(self, program):
        program = _validate_program(program)
        code = program["code"]
        pc = 0
        while pc < len(code):
            item = code[pc]
            op = item[0]
            line = item[-1] if op != "HALT" else 0
            self.tick(line)
            pc += 1
            if op == "HALT":
                if self.stack or self.repeats:
                    raise CoreBytecodeError("bytecode halted with an unbalanced runtime stack")
                break
            if op == "CONST": self.push(item[1], line)
            elif op == "LOAD":
                if item[1] not in self.variables: raise core.PlainlyCoreError("unknown name %r" % item[1], line)
                self.push(self.variables[item[1]], line)
            elif op in ("DECLARE", "STORE"):
                value = self.pop(line)
                name = item[1]
                exists = name in self.variables
                if op == "DECLARE" and exists: raise core.PlainlyCoreError("name %r has already been declared" % name, line)
                if op == "STORE" and not exists: raise core.PlainlyCoreError("cannot set unknown name %r" % name, line)
                checker = core.Interpreter(max_steps=core.MAX_STEPS)
                checker.variables = self.variables
                checker.store_value(name, value, line, op == "DECLARE")
                self.variables = checker.variables
            elif op == "SAY":
                value = core._show(self.pop(line))
                size = len(value.encode("utf-8")) + 1
                if size > core.MAX_OUTPUT_BYTES - self.output_bytes:
                    raise core.PlainlyCoreError("program output exceeded the 1 MiB limit", line)
                self.output_bytes += size
                self.output.append(value)
            elif op == "POP": self.pop(line)
            elif op == "DUP":
                if not self.stack:
                    raise CoreBytecodeError("bytecode stack underflow")
                self.push(self.stack[-1], line)
            elif op == "BOOL_CHECK":
                value = self.pop(line)
                if not isinstance(value, bool):
                    raise core.PlainlyCoreError("condition needs a yes/no value", line)
                self.push(value, line)
            elif op == "UNARY":
                value = self.pop(line)
                if item[1] == "not":
                    if not isinstance(value, bool): raise core.PlainlyCoreError("'not' needs a yes/no value", line)
                    self.push(not value, line)
                else:
                    number = core.Interpreter().checked_number(value, line)
                    self.push(core.Interpreter().checked_number(-number, line), line)
            elif op == "BINARY":
                right, left = self.pop(line), self.pop(line)
                self.push(self.binary(item[1], left, right, line), line)
            elif op == "CALL":
                count = item[2]
                if count > len(self.stack): raise CoreBytecodeError("bytecode stack underflow")
                args = self.stack[-count:] if count else []
                if count: del self.stack[-count:]
                self.push(self.builtin(item[1], args, line), line)
            elif op == "BUILD_LIST":
                count = item[1]
                if count > len(self.stack): raise CoreBytecodeError("bytecode stack underflow")
                values = self.stack[-count:] if count else []
                if count: del self.stack[-count:]
                self.push(list(values), line)
            elif op == "JUMP": pc = item[1]
            elif op == "JUMP_FALSE":
                condition = self.pop(line)
                if not isinstance(condition, bool): raise core.PlainlyCoreError("condition needs a yes/no value", line)
                if not condition: pc = item[1]
            elif op == "JUMP_TRUE":
                condition = self.pop(line)
                if not isinstance(condition, bool): raise core.PlainlyCoreError("condition needs a yes/no value", line)
                if condition: pc = item[1]
            elif op == "REPEAT_START":
                count = self.pop(line)
                if not core._is_number(count) or int(count) != count or count < 0 or count > core.MAX_REPEAT:
                    raise core.PlainlyCoreError("repeat needs a whole number from 0 to %d" % core.MAX_REPEAT, line)
                if count == 0: pc = item[1]
                else: self.repeats.append([int(count), pc])
            elif op == "REPEAT_NEXT":
                if not self.repeats: raise CoreBytecodeError("repeat stack underflow")
                frame = self.repeats[-1]
                frame[0] -= 1
                if frame[0] > 0: pc = item[1]
                else: self.repeats.pop()
        return "\n".join(self.output) + ("\n" if self.output else "")


def compile_source(source):
    try:
        return Compiler().compile(core.parse(source))
    except core.PlainlyCoreError:
        raise
    except CoreBytecodeError:
        raise
    except Exception as exc:
        raise CoreBytecodeError("could not compile Plainly core source: %s" % exc) from None


def run_source(source, max_steps=core.MAX_STEPS):
    return VirtualMachine(max_steps).run(compile_source(source))


def compile_file(source_path, output_path=None):
    source = core.read_source_file(source_path)
    blob = dumps(compile_source(source))
    if output_path is None:
        output_path = os.path.splitext(source_path)[0] + ".core.pbc"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(output_path, flags, 0o600)
    except FileExistsError:
        raise CoreBytecodeError("refusing to overwrite existing bytecode: " + output_path) from None
    except OSError:
        raise CoreBytecodeError("could not safely create bytecode output") from None
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(blob)
    except BaseException:
        try: os.unlink(output_path)
        except OSError: pass
        raise
    return output_path


def run_file(path, max_steps=core.MAX_STEPS):
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow and os.path.islink(path):
        raise CoreBytecodeError("symbolic links are not allowed for bytecode input")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0) | nofollow
    try:
        fd = os.open(path, flags)
    except OSError:
        raise CoreBytecodeError("could not safely open bytecode file") from None
    try:
        import stat
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BLOB + 46:
            raise CoreBytecodeError("bytecode path must be a regular, unlinked file within the size limit")
        chunks = []
        total = 0
        while True:
            chunk = os.read(fd, min(65536, MAX_BLOB + 47 - total))
            if not chunk: break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_BLOB + 46: raise CoreBytecodeError("bytecode file is too large")
    finally:
        os.close(fd)
    return VirtualMachine(max_steps).run(loads(b"".join(chunks)))


__all__ = ["CoreBytecodeError", "Compiler", "VirtualMachine", "compile_source", "run_source", "dumps", "loads", "compile_file", "run_file"]
