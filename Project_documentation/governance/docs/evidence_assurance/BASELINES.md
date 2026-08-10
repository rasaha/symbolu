# Baselines A–T (Phase 12)

*Implemented in `evidence_assurance/baselines.py`; evaluated by `evidence_assurance/eval_baselines.py`
→ `eval_results/baselines_v1.json`. Every baseline maps a case to one decision — **deliver the claim
as positively supported? (yes/no)** — which is exactly what the safety endpoints score.*

## Endpoints

- **correlated-failure escape** (primary safety, lower better): fraction of the
  `CORRELATED_FAILURE` + `ADVERSARIAL_PROVENANCE` trap cases delivered as supported. Every trap case
  is gold-unsupported, so any delivery there is an escape. This is the headline number.
- **escape** (overall, lower better): delivered-as-supported over all gold-unsupported cases.
- **false block** (co-primary, lower better): refused delivery over all gold-supported cases.

Only `T_oracle` sees TRUE latent state; all others see OBSERVED metadata only (anti-circularity).

## The 20 baselines

| Class | Baselines |
|---|---|
| Naive / trivial | `A_always_deliver`, `H_always_block` |
| Corroboration counting | `B_source_count`, `C_diversity` |
| Downstream signals (AssertionGate-style) | `D_grounding`, `E_entailment`, `F_grounding_and_entail`, `G_passage_signal`, `I_majority_signal` |
| Provenance / independence | `J_provenance_conf`, `K_independence` |
| Structured EA layers | `L_alignment`, `M_counterevidence`, `N_indep_align`, `O_indep_align_counter` |
| Composite / gated | `P_full_ea_rule`, `Q_authority_grounding`, `R_fresh_grounding` |
| Learned | `S_learned_comparator` (fixed-weight logistic-style over observed signals) |
| Upper bound | `T_oracle` |

## Result (ea_corpus_v1_1: 624 cases, 132 supported, 492 unsupported, 156 trap)

Ranked by correlated-failure escape, then false-block:

| baseline | signal-only | corr-failure escape | escape | false block |
|---|:--:|--:|--:|--:|
| `K_independence` | | **0.000** | 0.366 | **0.000** |
| `T_oracle` | | **0.000** | **0.000** | **0.000** |
| `L_alignment` | | **0.000** | 0.313 | 0.432 |
| `N_indep_align` | | **0.000** | 0.124 | 0.432 |
| `O_indep_align_counter` | | **0.000** | 0.039 | 0.432 |
| `P_full_ea_rule` | | **0.000** | **0.000** | 0.432 |
| `H_always_block` | | 0.000 | 0.000 | 1.000 |
| `M_counterevidence` | | 0.442 | 0.612 | 0.000 |
| `D_grounding` | yes | 0.667 | 0.789 | 0.000 |
| `E_entailment` | yes | 0.667 | 0.789 | 0.000 |
| `F_grounding_and_entail` | yes | 0.667 | 0.789 | 0.000 |
| `I_majority_signal` | yes | 0.667 | 0.789 | 0.000 |
| `J_provenance_conf` | | 0.667 | 0.894 | 0.000 |
| `Q_authority_grounding` | | 0.667 | 0.740 | 0.000 |
| `R_fresh_grounding` | | 0.667 | 0.577 | 0.000 |
| `A_always_deliver` | yes | 1.000 | 1.000 | 0.000 |
| `B_source_count` | yes | 1.000 | 1.000 | 0.000 |
| `C_diversity` | yes | 1.000 | 1.000 | 0.000 |
| `G_passage_signal` | yes | 1.000 | 1.000 | 0.000 |
| `S_learned_comparator` | | 1.000 | 1.000 | 0.000 |

## What the baselines establish (honest reading)

1. **The correlated-failure trap is real and defeats signal-only methods.** Every downstream-signal
   baseline (grounding, entailment, source-count, diversity, majority-vote) escapes **0.67–1.00** of
   the trap. Grounding and entailment are *high* on aligned-but-wrong cases by construction, so
   trusting them delivers correlated failures as supported.

2. **A tuned classifier over the same signals does not rescue it.** `S_learned_comparator` — a
   fixed-weight logistic-style scorer over the observed signals — escapes **1.000** of the trap. The
   problem is not model capacity; it is that the *inputs* carry no independence/provenance information.

3. **Independence + alignment + counterevidence drives trap escape to 0.** `O_indep_align_counter`
   and `P_full_ea_rule` reach **0.000** correlated-failure escape (and 0.000 / 0.039 overall escape).
   This is the signal the study is testing: provenance-aware, independence-aware verification catches
   what downstream composition cannot.

4. **The naive composite over-blocks — this is the open problem, not a solved one.** `P_full_ea_rule`
   and the alignment-based composites false-block **0.432** of gold-supported cases. The main cause:
   `VERIFIED_WITH_LIMITATIONS` (overstated-but-supported) is treated by strict alignment as scope
   misalignment and blocked, when it should be *qualified*, not refused. This motivates the Phase-13
   reference component (M8), which must map DEPENDENT / overstated / low-independence to **QUALIFY**
   rather than block — recovering safety without paying full false-block cost.

5. **No single layer suffices.** `K_independence` alone is safe on the trap (0.000) but misses stale /
   conflicted independent sources (0.366 overall escape); `M_counterevidence` alone catches only the
   subset with discoverable counterevidence (0.442 trap escape). The layers are complementary, which
   is the architecture Phase 13 assembles and Phase 18 ablates.
