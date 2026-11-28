# Changelog

## 1.5.0

- Start the independent Plainly core with its own tokenizer, parser, AST, and interpreter.
- Add core-run and core-check commands without routing independent-core source through generated Python, JavaScript, or C.
- Support variables, reassignment, numbers, text, yes/no values, lists, arithmetic, comparisons, boolean logic, conditions, while loops, repeat loops, and selected built-ins in the core preview.
- Add UTF-8 source handling, descriptor-based no-follow file loading where supported, bounded reads, and strict regular-file checks.
- Add validated instruction budgets, aggregate variable/value/text limits, and cumulative output limits.
- Add independent core regression tests and CI coverage.
- Document the core grammar, limitations, security boundary, and long-term compiler, WebAssembly, frontend, backend, and package-manager roadmap.
- Keep the legacy 1.4 commands available while the new core is incomplete; the default run command has not yet migrated.


## 1.4.0

- Add secure-default cross-platform app/game project manifests for Android, iOS, Windows, Linux, and macOS target declarations.
- Add `plainly init app|game NAME` project scaffolding and `plainly project-check` validation commands.
- Reject duplicate manifest keys, unknown fields/capabilities/targets, unsafe entry paths, symlinked or hard-linked project inputs, and oversized project files.
- Add project security regression tests and CI coverage.
- Document that native mobile/desktop packaging and game engine APIs remain planned work, not shipped features.


## Unreleased

- Make beginner editor helper setup tolerate lightweight DOM environments without optional selector APIs.
- Correct the existing bytecode list-access test's expected newline characters.

- Correct an accidental literal newline in the browser editor script so its regression check can parse the page.
- Correct newline escaping in the new independent-core regression tests.

- Allow up to six words in independent-core variable names, bringing its naming style closer to the existing Plainly language.
- Add `show`, `display`, and `print` as aliases for the independent core's `say` output statement.
- Extend interpreter and bytecode regression coverage for multi-word names and output aliases.

- Run deterministic core fuzz cases and independent core bytecode CLI regression tests in the full Windows/macOS/Linux audit matrix.
- Add the independent core AST-to-bytecode VM module and its differential, malformed-file, and execution-budget tests to the full cross-platform audit workflow and documented local test commands.
- Add an independent AST-to-bytecode compiler for the Plainly core, with a bounded stack VM and a checksummed versioned `.core.pbc` container.
- Add `core-compile` and `core-execute` CLI commands without using Python's AST module or generated Python code.
- Add differential compiler/VM tests for arithmetic, conditions, loops, lists, built-ins, short-circuit logic, Unicode, malformed bytecode, tampering, and execution limits.
- Harden bytecode validation against duplicate JSON keys, early HALT instructions, invalid jumps, malformed operands, and unsafe numeric values.
- Extend the Windows, macOS, and Linux CI matrix to compile, test, and execute independent core bytecode samples.
- Add a documented independent-core threat model and deterministic seeded source/bytecode fuzz regression tests, executed on every CI platform.
- Add subprocess-level CLI regression tests for compilation from another working directory, clean source-error reporting, and refusal to overwrite existing bytecode.


- Pin the separate cross-platform CI workflow to Ubuntu 24.04, Windows Server 2022, and macOS 15 so runner-image changes do not silently break Python compatibility jobs.
- Avoid reverse-DNS lookups during HTTP server startup; the listener now uses its numeric bound address for server metadata, preventing macOS startup hangs without requiring DNS.
- Make Discord bot shutdown responsive to provider stop events instead of waiting for a full Gateway heartbeat interval.
- Validate hosting process stop timeouts and reject booleans, non-finite values, strings, negative values, and excessive waits.
- Add regression coverage for prompt Discord shutdown and invalid provider stop timeouts.

- Add opt-in macOS stack dumps when the local server integration test cannot bring up its listener.
- Add opt-in server startup diagnostics to help troubleshoot platform-specific listener startup issues.
- Correct HTTP CRLF framing in the cross-platform hosting integration test and make server access logging safe for malformed requests.
- Use direct TCP loopback requests in hosting integration tests and capture macOS child-process/listener diagnostics on failure.
- Improve cross-platform local hosting readiness checks with shorter retries, a longer startup allowance, unbuffered child output, and actionable failure diagnostics.
- Make local HTTP integration tests bypass inherited proxy settings so loopback checks work consistently on macOS, Windows, and Linux.
- Move macOS CI jobs from the retired `macos-14` runner to the supported `macos-15` runner.
- Extend automated compatibility checks across Windows, macOS, and Linux for supported Python versions and the browser test suite.
- Build and run the native sample with GCC/Clang-compatible toolchains on Windows, macOS, and Linux.
- Add the Windows `.exe` suffix to native output names and improve the PowerShell run hint.
- Repair malformed Markdown line breaks in the 1.5.0 security, language specification, README, and changelog sections.

- Correct Discord Gateway heartbeat timing and require heartbeat acknowledgements before the next scheduled heartbeat.
- Reconnect when Discord requests a new Gateway session and disable automatic mention parsing in bot replies.
- Extend mocked integration coverage for the safe Discord message payload.


## 1.3.0

- Add basic Discord Gateway and Telegram Bot API text-message integrations with per-app token environment variables.
- Add Plainly bot permission statements, message fields, reply handlers, and bot start statements.
- Add provider-configurable website bind address, port override, hostname allowlist, and /healthz endpoint.
- Add plainly_host.py, a per-app child-process adapter with status, logs, stop operations, and a reduced child environment.
- Add mocked bot integration tests and hosting/provider lifecycle tests.
- Document provider integration requirements and the external OS/container isolation still required before accepting untrusted programs.

## 1.2.0

- Add a versioned binary `.pbc` bytecode format and a dedicated Plainly virtual machine.
- Add `plainly compile` and `plainly execute` commands.
- Support calculations, text, booleans, conditions, loops, lists, functions, and selected built-in helpers in bytecode version 1.
- Add bytecode format validation, checksums, execution limits, and automated regression tests.


## 1.1.1

- Reject symbolic links, hard-linked files, and non-regular files in permitted runtime file access.
- Add focused security regression tests and CI checks for Python, browser, and native paths.
- Publish security boundaries, known limitations, and audit deployment guidance.


## 1.1.0

- Easier text: it ends by itself before `followed by`, `joined to`, `that asks` and `and the words`.
- `contains` checks text for words, ignoring capital letters, so rule-based chatbots are possible.
- Eight lessons in the browser version, six as files, and a chatbot example for the server.
- Plainly offers to fix a fixable problem and run the program in one step.

## 1.0.0

First public release.

- Plain English language with numbers, text, yes or no values, lists, records, functions and loops.
- Checks types and permissions before running. No null: missing values are `maybe`.
- `run` mode, and a fast `native` mode that compiles to C.
- Websites: a real server, pages, boxes and buttons that talk to the server, and a memory that lasts between visits.
- Browser version with live pages and nothing to install.
- Names can use any words; symbols are allowed inside text.
- `fix` command and a Fix it button that repair common mistakes (never permissions).
- Test suites for the Python and browser versions.
