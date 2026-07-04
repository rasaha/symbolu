# Track E — Real Pilot Configuration Proposal (docs only)

**Proposal only. Nothing run, scored, or approved.** No experiment, no LLM/scorer call, no
network, no model download, no scoring of the hypothesis. `frozen/manifest.json` remains
**NOT_READY** (not edited here); the psr runner remains **NOT_RUN**; Stage A is untouched;
**Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no `EXPERIENTIAL_WEATHER_SIGNAL`, no
Sanskrit privilege. Nothing here reinterprets the Track C or D0 negatives.

**Not a rescue of Track C / D0.** Track C tested dictionary-referent recovery (no robust signal);
D0 tested experiential-weather recovery (`LLM_PILOT_NO_SIGNAL`). Track E tests a *different* claim
— incremental candidate-meaning reweighting — and its eventual result cannot soften or reopen
those negatives. Default expectation stays `NO_SIGNAL` / `CONTEXT_ONLY_EXPLAINS`.

---

## 1. Purpose

This document proposes a concrete configuration for a **real** Track E pilot so it can be reviewed
and, if approved separately, frozen and run later. **It is not approval to run.** No word,
context, candidate, boundary, or score in this file has been executed; the harness real-run path
(`track_e_harness.run_real_pilot`) still raises `NotImplementedError` and is not enabled by this
proposal. Running requires a completed §12 approval checklist, a frozen `track_e_config` bundle,
and an explicit go decision — none of which exist yet.

## 2. Current representation

The pilot proposal uses the **current flat boundary-constraint design** already implemented in the
synthetic harness. Six arms, identical data/architecture, only the boundary/inputs change:

- **A — real boundary** (the true varṇa/vṛtti composition of the word),
- **B — scrambled boundary** (same glosses, permuted varṇa→gloss assignment; frozen seed),
- **X — context-only** (no boundary),
- **F — etymology-only** (root/historical prior, no varṇa),
- **D — dictionary-only** (dictionary gloss, no context/varṇa),
- **I — Barnum boundary** (`max` over a fixed generic-boundary family, as in D0).

**The four-sphere JSON remains parked and not integrated.** `track_e_varna_sphere_lexicon.json`
stays a saved candidate artifact; this pilot does **not** load, reference, or score it. Adopting a
four-sphere representation would be a separate proposal with its own controls (a flat-gloss
gatekeeper, four-sphere scramble, sphere-ablation, and a four-sphere Barnum baseline) and its own
approval — out of scope here.

## 3. Pilot size

- **Recommended pilot:** **20–30 polysemous/broad words**, **2 contexts per word** where feasible
  → **40–60 context cases** total.
- **Smoke-pilot option (recommended first):** a smaller **10–15 context cases** (≈6–8 words × 1–2
  contexts) to shake out packetization, blinding, JSON validity, and the scorer contract **before**
  spending on the full pilot. A smoke pilot is a plumbing check, not evidence: it is **not**
  labeled `BOUNDARY_CONSTRAINT_SIGNAL` regardless of numbers (too small for CIs/seed stability).
- Include a small **control-domain** subset of words where varṇa should be irrelevant (sanity that
  the method isn't "always helps").

## 4. Word selection criteria

Choose words with **broad candidate-space ambiguity** — a dictionary that admits several distinct
*kinds* of the same gloss, so context (not the boundary alone) can pick one. Proposed English
seed list (English-mediated by design; see the ceiling note in §11):

`happy, heart, desire, peace, anger, fear, love, duty, power, knowledge, attachment, freedom,
light, darkness, movement, stillness.`

Selection rules:
- each word must support **≥1 context-correct** sense plus **≥3 semantically-adjacent** senses;
- prefer words whose senses are near-neighbors (peace vs relief vs harmony), not unrelated
  homographs (bank), so hard negatives are genuinely hard;
- **famous / high-contamination Sanskrit terms are separated** into an **exploratory-only**
  subset that does **not** drive the primary label (as in the D0 contamination-reduced split); if
  a Sanskrit surface term is used at all, it is blinded per §7 and reported apart from the English
  set.

## 5. Context design

Each (word, context) item must have:
- **one sentence of context** (disambiguating, natural),
- **no clueing by exact candidate wording** — the context sentence must not contain the candidate
  glosses verbatim (else it hands the scorer the answer),
- **exactly one context-correct interpretation** (authored blind to the varṇa decomposition),
- **≥3 hard negatives** (semantically adjacent; e.g. peace vs relief vs harmony),
- **≥1 dictionary-valid but context-wrong** candidate (right dictionary sense, wrong here),
- **≥1 Barnum-compatible** candidate (a broad interpretation a generic boundary would favor).

Freeze rules: candidate sets + context-correct labels authored by independent annotators **before**
attaching varṇa decompositions; inter-annotator agreement on the context-correct label recorded;
low-agreement items excluded; all inputs hashed before any run.

## 6. Candidate examples (illustrative; must not be used to tune the test)

Five example records (candidate order here is exposition only — real packets shuffle; the
`context_correct` label lives in a separate hidden key):

| Word | Candidate interpretations (one context-correct + hard negatives + dict-wrong + Barnum-compatible) |
|---|---|
| **happy** | peaceful contentment · sensory pleasure · ego satisfaction · relief · affection |
| **heart** | physical organ · courage · emotional center · vulnerability · affection |
| **desire** | aspiration · craving · lust · devotion · ambition |
| **peace** | harmony · avoidance · surrender · relief · silence |
| **power** | authority · vitality · domination · capacity · spiritual force |

For each, a specific context sentence selects exactly one as context-correct (e.g. *happy* → "After
the long illness finally passed, she felt happy" cues **relief**, not sensory pleasure), with the
others serving as hard negatives / dictionary-valid-but-wrong / Barnum-compatible roles. The
concrete context→correct mappings are authored separately and blind, then frozen.

## 7. Blinding and packetization

The scorer packet must contain **only** the context sentence, the shuffled candidate
interpretations, and (for the relevant arm) **one** boundary/control description presented
generically as "an internal constraint" — never named by arm. Hard rules, enforced by a pre-send
leak scan that aborts the packet on any hit:

- **no surface word** where blinding is feasible (mandatory for the famous-word subset),
- **no varṇa names**,
- **no root names** (moha/bhaya/kāma/tṛṣṇā/… — these name the answers),
- **no arm labels** (A/B/X/F/D/I never appear; the boundary is described, not labeled),
- **candidates shuffled** per packet; roles (`context_correct` / `hard_negative` / …) never shown;
- hidden keys (`cand_*`→role, arm identity, surface word) live in a separate file never sent to the
  scorer.

## 8. Model / scorer setup

Cross-model, blinded, as in the D0 protocol:
- **generator ≠ scorer**: one model to draft candidate profiles/etymology priors *if generation is
  needed*, a **different** model to score — never the same model for both;
- **low temperature** (near-deterministic decoding), fixed seeds logged;
- **JSON-only outputs** validated against a fixed schema; malformed → item dropped, rate tracked;
- **no browsing / no tool use** during scoring;
- **no memory / no carryover** between packets (each packet scored in isolation; no chat history);
- a **contamination probe** packet per session to detect whether the scorer can name the hidden
  word/varṇa/root.

## 9. Metrics and decision

Per (word, context, arm), rank the context-correct candidate and compute:
- **MRR**, **Top-1**, **pairwise accuracy** (context-correct vs each hard negative),
- deltas: **A_vs_X**, **A_vs_B**, **A_vs_F**, **A_vs_D**, **A_vs_I**,
- **family-aware bootstrap CIs** on every delta — **CI lower bound > 0 required** for a positive,
- **seed stability** across **≥5 seeds** (report the delta/p distribution — the Track C/D0 lesson
  that a single borderline seed is not a result).

**`A_vs_X` (incremental-over-context) is primary.** If context-only already selects the candidate
(`A_vs_X ≤ 0` / CI includes 0), varṇa has added nothing and no positive is possible regardless of
the other arms. A `BOUNDARY_CONSTRAINT_SIGNAL` requires A to beat **X, B, F, D, and I** — every
control, CI-lower > 0, seed-stable — not just the dictionary baseline. Allowed labels only:
`BOUNDARY_CONSTRAINT_SIGNAL`, `NO_SIGNAL`, `CONTEXT_ONLY_EXPLAINS`, `ETYMOLOGY_EXPLAINS`,
`SCRAMBLE_EQUIVALENT`, `BARNUM_BOUNDARY`, `INCONCLUSIVE`. Forbidden: `ONTOLOGICAL_SIGNAL`,
`SANSKRIT_PRIVILEGE`, any Track-B-unblocking or validation language.

## 10. Abort / contamination criteria

Abort the run, or label the affected items `CONTAMINATED` / `INCONCLUSIVE` (never a positive), if:
- the **scorer names Sanskrit / a varṇa / a root** (contamination probe fires),
- the **surface word leaks** into a packet,
- **candidate role labels leak** into a packet,
- the **JSON-malformed rate is too high** (pre-registered threshold, e.g. > ~15% of packets),
- **context-only (X) solves everything** (A_vs_X CI includes 0) → `CONTEXT_ONLY_EXPLAINS`,
- the **Barnum boundary (I) ties or beats real (A)** → `BARNUM_BOUNDARY`,
- the **scrambled boundary (B) ties real (A)** → `SCRAMBLE_EQUIVALENT`.

Any of the last three is a legitimate falsifier, not a failure of the pipeline.

## 11. Expected outcomes

**Default expectation: `NO_SIGNAL` or `CONTEXT_ONLY_EXPLAINS`.** A boundary/reweighting hypothesis
is flexible and prone to trivial "success," so the controls exist to make it refutable. What each
non-signal outcome would mean:

- **`CONTEXT_ONLY_EXPLAINS`** (X ≈ A) — context already selects the candidate; varṇa adds nothing.
  *Most likely outcome.*
- **`ETYMOLOGY_EXPLAINS`** (F ≈ A) — root/historical priors account for selection.
- **`SCRAMBLE_EQUIVALENT`** (B ≈ A) — the specific varṇa→gloss mapping adds nothing.
- **`BARNUM_BOUNDARY`** (I ≥ A) — a generic boundary reweights as well; not varṇa-specific.
- **`NO_SIGNAL`** — A fails to beat the controls generally.
- **`INCONCLUSIVE`** — CI includes 0, high drop rate, low candidate agreement, or arms not
  separable.
- **`BOUNDARY_CONSTRAINT_SIGNAL`** — A beats every control, CI-lower > 0, seed-stable. Even this is
  capped: it would mean only "varṇa adds incremental candidate-selection value **in this
  English-mediated architecture**," **not** ontological truth, and would require rigorous,
  independent replication before any strong claim. English mediation and shared-source ceilings
  apply throughout; Track B stays blocked either way.

## 12. Approval checklist (to be completed before any run)

| Field | Value (fill before approval) |
|---|---|
| Selected model pair (generator ≠ scorer) | ☐ ________ / ________ |
| Final word list (frozen, hashed) | ☐ ________ |
| Final contexts (frozen, hashed) | ☐ ________ |
| Candidate authoring method (blind; annotators; agreement recorded) | ☐ ________ |
| Boundary representation | ☐ **flat boundary-constraint (current)** — four-sphere NOT used |
| Pilot size chosen (smoke 10–15 / full 40–60) | ☐ ________ |
| Seeds (≥5) + bootstrap config | ☐ ________ |
| Leak-scan + contamination-probe enabled | ☐ yes ☐ no |
| `run_real_pilot` explicitly enabled for this run only | ☐ yes ☐ no |
| Approval signature / date | ☐ ________ |

Until every box is filled and signed, the run is **not** approved and the runner stays NOT_RUN.

## 13. Boundary statement

This is a Track E pilot configuration proposal only. No real Track E signal has been tested. Four-sphere JSON remains a saved candidate artifact, not an adopted Track E input. Track B remains blocked. Structure, not validated meaning.
