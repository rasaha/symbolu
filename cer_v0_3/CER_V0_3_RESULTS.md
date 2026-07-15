# CER V0.3 — Results (Deliverable 7)

Executed AFTER the preregistration (`CER_V0_3_PREREGISTRATION.md`, commit `60ed330`;
fingerprints frozen at `2ef5968`). No threshold or expectation was tuned after observing
final aggregates. All numbers are measured on real components in this environment.

Labels: `FACT` (measured) · `INTERPRETATION`.

---

## 1. Headline
`FACT`. An **independent clean-room** implementation (written from the published spec,
importing none of the reference code, stdlib only) reproduces **byte-identical** normalized
payloads, canonical bytes, and digests for the entire existing corpus; and a **materially
non-Kubernetes domain** (`database.mutation.v1`) runs through the same universal envelope,
the same v2 identity, the frozen ActionGate (direct `DB_MUTATION`/R7 mapping), and a new
database ACP adapter — with **0** lines changed in ActionGate, the ACP core, or the CER
V0.1/V0.2 packages, and **0** cross-domain identity collisions.

```
DB base mutation digest (both producers, both implementations) = 05ad2c02…
V0.2 scale digest 07f7a6aa… / rollout 72ddae26…  (unchanged)   cross-domain collisions = 0
```

## 2. Differential conformance (Q1, Q3) — `conformance/differential_v0_1_v0_2.json`
`FACT`. **77 items** (47 V0.2 valid + 4 V0.2 invalid + 26 V0.1 translated). Reference vs
clean-room:
| Check | Result |
|---|---|
| Validation-result agreement | **77 / 77** |
| Normalized-payload agreement (valid) | **73 / 73** |
| Canonical-byte agreement (valid) | **73 / 73** |
| Digest agreement (valid) | **73 / 73** |
| Error-category agreement (invalid) | **4 / 4** |
| V0.1 identity reproduced (clean-room == reference == frozen) | **26 / 26** |
| **Identity-affecting differences / spec ambiguities** | **0 / 0** |

Payload and bytes are compared **before** the digest — a matching hash with divergent
normalized content would not pass.

## 3. Cross-domain conformance (Q2, Q4) — `conformance/cross_domain_results.json`
`FACT`. **29 / 29 cases**, `all_passed = true`, deterministic.
| Metric | Result |
|---|---|
| New-domain valid (equal across 2 producers) | **5 / 5** |
| Expected identity differences | **9 / 9** |
| Invalid & security (both implementations fail closed) | **9 / 9** |
| Governance holds (HELD_BY_ACP / PENDING) | **2 / 2** |
| Authorization deny (unbounded → BLOCKED) | **1 / 1** |
| Cross-domain evidence/approval transfer rejected | **3 / 3** |
| Cross-domain identity collisions | **0** |
| Producer agreement (ugence == tool-runtime) | ✓ (digest `05ad2c02…`) |
| Clean-room agreement on DB cases | ✓ |
| Regression: scale/rollout digests unchanged | ✓ / ✓ |
| `ownership_no_runtime_switch` | **true** |

All four composed outcomes reproduce in the database domain via the frozen `compose()`:
**PROCEED / HELD_BY_ACP / PENDING_AUTHORIZATION / BLOCKED_BY_AUTHORIZATION**.

## 4. Security invariants (§11) — all 15 hold
`FACT`. Per `CER_CROSS_DOMAIN_SECURITY.md`: independent-digest agreement, fail-closed
invalids, no secret in identity/bytes/output, producer agreement, material-change
sensitivity, cross-domain evidence & approval non-transfer, no K8s/DB collision, unknown
profile & downgrade fail closed, provenance-invariant identity, DENY-final, ACP-cannot-
authorize, stale-state hold, no runtime branch in the frozen core, no bypass to the tool
executor. No secret string appears anywhere in the canonical bytes or conformance output.

## 5. Specification ambiguity audit (§10)
`FACT`. `CER_SPECIFICATION_ERRATA.md` gives normative language for all 15 ambiguity classes
(absent vs null, integers vs decimals, Unicode NFC, duplicate keys, map/array ordering,
empty collections, defaults, timestamps, identifiers/case, URI normalization, extension
namespaces, profile-version negotiation, unknown fields, error classification). **0
identity-affecting ambiguities** found; **no prior vector modified**.

## 6. Metrics (§13)
`FACT`.
**Independent implementation:** existing-vector pass 73/73; normalized-payload / canonical-
byte / digest agreement 100%; invalid-vector agreement 4/4; forbidden-import violations 0;
spec ambiguities found 0 (identity-affecting 0); clean-room 671 LOC (stdlib only, 0
third-party deps).
**Cross-domain profile:** schema-validation 100%; expected-equal / expected-different
accuracy 100%; invalid-request rejection 9/9; cross-profile collisions 0; evidence-transfer
rejection 3/3; deterministic rerun identity ✓.
**Governance:** ActionGate / ACP / composition equivalence across producers ✓; state-drift,
modified-action, bypass all rejected; runtime-specific branch count **0**.
**Repository impact:**
| Component | Lines |
|---|---|
| ActionGate reference | **0** (frozen; `projection.py` `ce458712`, `gate.py` `a358c645`, `schema.py`, `policy.py`) |
| ACP core (`compose`/outcomes/`ActionDecision`) | **0** (frozen; `composition.py` `b810e2f0`, `outcomes.py` `21fd7283`) |
| CER V0.1 / V0.2 shared core | **0** (frozen; vectors `3ec7f36d` / `3dc9f372` unchanged) |
| Clean-room implementation | 671 LOC (new) |
| Database profile (`profiles/`) | 280 LOC (new) |
| Database ACP adapter (`acp_db/`) | 262 LOC (new) |
| Producers (2, DB) | 105 LOC (new) |
| New V0.3 package total (py) | 3,068 LOC |
| New conformance vectors | DB digest vectors (`conformance/vectors.json`, fp `06696792`) + differential (77) + cross-domain (29) records |
| Regression tests | **284 passed** (195 ActionGate + 23 V0.1 + 22 V0.2 + 44 V0.3) |

## 7. Verdicts (per frozen thresholds, §13 of the preregistration)
`FACT`.
1. **Independent implementability** → `CER_INDEPENDENT_IMPLEMENTATION_CONFORMANT`. The
   clean-room ran, imported no reference code (AST-proven, 0 third-party deps), and agreed
   on payload + bytes + digest for every valid vector with 0 identity-affecting ambiguity.
2. **Cross-domain profile** → `CER_CROSS_DOMAIN_SUPPORTED`. `database.mutation.v1` validates,
   produces distinct non-colliding identities, preserves exact-action binding, and passes
   governance; the ActionGate mapping is a genuine **direct** mapping onto the pre-existing
   `DB_MUTATION`/R7 with **0** core changes (not an inaccurate mapping to avoid a schema change).
3. **Governance portability** → `CONTROL_PLANE_CROSS_DOMAIN_SUPPORTED`. The frozen ActionGate
   + the new database ACP adapter reproduce all four composed outcomes with **0** frozen-core
   changes and **0** runtime/domain branch in the frozen core.
4. **Security** → `CER_SECURITY_INVARIANTS_HOLD`. All 15 §11 invariants hold; no secret enters
   identity; no cross-domain evidence/approval transfer; no collision.
5. **Draft maturity** → `CER_V0_3_READY_FOR_PUBLIC_REPOSITORY`. Two independent conformant
   implementations; no identity-affecting ambiguity; two materially different domains; no
   cross-profile collision; complete versioned vectors; no runtime-specific Control Plane
   branch; no unresolved high-severity security issue; backward-compatible with V0.1/V0.2.
   **No standards-body acceptance or industry-adoption claim.**

## 8. Falsification outcome
`INTERPRETATION`. All four questions were attacked and none was falsified: Q1/Q3 with an
independent implementation compared on payload+bytes+digest (not hashes) across 77 items
(0 divergence); Q2 with a database mutation that could have collided with a Kubernetes
action or forced an inaccurate mapping (it did neither); Q4 with a new ACP domain that
could have required a frozen-core change or a runtime branch (it required neither). The
negative controls — secret injection, unsupported operation, ambiguous/malformed target,
NaN scope, unknown profile/extension, missing state binding, stale state, cross-domain
evidence/approval transfer, profile downgrade, direct bypass — all fail closed. Within the
frozen scope, the hypotheses **survived**.

## 9. Honest limitations
`INTERPRETATION`. Two domains (Kubernetes + database); database DELETE reserved for a future
`database.delete.v1`. ACP over authored fixtures (no live cluster / live database telemetry).
ActionGate reference HMAC signing (not production custody). Deterministic producers (no live
LLM). These bound the breadth of the claim, not its correctness.
