# Plainly language specification — Core 0.1

This document specifies the independent Plainly core interpreter introduced in 1.5.0. It is a deliberately small foundation, not a claim that all planned Plainly features already exist.

## Design goals

- Plainly source is interpreted by Plainly's own tokenizer, parser, abstract syntax tree, and runtime.
- This core does not translate programs into Python, JavaScript, or C.
- Syntax should remain readable and English-oriented.
- Invalid operations should produce source-line diagnostics.
- Program execution must have explicit source, parser, numeric, collection, text, and instruction limits.
- Filesystem, network, process, browser, and native capabilities are not available in this core.

## Source format

A source file uses UTF-8 and the .plain extension. Each statement occupies one line. A hash (#) begins a comment outside a quoted string. A note line is ignored by the interpreter and can be used for a human-readable note.

Names currently use ASCII letters, digits, and underscores, and must begin with a letter or underscore. Names are case-sensitive. Multi-word names are not yet supported in the independent core.

## Statements

Declare a value once:

~~~plain
let score be 10
~~~

Change an existing value:

~~~plain
set score to score plus 5
~~~

Display a value:

~~~plain
say score
say "Hello from Plainly"
~~~

Choose a branch:

~~~plain
if score is at least 15 then
say "Passed"
otherwise
say "Try again"
end if
~~~

Repeat while a yes/no condition is true:

~~~plain
while score is less than 20 do
set score to score plus 1
end while
~~~

Repeat a fixed number of times:

~~~plain
repeat 3 times do
say "Hello"
end repeat
~~~

Declarations currently use one program-wide variable environment. Declare loop variables before a loop and update them with set.

## Values and expressions

The core supports numbers, text, yes/no values, and lists. List values use square brackets and comma-separated expressions:

~~~plain
let scores be [12, 18, 9]
say length(scores)
say largest(scores)
~~~

String literals use double quotes and JSON-compatible escapes. Unicode text is preserved.

Operators include:

| Operation | Supported spellings |
|---|---|
| Add | +, plus |
| Subtract | -, minus |
| Multiply | *, times |
| Divide | /, divided by |
| Floor divide | // |
| Remainder | % |
| Power | ** |
| Equal | ==, is, equals, is equal to |
| Not equal | !=, is not equal to, not equal to |
| Less / at most | <, less than, is less than, <=, at most, is at most |
| Greater / at least | >, greater than, is greater than, >=, at least, is at least |
| Boolean | and, or, not |

Parentheses group expressions. The and and or operators short-circuit. Conditions must evaluate to yes/no values. Numbers and text cannot be mixed in arithmetic; + joins two text values.

The first core includes these built-in functions:

- length(value) accepts text or a list.
- sqrt(number) returns the square root of a non-negative number.
- absolute(number) returns the absolute value.
- largest(list) and smallest(list) accept non-empty lists of numbers.

Function declarations, user-defined functions, records, nullable/maybe values, modules, imports, exceptions, asynchronous tasks, and static type declarations are not implemented in this core yet.

## Current core limits

| Limit | Value |
|---|---:|
| Source file | 1 MiB |
| Source lines | 100,000 |
| Characters per line | 8,192 |
| Tokens | 50,000 |
| Expression / block nesting | 128 |
| Execution steps | 100,000 |
| Repeat count | 100,000 |
| List items | 10,000 |
| Text value / output | 1 MiB |
| Numeric magnitude | 10^100 |

Limits are defense-in-depth against accidental resource exhaustion. They do not turn the interpreter into a secure sandbox.

## Run and check

The independent core has separate commands while compatibility work continues:

~~~sh
plainly core-check hello.plain
plainly core-run hello.plain
~~~

The existing run, check, build, c, native, compile, and execute commands are legacy execution paths for the larger 1.4 language. In particular, the legacy run path still uses the existing Python-based implementation. It has not yet been replaced because the independent core does not yet implement the complete legacy language. Do not mistake the new core preview for full feature parity.

## Security boundary

The core runtime has no file, network, process, browser, native-extension, or dynamic-import statements. It does not execute source strings or generate code for another language. It still runs inside the host Python process, and parser/runtime defects are possible. It is not an OS sandbox and must not be used to host untrusted multi-tenant code. Use OS-level isolation, least privilege, quotas, and independent security review for hosted workloads.
