# CER — Normative Specification (Public Draft)

Version 0.2 envelope · identity profile v2 · `cer_version` string `"0.2"`.

Keywords MUST / MUST NOT / SHOULD / MAY per RFC 2119.

## 1. Object model
A CER is a JSON object with these top-level members:

| Member | Req. | Meaning |
|---|---|---|
| `cer_version` | MUST | `"0.2"`. An implementation MUST reject any other value (fail closed). |
| `profile` | MUST | Profile id + version, e.g. `kubernetes.scale.v1`. Unknown profile MUST fail closed. |
| `risk_tier` | MAY | Advisory tier; not part of identity. |
| `authority` | MUST | `principal`, `permissions`, and (optional) `delegator`, `delegation_chain`, `key_id`. |
| `state_binding` | MUST | `resource_version`, `state_hash`, `as_of`, `operational` (+ optional `source`, `correlation_id`, `sequence_id`). |
| `policy_ref` | MUST | `version` (+ optional `digest`). |
| `actuation` | MUST | Profile-specific payload; MUST contain `operation` consistent with the profile. |
| `provenance` | MAY | `runtime`, `model_provider`, `model`, `objective`, … — **excluded from identity**. |
| `extensions` | MAY | Empty map or absent. Any non-empty unrecognized extension MUST fail closed. |

An unknown top-level member MUST fail closed (no silent drop).

## 2. Profiles
A profile fixes: the ActionGate `operation`; the `tool` identity (`server_id`, `tool_name`); the
required / optional / **prohibited** actuation fields; value normalization; and the derived
identity-bearing `arguments`, `target_resource`, `reversibility`, and optional `rollback_plan`.
Profiles are **domain-separated** by `tool.server_id` + `tool.tool_name` (inside the hashed
payload) plus a disjoint argument set, so two profiles MUST NOT produce the same identity.

This draft defines three profiles (see `schemas/`):
- `kubernetes.scale.v1` — replica-count change.
- `kubernetes.rollout.v1` — manifest/image rollout.
- `database.mutation.v1` — bounded transactional data mutation (INSERT / UPDATE / DDL). Carries
  only non-secret identity; raw SQL and credentials are **prohibited** (fail closed).

A prohibited field present under a profile (e.g. a Kubernetes field under the database profile) is
a **profile downgrade** and MUST fail closed.

## 3. Canonicalization (JCS + Action Profile)
The identity payload (§4) is serialized with RFC 8785 (JCS) plus the Action Profile:
- UTF-8, no BOM, no insignificant whitespace.
- Object member names sorted by UTF-16 code-unit order.
- JSON string escaping: the seven short escapes + `\u00XX` for other C0 controls; all other
  characters literal (no `\uXXXX` expansion of non-ASCII).
- **No bare JSON numbers** in the identity payload — every numeric is a typed string. A bare
  integer/float MUST be rejected.
- Arrays preserve order EXCEPT schema-declared **set paths** (`credential_scope.permissions`),
  which are order-independent and MUST reject duplicate elements.
- NFC is **validated** (never rewritten) on schema-declared paths (none in this draft's payload).
- Duplicate object keys and non-finite numbers MUST be rejected.

## 4. Identity projection (profile v2)
The action identity is computed over a projection of the universal envelope. **Included:**
`agent_identity.{id,key_id}`, `delegator`, `delegation_chain`, `tool`, `operation`,
`target_resource`, `arguments`, `credential_scope`, `current_state_hash`, `state_freshness`,
`reversibility`, `policy_version`, `correlation_id`, `sequence_id`, and `rollback_plan` when
present. **Excluded (provenance / non-identity):** `runtime`, `model_provider`, `objective`,
`action_id`, `timestamp`, `agent_identity.sig`, `approvals`, `attestation`. Provenance therefore
**cannot alter identity**.

## 5. Hashing
```
digest = SHA-256( LP(domain_tag) ‖ LP(canon_version) ‖ LP(schema_version) ‖ LP(canonical_bytes) )
LP(x)  = uint64_be(len(x)) ‖ x
domain_tag  = "SYMBOLU/ACTIONGATE/ACTION/v1"
canon_version = "1"
schema_version = "2.0.0"        (identity profile v2)
```
`schema_version` domain-separates identity profiles (v1 = `"1.0.0"`, v2 = `"2.0.0"`), so the same
envelope under different profiles yields different digests and cannot be confused.

## 6. Validation & failure (fail closed)
An implementation MUST reject, before producing any identity: wrong `cer_version`; unknown profile;
unknown top-level or actuation field; missing required field; operation inconsistent with the
profile; prohibited/downgrade field; non-empty unrecognized extension; bad numeric (bare/NaN/Inf);
duplicate keys; and, for domains that declare it, secret material (raw credentials, DSNs,
connection strings, statement text, or embedded-credential value patterns).

## 7. Conformance
Given a CER, a conformant implementation MUST reproduce the **normalized payload (§4)**, the
**canonical bytes (§3)**, and the **digest (§5)** in `vectors/vectors.json`. A matching digest
with a divergent normalized payload is **not** conformant. See `conformance/run.py`.
