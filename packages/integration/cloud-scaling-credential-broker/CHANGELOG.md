# Changelog — ugence-cloud-scaling-credential-broker

## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

## 0.1.0 — Phase 5X, initial release

- `CredentialBrokerPort` and `ReferenceCredentialBroker` (D-1).
- Token-guarded `CredentialRequest` minted only by `CredentialRequestMinter` (D-2).
- `derive_least_privilege_role` and `role_widening` (D-3).
- `CredentialBrokerSeam` with production/reference factories, the ratified window, derived
  grant ids and replay (D-4).
- `CredentialGrant`, `CredentialGrantStore` and the in-memory reference store (D-5).
- Neighbours unmodified: Risk Authority 0.8.0, action-admission 0.1.0, execution-reservation 0.1.0.
