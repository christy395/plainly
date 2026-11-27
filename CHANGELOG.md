# Changelog

## 1.4.0

- Add secure-default cross-platform app/game project manifests for Android, iOS, Windows, Linux, and macOS target declarations.
- Add `plainly init app|game NAME` project scaffolding and `plainly project-check` validation commands.
- Reject duplicate manifest keys, unknown fields/capabilities/targets, unsafe entry paths, symlinked or hard-linked project inputs, and oversized project files.
- Add project security regression tests and CI coverage.
- Document that native mobile/desktop packaging and game engine APIs remain planned work, not shipped features.


## Unreleased

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
