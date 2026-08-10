# CER V0.1 — Frozen Specification (Deliverable 1)

Narrowly scoped for the cross-runtime conformance experiment. Frozen before the producers/adapters were built. Machine-readable mirror: `cer_v0_1.schema.json`. Reference implementation: `spec.py`.

Scope is deliberately minimal: **one shared actuation surface, `kubernetes.scale`**, one operation family. No additional domains (per milestone constraint).

Labels: `FACT` (grounded in the implemented reference) · `RECOMMENDATION`.

---

## 1. What a CER is

A CER V0.1 is a JSON object describing **one exact requested actuation** plus the authority requested for it, emitted by a runtime *before* execution. It is the only object that crosses the runtime → AI Control Plane boundary. Its *identity* is the ActionGate **v2** action digest of its derived envelope (provenance excluded) — see `CER_IDENTITY_PROFILE.md`.

## 2. Structure (four sections)

```
{ cer_version:"0.1", profile:"cer.k8s.scale/0.1", risk_tier:"GOVERNED"|"LOW_RISK",
  identity   { ... },     // identity-bearing — defines the exact actuation
  provenance { ... },     // non-identity — retained for audit only
  evidence   { ... } }    // optional — scrutiny-only
```

### 2.1 Identity-bearing fields (participate in the digest)
`FACT` (`spec.IDENTITY_FIELDS`, enforced in `validate_cer`):

| Field | Meaning | Why identity-bearing (justification) |
|---|---|---|
| `operation` | ActionGate consequence class (`DEPLOY` for a scale) | changes what is authorized |
| `actuation_interface` | the shared tool surface — pinned to `kubernetes.scale` | different interface = different action (FF1 of prior milestone) |
| `target` `{cluster, namespace, deployment}` | what is acted on | a different target is a different action |
| `arguments` | canonical args (typed-string numerics) | the actuation parameters |
| `requested_state_transition` `{replicas:{from,to}}` | the exact state change | the substance of the request |
| `authority` `{principal, permissions, delegator, delegation_chain}` | who acts, with what privilege | a read vs write, or a wider scope, is a different governed action |
| `external_state_binding` `{resource_version, state_hash, as_of, ...}` | the state the decision assumes (TOCTOU) | stale state must invalidate; binding is authorization-semantic |
| `policy_ref` `{version, digest}` | which enterprise policy | the policy in force is part of identity |
| `reversibility` | consequence class | authorization-semantic (`MAX_IRREVERSIBILITY`) |

### 2.2 Non-identity provenance (retained, excluded from digest)
`FACT` (`spec.PROVENANCE_FIELDS`): `runtime`, `runtime_version`, `model_provider`, `model`, `planner`, `objective`, `reasoning_trace_ref`, `adapter_version`, `explanation`. Justification: each is decision-inert (no ActionGate predicate reads it — verified by grep of `gate.py`) and describes the *producer*, not the *actuation*. Excluding them is what lets two runtimes emitting the same actuation collide to one identity. **They are NOT excluded to force a match — they are excluded because they carry no authorization semantics.**

### 2.3 What MUST NOT appear
Prompt, reasoning trace content, memory state, planner internals, model weights/params, the policy itself (only `policy_ref`), live world-state values beyond the `state_hash`/`resource_version` binding, the verdict. Unknown top-level keys and non-empty unrecognized `extensions` **fail closed** (`validate_cer`).

## 3. Frozen canonicalization & identity

`FACT` — CER V0.1 reuses the frozen ActionGate canonicalization/hashing (it does not invent a second scheme):
- **Canonicalization profile:** JCS / RFC-8785 via `action_gate_ref.jcs` — UTF-8/NFC, keys sorted by UTF-16 code unit, **no bare JSON numbers** (typed-string numerics), NaN/Inf/duplicate-keys rejected. Set-path dedup for `credential_scope.permissions`.
- **Domain separation:** `digest = H(LP(ACTION_tag) || LP(canon_ver="1") || LP(schema_ver="2.0.0") || LP(canonical_bytes))` (`action_gate_ref.hashing.domain_digest`). Schema version `2.0.0` domain-separates v2 from legacy v1.
- **Digest:** SHA-256 default, algorithm-prefixed.
- **Numeric handling:** all numerics are strings in `arguments`/`requested_state_transition` (Action Profile). Booleans/ints in `external_state_binding.operational` are consumed by ACP, not by the identity digest.
- **Null / omission:** required fields absent or null → `CERValidationError` (fail closed). Optional `evidence`/`extensions` may be omitted.
- **Map ordering:** irrelevant — canonicalization sorts keys. `credential_scope.permissions` is a declared set (order-independent).
- **Invalid-value behavior:** unknown `operation`, malformed `state_hash`/`policy_ref.version`/`as_of`, or an unsupported `profile`/extension → fail closed.

## 4. Profile negotiation & extensions
`FACT`. V0.1 pins exactly `profile = "cer.k8s.scale/0.1"` and `actuation_interface = "kubernetes.scale"`. A control plane that does not understand the profile MUST fail closed (`UNSUPPORTED_PROFILE`), never guess. `extensions` is reserved; a non-empty unrecognized extension fails closed (proven by a corpus case).

## 5. Digest test vectors
`FACT`. Frozen vectors in `conformance/vectors.json` (CER → expected `action_digest`), consumed by `conformance/runner.py`. See `CER_CROSS_RUNTIME_RESULTS.md` for the executed values.

## 6. Explicit non-goals (frozen)
Not a multi-domain schema (only `kubernetes.scale`); not a transport; not a policy or world-model carrier; not an industry standard (this is V0.1 internal evidence, per milestone constraints). Provenance is present for audit, never for identity.
