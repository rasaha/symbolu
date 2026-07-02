# Track E Implementation & Pilot Plan — Varṇa Boundary-Constraint Test (docs only)

**Planning only. Nothing implemented, run, or scored.** No experiment, no LLM call, no results,
no threshold change, no artifact mutation, no manifest marked READY. `manifest.json` remains
NOT_READY; runner remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED**; no
`ONTOLOGICAL_SIGNAL`; no Sanskrit privilege. This turns
`PREREG_TRACK_E_VARNA_BOUNDARY_CONSTRAINT.md` into a build spec; **no run is approved.**

**Not a rescue of Track C / D0.** Those tested dictionary-referent and experiential-weather
recovery (both negative). Track E tests a *different* claim — incremental candidate reweighting
— and cannot reinterpret or soften those negatives.

**Skeptical note.** A boundary/reweighting design is flexible and thus prone to false positives:
the two dominant failure modes are "context already selects the answer" and "any generic boundary
reweights the same way." The controls (esp. context-only X and Barnum I) and the incremental
A>X bar exist to catch these. Default expectation: `NO_SIGNAL` / `CONTEXT_ONLY_EXPLAINS`.

## 1. Purpose

Specify what must be built and frozen before a Track E run: data schemas, candidate design,
controls, packet construction, metrics, decision logic, and a synthetic-first harness — under an
explicit approval gate. It authorizes nothing.

## 2. Testing object

Track E tests **incremental candidate-meaning reweighting by the real varṇa boundary**:
- **NOT** dictionary recovery (Track C),
- **NOT** experiential-weather recovery (D0),
- **but** whether adding the real varṇa boundary `v` improves selection of the *context-correct*
  candidate **over** context-only, etymology-only, dictionary-only, scrambled-varṇa, and a
  generic (Barnum) boundary. The unit is the *incremental* gain over context/etymology; varṇa
  must add something those don't already provide.

## 3. Data schemas (docs; NOT frozen artifacts; separate from frozen/manifest.json)

**`track_e_words.jsonl`**
```
{"word_id":"e000","surface_word":"<word>","language":"<sa|en|...>","source":"<lexicon>",
 "dictionary_gloss":"<candidate-permitting gloss>","varna_decomposition":["..."],
 "decomp_mode":"consonant_only|vowel_aware","contamination_risk":"low|med|high",
 "domain":"abstract|concrete|control"}
```

**`track_e_contexts.jsonl`** (≥1 per word)
```
{"context_id":"e000-c0","word_id":"e000","context_sentence":"<disambiguating sentence>",
 "context_correct_candidate_id":"cand_k"}
```

**`track_e_candidate_meanings.jsonl`**
```
{"word_id":"e000","candidates":[
   {"candidate_id":"cand_1","gloss":"<interpretation>","role":"context_correct|hard_negative|
     dict_valid_context_wrong|barnum_compatible"} ...],
 "authored_before_varna":true,"annotators":["A1","A2"],"agreement":0.72}
```

**`track_e_etymology_notes.jsonl`**
```
{"word_id":"e000","root":"<dhatu/root or null>","note":"<historical/root prior or null>",
 "prior_over_candidates":{"cand_1":0.0} }   // optional; null if unavailable
```

**`track_e_varna_boundaries.jsonl`**
```
{"word_id":"e000","boundary_real":"<v: composed vṛtti-gloss boundary description>",
 "boundary_scrambled":"<v': scrambled-assignment boundary>","scramble_seed":<int>}
```

**`track_e_barnum_boundaries.json`** (generic boundaries, fixed family)
```
{"schema_version":"1.0","family":{"B1_generic_emotional":"...","B2_affliction":"...",
 "B3_spiritual":"...","B4_inner_growth":"..."},"note":"generic 'could-apply-to-anything' boundaries"}
```

**`track_e_manifest.json`** (separate from frozen/manifest.json; never edit that)
```
{"schema_version":"1.0","status":"NOT_READY","hashes":{...},"seeds":{...},
 "run_enabled":false,"note":"Track E input bundle; boundary-constraint test; not validation"}
```

## 4. Candidate-meaning design

Per (word, context) build a candidate set with, at minimum:
- exactly **one context-correct** candidate,
- **≥3 plausible hard negatives** (semantically adjacent; e.g. peace vs relief vs harmony),
- **≥1 dictionary-valid but context-wrong** candidate (right dictionary sense, wrong here),
- **≥1 Barnum-compatible** candidate (a broad interpretation a generic boundary would favor),
- **no candidate authored after seeing the varṇa decomposition** (blind authoring; agreement-
  gated; low-agreement items excluded).
Candidate order is shuffled per packet; the context-correct label lives only in a separate key.

## 5. Controls

Identical data + architecture; only the boundary/inputs change:
- **A — real varṇa boundary** (`boundary_real`),
- **B — scrambled varṇa boundary** (`boundary_scrambled`, frozen seed),
- **X — context-only** (no boundary),
- **F — etymology-only** (etymology prior, no varṇa),
- **D — dictionary-only** (dictionary gloss, no context/varṇa),
- **I — Barnum/generic boundary** (`max` over the fixed Barnum family, as in D0).

## 6. Scoring packets (blinded, anonymized)

Per (word, context, arm) the scorer sees:
- the **context sentence**,
- the shuffled **candidate interpretations** (`cand_*`, no role labels),
- **one boundary description** appropriate to the arm (real / scrambled / none / etymology /
  dictionary / Barnum) — presented generically as "an internal constraint," never named by arm,
- **no surface word** where blinding requires it (esp. famous words), and **no arm label**.
Hidden keys (`cand_*→role`, arm identity, surface word) live in a separate file never sent to the
scorer. Deterministic seed logging; a pre-send scan asserts no arm/role/word leaks into a packet.
(For an LLM scorer, the D0 protocol applies: generator≠scorer, JSON-only, contamination probe.)

## 7. Metrics

Rank the context-correct candidate under each arm; compute:
- **MRR**, **Top-1**, **pairwise accuracy** (context-correct vs each hard negative),
- deltas: **A_vs_X**, **A_vs_B**, **A_vs_F**, **A_vs_D**, **A_vs_I**,
- **family-aware bootstrap CIs** on every delta (CI lower > 0 required for a positive),
- **seed stability** (≥5 seeds; report the p / delta distribution — the Track C/D0 lesson).
The **A_vs_X** (incremental-over-context) delta is primary: if ≤ 0, varṇa adds nothing.

## 8. Decision labels

Allowed only:
- `BOUNDARY_CONSTRAINT_SIGNAL` — A beats X, B, F, D, **and** I (all CI-lower > 0, seed-stable,
  hard-negatives ruled out).
- `NO_SIGNAL`
- `CONTEXT_ONLY_EXPLAINS`
- `ETYMOLOGY_EXPLAINS`
- `SCRAMBLE_EQUIVALENT`
- `BARNUM_BOUNDARY`
- `INCONCLUSIVE`

Forbidden: `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking / validation
language. Even a positive is "incremental utility in this architecture," never ontological truth.

## 9. Synthetic-first harness plan (build + prove before real data)

A toy harness (like `track_d_d0_harness.py`) that accepts a scorer response *in* (no LLM),
anonymizes arms/candidates with a hidden key, computes the §7 metrics, and assigns a §8 label.
Toy fixtures marked `toy_not_for_scoring=true` (nonsense tokens; no real words) covering:
- **A beats all controls** → `BOUNDARY_CONSTRAINT_SIGNAL`,
- **context-only explains** (X ≈ A) → `CONTEXT_ONLY_EXPLAINS`,
- **etymology explains** (F ≈ A) → `ETYMOLOGY_EXPLAINS`,
- **scramble equals real** (B ≈ A) → `SCRAMBLE_EQUIVALENT`,
- **Barnum boundary wins** (I ≥ A) → `BARNUM_BOUNDARY`,
- **malformed scorer output** → `INCONCLUSIVE`,
- **contamination flag** → contamination handling (probe/scan).
Tests assert anonymization hides arms/roles/words, the no-real-data guard, deterministic
seeding, label assignment, and that forbidden labels are never emitted. **No real scoring.**

## 10. Guardrails (hard gates)

- **No real-run path** until explicit approval (env gate + completed approval checklist), and a
  frozen `track_e_config` bundle; the harness rejects non-toy inputs.
- **No model calls in this phase** (synthetic only).
- **No result labels beyond synthetic fixtures.**
- **No Track B changes; no Stage A changes; no `frozen/manifest.json` edit.**
- Labels constrained to the §8 set; `ONTOLOGICAL_SIGNAL`/`SANSKRIT_PRIVILEGE` asserted against.

## 11. Pilot-size recommendation (recommendation only — not frozen)

- **20–30 broad/polysemous words**; **2–3 contexts per word** if feasible.
- Mixed **abstract / concrete / control** domains; include a control domain where varṇa should be
  irrelevant (sanity that the method isn't "always helps").
- **Famous-word contamination subset separated** and exploratory-only (does not drive the label),
  as in the D0 contamination-reduced split.

## 12. Failure interpretation

- **`CONTEXT_ONLY_EXPLAINS`** — X ≈ A: context already selects the candidate; varṇa adds nothing
  (the most likely outcome).
- **`ETYMOLOGY_EXPLAINS`** — F ≈ A: root priors account for selection.
- **`SCRAMBLE_EQUIVALENT`** — B ≈ A: the specific varṇa mapping adds nothing.
- **`BARNUM_BOUNDARY`** — I ≥ A: a generic boundary reweights as well; not varṇa-specific.
- **`NO_SIGNAL`** — A fails to beat controls generally.
- **`INCONCLUSIVE`** — CI includes 0, high drop rate, low candidate agreement, or controls not
  separable.
Each is informative triage; none is a rescue, and none may be reported as validation.

## 13. Boundary statement

Track E tests incremental varṇa boundary constraint over candidate meanings. It does not rescue
Track C or D0. Track B remains blocked. Structure, not validated meaning.
