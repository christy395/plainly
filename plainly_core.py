#!/usr/bin/env python3
"""Independent Plainly language core.

This module deliberately does not generate or execute Python, JavaScript, or C.
It tokenizes Plainly source, parses it into a Plainly AST, and interprets that AST.
The first core release is intentionally small; see LANGUAGE_SPEC.md.
"""
import json
import math
import re
from dataclasses import dataclass

VERSION = "0.1.0"
MAX_SOURCE_BYTES = 1024 * 1024
MAX_LINE_LENGTH = 8192
MAX_SOURCE_LINES = 100000
MAX_TOKENS = 50000
MAX_AST_DEPTH = 128
MAX_STEPS = 100000
MAX_REPEAT = 100000
MAX_COLLECTION_ITEMS = 10000
MAX_TEXT_LENGTH = 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_VARIABLES = 10000
MAX_RUNTIME_VALUES = 100000
MAX_NUMBER_MAGNITUDE = 1e100

_TOKEN = re.compile(
    r'\s*(?:(?P<number>(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))'
    r'|(?P<string>"(?:\\.|[^"\\])*")'
    r'|(?P<identifier>[A-Za-z_][A-Za-z0-9_]*)'
    r'|(?P<operator>==|!=|<=|>=|\*\*|//|[()+\-*/%<>=,\[\]]))'
)


class PlainlyCoreError(Exception):
    """A source, parsing, or execution error with an optional source line."""
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self):
        return ("line %d: " % self.line if self.line else "") + self.message


@dataclass(frozen=True)
class Token:
    value: str
    kind: str
    line: int


@dataclass(frozen=True)
class Expr:
    kind: str
    value: object
    children: tuple
    line: int


@dataclass(frozen=True)
class Statement:
    kind: str
    value: object
    expression: object
    body: tuple
    alternate: tuple
    line: int


@dataclass(frozen=True)
class Program:
    statements: tuple


def tokenize(source):
    if not isinstance(source, str):
        raise PlainlyCoreError("source must be text")
    try:
        size = len(source.encode("utf-8"))
    except UnicodeEncodeError:
        raise PlainlyCoreError("source contains invalid Unicode")
    if size > MAX_SOURCE_BYTES:
        raise PlainlyCoreError("source is larger than the 1 MiB limit")

    if source.count("\n") + source.count("\r") > MAX_SOURCE_LINES * 2:
        raise PlainlyCoreError("source contains too many lines")
    result = []
    token_count = 0
    for line_no, raw in enumerate(source.splitlines(), 1):
        if len(raw) > MAX_LINE_LENGTH:
            raise PlainlyCoreError("line is longer than the 8192-character limit", line_no)
        # A hash starts a comment only outside a quoted string.
        text = []
        quoted = False
        escaped = False
        for char in raw:
            if quoted:
                text.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                text.append(char)
            elif char == "#":
                break
            else:
                text.append(char)
        raw = "".join(text)
        pos = 0
        line_tokens = []
        while pos < len(raw):
            if raw[pos:].strip() == "":
                break
            match = _TOKEN.match(raw, pos)
            if not match:
                raise PlainlyCoreError("unexpected character %r" % raw[pos], line_no)
            kind = match.lastgroup
            value = match.group(kind)
            if kind == "string":
                try:
                    decoded = json.loads(value)
                except (ValueError, TypeError):
                    raise PlainlyCoreError("invalid string escape", line_no)
                try:
                    decoded_size = len(decoded.encode("utf-8"))
                except UnicodeEncodeError:
                    raise PlainlyCoreError("string contains invalid Unicode", line_no)
                if decoded_size > MAX_TEXT_LENGTH:
                    raise PlainlyCoreError("text value is too large", line_no)
                line_tokens.append(Token(decoded, "string", line_no))
            else:
                line_tokens.append(Token(value, kind, line_no))
            pos = match.end()
        token_count += len(line_tokens)
        if token_count > MAX_TOKENS:
            raise PlainlyCoreError("program contains too many tokens", line_no)
        if line_tokens:
            result.append(tuple(line_tokens))
    return tuple(result)


class ExpressionParser:
    """Pratt parser for Plainly expressions."""
    PRECEDENCE = {
        "or": 1, "and": 2,
        "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3,
        "+": 4, "-": 4, "*": 5, "/": 5, "//": 5, "%": 5, "**": 6,
    }

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self, offset=0):
        index = self.pos + offset
        return self.tokens[index] if index < len(self.tokens) else None

    def take(self):
        token = self.current()
        if token is None:
            return None
        self.pos += 1
        return token

    def accept(self, value):
        token = self.current()
        if token and token.value.lower() == value:
            self.pos += 1
            return True
        return False

    def operator(self):
        token = self.current()
        if token is None:
            return None, 0
        word = token.value.lower()
        # English aliases are part of Plainly's syntax, not a JavaScript layer.
        phrases = (
            (("is", "not", "equal", "to"), "!="),
            (("not", "equal", "to"), "!="),
            (("is", "less", "than"), "<"),
            (("less", "than"), "<"),
            (("is", "at", "most"), "<="),
            (("at", "most"), "<="),
            (("is", "greater", "than"), ">"),
            (("greater", "than"), ">"),
            (("is", "at", "least"), ">="),
            (("at", "least"), ">="),
            (("is", "equal", "to"), "=="),
            (("divided", "by"), "/"),
        )
        for phrase, op in phrases:
            if all(self.current(i) and self.current(i).value.lower() == part
                   for i, part in enumerate(phrase)):
                return op, len(phrase)
        aliases = {
            "is": "==", "equals": "==", "equal": "==",
            "plus": "+", "minus": "-", "times": "*",
            "and": "and", "or": "or",
        }
        if word in aliases:
            return aliases[word], 1
        if token.kind == "operator" and word in self.PRECEDENCE:
            return word, 1
        return None, 0

    def expression(self, minimum=0, depth=0):
        if depth > MAX_AST_DEPTH:
            line = self.current().line if self.current() else None
            raise PlainlyCoreError("expression nesting is too deep", line)
        token = self.take()
        if token is None:
            raise PlainlyCoreError("expected an expression")
        word = token.value.lower()
        if token.kind == "number":
            if len(token.value) > 128:
                raise PlainlyCoreError("number literal is too long", token.line)
            value = float(token.value) if "." in token.value else int(token.value)
            left = Expr("literal", value, (), token.line)
        elif token.kind == "string":
            left = Expr("literal", token.value, (), token.line)
        elif token.kind == "identifier" and word in ("yes", "true", "no", "false"):
            left = Expr("literal", word in ("yes", "true"), (), token.line)
        elif token.kind == "identifier" and word == "not":
            child = self.expression(3, depth + 1)
            left = Expr("unary", "not", (child,), token.line)
        elif token.value == "-":
            child = self.expression(6, depth + 1)
            left = Expr("unary", "-", (child,), token.line)
        elif token.value == "(":
            left = self.expression(0, depth + 1)
            if not self.accept(")"):
                raise PlainlyCoreError("expected ')' to close the expression", token.line)
        elif token.value == "[":
            items = []
            if not self.accept("]"):
                while True:
                    items.append(self.expression(0, depth + 1))
                    if self.accept("]"):
                        break
                    if not self.accept(","):
                        raise PlainlyCoreError("expected ',' or ']' in the list", token.line)
                    if len(items) >= MAX_COLLECTION_ITEMS:
                        raise PlainlyCoreError("list literal contains too many items", token.line)
            left = Expr("list", None, tuple(items), token.line)
        elif token.kind == "identifier":
            if self.accept("("):
                args = []
                if not self.accept(")"):
                    while True:
                        args.append(self.expression(0, depth + 1))
                        if self.accept(")"):
                            break
                        if not self.accept(","):
                            raise PlainlyCoreError("expected ',' or ')' after function input", token.line)
                        if len(args) >= 16:
                            raise PlainlyCoreError("a function call may have at most 16 inputs", token.line)
                left = Expr("call", word, tuple(args), token.line)
            else:
                left = Expr("name", token.value, (), token.line)
        else:
            raise PlainlyCoreError("expected a number, text, yes/no value, name, or '('", token.line)

        while True:
            op, consumed = self.operator()
            if op is None:
                break
            precedence = self.PRECEDENCE[op]
            if precedence < minimum:
                break
            line = self.current().line
            self.pos += consumed
            # Exponentiation is right-associative; other operators are left-associative.
            right = self.expression(precedence if op == "**" else precedence + 1, depth + 1)
            left = Expr("binary", op, (left, right), line)
        return left

    def finish(self):
        result = self.expression()
        if self.current() is not None:
            token = self.current()
            raise PlainlyCoreError("unexpected %r after the expression" % token.value, token.line)
        return result


class Parser:
    def __init__(self, lines):
        self.lines = lines
        self.pos = 0
        self.statement_count = 0

    def peek(self):
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def line_text(self, tokens):
        return [t.value.lower() if t.kind == "identifier" else t.value for t in tokens]

    def expression(self, tokens):
        if not tokens:
            raise PlainlyCoreError("expected an expression")
        return ExpressionParser(tokens).finish()

    def block(self, stop_words=(), depth=0):
        if depth > MAX_AST_DEPTH:
            token = self.peek()[0] if self.peek() else None
            raise PlainlyCoreError("block nesting is too deep", token.line if token else None)
        result = []
        while self.pos < len(self.lines):
            tokens = self.peek()
            words = self.line_text(tokens)
            first = words[0]
            if first in stop_words or (len(words) >= 2 and words[0] == "end"):
                break
            self.pos += 1
            self.statement_count += 1
            if self.statement_count > MAX_TOKENS:
                raise PlainlyCoreError("program contains too many statements", tokens[0].line)
            line = tokens[0].line

            if first == "note":
                continue
            if first == "let":
                if len(tokens) < 4 or tokens[1].kind != "identifier" or words[2] != "be":
                    raise PlainlyCoreError("use: let name be expression", line)
                result.append(Statement("let", tokens[1].value, self.expression(tokens[3:]), (), (), line))
            elif first == "set":
                if len(tokens) < 4 or tokens[1].kind != "identifier" or words[2] != "to":
                    raise PlainlyCoreError("use: set name to expression", line)
                result.append(Statement("set", tokens[1].value, self.expression(tokens[3:]), (), (), line))
            elif first == "say":
                result.append(Statement("say", None, self.expression(tokens[1:]), (), (), line))
            elif first == "if":
                if len(tokens) < 3 or words[-1] != "then":
                    raise PlainlyCoreError("use: if expression then", line)
                condition = self.expression(tokens[1:-1])
                body = self.block(("otherwise",), depth + 1)
                alternate = ()
                if self.peek() and self.line_text(self.peek())[0] == "otherwise":
                    other = self.peek()
                    if len(other) != 1:
                        raise PlainlyCoreError("'otherwise' must be on its own line", other[0].line)
                    self.pos += 1
                    alternate = self.block(depth=depth + 1)
                if not self.peek() or self.line_text(self.peek()) != ["end", "if"]:
                    raise PlainlyCoreError("if block needs 'end if'", line)
                self.pos += 1
                result.append(Statement("if", None, condition, tuple(body), tuple(alternate), line))
            elif first == "while":
                if len(tokens) < 3 or words[-1] != "do":
                    raise PlainlyCoreError("use: while expression do", line)
                condition = self.expression(tokens[1:-1])
                body = self.block(depth=depth + 1)
                if not self.peek() or self.line_text(self.peek()) != ["end", "while"]:
                    raise PlainlyCoreError("while block needs 'end while'", line)
                self.pos += 1
                result.append(Statement("while", None, condition, tuple(body), (), line))
            elif first == "repeat":
                if len(tokens) < 4 or words[-2:] != ["times", "do"]:
                    raise PlainlyCoreError("use: repeat number times do", line)
                count = self.expression(tokens[1:-2])
                body = self.block(depth=depth + 1)
                if not self.peek() or self.line_text(self.peek()) != ["end", "repeat"]:
                    raise PlainlyCoreError("repeat block needs 'end repeat'", line)
                self.pos += 1
                result.append(Statement("repeat", None, count, tuple(body), (), line))
            elif first == "otherwise" or first == "end":
                raise PlainlyCoreError("unexpected block ending", line)
            else:
                raise PlainlyCoreError("unknown statement %r" % tokens[0].value, line)
        return result

    def parse(self):
        statements = self.block()
        if self.pos != len(self.lines):
            token = self.peek()[0]
            raise PlainlyCoreError("unexpected block ending", token.line)
        return Program(tuple(statements))


def parse(source):
    return Parser(tokenize(source)).parse()


def _show(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else "%.12g" % value
    if isinstance(value, list):
        return "[" + ", ".join(_show(item) for item in value) + "]"
    return str(value)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class Interpreter:
    def __init__(self, output=None, max_steps=MAX_STEPS):
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= MAX_STEPS:
            raise PlainlyCoreError("execution budget must be an integer from 1 to %d" % MAX_STEPS)
        self.variables = {}
        self.output = output if output is not None else []
        self.output_bytes = 0
        self.steps = max_steps

    def tick(self, line):
        self.steps -= 1
        if self.steps < 0:
            raise PlainlyCoreError("execution step limit exceeded", line)

    def checked_number(self, value, line):
        if not _is_number(value):
            raise PlainlyCoreError("this operation needs numbers", line)
        try:
            finite = math.isfinite(float(value))
        except (OverflowError, ValueError):
            finite = False
        if not finite or abs(value) > MAX_NUMBER_MAGNITUDE:
            raise PlainlyCoreError("number is outside the supported range", line)
        return value

    def store_value(self, name, value, line, is_new):
        if is_new and len(self.variables) >= MAX_VARIABLES:
            raise PlainlyCoreError("program declares too many variables", line)
        pending = [value] + [v for key, v in self.variables.items() if key != name]
        total = 0
        text_bytes = 0
        while pending:
            current = pending.pop()
            total += 1
            if total > MAX_RUNTIME_VALUES:
                raise PlainlyCoreError("runtime value limit exceeded", line)
            if isinstance(current, str):
                text_bytes += len(current.encode("utf-8"))
                if text_bytes > MAX_TEXT_LENGTH:
                    raise PlainlyCoreError("combined runtime text limit exceeded", line)
            elif isinstance(current, list):
                if len(current) > MAX_COLLECTION_ITEMS:
                    raise PlainlyCoreError("list contains too many items", line)
                pending.extend(current)
            elif _is_number(current):
                self.checked_number(current, line)
            elif not isinstance(current, bool):
                raise PlainlyCoreError("unsupported runtime value", line)
        self.variables[name] = value

    def evaluate(self, expr):
        self.tick(expr.line)
        kind, value = expr.kind, expr.value
        if kind == "literal":
            return self.checked_number(value, expr.line) if _is_number(value) else value
        if kind == "name":
            if value not in self.variables:
                raise PlainlyCoreError("unknown name %r" % value, expr.line)
            return self.variables[value]
        if kind == "list":
            return [self.evaluate(item) for item in expr.children]
        if kind == "unary":
            child = self.evaluate(expr.children[0])
            if value == "not":
                if not isinstance(child, bool):
                    raise PlainlyCoreError("'not' needs a yes/no value", expr.line)
                return not child
            return self.checked_number(-self.checked_number(child, expr.line), expr.line)
        if kind == "call":
            args = [self.evaluate(item) for item in expr.children]
            if value == "length" and len(args) == 1 and isinstance(args[0], (str, list)):
                return len(args[0])
            if value == "sqrt" and len(args) == 1:
                number = self.checked_number(args[0], expr.line)
                if number < 0:
                    raise PlainlyCoreError("square root needs a non-negative number", expr.line)
                return self.checked_number(math.sqrt(number), expr.line)
            if value == "absolute" and len(args) == 1:
                return self.checked_number(abs(self.checked_number(args[0], expr.line)), expr.line)
            if value in ("largest", "smallest") and len(args) == 1 and isinstance(args[0], list):
                if not args[0]:
                    raise PlainlyCoreError(value + " needs a non-empty list", expr.line)
                if not all(_is_number(item) for item in args[0]):
                    raise PlainlyCoreError(value + " needs a list of numbers", expr.line)
                result = max(args[0]) if value == "largest" else min(args[0])
                return self.checked_number(result, expr.line)
            raise PlainlyCoreError("unknown function or wrong inputs for %r" % value, expr.line)

        left = self.evaluate(expr.children[0])
        # Keep boolean operators short-circuiting.
        if value == "and":
            if not isinstance(left, bool):
                raise PlainlyCoreError("'and' needs yes/no values", expr.line)
            return False if not left else self._boolean(self.evaluate(expr.children[1]), expr.line)
        if value == "or":
            if not isinstance(left, bool):
                raise PlainlyCoreError("'or' needs yes/no values", expr.line)
            return True if left else self._boolean(self.evaluate(expr.children[1]), expr.line)
        right = self.evaluate(expr.children[1])

        if value in ("+", "-", "*", "/", "//", "%", "**"):
            if value == "+" and isinstance(left, str) and isinstance(right, str):
                result = left + right
                if len(result.encode("utf-8")) > MAX_TEXT_LENGTH:
                    raise PlainlyCoreError("text result is too large", expr.line)
                return result
            a = self.checked_number(left, expr.line)
            b = self.checked_number(right, expr.line)
            if value in ("/", "//", "%") and b == 0:
                raise PlainlyCoreError("division by zero", expr.line)
            try:
                if value == "+": result = a + b
                elif value == "-": result = a - b
                elif value == "*":
                    if abs(a) > 1e50 or abs(b) > 1e50:
                        raise PlainlyCoreError("multiplication inputs are too large", expr.line)
                    result = a * b
                elif value == "/": result = a / b
                elif value == "//": result = a // b
                elif value == "%": result = a % b
                else:
                    if abs(b) > 10000:
                        raise PlainlyCoreError("exponent is too large", expr.line)
                    result = a ** b
            except (OverflowError, ValueError, ZeroDivisionError):
                raise PlainlyCoreError("the calculation is outside the supported range", expr.line)
            return self.checked_number(result, expr.line)

        if value in ("==", "!="):
            if type(left) is not type(right) and not (_is_number(left) and _is_number(right)):
                equal = False
            else:
                equal = left == right
            return equal if value == "==" else not equal
        if value in ("<", "<=", ">", ">="):
            if type(left) is not type(right) and not (_is_number(left) and _is_number(right)):
                raise PlainlyCoreError("comparison values must have matching types", expr.line)
            if not (_is_number(left) or isinstance(left, str)):
                raise PlainlyCoreError("these values cannot be ordered", expr.line)
            return {"<": left < right, "<=": left <= right,
                    ">": left > right, ">=": left >= right}[value]
        raise PlainlyCoreError("unsupported operation", expr.line)

    def _boolean(self, value, line):
        if not isinstance(value, bool):
            raise PlainlyCoreError("condition needs a yes/no value", line)
        return value

    def execute_block(self, statements):
        for statement in statements:
            self.tick(statement.line)
            kind = statement.kind
            if kind == "let":
                if statement.value in self.variables:
                    raise PlainlyCoreError("name %r has already been declared" % statement.value, statement.line)
                value = self.evaluate(statement.expression)
                self.store_value(statement.value, value, statement.line, True)
            elif kind == "set":
                if statement.value not in self.variables:
                    raise PlainlyCoreError("cannot set unknown name %r" % statement.value, statement.line)
                value = self.evaluate(statement.expression)
                self.store_value(statement.value, value, statement.line, False)
            elif kind == "say":
                value = _show(self.evaluate(statement.expression))
                output_size = len(value.encode("utf-8")) + 1
                if output_size > MAX_OUTPUT_BYTES - self.output_bytes:
                    raise PlainlyCoreError("program output exceeded the 1 MiB limit", statement.line)
                self.output_bytes += output_size
                self.output.append(value)
            elif kind == "if":
                condition = self._boolean(self.evaluate(statement.expression), statement.line)
                self.execute_block(statement.body if condition else statement.alternate)
            elif kind == "while":
                while self._boolean(self.evaluate(statement.expression), statement.line):
                    self.execute_block(statement.body)
            elif kind == "repeat":
                count = self.evaluate(statement.expression)
                if not _is_number(count) or int(count) != count or count < 0 or count > MAX_REPEAT:
                    raise PlainlyCoreError("repeat needs a whole number from 0 to %d" % MAX_REPEAT, statement.line)
                for _ in range(int(count)):
                    self.tick(statement.line)
                    self.execute_block(statement.body)
            else:
                raise PlainlyCoreError("unsupported statement", statement.line)


def check_source(source):
    return parse(source)


def run_source(source, max_steps=MAX_STEPS):
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= MAX_STEPS:
        raise PlainlyCoreError("execution budget must be an integer from 1 to %d" % MAX_STEPS)
    program = parse(source)
    output = []
    Interpreter(output=output, max_steps=max_steps).execute_block(program.statements)
    return "\n".join(output) + ("\n" if output else "")


def read_source_file(path):
    import os
    import stat
    if os.path.islink(path):
        raise PlainlyCoreError("source path must not be a symbolic link")
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode):
        raise PlainlyCoreError("source path must be a regular file")
    if info.st_size > MAX_SOURCE_BYTES:
        raise PlainlyCoreError("source is larger than the 1 MiB limit")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read(MAX_SOURCE_BYTES + 1)
    except UnicodeError:
        raise PlainlyCoreError("source file must contain valid UTF-8 text")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise PlainlyCoreError("source is larger than the 1 MiB limit")
    return source


def check_file(path):
    return check_source(read_source_file(path))


def run_file(path):
    return run_source(read_source_file(path))


__all__ = [
    "VERSION", "PlainlyCoreError", "Program", "tokenize", "parse",
    "check_source", "run_source", "read_source_file", "check_file", "run_file",
]
