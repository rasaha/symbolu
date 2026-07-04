# Track E — Smoke-Pilot Input Bundle Status

**Input bundle created for REVIEW ONLY. Nothing run, scored, or approved.** No experiment, no
LLM/scorer call, no network, no model download. `frozen/manifest.json` remains **NOT_READY** (not
edited); the psr runner remains **NOT_RUN**; Stage A is untouched; **Track B remains BLOCKED**; no
`ONTOLOGICAL_SIGNAL`, no `EXPERIENTIAL_WEATHER_SIGNAL`, no Sanskrit privilege. Nothing here
reinterprets the Track C or D0 negatives.

## What was created

The 10–15-case smoke input bundle specified in `TRACK_E_SMOKE_PILOT_RUNBOOK.md`, using the
**current flat boundary-constraint design** (arms **A** real boundary, **B** scrambled boundary,
**X** context-only, **F** etymology-only, **D** dictionary-only, **I** Barnum boundary). **12
cases.**

| File | Contents |
|---|---|
| `track_e_smoke_words.jsonl` | 12 words: domain, decomp_mode, contamination_risk, exploratory_only, scorer-facing `broad_gloss`; hidden `dev_surface_word` / `dev_varna_sequence` (draft, consonant-only) |
| `track_e_smoke_contexts.jsonl` | one disambiguating sentence per case; `context_correct_candidate_id` (hidden answer key) |
| `track_e_smoke_candidates.jsonl` | 6 candidates per case (1 context-correct, 3 hard negatives, 1 dictionary-valid-but-context-wrong, 1 Barnum-compatible); `role` is a hidden field |
| `track_e_smoke_etymology.jsonl` | generic scorer-facing `etymology_prior_description` (arm F); actual root in hidden `dev_root` |
| `track_e_smoke_boundaries.jsonl` | scorer-facing `boundary_real_description` (A) and `boundary_scrambled_description` (B), composed from the frozen en_gloss table; hidden `dev_varna_sequence` + full gloss terms |
| `track_e_smoke_barnum.json` | 4 generic Barnum boundaries (B1–B4) + the arm-I `max` rule |
| `track_e_smoke_seeds.json` | fixed seeds: candidate shuffle, boundary scramble, packet order, Barnum variant order |
| `track_e_smoke_manifest.json` | `run_enabled:false`, `approval_status:"NOT_APPROVED"`, `representation:"flat_boundary_constraint"`, `four_sphere_integrated:false`, file list + sha256 hashes, case groupings |

**Case mix:** 7 abstract_primary, 3 concrete_control, 2 famous_exploratory (`exploratory_only:true`,
excluded from the primary label set). Primary read = the 7 abstract cases only.

## How boundaries were built (honesty note)

The scorer-facing `boundary_real_description` for each word is composed **deterministically** from
the **frozen `realization_en_gloss.json`** glosses of that word's varṇa sequence; the scrambled
arm reads a seeded permutation of the same table. The varṇa **sequences themselves are DRAFT,
consonant-only, and unverified** (`dev_status:"draft_consonant_only_unverified"`) and live only in
hidden `dev_` fields — they **must be linguistically verified before any freeze**. This bundle is a
review draft, not a frozen artifact.

## Authored candidate positions (balanced)

Authoring-time correct-answer positions use a **seeded balanced permutation**: each of the 6
candidate slots holds the correct answer **exactly twice** across the 12 cases, with adjacency and
periodic cycles rejected. It is driven by `seeds.candidate_authoring_balanced = 8675309` (recorded
in `track_e_smoke_seeds.json` and the manifest's `authoring_note`); the other candidates per case
are shuffled deterministically via `f"{candidate_authoring_balanced}:others:{word_id}"`. This
supersedes both the earlier regular descending cycle (`cand_1, cand_6, cand_5, …`) and the interim
naive pseudo-random assignment (which left slot 6 unused). **Candidate meanings and correct labels
are unchanged; only ids/order changed.** Resulting correct-answer slots:
`[5,1,2,4,1,2,3,6,3,6,4,5]` — all 6 slots used exactly twice, no adjacent repeat, no cycle.

This is **authoring hygiene / reviewer optics only.** The real protection is the **runtime packet
shuffle**, which remains **mandatory**: every packet is re-shuffled with `seeds.candidate_shuffle`
and `role`/`context_correct_candidate_id` stay hidden, so the authored order never reaches a
scorer. The runbook §8 approval gate now carries an explicit "Runtime candidate shuffle enabled"
checkbox.

## Anonymization (enforced by the builder's validation)

Scorer-facing fields carry **no surface word, no varṇa names, no root names, and no arm labels**;
parentheticals in the frozen glosses (which sometimes name a varṇa/root, e.g. the `ha` gloss) are
stripped from the composed boundary text. Roles, the correct-answer id, and all `dev_` fields are
hidden. A whole-word scan over every scorer-facing string confirms none contains a case's surface
word, a root-name token, or a varṇa key; a separate check confirms no context sentence contains
candidate wording verbatim.

## Validation (all green; data-only, no experiment)

- all 8 files parse (JSON / JSONL);
- 12 cases, mix within bounds (7 / 3 / 2);
- every case: exactly 1 context-correct, ≥3 hard negatives, ≥1 dict-valid-context-wrong, ≥1
  Barnum-compatible; unique candidate ids; answer id resolves to the context-correct role;
- exploratory-only cases excluded from `primary_label_cases`;
- correct-answer positions exactly balanced (each of the 6 slots ×2) with no adjacency and no
  descending / arithmetic / repeated-period cycle;
- **four-sphere artifact not referenced** in any data file (and `four_sphere_integrated:false` in
  the manifest);
- no scorer-facing field leaks surface/varṇa/root tokens;
- manifest `run_enabled:false`, `approval_status:"NOT_APPROVED"`.

## What this is NOT

- Not a run, not scoring, not an LLM call — data preparation only.
- **Four-sphere JSON not integrated.** `track_e_varna_sphere_lexicon.json` stays a parked candidate
  artifact; this bundle uses the flat design only.
- Not an approved smoke pilot. Approval requires the completed §8 gate in the runbook (model pair,
  frozen case list, seeds, signature) and verified varṇa sequences; until then the runner stays
  NOT_RUN and `run_enabled:false`.
- Not validation, and not a rescue or reinterpretation of Track C / D0. Track B remains blocked.

---

Track E smoke input bundle prepared for review only. Smoke pilot is not approved or run. Four-sphere JSON remains a saved candidate artifact, not an adopted Track E input. Track B remains blocked. Structure, not validated meaning.
