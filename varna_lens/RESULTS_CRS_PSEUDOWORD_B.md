# Results — Design B (CRS-weighted interpretation) on pseudowords

> Pre-registration: `PREREG_CRS_POLE_SELECTION.md` (Design B = rank/weight structurally-decoded readings;
> never flip a pole). Harness: `crs_pseudoword_test.py` + `wordlist_pseudo.py`. **Date:** 2026-06-25.
> Interpretive lens — not part of C×R×S(truth). This run reports the machine-checkable arms and **gates** the
> content verdict; it does **not** declare Design B valid or invalid.

## What was built and run
- 80 seeded pronounceable **pseudowords** (no dictionary meaning ⇒ nothing for the semantic term S to leak).
- Structural decode per word (Design A / R) → `emergent_valence`; CRS scaffold `α·logC + β·logR + γ·logS`
  with the firewall (S sees only the decoded reading + context pole), the control ladder, and per-word
  provenance logging.
- Arms executed **now** (no API needed): `random` null judge, `structure` judge, the relabeling-invariance
  check, and an **independent** structural-vs-sound-symbolism correlation. `N_BOOT = 10000`.

## Findings

| measurement | value | reading |
|---|---|---|
| **relabeling-invariant** (permute lexicon glosses → recompute) | **TRUE** | structural score is gloss-INDEPENDENT |
| structural reading vs independent sound-symbolism (Spearman) | **0.205**, 95% CI **[−0.018, 0.424]** | CI includes 0 → **not significant** |
| random-judge null vs sound-symbolism | −0.106 | ≈ chance (machinery clean) |
| `structure`-judge model vs sound-symbolism | 0.205 (== structural) | structure-S adds **nothing** beyond R |

## The gating result (why the content verdict cannot be reached deterministically)

> **A deterministic, structure-based S is RELABELING-INVARIANT.** The decoded signs / `emergent_valence`
> depend on phoneme POSITION, not on gloss CONTENT (empirically confirmed: permuting the entire lexicon left
> every per-word structural score identical, `relabeling_invariant = TRUE`). Therefore any deterministic
> structure-S equals R up to the context sign and **cannot distinguish the real lexicon from a shuffled one**.

Consequence for the prereg: the **content** question Design B ultimately asks — *does the binding/liberating
MEANING cohere with context better than shuffled-S?* — **cannot be answered by any deterministic structural
judge.** It necessarily requires a **semantic** judge (LLM / human) reading the actual glosses — which is
precisely the channel the firewall watches, and which is **gated** here (`ANTHROPIC_API_KEY` absent).

This is not a workaround failure; it is the relabeling-invariance theorem of this project, reappearing at
the operator level: only gloss-SEMANTICS can break the real-vs-shuffled tie, and a deterministic structure-S
never uses gloss semantics.

## Decision-rule status (per prereg §8): **GATED**
- **R1 / R2 / R3 are not adjudicated for content.** They compare CRS to R-only and shuffled-S on **human
  coherence ratings**; the only content-sensitive S (LLM/human) is unavailable in this environment.
- **Structural baseline characterized:** the structure-only reading shows **no significant** alignment with
  an independent sound-symbolism axis (r = 0.205, CI [−0.018, 0.424]) — consistent with the project's prior
  NO_SIGNAL track record, though here it is only an off-axis cross-check, not the on-axis verdict.
- **No claim** that Design B is valid or invalid is made. The machinery is validated (random null clean;
  invariance proven; provenance logged); the verdict awaits the semantic judge.

## Exact next step to reach a verdict
Run `crs_pseudoword_test.py --judge llm` (the real content-S) **with API/panel access**, on the
**binding/liberating** context frame (the on-axis frame, rated as an internal impression per prereg §7),
with the held-out human/LLM coherence target and the **shuffled-S** control. Pass iff CRS beats both R-only
and shuffled-S on pseudowords (prereg R3). Until then, Design A (structure-first) remains the sole shipped
reader, exactly as the prereg's decision A specifies.

## Firewall / integrity notes
- S was handed only `(decoded reading, context sign)` — never a gloss, known valence, target explanation, or
  eval label. Pseudowords have no gloss, enforcing this structurally.
- Prior empirical/falsification results are untouched; no pole was ever flipped (Design B constraint held).
