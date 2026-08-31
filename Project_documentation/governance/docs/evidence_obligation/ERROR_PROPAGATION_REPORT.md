# Error-Propagation Report (Phase 16)

*`evidence_obligation/error_propagation.py` → `eval_results/error_propagation.json`. Injects each
canonical obligation error into the correct (oracle) obligation and measures how far it propagates into
the frozen EvidenceAssurance delivery.*

## Baseline

At the **correct (gold) obligations, unsafe allows = 0** on held-out + adversarial. This re-confirms the
concept is safe when obligations are right; every unsafe allow downstream is an *obligation error*.

## Induced unsafe allows per error (887 items)

| Injected error | items affected | induced unsafe allows |
|---|---|---|
| **factual_as_opinion** | 87 | **87** |
| **high_risk_as_low_risk** | 75 | **75** |
| **external_reduced_to_context** | 39 | **39** |
| impl_assigned_to_marketing | 55 | 6 |
| policy_treated_as_impl | 20 | 0 |
| stale_policy_as_current | 1 | 0 |
| attribution_as_truth | 2 | 0 |
| internal_as_independent | 3 | 0 |
| fixture_as_telemetry | 69 | 0 |
| unknown_forced_authoritative | 53 | 0 |
| human_review_suppressed | 53 | 0 |
| opinion_as_factual | 0 | 0 |

## What propagates and what the contract absorbs

- **Dangerous = burden-stripping errors.** The three high-propagation errors all *remove* an evidence
  burden: treating a factual claim as opinion (87), downgrading a high-risk claim to low-risk (75), and
  reducing an external requirement to context (39). These are precisely the "unsafe shortcut" directions
  and precisely the failure mode of the reference classifier's self-verification blind spot.
- **Absorbed = evidence-absent errors.** Errors that *raise* the burden or that name evidence the
  artifact doesn't have propagate to **0** unsafe allows: `policy_treated_as_impl` (no implementation
  evidence → INSUFFICIENT), `fixture_as_telemetry` (no telemetry → INSUFFICIENT),
  `internal_as_independent` (no external → INSUFFICIENT). The contract's fail-closed asymmetry (a
  standard requiring absent evidence can never yield VERIFIED) absorbs them.

## Reading + a stated metric limitation

The safety of the whole pipeline rests on **not stripping evidence burden**. Risk-downgrade and
factual→opinion are the errors to defend against — which is why `risk.py` resolves ambiguity upward and
the taxonomy floors preference/opinion off the no-gate class at high risk.

**Metric limitation (disclosed):** `human_review_suppressed → context` shows 0 induced unsafe because the
unsafe-allow metric counts only claims whose *gold* needs independent evidence; a suppressed human-review
that becomes a clean allow is a control failure not captured by this particular endpoint. It is caught
instead by the review-workflow requirement (the obligation still carries `human_review_requirement`) and
is noted here rather than hidden.
