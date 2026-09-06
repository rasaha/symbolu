# ADR — Governed Value observation ingress (GV-DEP, GV-PRODUCER, GV-ORDER)

**Status:** rulings ratified by the owner, 2026-09-06; implemented in
`ugence-governed-value` 0.3.0.
**Maturity:** the kernel remains **EXPERIMENTAL**, a downstream reported-value
calculation over caller-reported, unverified inputs. It still emits exactly
`POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED` and can never claim a figure is
observed, attributed or verified. **Nothing here raises the emitted
classification, and nothing here is production-ready.**
**Predecessors:** `ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md` (D-1 … D-18,
§23 anti-gaming invariants, §25 milestones),
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 5, row 4).

## 1 — The question

Wave 5 row 4 names the GV-2 evidence layer and the GV-4 authority layer as
absent. Which half is buildable now? Answer: the evidence *contracts* already
exist and nobody uses them, so the kernel can begin carrying typed observations
today; the authority half cannot be built at all until an attesting authority
exists, and the one candidate is itself reference-grade.

## 2 — Audit findings

| Finding | Evidence |
| --- | --- |
| The kernel is a stdlib-only leaf with no dependency at all, not even on the shared contract layer `[V]` | `pyproject.toml` before this change: `dependencies = []` |
| It emits one classification cell as two module constants, invariant across every scorability verdict `[V]` | `services/scorer.py` `_EVIDENCE` / `_AUTHORITY`; `tests/contract/test_classification.py` |
| The full GV-2E evidence vocabulary already ships: the five axes, `EvidenceProvenance`, `MetricClaim`, and `MetricObservation`, which fixes `OBSERVED` internally, requires an `AssessmentWindow` and evidence references, and refuses `MODELED` `[V]` | `ugence-governance-contracts` `contracts/evidence.py`, released at 0.2.0 |
| **No package under any `src/` constructs a `MetricObservation`.** The only references outside the contracts package are four test files `[V]` | repository-wide search over `packages/*/src` |
| The authority seam existed at 0.1.0 and was deliberately removed at 0.2.0 `[V]` | `CHANGELOG.md`, *Removed (deferred)*: "the authority-adapter seam (GV-4)"; `integrations/` is gone |
| Elevation above the weakest cell cannot come from a caller label: it requires provenance **and** method **and** authority, and a producer may never attest its own output `[R]` | predecessor ADR §23 invariants 1 and 10 |
| The only attesting machinery in this repository is the Trusted Evidence Authority, which is reference-grade, wired to no deployment, and whose custody question DD-10b is still deferred `[I]` | `ADR_UGENCE_TEA_PRODUCTION_TRUST_ANCHOR_RESOLVER.md`; DD-10b |

## 3 — Rulings

| Ruling | Consequence in code |
| --- | --- |
| **GV-DEP = DEPEND_ON_GOVERNANCE_CONTRACTS** | `pyproject.toml` declares `ugence-governance-contracts>=0.2.0`, the release that first defines `MetricObservation`. The leaf posture — `dependencies = []` — **ends**, deliberately. Copying the shapes, the D-22(4)/D-34 precedent, is closed here: BR-2 copies from a package it is *forbidden* to import, whereas `governance-contracts` is the shared contract layer every capability already depends on, and a second copy of the evidence vocabulary is the fork that layer exists to prevent. No third-party dependency is added; the offline distribution verifier now builds a wheelhouse holding exactly this package and that one. |
| **GV-PRODUCER = TYPED_INGRESS_ON_THE_KERNEL** | No new package, and the kernel produces nothing. `admit_observations(case, observations)` accepts already-constructed `MetricObservation`s at a typed seam and binds each to the case: exact type, matching `tenant_id`, `governed_unit` equal to the case's natural unit, and no duplicate `observation_id`. Any violation raises `ObservationBindingError` and no result is produced. Whoever constructs the observations is the composition root's concern, exactly as RA-8's attested ingress leaves its attester to its deployment. |
| **GV-ORDER = BUILD_OBSERVED_RUNG_NOW** | The plumbing lands now; the classification does not move. `GovernedValueResult` gains `observed_metrics`, a tuple of `ObservedMetric` records — observation id, metric id, governed unit, window bounds, evidence-reference count and content digest — carried **outside every monetary term and outside the scorability verdict**. `evidence_status` stays `REPORTED` and `authority_status` stays `UNVERIFIED` with observations present, pinned by test. |

## 4 — Why OBSERVED is not emitted, stated so it is not read as an oversight

`MetricObservation` fixes `OBSERVED` on its own axis, and it would be easy to
read that as licence for the kernel to emit `EvidenceStatus.OBSERVED` once one
is bound. It is not. The caller who supplies the case also supplies the
observation, so emitting `OBSERVED` on that basis is precisely the
caller-elevated evidence §23 invariant 1 forbids — the contract's structural
rules constrain the *shape* of the claim, not the honesty of whoever filled it
in. Elevation waits for an authority that can say the observation was made,
which is GV-4, which is blocked. What the kernel gains now is that the
observation is **typed, bound and recorded** rather than absent, so the seam
exists when the authority does.

## 5 — What did not move

Every GV-0 and GV-1 rule: additive unbounded expected loss, no re-discounting of
reported benefit, investment distinct from cost-to-serve, historical loss
distinct from forward expected loss, exact minor-unit money, `None` unequal to
explicit zero, determinism, fail-closed suppression of the headline, geography
and domain touching no money, and `reported_confidence` staying out of the
arithmetic. No monetary term, guard, reason or advisory reads `observed_metrics`.

## 6 — Next step

GV-4 stays blocked on DD-10b and on the Trusted Evidence Authority's own
maturity. The producer of observations is a deployment concern until an
authority exists to attest them.
