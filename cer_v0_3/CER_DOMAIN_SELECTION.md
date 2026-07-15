# CER V0.3 — Second-Domain Selection (Stage 1)

Selecting the non-Kubernetes domain by **repository-grounded executable logic**, per
the milestone preference order (database → filesystem → HTTP/API → non-K8s cloud →
enterprise workflow).

Labels: `FACT` (grep/enum-grounded) · `INTERPRETATION`.

## Selected domain: `database.mutation.v1` (preference rank #1)

`FACT`. The database domain is the **only** candidate for which the frozen ActionGate
core already carries first-class, executable, testable governance — not a label we would
have to add. The evidence:

### 1. Operation taxonomy already includes database mutations (closed enum)
`FACT`. `action_gate_ref/schema.py` defines the closed `OPERATIONS` frozenset. Two of its
ten members are database operations:
```
DB_MUTATION   # general INSERT / UPDATE / DDL
DB_DELETE     # destructive delete class
```
`schema.py` rejects any operation outside this set (`InvalidEnumError`), so an unknown
operation fails closed. **No Kubernetes SCALE/ROLLOUT operation exists in this enum at all**
— the two K8s profiles both map to the abstract `DEPLOY` operation. The taxonomy is a
cloud/infra *risk* taxonomy, not a Kubernetes taxonomy.

### 2. A signed policy rule already governs `DB_MUTATION` (executable)
`FACT`. `action_gate_ref/policy.py` rule **R7** binds to `operation == "DB_MUTATION"`:
```
FORBID  fact "unbounded"
REQUIRE_SIMULATION fidelity MEDIUM
MAX_SCOPE value 10000 on fact "affected_count"
ALLOW_WITH_CONSTRAINTS {in_transaction: True}
```
and **R3** governs `DB_DELETE` (forbids `last_replica`, hard-requires
`verified_restorable_backup`, caps irreversibility, dual-control approval). These rules are
already signed into the default policy bundle the CER control plane uses
(`DEFAULT_SIGNED_POLICY = sign_policy(build_bundle())`).

### 3. Deterministic fact extraction already reads database facts
`FACT`. `action_gate_ref/gate.py::extract_facts` reads database-relevant keys straight from
the envelope `arguments`: `unbounded`, `affected_count`, `last_replica`. So a database
mutation flows through the real decision state machine end-to-end with **zero ActionGate
changes** — the mapping is *direct*, not forced (milestone §6 "direct mapping" outcome).

### 4. Materially different from Kubernetes deployment management
`INTERPRETATION`. A database mutation's identity is over a *statement against stored data*
(connection identity, schema, table, SQL operation, normalized parameters / statement
digest, affected-row scope, transaction/isolation, expected row-version, compensation
reference) — not over cluster/namespace/deployment/replicas/manifest. None of the K8s
profile's identity-bearing fields (image digest, replica transition, rollout strategy,
surge/unavailable) is meaningful for a database mutation, and vice-versa. This is the
"materially different domain" the milestone requires, and it stresses the universal
envelope in a genuinely new way (statement digest vs image digest; affected-row bound vs
blast-radius; transaction/isolation vs freeze window).

## Why not the lower-ranked candidates
`INTERPRETATION`.
- **Filesystem / generic HTTP / non-K8s cloud / enterprise workflow** — none has a matching
  operation in the frozen `OPERATIONS` enum or a governing policy rule. Selecting any of
  them would require *adding* an ActionGate operation and rule to make it actionable
  (otherwise `NO_RULE → ESCALATE_TO_HUMAN`), i.e. modifying the frozen core. The database
  domain is the only one that proves cross-domain portability **without** touching the
  frozen governance core — the sharper falsification test.

## Consequence for the milestone
`FACT`.
- **ActionGate mapping (§6): direct.** `database.mutation.v1` → `operation="DB_MUTATION"`,
  `tool.server_id="database"`, governed by existing R7. Expected ActionGate lines changed: **0**.
- **ACP adapter (§7): new sibling adapter required.** The ACP *core* (`compose`,
  `ActionDecision`, `CloudRecommendation`) is domain-neutral and reused unchanged; the
  Kubernetes `cloud/` constraint evaluator is K8s-specific and does NOT apply to a database.
  V0.3 adds a new deterministic database operational-safety evaluator (`cer_v0_3/acp_db/`)
  that reuses the frozen `compose()` verbatim. Expected ACP-core lines changed: **0**.
- **Secret handling:** database *credentials* (password, DSN secrets, connection tokens)
  are **prohibited** in the CER and never enter identity, logs, or vectors — only a
  non-secret connection *identity* (host/port/database/role name, or an opaque
  connection-ref) participates. Enforced by the profile's prohibited-field + secret-pattern
  checks (§5, §11).
