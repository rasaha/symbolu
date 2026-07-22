# Package Immutability Report — v1.1.1 under Implementation A

- Composite hash of all v1.1.1 files BEFORE Implementation A execution: `39672e116f84bf15f9b96771cc051384fe9e0597e37726eb9d6857ce6f7b3565`
- Composite hash AFTER Implementation A blind execution + comparison: `39672e116f84bf15f9b96771cc051384fe9e0597e37726eb9d6857ce6f7b3565`
- **Identical → the implementation wrote nothing into the package.**
- corpus_root, package_root, and runtime config_fingerprint after execution match the manifest values.
- Implementation A's own source and committed results were restored to their committed state after the
  v1.1.1 re-run; the v1.1.1 run outputs are archived under `implementation-a-rerun-v1.1.1/`.
- v1.0.0 and v1.1.0 packages are byte-unchanged (verified: 0 git modifications to those directories).
