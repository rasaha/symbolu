# B1.6 — 10-Sample Exploratory Generation Probe: Results Record

**Status:** results record (docs-only). Captures the aggregate outcome of the B1.6-v2 **10-sample exploratory**
generative-utility probe that was executed on an operator model host (RunPod, transformers backend). Raw
outputs/ratings live under gitignored `run_out/` and are **not** committed; this file is the durable record of
the numbers.

**Descriptive result label: `B1_6_EXPLORATORY_10_SAMPLE_RESULT_RECORDED` — finding: NO EVIDENCE OF BENEFIT (null).**
This is an **exploratory** probe. It **cannot** and does **not** emit a prereg `GENUTILITY_*` terminal verdict.
**B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

---

## 1. What was tested

Whether the Symbol-U varṇa scaffold, used as a **generative/interpretive scaffold** (not a decoder), produces
**better blind-rated interpretations** than baselines and — critically — than a **scrambled** version of itself.

- **Representation:** `v2_named_vritti` (active; v1 superseded).
- **Design:** 10 target words × 5 arms × 2 generators → 100 intended outputs (exploratory subset of the
  24-word pilot). Deterministic 10-word subset: river, balance, Maya→(re-blinded), lotus, Lumen, grief, bridge,
  freedom, Rowan, dawn.
- **Arms:** `SYMBOLU_SCAFFOLD`, `PLAIN_PROMPT_BASELINE`, `GENERIC_STRUCTURED_PROMPT_BASELINE`,
  `RANDOMIZED_SYMBOLU_CONTROL` (scramble), `SEMANTIC_LLM_BASELINE`.
- **Generators (blind codes):** M1 = `mistralai/Mistral-7B-Instruct-v0.3`, M2 = `Qwen/Qwen2.5-7B-Instruct`.
- **Judges (blind, 3-panel; families ≠ generators):** `meta-llama/Llama-3.1-8B-Instruct`,
  `meta-llama/Meta-Llama-3-8B-Instruct`, `google/gemma-2-9b-it`.
- **Backend:** local `transformers` direct-load (no vLLM). Gated by an operator evidence-freeze + ratings-freeze
  declaration; judges read only the blind judge-visible file; unblinding only at aggregation.

## 2. Provenance (frozen-input hashes, for traceability)

| input | sha256 |
|---|---|
| target scaffolds (v2) | `7f331deb845bbd26b6e2392e538bcffa6b206bbfae748085b34ed6d8365cf0dc` |
| scaffold manifest (v2) | `e3f6bc3d7426e3d5620127dc3afaa836b84ef82dfec3459a44382c735ec141ad` |
| randomized control (v2) | `f6bc91d5d23afeff83abcbae58231908f13355095b446bd0207ab0cb30add997` |
| prompt/rubric doc | `080a67086c8631568c53c57a02d76f75a8a25f5ce3f8f8bc4f3205655b0ecc5b` |
| evidence-freeze declaration | `e2d8a8593d818dff2a702edfd72f5427338d45488fd4380e07da4481c02a072a` |
| judge-visible package | `510f67c63d3f13a2cd2cc721ddf906e4cefdbbe8bdf42dcbba0007c3020926f6` |
| re-blind seed | `20260708` |

## 3. Sample realized (94 / 100)

6 outputs dropped to output-format/blindness filters (Qwen only), all on **baseline** arms — the conservative
direction (dropping weaker baseline outputs can only make baselines look *better*, not worse for Symbol-U).

| arm | M1 | M2 |
|---|---|---|
| **SYMBOLU_SCAFFOLD** | 10 | **10** |
| PLAIN_PROMPT_BASELINE | 10 | 7 |
| GENERIC_STRUCTURED_PROMPT_BASELINE | 10 | 8 |
| **RANDOMIZED_SYMBOLU_CONTROL** | 10 | **10** |
| SEMANTIC_LLM_BASELINE | 10 | 9 |

Judging grid: **282 / 282** ratings (94 outputs × 3 judges), complete.

## 4. Primary result — arm quality composites

Penalty-adjusted composite (mean of 8 positive dims minus mean(penalty−1)); higher = better. 7-point scale.
`n` = ratings (outputs × 3 judges).

| arm | n | penalty-adjusted | CI95 | raw |
|---|---|---|---|---|
| **SYMBOLU_SCAFFOLD** | 60 | **5.423** | [5.34, 5.51] | 5.756 |
| RANDOMIZED_SYMBOLU_CONTROL (scramble) | 60 | 5.450 | [5.34, 5.57] | 5.800 |
| GENERIC_STRUCTURED_PROMPT | 54 | 5.558 | [5.42, 5.72] | 5.762 |
| PLAIN_PROMPT | 51 | 5.566 | [5.40, 5.71] | 5.743 |
| SEMANTIC_LLM | 57 | 5.656 | [5.54, 5.77] | 5.787 |

**Symbol-U ranks last of five on the penalty-adjusted composite, and is essentially tied with (marginally below)
its own scrambled control.** On the raw composite all five arms are within ~0.06 (indistinguishable). CIs overlap
throughout, so the careful statement is *no evidence of benefit*, not *proven harm*.

## 5. Paired preferences — Symbol-U vs each control

Paired by word, penalty-adjusted composite; win = Symbol-U higher.

| contrast | win | tie | loss | win-rate |
|---|---|---|---|---|
| SYMBOLU vs PLAIN_PROMPT | 1 | 0 | 9 | 0.10 |
| SYMBOLU vs GENERIC_STRUCTURED | 3 | 0 | 7 | 0.30 |
| SYMBOLU vs RANDOMIZED (scramble) | 4 | 0 | 6 | 0.40 |
| SYMBOLU vs SEMANTIC | 1 | 2 | 7 | 0.10 |

Symbol-U loses the paired comparison to **every** control, including a shuffle of itself. The pattern holds
across both generators (arm×generator: SYMBOLU M1 5.68 / M2 5.31, under the baselines in both).

## 6. Per-dimension — Symbol-U vs its scramble (the decisive test)

If the varṇa-specific content mattered, Symbol-U should beat its scramble. It does not (net leans to scramble:
3 dims lean Symbol-U, 5 lean scramble, 2 tie).

| dimension (higher=better unless noted) | Symbol-U | scramble | edge |
|---|---|---|---|
| specificity_to_target | 5.550 | 5.350 | **Symbol-U +0.20** |
| interpretive_richness | 6.233 | 6.167 | Symbol-U +0.07 |
| overclaim_penalty (lower=better) | 1.667 | 1.700 | Symbol-U +0.03 |
| practical_usefulness | 5.350 | 5.350 | tie |
| hallucination_penalty (lower=better) | 1.000 | 1.000 | tie |
| coherence | 6.067 | 6.100 | scramble |
| non_genericity | 5.383 | 5.433 | scramble |
| creativity_aesthetic | 5.550 | 5.583 | scramble |
| internal_consistency | 6.267 | 6.317 | scramble |
| caution_epistemic_humility | 5.650 | 6.100 | **scramble +0.45** |

**The one theory-relevant lean is `specificity_to_target` (+0.20).** It is flagged as a *hypothesis-generating
hint only*: small, within noise at this n, uncorrected across 10 dimensions (the field as a whole leans to the
scramble), and outweighed (it does not lift the composite above scramble). It is **not** evidence.

## 7. Fluency + the one real (format-driven) effect

Fluency proxies + creativity, per arm:

| arm | coherence | internal_consistency | creativity |
|---|---|---|---|
| SYMBOLU_SCAFFOLD | 6.067 | 6.267 | **5.550** |
| RANDOMIZED (scramble) | 6.100 | 6.317 | **5.583** |
| GENERIC_STRUCTURED | 6.574 | 6.593 | 4.574 |
| PLAIN_PROMPT | 6.627 | 6.627 | 3.961 |
| SEMANTIC | 6.667 | 6.667 | 3.789 |

- **Fluency:** Symbol-U is *lowest* on coherence and internal-consistency — it slightly **reduces** fluency.
- **Creativity:** Symbol-U (and its scramble) score far higher than plain/semantic (~5.55 vs ~3.8) — a real,
  large effect. But the **scramble matches it**, so this is the **scaffold *format*** (imagery + two poles),
  **not** the varṇa meanings.

## 8. Divergence (does it give a different perspective?)

MiniLM cosine distance (0 = same meaning; 0.733 = a different word/topic, the calibration ceiling):

| comparison (same word) | distance |
|---|---|
| Symbol-U vs PLAIN | 0.419 |
| scramble vs PLAIN | 0.371 |
| Symbol-U vs scramble | 0.314 |
| *PLAIN vs PLAIN, different words (calibration)* | *0.733* |

Symbol-U produces a **moderately different** reading than a plain prompt (~60% of the way to "different topic"),
but the scramble reproduces ~88% of that divergence (0.371 vs 0.419), and Symbol-U is closer to its own scramble
(0.314) than to plain (0.419). The "different perspective" is a **format** effect, not a meaning effect.

## 9. Efficiency (things LLMs care about)

| arm | input tok | output tok | lexical diversity | valid/20 |
|---|---|---|---|---|
| SYMBOLU_SCAFFOLD | 436 | 290 | 0.687 | 20/20 |
| RANDOMIZED | 385 | 281 | 0.694 | 20/20 |
| GENERIC_STRUCTURED | 179 | 228 | 0.717 | 18/20 |
| PLAIN_PROMPT | 140 | 224 | 0.719 | 17/20 |
| SEMANTIC | 158 | 211 | 0.727 | 19/20 |

Symbol-U is **~3× the prompt cost** of a plain prompt and produces longer output, for no quality gain — strictly
*less* token-efficient. Lexical diversity is slightly *lower* (the creativity is thematic imagery, not
vocabulary). The one upside — 20/20 format compliance (steerability) — is matched exactly by the scramble
(format-driven). Hallucination ≈ none in all arms; overclaim tied-low; caution slightly worse for Symbol-U.

## 10. Interpretation (plain language)

**The generation was not helpful.** Symbol-U scored at the bottom of five arms on overall quality, lost the
paired comparison to plain prompts 9-to-1, and — the decisive point — could **not** beat a scrambled version of
its own mapping on any aggregate measure. The only real, large effect (more creative / ~60% more divergent
readings) is a property of the **scaffold format** and is fully reproduced by shuffling the varṇa meanings. It
also costs ~3× the tokens. This is a clean **null** for the varṇa-specific hypothesis, fully consistent with
B1.4b′.

**The one honest, non-hypothesis takeaway:** as a *creativity/divergence scaffold*, the format reliably moves a
model off its default reading — usable as a brainstorming aid, sold as what it is (a structured imagery prompt),
with no dependence on the meanings being real.

## 11. Limits (what this does and does not license)

Exploratory only: 10 words, 94 outputs, 2 generator models, LLM judges (not humans), descriptive stats (no
powered significance test, CIs overlap). It **rules nothing in** and cannot *prove* uselessness — it found no
benefit across 4 controls × 2 models × averaged-and-paired views. The `specificity_to_target` +0.20 lean is the
only thread worth a follow-up: a **preregistered, powered** run with `SYMBOLU vs RANDOMIZED` on
`specificity_to_target` as the single primary endpoint, fixed N and analysis committed before looking.

## 12. Guardrails

No prereg `GENUTILITY_*` terminal verdict is emitted (exploratory probe). No semantic-truth claim. No ontology,
no Sanskrit privilege. **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b blocked; Track B blocked.
**Structure, not validated meaning.**
