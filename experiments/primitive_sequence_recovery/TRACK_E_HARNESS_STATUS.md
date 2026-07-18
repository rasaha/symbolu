# Track E Synthetic Harness — Status

**Synthetic mechanics only. Nothing run, scored, or validated.** No LLM, no network, no real
data, no model download, no scoring of the hypothesis. `manifest.json` remains **NOT_READY**; the
psr runner remains **NOT_RUN**; Stage A is untouched; **Track B remains BLOCKED**; no
`ONTOLOGICAL_SIGNAL`, no `EXPERIENTIAL_WEATHER_SIGNAL`, no Sanskrit privilege.

**Four-sphere JSON not integrated.** This harness implements the *current* Track E flat
boundary-constraint design (single boundary per arm; controls A/B/X/F/D/I). The four-sphere varṇa
lexicon (`track_e_varna_sphere_lexicon.json`) remains a **saved candidate artifact only** — it is
**not** loaded, referenced, or used by the harness, fixtures, or tests, and adopting it would
require separate approval and its own controls. This is the
synthetic-first harness required by §9 of `TRACK_E_IMPLEMENTATION_PILOT_PLAN.md`, built and proven
on toy data **before** any real Track E data exists.

## What was built

| File | Role |
|---|---|
| `track_e_harness.py` | Metric + decision mechanics. Takes a synthetic scorer's per-arm candidate scores *in*; computes per-arm MRR / Top-1 / pairwise, the incremental deltas (`A_vs_X` primary, plus `A_vs_B/F/D/I`), and assigns one of the seven allowed Track E labels. Loud `RejectedFixture` on any malformed / contaminated / real-language input. `run_real_pilot()` raises `NotImplementedError`. |
| `toy_fixtures/track_e_toy_cases.json` | 9 SYNTHETIC cases (nonsense tokens only), marked `toy_not_for_scoring=true` + `synthetic_only=true`. Seven exercise each allowed label; two are deliberate rejects (malformed scorer output; contamination flag). |
| `test_track_e_harness.py` | Synthetic mechanics tests (all passing). |

## What the harness does (and does not) do

- **Does:** rank the context-correct candidate under each of the six arms (A real, B scrambled,
  X context-only, F etymology-only, D dictionary-only, I Barnum), compute the incremental deltas,
  and apply the pre-registered decision precedence. It is a deterministic scoring/labeling
  calculator over scores that are *handed to it*.
- **Does not:** call any model, embed anything, decompose any word, or decide whether a boundary
  is "real." It computes nothing about Symbol-U. The scores in the fixtures are hand-authored
  synthetic numbers chosen to trigger specific label branches — they are not evidence of anything.

## Decision precedence (as implemented and tested)

`decide()` applies, in order (equivalence band `EPS = 0.02` on MRR):

1. **arm span ≤ eps** → `INCONCLUSIVE` (arms not separable; the setup can't discriminate).
2. **`A_vs_X` ≤ eps** → `CONTEXT_ONLY_EXPLAINS` — **primary falsifier**: no incremental gain over
   context. This veto takes precedence over every other, matching the prereg's core bar
   ("if context already selects the candidate, varṇa has nothing left to explain").
3. **`A_vs_B` ≤ eps** → `SCRAMBLE_EQUIVALENT` (specific mapping adds nothing).
4. **`A_vs_I` ≤ eps** → `BARNUM_BOUNDARY` (a generic boundary reweights as well).
5. **`A_vs_F` ≤ eps** → `ETYMOLOGY_EXPLAINS` (root priors account for it).
6. **all of `A_vs_X/B/F/D/I` > eps** → `BOUNDARY_CONSTRAINT_SIGNAL` (A beats every control).
7. otherwise → `NO_SIGNAL` (e.g. dictionary-only ties A: not a veto tier, but blocks SIGNAL).

`BOUNDARY_CONSTRAINT_SIGNAL` requires beating **every** control, so on toy data it is the hardest
branch to reach — by design. `A_vs_D` (dictionary) is intentionally not a standalone veto tier; a
dictionary tie falls through to `NO_SIGNAL` rather than a "dictionary explains" label.

> Note: this harness uses the point-delta / `EPS`-band mechanics for synthetic label coverage. A
> real run additionally requires the prereg's **family-aware bootstrap CIs (lower > 0)** and
> **multi-seed stability** on every delta before any positive; those statistics are not part of
> this synthetic scaffold and are not implemented here.

## Test coverage (all passing)

Run: `python3 experiments/primitive_sequence_recovery/test_track_e_harness.py`

- **Every allowed label is producible** by a toy case; the seven cases map to their
  `expected_label`.
- **Decision precedence** is asserted directly: `A_vs_X` (context) veto beats simultaneous
  scramble/Barnum/etymology ties; scramble beats Barnum+etymology; Barnum beats etymology; a
  dictionary tie yields `NO_SIGNAL`, not `SIGNAL`.
- **`BOUNDARY_CONSTRAINT_SIGNAL` requires beating every control** (all five deltas > eps).
- **Forbidden labels are never emitted** (asserted in `process_case` and in tests); a forbidden
  label string appearing anywhere in a case is rejected.
- **Real-language markers are rejected** — tested inline (a banned marker is deliberately kept out
  of the committed fixtures, which are re-scanned to prove they contain none).
- **Toy flags are mandatory** at both the file and per-case level; contamination flag rejects.
- **Malformed inputs fail loudly**: <3 candidates, duplicate ids, zero/two `context_correct`
  roles, absent `context_correct` id, missing arm, out-of-range / non-numeric / boolean score,
  missing per-candidate score.
- **Blinding utility** hides roles and the correct-answer id behind anonymized `cand_*` ids while
  the key still recovers the answer.
- **No real-run path**: `run_real_pilot()` raises `NotImplementedError`.
- **Determinism**: `process_case` is stable across calls.
- **Guardrails**: runner `NOT_RUN`, manifest `NOT_READY`, no LLM/network/ML libs imported, Stage A
  not imported.

## What this is NOT

- Not a Track E result. No real word, context, candidate set, or boundary has been scored.
- Not a rescue of Track C (dictionary-referent recovery: no robust signal) or D0
  (experiential-weather recovery: `LLM_PILOT_NO_SIGNAL`). Track E tests a *different* claim
  (incremental candidate reweighting) and cannot reinterpret or soften those negatives.
- Not a claim that a real Track E run is approved, ready, or likely to be positive. The prereg's
  default expectation stays `NO_SIGNAL` / `CONTEXT_ONLY_EXPLAINS`.
- Not an adoption of the four-sphere representation. `track_e_varna_sphere_lexicon.json` stays a
  saved candidate artifact; nothing here loads or depends on it.

## Next step (gated; not taken here)

A real Track E run remains gated behind: an approval checklist, a frozen `track_e_config` input
bundle (words / contexts / blind candidate sets / real+scrambled boundaries / Barnum family /
etymology notes), a generator≠scorer blinded LLM protocol, and the family-aware bootstrap-CI +
multi-seed statistics above. None of that is built or authorized here.

---

Track E synthetic harness validates mechanics only. Four-sphere JSON remains a saved candidate artifact, not an adopted Track E input. No real Track E signal has been tested. Track B remains blocked. Structure, not validated meaning.
