# O1.5 Construct-Validity & Dynamic-Range Report

> Offline diagnostic gate BEFORE O2A. No LLM, no policy, no API. Hand-authored
> diagnostic corpus (NOT the O2A benchmark). SBERT deferred to O2A (not installed).


## 1. Summary verdict: **FAIL**

| check | result |
|---|---|
| dynamic_range | PASS |
| separation | PASS |
| direction | FAIL |
| paraphrase_stable | FAIL |
| minimal_pairs | PASS |
| beats_substrate | PASS |
| beats_shuffle | PASS |

baseline class-separation (inter/intra over 12 categories; >1 separates): reading=1.11, substrate=1.10, sentiment=2.28, length=1.24, random_labels=1.03

## 2. Dynamic range (reading features across 12 categories)

distinct states: 60/60 · reading mean-std 0.101 vs substrate mean-std 0.078

| feature | std | min | max | near-constant | saturated |
|---|---|---|---|---|---|
| valence_ratio | 0.063 | 0.29 | 0.60 | False | False |
| polarity_balance | 0.157 | -0.39 | 0.22 | False | False |
| tension | 0.087 | 0.39 | 0.77 | False | False |
| coherence | 0.030 | 0.00 | 0.11 | True | False |
| mean_sign | 0.169 | -0.12 | 0.50 | False | False |

## 3. Internal consistency (contrast pairs)

| contrast | inter/intra | dir-feature | direction-correct |
|---|---|---|---|
| joy_vs_grief | 0.94 | valence_ratio | True |
| calm_vs_urgent | 1.07 | - | - |
| grounded_vs_specul | 1.15 | coherence | False |
| clear_vs_confused | 1.11 | coherence | False |
| memory_vs_nonmemory | 1.22 | - | - |
| certain_vs_uncertain | 1.15 | coherence | False |

## 4. Paraphrase stability (within-set vs overall distance)

| group | n | within | overall | stable (within<0.6*overall) |
|---|---|---|---|---|
| 0 | 4 | 1.84 | 2.93 | False |
| 1 | 4 | 3.84 | 2.93 | False |
| 2 | 4 | 2.30 | 2.93 | False |
| 3 | 4 | 2.35 | 2.93 | False |

## 5. Minimal-pair sensitivity

| feature | A | B | f(A) | f(B) | expect | correct |
|---|---|---|---|---|---|---|
| coherence | This is verified. | This is only a guess. | 0.01 | 0.24 | A>B | False |
| valence_ratio | I remember you said that. | I do not remember that. | 0.44 | 0.47 | either | True |
| valence_ratio | He was calm and steady. | He was panicking wildly. | 0.28 | 0.40 | A>B | False |
| valence_ratio | The plan succeeded. | The plan failed. | 0.57 | 0.55 | A>B | True |
| coherence | It is certainly true. | It might possibly be true. | 0.12 | 0.04 | A>B | True |
| valence_ratio | We are safe now. | We are in danger now. | 0.58 | 0.44 | A>B | True |

## 6. Phonetic-substrate comparison

mean inter/intra over contrasts — reading **1.11** vs substrate **1.05** → reading beats substrate: **True**


## 7. Shuffle / relabel sanity check

mean inter/intra — real poles **1.11** vs shuffled poles **1.04** → ontology does work (real>shuffle): **True**

(If real ≈ shuffled, the specific pole assignment carries no signal.)


## 8. Decision

**FAIL** — PASS needs ≥6/7 checks AND none of {dynamic_range, paraphrase_stable, beats_substrate, beats_shuffle}} failing. PARTIAL = some-but-weak. FAIL = near-constant / unstable / loses to substrate / shuffle ties.


> **Gate verdict: do NOT build O2A on the current reading as-is.** The failing checks localize where the reading is inadequate (see tables).


## 9. Interpretation (auto-derived)

- **Has dynamic range but it is SURFACE-driven:** 60/60 distinct states, yet paraphrases of one meaning are as far apart as different meanings (audit 3 within≈/≥overall = True). Variation tracks sound/form, not meaning.
- **Loses to trivial baselines at separating the 12 categories:** reading 1.11 vs sentiment 2.28 (LOSES) and vs length 1.24 (LOSES). A ~60-word sentiment list separates them far better.
- **Only marginally exceeds its own controls:** over substrate by +0.05, over pole-shuffle by +0.07 — technically positive, but negligible.
- **Epistemic distinctions are backwards/dead:** coherence std=0.030 (near-constant=True); grounded/clear/certain direction-correct = [False, False, False].
- **Net:** the reading is not near-constant, but its variance is dominated by surface phonetic form rather than meaning; it underperforms a trivial sentiment baseline and is unstable under paraphrase. Construct validity is **not** established.