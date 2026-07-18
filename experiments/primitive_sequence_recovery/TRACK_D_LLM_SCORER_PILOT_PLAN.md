# Track D — Stage D0 LLM-Scored Exploratory Pilot Plan (docs only)

**Plan only. No scoring has occurred. No actual run unless explicitly approved.** `manifest.json`
remains NOT_READY; runner remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED**; no
`ONTOLOGICAL_SIGNAL`; no Sanskrit privilege; Track C V1 negative stands. D0 is **exploratory
triage**, contamination-prone, and **cannot** produce a strict `EXPERIENTIAL_WEATHER_SIGNAL`.

## 0. Honest status of D0

- **Not rigorous validation.** Profiles are **LLM-generated** (not human-blind ground truth); the
  scorer is an **LLM judge** (knows Sanskrit/words/lore). A "match" can be the model's own
  internal consistency, not a real signal. D0 answers only: *is D1 worth funding?*
- Every guardrail below is to reduce — not eliminate — contamination. Residual contamination is
  assumed; the `LLM_PILOT_CONTAMINATED` label exists precisely for it.

## 1. Two-stage blinded LLM design

**Stage 1 — profile generation (word-identity-blind).**
- Input to the LLM: **dictionary meaning only** (+ optional POS/domain). **Not** the Sanskrit
  spelling, **not** the varṇa sequence, **not** the vṛtti glosses. (Excluding the spelling too is
  a deliberate contamination-reduction choice — seeing the Sanskrit word invites cultural/
  etymological priors.)
- Output: an experiential-weather profile of 8–20 controlled-vocabulary descriptors.
- **Cross-model rule (recommended):** the Stage-1 *generator* model should differ from the
  Stage-2 *scorer* model, so a "match" cannot be one model agreeing with itself.

**Stage 2 — anonymous scoring (fully blinded).**
- Input to the LLM: a set of **anonymous composition texts** (arms A/B/C/I all rendered as bare
  gloss-token strings, labelled only `comp_1..comp_n`, shuffled) and **anonymous profile IDs**
  (descriptor lists labelled `prof_X`, no word attached).
- The judge does **not** see: Sanskrit words, dictionary meanings, which composition is real,
  arm labels, or Stage-1 provenance.
- Task: for each profile, score/rank how well each anonymous composition matches it.
- **Structured JSON output only** (§4) — no free-text rationale in the scoring call (rationale is
  a leakage channel; a separate contamination probe handles auditing, §5).

## 2. Randomized arms

For each target word, build these compositions, **shuffle**, and present anonymously:

| arm | composition text presented to the judge |
|---|---|
| **A** | real varṇa/vṛtti gloss composition |
| **B** | scrambled varṇa assignment (same glosses, permuted; per seed) |
| **C** | equal-length affliction-gloss decoy (random vṛtti-gloss set, matched length) |
| **I** | Barnum family members I₁..I₄ (generic-emotional, spiritual/transformation, affliction/wound, inner-growth) |

The judge never learns which is which. (Dictionary/lexical/etymology arms D/E/F from the full
prereg are **not** part of the LLM pilot; they belong to D1's deterministic harness.)

## 3. Barnum control (decisive)

Use the fixed Barnum family and take **max(I₁..I₄)** per target. **If the judge scores the
real composition (A) at or below the best-scoring Barnum member, D0 = `LLM_PILOT_NO_SIGNAL`**,
regardless of A vs B/C. A composition that matches a one-size-fits-all profile no better than a
generic one has triaged *against* the hypothesis.

## 4. Structured JSON output (only)

Stage 1 (generation):
```
{"profile_id":"prof_X","descriptors":["...8-20 controlled-vocab terms..."]}
```
Stage 2 (scoring) — per profile, scores for every anonymous composition:
```
{"profile_id":"prof_X",
 "scores":{"comp_1":0.0-1.0,"comp_2":0.0-1.0,"...":0.0},
 "ranking":["comp_k","comp_j","..."]}
```
Any non-JSON / malformed output → item dropped and counted (not silently); excessive drop rate →
`LLM_PILOT_INCONCLUSIVE`.

## 5. Contamination checks

- **Word-identification probe:** in a separate blinded call, ask the judge to name the Sanskrit
  word / its meaning from an anonymous composition. If it can identify targets above chance →
  the blinding is broken → `LLM_PILOT_CONTAMINATED`.
- **Reference-scan flag:** scan any judge output (and any allowed metadata) for references to
  Sanskrit meaning, the target word, cultural/symbolic/spiritual interpretation, or etymology not
  present in the blinded prompt. Any such reference flags contamination.
- **Cross-model check:** if generator == scorer and results are strong, flag shared-prior
  inflation; prefer generator ≠ scorer.
- **Leakage/tautology inheritance:** exclude words flagged in the Track C audit (e.g. `kāma`,
  gloss literally containing a descriptor) and report separately.
- **Rationale suppression:** JSON-only scoring (no chain-of-thought in the scoring call) to limit
  the judge from reasoning its way to the word identity.

If contamination flags fire materially → **`LLM_PILOT_CONTAMINATED`** (overrides a suggestive
result).

## 6. Metrics

Per target, rank the **real** composition (A) among all anonymous compositions by the judge's
match score to that target's own Stage-1 profile:
- **MRR**, **Top-1**, **pairwise accuracy** (A vs each control).
- Deltas: **A−B**, **A−C**, **A−max(I₁..I₄)**.
- Chance baselines predefined (K = #compositions per target).
- **Robustness:** ≥3 scramble seeds; ≥2 judge temperatures = 0 runs for determinism check;
  bootstrap CI (family-aware) on each delta; report seed/run variance. (Lighter than D1 — this is
  triage — but variance must be reported, per the Track C lesson that single-seed pass is fragile.)

## 7. Decision labels (D0 only)

Allowed:
- **`LLM_PILOT_SUGGESTIVE`** — A beats B, C, **and max(I₁..I₄)** on the primary metric, no
  material contamination flags, effect not obviously seed-fragile. Means only: *D1 may be worth
  funding.*
- **`LLM_PILOT_NO_SIGNAL`** — A ≈ B, or A ≤ best Barnum, or fails the controls.
- **`LLM_PILOT_INCONCLUSIVE`** — high output-drop, high variance, degenerate profiles, or controls
  not separable.
- **`LLM_PILOT_CONTAMINATED`** — contamination probe/scan fires materially (overrides suggestive).

**Forbidden at D0:** `EXPERIENTIAL_WEATHER_SIGNAL`, `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any
Track-B-unblocking or validation language. Even `LLM_PILOT_SUGGESTIVE` is **triage, not evidence
for Symbol-U**.

## 8. Reporting template

| axis | metric | real (A) | scrambled (B) | decoy (C) | best Barnum max(I₁..I₄) | chance | CI(A−ctrl) | contamination | label |
|---|---|---|---|---|---|---|---|---|---|
| LLM pilot (abstract set) | MRR/Top1/pairwise | | | | | | | flags? | |
| concrete negative-control | " | | | | | | | | (must be ~chance) |

Plus: generator model + scorer model (and whether distinct), seeds/temperatures, output-drop
rate, contamination-probe result, excluded leakage words, and the explicit statement that
profiles are LLM-generated (not human-blind).

## 9. Environment / approval

- Requires an available LLM (hosted or a local frozen model). In an offline-only environment this
  cannot run; the honest outcome there is "pilot not run — no LLM available," not a fabricated
  result.
- **No actual scoring until explicitly approved.** On approval, prefer a **local/frozen** or
  version-pinned model and record model id/version; a hosted API is exploratory-only and its
  nondeterminism/version drift must be reported.

---

D0 is exploratory triage only. D1 human-blind validation is deferred. Track B remains blocked.
Structure, not validated meaning.
