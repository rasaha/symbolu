# Track D — D0 Error Taxonomy & Discovery-Analysis Plan (docs only)

**Discovery-analysis plan for a future D0 run. Nothing executed.** No D0 run, no LLM call, no
real scoring, no results. `manifest.json` remains NOT_READY; runner remains NOT_RUN;
`frozen/manifest.json` untouched; Stage A untouched; **Track B remains BLOCKED**; no
`EXPERIENTIAL_WEATHER_SIGNAL`, no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege.

Purpose: make D0 report **what kind of failure** occurred, not just pass/fail — so a
`LLM_PILOT_NO_SIGNAL` becomes *informative* (wrong hypothesis vs wrong/too-narrow construct)
without ever being rescued into a positive. Companion: `TRACK_D_D0_REAL_PILOT_RUNBOOK.md`,
`TRACK_D_D0_PROPOSED_PILOT_CONFIG.md`, `TRACK_D_LLM_SCORER_PILOT_PLAN.md`.

## 1. Error taxonomy (predefined categories)

Each category has a detection rule computed from the D0 report (arms A/B/C/I, subsets, seeds).
Categories are **diagnostic labels**, not outcome labels; the outcome label stays one of
`LLM_PILOT_SUGGESTIVE / NO_SIGNAL / INCONCLUSIVE / CONTAMINATED`.

| category | detection rule (from D0 metrics) |
|---|---|
| `BARNUM_OVERMATCH` | `max(I₁..I₄)` ≥ target-profile score for A (real ≤ best Barnum) |
| `SCRAMBLE_EQUIVALENT` | A ≈ B (real vs scrambled delta within noise band) |
| `DECOY_EQUIVALENT` | A ≈ C (real vs equal-length affliction decoy within noise band) |
| `CONCRETE_OVERMATCH` | concrete negative-control set matches ≈ as strongly as the abstract primary set |
| `FAMOUS_WORD_CONTAMINATION` | §4c high-contamination subset "succeeds" while §4a/§4b primary fails |
| `PROFILE_TOO_GENERIC` | target profile fails hard-negative discrimination (not ranked above emotionally-adjacent neighbors) |
| `SCORER_CONTAMINATION` | judge references Sanskrit / culture / hidden identity / out-of-packet knowledge (probe or scan) |
| `VOWEL_ONLY_GAIN` | any gain appears only in vowel-aware (G) vs consonant-only (H), not in A-vs-controls |
| `ETYMOLOGY_EXPLAINS_GAIN` | etymology baseline (F) accounts for the effect (A−F ≈ 0) |
| `SUBDOMAIN_SPECIFIC` | signal confined to a specific semantic class (e.g., only afflictions, only relational terms) |
| `POSSIBLE_NEW_CONSTRUCT` | a **consistent** pattern appears that is **not** aligned with the pre-registered weather hypothesis |

Multiple categories may fire; report all, ranked by prevalence. `POSSIBLE_NEW_CONSTRUCT` is the
only "generative" category and is bound by the no-rescue rule (§3).

## 2. Discovery report (added to the D0 report)

Beyond the primary label, the report summarizes:

- **Dominant failure class** — which taxonomy category fired most across items.
- **By word domain** — do failures differ across abstract vs concrete vs (exploratory) famous?
- **Abstract vs concrete controls** — do abstract/psychological words behave differently from the
  concrete negative-control? (If not → `CONCRETE_OVERMATCH` / Barnum at corpus level.)
- **Famous vs low-contamination** — do §4c famous words behave differently from §4a low/med
  words? (If famous "work" and primary doesn't → `FAMOUS_WORD_CONTAMINATION`.)
- **Barnum locus** — is `BARNUM_OVERMATCH` **global** (all I₁..I₄) or specifically **I₃
  affliction/wound**? (I₃-only overmatch is the expected pattern, since vṛtti glosses *are*
  afflictions — see §4 queue item "affliction-field prediction.")
- **Non-Barnum structure** — does any subdomain show consistent structure **not** explained by
  Barnum/scramble/decoy/etymology (candidate `SUBDOMAIN_SPECIFIC` / `POSSIBLE_NEW_CONSTRUCT`)?

All of this is descriptive triage output; none of it changes the primary label.

## 3. No-rescue rule (binding)

- Discovery analysis **cannot** convert a `LLM_PILOT_NO_SIGNAL` (or any non-`SUGGESTIVE` label)
  into a positive result. Failure explanation ≠ success.
- Any construct suggested by `POSSIBLE_NEW_CONSTRUCT` (or by the §4 queue) **must become a new,
  separate pre-registration** with its own hypothesis, controls, and freeze — authored **before**
  looking at more data. It is a *lead*, not a finding.
- **No post-hoc reinterpretation** of D0 output may be reported as validation, as
  `EXPERIENTIAL_WEATHER_SIGNAL`, as `ONTOLOGICAL_SIGNAL`, or as Track-B progress.
- The concrete-control and Barnum gates remain hard: a result that fails them is negative
  regardless of any interesting-looking substructure.

## 4. Possible next-hypothesis queue (only if D0 is negative; each needs a NEW pre-registration)

Leads to consider — **none assumed, none a rescue** — each requiring its own pre-reg + controls:

- **affliction-field prediction** — do compositions predict an affliction/wound field rather than
  a full "experiential weather"? (Motivated by expected I₃ overmatch.)
- **guṇa / polarity prediction** — do compositions predict sattva/rajas/tamas or a
  binding↔liberating polarity rather than specific emotions?
- **contrastive antonym / prefix recovery** — vowel-aware model distinguishing a-privative pairs
  (vidyā/avidyā, himsā/ahimsā) that consonant-only cannot.
- **vowel-aware semantic shift** — does adding vowel varṇas change recovery at all?
- **abstract-only vṛtti matching** — restrict the claim to abstract/psychological terms (drop
  concrete nouns as out-of-domain).
- **relational / emotional-role matching** — predict relational roles (self/other, approach/
  withdraw) instead of profiles.
- **etymology-mediated signal** — is any usable signal actually an etymology effect (test with F)?
- **non-English / non-LLM scorer requirement** — the whole approach may need a scorer that is not
  English-embedding- or LLM-based to escape leakage (points back toward the blocked independence
  problem, honestly noted).

Each item, if pursued, starts a fresh hypothesis document; it does not reopen or reinterpret D0.

## 5. Boundary

D0 discovery analysis can explain failure modes but cannot rescue a failed pilot. Any new
construct requires a new pre-registration. Track B remains blocked. Structure, not validated
meaning.
