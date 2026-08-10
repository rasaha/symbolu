# Safety–Utility Calibration Frontier (Phase 17)

*`evidence_obligation/calibration_frontier.py` → `eval_results/calibration_frontier.json`. Which
utility-improvement strategies buy clean-allow **without** buying unsafe allows? The full policy must
earn its complexity.*

## The frontier (held-out clean-allow vs safety)

| Strategy | clean allow | high-risk unsafe | adversarial unsafe | safe & useful |
|---|---|---|---|---|
| global_threshold_lowering | 1.000 | 15 | 100 | — |
| lowrisk_bypass | 1.000 | 15 | 100 | — |
| **risk_only_contextual** | **0.668** | 0 | 0 | **YES** |
| full_evidence_obligation (Q) | 0.584 | 0 | 10 | — |
| claim_type_contextual | 0.344 | 2 | 20 | — |
| **learned_comparator (S)** | 0.332 | 0 | 0 | **YES** |
| **oracle_obligation** | 0.296 | 0 | 0 | **YES** |
| **simple_contextual (P)** | 0.264 | 0 | 0 | **YES** |
| prior_uniform | 0.000 | 0 | 0 | — |

Safe = 0 adversarial unsafe AND ≤1 high-risk unsafe. Prior baseline: 0% clean allow, 85.5%
over-qualification.

## Findings that shape the decision

1. **Burden-stripping strategies dominate on utility but are inadmissible.** `global_threshold_lowering`
   and `lowrisk_bypass` reach 100% clean allow but leak 15 high-risk and 100 adversarial unsafe allows.
   The global-threshold change is decisively unsafe — **H0-16 rejected**.

2. **The full component does NOT dominate the frontier.** `full_evidence_obligation` (Q) reaches 58.4%
   clean allow but crosses into unsafe territory (10 adversarial unsafe), so it is **not** on the
   safe-and-useful frontier. Meanwhile **risk_only_contextual (C) reaches the highest safe clean-allow
   (66.8%)** with 0 high-risk and 0 adversarial unsafe — a far simpler policy. This is a strong
   **H0-2 / H0-13 / H0-17** signal: a simple risk-based or learned calibration occupies the safe-useful
   region that the full component does not.

3. **A safe, useful region exists and is large.** oracle (29.6%), learned (33.2%), simple-contextual
   (26.4%), and risk-only (66.8%) are all safe-and-useful and all beat the prior 0% clean allow — so the
   central hypothesis (contextual obligation improves utility without weakening safety) is **supported at
   the concept level**, just not uniquely by the richest component.

4. **Caveat on risk-only.** C's 66.8% comes with 16 *low/medium-risk* unsafe allows (0 high-risk, 0
   adversarial) — it clean-allows low-risk claims whose gold wanted corroboration. Whether that residual
   is acceptable is a product judgment; it does not touch the safety-critical (high-risk/adversarial)
   surface. The learned comparator (S) trades some clean-allow for near-zero total unsafe (1).

## Bottom line for the architecture

The complexity of the full `EvidenceObligation` component is **not** justified by this frontier: simpler
safe strategies (risk-only, learned, simple-contextual) reach the safe-and-useful region and the full
component does not dominate them. The obligation *concept* is validated (oracle is safe and useful); the
*specific rich classifier* over-allows. This points the architectural decision toward **reduce/simplify**
(claim-type+risk or risk-tier policy) and the pilot decision toward **fix the obligation classifier's
safety first**, both examined in the ablation (Phase 18) and decision (Phase 25).
