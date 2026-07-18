# CER Clean-Room Implementation (Deliverable 2)

An **independent** implementation of CER validation, canonicalization, v2 identity
projection, and action-digest — written from the published specification and JSON
Schema, sharing no code with the reference (`action_gate_ref`, `cer_v0_1`,
`cer_v0_2`, `symbolu_robotics`).

Labels: `FACT` (implemented/tested).

## Boundary (deliverable 14)
`FACT`. Package `cer_v0_3/cleanroom/` (547 LOC). Imports **only** the Python
standard library (`json`, `hashlib`, `struct`, `unicodedata`, `dataclasses`,
`typing`, `ast`) plus its own relative modules. The AST test
`tests/test_forbidden_imports.py` proves:
- no import of `action_gate_ref`, `cer_v0_1`, `cer_v0_2`, `symbolu_robotics`;
- no import of any original-side `cer_v0_3` sub-package (profiles/producers/acp_db/…);
- every absolute import resolves to `sys.stdlib_module_names` → **zero third-party
  dependencies** (no external JCS/RFC-8785 library was used; JCS is reimplemented).

## Modules
`FACT`.
| File | LOC | Responsibility |
|---|---|---|
| `errors.py` | 81 | Portable error taxonomy; each error carries a stable `category` string for cross-implementation comparison. |
| `canon.py` | 118 | JCS (RFC-8785) + Action-Profile canonicalizer: UTF-16-code-unit key sort, minimal string escaping, **bare-number rejection**, NFC validation on declared paths, set-path ordering/dedup, duplicate-key & non-finite rejection. |
| `digest.py` | 44 | Domain-separated, length-prefixed SHA-256 identity: `H(LP(tag)‖LP(canon_ver)‖LP(schema_ver)‖LP(canon))`, `LP(x)=uint64_be(len)‖x`, tag `SYMBOLU/ACTIONGATE/ACTION/v1`, schema version `2.0.0` (v2). |
| `profiles.py` | 135 | Declarative profile registry (a deliberately different shape from the reference's module-per-profile design): required/optional/**prohibited** fields, target-id derivation, identity-bearing argument normalization, rollback-plan mapping, per-profile format checks. |
| `cer.py` | 148 | `validate` / `normalized_payload` (v2 projection) / `canonical_bytes` / `action_digest`. Builds the universal envelope from the CER + profile mapping, then projects out provenance (`runtime`, `model_provider`, `objective`) and the non-identity fields (`action_id`, `timestamp`, `agent_identity.sig`, `approvals`, `attestation`). |

## What it reproduces from spec (not from source)
`FACT`. The v2 identity projection object (keys: `agent_identity{id,key_id}`,
`delegator`, `delegation_chain`, `tool`, `operation`, `target_resource`,
`arguments`, `credential_scope`, `current_state_hash`, `state_freshness`,
`reversibility`, `policy_version`, `correlation_id`, `sequence_id`, optional
`rollback_plan`), the JCS+Profile canonical bytes, and the hex digest.

## Independent verification (this stage)
`FACT`. Against the FROZEN V0.2 base digests, with no reference import in the
assertions:
- `kubernetes.scale.v1`  → `07f7a6aa…` ✓ (byte-identical to V0.2)
- `kubernetes.rollout.v1` → `72ddae26…` ✓
- provenance-invariant, deterministic, profiles domain-separated, and fails closed
  on unknown profile / profile downgrade / unsupported extension / bare number.

12 standalone tests pass. Full cross-vector agreement (normalized payload, canonical
bytes, digest, and error class) against the reference is proven by the differential
runner in `CER_DIFFERENTIAL_CONFORMANCE.md` (deliverable 3). The `database.mutation.v1`
profile is added to this same registry from its published spec in a later stage, so
the clean-room independently implements the cross-domain profile as well.
