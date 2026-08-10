# CER V0.3 — Internal Executive Summary (Deliverable 17)

**What this milestone did:** answered whether CER is a real, independently-implementable
cross-domain standard — not just one team's code. It (a) reimplemented CER from the written
spec in a clean room and proved byte-for-byte agreement, and (b) carried the identity +
governance architecture into a materially non-Kubernetes domain (database mutation) with
**zero** changes to the frozen ActionGate and ACP cores.

Labels: `FACT` (measured/implemented) · `INTERPRETATION`.

## The result in one line
`FACT`. Two independent implementations (reference + clean-room, no shared code) produce
identical normalized payloads, canonical bytes, and digests for every V0.1/V0.2 vector; a new
`database.mutation.v1` profile produces a distinct non-colliding identity (`05ad2c02…`) that
the frozen ActionGate governs directly via the pre-existing `DB_MUTATION`/R7 rule and a new
database ACP adapter reproduces all four composed outcomes — all with 0 frozen-core changes.

## Four questions — all survived falsification
`FACT`. Q1 independent implementability; Q2 non-Kubernetes domain on the same envelope; Q3
byte-identical canonical payloads/digests; Q4 governance precision with a new ACP domain
adapter. Each was attacked (payload/bytes comparison not just hashes; a DB action that could
collide with K8s or force an inaccurate mapping; a new ACP domain that could require a core
change or runtime branch); none was falsified.

## Five verdicts (per frozen thresholds)
1. **Independent implementability** → `CER_INDEPENDENT_IMPLEMENTATION_CONFORMANT` (77/77 items, 0 identity-affecting ambiguity, AST-proven boundary, 0 third-party deps).
2. **Cross-domain profile** → `CER_CROSS_DOMAIN_SUPPORTED` (direct `DB_MUTATION`/R7 mapping, 0 core changes, 0 collision).
3. **Governance portability** → `CONTROL_PLANE_CROSS_DOMAIN_SUPPORTED` (all 4 outcomes via frozen `compose()`, 0 core change, 0 runtime branch).
4. **Security** → `CER_SECURITY_INVARIANTS_HOLD` (all 15 §11 invariants).
5. **Draft maturity** → `CER_V0_3_READY_FOR_PUBLIC_REPOSITORY` (all criteria met; **no standards-body / industry-adoption claim**).

## What was built (staged, pushed commits)
`FACT`.
1. **Freeze + domain selection** — immutable V0.2 fingerprints; database selected by executable evidence (ActionGate already carries `DB_MUTATION`/R7).
2. **Clean-room** (671 LOC, stdlib only) — independent JCS + v2 projection + LP hashing + validation; AST forbidden-import test; byte-identical to V0.2 baseline.
3. **Differential conformance** — 77 items through both implementations; payload+bytes+digest+validation+error-class compared; 0 identity-affecting differences.
4. **Database profile + ActionGate mapping + ACP adapter** — non-Kubernetes envelope; direct `DB_MUTATION`/R7 (0 AG change); new database operational-safety adapter reusing the frozen `compose()` (0 ACP-core change).
5. **Two DB producers + cross-domain corpus + security + backward-compat + errata** — 29 cases; 15 security invariants; frozen fingerprints unchanged; 15-class ambiguity audit (0 identity-affecting).
6. **Preregistration** (committed before the final run).
7. **Final run + results** — differential 77/77, cross-domain 29/29, regression 284 passed.

## Why identity held across a new domain without weakening binding
`FACT`. The database action carries only non-secret identity (statement/parameter digests,
logical connection ref, affected-row bound, transaction/isolation, expected row-version,
compensation ref). Domain separation comes from `tool.server_id="database"` + `tool.tool_name
="mutation"` + a disjoint argument set inside the hash — not from hashing the profile string —
so no K8s/DB collision is possible, while the same v2 projection and canonicalization apply
unchanged. A recursive secret guard keeps credentials out of identity, logs, and vectors.

## What did NOT change (constraints honored)
`FACT`. **ActionGate: 0 lines** (frozen; `DB_MUTATION`/R7 already existed). **ACP core: 0
lines** (frozen `compose`/outcomes/`ActionDecision`). **CER V0.1/V0.2: 0 lines** (vectors
`3ec7f36d`/`3dc9f372` unchanged). **Context Minimization: 0 lines**. No frozen vector edited;
no implementation tuned to the other to hide an ambiguity; nothing actuates (shadow-only).
VC brief / pitchbook untouched.

## Honest limitations (`INTERPRETATION`)
Two domains (Kubernetes + database); DB DELETE reserved. ACP over authored fixtures (no live
cluster / database telemetry). Reference HMAC signing (not production custody). Deterministic
producers (no live LLM). These bound the breadth, not the correctness.

## Recommended next step
`INTERPRETATION`. The standard now has two independent implementations and two materially
different domains. The next increment (a future milestone) is a third independent
implementation in a different language, a third domain (e.g. filesystem or generic HTTP with a
versioned ActionGate operation), a live-cluster/live-DB ACP path, and production asymmetric
signing. No standards-body or industry-adoption claim should be made before that breadth exists.

## Artifacts
`cer_v0_3/`: `CER_V0_2_BASELINE_FREEZE.md`, `CER_DOMAIN_SELECTION.md`,
`CER_CLEAN_ROOM_IMPLEMENTATION.md`, `CER_DIFFERENTIAL_CONFORMANCE.md`,
`CER_DATABASE_MUTATION_PROFILE.md`, `CER_CROSS_DOMAIN_SECURITY.md`,
`CER_SPECIFICATION_ERRATA.md`, `CER_V0_3_PREREGISTRATION.md`, `CER_V0_3_RESULTS.md`,
`CER_V0_3_PUBLICATION_CHECKLIST.md`; `cleanroom/`, `profiles/` (+ schema), `acp_db/`,
`producers/`, `db_actuation.py`, `envelope.py`, `control_plane.py`, `corpus.py`,
`conformance/` (differential, cross_domain, vectors, results), `tests/` (44 tests).
Frozen, reused unchanged: ActionGate reference + ACP core + CER V0.1/V0.2.
