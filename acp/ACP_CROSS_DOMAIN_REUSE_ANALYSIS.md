# ACP Cross-Domain Reuse Analysis (V2 §10)

Classifies every ACP property by how it transferred from robotics to cloud, and
reports honest reuse percentages. The frozen V1 core's combined SHA-256 is
**unchanged** at V2 completion — see `ACP_V1_FREEZE.md` §4 (verified:
`8f8660e293308cf94c983a26a2ae69c9`).

## Classification legend

`UNCHANGED_CORE` reused byte-for-byte · `GENERALIZED_CLEANLY` a core *pattern*
re-instantiated with cloud types, no core edit · `DOMAIN_ADAPTER_ONLY`
cloud-specific code any domain must write · `CORE_CHANGE_REQUIRED` forced a core
edit · `DID_NOT_TRANSFER` robotics-only, correctly absent from cloud.

## Per-property

| ACP property | classification | evidence |
|---|---|---|
| canonical identity / serialization (`identity`, `normalize_float`) | **UNCHANGED_CORE** | imported + used by all 3 cloud envelopes; domain-separated |
| `ConstraintResult` / `ConstraintKind` (hard/soft) | **UNCHANGED_CORE** | every cloud HARD result is a core `ConstraintResult` |
| non-compensatory hard filter (`filter_admissible`) | **UNCHANGED_CORE** | runs unchanged on cloud candidates; test `test_frozen_selector_executes_on_cloud` |
| deterministic total-order selection (`LexicographicActionSelector`) | **UNCHANGED_CORE** | selects cloud candidates; trace binds `world.version` + `candidate.identity` |
| closed outcome set (`ActionDecision`) | **UNCHANGED_CORE** | cloud maps onto it; adds no new states |
| structured `DecisionTrace` | **UNCHANGED_CORE** | emitted for cloud decisions unchanged |
| commit revalidation (`ReferenceCommitRevalidator`, `ControlAuthorization`) | **UNCHANGED_CORE** | reused for cloud TOCTOU (state drift + candidate mutation) |
| typed error hierarchy (`ACPError`, `SchemaValidationError`) | **UNCHANGED_CORE** | cloud envelopes/adapter raise + catch core errors |
| fail-closed philosophy | **UNCHANGED_CORE** | same rule: no hard evidence ⇒ inadmissible |
| hard-before-soft ordering | **UNCHANGED_CORE** | inherited from `filter_admissible`; no cloud soft score can compensate |
| shadow-only + bounded sink + OFF-by-default | **GENERALIZED_CLEANLY** | `CloudShadowAdapter` re-instantiates the robotics `ShadowPlannerHook` pattern |
| state/action/evidence envelope pattern (`.version`/`.identity`/`validity`) | **GENERALIZED_CLEANLY** | cloud envelopes mirror the robotics envelope contract |
| constraint-evaluator interface (`evaluate → (evidence, results)`, `safety_critical`) | **GENERALIZED_CLEANLY** | `CloudConstraintEvaluator` matches the robotics evaluator shape |
| cloud envelope *fields* (replicas, manifest, rollback…) | **DOMAIN_ADAPTER_ONLY** | `cloud/envelopes.py` |
| cloud hard constraints (readiness/blast/capacity/freeze/rollback) | **DOMAIN_ADAPTER_ONLY** | `cloud/constraints.py`, driven by real `cloud_controller` |
| outcome→cloud-operation mapping | **DOMAIN_ADAPTER_ONLY** | `cloud/outcomes.py` |
| ActionGate × ACP composition | **DOMAIN_ADAPTER_ONLY** | `cloud/composition.py` |
| robotics thresholds / trajectory equations | **DID_NOT_TRANSFER** | not present in cloud (per §2 non-goal — correct) |
| `physical_evidence`, `predictor_evidence`, `safety_adapters/` | **DID_NOT_TRANSFER** | robotics domain layer; cloud has its own equivalents |

**No property is `CORE_CHANGE_REQUIRED`.** The cloud adapter needed **zero**
edits to the frozen core.

## Reuse percentages (honest, not inflated)

Not inflated by copied docs or renamed fields; measured on real, exercised code.

| dimension | reuse | basis |
|---|---|---|
| **decision-core code** | **100 %** (0 lines changed) | the 10 frozen modules (1,199 LOC) are hash-identical; the adapter is purely additive |
| **core interfaces** | **9 / 9 reused unchanged** | `identity`, `normalize_float`, `ConstraintResult`, `ConstraintKind`, `filter_admissible`, `LexicographicActionSelector`, `ActionDecision`, `DecisionTrace`, `ReferenceCommitRevalidator` — all imported + exercised |
| **architecture / invariants** | **100 %** | canonical identity, hard-before-soft, fail-closed, explicit outcomes, state/action binding, decision traces, shadow-only, commit revalidation — all held in cloud |
| **test patterns** | **pattern-reused, domain-specific assertions** | fail-closed, determinism, bounded-sink, OFF-by-default, no-actuation invariants transferred as test *shapes*; the numbers are cloud |

### What the domain had to supply (the honest denominator)

The cloud adapter is **1,080 LOC** of new domain code (envelopes 178, constraints
355, adapter 320, composition 125, outcomes 51, init 51). This is the
irreducible per-domain cost: every new domain must define its own state/action/
evidence fields, its own real-evidence-backed constraints, its own outcome
interpretation, and its own authorization composition. **None of it required
touching the core** — which is exactly the reusability claim.

## Interpretation

The split landed almost exactly where the preregistration predicted: the
*decision machinery* is domain-neutral and was reused unchanged; the *domain
knowledge* (fields, thresholds, evidence source, authorization boundary) is new
per domain. The one nuance worth flagging: `NO_ACTIVE_FREEZE` uses a carried flag
rather than calling `BlackoutWindow.is_active` inside the evaluator, to keep
canonical identity timezone-independent — an adapter-level modelling choice, not a
core concession.
