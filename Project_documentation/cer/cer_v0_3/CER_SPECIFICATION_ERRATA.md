# CER Specification Errata & Ambiguity Audit (Deliverable 6)

Every disagreement between the original and clean-room implementations is treated as
a **specification-review event**. This document is the §10 ambiguity audit: each
canonicalization/identity ambiguity class is given explicit normative language.

**Prior conformance vectors are never modified.** Where the two implementations agreed
(the entire V0.1/V0.2 corpus and the new database corpus), the normative rule is the
already-implemented behaviour, pinned here so a third implementer cannot diverge.

Labels: `FACT` (measured/implemented) · `NORMATIVE` (rule statement).

## Differential outcome
`FACT`. Across **77** V0.1/V0.2 differential items and the **29**-case cross-domain
corpus, the independent implementations produced **0 identity-affecting differences**
and **0 identity-affecting specification ambiguities**. No erratum modifies an existing
vector. The audit below records the normative resolution for each class.

## Ambiguity classes (§10)
| # | Class | `NORMATIVE` resolution | Severity if violated |
|---|---|---|---|
| 1 | absent vs null | A required field that is `null` is invalid (fail closed). An absent optional identity-bearing field (`rollback_plan`/`compensation_ref`/`parameters_digest`) is simply absent from the projected payload — it is NOT rendered as `null`. Absent ≠ null-valued. | high (identity) |
| 2 | integers vs decimals | No bare JSON numbers in the identity payload — **all numerics are typed strings** (`replicas`, `affected_count`, `max_surge`, …). `"12"` ≠ `"12.0"`; canonicalization rejects any bare int/float (`E_BARE_NUMBER`). | high |
| 3 | Unicode normalization | Strings are NOT re-normalized at hash time. NFC is *validated* (never rewritten) only on schema-declared NFC paths (currently none for the action payload). Non-NFC on a declared path fails closed (`E_NON_NFC`). | high |
| 4 | duplicate keys | Duplicate object keys are rejected at parse (`E_DUPLICATE_KEY`); they never silently collapse. | high |
| 5 | map ordering | Object member order is irrelevant: keys are sorted by UTF-16 code-unit order before serialization. Producers may emit any key order (corpus `D04`). | none (normalized) |
| 6 | array ordering | Arrays preserve declaration order EXCEPT schema-declared set paths (`credential_scope.permissions`), which are order-independent and reject duplicate elements. | high on set paths |
| 7 | empty collections | An empty required collection (`target_resource`, `delegation_chain`) is invalid. `extensions: {}` and absent extensions are equivalent (both permitted); any non-empty unrecognized extension fails closed. | medium |
| 8 | default values | Defaults are applied by the producer/profile mapping BEFORE projection (`key_id="cer-key"`, `delegator` fallback, `sequence_id="1"`), so a defaulted value and an explicit equal value yield the same identity. Defaults are documented per profile; they are not implicit at hash time. | medium |
| 9 | timestamps | RFC-3339 UTC, `Z`, exactly 3 fractional digits (`state_freshness.as_of`). `timestamp`/`action_id` are excluded from identity; freshness is compared, not hashed into the action digest beyond `as_of`. | medium |
| 10 | identifiers & case sensitivity | Identifiers are case-sensitive and compared literally. Digests are lowercase `sha256:<64hex>` (validated). A different-case identifier is a different identity. | high |
| 11 | URI normalization | The CER performs NO URI normalization. Logical references (`connection_ref`, `compensation_ref`, target ids) are opaque strings compared byte-for-byte; producers must pre-normalize. | medium |
| 12 | extension namespaces | `extensions` is a map; only the empty map is recognized in V0.2/V0.3. Any populated extension fails closed until a versioned extension namespace is registered. | medium |
| 13 | profile-version negotiation | The profile id carries its version (`…v1`). An unknown profile/version fails closed; there is no implicit up/down-negotiation. `cer_version` mismatch is rejected. | high |
| 14 | unknown fields | Unknown top-level keys and unknown actuation fields fail closed (no silent drop), so an attacker cannot smuggle identity-irrelevant fields or hide a downgrade. | high |
| 15 | error classification | Both implementations map errors into a shared coarse taxonomy (SCHEMA / UNKNOWN_PROFILE / OPERATION_MISMATCH / PROHIBITED_FIELD / UNSUPPORTED_EXTENSION / MISSING_FIELD / UNKNOWN_FIELD / VALUE_FORMAT / SECRET_MATERIAL / CANONICALIZATION). Divergence in the *label* (not in valid/invalid) is a `harmless_diagnostic`; divergence in valid/invalid is a high-severity ambiguity. Measured divergence: **0**. | low (label) / high (validity) |

## Standing rule
`NORMATIVE`. Any future third implementation MUST reproduce the normalized payload and
canonical bytes for the frozen vectors, not merely the digest. A digest match with a
divergent normalized payload is a conformance failure, not a pass (enforced by the
differential runner). Any newly-discovered identity-affecting ambiguity is a
**high-severity standards defect** and is resolved by new normative language + new
vectors here — never by editing a frozen vector or tuning one implementation to the other.
