# B1 — Native Sanskrit Word-Specificity Run: Result (NULL)

**Outcome: `NO_WORD_SPECIFIC_SIGNAL`. The primary contrast fails every pre-registered success criterion.** On the
frozen native Devanāgarī consonant-backbone packets, three independent, family-diverse blind LLM evaluators do **not**
identify the intended word from the true varṇa packet better than matched false / scrambled / random / generic /
feature-only controls. Structure, not validated meaning. B1.10's pole-legibility negative (−2.78) stands; this
converges with it. No positive word-specificity claim is made.

## Provenance

- Packet freeze: `42f38d57` · pre-run audit: `fc15a0d8` · harness: `12e37995`.
- Evaluators (3 distinct families, each disjoint from the paraphrase-authoring family): `llama`
  (meta-llama/Llama-3.1-8B-Instruct), `gemma` (google/gemma-2-9b-it), `qwen` (Qwen/Qwen2.5-14B-Instruct); temperature 0,
  greedy, one-retry policy. Presentation order randomized per evaluator (frozen seeds).
- 720 evaluator-facing presentations × 3 evaluators = **2160**, each 720/720 answered, **0 invalid, 0 missing**.
- Raw-evidence freeze verified (`frozen: true`, combined sha256 `84feec0d…`) **before** the answer key was loaded;
  scoring never modified raw evidence. Analysis: `native_ws_analysis/native_word_specificity_analysis.json`.

## Primary contrast (Δ = Acc(T) − max(Acc(X),Acc(R),Acc(G),Acc(F)); chance = 1/6 ≈ 0.167)

| set | Δ | BCa 95% CI | permutation p | verdict |
|---|---|---|---|---|
| A | **0.020** | [−0.074, 0.111] | 0.18 | fails (need Δ≥0.15 **and** CI-lower>0) |
| B | **−0.056** | [−0.148, 0.028] | 0.60 | fails (CI-lower ≤ 0) |

## Per-arm accuracy (n)

| arm | Set A | Set B |
|---|---|---|
| **T** true | 0.194 (108) | 0.167 (108) |
| X cross-word | 0.102 (108) | 0.185 (108) |
| S scrambled | 0.176 (108) | 0.185 (108) |
| R random-assignment | 0.174 (540) | 0.176 (540) |
| G generic | 0.167 (108) | 0.157 (108) |
| **F feature-only** | 0.167 (108) | **0.222 (108)** |

- **T sits at chance** in both sets (0.194 / 0.167). In Set B the **feature-only arm F (0.222) exceeds T** — the
  content-free structural condition does as well or better than the real varṇa descriptions.
- Direction is **not** consistent across families: per-family Δ = gemma −0.028, llama +0.011, qwen −0.028 (all ≈ 0).

## Precommitted flagged-word sensitivity (source-intrinsic proximity: bhaya/duḥkha/sukha/deha)

Excluding the four words whose glosses the source lexicon is semantically adjacent to, Δ becomes **more negative**:

| set (flagged excluded) | Δ | BCa 95% CI |
|---|---|---|
| A | **−0.097** | [−0.333, 0.028] |
| B | **−0.139** | [−0.417, −0.051] |

The small Set-A positivity in the full analysis was carried entirely by the flagged words — i.e. by the documented
source-lexicon confound, **not** by any varṇa mechanism. On the clean (non-flagged) words the true packet performs
**worse** than the controls. This is exactly the interpretation limit the sensitivity analysis was precommitted to
expose, and it removes the only place a positive could have appeared.

> Source-intrinsic semantic proximity is part of the mapping under test, but because the upstream lexicon may have
> been authored with semantic awareness, concentration of the effect in these words limits causal interpretation.

## Diagnostics

- Same-valence-subset accuracy: A 0.333 (the two flagged negatives, small n), B 0.194 (≈ chance).
- Structural-shortcut: F ≥ T → no semantic content is needed to match T; the trivial signal is structural, not
  meaning-bearing. Random-assignment R ≈ T → the specific assignment adds nothing.

## What this establishes — and does not

- **Establishes:** on the clean native consonant backbone, with matched controls, three model families, position
  counterbalancing, genuinely context-isolated paraphrase authoring, and freeze-before-score discipline, **there is
  no evidence that the varṇa mappings let a blind evaluator recover the specific word.** The negative is credible
  precisely because the whole apparatus was built to deny a false positive any room.
- **Does not establish:** that varṇas are meaningless in every sense. This bounds one specific, well-posed claim
  (blind six-way word identification from the confirmatory consonant-backbone packet) and finds it unsupported.
  Vowels/markers were excluded (authored-provisional). No ontology / Sanskrit-privilege / semantic-truth claim.

## Status

Terminal record for the native Sanskrit word-specificity line. The hypothesis, as operationalized and preregistered,
is **not supported**. No result-dependent edits; success thresholds unchanged.
