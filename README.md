# Plainly

**A programming language written in plain English.**

Plainly lets you write programs as instructions instead of traditional punctuation-heavy code. Its source files use the `.plain` extension.

```plain
let age be 15

if age is at least 13 then
say the words You are a teenager
otherwise
say the words You are not a teenager
end if
```

<sub>Current version: **1.1.1** · License: MIT · Status: early public release, preparing for independent security review</sub>

> **Security notice:** Plainly is a programming language and runtime, not a secure sandbox. Do not run programs from untrusted people on a machine or account that contains secrets or important data. Read [SECURITY.md](SECURITY.md) before hosting programs for other users. This project has not been independently audited.

---

## Contents

- [What Plainly can do](#what-plainly-can-do)
- [Quick start](#quick-start)
- [Your first program](#your-first-program)
- [Language guide](#language-guide)
- [Files and permissions](#files-and-permissions)
- [Remembering data](#remembering-data)
- [Building websites](#building-websites)
- [Browser editor](#browser-editor)
- [Native executable and machine code](#native-executable-and-machine-code)
- [Commands](#commands)
- [Examples in this repository](#examples-in-this-repository)
- [Tests and audit preparation](#tests-and-audit-preparation)
- [Rust and Go status](#rust-and-go-status)
- [Known limitations](#known-limitations)
- [Contributing](#contributing)

## What Plainly can do

Plainly 1.1.1 currently includes:

- English-like statements, variables, calculations, comparisons, and yes/no logic.
- Lists, records, user-defined functions, loops, and conditional blocks.
- Type checking before execution, including `maybe` values for values that might be missing.
- Friendly diagnostics that identify the line with a problem.
- A repair command for common syntax mistakes. It writes a separate fixed file and never adds file permissions automatically.
- Explicit file permissions and a small persistent memory feature.
- A local Python web server with simple pages, input boxes, buttons, and request handlers.
- A browser editor that runs its supported language subset without installing Python.
- A native compilation path for a restricted subset of the language.

The Python runtime and browser editor do not support exactly the same features. See [Known limitations](#known-limitations).

## Installation

Plainly's command-line interpreter is written in Python. **Python 3.8 or newer is required.** The browser editor is a separate option and does not require Python.

### 1. Check Python

Open a terminal (Command Prompt or PowerShell on Windows) and run:

```sh
python --version
```

On macOS or Linux, you may need:

```sh
python3 --version
```

If the command is not found, install Python 3.8 or newer from [python.org](https://www.python.org/downloads/) and enable the option to add Python to PATH on Windows.

### 2. Download Plainly

The recommended method is to clone the repository:

```sh
git clone https://github.com/christy395/plainly.git
cd plainly
```

If Git is not installed, open the repository on GitHub, choose **Code → Download ZIP**, extract the ZIP file, and open a terminal in the extracted `plainly` folder.

### 3. Install Plainly

You can run it directly from the downloaded folder without installing a package:

```sh
python plainly.py version
python plainly.py run hello.plain
```

On macOS or Linux, use `python3` if that is the Python command on your system:

```sh
python3 plainly.py version
python3 plainly.py run hello.plain
```

To install the command-line package from the repository folder, run:

```sh
python -m pip install .
```

On macOS or Linux, use `python3 -m pip install .` if needed. After installation, check it:

```sh
plainly version
plainly run hello.plain
```

If the `plainly` command is not found, the Python scripts directory may not be on PATH. You can always use `python plainly.py` from the repository folder.

### 4. Optional: create a virtual environment

A virtual environment keeps the installation separate from other Python projects.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
```

Windows Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install .
```

macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

To leave the virtual environment, run `deactivate`.

### 5. Optional tools

- **C compiler:** GCC or Clang is needed only for the existing `native` command. The command compiles the supported Plainly subset through generated C code. It is not a Plainly binary-bytecode compiler.
- **Node.js:** needed only to run the browser test file `web_test.js`.
- **Browser:** needed only to open `plainly-web.html`.

### 6. Run your first program

```sh
plainly version
plainly check hello.plain
plainly run hello.plain
```

If you have not installed the command, use `python plainly.py` (Windows) or `python3 plainly.py` (macOS/Linux) instead.

### Installation troubleshooting

| Problem | What to try |
|---|---|
| `python` is not recognized | Install Python and enable PATH, or try `py` on Windows / `python3` on macOS and Linux. |
| `No module named pip` | Repair the Python installation so it includes pip, then retry. |
| Permission denied during installation | Use a virtual environment as shown above; avoid system-wide administrator installs. |
| `plainly` is not recognized | Run from the repository with `python plainly.py`, or add the Python scripts directory to PATH. |
| File not found | Run the command from the folder containing the `.plain` file, or provide its path. |
| Native compilation fails | Install a compatible C compiler and ensure it is available on PATH. |


## Your first program

Create a file named `hello.plain`:

```plain
note My first Plainly program
say the words Hello, world.
let first number be 20
let second number be 22
let answer be first number plus second number
say answer
```

Run it:

```sh
python3 plainly.py run hello.plain
```

Expected output:

```text
Hello, world.
42
```

## Language guide

A Plainly program is a sequence of sentences. Put one statement on each line.

### Basic rules

1. A line beginning with `note` is a comment.
2. Blocks are closed with `end` and the block name: `end if`, `end while`, `end repeat`, `end for`, or `end define`.
3. Names can contain multiple words. The current limit is six words.
4. Plainly avoids punctuation in program syntax. Use words such as `plus`, `minus`, `times`, and `divided by`.
5. Put literal text after `the words`. Use `end words` when more of the sentence follows and the end of the text would otherwise be unclear.
6. Symbols such as quotes, brackets, parentheses, colons, semicolons, and underscores are allowed inside text, but not in normal program syntax.

### Values and types

The main types are:

| Type | Meaning | Example |
|---|---|---|
| `number` | A whole or decimal number | `let score be 42` |
| `text` | A piece of text | `let player be the words Alex` |
| `truth` | Yes or no | `let is ready be true` |
| `a list of number` | A list of numbers | `let scores be a list of 4 and 8 and 15` |
| `maybe number` | A number that may not exist | `let result be parsed number of the words 42 end words` |
| record type | A value with named fields | See [Records](#records). |

Plainly does not use a regular null value. A value that may be missing is represented by a `maybe` value and must be handled.

### Variables and calculations

```plain
let balance be 100
add 25 to balance
subtract 10 from balance
set balance to balance times 2
say balance
```

Math operators are `plus`, `minus`, `times`, `divided by`, and `modulo`.

Join text with `followed by` (adds a space) or `joined to` (does not add a space):

```plain
let player be the words Alex
say the words Welcome followed by player
```

### Conditions

```plain
let score be 82

if score is at least 90 then
say the words Excellent
otherwise if score is at least 60 then
say the words Passed
otherwise
say the words Try again
end if
```

Comparisons include `is`, `is not`, `is greater than`, `is less than`, `is at least`, and `is at most`. Combine yes/no expressions with `and`, `or`, and `not`.

### Loops and lists

```plain
let pets be a list of the words cat and the words dog and the words fish
add the words bird end words to pets

for each pet in pets do
say the words I like followed by pet
end for

say length of pets
say entry 1 of pets
```

List positions start at 1. Plainly checks that a requested position exists.

Other loop forms:

```plain
repeat 3 times do
say the words Hello
end repeat

let counter be 1
while counter is at most 3 do
say counter
add 1 to counter
end while
```

### Functions

Define a function with named inputs and a return type:

```plain
define rectangle area of width as number with height as number giving number
give back width times height
end define

say rectangle area of 5 with 4
```

Functions must be defined before they are used.

### Records

A record groups named fields:

```plain
a record called item has name as text and price as number

let apple be a new item with name the words apple end words and price 3
say name of apple
say price of apple
```

### Maybe values

A conversion can produce a value that might not exist:

```plain
let parsed be parsed number of the words 42 end words
let safe number be parsed or else 0
say safe number

if parsed has a value as actual number then
say actual number
otherwise
say the words That was not a number
end if
```

### Input and built-in helpers

- `what the user types` reads a line of text.
- `length of` returns the length of a text value or list.
- `square root of`, `absolute value of`, and `rounded of` work with numbers.
- `largest of` and `smallest of` work with number lists.
- `parsed number of` attempts to convert text into a number and returns a maybe value.

## Files and permissions

A program must declare file access before using a file:

```plain
allow reading the file prices.txt
allow writing the file report.txt

let prices be the numbers in the file prices.txt
say largest of prices
write the words Report complete end words to the file report.txt
```

The file permission syntax is an explicit language-level check. Plainly also rejects path separators, symbolic links, non-regular files, and files with multiple hard links in its runtime file helpers.

**This is not an operating-system sandbox.** Use a private working directory for each program. Do not share a writable directory between tenants, and do not put secrets in a directory that a program can access. Read [SECURITY.md](SECURITY.md).

## Remembering data

The Python runtime can save small values between runs. A program must declare the memory file first:

```plain
allow remembering in the file memory.json

let visits be what I remember called visits as a number or else 0
let updated visits be visits plus 1
remember updated visits as visits
say updated visits
```

Supported saved values include numbers, text, yes/no values, and lists of those types. A program can use one memory file. The runtime limits the serialized memory data to 1 MB.

## Building websites

The Python runtime can serve a small local website. This server is intended for development and local testing. It binds to `127.0.0.1` and is not a public production web server.

Example `site.plain`:

```plain
when someone visits the path home do
show a heading with the words Welcome to my site end words
show a paragraph with the words Built in Plainly end words
reply with the page
end when

when someone visits the path hello do
let visitor name be the visitor sent name
reply with the words Hello followed by visitor name
end when

start the server on port 8099
```

Run it:

```sh
python3 plainly.py run site.plain
```

Open `http://127.0.0.1:8099` on the same machine. The server feature is deliberately limited. Do not expose it to the public internet without a separate security design and review.

## Browser editor

Open `plainly-web.html` in a modern browser. It includes lessons, a code editor, a Run button, and interactive page examples.

The browser editor runs a smaller subset than the Python interpreter. It does not support file access, persistent memory, records, maybe values, or the Python web-server feature. Browser programs cannot access local files or make arbitrary network requests.

## Native executable and machine code

The `native` command compiles a supported subset of Plainly into C source, then invokes a system C compiler to create a native executable:

```sh
python3 plainly.py native speed.plain
./speed
```

The native output is a platform-specific executable containing machine code. Plainly does not ask you to write raw binary instructions. It translates the Plainly program into C and lets GCC, Clang, or another compatible C compiler generate the executable.

The native backend currently supports numbers, text, yes/no values, number lists, functions, and control-flow statements. It does not currently support file access, records, maybe values, or the web-server feature. The native output must be treated as executable code and run only with the same isolation precautions as any other program.


**Binary bytecode status:** this repository version does not yet provide a `.pbc` bytecode format or a binary virtual machine. The existing `native` command produces a platform-specific executable through generated C. Do not use `.pbc` commands or expect binary bytecode support in this version.

## Commands

| Command | Purpose |
|---|---|
| `plainly run FILE` | Check and run a Plainly program |
| `plainly check FILE` | Check the program without running it |
| `plainly fix FILE` | Write a separate repaired file when common mistakes can be fixed |
| `plainly build FILE` | Print the generated Python |
| `plainly c FILE` | Print the generated C for the native subset |
| `plainly native FILE` | Build a native executable |
| `plainly version` | Print the language version |

The same commands can be run with `python3 plainly.py` instead of the installed `plainly` command.

## Examples in this repository

The example files are currently in the repository root:

| File | Demonstrates |
|---|---|
| `hello.plain` | First program |
| `fizz.plain` | Conditions, functions, and loops |
| `shop.plain` | Records, lists, functions, and calculations |
| `maybe.plain` | Maybe values and safe conversion |
| `files.plain` | Explicit file permissions |
| `counter.plain` | Local website and persistent memory |
| `site.plain` | Local website with two routes |
| `app.plain` | Page inputs and a server response |
| `speed.plain` | Native compilation example |

The files `discord_bot.plain` and `telegram_bot.plain` are retained as experimental drafts only. The current interpreter does not implement their bot statements; they are not working integrations and are not supported examples.

## Tests and audit preparation

Run these checks from the repository root:

```sh
python3 -m py_compile plainly.py
python3 audit_tests.py
node web_test.js
python3 plainly.py check hello.plain
python3 plainly.py run hello.plain
```

When a C compiler is installed, also test native output in a disposable environment:

```sh
python3 plainly.py native speed.plain
./speed
```

GitHub Actions runs the focused Python, browser, and native regression checks on pushes and pull requests. A passing CI run demonstrates only that these automated checks passed. **It does not mean the project passed a security audit.**

For audit scope, known limitations, safe deployment requirements, and vulnerability reporting, see [SECURITY.md](SECURITY.md).

## Rust and Go status

This release does not include Rust or Go compiler backends. The existing native path is C-based. Adding Rust or Go backends would require a separate implementation and cross-backend tests to prove that types, errors, and program behavior remain consistent. They are not being represented as implemented or audit-tested in this release.

## Known limitations

- Plainly is an early public release and has not received an independent security audit.
- The interpreter executes compiler-generated Python. The restricted built-ins are not a security sandbox.
- Runtime permissions, memory selection, and routes are module-level state. Do not run independent tenants concurrently inside one interpreter process.
- Plainly does not impose general CPU, memory, process-count, or wall-clock limits. Enforce them outside the interpreter.
- The local web server is not designed as a public multi-tenant server.
- The native compiler supports only a subset of the language and produces an executable that has the privileges of the account running it.
- The browser editor and Python runtime support different language subsets.
- Discord and Telegram bot integration is not implemented.

## Contributing

Contributions and issue reports are welcome. For language changes:

1. Keep new syntax consistent with the existing plain-English style.
2. Add regression tests for valid programs and invalid input.
3. Run the Python and browser checks before submitting a change.
4. Update this README and [CHANGELOG.md](CHANGELOG.md) when behavior or supported syntax changes.
5. Review the impact on [SECURITY.md](SECURITY.md), especially when adding file, network, process, or native-code capabilities.

Plainly is distributed under the MIT License. See [LICENSE](LICENSE).
