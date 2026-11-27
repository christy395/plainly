# Plainly binary bytecode format

This document describes the .pbc container and bytecode version 1 instruction set. The format is intentionally small, binary, versioned, and independent of Python bytecode.

## Container

All integer fields use unsigned big-endian byte order unless stated otherwise. Text is UTF-8.

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 bytes | Magic signature: PLNYBC followed by CR and LF (PLNYBC\\r\\n) |
| 8 | 2 bytes | Format version (1) |
| 10 | 4 bytes | Payload length in bytes |
| 14 | 32 bytes | SHA-256 digest of the payload |
| 46 | Variable | Payload |

The reader checks the signature, version, exact payload length, and checksum before decoding instructions. The current implementation rejects files larger than 16 MiB.

## Payload

The payload begins with a 16-bit function count. Each function entry contains:

1. Function name as a 16-bit byte length followed by UTF-8 bytes.
2. A 16-bit parameter count.
3. Each parameter name in the same length-prefixed UTF-8 form.
4. A 32-bit instruction count.
5. That many encoded instructions.

After the function entries, the payload contains a 32-bit instruction count and the main program's instructions.

Names and instruction text use a 16-bit byte length followed by UTF-8 bytes. Numeric constants use an IEEE-754 64-bit floating-point value in big-endian byte order. Jump locations are instruction indexes, not byte offsets.

## Instruction set version 1

| ID | Instruction | Operand |
|---:|---|---|
| 0 | HALT | None |
| 1 | PUSH_NUMBER | 64-bit float |
| 2 | PUSH_TEXT | 32-bit byte length + UTF-8 text |
| 3 | PUSH_BOOL | One byte (0 or 1) |
| 4 | PUSH_NONE | None |
| 5 | LOAD | Variable name |
| 6 | STORE | Variable name |
| 7 | POP | None |
| 8 | SAY | None |
| 9 | ADD | None |
| 10 | SUB | None |
| 11 | MUL | None |
| 12 | DIV | None |
| 13 | MOD | None |
| 14 | EQ | None |
| 15 | NE | None |
| 16 | LT | None |
| 17 | LE | None |
| 18 | GT | None |
| 19 | GE | None |
| 20 | NOT | None |
| 21 | JUMP | 32-bit instruction index |
| 22 | JUMP_FALSE | 32-bit instruction index |
| 23 | JUMP_TRUE | 32-bit instruction index |
| 24 | DUP | None |
| 25 | BUILD_LIST | 16-bit item count |
| 26 | APPEND | None |
| 27 | BUILTIN | Built-in name + 8-bit argument count |
| 28 | CALL | Function name + 8-bit argument count |
| 29 | RETURN | None |
| 30 | ITER_PREP | None |
| 31 | ITER_NEXT | Variable name + 32-bit exit instruction index |

The VM uses a value stack for expression evaluation. JUMP_FALSE and JUMP_TRUE pop the tested value. ITER_PREP converts the top stack value into an iterator; ITER_NEXT assigns the next item to its variable or exits when the iterator is exhausted. Function calls use isolated local variable dictionaries and share the same function table.

## Compatibility and versioning

A reader must reject unknown format versions and unknown instruction IDs. Existing opcode IDs must never be reused or assigned a different meaning. Incompatible container or instruction changes require a new format version.

Bytecode version 1 supports the feature subset listed in the README. Unsupported source-language features are rejected by the compiler. The bytecode VM does not load or execute Python source, native machine code, or operating-system commands.

The SHA-256 field detects accidental damage and tampering; it is not a digital signature and does not prove who created a bytecode file. The VM's execution limit is a guard against accidental runaway programs, not a complete security sandbox.
