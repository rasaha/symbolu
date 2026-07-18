# B1.12 — Post-Study Synthesis

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`

A research synthesis over the **completed** B1.12 studies. **No new experiment, no scoring, no protocol revision, no
methodology redesign, no V3.** Every number below is aggregated from already-recorded scores; none is re-scored or
re-interpreted. The goal is **not** to judge whether Symbol-U is true, but to locate where the symbolic layer
behaves *consistently enough to be practically useful*.

**Runs included.** V1 (two-LLM **crossover**, author→scorer, 20 words, 54 mapped components), V2 (two **independent
judges**, no crossover, fresh 20 words, 60 components), the **halted** V2 first attempt (aborted on `jaṅghā` — score-0
had no relationship label; recorded in `B1_12_V2_METHODOLOGY_CONTRADICTION_LOG.md`), and the **v2.1 amendment**
(added `no_relationship`, valid iff score 0). The earlier 60-word affliction/**resolution** pilot is B1.12 lineage but
used a *different* (resolution/PMM) scale, so its scores are **not pooled** here — pooling them would be reinterpreting
old scores under a frame they were not produced in. It is noted for completeness only.

**One cross-study caveat, stated up front.** V1 and V2 used *different frozen scale calibrations* (V2 tightened the
25-vs-50 boundary and added `no_relationship`). Therefore **absolute scores are not directly comparable across the two
studies**; the robust, calibration-independent signals are **cross-evaluator agreement** and **disagreement
magnitude**, and those carry the stability claims below. Absolute means are reported as descriptive context, not as
cross-study deltas.

---

## Part 1 — Aggregate of every completed run

Each study contributes **two evaluations per component** (V1: run-A Mistral-scored + run-B Qwen-scored; V2: Qwen judge
+ Mistral judge).

| | **V1 — crossover** | **V2 — independent** |
|---|---|---|
| Design | Qwen⇄Mistral, author→scorer (anchored) | Qwen ∥ Mistral, independent (blind) |
| Words / components | 20 / 54 | 20 (fresh) / 60 |
| Exact score agreement | 0.500 | 0.533 |
| Within-one-step agreement | **0.944** | 0.850 |
| Mean abs score diff | 13.89 | 15.42 |
| Signed bias (A−B) | **−11.11** | **−4.58** |
| Relationship exact agreement | 27 (0.500) | 36 (0.600) |
| Relationship incompatible | 19 (0.352) | 17 (0.283) |
| Pooled score distribution (0/25/50/75/100) | 1 / 41 / 47 / 19 / 0 | 22 / 59 / 18 / 20 / 1 |
| Pooled mean score (descriptive only) | 44.4 | 33.1 |
| `no_relationship` components | 0 (label did not exist) | 22 |
| Per-word verdict agreement | 0.50 | 0.50 |
| Model/role-dependence verdict | SIGNIFICANT | SIGNIFICANT |
| STRONG-resonance words (≥1 judge) | 0 | 4 (dama in both) |

Reading: independence **halved the systematic directional bias** (11.11→4.58) and **raised relationship-choice
agreement** (0.50→0.60), but **per-word verdict agreement is identical (0.50)** and large gaps rose (within-one-step
0.944→0.85). Both studies land at SIGNIFICANT dependence. The `no_relationship` amendment and the tightened scale
pulled the V2 distribution toward the extremes (22 zeros, 1 hundred) versus V1's mid-clustering.

## Part 2 — Disagreement clusters (pooled, 55 disagreeing of 114 components)

| Cause | share of all disagreements | of the large (≥50) gaps |
|---|---|---|
| **Calibration — same relationship, different magnitude** | **24 (44%)** | 2 |
| `no_relationship` split (one judge sees nothing, other a positive) | 10 (18%) | 3 |
| Relationship swap, *compatible* | 9 (16%) | 2 |
| Relationship swap, *incompatible* | 6 (11%) | — |
| Opposition-vs-other | 6 (11%) | **5** |

**Dominant cause = calibration** (same relationship chosen, scores differ by a step) — nearly half of all
disagreements. But the **largest-magnitude** disagreements are **opposition-related** and **`no_relationship` splits**:
the models most often *blow apart* (≥50) when one reads a clean opposition the other rates weak, or when one sees a
concrete word as unrelated and the other manufactures a link.

## Part 3 — Relationship families, most → least stable

Ranked by **cross-evaluator agreement when both chose the same relationship** (calibration-robust), then variance.

| Relationship | uses | avg score | stdev | agreement when shared |
|---|--:|--:|--:|--:|
| **`no_relationship`** | 22 | 0 | 0.0 | **1.00** |
| **`opposition`** | 44 | 55.1 | 23.0 | **0.79** |
| `implication` | **105** | 34.5 | **14.4** | 0.54 |
| `characteristic_expression` | 30 | 50.8 | 19.9 | 0.40 |
| `natural_consequence` | 14 | 41.1 | 15.3 | 0.00 (2 shared) |
| `constitutive_property` / `embodiment` / `generation` / `regulation` / `resolution` | ≤4 each | — | — | too few to rank |

- **`no_relationship`** and **`opposition`** are the two trustworthy relationships: the first agrees perfectly (a
  reliable "does-not-apply" signal), the second is the best-agreed substantive one and carries the highest resonance.
- **`implication`** is the high-volume workhorse (105 uses, lowest variance) but agrees only 0.54 — reliable as a
  *weak-signal default*, not for magnitude.
- **`characteristic_expression`** and **`natural_consequence`** are unstable; the remaining types are too rarely used
  to rank.

## Part 4 — Word-category stability

| Category | n | avg score | stdev | cross-eval abs diff | exact agree | `no_relationship` rate |
|---|--:|--:|--:|--:|--:|--:|
| virtue_calm | 24 | **57.3** | 19.7 | 16.7 | 0.542 | 0.00 |
| afflictive | 25 | 48.5 | 19.0 | 17.0 | **0.40** | 0.00 |
| natural_action_abstract | 21 | 29.2 | 18.8 | **10.7** | **0.619** | 0.119 |
| concrete_object | 23 | 27.7 | 16.7 | 12.0 | 0.565 | 0.152 |
| animal_body_living | 21 | 26.2 | 18.9 | 16.7 | 0.476 | **0.238** |

**The central finding of the synthesis:** resonance strength and evaluator agreement are **inversely related**. The
affective domains (**virtue, affliction**) resonate *strongly* (avg 57, 48) but are the **least agreed** (afflictive
exact 0.40). The concrete/abstract domains resonate *weakly* but are the **most agreed** (natural_action exact 0.62,
lowest disagreement) — the models agree *that little resonates*. Animal/body words carry the most `no_relationship`
(0.24). So "consistently resonates" splits into two different claims: virtue/affliction words consistently score
**high but contested**; concrete/abstract words consistently score **low but concordant**.

## Part 5 — Mapping (per-varṇa) stability

Full ranking in `mapping_ranking.json`. **Power caveat:** 9 of 27 covered varṇas appear in only one word (n≤1); only
11 have n≥4. Rankings by absolute resonance are soft (they blend V1/V2 calibrations); rankings by cross-evaluator
disagreement and `no_relationship` rate are robust.

**Well-supported (n≥4), by resonance:**

| varṇa | avg resonance | cross-eval diff | `no_relationship` | n | note |
|---|--:|--:|--:|--:|---|
| **d** | 52.5 | **5.0** | 0.20 | 5 | peevishness / reactive irritability — stable + resonant |
| **s** | 51.8 | 10.7 | 0.00 | 7 | sattvic impulse clung to — stable + resonant |
| **v** | 40.6 | **6.2** | 0.12 | 4 | over-holding / rigid fixity — stable |
| **y** | 37.5 | 8.3 | 0.00 | 6 | stable, mid resonance |
| k | 41.7 | 20.8 | 0.04 | 12 | evaluator-sensitive |
| r | 41.1 | 17.9 | 0.04 | 14 | evaluator-sensitive |
| t | 41.1 | **25.0** | 0.00 | 7 | most evaluator-sensitive |
| n | 31.9 | 19.4 | 0.06 | 9 | evaluator-sensitive |
| p | 30.7 | 15.9 | 0.14 | 11 | mid |
| m | 35.7 | 14.3 | 0.07 | 7 | mid |
| l | 25.0 | 8.3 | 0.25 | 6 | low resonance, stable |

- **Strongest & most stable mappings:** **d** (peevishness), **s** (sattvic impulse), **v** (rigid over-holding) —
  decent resonance *and* low cross-evaluator disagreement.
- **Weakest mappings:** the **ego/ahaṃkāra family — `j` (inflated "I did"), `ṅ` (dambha/vanity), `gh`
  (mamatā/possessiveness)** — drew **unanimous `no_relationship`/0** on the (body-part) words carrying them. Stable at
  **zero** (but n=1 each, so this is "these mappings did not resonate with the specific words tested", not a
  general verdict). `l` (cruelty, 25) and `b`/`ḍ` (25) are also low.
- **Most evaluator-sensitive mappings:** **t** (diff 25.0), **k** (20.8), **n** (19.4), **r** (17.9) — high-usage
  consonants where the two evaluators most disagree on strength.

## Part 6 — Engineering-readiness ranking

*Not a truth ranking — a "what could an auxiliary reflective layer use first" ranking, keyed on agreement/robustness.
Full JSON: `engineering_readiness_ranking.json`.*

**Tier 1 — high confidence (agreement-stable ends).**
- Relationship signals: **`no_relationship`** (agrees 1.00 — a trustworthy "this mapping does not apply") and
  **`opposition`** (agrees 0.79, highest substantive resonance).
- Mappings: **d, s, v, y** (low cross-evaluator disagreement, decent resonance, n≥4).
- Deploy only where the bare word *clearly opposes* an affliction mapping (virtue words) or *clearly has no*
  relationship. These are exactly the two ends where both models concur.

**Tier 2 — promising but evaluator-sensitive.**
- `implication` as a *weak-signal-only* indicator (0.54 agreement — never surface its magnitude).
- Mappings **k, r, t, n, p, m** (high usage, but cross-eval diff 14–25).
- The **virtue/affliction** domains: strong resonance, but the *least* agreement — present with an explicit
  confidence caveat; do not act on magnitude.

**Tier 3 — experimental.**
- Rare/low-agreement relationships (`characteristic_expression` 0.40, `natural_consequence` 0.0, and the ≤4-use types).
- Low-power mappings (the 16 varṇas with n≤2).
- Concrete/animal/abstract domains (low resonance; animal highest `no_relationship`).

## Part 7 — Research conclusions

**1. What actually became clearer.**
- LLM-adjudicated resonance is evaluator-dependent in a now-*characterized* way: the author→scorer confound produced a
  ~11-pt systematic bias that **independence removed** (residual −4.6), yet **per-word agreement stayed at 0.50 in
  both studies** — so the instability is *word-specific*, not a role artifact.
- The single biggest disagreement driver is **calibration** (same relationship, different magnitude — 44%), while the
  biggest *blow-ups* are **opposition strength** and **concrete-word "nothing vs a link."**
- **`opposition` and `no_relationship` are the reliable signals; `implication` is a reliable weak default.**
- **Resonance and agreement are anti-correlated across domains** (virtue/affliction: high+contested;
  concrete/abstract: low+concordant).

**2. Hypotheses that survived.**
- **Opposition/resolution are genuine resonance relationships** (the §1.4 correction let virtue words reach STRONG via
  opposition — `dama` STRONG in *both* judges; V1 produced no STRONG at all). Polarity-reversal carries signal.
- **The method discriminates and can say "no."** It yields a real category gradient (virtue/affliction ≫
  concrete/animal) and `no_relationship` was used honestly (Qwen 15/60), agreeing perfectly where used.

**3. Assumptions disproved.**
- That the crossover/anchoring bias was the *main* reliability problem — removing it did **not** improve agreement.
- That one relationship label per component always suffices — a legitimate score-0 had **no expressible label** (the
  halt / v2.1 amendment).
- That consonant mappings behave uniformly — the ego-family mappings (j/ṅ/gh) drew unanimous zero while
  affliction/desire mappings (d/s/ṣ) scored high.

**4. What remains genuinely unknown.**
- Whether the high-resonance-but-low-agreement affective words reflect real symbolic structure or evaluator
  projection (the `akrodha` semantic-radius disagreement).
- Whether concrete words truly lack a relationship or the "direct vs supplemented" threshold is simply too strict (the
  `kapāla` case — identical reasoning, 0 vs 50).
- Per-mapping behaviour for the ~16 low-power varṇas (n≤2) — most of the alphabet is under-sampled.
- Whether the STRONG opposition results generalize or are an artifact of pairing virtue words with affliction glosses.

**5. Highest expected-information-gain future directions** (new, separate studies — **not** reopening B1.12 or
revising its methodology):
- **Per-varṇa saturation:** many words per *single* varṇa (target n≥10/mapping) to rank all mappings with power and
  resolve Part-5's under-sampling — the highest-EIG move, since 16/27 mappings are currently n≤2.
- **Human-vs-LLM calibration on the borderline cases** (`akrodha`/`kapāla` types) to separate genuine symbolic
  ambiguity from the fixable "direct" threshold.
- **Alternate/shuffled-mapping control** (does affective-word resonance survive the *wrong* mapping?) — the one test
  that would tell whether high affective resonance is content or projection.
- **A third independent judge** to test whether 0.50 verdict agreement is a two-model artifact or a stable ceiling.

---

## Deliverables in this directory
`B1_12_SYNTHESIS_REPORT.md` (this file), `study_comparison.json`, `disagreement_clusters.json`,
`relationship_ranking.json`, `category_ranking.json`, `mapping_ranking.json`,
`engineering_readiness_ranking.json`, `future_research_roadmap.json`.

## Discipline
Synthesis only. No mapping, parser, gloss, scale, taxonomy, verdict band, or prior score was modified or re-scored;
no V3 proposed; B1.12 treated as complete. Absolute cross-study score comparisons are explicitly avoided because V1
and V2 used different frozen calibrations; stability claims rest on calibration-robust agreement/disagreement.
