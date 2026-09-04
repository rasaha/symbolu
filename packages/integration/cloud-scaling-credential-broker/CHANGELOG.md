# Changelog — ugence-cloud-scaling-credential-broker

## 0.1.0 — Phase 5X, initial release

- `CredentialBrokerPort` and `ReferenceCredentialBroker` (D-1).
- Token-guarded `CredentialRequest` minted only by `CredentialRequestMinter` (D-2).
- `derive_least_privilege_role` and `role_widening` (D-3).
- `CredentialBrokerSeam` with production/reference factories, the ratified window, derived
  grant ids and replay (D-4).
- `CredentialGrant`, `CredentialGrantStore` and the in-memory reference store (D-5).
- Neighbours unmodified: Risk Authority 0.8.0, action-admission 0.1.0, execution-reservation 0.1.0.
