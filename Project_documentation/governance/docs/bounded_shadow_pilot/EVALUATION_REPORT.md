# Bounded Natural-Artifact Shadow Pilot — Evaluation Report (Phases 19–20)

*The single scored run and its synthesis. `bounded_shadow_pilot/pilot_execution.py` →
`eval_results/pilot_execution.json`. Answers the pilot's research question with falsifiable evidence.*

## Research question

> Does the governed inference runtime remain safe, useful, auditable, and understandable when applied to
> naturally occurring artifacts that were not designed for its test corpora?

## Execution (n = 857, frozen natural corpus, single scored run)

- **Guards:** prior-artifact guard (22) intact; eval freeze (7 artifacts) intact — verified **before**
  scoring.
- **Final distribution:** `WOULD_QUALIFY` 735 · `EVIDENCE_UNAVAILABLE` 67 · `WOULD_ESCALATE` 27 ·
  `WOULD_CONSTRAIN_ACTION` 25 · `INDETERMINATE` 3. **Zero `WOULD_ALLOW`.**
- **Safety:** `unsafe_permit = 0`; every record `enforced=False`.
- **Native ActionGate:** 28 derived actions, **all preserved as native `SIMULATE_AND_RETRY`** (no
  collapse, no GATE_ERROR).
- **Stop conditions:** all six PASS.
- **Pilot outcome: `COMPLETED_NO_STOP`.**

## Findings by dimension

### Safe — YES (transfers)

Zero fully-supported unsafe permits on natural artifacts; every operational fault and the native
ActionGate fail closed; no path enforces. The safety property established on the structured corpus
**transfers** to natural text. Residual: 2 of 6 review-worthy artifacts are delivered as `WOULD_QUALIFY`
rather than withheld — small, disclosed, and not a fully-supported escape.

### Useful — NO (does not transfer, as configured)

On natural artifacts the runtime emits **0% clean allow**: 85.5% over-qualified, 13.8% withheld. The
adversarial derivation-sensitivity probe shows this is **evidence-driven** — flipping the derived
evidence base to optimistic `VERIFIED` restores an 83.3% clean-allow rate. The runtime is not broken; an
**evidence-grounded** runtime conservatively qualifies **evidence-free** natural text. Utility does not
transfer without an evidence-acquisition step or a natural-text calibration of the evidence stage.

### Auditable — YES (transfers)

Full-stack determinism holds on natural inputs (O == N); every record carries a stable replay signature;
frozen audit completeness 1.0. The audit/replay property transfers.

### Understandable — PARTIAL

Every decision carries reason codes, a native ActionGate outcome (zero loss), and derivation provenance.
But the dominant disposition (`WOULD_QUALIFY`, 85.5%) is uniform and evidence-driven, so per-artifact
explanations are honest yet **low-information** — they largely restate "no external evidence". Reviewer
burden is 11.6% (1 in 9), concentrated in `EVIDENCE_UNAVAILABLE`/`WOULD_ESCALATE`.

## Mandatory ActionGate check

Native semantics preserved end-to-end: all six outcomes reproduced (Phase 5), native semantic loss 0%,
no safety-relevant outcome collapsed, 28 real derived actions decided natively in execution. **No pilot
blocker.**

## Falsification summary

Six preregistered nulls, all rejected: safety, native-ActionGate-preservation, determinism, evidence-
sufficiency (857 ≥ 200), and non-contamination stand; the utility-transfer null is rejected in the
**negative** direction (utility does not transfer). The headline is stress-tested by the derivation-
sensitivity probe.

## One-line result

> On naturally occurring artifacts the governed runtime is **safe and auditable and preserves native
> ActionGate semantics with zero loss**, but — as configured for evidence-grounded structured inputs —
> it is **not yet useful** on evidence-free natural text, over-qualifying 85.5% of benign documentation;
> the effect is provably evidence-driven, not a safety regression. Pilot completed with no stop
> condition triggered.
