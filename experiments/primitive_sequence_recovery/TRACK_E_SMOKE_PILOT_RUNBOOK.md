# Track E — Smoke-Pilot Runbook (docs only)

**Runbook only. Nothing run, scored, or approved.** No experiment, no LLM/scorer call, no network,
no model download, no scoring of the hypothesis. `frozen/manifest.json` remains **NOT_READY** (not
edited here); the psr runner remains **NOT_RUN**; Stage A is untouched; **Track B remains
BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no `EXPERIENTIAL_WEATHER_SIGNAL`, no Sanskrit privilege.
Nothing here reinterprets the Track C or D0 negatives.

**Not a rescue of Track C / D0.** Track C tested dictionary-referent recovery (no robust signal);
D0 tested experiential-weather recovery (`LLM_PILOT_NO_SIGNAL`). Track E tests a *different* claim
— incremental candidate-meaning reweighting — and its result cannot soften or reopen those
negatives. Default expectation stays `NO_SIGNAL` / `CONTEXT_ONLY_EXPLAINS`.

---

## 1. Purpose

This is a **runbook for a small smoke pilot** of the Track E flat boundary-constraint test, so that
— **after a separate explicit approval** — 10–15 real context cases can be run. **It is not
approval to run.** No case, packet, or score here has been executed; the harness real-run path
(`track_e_harness.run_real_pilot`) still raises `NotImplementedError` and is not enabled by this
document. It uses the current flat design (arms **A** real boundary, **B** scrambled boundary,
**X** context-only, **F** etymology-only, **D** dictionary-only, **I** Barnum boundary). The
four-sphere JSON (`track_e_varna_sphere_lexicon.json`) remains a **parked candidate artifact** and
is **not** loaded, referenced, or scored here.

## 2. Smoke-pilot scope

- **10–15 context cases total** (≈6–8 words, 1–2 contexts each).
- This is **plumbing / triage only** — it exists to shake out packetization, blinding, leak scan,
  JSON validity, the scorer contract, and the metric path on real inputs at low cost. It is
  **not final evidence**: the sample is too small for family-aware bootstrap CIs and multi-seed
  stability, so a smoke pilot **cannot** yield `BOUNDARY_CONSTRAINT_SIGNAL` no matter the numbers.
  Its only "positive" outcome is *"plumbing clean → a full pilot is justified."* A negative or
  contaminated smoke result is itself informative and money-saving.

## 3. Input freeze requirements

All inputs must be authored, hashed, and frozen **before** any packet is generated (a `track_e_*`
bundle separate from `frozen/manifest.json`, which is never edited for this). Exact files:

| File | Contents |
|---|---|
| `track_e_smoke_words.jsonl` | smoke word + context list (word_id, surface_word, language, domain, decomp_mode, contamination_risk) |
| `track_e_smoke_contexts.jsonl` | one disambiguating sentence per case (context_id, word_id, context_sentence, context_correct_candidate_id) |
| `track_e_smoke_candidates.jsonl` | candidate meanings + hard negatives (candidate_id, gloss, role; authored_before_varna=true; annotators; agreement) |
| `track_e_smoke_etymology.jsonl` | etymology notes / root priors per word (or null where unavailable) |
| `track_e_smoke_boundaries.jsonl` | boundary decompositions: `boundary_real` (A) and `boundary_scrambled` (B) per word |
| `track_e_smoke_barnum.json` | fixed Barnum boundary family (generic "could-apply-to-anything" boundaries) for arm I |
| `track_e_smoke_seeds.json` | scramble seed(s) + packet-shuffle seed(s) + bootstrap seed(s), all recorded |
| `track_e_smoke_manifest.json` | bundle manifest: `status:"NOT_READY"`, `run_enabled:false`, hashes of all the above |

Freeze rule: once hashed, inputs are immutable for the run; any change requires a re-freeze and a
new approval. The bundle manifest starts and stays `NOT_READY` / `run_enabled:false` until §8 is
signed.

## 4. Recommended case mix

Within the 10–15 cases:
- **6–8 broad abstract / polysemous cases** (the primary set that could carry a signal),
- **3–4 concrete / control cases** where varṇa should be irrelevant (sanity that the method isn't
  "always helps"; these are expected at chance),
- **1–3 famous / high-contamination cases marked exploratory-only** — blinded per §6, reported
  apart, and **excluded from the primary label** (as in the D0 contamination-reduced split).

Report the three subsets separately; the primary read is the abstract set only.

## 5. Candidate authoring protocol

Candidate meanings must be authored **before** anyone sees the varṇa boundary packets (blind to the
decomposition), by independent annotators, with inter-annotator agreement on the context-correct
label recorded; low-agreement cases are excluded. Each case must contain:
- **exactly one context-correct** candidate,
- **≥3 hard negatives** (semantically adjacent; e.g. peace vs relief vs harmony),
- **≥1 dictionary-valid but context-wrong** candidate (correct dictionary sense, wrong here),
- **≥1 Barnum-compatible** candidate (a broad interpretation a generic boundary would favor).

The context sentence must **not** contain the candidate glosses verbatim (no clueing). Candidate
order is shuffled per packet; the context-correct label lives only in the hidden key (§6).

## 6. Packet generation (arms A/B/X/F/D/I)

For each (case, arm), build an anonymized packet containing **only**: the context sentence, the
shuffled candidate interpretations (`cand_*`), and — for arms that carry one — **one** boundary/
control description presented generically as "an internal constraint," never named by arm. Hard
rules, enforced by a **pre-send leak scan** that aborts the packet on any hit:

- **no surface word** where blinding is feasible (mandatory for the famous-word subset),
- **no varṇa names**,
- **no root names** (moha / bhaya / kāma / tṛṣṇā / … — they name the answers),
- **no arm labels** (A/B/X/F/D/I never appear in a packet),
- **candidates shuffled**; roles (`context_correct`/`hard_negative`/…) never shown,
- **hidden answer key separate**: `cand_*`→role, arm identity, and surface word live in a file
  never sent to the scorer.

Arm contents: **A** = real boundary description; **B** = scrambled-assignment boundary (frozen
seed); **X** = no boundary (context + candidates only); **F** = etymology prior only; **D** =
dictionary gloss only (no context); **I** = `max` over the Barnum family. All other packet fields
identical across arms so only the boundary/input varies.

## 7. Model setup

- **generator ≠ scorer**: if generation is needed (candidate profiles / etymology priors), use one
  model to generate and a **different** model to score — never the same model for both;
- **low temperature** (near-deterministic), seeds logged;
- **JSON-only output** validated against a fixed schema; malformed → drop the item, track the rate;
- **no browsing / no tool use** during scoring;
- **no memory / no carryover** between packets (each scored in isolation; no chat history);
- a **contamination-probe** packet per session to check whether the scorer can name the hidden
  word / varṇa / root.

## 8. Run approval gate

The run must **refuse** until every field below is filled and signed. Until then the runner stays
NOT_RUN and `run_enabled:false`.

| Field | Value (fill before approval) |
|---|---|
| Selected generator model | ☐ ________ |
| Selected scorer model (≠ generator) | ☐ ________ |
| Final smoke case list (frozen, hashed) | ☐ ________ |
| Final seeds (scramble / shuffle / bootstrap) | ☐ ________ |
| Boundary representation | ☐ **flat boundary-constraint (current)** — four-sphere NOT used |
| Leak-scan + contamination-probe enabled | ☐ yes ☐ no |
| `run_real_pilot` enabled for this run only | ☐ yes ☐ no |
| Approval date / signature | ☐ ________ |

## 9. Metrics

Per (case, arm), rank the context-correct candidate and compute:
- **MRR**, **Top-1**, **pairwise accuracy** (context-correct vs each hard negative),
- deltas: **A_vs_X**, **A_vs_B**, **A_vs_F**, **A_vs_D**, **A_vs_I**.

**`A_vs_X` (incremental-over-context) remains primary**: if context-only already selects the
candidate, varṇa has added nothing. (Full-pilot statistics — family-aware bootstrap CIs with
lower bound > 0 and ≥5-seed stability — are **not** claimable at smoke-pilot size; report point
deltas and note they are indicative only.)

## 10. Decision labels

Allowed labels only:
- `BOUNDARY_CONSTRAINT_SIGNAL` (not reachable at smoke size — flagged, never asserted here),
- `NO_SIGNAL`,
- `CONTEXT_ONLY_EXPLAINS`,
- `ETYMOLOGY_EXPLAINS`,
- `SCRAMBLE_EQUIVALENT`,
- `BARNUM_BOUNDARY`,
- `INCONCLUSIVE`.

Forbidden: `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking or validation
language. At smoke size the honest outcomes are `INCONCLUSIVE` (too small / arms not separable),
one of the "X/F/B/I explains" falsifiers, `NO_SIGNAL`, or "plumbing clean → full pilot justified."

## 11. Abort / contamination criteria

Abort the run, or flag affected cases `CONTAMINATED` / `INCONCLUSIVE` (never a positive), if:
- the **surface word leaks** into a packet,
- **varṇa / root names leak** into a packet,
- the **model mentions Sanskrit / a varṇa / a root** (contamination probe fires),
- the **JSON-malformed rate is too high** (pre-registered threshold, e.g. > ~15% of packets),
- **context-only (X) solves all cases** → `CONTEXT_ONLY_EXPLAINS`,
- the **Barnum boundary (I) ties or beats real (A)** → `BARNUM_BOUNDARY`,
- the **scrambled boundary (B) ties real (A)** → `SCRAMBLE_EQUIVALENT`.

Any of the last three is a legitimate falsifier, not a pipeline failure.

## 12. Reporting template

```
Track E smoke-pilot report (plumbing/triage; not final evidence)
- primary_label: <one of the §10 allowed labels>            # never BOUNDARY_CONSTRAINT_SIGNAL at smoke size
- n_cases: <abstract> + <concrete/control> + <famous exploratory-only>
- per_arm_means: { A:{mrr,top1,pairwise}, B:{...}, X:{...}, F:{...}, D:{...}, I:{...} }
- deltas: { A_vs_X, A_vs_B, A_vs_F, A_vs_D, A_vs_I }         # point deltas; indicative only
- per_case_rows:
    [ { case_id, domain, target_rank_A, A_vs_X, A_vs_B, A_vs_I, notes } , ... ]
- dominant_failure_class: <CONTEXT_ONLY | SCRAMBLE_EQUIVALENT | BARNUM_BOUNDARY | ETYMOLOGY | mixed>
- contamination_notes: <probe result; any leak-scan hits; malformed-JSON rate>
- full_pilot_justified: <yes / no / needs-fixes>  +  one-line rationale
```

Report abstract, concrete-control, and famous subsets separately; the famous subset is
exploratory-only and does not drive `primary_label` or `full_pilot_justified`.

## 13. Boundary statement

Track E smoke pilot is not yet approved or run. Four-sphere JSON remains a saved candidate artifact, not an adopted Track E input. Track B remains blocked. Structure, not validated meaning.
