# ugence-jcs

RFC 8785 (JSON Canonicalization Scheme) + Action-Profile canonicalization as an
independently installable, standard-library-only, authority-neutral leaf
distribution.

It maps an already-parsed JSON value to canonical bytes. That is the whole
capability.

## What this package is not

It carries no authority and decides nothing. It contains no digest framing, no
envelope schema, no profile registry, no policy, and no decision, authorization,
clearance or eligibility vocabulary. Callers that need an identity digest compose
one over these bytes themselves — the domain separation, length prefixing and
schema versioning belong to the caller's domain, not here.

## Provenance

The implementation was extracted from `cer_v0_3/cleanroom/canon.py`, the CER V0.3
clean-room canonicalizer: an independent reimplementation written from the
published specification (`ACTION_CANONICALIZATION_AND_HASHING_SPEC.md` §2, §7)
that shares no code with the reference ActionGate path. The extraction preserves
that independence — `ugence_jcs` imports only the standard library — and preserves
the byte stream exactly. `cer_v0_3/cleanroom` now consumes this distribution.

Two independent proofs pin the preservation:

* `packages/jcs/tests/test_canonical_vectors.py` asserts canonical-byte vectors
  captured from the implementation **before** the move;
* `cer_v0_3/tests/test_cleanroom.py` still reproduces the frozen CER V0.2 identity
  digests (`test_cleanroom_matches_frozen_scale_digest`,
  `test_cleanroom_matches_frozen_rollout_digest`) through the extracted module.

## Usage

```python
from ugence_jcs import canonical_bytes

canonical_bytes({"b": "1", "a": "2"})
# b'{"a":"2","b":"1"}'

# Schema-declared "set" paths are order-independent and reject duplicates.
canonical_bytes({"perms": ["write", "read"]}, frozenset({"perms"}))
# b'{"perms":["read","write"]}'
```

`canonical_string(value, set_paths, nfc_paths)` returns the same content as text.

`canonical_sha256_hex(value, set_paths, nfc_paths)` returns the lowercase
64-character SHA-256 hex digest of exactly those canonical bytes — a bare digest
with no domain tag, no length prefix and no `sha256:` prefix; callers that need
one apply it themselves.

```python
from ugence_jcs import canonical_sha256_hex

canonical_sha256_hex({"b": "1", "a": "2"})
# 'f7a837dc9b605d08d450f14bb4927ae8ab268b757d17b579b4e8e61500d87c4a'
```

## Action Profile

* UTF-8 output, no BOM, no insignificant whitespace.
* Object member names sorted by UTF-16 code-unit order.
* The seven short escapes plus `\u00XX` for other C0 controls; every other
  character is emitted literally (no `\uXXXX` expansion of non-ASCII).
* **No bare JSON numbers.** Every numeric must already be a typed string upstream;
  a bare `int` or `float` is rejected. This is the profile's central rule.
* Arrays keep declaration order except on caller-declared `set_paths`, which are
  sorted and reject duplicate elements.
* NFC is *validated, never rewritten*, on caller-declared `nfc_paths`.
* Non-finite floats, non-string keys and unsupported types are rejected.

Every rejection is a `JcsError` subclass carrying a stable `category` key
(`E_BARE_NUMBER`, `E_NAN_INF`, `E_NON_NFC`, `E_UNSUPPORTED_TYPE`,
`E_DUPLICATE_SET_ELEMENT`) so differential runners can compare failure classes
across implementations without depending on exception types.

## Dependencies

Python standard library only. Zero runtime dependencies, including no third-party
JCS library. `packages/jcs/tests/test_leaf_boundaries.py` enforces this statically
and in an isolated subprocess.

## Scope note

This distribution is the RFC 8785 / JCS exact-identity substrate only. It does not
converge the canonicalizers of the policy workflow compiler, Agent Workforce
Composer, Risk Authority, Policy Authority or Cloud Scaling Controller, whose
semantics and domains differ.

## Verify

```
python -m pytest packages/jcs/tests -q
python packages/jcs/verify_jcs_distribution.py
```

Status: alpha. Not pilot-validated, not production-certified. The production CER
identity path still runs the reference implementation; only the clean-room
consumes this package.
