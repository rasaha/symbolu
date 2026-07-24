# Limitations and Falsification (Phase 24)

*`evidence_obligation/architectural_decision.py` → `eval_results/decision.json`. All 18 preregistered
nulls resolved from the frozen evidence: **12 rejected, 6 retained.** Negative and null findings are
preserved, not buried.*

## Direct answers

- **Did contextual obligations improve utility?** **Yes, materially.** Clean allow 0% → 29.6% (safe
  oracle) / 58.4% (reference); over-qualification 85.5% → 2%. (H0-9, H0-10 rejected.)
- **Did safety remain intact?** **At the concept level, yes** (oracle: 0 unsafe everywhere). **For the
  reference classifier, no** — it leaks 10 adversarial disguise cases. (H0-11 retained for the
  component, rejected for the concept.)
- **Did risk tier alone perform as well?** **Yes — better.** Risk-only reaches 0.668 clean allow at 0
  adversarial unsafe and 3 rules, beating the reference. (H0-2 retained.)
- **Did claim type alone perform as well?** No — the reference beats claim-type-only. (H0-3 rejected.)
- **Did source role add value?** Yes, for utility (ablation: −27pp clean allow when removed); not for
  safety. (H0-4 rejected.)
- **Was implementation evidence safe?** Yes — 0 unsafe self-support, circular guard holds. (H0-6
  rejected.)
- **Was the no-evidence-required class safe?** Yes — 0/500 high-risk-or-factual no-gate assignments.
  (H0-8 rejected.)
- **Did global threshold reduction fail?** Yes — 100 adversarial unsafe allows. (H0-16 rejected.)
- **Did EvidenceAssurance already capture obligation differences?** No — uniform-derivation EA is 0%
  clean; obligation-fed EA is 58%. The obligation is the lever. (H0-12 rejected.)
- **Did the simple comparator match the full component?** **Yes** — risk-only and learned match/beat it.
  (H0-13 retained.)
- **Did human disagreement undermine the concept?** Partly — simulated reviewer agreement is 0.316; the
  concept survives via adjudication, but fine labels are unstable. (H0-14 retained, pending real study.)
- **Is a distinct EvidenceObligation stage justified?** **No** — a 3-rule risk / claim+source policy
  suffices; the 90-rule stage is not justified. (H0-17 retained.)
- **Is it needed only for some domains?** The hard-floor value (medical/financial/legal) is
  domain-concentrated; the general utility gain is broad. A high-risk-domain-only deployment is a viable
  reduced option.
- **Is the system now ready for an external shadow pilot?** **No** — adversarial leak + reviewer
  instability + no real review study. (H0-18 retained.)

## Null ledger (12 rejected / 6 retained)

| Retained (honest negatives) | Why |
|---|---|
| H0-2 risk-tier alone as good | risk-only dominates the component |
| H0-11 weakens high-risk safety | reference leaks 10 adversarial (concept safe) |
| H0-13 simple comparator matches | risk-only / learned match-or-beat at far lower complexity |
| H0-14 reviewers disagree too much | simulated agreement 0.316 |
| H0-17 distinct stage unnecessary | 90-rule stage not justified over 3 rules |
| H0-18 readiness still blocked | leak + instability + no real review |

Rejected: H0-1, H0-3, H0-4, H0-5, H0-6, H0-7, H0-8, H0-9, H0-10, H0-12, H0-15, H0-16.

## Limitations (stated plainly)

1. **The gold is largely a function of claim-type + risk**, so a learned map over those features recovers
   it well — inflating the case for simplification and deflating apparent component value.
2. **The reviewer study is simulated**, not human. Reviewer agreement and override skew are proxies.
3. **Available evidence is modelled**, not real — natural artifacts carry no true external/telemetry/
   policy evidence; the safe utility ceiling (oracle 29.6%) is conditioned on this model.
4. **Authority accuracy 1.0 is on the canonical 16-case set**, not the full natural corpus.
5. **No production validation** — shadow-only, read-only, de-identified, single execution window.
6. **The reference classifier has a concrete blind spot** (model self-verification framed as neutral
   statement) reported, not patched, to avoid overfitting the adversarial set.
