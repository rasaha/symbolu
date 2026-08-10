# EvidenceAssurance — Evaluation Report (Phase 22)

*Synthesis against the frozen protocol (`EVALUATION_PROTOCOL.md`). All numbers come from the
hash-pinned artifacts (`verify_frozen.py`); nothing here is recomputed with different settings. Corpus:
`ea_corpus_v1_1`, 624 cases, 132 gold-supported, 492 gold-unsupported, 156 in the correlated-failure /
adversarial trap.*

## 1. Headline

On the frozen corpus, the reference EvidenceAssurance component reaches **correlated-failure escape =
0.000** and **overall escape = 0.000** at a **false-block of 0.114** — and that false-block is
*entirely* the injected NLI-proxy noise (15/132), not structural over-blocking. Every signal-only
method — including a tuned learned comparator — escapes **0.67–1.00** of the trap. That gap is the
result.

But the result is **bounded**, and the bounds are as important as the headline:
- The component escapes **100%** on a constructed no-tell correlated failure (S23). It catches failures
  that leave an observable tell; it cannot catch those that leave none.
- On *this* corpus the primary endpoint is reachable by **independence-checking alone** (2 probes of
  18), because every trap case carries multiple tells. The full stack's extra layers are justified by
  **adversarial robustness** and by covering **non-correlated** failure states — not by the headline
  number on benign data.

## 2. Primary & co-primary endpoints

| Method (representative) | corr-failure escape ↓ | false-block ↓ |
|---|--:|--:|
| `A_always_deliver`, `B_source_count`, `C_diversity`, `G_passage_signal` | 1.000 | 0.000 |
| `S_learned_comparator` (fixed-weight over observed signals) | 1.000 | 0.000 |
| `D_grounding` = `E_entailment` = `F` = `I_majority_signal` | 0.667 | 0.000 |
| `J_provenance_conf`, `Q_authority_grounding`, `R_fresh_grounding` | 0.667 | 0.000–0.740 |
| `M_counterevidence` alone | 0.442 | 0.000 |
| `K_independence` alone | **0.000** | 0.000 |
| `O_indep_align_counter`, `P_full_ea_rule` | **0.000** | 0.432 |
| **Reference component (full stack)** | **0.000** | **0.114** |
| `H_always_block` | 0.000 | 1.000 |
| `T_oracle` | 0.000 | 0.000 |

Reading:
- **Downstream signals cannot see correlated failure.** Grounding, entailment, source-count,
  diversity, majority-vote — all 0.67–1.00. They are high *by construction* on aligned-but-wrong
  claims.
- **A classifier over those signals does not help** (`S` = 1.000). The deficiency is in the *inputs*,
  not the model — the signals carry no independence/provenance information.
- **The component dominates the naive composites on false-block** (0.114 vs 0.432) at equal escape,
  because it qualifies overstated-but-supported claims instead of refusing them.
- **`K_independence` alone also reads 0.000 / 0.000 here** — the honest, non-flattering fact the
  protocol required us to surface. Section 5 explains why the full stack still matters.

## 3. The component's false-block is noise, not refusal

All 15 false-blocked cases (5 gold `VERIFIED`, 10 gold `VERIFIED_WITH_LIMITATIONS`) are flipped to
`MISALIGNED` by the corpus's 10% `observed_alignment_signal` noise (an imperfect NLI proxy).
15 / 132 = 0.1136 = the measured false-block **exactly**. No supported case is refused for a structural
reason; the residual is the cost of a noisy passage signal and would fall with a better NLI proxy or
human adjudication on flagged cases. (Asserted in the test suite so it cannot silently regress.)

## 4. Disposition accuracy and the correlated-failure boundary

Exact 8-way disposition accuracy: **0.768**. The residual is two things, both honest:
- **NLI noise** (as above) misroutes some supported cases to `MISALIGNED`.
- **The correlated-failure boundary.** Gold `REJECT_EVIDENCE_STATE` (the trap) is labeled
  `CONFLICTED` (66, counterevidence surfaced), `MISALIGNED` (25, passage-signal flagged), or
  `INDETERMINATE` (13, provenance untrusted) — **never `VERIFIED`**. The component safely *refuses*
  correlated failure even when it cannot precisely *name* it as REJECT. Naming it requires discoverable
  counterevidence or model/methodological-independence information that is not in evidence metadata.

## 5. Robustness, ceiling, and the complexity question

**Correlated-failure scenarios (Phase 15, 23 scenarios).** Escape = 0 on all 11 embedded failure
types, the clean control, and 10 fabricated-diversity attacks — *but* we verified this is because every
trap case in the corpus carries ≥1 tell (0 cases pass alignment and lack counterevidence). So the clean
sweep credits the *stack*, not independence-checking alone.

**The honest ceiling (S23).** A false claim with no observable tell — aligned passage, no
counterevidence, fabricated independent provenance — **escapes 100%**. No metadata-based method can
catch a failure that leaves no metadata trace (taxonomy types 23/30). This is disclosed, not buried.

**Missing metadata (Phase 16, 0–70%).** Escape stays **0.000** at every level; abstention
(`INDETERMINATE`) rises 0.02 → 0.34 and false-block 0.11 → 0.76. The component degrades to *withhold*,
never to *guess supported*. Safe, not silent.

**Ablation (Phase 18).** No single layer is individually necessary for zero correlated-failure escape
(multi-tell redundancy). Each layer owns a different non-correlated failure state (freshness→staleness
accuracy 0.768→0.601 when removed; alignment→misalignment; etc.).

**Defense in depth (Phase 19).** Under fully-fabricated provenance, `independence` alone escapes
**0.500**; +alignment 0.192; +counterevidence 0.250; **full stack 0.000**. This is the justification
for the complexity: adversarial robustness, not benign accuracy.

## 6. Verdict against the frozen decision rules

| Decision rule (from protocol) | Met? |
|---|---|
| Corr-failure escape materially below every signal-only baseline | **Yes** — 0.000 vs 0.667–1.000 |
| Zero escape not bought by blocking (false-block at/near noise floor) | **Yes** — 0.114 = 15/132 noise |
| No-tell ceiling disclosed, claim bounded | **Yes** — S23 = 1.0 disclosed |
| Complexity justified only under adversarial-metadata threat model | **Yes** — benign subset = independence alone |

## 7. Bounded claim (the only claim this study licenses)

> Provenance- and independence-aware evidence verification catches correlated grounding+entailment
> failures that downstream signal composition — including a learned comparator over those signals —
> cannot, **for correlated failures that leave an observable tell** (a misaligned passage, discoverable
> counterevidence, or detectable provenance dependence). It does **not** catch no-tell correlated
> failures (shared-premise model consensus, training-data contamination); those require independent
> human or external verification. The multi-layer stack is warranted where evidence metadata may be
> fabricated; where metadata is trustworthy, independence-first with the remaining layers for
> non-correlated failure states is the honest, cheaper configuration.

Everything in this report is reproducible from the frozen artifacts and asserted in the Phase-20 tests.
