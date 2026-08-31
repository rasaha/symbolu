# Limitations and Falsification (Phase 22)

*`minimal_evidence_policy/architectural_decision.py` → `eval_results/decision.json`. All 17 nulls resolved
from the frozen evidence: **12 rejected, 4 retained, 1 NOT EVALUATED.** Negatives preserved.*

## Direct answers

- **Did risk-only perform as well?** **No** — risk-only leaks 52 held-out unsafe allows; the minimal
  policy 0. (H0-1 rejected.)
- **Did claim type add utility/safety?** **Yes** — it is safety-critical: removing it adds 43 unsafe
  allows. (H0-2 rejected.)
- **Did source role add utility?** **No** — not a load-bearing modifier here. (H0-3 retained.)
- **Did anti-self-verification prevent real failures?** **Nuanced — retained.** On this dataset the
  invariants add **0 marginal** safety because the risk floor + claim-type modifiers already catch the
  constructed traps (the adversarial self-verification cases use claim families that independently
  escalate to E3). The invariants are retained as **classification-independent insurance**; a cleaner
  adversarial isolation (self-verification on a low-burden claim family) is needed to measure their
  marginal value and is future work. (H0-4 retained, honestly.)
- **Did upward-only monotonicity matter?** **Yes** — 0/528 violations, and error-propagation shows the
  burden-stripping downgrades monotonicity forbids are the dangerous ones. (H0-5 rejected.)
- **Did real reviewers agree?** **NOT EVALUATED** — no real reviewers. (H0-12.)
- **Did review burden become acceptable?** **Yes** — 9.6% < 25%. (H0-11 rejected.)
- **Did the minimal policy beat the rich component?** **Yes on safety** — 0 vs 85 total unsafe at similar
  clean allow. (H0-13 rejected.)
- **Did global threshold reduction remain unsafe?** **Yes** — 75+ adversarial unsafe. (H0-14 rejected.)
- **Did clean allow become operationally useful?** **Yes** — 0% → 50%. (H0-7/H0-16 rejected.)
- **Did high-risk / action safety remain intact?** **Yes** — 0 unsafe in both. (H0-9/H0-10 rejected.)
- **Is an external shadow pilot justified?** **No** — human validation NOT EVALUATED. (H0-17 retained.)
- **Is another internal pilot required?** **Yes** — as the vehicle for real human validation before any
  external step.

## Null ledger

| Retained / NE (honest negatives) | Why |
|---|---|
| H0-3 source-role no utility | source role not load-bearing here |
| H0-4 anti-self-verification no marginal safety | modifiers already catch the traps on this set |
| H0-6 review fallback no value | M equals Full on metrics here |
| H0-12 reviewers cannot agree | NOT EVALUATED (no real reviewers) |
| H0-17 external readiness blocked | human validation missing |

Rejected: H0-1, H0-2, H0-5, H0-7, H0-8, H0-9, H0-10, H0-11, H0-13, H0-14, H0-15, H0-16.

## Limitations (stated plainly)

1. **The adversarial set does not cleanly isolate the invariants** — its self-verification cases also
   trigger claim-type escalation, so the invariants' marginal safety is under-measured (H0-4 could not be
   cleanly rejected). This is the main methodological gap.
2. **Human validation is NOT EVALUATED** — the reviewer proxy is an independent-rubric simulation, never
   human validation.
3. **The gold is largely a function of claim-type + risk**, so a learned map recovers it — the same
   caveat as the prior track.
4. **Available evidence is modelled** — natural artifacts carry no real external/telemetry evidence; the
   clean-allow ceiling is conditioned on this model.
5. **No production validation** — shadow-only, read-only, single internal tenant, single window.
