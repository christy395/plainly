# Plainly cross-platform app and game roadmap

## Project support available in 1.4.0

Plainly can create and validate a shared project folder:

```sh
plainly init app MyApp
plainly init game MyGame
plainly project-check MyApp
```

The project manifest can list these intended targets:

- Android
- iOS
- Windows
- Linux
- macOS

A target declaration means the project intends to support that platform. It does not mean Plainly can currently compile or package an app for it.

## Platform build status

| Platform | Project target declaration | Native package/export |
|---|---|---|
| Android | Available | Not implemented |
| iOS | Available | Not implemented |
| Windows | Available | Not implemented |
| Linux | Available | Not implemented |
| macOS | Available | Not implemented |

## What is needed to ship native apps

- A stable, versioned Plainly runtime ABI and standard library.
- Platform adapters for application lifecycle, UI, input, storage, networking, accessibility, and notifications.
- A shared rendering and audio layer for games, plus asset import and frame scheduling.
- Android build adapter using the Android SDK, Gradle, and a supported native toolchain.
- iOS build adapter using Xcode, Apple SDKs, signing, and provisioning; final iOS builds require supported Apple build infrastructure.
- Windows, Linux, and macOS build adapters with platform-specific packaging and signing.
- Cross-compilation and reproducible-build tests on real platform runners or supported build hosts.
- Store-compliant permissions, privacy declarations, accessibility checks, and signing workflows.

## Security requirements before platform runtimes are trusted

1. Define capabilities for every sensitive API and deny by default.
2. Enforce capabilities in the runtime and operating system boundary, not only in project metadata.
3. Use memory-safe implementation languages for privileged runtime components where practical.
4. Keep app code isolated from the build service, signing keys, host filesystem, and other tenants.
5. Verify compiler/toolchain versions and dependency hashes; generate an SBOM for every build.
6. Sign release artifacts and verify signatures before install or update.
7. Fuzz the parser, type checker, bytecode loader, package reader, and native bridge.
8. Run independent security reviews and publish vulnerability response procedures.
9. Test permission bypasses, malformed input, resource exhaustion, update rollback, and supply-chain compromise.
10. Provide a documented threat model and platform-specific hardening guides.

## Current security boundary

The project manifest validator rejects malformed or unsafe project metadata and defaults to no capabilities and denied networking. It is not a sandbox, does not yet mediate native APIs, and does not make generated executables safe to run. Do not run untrusted projects on a machine containing secrets. Do not describe Plainly as unhackable or independently certified.
