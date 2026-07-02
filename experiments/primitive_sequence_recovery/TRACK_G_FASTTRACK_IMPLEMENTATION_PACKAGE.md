# Track G — Fast-Track Implementation Package (up to dry-run readiness)

**Built up to, but not including, a real model run.** No LLM/scorer call, no network, no scoring in
this environment. `frozen/manifest.json` remains NOT_READY; the base Track G smoke manifest stays
`run_enabled:false` / `NOT_APPROVED`; psr runner NOT_RUN; Stage A untouched; four-sphere JSON
parked/not integrated; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege.
Track G is a **fresh** hypothesis — it does not rescue or reinterpret Tracks C / D0 / E-flat / F.

## Correction applied — A is now varṇa-derived (not hand-authored)

An earlier version of this smoke authored the "real" polarity vector **A per word by hand**, which
meant a run would have tested *researcher-authored word-level polarity*, not *varṇa composition*.
That is fixed:

- **`track_g_varna_polarity_table.json`** (new) — a frozen per-varṇa table mapping each of the 34
  frozen varṇas to **signed contributions over the 10 axes**, authored from the frozen vṛtti glosses
  **blind to the target words' expected poles**, and flagged `researcher_authored_candidate_representation`
  / `unvalidated` / `high_degrees_of_freedom` / `not_ontological_evidence`.
- **`track_g_derive.py`** (new) — deterministic derivation: **A** = sum of the word's varṇas'
  signed contributions across axes, thresholded to a sign (no per-word override; missing table
  entry fails loudly); **R** = sign-flip(A); **B** = seeded-scramble(A).
- **Boundaries regenerated** so A/R/B are the derived vectors; **assignments** no longer author A
  (they record only the pre-registered *evaluation target*: `expected_relation`/`expected_pole`,
  frozen).

This changes Track G from **“researcher-authored word-level polarity smoke”** to
**“researcher-authored varṇa-table-derived polarity smoke.”** The varṇa table is *still*
researcher-authored and high-DOF, so **even a future positive smoke result would remain exploratory,
architecture-bound engineering utility only — never ontology, never validation, never a Track B
unblock.** (Honestly: the derived A vectors mostly do **not** match the pre-registered poles —
e.g. *happy* derives toward contraction/fear/inertia — because the table was authored from glosses,
not tuned to the answers. Default expectation remains `NO_SIGNAL` / `RANDOM_POLARITY_EXPLAINS`.)

## What Track G tests

Whether a **pre-registered, frozen** varṇa **signed-polarity** vector places a word on its target
pole/candidate better than **random-flip (R)**, scrambled (B), Barnum (I), context-only (X), and
dictionary-only (D). `A_vs_R` (does sign matter) and `A_vs_X` (incremental over context) are the two
primary bars. Even a positive is architecture-bound engineering utility, never ontological truth,
and cannot unblock Track B.

## Files created

| File | Role |
|---|---|
| `track_g_harness.py` | Synthetic polarity-boundary mechanics (no LLM): per-arm MRR/Top-1/pairwise, deltas `A_vs_R/X/B/I/D`, frozen-polarity / post-hoc gate, 8 labels. `run_real_pilot()` raises. |
| `toy_fixtures/track_g_toy_cases.json` | 10 synthetic cases (8 labels + malformed + contamination). |
| `test_track_g_harness.py` | Harness tests — all passing. |
| `track_g_smoke_words.jsonl` | 10 smoke cases (concept + hidden dev surface/varṇa). |
| `track_g_smoke_contexts.jsonl` | one disambiguating sentence per case. |
| `track_g_smoke_candidates.jsonl` | target + opposite-pole + hard-negatives + Barnum-compatible per case. |
| `track_g_polarity_axes.json` | the 10 signed axes (frozen; examples illustrative-only). |
| `track_g_varna_polarity_table.json` | **frozen per-varṇa signed axis contributions** (researcher-authored, high-DOF, unvalidated) — the source of the derived A. |
| `track_g_derive.py` | deterministic derivation: A = aggregate(varṇa seq × table); R = flip(A); B = scramble(A). |
| `track_g_polarity_assignments.jsonl` | per-case **frozen** *evaluation target* only (`assigned_before_scoring:true`, `frozen:true`, relation, pole); **does not author A**. |
| `track_g_smoke_boundaries.jsonl` | **derived** real / scrambled / random-flip polarity descriptions + dictionary desc. |
| `test_track_g_derive.py` | derivation tests (A derived, no override, R/B transforms, missing-entry fails loudly) — all passing. |
| `track_g_barnum_polarity.json` | generic Barnum polarity family + arm-I max rule. |
| `track_g_smoke_seeds.json` | fixed seeds (shuffle / scramble / random-flip / packet / Barnum). |
| `track_g_smoke_manifest.json` | `run_enabled:false`, `NOT_APPROVED`, `four_sphere_integrated:false`, `track_b_status:BLOCKED`, hashes. |
| `track_g_smoke_runner.py` | Dry-run packet emission (arms A/R/B/I/X/D) + leak scan + refusal gates. **No model calls.** |
| `test_track_g_smoke_runner.py` | Runner dry-run/gate tests — all passing. |
| `track_g_smoke_approved_run_config.json` | Separate approved-config **template** (base manifest stays gated). |
| `TRACK_G_SMOKE_OPERATOR_RUNBOOK.md` | Exact RunPod commands + abort checks. |

## Design (as required)

- **Arms:** A real frozen polarity · R random polarity flip · B scrambled varṇa polarity · I
  Barnum/generic polarity · X context-only · D dictionary-only.
- **Primary gates:** A must beat R, X, B, I, D; **`A_vs_R` and `A_vs_X` are primary.**
- **Labels (only):** `POLARITY_BOUNDARY_SIGNAL`, `RANDOM_POLARITY_EXPLAINS`, `CONTEXT_ONLY_EXPLAINS`,
  `SCRAMBLE_EQUIVALENT`, `BARNUM_POLARITY`, `NO_SIGNAL`, `INCONCLUSIVE`, `INVALID_POSTHOC_POLARITY`.
- **Frozen polarity:** each case's direction/pole is hashed `assigned_before_scoring:true`; any
  post-hoc change → `INVALID_POSTHOC_POLARITY` (whole run discarded). The **random-flip arm is
  mandatory** (a bundle without R is invalid).
- **Leak-proofing:** scorer packets carry no surface word, varṇa names, root names, arm labels,
  candidate roles, **or the polarity direction** (`expected_pole`/`expected_relation` never sent);
  candidates shuffled, hidden key separate.

## Validation performed

- **`test_track_g_harness.py`** — green: all 8 labels producible; `A_vs_R` + `A_vs_X` both primary;
  random-flip/scramble/Barnum vetoes; post-hoc → `INVALID_POSTHOC_POLARITY`; forbidden/banned/
  malformed rejected; real-run path unavailable.
- **`test_track_g_smoke_runner.py`** — green: dry-run 0 model calls; shuffle; arm randomization;
  hidden-key separation; leak scanner (surface/varṇa/root/role/arm/**polarity-direction**/four-sphere);
  refusal gates (env + config); base manifest stays `run_enabled:false` / `NOT_APPROVED`.
- **Dry-run:** **90 packets** (10 cases × [5 arms + 4 Barnum variants]), leak-clean, arm-randomized,
  no hidden labels, no four-sphere, 0 model calls.

## No real run

No model was called; no `track_g_smoke_outputs.json` exists. A real run requires the separate
approved config (with a filled `scorer_model` + signature), the env token
`TRACK_G_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_G_SMOKE`, a leak-clean dry-run, and frozen polarity with
the random-flip arm — and even then it is exploratory triage, not validation. A model/judge scoring
step for Track G is a separate, later, explicitly-approved addition; this package stops at dry-run
readiness.

---

Track G fast-track package created up to dry-run readiness only. No real Track G smoke pilot has been run. Track B remains blocked. Structure, not validated meaning.
