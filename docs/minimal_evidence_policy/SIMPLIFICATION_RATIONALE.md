# Simplification Rationale (Phase 1)

*Why replace the rich 90-rule EvidenceObligation component with a minimal monotonic policy, and what the
minimal policy must preserve.*

## The evidence for simplifying

The prior study's ablation, complexity challenge, and calibration frontier converged on one conclusion:

1. **The rich component does not dominate.** Risk-only (3 rules) reached higher safe clean-allow (66.8%)
   than the rich reference (58.4%), at **0 adversarial unsafe** vs the rich component's **10**.
2. **Most of the machinery was inert.** Ablation showed the authority-guard, risk-escalation, and
   structural-floor logic changed nothing on the natural data; only `risk` was load-bearing for safety
   and `source_role` for utility.
3. **The rich classifier had a concrete safety blind spot** — it clean-allowed model self-verification
   ("the model states its output is verified") because that pattern isn't a learned feature.
4. **Fine obligation labels were unstable** (simulated reviewer agreement 0.316), so a high-resolution
   14-class classifier is trying to be more precise than the ground truth supports.

The lesson: precision beyond what the labels support **adds complexity and adversarial surface without
adding safe utility**. The remedy is not a better big classifier — it is a small, explicit, auditable
policy whose safety comes from **hard invariants**, not learned features.

## What the minimal policy keeps and drops

| Keep | Drop |
|---|---|
| Non-negotiable **risk floor** (the load-bearing safety feature) | The 90-rule learned-ish surface |
| **Upward-only** modifiers (claim-type, source-role, temporal, actionability) | Downward adjustments of any kind |
| **Explicit structural invariants** (anti-self-verification, etc.) as hard rules | Inference of authority from "internal" |
| **6 ordered outcomes** (E0<E1<E2<E3<E4<ER) | The 14-type high-resolution vocabulary |
| **Human review** for unresolved / triggered-invariant cases | Optimistic defaults on unknown metadata |
| The obligation-relative contract ("standard met ≠ truth") | Any lowering of frozen thresholds |

## The design commitments

- **Monotonicity as a safety property.** Increasing risk, actionability, uncertainty, or freshness
  requirements can only *raise* the obligation. This is testable exhaustively (Phase 15) and any
  violation is a pilot blocker.
- **Invariants as hard rules, not features.** The self-verification failure that beat the rich classifier
  becomes `INV-1` (no model self-verification) — an explicit, un-learnable rule.
- **Complexity budget.** ≤20 primary rules, no learned model, no hidden weighted aggregate, ≤6 outcomes,
  every decision explainable in one trace. If exceeded, documented and justified.
- **Earn its use.** The minimal policy is compared against risk-only, claim+source+risk, the rich
  component, and the oracle; it is selected only if the frontier justifies it — never "because it was
  proposed."

## What success looks like

A policy that: recovers most of the safe utility (clean-allow materially above the prior 0%, over-
qualification materially below 85.5%); holds **0 unsafe high-risk allows, 0 unsafe action allows, 0
self-verification escapes**; keeps review burden bounded; is monotonic; is explainable in one trace; and
is ready for an **internal single-tenant** pilot with **real reviewers** — not an external customer.
