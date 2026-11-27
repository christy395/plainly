# Plainly independent core threat model

## Scope

This document covers plainly_core.py, plainly_core_bytecode.py, and the core-* command-line paths. It does not claim that the legacy 1.4 runtime, browser editor, web server, bot adapters, or provider process adapter have the same security properties.

## Assets

- The host machine, its files, credentials, network access, and other processes.
- Integrity and availability of the Plainly compiler, bytecode decoder, and virtual machine.
- The correctness of program output and source diagnostics.
- The user's source files and compiled bytecode files.

## Trust boundaries

- Plainly source text is untrusted input.
- .core.pbc bytecode is untrusted input, even when its checksum is valid. The checksum detects accidental corruption; it is not a digital signature and does not prove who created the file.
- The compiler and VM execute inside the Python process that launches them. The independent core does not generate or execute Python source, JavaScript, or C, but its current implementation is still written in Python.
- A process boundary or VM instruction budget is not an operating-system sandbox.

## Threats and current mitigations

| Threat | Current mitigation |
|---|---|
| Oversized source | 1 MiB source limit, line/token limits |
| Parser or expression nesting exhaustion | AST and block nesting limits |
| Infinite loops or excessive instruction work | VM instruction budget |
| Oversized values and output | Variable, aggregate value, collection, text, stack, and output limits |
| Corrupt bytecode | Versioned header, exact length, SHA-256 corruption check |
| Crafted bytecode operands | Opcode allowlist, operand shape/type/range validation, jump validation |
| Duplicate JSON keys and malformed Unicode | Duplicate-key rejection and strict UTF-8/Unicode checks |
| Accidental overwrite of compiled output | Exclusive file creation; existing output is not replaced |
| Symlink/hard-link bytecode input | No-follow open where supported and regular-file/link-count checks |

## Explicit non-goals and limitations

- No filesystem, network, process, reflection, dynamic import, native-extension, or host API opcodes exist in this core VM.
- This VM does not isolate Python itself from vulnerabilities in the host interpreter or operating system.
- The current core has no production package manager, browser/WebAssembly runtime, native mobile runtime, graphics/audio engine, or full web framework.
- The legacy runtime and hosting adapter are not safe containers for arbitrary public multi-tenant workloads. Use OS-level isolation, per-tenant identities, resource limits, and network/filesystem policy before hosting untrusted users' programs.
- The current checksum is for integrity detection, not authenticity. Signed artifacts and a dependency/software supply-chain process remain future work.

## Security testing

Run:

~~~sh
python audit_tests.py
python core_tests.py
python core_bytecode_tests.py
python core_fuzz_tests.py
~~~

The seeded fuzz tests are regression tests, not a substitute for long-running coverage-guided fuzzing, external penetration testing, or an independent security review.
