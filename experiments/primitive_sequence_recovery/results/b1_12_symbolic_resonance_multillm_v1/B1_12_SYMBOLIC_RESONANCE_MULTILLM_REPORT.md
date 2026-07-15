# B1.12 Bare-Word Symbolic Resonance — Multi-LLM Crossover · RESULTS

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`

**Controlling preregistration:** `VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md`
**Pre-run freeze:** `B1_12_BSR_VERDICT_AND_ROLE_STABILITY_FREEZE.md`
**Frozen word list (20 words):** `b1_12_symbolic_resonance_wordlist_v1/` — SHA-256 `9779384d…8f8a6ba`
**Frozen mappings:** `frozen/varna_native_stage1_merged_v3.json` (`65116f37…`, ś/ṣ-corrected + vocalic layer)
**Headline:** `role_dependence = SIGNIFICANT_ROLE_DEPENDENCE`. **No word reached STRONG resonance in either run.**

This document reports what two independent open-weight LLMs actually produced. It is exploratory and is **not**
confirmatory evidence for composable varṇa meaning. The finding it supports is a limitation, not a confirmation.

---

## 1. What ran

Two-run crossover, deterministic decoding (temperature 0, top-p 1, top-k −1, seed 20260714, bf16), one model
resident at a time on a single A100-80GB (vLLM 0.10.1.1):

| Run | Author (profile + bidirectional evidence) | Scorer (final relationship + BSR score) |
|---|---|---|
| **A** | Qwen3-32B | Mistral-Small-3.1-24B |
| **B** | Mistral-Small-3.1-24B | Qwen3-32B |

Each word's mapped occurrences (native Stage-1 parse, frozen v3 glosses) were scored on the frozen 5-point BSR
scale (0/25/50/75/100 = "cannot support without external meaning" … "directly and characteristically accounted
for by the bare word"). Verdict thresholds, the relationship taxonomy, and the role-dependence rule were frozen
**before** any model call. No forced consensus — both judgments are retained. 54 mapped occurrences across 20
words.

---

## 2. Headline results

### 2.1 Central tendency is modest; the ceiling is MODERATE

- **Overall mean BSR:** Run A ≈ **37.7**, Run B ≈ **48.7** (word-mean average).
- **No STRONG_RESONANCE anywhere** (STRONG requires mean ≥ 75 **and** min ≥ 50). The single highest word-mean in
  the entire study is **66.67** (garva, sneha — both in Run B). Under a genuine composable-meaning hypothesis one
  would expect at least some words to reach STRONG; none did.
- Verdict distribution:

| Verdict | Run A (Mistral scores) | Run B (Qwen scores) |
|---|---|---|
| STRONG | 0 | 0 |
| MODERATE | 7 | 14 |
| WEAK | 7 | 5 |
| MINIMAL | 5 | 1 |
| NO_RESONANCE | 1 (dīpa) | 0 |

### 2.2 Scoring is evaluator-dependent → `SIGNIFICANT_ROLE_DEPENDENCE`

The role-dependence rule fired **SIGNIFICANT** on the *systematic* clause:

- **Signed component bias A − B = −11.11** (|·| ≥ 15 is the "systematic" trigger at the component tally; the
  word-mean gap is ≈ −11 in the same direction). Whichever pairing scores, **Mistral-as-scorer is systematically
  ~11 points stricter than Qwen-as-scorer.** The verdict a word receives depends materially on the evaluator.
- **Exact verdict agreement = 0.50** (10/20 words). Below the 0.80 needed for ROLE_STABLE.
- **Component score agreement:** exact 0.50, within-one-step 0.944, mean abs diff 13.89. So the two models rarely
  differ by more than one 25-point step, but the *consistent directional bias* plus band-boundary effects flip
  half the verdicts.
- **4 evaluator-sensitive words** (≥ 2 verdict bands apart): **dīpa, kāka, nāsā, pāṭha.** dīpa swings from
  NO_RESONANCE (12.5, Mistral) to MODERATE (50.0, Qwen) — a 37.5-point, 3-band swing driven purely by which model
  scores.

### 2.3 The models disagree on the *kind* of relationship, not just the strength

Of 54 occurrences, the relationship-type assignments were **exact 27 (50%), compatible 8 (15%), incompatible 19
(35%)**. On more than a third of occurrences the two models chose *incompatible* relationship types — and many of
those are **direction flips between `opposition` and `implication`** (e.g. bhūmi ×2, dīpa, setu, santoṣa): one
model reads the bare word as *implying* the mapping, the other as *opposing* it. Disagreement about the sign of
the relationship is stronger evidence against a stable underlying signal than mere score scatter.

### 2.4 Profiles agree even where scores don't

Bare-word *profiles* (the locked ordinary-meaning prototype) matched closely: **14/20 "same"** (identical or
near-identical text — both models gloss garva as "arrogance", etc.), 2 minor, 4 material differences. So the
divergence is **not** about what the words mean; it is about how naturally each model judges the frozen mapping to
follow from that shared meaning. The instability lives in the resonance judgment, exactly where the hypothesis
needs stability.

---

## 3. Per-word results

| Word | Category | mean A | verdict A | mean B | verdict B | agree | eval-sensitive |
|---|---|--:|---|--:|---|:--:|:--:|
| garva | afflictive | 50.0 | MODERATE | 66.67 | MODERATE | ✓ | |
| sneha | virtue_calm | 50.0 | MODERATE | 66.67 | MODERATE | ✓ | |
| droha | afflictive | 50.0 | MODERATE | 58.33 | MODERATE | ✓ | |
| kapaṭa | afflictive | 50.0 | MODERATE | 58.33 | MODERATE | ✓ | |
| santoṣa | virtue_calm | 43.75 | WEAK | 62.5 | MODERATE | ✗ | |
| titikṣā | virtue_calm | 37.5 | WEAK | 56.25 | MODERATE | ✗ | |
| kleśa | afflictive | 50.0 | MODERATE | 50.0 | MODERATE | ✓ | |
| prema | virtue_calm | 50.0 | MODERATE | 50.0 | MODERATE | ✓ | |
| dīpa | concrete_object | 12.5 | NO_RESONANCE | 50.0 | MODERATE | ✗ | ⚠ |
| kāka | animal_body_living | 25.0 | MINIMAL | 50.0 | MODERATE | ✗ | ⚠ |
| nāsā | animal_body_living | 25.0 | MINIMAL | 50.0 | MODERATE | ✗ | ⚠ |
| pāṭha | natural_action_abstract | 25.0 | MINIMAL | 50.0 | MODERATE | ✗ | ⚠ |
| naukā | concrete_object | 37.5 | WEAK | 50.0 | MODERATE | ✗ | |
| vastra | concrete_object | 31.25 | WEAK | 50.0 | MODERATE | ✗ | |
| bāhu | animal_body_living | 50.0 | MODERATE | 37.5 | WEAK | ✗ | |
| snāna | natural_action_abstract | 41.67 | WEAK | 33.33 | WEAK | ✓ | |
| setu | concrete_object | 37.5 | WEAK | 37.5 | WEAK | ✓ | |
| rūpa | natural_action_abstract | 37.5 | WEAK | 37.5 | WEAK | ✓ | |
| mayūra | animal_body_living | 25.0 | MINIMAL | 33.33 | WEAK | ✗ | |
| bhūmi | natural_action_abstract | 25.0 | MINIMAL | 25.0 | MINIMAL | ✓ | |

---

## 4. Where the residual signal lives — a construct-validity confound

Category means (average of both runs):

| Category | mean A | mean B |
|---|--:|--:|
| afflictive (droha, garva, kapaṭa, kleśa) | 50.0 | 58.3 |
| virtue_calm (prema, santoṣa, sneha, titikṣā) | 45.3 | 58.9 |
| concrete_object (dīpa, naukā, setu, vastra) | 29.7 | 46.9 |
| animal_body_living (bāhu, kāka, mayūra, nāsā) | 31.3 | 42.7 |
| natural_action_abstract (bhūmi, pāṭha, rūpa, snāna) | 32.3 | 36.5 |

The strongest and most *stable* resonance is concentrated in the **afflictive** and **virtue/calm** words. This is
predicted by a confound, not by the hypothesis: the frozen v3 consonant glosses are the **binding-vṛtti
(affliction) layer** — mappings like "restless striving that cannot stop", "defeatist annihilation-thought",
"over-holding gone rigid". An *affliction word* (garva = arrogance, droha = malice, kleśa = affliction) matching an
*affliction gloss* is close to tautological; the "resonance" is largely the affective/afflictive class of the word
overlapping the affective class of the gloss, not evidence that the individual varṇas carry composable meaning.

Consistently, **all four evaluator-sensitive words are concrete/body/abstract** (dīpa lamp, kāka crow, nāsā nose,
pāṭha lesson) — where no such class-overlap exists, the score tracks the generosity of the scorer. Qwen (Run B)
rated a lamp, a boat (naukā), clothing (vastra), a nose, and a crow as **MODERATE**; Mistral (Run A) rated the same
words MINIMAL/WEAK/NO.

**This is a construct-validity concern, not a demonstrated Barnum effect.** A Barnum result requires *non-specific*
fitting — the mappings resonating roughly equally with everything. The data show the opposite in part: there is a
real **category gradient** (afflictive/virtue well above concrete/animal/abstract) and Mistral actively rejects
concrete words. That gradient means the instrument *does* discriminate; it is not indiscriminately fitting. A
genuine Barnum test would require running shuffled or alternate-mapping packets and showing they fit equally well —
which this run deliberately did **not** do (no-shuffle is preregistered; specificity was out of scope here). What
the data support is therefore weaker and more specific than "Barnum": (a) a **domain confound** — the frozen
consonant glosses are drawn almost entirely from the affliction/vṛtti domain, so affective words share a semantic
field with the glosses for reasons unrelated to per-varṇa composability; and (b) **interpretive flexibility** at
the rubric's 50-level ("plausible but requires interpretation"), which one model (Qwen) reaches for concrete words
and the other (Mistral) does not. Whether that flexibility is correctable prompt/rubric ambiguity or an inherent
property of symbolic-resonance judgment is exactly what a disagreement audit (§6.1) would resolve — it is not
settled by this run.

---

## 5. Interpretation (honest, adversarial)

**Scope first.** This run tested *one* instrument, not Symbol-U as a whole: one frozen mapping layer (v3 consonant
binding-vṛtti glosses), one bare-word symbolic-resonance rubric, 20 words, two model families, one author/scorer
crossover, no shuffle/alternate controls. Conclusions below are about **the B1.12 LLM-adjudicated resonance
instrument**, not about whether the varṇa mappings have value.

1. **The instrument does not yet provide robust support.** Zero STRONG verdicts; ceiling MODERATE; overall mean
   between WEAK and MODERATE. Under fixed mappings and a no-shuffle rubric, the bare words do not *robustly*
   account for their varṇa mappings — but see (2): most of that is instrument instability, not a clean null.
2. **Scoring is significantly evaluator-dependent.** SIGNIFICANT role-dependence, a systematic ~11-point scorer
   bias (Mistral stricter, Qwen more generous), only 50% verdict agreement, and 35% *incompatible* relationship
   assignments (including implication/opposition sign-flips). The models agree on *what the words mean* (14/20
   identical profiles) but not on *how strongly the mappings resonate*. A word's verdict currently depends too
   much on which model scores it for the score to be treated as model-independent.
3. **The residual pattern has more than one explanation.** The stably-MODERATE words are afflictive/virtue words
   whose semantic field overlaps the affliction gloss layer (a domain confound), and the concrete-word scores
   track scorer generosity (interpretive flexibility). This is *not* a demonstrated Barnum effect — the category
   gradient shows the instrument discriminates, and no shuffle/alternate-mapping control was run (§4). Whether the
   flexibility is correctable rubric/prompt ambiguity or an inherent property of the judgment is unresolved.

**Bottom line:** this is a **methodological-limitation result about the instrument**, not a verdict on Symbol-U.
The reliable finding is that the two LLMs agree reasonably on word meaning but not sufficiently on mapping
resonance, so the current B1.12 LLM scorer is not yet stable enough to serve as an evaluator. It does **not**
establish that the symbolic mappings lack a signal; that question is not answerable from this run.

---

## 6. Recommended next step — disagreement audit (before any further run)

Do not re-run yet. First preserve the missing per-token artifacts (`run_a_scores.json`, `run_b_scores.json`,
`raw_all.jsonl` — see §8), then audit every component where the two runs' scores differ by ≥ 50: inspect the exact
frozen mapping, each model's evidence, the final relationship chosen, and classify the cause as (a) one model
adding semantic supplementation, (b) one model simply stricter, or (c) the rubric genuinely permitting two
reasonable scores. That classification — correctable ambiguity vs. inherent model-dependence — determines whether
the instrument can be tightened or whether LLM adjudication is the wrong tool here. It is the prerequisite for any
claim beyond "evaluator-dependent."

---

## 7. Method integrity notes

- **Frozen before any model call:** BSR scale, 10-type relationship taxonomy, verdict thresholds, role-dependence
  rule, and the 20-word list (all FRESH_UNINSPECTED at selection; glosses read only at scoring time, never during
  selection). Two hard gates passed: input-hash match and required-model availability (no family substitution —
  the exact Qwen3-32B and Mistral-Small-3.1-24B were used).
- **Retries** fired only for structural invalidity (malformed JSON, missing field/evidence, invalid score, invented
  relationship) — never for an unfavorable score — and every attempt is logged in the raw outputs.
- **Relationship-token canonicalization.** The relationship type is a controlled vocabulary. Mistral
  deterministically emitted the orthographic typo `constituitive_property` for `constitutive_property`, which the
  retry loop could not clear. A logged canonicalizer (`bsr_rubric.canonicalize_relationship`) coerces a token to
  its exact taxonomy form **only** when unambiguous (exact / case-separator normalization / unique nearest within
  Levenshtein ≤ 2); semantically distinct tokens (e.g. `causation`, `vibes`) are **not** coerced and still fail as
  `invented_relationship`. This never altered a score, evidence, or which relationship a model chose; every
  coercion is recorded in the `coercions` field of the per-attempt raw log. **Exactly 2 coercions fired in the
  whole run, both `constituitive_property → constitutive_property`** — no other token was touched.
- **No forced consensus.** Run A and Run B judgments are both retained; disagreement is reported, not averaged away.

## 8. Artifacts

Archived in this directory (reconstructed verbatim from the completed RunPod execution): `run_manifest.json`
(`status: COMPLETED`), `model_manifest.json`, `input_hashes.json`, `wordlist_manifest.json`,
`word_verdict_agreement.json`, `relationship_agreement.json`, `role_dependence_summary.json`, and this report.
The full per-component score files (`run_{a,b}_scores.json`), profiles/evidence, and raw model-output logs
(`raw_all.jsonl`, `run_{a,b}_raw_outputs.jsonl`) were produced on the ephemeral execution pod; the pod had no push
access, so the word- and occurrence-level aggregates above (which fully determine every claim in this report) were
transcribed verbatim and the per-token raw logs remain on the pod unless separately exported.

## 9. Repository discipline

No frozen input, controlling preregistration, prior B1.12 artifact, calibration score, feature-lift artifact, or
resolution-study output was modified. This run reads frozen glosses only at scoring time. Structure and reported
model outputs — not validated meaning.
