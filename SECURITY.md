# Security policy and audit notes

## Status

Plainly 1.4.0 is being prepared for an independent security review. **It has not been independently audited, certified, or approved for running untrusted programs.** The checks in this repository are regression tests only.

Please do not treat this document, the permission syntax, or a passing test suite as proof that Plainly is a secure sandbox.

## Supported execution paths

- `run` compiles Plainly source into generated Python and executes that generated code with a restricted set of built-ins.
- `compile` validates supported source and emits a versioned `.pbc` binary instruction file. `execute` runs those instructions in the Plainly virtual machine; bytecode version 1 does not evaluate generated Python or expose file, network, or operating-system process instructions.
- `native` generates C for the currently supported subset and invokes an installed C compiler to create a native executable. The build command does not run the resulting executable.
- `plainly-web.html` runs its supported subset in the browser. Its page explains that browser programs cannot access the user's files or call a server.
- The Python web server binds to `127.0.0.1` by default. A provider can explicitly bind it to another interface with `--host` or `PLAINLY_HOST`; public binding requires a configured Host-header allowlist. HTTPS must terminate at a provider reverse proxy.
- plainly_bots.py implements basic Telegram long polling and Discord Gateway message events. These integrations make outbound HTTPS/WebSocket connections to their respective platform APIs and require app-scoped tokens.
- plainly_host.py can start each app as a separate child process with a reduced environment. It does not create containers, namespaces, cgroups, network policies, or resource quotas.

The restricted Python built-ins and Plainly's file permission statements are **not** an operating-system security boundary. Generated Python is executed with the permissions of the Plainly process. The bytecode VM has a narrower feature set, but still runs inside the Plainly process and is not an OS sandbox. A native executable has the permissions of the account that runs it.

## Project manifest security in 1.4.0

The project scaffold starts with no granted capabilities, denied network access, project-only filesystem scope, and native extensions disabled. The validator rejects duplicate JSON keys, unknown manifest fields, unknown capabilities, invalid platform targets, path traversal in the entry filename, symlinked or non-regular manifest/source files, hard-linked files, and inputs over fixed size limits. These checks protect project parsing and reduce unsafe configuration mistakes; they are not a sandbox and do not prove that a future native runtime is safe. Filesystem race conditions and platform-specific behavior still require review and OS-level isolation.

## Deployment requirements before accepting untrusted programs

1. Run each user's program in a separate OS process and a separate private working directory. Do not run mutually untrusted tenants as threads in one Python interpreter process.
2. Run as a dedicated, unprivileged operating-system account. Never run the interpreter or generated executable as root or with administrator privileges.
3. Apply OS/container/VM isolation, memory and CPU limits, process-count limits, execution timeouts, disk quotas, and network-deny rules outside Plainly.
4. Do not mount host secrets, deployment credentials, SSH keys, container sockets, or other tenants' files into a program's environment.
5. Give each job a disposable filesystem. Do not share writable directories between users. File permissions inside Plainly are an additional check, not a replacement for OS permissions.
6. Keep native compilation and execution disabled for untrusted source unless the build and execution steps are contained by the same isolation policy.
7. Keep the web server behind a managed HTTPS reverse proxy. Public binding must use an explicit hostname allowlist, and provider routing must expose only the assigned app domain.
8. Store Discord and Telegram tokens as per-app secrets. Do not put them in source files, shared environment variables, or provider control-plane configuration visible to other tenants.
9. Restrict bot egress to the required platform endpoints where practical, and prevent app processes from reaching provider metadata services or internal control-plane endpoints.
10. Pin and review the Python runtime, C compiler, build image, and package dependencies used by the deployment.

## File-access hardening in 1.1.1

Plainly rejects path separators and hidden-file names in its file permission syntax. Runtime file opens now reject symbolic links and non-regular files. Where the operating system supports `O_NOFOLLOW`, the final path component is opened without following a symbolic link. Runtime checks also reject files with more than one hard link.

These checks reduce accidental or simple link-based escapes. They do not make a shared working directory safe: other filesystem races, platform differences, mount behavior, and host-level permissions still matter. Use a private directory for every program.

## Known limitations and review targets

- The `run` interpreter uses Python `exec` on compiler-generated code. The limited built-ins are not a sandbox against hostile source or runtime vulnerabilities.
- Bytecode version 1 validates its magic, version, length, and SHA-256 checksum, and limits a run to 1,000,000 VM instructions, nested function calls to 100 levels, and bytecode files to 16 MiB. The checksum is not a digital signature or creator identity check. The VM does not provide general memory quotas or OS isolation, and implementation vulnerabilities remain possible.
- Runtime state such as file permissions, memory-file selection, and HTTP routes is held in module-level state. Independent tenants must not share one interpreter process.
- Programs can use unbounded loops or consume substantial CPU and memory. Plainly does not itself provide general CPU, memory, process, or wall-clock quotas.
- The server feature is a small HTTP server, not a full production web framework. Public deployments require a reverse proxy, hostname allowlisting, and provider-enforced request/resource limits.
- The hosting process adapter has an in-memory registry and does not persist jobs or recover them after the provider control plane restarts. It is not a complete hosting service.
- The bot integrations are first-version text-message handlers. They do not implement Discord slash commands/interactions, reactions, attachments, voice, or Telegram webhooks. Discord message content requires the privileged intent to be enabled for the application.
- The native backend emits C and relies on an external C compiler. Native output is machine code after compilation and must be treated as executable code.
- The cross-platform project manifest is not a native build system. No Android/iOS/desktop package generation, native UI bridge, graphics/audio/input engine, signing, or store publishing is implemented in 1.4.0.
- A capability declaration is metadata until a runtime enforces it at every OS boundary. Do not treat manifest permissions as enforced isolation.
- A Rust backend and a Go backend are not implemented in this release. Do not assume Rust or Go compilation, binary compatibility, or equivalent security properties.
- The discord_bot.plain and telegram_bot.plain examples require the matching app token. Discord also requires the optional websockets dependency and an enabled Message Content Intent.
- A separate process and reduced environment are not equivalent to OS isolation. The provider adapter alone is not safe for running untrusted customer code.

## Regression checks

Run from the repository root:

```sh
python3 -m py_compile plainly.py plainly_bytecode.py
python3 audit_tests.py
python3 bytecode_tests.py
python3 plainly.py compile hello.plain
python3 plainly.py execute hello.pbc
node web_test.js
python3 plainly.py check hello.plain
python3 plainly.py run hello.plain
```

If a C compiler is available, test the native path:

```sh
python3 plainly.py native speed.plain
./speed
```

The native command creates the executable; run it only in a disposable test environment. Windows users can run the same checks with `py` instead of `python3`, and should use the appropriate executable name.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the repository maintainer before publishing exploit details. Include the affected version or commit, the exact feature involved, impact, and a minimal reproduction that does not access anyone else's data. Do not include real credentials, personal data, or live service tokens in reports.
