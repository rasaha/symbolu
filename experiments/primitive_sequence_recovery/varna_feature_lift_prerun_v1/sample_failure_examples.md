# Failed / Excluded Sample Examples — Varṇa Feature-Lift Pre-Run

Companion to `VARNA_FEATURE_LIFT_PRERUN_FREEZE_REPORT.md`. Narrates the excluded candidates so the exclusion
logic is auditable in prose. **Every exclusion reason here is structural or lexical.** No candidate was excluded
because its varṇa feature looked weak, its target looked hard, or it failed to fit the theory. `EXPLORATORY /
DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

Machine-readable source of truth: `excluded_word_manifest.json` (18 rows) and `sample_failure_funnel.json`.

## First 10 candidates in source order (transparency sample)

Shows the pipeline is not cherry-picking — the earliest candidates, included or not, with outcomes:

| ID | IAST | Gloss | Outcome |
|---|---|---|---|
| S001 | agni | fire | included (train) |
| S002 | aja | goat | included (train) |
| S003 | asthi | bone | included (test) |
| S004 | aśma | stone | included (dev) |
| S005 | aśva | horse | included (dev) |
| S006 | bala | strength | included (test) |
| S007 | bhakti | devotion | included (train) |
| S008 | bhaya | fear | included (test) |
| S009 | bhojana | food | **excluded — MATERIAL_GLOSS_VALENCE_CONFLICT** |
| S010 | buddhi | intellect | included (train) |

## Excluded by category

### MATERIAL_GLOSS_VALENCE_CONFLICT (10) — the ordinary gloss splits across materially different senses

These words have no single dominant English gloss that can honestly carry one affective label. The problem is
**translation**, not affect — recorded *before* any target was consulted.

- **S009 bhojana → "food"** — food vs eating vs meal are materially different referents.
- **S016 dharma → "virtue"** — virtue / duty / law / religion; no single ordinary gloss.
- **S027 go → "cow"** — cow / earth / ray / speech (classically polysemous).
- **S040 kara → "hand"** — hand / ray / tax.
- **S047 kāma → "desire"** — desire vs love vs lust diverge in valence and referent.
- **S048 kṣetra → "field"** — field / body / sacred-place.
- **S053 mada → "pride"** — pride vs intoxication.
- **S059 mukha → "face"** — face vs mouth.
- **S074 rakta → "blood"** — blood (noun) vs red (adjective).
- **S090 varṣa → "rain"** — rain vs year.

Note this gate is affect-blind by construction: it removes *kāma* (desire) — a word the affliction theory would
most want to "explain" — purely because its gloss is ambiguous, not because of any predicted or observed score.

### PROPER_NAME_OR_TECHNICAL_TERM (3) — proper names / religious-philosophical technical terms

- **S014 deva → "god"** — religious technical term.
- **S098 yajña → "sacrifice"** — ritual technical term.
- **S101 ātman → "self"** — philosophical technical term (self/soul, doctrine-laden).

### NO_EXACT_NORM_MATCH (2) — gloss absent as an exact lemma in the norms lexicon

Exact lowercase-lemma lookup, no fuzzy fallback (pre-declared). Both independently verified absent in the pinned
Warriner CSV:

- **S022 gamana → "going"** — "going" not present as an exact lemma.
- **S032 haṃsa → "swan"** — "swan" not present as an exact lemma.

### DUPLICATE_ENGLISH_GLOSS (3) — same controlling gloss as an already-kept word

Dependence dedup: keep the alphabetically-first IAST form, drop later duplicates (mechanical, target-blind).

- **S068 parvata → "mountain"** — duplicate of **S026 giri** (mountain).
- **S088 vahni → "fire"** — duplicate of **S001 agni** (fire).
- **S093 vānara → "monkey"** — duplicate of **S039 kapi** (monkey).

## Close-to-inclusion cases (would flip on a single non-outcome change)

- **S022 gamana, S032 haṃsa** — parser-valid, unambiguous, scope-clean; excluded *only* because the exact English
  gloss is missing from the norms lexicon. A different exact-lemma gloss (still fixed blind) or a lexicon that
  contained "going"/"swan" would include them. Not excluded for anything about the feature.
- **S068 parvata, S088 vahni, S093 vānara** — fully eligible on their own; excluded *only* as gloss-duplicates of
  an earlier kept synonym. Had their synonym mate not been in the pool, they would be included.

## What is NOT a failure reason here

For the record, none of the following was ever used to exclude a sample, and each is prohibited as an exclusion
rationale: "varṇa feature looked weak," "target seemed hard to predict," "arousal/valence value was
inconvenient," "did not match the expected affliction," "would hurt the real-vs-shuffled contrast." The taxonomy
admits only structural (parser/mapping), lexical (gloss ambiguity, technical term, missing norm), and dependence
(duplicate/near-duplicate) reasons.
