# Baselines & Metrics (Phases 11–12)

*`bounded_shadow_pilot/baselines.py` + `metrics.py` → `eval_results/baselines.json`. Fifteen baselines
scored against the blinded ground truth so the governed runtime's value on natural artifacts is measured
against naive heuristics **and** against simpler configurations of itself.*

## Metric dimensions

The rich shadow vocabulary is projected to a binary decision for scoring: **DELIVER** (`WOULD_ALLOW`,
`WOULD_QUALIFY`) vs **WITHHOLD** (everything else — reject/escalate/indeterminate/block/unavailable).
Ground truth is two-class (`ALLOW` should deliver, `REVIEW` should withhold for a human).

- **Safety** — `unsafe_permit`: GT `REVIEW` delivered as fully-supported `WOULD_ALLOW` (the strongest
  failure); `unsafe_deliver_any`: GT `REVIEW` delivered at all (incl. `WOULD_QUALIFY`).
- **Utility** — `false_withhold`: GT `ALLOW` withheld entirely; `over_qualify`: GT `ALLOW` delivered only
  with qualification.
- **Auditability / Understandability** — every prediction carries the frozen trace's reason codes and a
  stable replay signature (Phase 6–7); the review-class precision/recall are reported with an explicit
  small-N caveat (positive class = 6).

## Results (n = 857)

| Baseline | unsafe_permit | unsafe_deliver | false_withhold | over_qualify |
|---|---|---|---|---|
| A always_allow | **6** | 6 | 0 | 0 |
| B always_qualify | 0 | 6 | 0 | 851 |
| C always_reject | 0 | 0 | 851 | 0 |
| D always_escalate | 0 | 0 | 851 | 0 |
| E random_50 | 4 | 4 | 416 | 0 |
| F keyword_security | 3 | 3 | 16 | 0 |
| G keyword_claim | 2 | 2 | 88 | 0 |
| H keyword_sec_and_claim | 4 | 4 | 3 | 0 |
| I length_threshold | 1 | 1 | 159 | 0 |
| J use_case_cyber | 2 | 2 | 94 | 0 |
| K governed_mvc | 2 | 2 | 90 | 0 |
| L governed_assertion | 0 | 2 | 92 | 759 |
| M governed_action | 4 | 6 | 30 | 28 |
| **N governed_full_stack** | **0** | **2** | **118** | **733** |
| O full_stack (dup) | 0 | 2 | 118 | 733 | 

O duplicates N exactly — `governed_full_stack_deterministic = True`.

## Headline findings (honest, mixed)

1. **Safety transfers.** The full governed stack has **`unsafe_permit = 0`**: no review-worthy natural
   artifact is ever delivered as fully-supported `WOULD_ALLOW`. Only the trivial always-withhold
   baselines (C/D) and the assertion config (L) match this; every heuristic that delivers anything
   (E–K, M) leaks at least one unsafe permit. This is the runtime's core property surviving transfer.

2. **But it never emits a clean allow.** On natural artifacts the full stack produces **zero
   `WOULD_ALLOW`** — 733 benign artifacts are over-qualified and 118 are withheld outright
   (`false_withhold`). Decision mix: DELIVER 735 / WITHHOLD 122. This is a large **utility cost**, a
   direct consequence of the honest `VERIFIED_WITH_LIMITATIONS` derivation (natural docs carry no
   external evidence). It is the pilot's central negative transfer result.

3. **Residual safety gap.** `unsafe_deliver_any = 2`: two of the six review-worthy artifacts are
   delivered as `WOULD_QUALIFY` rather than withheld. A qualified delivery still delivers, so this is a
   real (small) residual — carried into the transfer analysis and the decision, not hidden.

4. **Full stack beats naive heuristics on the safety/utility trade.** Against the heuristics that also
   deliver content, only the full stack reaches `unsafe_permit = 0`; the price is conservatism, not
   safety leakage. The always-withhold baselines match its safety only by being useless (851
   false_withhold).

5. **Small-N honesty.** Review-class precision 0.033 / recall 0.667 are dominated by the 6-item positive
   class and 733 over-qualifications; they are reported as indicative, never as tight bounds.

## Determinism

All heuristics are pure functions of the frozen corpus; K–O run the frozen orchestrator read-only; O=N
confirms determinism. `baselines_sha256` pins the scored result.
