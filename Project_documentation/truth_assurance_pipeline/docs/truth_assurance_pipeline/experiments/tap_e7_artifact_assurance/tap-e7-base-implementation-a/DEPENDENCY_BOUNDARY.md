# Dependency Boundary — Implementation A

## Runtime dependencies
Python 3.11 standard library only (`json`, `re`, `hashlib`, `base64`, `unicodedata`,
`fractions`). No third-party packages. No network. No LLM. No embedding model. No external
entity knowledge.

## Package inputs (read-only)
- `resources/**` (normative resource tables)
- `grammar/**`, `schemas/**`
- `corpus/*.json` (input envelope only; expected/phenomenon/purpose stripped before use)
- `manifest/{release,resource,corpus}-manifest.json`
- `hashes/*` (for fingerprint verification)

## Explicitly NOT used
- `expected/**`, `derivations/**` (blind-guarded)
- any file under `tap-e7-base-companion-1.1.0-tooling/`
- fixture id / group / purpose / phenomenon for dispatch decisions

## Shared-utility note
UTF-8 read, JSON serialization, SHA-256, and canonical ordering are the only shared concepts;
each is implemented locally in `src/verifier.py` and covered by `tests/run_all_tests.py`
(unit group).
