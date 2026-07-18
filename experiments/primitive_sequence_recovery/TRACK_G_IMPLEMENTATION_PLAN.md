# Track G — Implementation Plan (Polarity Boundary Test, docs only)

**Planning only. Nothing implemented, run, or scored.** No experiment, no LLM/scorer call, no
network, no artifact mutation, no manifest marked READY. `frozen/manifest.json` remains NOT_READY;
psr runner NOT_RUN; Stage A untouched; four-sphere JSON parked/not integrated; **Track B remains
BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. This turns
`PREREG_TRACK_G_POLARITY_BOUNDARY.md` into a build spec; it authorizes **no run and no code**.

**Not a rescue of Tracks C / D0 / E / F.** Those tested dictionary recovery (no signal),
experiential-weather (`LLM_PILOT_NO_SIGNAL`), candidate-boundary selection (`CONTEXT_ONLY_EXPLAINS`),
and inference steering (`CORRECTNESS_DEGRADED`). Track G tests a *different* relation (signed
polarity boundary) and cannot reinterpret or soften those negatives.

**Skeptical note.** Polarity is the most flexible hypothesis in the arc: allowing "direct **or**
contrast" conformance is unfalsifiable unless direction/pole is **frozen before scoring** and a
**random polarity-flip control** fails. The build makes both first-class. Default expectation:
`NO_SIGNAL` / `RANDOM_POLARITY_EXPLAINS` / `CONTEXT_ONLY_EXPLAINS`.

## 1. Purpose

Specify what must be built and frozen before a Track G run: data schemas, the polarity-axis and
frozen-assignment formats, candidate design, controls (incl. random-flip), packetization, metrics,
decision logic, and a synthetic-first harness — under an explicit approval gate. **No run or code is
authorized here.**

## 2. Testing object

Track G tests **signed polarity-boundary utility**: whether a *pre-registered* real varṇa polarity
vector places a word on its **frozen** target pole/candidate better than random-flip, scramble,
Barnum, context-only, and dictionary-only. It is **not**:
- dictionary-referent recovery (Track C),
- experiential-weather recovery (D0),
- flat candidate-boundary selection (Track E),
- answer/inference steering (Track F).

Even a positive is architecture-bound, English/LLM-mediated engineering utility — never ontological
truth, never a Track B unblock.

## 3. Data schemas (docs; NOT frozen artifacts; separate from frozen/manifest.json)

**`track_g_words.jsonl`**
```
{"word_id":"g000","surface_word":"<word or null>","concept":"<english concept>","language":"<sa|en>",
 "dictionary_gloss":"<gloss>","varna_decomposition":["..."],"decomp_mode":"consonant_only|vowel_aware",
 "contamination_risk":"low|med|high","exploratory_only":false,
 "dev_only":["surface_word","varna_decomposition"]}
```

**`track_g_contexts.jsonl`**
```
{"context_id":"g000-c0","word_id":"g000","context_sentence":"<disambiguating sentence>"}
```

**`track_g_candidates.jsonl`**
```
{"case_id":"g000-c0","candidates":[{"candidate_id":"cand_1","gloss":"...","role":"target|
  opposite_pole|hard_negative|barnum_compatible|dict_valid_polarity_wrong"} ...],
 "authored_before_polarity":true,"annotators":["A1","A2"],"agreement":0.NN}
```

**`track_g_polarity_axes.json`** — see §4.
**`track_g_polarity_assignments.jsonl`** — see §5 (the frozen sign/direction per case).

**`track_g_boundaries.jsonl`** (the polarity vectors per case, for arms A/B/R)
```
{"case_id":"g000-c0","polarity_real":{"<axis_id>":+1|-1|0, ...},
 "polarity_scrambled":{...},"scramble_seed":<int>,
 "polarity_random_flip":{...},"random_flip_seed":<int>,
 "dev_varna_axis_contributions":{...}}
```

**`track_g_barnum_polarity.json`**
```
{"schema_version":"1.0","family":{"P1_generic":{"<axis_id>":..}, "P2_...":{...}},
 "arm_I_rule":"max over family","note":"generic could-fit-anything polarity profiles"}
```

**`track_g_seeds.json`**
```
{"schema_version":"1.0","seeds":{"candidate_shuffle":<int>,"scramble":<int>,"random_flip":<int>,
 "packet_order":<int>,"barnum_variant":<int>}}
```

**`track_g_manifest.json`** (separate from frozen/manifest.json; never edit that)
```
{"schema_version":"1.0","bundle_type":"track_g_input_bundle","status":"NOT_READY","run_enabled":false,
 "approval_status":"NOT_APPROVED","representation":"signed_polarity_boundary","four_sphere_integrated":false,
 "track_b_status":"BLOCKED","arms":["A","R","B","I","X","D"],"hashes":{...},"seeds":{...},
 "note":"Track G polarity-boundary input bundle; not validation"}
```

## 4. Polarity-axis schema (`track_g_polarity_axes.json`)

Each axis:
```
{"axis_id":"expansion_contraction","positive_pole":"expansion","negative_pole":"contraction",
 "description":"<what the axis means>","allowed_direct_relation":true,"allowed_contrast_relation":true,
 "examples":["<illustrative-only; MUST NOT be used to tune the test>"],"leak_risk":"low|med|high"}
```
Candidate axes (from the prereg): expansion/contraction, clarity/obscuration, binding/release,
desire/contentment, fear/courage, attachment/freedom, activity/inertia, ascent/descent,
illumination/darkness, integration/fragmentation. The axis list is authored and hashed **before**
scoring; `examples` are flagged illustrative-only and are never used to select or tune assignments.

## 5. Frozen polarity-assignment schema (`track_g_polarity_assignments.jsonl`) — load-bearing

Each case:
```
{"case_id":"g000-c0","word_id":"g000","concept":"<concept>","context_id":"g000-c0",
 "selected_axis_ids":["fear_courage","attachment_freedom"],
 "expected_relation":"direct|contrast|excluded","expected_pole":"<pole on the target axis>",
 "assignment_author":"<annotator>","assigned_before_scoring":true,
 "freeze":{"hash":"<sha256 of this assignment>","frozen_at_commit":"<hash>","agreement":0.NN}}
```
- **`assigned_before_scoring` must be true and hashed before any output is seen.** The sign
  (`expected_pole`) and direction (`expected_relation`) are fixed in advance.
- **`excluded`** cases (ambiguous/low-agreement) are dropped from the primary label, not scored.
- **Any post-hoc change to `selected_axis_ids`, `expected_relation`, or `expected_pole`
  invalidates the case** → `INVALID_POSTHOC_POLARITY` (§10); such a case is discarded, never scored
  as a positive.

## 6. Candidate design

Per case, a pre-registered, blind-authored candidate set (order shuffled per packet; roles in the
hidden key only) with at minimum:
- **target candidate** (the reading on the pre-registered pole),
- **opposite-pole candidate** (the other end of the target axis),
- **≥2 hard negatives** (semantically adjacent, on/near the axis),
- **≥1 Barnum-compatible candidate** (broad reading a generic polarity favors),
- **≥1 dictionary-valid but polarity-wrong candidate** where applicable (right dictionary sense,
  wrong pole).
Authored **before** the polarity assignment; agreement-gated; low-agreement items excluded.

## 7. Controls (arms)

Identical data/architecture; only the polarity input changes:
- **A — real frozen polarity boundary** (`polarity_real`),
- **R — random polarity flip** (`polarity_random_flip`, frozen seed) — **the key control**,
- **B — scrambled varṇa polarity** (`polarity_scrambled`, frozen seed),
- **I — Barnum / generic polarity** (`max` over the Barnum family),
- **X — context-only** (no polarity),
- **D — dictionary-only** (dictionary gloss; no context, no polarity).

## 8. Packetization (scorer-facing, anonymized)

Each packet contains only: the context (for arms that use it), the shuffled candidate glosses
(`cand_*`), and — for arms that carry one — a single polarity description presented generically as
"an internal orientation," never named by arm. Hard rules, enforced by a pre-send leak scan:
- **no surface word** where blinding requires hiding it (esp. famous words),
- **no varṇa names**,
- **no acoustic root names** (moha/bhaya/kāma/…),
- **no arm labels** (A/R/B/I/X/D never appear),
- **no candidate role labels** (target/opposite_pole/hard_negative/… hidden),
- **no hidden polarity direction** (`expected_relation`/`expected_pole` never sent to the scorer),
- **candidates shuffled**; the correct answer + roles + arm identity + polarity direction live only
  in a **separate hidden key** never sent to the scorer.

## 9. Metrics

Rank the pre-registered target candidate under each arm; compute:
- **MRR**, **Top-1**, **pairwise accuracy** (target vs each hard negative),
- deltas: **`A_vs_R`**, **`A_vs_X`**, **`A_vs_B`**, **`A_vs_I`**, **`A_vs_D`**,
- family-aware **bootstrap CIs** (CI lower > 0 for each contrast) and multi-seed stability **if
  sample size permits** (a smoke reports point deltas only, exploratory).

**`A_vs_R` (does sign matter) and `A_vs_X` (incremental over context) are the two primary bars.** A
positive requires A to clear **every** control, not just one.

## 10. Decision logic (allowed labels only)

Precedence (equivalence band `eps`; a smoke uses point deltas):
1. any case with a **post-hoc polarity change** present in the bundle → **`INVALID_POSTHOC_POLARITY`**
   (whole run discarded; never scored as signal).
2. arms not separable / high drop / low agreement → `INCONCLUSIVE`.
3. `A_vs_R` ≤ eps → **`RANDOM_POLARITY_EXPLAINS`** (sign carries no information).
4. `A_vs_X` ≤ eps → **`CONTEXT_ONLY_EXPLAINS`**.
5. `A_vs_B` ≤ eps → **`SCRAMBLE_EQUIVALENT`**.
6. `A_vs_I` ≤ eps → **`BARNUM_POLARITY`**.
7. all of `A_vs_R / A_vs_X / A_vs_B / A_vs_I / A_vs_D` > eps (CI-lower > 0, seed-stable) →
   **`POLARITY_BOUNDARY_SIGNAL`**.
8. otherwise → `NO_SIGNAL`.

**Forbidden:** `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking / validation
language.

## 11. Synthetic-first plan (build + prove before real data)

A toy harness (like `track_e_smoke_runner.py` / `track_f_harness.py`) that accepts **synthetic**
scorer output *in* (no LLM), anonymizes arms/candidates/polarity with a hidden key, computes §9
metrics, and assigns a §10 label. Toy fixtures marked `toy_not_for_scoring=true` + `synthetic_only=
true` (nonsense tokens; no real words) covering:
- **A beats all controls** → `POLARITY_BOUNDARY_SIGNAL`,
- **random flip equals/beats A** → `RANDOM_POLARITY_EXPLAINS`,
- **context-only explains** → `CONTEXT_ONLY_EXPLAINS`,
- **scramble equals/beats A** → `SCRAMBLE_EQUIVALENT`,
- **Barnum equals/beats A** → `BARNUM_POLARITY`,
- **post-hoc polarity mutation** (assignment changed after "scoring" flag) → `INVALID_POSTHOC_POLARITY`,
- **malformed scorer output** → rejected loudly,
- **leakage** (surface/varṇa/root/role/arm/polarity-direction token) → rejected.
Tests assert every allowed label producible; forbidden labels rejected; real-run path unavailable;
toy flags mandatory; **`A_vs_R` and `A_vs_X` both gate the positive**; the random-flip arm is
mandatory (a bundle without R is rejected); malformed/leak fail loudly. **No real scoring.** A
refusal-gated, no-model-call runner (separate approved config, as in Track E/F) emits packets for
external scoring and never calls a model itself.

## 12. Pilot-size recommendation (recommendation only — not frozen, not approved)

- **10–15 smoke cases first** (exploratory triage; point deltas only; cannot validate).
- **20–30 full-pilot cases only if the smoke is clean** (with bootstrap CIs + multi-seed stability).
- A **famous / high-contamination subset**, if used, is separated and exploratory-only (excluded
  from the primary label), as in the D0/E splits.
- Include a **control-domain / off-axis subset** where polarity should be irrelevant (sanity that
  the method isn't "always helps").

## 13. Failure interpretation

- **`RANDOM_POLARITY_EXPLAINS`** (A ≈ R) — the sign carries no information; any polarity "matches."
- **`CONTEXT_ONLY_EXPLAINS`** (A ≈ X) — context already fixes the pole; polarity adds nothing (the
  Track E-flat pattern recurring).
- **`SCRAMBLE_EQUIVALENT`** (A ≈ B) — the specific varṇa→axis mapping adds nothing.
- **`BARNUM_POLARITY`** (A ≈ I) — a generic polarity profile suffices; not varṇa-specific.
- **`NO_SIGNAL`** — A fails to beat controls generally.
- **`INCONCLUSIVE`** — CI includes 0, high drop rate, low agreement, or arms not separable.
- **`INVALID_POSTHOC_POLARITY`** — direction/pole changed after outputs were seen; the run is
  discarded, not a result. Each non-signal is informative triage; none is a rescue or validation.

## 14. Guardrails (hard gates)

- **No real run without separate approval** (env gate + completed checklist + frozen `track_g_config`
  + separate approved run config); the harness rejects non-toy inputs; no model calls in the build
  phase (synthetic only).
- **No post-hoc polarity editing** — assignments frozen/hashed before scoring; any change →
  `INVALID_POSTHOC_POLARITY`.
- **No random-flip omission** — a bundle without the R arm is invalid.
- **No Track B unblocking**; the confirmatory path stays blocked regardless of any Track G outcome.
- **No prior-negative reinterpretation** — Track C / D0 / E-flat / F unchanged; four-sphere stays
  parked (a four-sphere Track G variant is a separate future prereg/config).
- `ONTOLOGICAL_SIGNAL` / `SANSKRIT_PRIVILEGE` asserted against; `frozen/manifest.json` and Stage A
  never touched.

## 15. Boundary statement

Track G implementation planning only. No polarity-boundary signal has been tested. Track B remains blocked. Structure, not validated meaning.
