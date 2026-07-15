# CER `database.mutation.v1` Profile (Deliverable 4)

The non-Kubernetes domain profile, added through the same universal-envelope +
profile architecture. Governs a bounded, transactional data mutation
(INSERT / UPDATE / DDL) without carrying raw SQL or credentials.

Labels: `FACT` (implemented/tested).

## 1. Identity & versioning
`FACT`. `profile = "database.mutation.v1"`. CER envelope version stays `0.2` (the
profile is additive; the envelope schema did not change). Identity = ActionGate v2
`action_hash` of the profile's envelope projection. Domain-separated from the
Kubernetes profiles by `tool.server_id="database"` + `tool.tool_name="mutation"`
(both inside the hash) and a disjoint argument set.

## 2. Semantic operation vocabulary
`FACT`. `sql_operation ∈ {INSERT, UPDATE, DDL}`. **DELETE is intentionally excluded**
— it maps to the stricter ActionGate `DB_DELETE`/R3 class (verified restorable backup
+ dual control) and is reserved for a future `database.delete.v1`. Any other value
(e.g. `DELETE`, `TRUNCATE`, `DROP`) fails closed.

## 3. Fields
`FACT`.
| Field | Kind | In identity? |
|---|---|---|
| `operation` (`"DB_MUTATION"`) | required | yes (operation) |
| `target.connection_ref` / `schema` / `table` | required | yes (target_resource) |
| `sql_operation` | required | yes (arguments) |
| `statement_digest` (`sha256:…`) | required | yes (arguments) |
| `parameters_digest` / `predicate_digest` (`sha256:…`) | optional | yes when present |
| `affected_scope.estimated_rows` (int string) | required | yes (`arguments.affected_count`) |
| `affected_scope.unbounded` (bool) | required | yes (`arguments.unbounded`) |
| `transaction.mode` (`in_transaction`) / `isolation` | required | yes |
| `expected_row_version` | required | yes (state binding) |
| `compensation_ref` | optional | yes when present (`rollback_plan`) |
| `reversibility` | required | yes |
| `provenance.*` (runtime/model/objective) | — | **no** (v2 excluded) |

**Prohibited (fail closed):** every Kubernetes-only field (`replicas`, `image_digest`,
`current_manifest_digest`, `rollout_strategy`, `requested_state_transition`,
`max_surge`, `max_unavailable`, `timeout_s`, `rollback_ref`), and any secret-bearing
key anywhere in the actuation (`password`, `dsn`, `connection_string`, `credentials`,
`token`, `private_key`, **`statement`/`sql`/`sql_text`** raw text, …) plus values that
match embedded-credential patterns (`password=…`, `scheme://user:pass@…`, PEM blocks).

## 4. Normalization & value handling
`FACT`. Numerics are typed strings (`estimated_rows`, canonicalization rejects bare
numbers); `unbounded` is a JSON boolean; digests are lowercase `sha256:<64hex>`;
map key order is irrelevant (JCS sorts by UTF-16 code unit); the `credential_scope.
permissions` array is the only order-independent set path. No raw statement text is
ever normalized or hashed — only its digest.

## 5. Secret-handling rule
`FACT`. The CER carries only non-secret identity. A recursive guard rejects
secret-bearing keys and embedded-credential value patterns before any hashing, so no
secret can enter the identity, the canonical bytes, logs, traces, or conformance
vectors. Tested (`test_cross_domain_security.py`), and by the corpus "raw credential"
invalid case.

## 6. State binding, authority, extensions, failure
`FACT`. State binding: `expected_row_version` (optimistic concurrency) + the shared
`state_binding.state_hash`/`as_of`; the ACP adapter also binds the candidate to the
observed world version (`origin_state_version == world.version`). Authority: the
shared `authority.principal`/`permissions`/`delegator`/`delegation_chain` (privilege
monotonicity enforced by the frozen gate). Extensions: any non-empty unrecognized
`extensions` fails closed. Failure behaviour: unknown operation, unknown/unsupported
field, malformed identifier, non-integer scope, missing state binding, and secret
material all fail closed (`CERValidationError`).

## 7. ActionGate mapping (§6) — DIRECT, 0 core changes
`FACT`. `operation="DB_MUTATION"` maps onto the **existing** frozen ActionGate rule
**R7**: `FORBID unbounded`; `REQUIRE_SIMULATION MEDIUM`; `MAX_SCOPE affected_count ≤
10000`; `ALLOW_WITH_CONSTRAINTS in_transaction`. The profile's `arguments` supply the
exact facts R7 reads (`unbounded`, `affected_count`). Proven through the real gate:
bounded + in_transaction + simulation → **ALLOW_WITH_CONSTRAINTS(R7)**; `unbounded` →
**DENY(R7)**; `affected_count > 10000` or missing simulation → fail closed. This is a
genuine direct mapping (the taxonomy is a cloud/infra risk taxonomy, not K8s) — **not**
an inaccurate mapping chosen to avoid a schema change. ActionGate lines changed: **0**.

Evidence and approvals bind to the DB action's v2 `action_hash`; because scale/rollout/
mutation have different digests, no evidence/approval can transfer across domains
(§ `CER_CROSS_DOMAIN_SECURITY.md`).

## 8. Two independent implementations
`FACT`. The original (`profiles/database.py`) and the clean-room
(`cleanroom/profiles.py`, written from this document) produce **byte-identical**
normalized payloads and digests for the DB profile — e.g. base valid mutation digest
`05ad2c02…` on both. Verified by the differential runner (`CER_DIFFERENTIAL_CONFORMANCE.md`).
