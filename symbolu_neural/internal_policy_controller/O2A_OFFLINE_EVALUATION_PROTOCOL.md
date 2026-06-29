# O2A offline evaluation protocol — PRE-REGISTERED

> **Type:** pre-registration. **No code yet.** Datasets, features, baselines, metrics, and
> thresholds are frozen **before** any implementation or data peeking. The reading ρ is a
> hypothesis on trial; it must earn the right to a policy translator (O2B) through this
> offline gate alone — **no LLM, no API.**

## 0. Pre-registration discipline

1. Datasets (§2) are authored and **frozen** (committed; `sha256` recorded) **before** any
   feature or baseline is computed.
2. Reading-feature set (§3), baselines (§4), metrics (§5), thresholds (§6) are fixed
   **before** running. One run, one verdict.
3. Thresholds are **not** moved after seeing data. Deviations are logged as amendments
   with a reason, before re-running.

## 1. Hypotheses

- **H0 (null):** the varṇa semantic reading carries no meaning-discriminating signal
  beyond a sentiment baseline and the raw phonetic substrate; and/or it is unstable under
  paraphrase; and/or it fails to generalize beyond curated in-lexicon vocabulary.
- **H1 (alt):** the reading discriminates the contrasts the ontology *claims* to capture,
  **above sentiment and above the phonetic substrate**, is stable under
  same-meaning paraphrase (including same-meaning/different-sound), flips on
  opposite-meaning minimal pairs, is human-recoverable, and generalizes to a holdout.

## 2. Datasets (frozen before running)

### 2.1 Six labeled contrast sets — mapped to Symbol-U's OWN claimed dimensions
Each: 20 + 20 sentences, grouped as 5 meanings × 4 paraphrases per pole. Mapping the
contrasts to the ontology makes the test *fair to Symbol-U* — we ask whether the reading
captures the distinctions it claims to make.

| # | Contrast | Claimed Symbol-U dimension | Pole examples |
|---|---|---|---|
| C1 | **joy vs grief** | valence (liberating vs binding) | "We're overjoyed — she said yes." / "He's gone, and I'm shattered." |
| C2 | **calm vs urgent** | vṛtti motion / arousal | "No rush, take your time." / "Call 911 now — he's not breathing!" |
| C3 | **grounded vs speculative** | pramāṇa vs vikalpa | "The build passed all 412 tests." / "Prices might possibly rebound, who knows." |
| C4 | **clear vs confused** | clarity vs nidrā | "Do step 1, then step 2." / "I'm not sure… it's all a blur, hard to say." |
| C5 | **memory/recall vs non-memory** | smṛti vs non-smṛti | "As I recall from last year's report…" / "Here is a fresh definition of entropy." |
| C6 | **high-certainty vs low-certainty** | confidence | "This is definitely correct." / "Maybe, perhaps, it could be." |

**Adversarial note (pre-registered prediction):** the varṇa reading is affect/pole-
oriented, so it will likely do **better on C1–C2 (affective)** than on **C3–C6
(epistemic)**. If it fails the epistemic contrasts, that is itself a finding — the reading
covers only part of the claimed ontology — and is reported per-contrast, not hidden in an
average.

### 2.2 Paraphrase sets
- **P1 — same meaning, different wording** (10 meanings × 4). Stability test.
- **P2 — same meaning, different surface SOUND** (10 meanings × 3): synonyms chosen to
  share meaning but differ phonetically ("furious"/"livid"/"enraged"). **This is the
  decisive "merely sound-pattern" discriminator** — a meaning-reading should stay stable;
  a sound-reading should move.
- **P3 — opposite meaning, similar wording / minimal pairs** (15 pairs): "I am happy" vs
  "I am not happy"; "this is safe" vs "this is unsafe". A meaning-reading should **flip**;
  a surface/sound-reading should not.

### 2.3 Generalization / anti-circularity holdout
- **G1 — 30 sentences** with novel/rare vocabulary and cross-domain framing (technical,
  legal, scientific) where affect/intent is implicit — stressing vocabulary the
  hand-authored glosses were not built around.

Freeze: record `sha256` of the dataset file in the run log.

## 3. Reading-feature vector (fixed before running)
Per sentence, from the varṇa reading: `valence_continuous` (lib/(lib+bind)), `mean_sign`,
`tension` (fraction of adjacent pole-sign flips), `coherence` (1 − normalized entropy of
the pole/essence distribution), `dominant_pole` (one-hot). No features added/removed after
seeing results.

## 4. Baselines (fixed before running)
- **B0 — sentiment lexicon** (VADER compound; AFINN fallback). Guards "merely sentiment."
- **B1 — text length** (token count). Trivial-confound control.
- **B2 — random labels.** Sanity floor: the reading must NOT separate randomly-assigned
  labels (expected AUC ≈ 0.5); if it does, it is overfitting tiny n.
- **B3 — raw phonetic substrate** = the `vritti_mapper` dynamic-state distribution (the
  content-blind signal v3/v4 used). **The reading must beat this**, or the "semantic"
  reading is merely sound. *(This is the most important adversarial baseline.)*
- **B4 — sentence embedding** (optional; only if an offline embedding model already
  exists — do not add a dependency). Upper-reference for available semantic signal.

## 5. Metrics
1. **M1 Class separability** — per contrast (C1–C6): 5-fold-CV AUC from reading-features.
2. **M2 Inter/intra paraphrase ratio** — on P1+P2: R = mean(inter-meaning dist) /
   mean(intra-paraphrase dist) over standardized reading vectors.
3. **M2b Minimal-pair flip** — on P3: fraction of opposite-meaning pairs whose reading
   distance exceeds the median same-meaning paraphrase distance.
4. **M3 Residual variance beyond sentiment+length** — ΔAUC of reading over B0+B1, and
   partial correlation of reading with labels controlling for B0.
5. **M4 Blind human recoverability** — ≥3 raters pick the pole from the rendered reading
   alone (30-item sample); accuracy + Fleiss κ.
6. **M5 Out-of-lexicon generalization** — re-run M1/M3 on G1.

## 6. FROZEN pass/fail thresholds

- **M1 (meaningful discrimination):** mean AUC over C1–C6 ≥ **0.72**, AND reading beats
  **B3 (phonetic substrate)** by ≥ **0.07** on ≥ **4/6** contrasts, AND beats **B0
  (sentiment)** by ≥ **0.05** on ≥ **3/6**, AND beats **B2 (random ≈0.5)** on ≥ **5/6**.
- **M2 (paraphrase stability):** R ≥ **1.5** AND within-paraphrase `dominant_pole`
  agreement ≥ **70%**; **on P2 specifically** (different sound, same meaning) reading
  distance must be ≤ the C1–C6 inter-pole distance (i.e., sound change moves it less than
  meaning change).
- **M2b (minimal-pair flip):** ≥ **70%** of P3 opposite-meaning pairs flip.
- **M3 (non-redundancy):** ΔAUC ≥ **0.05** on ≥ 2 contrasts AND partial corr p < 0.05 on
  ≥ 2 contrasts. "**Redundant with sentiment**" = M1 passes but M3 fails.
- **M4 (interpretable):** accuracy ≥ **70%** and κ ≥ **0.4**. Fallback (no humans):
  strict CV logistic reading→label = "proxy only" → caps verdict at PROVISIONAL-PASS.
- **M5 (generalizing):** mean AUC on G1 ≥ **0.65** AND ≥ (in-set mean AUC − **0.10**).

## 7. Explicit failure modes (each tied to a guard)

| Failure mode | Caught by | Verdict |
|---|---|---|
| **Merely sentiment** | M3 fails (no variance beyond B0) | PARTIAL |
| **Merely sound-pattern** | loses to B3 (M1), or P2 moves it as much as meaning (M2) | FAIL |
| **Unstable under paraphrase** | M2 R < 1.5 or low dominant-pole agreement | FAIL |
| **Non-generalizing / circular w/ lexicon** | M5 collapses on G1 | FAIL |
| **Human-uninterpretable** | M4 < 70% / κ < 0.4 | FAIL (or PROVISIONAL if proxy) |
| **Tracks surface form, not meaning** | M2b minimal pairs don't flip | FAIL |

## 8. Decision tree

```
Run all metrics once on frozen data.
├─ M1 ✓ AND M2 ✓ AND M2b ✓ AND M3 ✓ AND M5 ✓ AND M4 ✓
│     → PASS  →  build the O2B policy translator.
├─ M1 ✓ but M3 ✗ (real but fully explained by sentiment)
│     → PARTIAL  →  improve the READING only (enrich ρ: positional/CSR/hierarchy).
│                    NO LLM, NO API. Re-enter this protocol.
└─ M1 ✗  OR  M2 ✗  OR  M2b ✗  OR  M5 ✗
      → FAIL  →  STOP the Symbol-U policy-controller path.
                  The current reading ρ is not meaningfully discriminative; document and halt.
```

## 9. Why O2A must pass before O2B exists

A policy translator (O2B) can only transmit signal that the reading actually contains.
Building O2B on a reading that hasn't passed O2A repeats the exact error this whole
investigation uncovered: v3/v4 spent real API budget translating a near-constant,
content-blind state into prompts, and the "null" that resulted said nothing about
Symbol-U — only about a signal that was never there. O2A is the firewall: it asks "is
there a meaning signal at all?" **deterministically, offline, for free**, with adversarial
baselines (sentiment, length, random, and the very phonetic substrate that failed before).
If the reading cannot clear those, no translator and no LLM can rescue it, and we save the
entire O2B + API cost. If it clears them, O2B finally tests a hypothesis worth testing.
O2B does not exist until O2A earns it.

## 10. Cost & pre-registered adversarial prior

Offline, deterministic, minutes of compute (M4 needs human raters; all else automatic).
**Zero API.** My genuine prior: the most likely outcome is **PARTIAL** — real
discrimination on the affective contrasts (C1–C2) that is **largely explained by
sentiment** (M3 fails) and/or **weak on the epistemic contrasts (C3–C6)** and on the G1
holdout. A clean PASS would be a genuinely surprising positive result and the first earned
justification for O2B. Either way the verdict is reached with no API and no policy code —
which is the point.
