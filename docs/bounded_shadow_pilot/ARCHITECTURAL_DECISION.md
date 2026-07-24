# Architectural Decision (Phase 21) — one of eleven

*`bounded_shadow_pilot/architectural_decision.py`. Evidence-gated from the frozen pilot artifacts.*

## The eleven options

| # | Option | Chosen |
|---|---|---|
| 1 | PROCEED to single-customer external shadow pilot (unconditional) | No — utility does not transfer |
| 2 | PROCEED to single-customer external shadow pilot WITH binding conditions | No — external exposure premature |
| 3 | PROCEED but INTERNAL single-tenant natural shadow pilot first (not external) | Constructive next step |
| **4** | **DO NOT PROCEED (external) — fix utility/calibration first; gate the external pilot** | **CHOSEN** |
| 5 | DO NOT PROCEED — fix native ActionGate semantics first | No — preserved, 0 loss |
| 6 | DO NOT PROCEED — fix safety first | No — 0 unsafe permits, fail-closed |
| 7 | DO NOT PROCEED — fix auditability/explainability first | No — determinism + replay transfer |
| 8 | NOT ENOUGH EVIDENCE — insufficient natural artifacts | No — 857 ≥ 200 |
| 9 | NOT ENOUGH EVIDENCE — natural language caused unhandled new failures | No — no unsafe-permit category, all fail-closed |
| 10 | STOP — serious safety/privacy/isolation/audit/control failure | No — no stop condition fired |
| 11 | DO NOT PROCEED — runtime fundamentally unsuitable for natural artifacts | No — safe, auditable, native-preserved |

## Dimension findings

| Dimension | Finding |
|---|---|
| safe | **True** (0 unsafe permits, all fail-closed, non-enforcing) |
| auditable | **True** (determinism + replay transfer) |
| actiongate_native_preserved | **True** (0 semantic loss, no blocker) |
| useful | **False** (85.5% over-qualification, 0% clean allow) |
| stopped | **False** (no stop condition fired) |
| enough_evidence | **True** (857 ≥ 200) |
| unhandled_new_failures | **False** (no unsafe-permit category) |

## Decision: Option 4 — do not proceed to an external single-customer pilot yet; gate it

Safety, auditability, and native ActionGate preservation all **transfer** to natural artifacts, and no
stop condition fired — so every "fix-X-first / stop / not-enough-evidence / unsuitable" option (5–11) is
excluded. But **utility does not transfer**: the runtime emits 0% clean allow on benign natural
documentation, over-qualifying 85.5%. Exposing an external customer to a near-zero-clean-allow runtime
would be low value and could misrepresent readiness, so the unconditional/external options (1–2) are not
taken.

**The external single-customer pilot is GATED** on the utility-calibration prerequisites
(`SINGLE_CUSTOMER_PILOT_PLAN.md`). **The constructive next step is Option 3** — an internal
single-tenant natural shadow pilot to gather real natural traffic and calibrate the evidence stage for
evidence-free text — after which the external pilot is re-gated.

This is a falsification-first outcome: the pilot found no safety blocker **and** honestly declined to
recommend external exposure, because the evidence shows the runtime is safe but not yet useful on
natural artifacts.
