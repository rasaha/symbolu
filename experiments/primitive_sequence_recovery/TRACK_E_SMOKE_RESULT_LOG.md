# Track E Smoke Pilot — Result Log (exploratory triage)

**Exploratory triage result. Not validation.** No `ONTOLOGICAL_SIGNAL`, no
`EXPERIENTIAL_WEATHER_SIGNAL`, no Sanskrit privilege. `frozen/manifest.json` remains NOT_READY; the
base smoke manifest stayed `run_enabled:false` / `NOT_APPROVED` throughout (authorization came from
the separate `track_e_smoke_approved_run_config.json`); the psr runner remains NOT_RUN; Stage A
untouched; four-sphere JSON not integrated; **Track B remains BLOCKED.** Per the no-rescue rule,
this result cannot be converted into a positive.

## Run

- **Environment:** RunPod, NVIDIA RTX 6000 Ada (48 GB), CUDA 12.4. Operator-run (Claude did not
  execute it).
- **Design:** flat boundary-constraint, arms A (real) / B (scrambled) / X (context-only) /
  F (etymology-only) / D (dictionary-only) / I (Barnum). 12 cases, **108 packets**.
- **Scorer model:** `mistralai/Mistral-7B-Instruct-v0.3`, temp 0.0, JSON-only, no browsing, no
  carryover. Generator `Qwen/Qwen2.5-7B-Instruct` recorded but **not exercised** (packets are
  pre-authored; only the scorer runs).
- **Coverage:** **12/12 cases scored**, 0 dropped; **malformed rate 0.0093** (1 packet of 108);
  **contamination: none**. The single malformed packet was benign — the scorer echoed a *mistyped*
  packet_id (`…415506` for the real `…415406`), correctly rejected as an unknown packet_id (not a
  content/contamination issue).
- **Full report (pod-generated):** `track_e_smoke_result.json` + `TRACK_E_SMOKE_RESULT.md`
  (committed separately from the pod).

## Result

- **Primary label:** **`CONTEXT_ONLY_EXPLAINS`**

| Arm | MRR | Top-1 |
|---|---|---|
| **X — context-only** | **0.9583** | **0.9167** |
| I — Barnum | 0.8750 | 0.7500 |
| F — etymology-only | 0.8472 | 0.7500 |
| B — scrambled boundary | 0.8056 | 0.7500 |
| **A — real varṇa boundary** | **0.7917** | 0.6667 |
| D — dictionary-only | 0.5236 | 0.2500 |

Incremental deltas (A minus control):

| Delta | Value | Reading |
|---|---|---|
| **`A_vs_X`** (primary) | **−0.1667** | real boundary is **worse** than context alone — primary falsifier fires |
| `A_vs_B` | −0.0139 | real ≈ scrambled (specific mapping adds nothing) |
| `A_vs_F` | −0.0556 | loses to etymology-only |
| `A_vs_I` | −0.0833 | loses to a generic Barnum boundary |
| `A_vs_D` | +0.2681 | beats only the (weakest) dictionary-only floor |

## Per-case pattern (rank of the context-correct candidate; 1 = best of 6)

| case | domain | A | B | X | F | D | I |
|---|---|---|---|---|---|---|---|
| e000 | abstract | **1** | 1 | 2 | 2 | 4 | 2 |
| e001 | abstract | 1 | 1 | 1 | 1 | 2 | 1 |
| e002 | abstract | 1 | 1 | 1 | 1 | 4 | 1 |
| e003 | abstract | 1 | 1 | 1 | 1 | 2 | 1 |
| e004 | abstract | **2** | 1 | 1 | 1 | 1 | 1 |
| e005 | abstract | 1 | 1 | 1 | 1 | 2 | 2 |
| e006 | abstract | 1 | 1 | 1 | 1 | 4 | 1 |
| e007 | concrete | **6** | 6 | 1 | 1 | 3 | 1 |
| e008 | concrete | **3** | 3 | 1 | 3 | 1 | 1 |
| e009 | concrete | **2** | 6 | 1 | 3 | 1 | 1 |
| e010 | famous | 1 | 1 | 1 | 1 | 5 | 2 |
| e011 | famous | 1 | 1 | 1 | 1 | 2 | 1 |

Two things drive the aggregate:

1. **Context-only (X) already solves the task** — X ranks the context-correct candidate #1 in
   **11 of 12 cases** (only e000 X=2). There is almost no headroom for any boundary to add value.
2. **The real boundary is actively harmful exactly where it is most mismatched — the concrete
   controls.** On e007/e008/e009 the real boundary ranks the correct concrete meaning **6, 3, 2**
   while context ranks it **1**. The affliction-vṛtti "boundary" drags the scorer away from
   *river / mountain / house* toward affliction-flavoured candidates. Those three cases account for
   essentially all of A's aggregate deficit; on the abstract/famous cases A is merely
   context-equivalent (mostly rank 1, but no better than X, and worse on e004).

So the negative `A_vs_X` is not noise: it is **context saturating the task** plus **the varṇa
boundary injecting domain-mismatched affliction semantics** that only hurts. Scramble (B) shows the
same concrete collapse (e007 B=6, e009 B=6), confirming the specific mapping is not what matters.

## Honest interpretation

- **`CONTEXT_ONLY_EXPLAINS`:** context-only (X) is the single strongest arm (MRR 0.958). Adding the
  real varṇa boundary does not merely fail to help — it **degrades** selection (A 0.792 < X 0.958).
  Under the pre-registered precedence, the incremental-over-context bar (`A_vs_X > 0`) fails, so no
  other arm can rescue a positive.
- **Every meaningful control also falsifies A:** the real boundary loses to scrambled (B),
  etymology (F), and Barnum (I), and beats only dictionary-only (D), which had the worst MRR by far.
  So the specific varṇa→gloss mapping carried no advantage, and the boundary as implemented (flat
  vṛtti-gloss composition) acts as a **domain-mismatched distractor** that pulls the scorer away
  from the context-correct sense.
- **Consistent with Track C and D0.** Track C found no robust dictionary-referent signal; D0 found
  `LLM_PILOT_NO_SIGNAL` for experiential-weather; Track E now finds the varṇa boundary adds no
  incremental candidate-selection value over context (and is net-negative). Under this
  English-mediated, single-scorer, single-seed smoke setup, there is **no evidence** that the varṇa
  boundary constrains candidate meaning.

## Consequence

- **Triage decision:** a larger pre-registered Track E pilot (D1-style, with bootstrap CIs, seed
  stability, blind authoring, independent replication) is **NOT justified under the current flat
  boundary-constraint design unless the hypothesis and/or design is revised.** A
  `CONTEXT_ONLY_EXPLAINS` at smoke scale is a legitimate, money-saving triage outcome — not a
  pipeline failure. This is **not** `BOUNDARY_CONSTRAINT_SIGNAL`, not validation, and not a positive
  of any kind.
- **No rescue.** This result must not be reinterpreted as positive, and it does not reopen or soften
  Track C, D0, or the Track B block. Any reformulated construct would need its own new
  pre-registration authored before looking at more data — a lead, not a finding.
- **Limits (why even this negative is bounded):** 12 cases only; a single scorer model and single
  decoding seed; English-mediated packets; the boundary text is the flat vṛtti-gloss composition
  (the four-sphere representation remains a parked, unadopted candidate). Smoke size cannot
  establish CIs or stability; the negative is triage-strength, not a definitive refutation.
- **Design caveat surfaced by the run — context ceiling.** X (context-only) MRR 0.958 means the
  contexts are near-ceiling; a boundary has little room to *demonstrate* value even if it had any.
  This was flagged as "too easy context" in the packet preview and is now borne out. A revised
  design would need harder contexts (a lower X baseline) to give any boundary detectable headroom.
  Note this cuts against a rescue, not toward one: even with the ceiling, the boundary is
  net-**negative** (esp. on concretes), so "no headroom" is not the whole story — it is also
  actively misleading where mismatched.

> Track E smoke pilot completed as exploratory triage only. Track B remains blocked. Structure,
> not validated meaning.
