# Prior Results and Scope (Phase 1)

*Minimal Evidence Obligation Policy and Internal Utility Pilot. Begins from the completed **Contextual
Evidence Obligation and Utility Calibration Study**, which recommended reducing the rich 90-rule
component to a small policy. Consumes all prior components **read-only**; enforced by
`minimal_evidence_policy/verify_prior_artifacts.py` (45 guarded artifacts, fails on drift).*

## What this track must not touch

Read-only, never modified: EvidenceAssurance, AssertionGate, ActionGate, ClaimIntegrity, ScopeIntegrity,
ExecutionGate, ModelPolicy, `evidence_obligation`, `bounded_shadow_pilot`, `customer_shadow_readiness`,
`governed_inference_pilot`, prior corpora/ground-truth/thresholds/evaluation-artifacts/freeze-manifests.
All new work lives under `minimal_evidence_policy/` and `docs/minimal_evidence_policy/`. The 45-artifact
guard (32 from the evidence_obligation guard + 13 evidence_obligation outcome-bearing artifacts) is the
mechanical proof of the boundary.

## Prior results recorded exactly

| Fact | Value |
|---|---|
| Prior natural-artifact clean allow (uniform burden) | **0%** |
| Prior over-qualification | **~85.5%** |
| Contextual obligation utility improvement | 0% → 29.6% (safe oracle) / 58.4% (rich reference) |
| Over-qualification after contextual obligation | 85.5% → ~2% |
| **Rich reference component adversarial unsafe allows** | **10** (model self-verification) |
| Rich reference clean allow | ~58.4% |
| **Risk-only comparator clean allow** | **~66.8%** |
| Risk-only adversarial unsafe allows | **0** |
| Ablation | `risk` is the primary load-bearing safety feature |
| Simulated reviewer agreement | 0.316 (low → real validation needed) |
| Prior architectural decision | Option 3: reduce to claim-type + source-role policy |
| Prior pilot decision | D: fix evidence obligation first |

## Why this is a simplification and real-validation study

The prior study proved the **concept** works (contextual obligation restores utility at zero conceptual
safety cost under the oracle) but that the **rich 90-rule classifier does not earn its complexity**: a
3-rule risk-only policy reached higher safe clean-allow (66.8% vs 58.4%) at zero adversarial unsafe (vs
10), and the rich classifier failed on model self-verification. This track therefore **simplifies rather
than builds another large classifier**: a minimal, explicit, monotonic policy with a non-negotiable risk
floor, upward-only modifiers, and hard structural invariants — and prepares it for **real human
validation** and an **internal single-tenant** pilot.

## Scope

- **Simplification-first.** Target ≤20 primary rules, 6 obligation outcomes, no learned model, every
  decision explainable in one trace.
- **Monotonic and fail-closed.** No modifier may lower the obligation below the risk floor; unknown
  critical metadata → human review; no model self-verification.
- **Read-only composition.** The minimal policy sits upstream of Evidence binding; it never modifies or
  lowers any frozen threshold.
- **New data.** New held-out natural artifacts, not the prior 857-set or the prior evidence_obligation
  held-out partition. NOT ENOUGH EVIDENCE returned honestly if natural supply is insufficient.
- **Real validation.** A real human-review study is a prerequisite for external readiness; simulated
  rubrics are never called human validation.
- **Bounded pilot.** Shadow-only, non-enforcing, single internal tenant, de-identified, no external
  customer onboarding, no production-readiness claim.

## Primary question

> Can a minimal, explicit evidence-obligation policy achieve useful natural-artifact clean-allow rates
> while preserving **zero unsafe high-risk and action allows** — based on a non-negotiable risk floor,
> limited upward-only claim-type and source-role modifiers, temporal/actionability escalation, explicit
> anti-self-verification invariants, and human review for unresolved cases?
