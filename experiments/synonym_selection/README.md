# experiments/synonym_selection — scaffolding only

Machinery for the **acoustic synonym-selection** pilot pre-registered in
`varna_lens/PREREG_SYNONYM_SELECTION.md` (Version A). **This is scaffolding only:**
verified plumbing, synthetic tests, and a guarded entrypoint. **No fit is computed on
real synonym data, the pre-registration is not frozen or run, and no semantic claim is
made.** Stage A is untouched.

## What is here

| file | role |
|---|---|
| `g2p.py` | Offline CMUdict loader + the **frozen** ARPABET→varṇa map (copied verbatim from `varna_lens/varna_lens.py`, incl. the frozen Indian-English dialect rule). Sound-only tokenization; **no nltk**. |
| `lexicon.py` | Loads the **curated** `varna_lens/lexicon_wordformation.json` `word_formation_reading` field (the binding/in-combination pole). **Not** the engine's `binding_state`. |
| `selection.py` | Confirmatory **equal-weight, consonant-only** composition; cosine selection; **scrambled-table null**; **homophone-invariance leakage check**; **frequency-baseline interface**. Reuses `experiments/common` (`stats`). |
| `reliability.py` | Krippendorff-style interval α + the two-stage gate: within-pool α below floor → **MEASUREMENT_FAILURE**, insider-vs-naïve α below floor → **CIRCULARITY_FAILURE**. |
| `rubric.py` | **Target→vṛtti bridge (Version A)** — frozen, name-blind rubric mapping coded TRAIT ratings → vṛtti vector; **Rubric A dispositive / Rubric B sensitivity** (`RUBRIC_DEPENDENT` if A passes but B disagrees; B can never rescue an A-fail). Synthetic placeholders only. |
| `run_synonym_selection.py` | Guarded entrypoint — emits **NOT_RUN** (no frozen, approved dataset present); computes no real fit. |
| `test_synonym_selection.py` | **Synthetic** machinery tests (24 checks). |
| `test_rubric.py` | **Synthetic** rubric-bridge tests (25 checks): reliable passes, unreliable → MEASUREMENT_FAILURE, insider/naïve divergence → CIRCULARITY_FAILURE, A/B sensitivity, no real data loaded. |

## Design choices (per the pre-registration)

- **Confirmatory composition** = equal-weight, consonant-only count vector over the
  consonant **reading** vocabulary (no positional decay, no vowels, no transitions —
  those are exploratory and are *not* implemented here).
- **Sound, not spelling.** Tokenization is strict g2p; the homophone-invariance check
  enforces that two words with identical g2p get identical profiles (orthographic leak ⇒
  run invalid).
- **Curated table.** Readings come from `lexicon_wordformation.json`, which differs from
  the engine's `lexicon_authoritative.json`/`binding_state` on ca/ra/va/sa/ha/kṣa and the
  vowels. We deliberately do **not** reuse the engine's readings.
- **Scrambled-table null** permutes which consonant gets which reading label (label set
  unchanged); a planted signal beats it, pure noise does not (verified in tests).

## Version-B modularity

`rubric.py` *is* the `target → vṛtti` bridge — the pilot's weakest link (pre-reg §5/§13).
It is isolated so a future **Version B** (pairwise human acoustic-quality judgments → target
ordering directly) can replace it without touching `g2p`/`lexicon`/`selection`: downstream
depends only on the bridge's **output** (per-target profiles/orderings), never on the rubric.

## Deliberately NOT done (gated on pre-reg freeze + approval)

- No real synonym sets, targets, or ground truth.
- No real trait inventory / vṛtti vocabulary (rubric uses synthetic placeholders).
- No real `target → vṛtti` coding or human ratings.
- No fit, no verdict, no frequency data bundled (only the interface).
- No exploratory arms (driver/passenger weighting, vowels, transitions).

## Run

```bash
python3 experiments/synonym_selection/test_synonym_selection.py   # 24 synthetic checks
python3 experiments/synonym_selection/run_synonym_selection.py    # prints NOT_RUN
```

> structure, not validated meaning.
