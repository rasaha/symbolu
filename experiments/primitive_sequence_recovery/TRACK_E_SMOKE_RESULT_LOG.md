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
  **contamination: none**.
- **Full report (pod-generated):** `track_e_smoke_result.json` + `TRACK_E_SMOKE_RESULT.md`
  (per-case rows live there).

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

> Track E smoke pilot completed as exploratory triage only. Track B remains blocked. Structure,
> not validated meaning.
