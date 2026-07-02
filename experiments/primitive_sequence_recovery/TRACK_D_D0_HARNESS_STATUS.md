# Track D — D0 Harness Status (synthetic dry-run only) (docs)

**The D0 harness mechanics are built and validated on SYNTHETIC TOY DATA ONLY.** No real pilot
has been run, no real scoring has occurred, no LLM was called, and no claim is made.
`manifest.json` remains NOT_READY; the runner remains NOT_RUN; Stage A untouched; **Track B
remains BLOCKED**; no `EXPERIENTIAL_WEATHER_SIGNAL`, no `ONTOLOGICAL_SIGNAL`, no Sanskrit
privilege. Track C V1 negative stands.

## What was built

- `track_d_d0_harness.py` — pure mechanics around a judge, with **no LLM call and no network**:
  `build_packet` (anonymize + seed-shuffle arms A/B/C and profiles target+I1..I4 into
  `comp_*`/`prof_*` with a hidden key), `synthesize_response` (test helper that models a judge
  *without* an LLM), `validate_response` (structured-JSON validation), `detect_contamination`
  (word-id / banned-reference flags), `score_case` (A-vs-B, A-vs-C, **A-vs-max(I₁..I₄)**, target
  rank), `assign_label` (LLM_PILOT_* only; failing Barnum alone → `NO_SIGNAL`), `process_case`
  (per-case pipeline). `run_real_pilot` **raises** — there is no real-scoring path.
- `toy_fixtures/d0_toy_cases.json` — synthetic toy cases marked `toy_not_for_scoring=true`: no
  real Sanskrit words, no real varṇa decompositions, no real vṛtti table, no Track C corpus
  words (compositions are nonsense tokens; profiles are placeholder descriptors). Includes the
  four required scenarios: A beats all controls; A loses to Barnum; contamination flag; malformed
  JSON.
- `test_track_d_d0_harness.py` — dry-run tests (all pass): anonymization hides arms/words;
  seeded randomization is deterministic yet permutes; Barnum max rule; JSON validation;
  contamination propagation/override; label assignment; malformed handling; the no-real-data
  guard (`build_packet` rejects non-toy input; `run_real_pilot` not implemented).

## Guards (so this cannot become a real run)

- The harness accepts **only** inputs marked `toy_not_for_scoring=True`; anything else raises.
- It imports no LLM/network library; the judge response is passed *in*, never fetched.
- Labels are constrained to `LLM_PILOT_SUGGESTIVE / LLM_PILOT_NO_SIGNAL /
  LLM_PILOT_INCONCLUSIVE / LLM_PILOT_CONTAMINATED`; forbidden labels are asserted against.

## What this is NOT

- **Not** a real D0 pilot, **not** real scoring, **not** evidence of any signal. The toy
  "SUGGESTIVE" result is a mechanics check on fabricated numbers — it means the plumbing works,
  nothing about Sanskrit or varṇas.

## To run the real D0 pilot later

Requires **explicit approval** and an **available LLM judge** (offline/pinned preferred; a hosted
API is exploratory-only with nondeterminism/version-drift reported). A thin adapter would: run
Stage-1 profile generation (dictionary-meaning-only), call the judge on `build_packet` outputs,
pass the returned JSON into `validate_response`/`detect_contamination`/`score_case`, and
aggregate with the D0 robustness plan. In an offline-only environment the honest outcome is
"pilot not run — no LLM available," never a fabricated result. D1 human-blind validation remains
deferred and is the only path to a rigorous Track D verdict.

---

D0 harness synthetic dry-run only. No real scoring has occurred. Track B remains blocked.
Structure, not validated meaning.
