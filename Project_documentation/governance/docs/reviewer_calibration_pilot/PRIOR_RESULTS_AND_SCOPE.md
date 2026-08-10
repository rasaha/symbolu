# Prior Results and Scope (Phase 1)

*Real Reviewer Calibration and Internal Single-Tenant Utility Pilot. Begins from the completed **Minimal
Evidence Obligation Policy and Internal Utility Pilot**, whose one outstanding gate was **real human
validation**. Consumes all prior components **read-only**; enforced by
`reviewer_calibration_pilot/verify_prior_artifacts.py` (59 guarded artifacts, fails on drift).*

## What this track must not touch

Read-only, never modified: `minimal_evidence_policy`, `evidence_obligation`, EvidenceAssurance,
AssertionGate, ActionGate, ClaimIntegrity, ScopeIntegrity, ExecutionGate, ModelPolicy,
`bounded_shadow_pilot`, `customer_shadow_readiness`, `governed_inference_pilot`, prior corpora/ground-
truth/thresholds/evaluation-artifacts/freeze-manifests. **The frozen minimal policy must not be modified
during outcome-bearing review, and no rule may be tuned on the final review set.** All new work lives
under `reviewer_calibration_pilot/` and `docs/reviewer_calibration_pilot/`. The 59-artifact guard (45
from the minimal_evidence_policy guard + 14 minimal_evidence_policy outcome-bearing artifacts) is the
mechanical proof of the boundary.

## Frozen minimal policy recorded exactly

| Fact | Value |
|---|---|
| Policy version | `minimal_evidence_policy_v1` |
| Obligation levels | 6 (E0 < E1 < E2 < E3 < E4 < ER) |
| Primary policy-logic rules | ~12 (risk floor + upward-only modifiers) |
| Structural invariants | 12 (INV-1..INV-12) |
| Clean allow (technical eval) | ~50% |
| Over-qualification | 0% |
| Unsafe high-risk allows | 0 |
| Unsafe action allows | 0 |
| Self-verification escapes | 0 |
| Circular-evidence escapes | 0 |
| Monotonicity violations | 0 / 528 |
| Frozen technical criteria | 10 / 10 pass |
| **Human validation** | **NOT EVALUATED** |

## Why this track must not alter the policy during review

The minimal policy passed all frozen technical criteria; the only missing evidence is whether **real
reviewers** understand and agree with it. Altering the policy while measuring human agreement would
conflate policy change with the very quantity being measured. So the policy is **frozen read-only**
throughout, and the final review set is never used to tune it — the track measures, it does not
calibrate-by-fitting.

## The central constraint (and this environment)

This track **requires real human reviewers**. Simulated or rubric-based outputs must never be presented
as human validation, and reviewer agreement must never be inferred from deterministic rubrics. Per the
governing spec: *if fewer than 2 real reviewers are available, complete only the preparatory and
technical phases, return **NOT ENOUGH HUMAN EVIDENCE**, and do not recommend an external pilot.* This
document records that constraint up front; the human-validation gap and its consequence are detailed in
`HUMAN_VALIDATION_GAP.md`.

## Primary question

> Can real reviewers use the frozen minimal evidence-obligation policy consistently, and does the policy
> produce decisions that are safe, useful, understandable, and operationally practical on naturally
> occurring internal artifacts?
