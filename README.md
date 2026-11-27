# Plainly

**A programming language written in plain English.**

Plainly lets you write programs as instructions instead of traditional punctuation-heavy code. Its source files use the `.plain` extension.

```plain
let age be 15

if age is at least 13 then
say "You are a teenager"
otherwise
say "You are not a teenager"
end if
```

<sub>Current version: **1.5.0** · License: MIT · Status: early public release, preparing for independent security review</sub>

> **Security notice:** Plainly is a programming language and runtime, not a secure sandbox. Do not run programs from untrusted people on a machine or account that contains secrets or important data. Read [SECURITY.md](SECURITY.md) before hosting programs for other users. This project has not been independently audited.

---

## Contents

- [What Plainly can do](#what-plainly-can-do)
- [Independent Plainly core](#independent-plainly-core)
- [Quick start](#quick-start)
- [Your first program](#your-first-program)
- [Language guide](#language-guide)
- [Files and permissions](#files-and-permissions)
- [Remembering data](#remembering-data)
- [Building websites](#building-websites)
- [Discord and Telegram bots](#discord-and-telegram-bots)
- [Cross-platform apps and games](#cross-platform-apps-and-games)
- [Hosting provider integration](#hosting-provider-integration)
- [Browser editor](#browser-editor)
- [Native executable and machine code](#native-executable-and-machine-code)
- [Commands](#commands)
- [Examples in this repository](#examples-in-this-repository)
- [Tests and audit preparation](#tests-and-audit-preparation)
- [Rust and Go status](#rust-and-go-status)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

## What Plainly can do

The 1.5.0 repository includes the existing 1.4 language implementation and a new independent core preview:

- English-like statements, variables, calculations, comparisons, and yes/no logic.
- Lists, records, user-defined functions, loops, and conditional blocks.
- Type checking before execution, including `maybe` values for values that might be missing.
- Friendly diagnostics that identify the line with a problem.
- A repair command for common syntax mistakes. It writes a separate fixed file and never adds file permissions automatically.
- Explicit file permissions and a small persistent memory feature.
- A small Python web server with routes, pages, input boxes, buttons, and provider-configurable host/port settings.
- Basic text-message integrations for Discord and Telegram bots in the Python runtime.
- A secure-by-default project manifest and app/game scaffolder with Android, iOS, Windows, Linux, and macOS target declarations.
- A provider process adapter for starting, stopping, checking, and reading logs from individual Plainly app processes.
- A browser editor that runs its supported language subset without installing Python.
- A native compilation path for a restricted subset of the legacy language.
- An independent Plainly core with its own tokenizer, parser, syntax tree, and interpreter. It does not generate or execute Python, JavaScript, or C.

The existing full-featured interpreter and browser editor do not support exactly the same features. See [Known limitations](#known-limitations).

## Independent Plainly core

Plainly 1.5.0 starts a separate implementation of the language from its foundations. The independent core includes its own tokenizer, parser, abstract syntax tree, and interpreter. Programs executed by this core are not translated into Python, JavaScript, or C.

This first preview supports variables, numbers, text, yes/no values, lists, arithmetic, comparisons, boolean logic, conditions, while loops, repeat loops, and a small set of built-in functions. It includes explicit limits for source size, token count, nesting, variables, aggregate runtime values, text, collections, numeric magnitude, execution steps, and cumulative output. Source files are opened with bounded descriptor-based checks and no-follow behavior where supported. These are defense-in-depth controls, not a secure sandbox.

Try it:

~~~plain
let score be 10
set score to score plus 5
if score is at least 15 then
say "Plainly is running its own interpreter"
otherwise
say "Try again"
end if
~~~

Check and run the included example:

~~~sh
plainly core-check core_hello.plain
plainly core-run core_hello.plain
plainly core-compile core_hello.plain
plainly core-execute core_hello.core.pbc
~~~

Read the exact grammar and current limits in [LANGUAGE_SPEC.md](LANGUAGE_SPEC.md). Review the independent core's trust boundaries in [CORE_THREAT_MODEL.md](CORE_THREAT_MODEL.md).

**Important:** this is the beginning of the rebuild, not full feature parity. The older `run`, `check`, `build`, `native`, `compile`, and `execute` commands still use the 1.4 implementation. The independent core now has its own AST-to-bytecode compiler and bounded virtual machine through `core-compile` and `core-execute`. It does not yet have user-defined functions, records, modules, static type declarations, a browser target, or a production web framework. Those remain planned stages, not shipped features.

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
plainly core-check core_hello.plain
plainly core-run core_hello.plain
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

The Python runtime includes a small HTTP server. By default it binds to `127.0.0.1` for local development. Hosting providers can explicitly configure its bind address, port, and accepted Host names. The server remains a lightweight feature rather than a full production web framework.

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

Open `http://127.0.0.1:8099` on the same machine. For a provider deployment, use the assigned port and a strict hostname allowlist:

```sh
python3 plainly.py run site.plain --host 0.0.0.0 --port 8080 --allow-host site.example.com
```

The same settings can be supplied with `PORT`, `PLAINLY_HOST`, and comma-separated `PLAINLY_ALLOWED_HOSTS` environment variables. Public deployments should sit behind a provider-managed HTTPS reverse proxy. The server exposes `/healthz` for basic health checks. See [HOSTING.md](HOSTING.md) for provider setup and security requirements.

## Discord and Telegram bots

The Python interpreter includes first-version, text-based bot integrations. They let a Plainly program respond to incoming messages and send a text reply. Install the optional dependency for Discord:

```sh
python3 -m pip install ".[bots]"
```

Telegram uses Bot API long polling and does not require the optional WebSocket package. Discord uses the Gateway WebSocket and requires the Message Content Intent to be enabled for the bot application.

A Telegram example:

```plain
allow running a Telegram bot
when a Telegram message arrives do
let said be the message text
if said contains the words hello end words then
reply with the words Hello followed by the message author
otherwise
reply with the words You said followed by said
end if
end when
start the Telegram bot
```

A Discord example:

```plain
allow running a Discord bot
when a Discord message arrives do
let said be the message text
if said contains the words hello end words then
reply with the words Hello followed by the message author
end if
end when
start the Discord bot
```

Store tokens in environment secrets, never in source code:

- Telegram: `PLAINLY_SECRET_TELEGRAM_TOKEN`
- Discord: `PLAINLY_SECRET_DISCORD_TOKEN`

The current integrations handle ordinary text messages and text replies. They do not yet implement slash commands, interactions, reactions, attachments, voice, or Telegram webhooks. Read [HOSTING.md](HOSTING.md) before deploying bots.

## Running Plainly across devices and operating systems

Plainly is designed to keep its **.plain source files portable**. The current command-line interpreter runs on desktop operating systems that support Python 3.8 or newer. GitHub Actions now checks the interpreter and its regression suites on Windows, macOS, and Linux.

| Environment | Current status |
|---|---|
| Windows, macOS, Linux desktop | Command-line runtime supported when Python 3.8+ is installed; covered by CI |
| Android and iOS devices | The browser editor can be used in a compatible mobile browser; a standalone mobile runtime and installable native app packages are not available yet |
| Native executables | Build separately for each target operating system and CPU architecture with a compatible C compiler; a compiled executable is not universally portable |
| Other operating systems and CPU architectures | Not yet comprehensively tested; support must be verified on the target |

“Cross-platform” does not mean that one native executable runs everywhere. Plainly source code is the portable part; the runtime, browser capabilities, compiler toolchain, and target platform still matter. Mobile browsers and every CPU architecture are not currently covered by automated device testing.

## Cross-platform apps and games

Plainly 1.4.0 introduces a shared project format and starter-project workflow:

```sh
plainly init app MyApp
plainly init game MyGame
plainly project-check MyGame
```

Each project contains `plainly.project.json` and `main.plain`. The manifest can declare Android, iOS, Windows, Linux, and macOS as intended targets. Security capabilities default to an empty list, network access defaults to denied, filesystem access is scoped to the project, and native extensions default to disabled. The validator rejects duplicate JSON keys, unknown fields and capabilities, unsupported targets, unsafe entry paths, symlinked source files, and oversized project inputs.

**Important:** these are project-format and validation foundations, not native app/game exporters. Plainly does not yet produce Android APK/AAB files, iOS IPA files, Windows installers, Linux packages, or macOS app bundles. Native UI, graphics, audio, input, mobile packaging, signing, and platform-specific SDK adapters remain future work. See [PLATFORM_SUPPORT.md](PLATFORM_SUPPORT.md) for the exact status and build-tool requirements.

## Hosting provider integration

The `plainly_host.py` module provides a Python process adapter for a provider to integrate into its own dashboard and control plane:

```python
from plainly_host import PlainlyHost

runtime = PlainlyHost()
runtime.start(
    app_id="customer-app-123",
    program="main.plain",
    workdir="/srv/plainly/apps/customer-app-123",
    env={"PORT": "8080", "PLAINLY_HOST": "0.0.0.0",
         "PLAINLY_ALLOWED_HOSTS": "site.example.com"},
)
print(runtime.status("customer-app-123"))
print(runtime.logs("customer-app-123"))
runtime.stop("customer-app-123")
```

The adapter manages child processes; it does not supply customer accounts, billing, persistent job records, automatic recovery, resource quotas, or OS/container isolation. A provider must build those services around it. **Do not run untrusted customer programs without external container or VM isolation.** See [HOSTING.md](HOSTING.md) and [SECURITY.md](SECURITY.md).

## Browser editor

Open `plainly-web.html` in a modern browser. It includes lessons, a code editor, a Run button, and interactive page examples.

The browser editor runs a smaller subset than the Python interpreter. It does not support file access, persistent memory, records, maybe values, or the Python web-server feature. Browser programs cannot access local files or make arbitrary network requests.

## Binary bytecode (.pbc)

Plainly can compile supported programs into a versioned binary bytecode file and run them in its own virtual machine. This is separate from the existing `native` command: bytecode runs in the Plainly VM and does not require a C compiler.

Compile a program and run its bytecode:

```sh
python3 plainly.py compile hello.plain
python3 plainly.py execute hello.pbc
```

When Plainly is installed as a command, use:

```sh
plainly compile hello.plain
plainly execute hello.pbc
```

The compiler creates the `.pbc` file next to the source file. For example, compiling `hello.plain` creates `hello.pbc`. A precompiled `hello.pbc` demonstration is also included in the repository root. The file starts with the Plainly bytecode signature, includes a format version and integrity checksum, and stores VM instructions and function metadata in binary form. You can copy the `.pbc` file to another compatible Plainly installation and execute it there.

### Bytecode version 1 support

The first bytecode version supports:
- Number, text, and yes/no values, variables, and arithmetic.
- Comparisons, `and`, `or`, and `not`.
- `if` / `otherwise`, `while`, `repeat`, and `for each` loops.
- Lists, adding values to lists, and iterating over lists.
- User-defined functions, function inputs, and returned values.
- Text joining, user input, and supported numeric/list helpers.

The normal Plainly parser and type checker validate source programs before bytecode is created. The bytecode compiler then translates the checked program into VM instructions; it does not execute the generated Python. The container header, binary layout, and opcode list are documented in [BYTECODE.md](BYTECODE.md).

### Current limitations

Bytecode version 1 does not support records, maybe-value pattern matching, file access, persistent memory, web servers/pages, or Discord/Telegram bot features. The compiler reports an unsupported feature instead of pretending it was compiled. These features remain available only through the existing interpreter where implemented.

The VM limits execution to 1,000,000 instructions per run and limits nested function calls. These safeguards help stop accidental infinite loops, but bytecode is not a general-purpose security sandbox. Do not run bytecode from untrusted sources on a machine with sensitive data.

## Native executable and machine code

The `native` command compiles a supported subset of Plainly into C source, then invokes a system C compiler to create a native executable:

On Windows PowerShell:

```powershell
python plainly.py native speed.plain
.\\speed.exe
```

On macOS or Linux:

```sh
python3 plainly.py native speed.plain
./speed
```

The native output is a platform-specific executable containing machine code. Plainly does not ask you to write raw binary instructions. It translates the Plainly program into C and lets GCC, Clang, or another compatible C compiler generate the executable.

The native backend currently supports numbers, text, yes/no values, number lists, functions, and control-flow statements. It does not currently support file access, records, maybe values, or the web-server feature. The native output must be treated as executable code and run only with the same isolation precautions as any other program.


## Commands

| Command | Purpose |
|---|---|
| `plainly core-check FILE` | Parse and validate source with the independent Plainly core |
| `plainly core-run FILE` | Run source with the independent Plainly core interpreter |
| `plainly run FILE [--host ADDRESS] [--port PORT] [--allow-host DOMAIN]` | Check and run a legacy-compatible program; optional website hosting settings |
| `plainly check FILE` | Check the program without running it |
| `plainly fix FILE` | Write a separate repaired file when common mistakes can be fixed |
| `plainly build FILE` | Print generated Python for the legacy implementation |
| `plainly c FILE` | Print the generated C for the native subset |
| `plainly native FILE` | Build a native executable |
| `plainly compile FILE` | Compile supported source to a binary `.pbc` file |
| `plainly execute FILE` | Run a binary `.pbc` file in the Plainly VM |
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
| `site.plain` | Website with two routes |
| `app.plain` | Page inputs and a server response |
| `telegram_bot.plain` | Telegram text-message bot example |
| `discord_bot.plain` | Discord text-message bot example |
| `speed.plain` | Native compilation example |

The bot examples use the first-version text-message integrations described above. They require the corresponding environment secret; Discord also requires the optional bot dependency and enabled Message Content Intent.

## Tests and audit preparation

Run these checks from the repository root:

```sh
python3 -m pip install ".[bots]"
python3 -m py_compile plainly.py plainly_bytecode.py plainly_bots.py plainly_host.py plainly_project.py plainly_core.py plainly_core_bytecode.py
python3 core_tests.py
python3 core_bytecode_tests.py
python3 core_fuzz_tests.py
python3 core_bytecode_cli_tests.py
python3 audit_tests.py
python3 bytecode_tests.py
python3 plainly.py core-check core_hello.plain
python3 plainly.py core-run core_hello.plain
python3 bot_tests.py
python3 hosting_tests.py
node web_test.js
python3 plainly.py check hello.plain
python3 plainly.py run hello.plain
```

When a C compiler is installed, also test native output in a disposable environment:

```sh
python3 plainly.py native speed.plain
./speed
```

GitHub Actions runs the Python interpreter, bytecode, bot-mock, hosting adapter, browser, and native regression checks on pushes and pull requests. Bot integration tests use local mocks; they do not need real platform tokens. A passing CI run demonstrates only that these automated checks passed. **It does not mean the project passed a security audit.**

For provider deployment, see [HOSTING.md](HOSTING.md). For audit scope, known limitations, safe deployment requirements, and vulnerability reporting, see [SECURITY.md](SECURITY.md).

## Rust and Go status

This release does not include Rust or Go compiler backends. The existing native path is C-based. Adding Rust or Go backends would require a separate implementation and cross-backend tests to prove that types, errors, and program behavior remain consistent. They are not being represented as implemented or audit-tested in this release.

## Known limitations

- Plainly has not received an independent security audit and is not a secure sandbox.
- The legacy compatibility interpreter executes compiler-generated Python with the permissions of its operating-system process. The independent core directly interprets its own AST but still runs inside the host Python process.
- File permissions, memory selection, bot handlers, and website routes are process-level runtime state. Run each tenant in a separate process and private workspace.
- Plainly does not impose general CPU, memory, process-count, disk, network, or wall-clock quotas. Hosting providers must enforce these outside the runtime.
- The built-in web server is small and should sit behind a managed HTTPS reverse proxy. It is not a full production web framework or a multi-tenant application server.
- Discord and Telegram integrations currently support simple text-message handling and text replies only. They do not yet cover slash commands, interactions, reactions, attachments, voice, or Telegram webhooks.
- Bytecode v1 is a compute-only subset; it does not support files, memory, websites, or bots.
- The provider process adapter has an in-memory registry and does not implement persistent job recovery, customer authentication, billing, or OS isolation. Its stop operation validates finite timeouts, and Discord Gateway sessions poll provider stop requests during receive waits.
- The native compiler supports only a subset of the language and produces an executable with the privileges of the account running it.
- The independent core is a preview and does not yet provide static type checking, functions, records, modules, compilation, browser execution, or full feature parity with the legacy language. Its documented resource limits are not a sandbox.
- The browser editor and legacy Python runtime support different language subsets. The browser editor is the portable option on modern phones and tablets; the Python CLI is for Python-capable desktop environments, and native Android/iOS packaging remains planned.

## Roadmap

### Available in 1.5.0

- [x] Independent Plainly tokenizer, parser, AST, and interpreter preview that does not generate or execute Python, JavaScript, or C.
- [x] Dedicated core commands, documented grammar, execution limits, and regression tests for malformed source, Unicode, arithmetic errors, and runaway loops.
- [x] Keep the 1.4 language implementation available as a compatibility path while the independent core grows to feature parity.
- [x] Versioned binary .pbc format and a dedicated bytecode VM for the supported compute subset.
- [x] Provider-controlled host, port, and Host-header allowlist for the small website server.
- [x] Basic Discord and Telegram text-message bot integrations.
- [x] A Python process adapter for provider-managed app lifecycle and logs.
- [x] Local mock-based integration tests for bot and hosting behavior.
- [x] Discord Gateway heartbeat scheduling, acknowledgement checks, reconnect handling, and safe mention defaults.
- [x] Responsive browser editor viewport support for mobile browsers and graceful local-storage failure handling.
- [x] Cross-platform app/game project manifest, secure-default capability policy, scaffolding, and validation for five target families.
- [x] GitHub Actions matrix for Python regression suites on Windows, macOS, and Linux, including the independent bytecode VM, plus a separate browser-editor test job.
- [x] Cross-platform HTTP hosting integration checks use direct loopback TCP and tolerate malformed-request logging.

### Security hardening completed in 1.5.0

- [x] Validate execution budgets and enforce a hard upper bound on core interpreter steps.
- [x] Cap declared variables, aggregate runtime values, retained text, collection sizes, and cumulative output.
- [x] Use bounded descriptor-based source reads, regular-file checks, strict UTF-8 decoding, and no-follow opens where supported.
- [x] Validate file type and hard-link count before truncating a permitted file, preventing rejected hard-link writes from modifying their targets.
- [x] Add a regression test proving a rejected hard-link write leaves the linked target unchanged.
- [x] Document the independent core's trust boundaries, current mitigations, and explicit security limitations in [CORE_THREAT_MODEL.md](CORE_THREAT_MODEL.md).
- [x] Add deterministic seeded source-mutation and malformed-bytecode fuzz regression tests to the cross-platform CI matrix.
- [ ] Add long-running coverage-guided fuzzing, property-based parser tests, and an independent security review.

### Planned work

- [x] Add an independent AST-to-bytecode compiler and bounded stack virtual machine for the independent core, with checksummed `.core.pbc` files and no Python AST or generated-Python execution.
- [x] Expose `core-compile` and `core-execute` commands for independent core bytecode.
- [x] Add differential tests comparing independent interpreter and VM behavior, plus malformed/tampered bytecode and execution-budget tests.
- [ ] Add static type checking, functions, records, modules, packages, error handling, and a versioned standard library to the independent core.
- [ ] Create a browser compilation target using WebAssembly, with Plainly-owned browser APIs and no user-authored JavaScript requirement.
- [ ] Build Plainly's frontend system for page structure, styling, browser events, accessibility, and component composition.
- [ ] Add a backend and web application framework with HTTP routing, database drivers, authentication primitives, and safe secret handling.
- [ ] Build a package manager, project/build tooling, formatter, debugger, language server, and cross-platform test harness for Plainly projects.
- [ ] Migrate the full legacy language feature set to the independent implementation, then retire the generated-Python execution path.
- [ ] Production-grade container or VM isolation examples and provider-specific resource controls.
- [ ] Durable job recovery, health monitoring, metrics, quotas, and automatic restarts in a provider control plane.
- [ ] More complete bot features, including Discord interactions and Telegram webhook support.
- [ ] Native app/game runtime and build adapters for Android, iOS, Windows, Linux, and macOS.
- [ ] Shared graphics, audio, input, UI, storage, and lifecycle APIs for games and applications.
- [ ] Reproducible builds, signed artifacts, software bill of materials, and verified dependency lockfiles.
- [ ] A more capable public web runtime with stronger request controls and application lifecycle hooks.

The planned items are not implemented features. Update this section whenever runtime capabilities change.

## Contributing

Contributions and issue reports are welcome. For language changes:

1. Keep new syntax consistent with the existing plain-English style.
2. Add regression tests for valid programs and invalid input.
3. Run the Python and browser checks before submitting a change.
4. Update this README and [CHANGELOG.md](CHANGELOG.md) when behavior or supported syntax changes.
5. Review the impact on [SECURITY.md](SECURITY.md), especially when adding file, network, process, or native-code capabilities.

Plainly is distributed under the MIT License. See [LICENSE](LICENSE).
