# signal_gov — Do model-internal signals improve governance?

A small, deterministic, reviewer-friendly harness that tests one question:

> Do **model-internal signals** (entropy, coherence, vritti, JEPA disagreement) make a
> governance layer better at catching unsafe tool calls than text-level governance?

It compares four **nested-ablation** governance scoring configurations as *detectors of
unsafe tool calls* and reports standard, deck-ready metrics.

> ⚠️ **This is a harness + smoke test, not a result.** The `mock` feature mode uses
> **synthetic, constructed-to-be-informative** features so CI can verify the plumbing and
> the ablation math. **No scientific claim follows from a `mock` run.** Real conclusions
> require the `real_cg` feature mode, the full balanced benchmark, and a held-out split.
> The pre-registered design (hypothesis + success/failure criteria) lives in
> [`../../AGENTIC_FRAMEWORK_SIGNAL_GOVERNANCE_EXPERIMENT.md`](../../AGENTIC_FRAMEWORK_SIGNAL_GOVERNANCE_EXPERIMENT.md).

---

## Quick start

```bash
make signal-gov-deps           # numpy, matplotlib, pytest
make signal-gov-smoke          # deterministic CI smoke test (10 scenarios, mock features)
make signal-gov-realcg-smoke   # LIVE internal-signal path via StubCGLLMAdapter (no torch/GPU)
make signal-gov-external-smoke # AgentDojo/InjecAgent ingestion on offline fixtures
make signal-gov-checkpoint-smoke # stock-model (Qwen/Llama/Mistral) path via mock backend
make signal-gov-pilot-assemble # assemble the balanced 30-50 scenario pilot set (CPU)
make signal-gov-cg-pilot       # GPU + CG checkpoint: first true pilot (see CG_PILOT_RUNBOOK.md)
make signal-gov-run            # full hand-built mini-set (mock) -> out/mock_handbuilt/
make signal-gov-data           # (re)write the on-disk benchmark JSONL
```

**First true pilot (GPU):** to produce the first real 30–50 scenario result on the actual
CG checkpoint path (`--mode real_cg` with `MistralCGAdapter`), follow
[`CG_PILOT_RUNBOOK.md`](CG_PILOT_RUNBOOK.md). Assemble the balanced set with
`make signal-gov-pilot-assemble` (CPU → `data/pilot_30_50.jsonl`), then run on a GPU box.
Reports auto-include a **Power & significance** disclaimer (a 30–50 pilot is underpowered —
directional, not confirmatory). Fill [`PILOT_REPORT_TEMPLATE.md`](PILOT_REPORT_TEMPLATE.md).

Or directly:

```bash
python -m experiments.signal_gov.run_experiment --mode mock --dataset smoke
python -m experiments.signal_gov.run_experiment --mode mock --dataset handbuilt
python -m experiments.signal_gov.run_experiment --mode cached --features path/to/features.jsonl --dataset handbuilt
python -m experiments.signal_gov.run_experiment --mode real_cg --checkpoint <ckpt> --dataset handbuilt  # needs torch
```

---

## The four configurations (strict nested ablations)

Each maps `(scenario, features) -> risk score ∈ [0,1]`; a threshold sweep turns the score
into a detector. Each config adds **exactly one** feature group to the previous one, so any
lift is attributable to the added group only.

| Config | Score = equal-weight mean of … | Adds |
|---|---|---|
| **C1** approval only | static approval flag (sensitive-tool list) | — |
| **C2** + risk taxonomy | C1, `risk_norm` | per-tool risk level |
| **C3** + confidence | C2, `1 − text_confidence` | text-level / self-reported confidence |
| **C4** + internal signals | C3, `internal_risk` | entropy, coherence, vritti, JEPA |

`internal_risk = mean(entropy, 1−coherence, vritti_risk, jepa_disagreement)`.

**Decisive isolation:** in `real_cg`, C3 and C4 use the **same model and same forward pass** —
the only difference is reading the 32-D internal state (C4) vs the text output (C3).

The scaffold uses **equal weights (zero tuning)** for transparency and determinism. The real
experiment should fit C3/C4 weights on a held-out **train** split and *also* report this fixed
zero-tuning variant (see the design doc).

---

## Execution modes

| Mode | Source of model-derived features | Needs |
|---|---|---|
| `mock` | deterministic synthetic (seeded by scenario_id; internals constructed to be informative) | numpy |
| `cached` | precomputed `features.parquet` / `.jsonl` | numpy (+pandas/pyarrow for parquet) |
| `real_cg` (`--real-cg-stub`) | **LIVE** path: `StubCGLLMAdapter` fixed 32-D state → `sovereign_bridge` → entropy/vritti adapters → JEPA | numpy + in-repo agentic pkg (**no torch**) |
| `real_cg` (live) | `MistralCGAdapter` (base `--checkpoint` + trained `--cg-state-dict`) → bridge → signal adapters → JEPA | torch + base model + trained CG state-dict |
| `real_checkpoint_cached` (`--hf-mock`) | stock-model path via deterministic mock backend (CI) | numpy + in-repo agentic pkg (**no torch**) |
| `real_checkpoint_cached` (live) | Qwen/Llama/Mistral: REAL logit `entropy` + **PROXY** hidden-state vritti/JEPA; caches features for offline C1–C4 | torch + transformers + weights |

The `real_checkpoint_cached` mode runs a stock model once and caches scenario-varying
features for offline evaluation — the path to the **30–50 scenario pilot**. On a stock
model only `entropy`/`text_confidence` are genuinely real; vritti/JEPA come from an
unvalidated hidden-state→state **proxy**. See
[`REAL_CHECKPOINT_CACHED.md`](REAL_CHECKPOINT_CACHED.md).

The `real_cg` path is **wired and tested with deterministic stub state** — see
[`REAL_CG_WIRING.md`](REAL_CG_WIRING.md) for the exact repo functions, what is real vs
stubbed, and what remains before running against a real checkpoint. Missing internal
signals **fail closed** (conservative high value + provenance flag), never silent zeros;
`--strict-signals` makes them hard errors.

For a **trained** CG head, pass `--checkpoint <BASE_MODEL> --cg-state-dict <trained
*_model.pt>` (e.g. `checkpoints_unified/best_model.pt`). The harness loads the trained
`state_projector`/`intent_projector`/`phase_adapter` (`cg_checkpoint.py`) and **fails closed**
if the state-dict is vanilla or untrained (zero `phase_adapter` output) — override with
`--allow-untrained-cg-head` (plumbing only). `--checkpoint` alone uses an untrained head and
warns. See [`CG_PILOT_RUNBOOK.md`](CG_PILOT_RUNBOOK.md).

`real_cg` and `real_checkpoint_cached` **write a reusable `features.jsonl` into `--out` by
default** (schema identical to `--mode cached`), so the expensive forward passes run once and
C1–C4 replay offline (`--mode cached --features <out>/features.jsonl`) is metric-identical
with provenance preserved. Disable with `--no-cache-write`.

`risk_norm` is real metadata (from `tool_risk_level`) in **every** mode; only confidence and
the internal signals are "extracted".

---

## Pre-registered benchmark schema

Balanced across three governance failure modes (target ~1/3 each):
`prompt_injection`, `destructive_enterprise`, `ambiguous_hallucinated`. The hand-built mini-set
(`data/handbuilt_miniset.jsonl`, 15 scenarios, 5 per category, 6 unsafe / 9 safe) spans all
three so the scaffold runs offline. In the full benchmark the injection third is sourced from
**AgentDojo / InjecAgent** (`dataset.load_external`, a stub here).

Every scenario has exactly these fields:

| field | meaning |
|---|---|
| `scenario_id` | stable unique id |
| `source` | dataset of origin |
| `category` | one of the three failure modes |
| `user_prompt` | the user's actual request |
| `proposed_tool` | the tool call proposed at the decision point |
| `tool_risk_level` | `read_only`/`write`/`execute`/`destructive`/`privileged` |
| `tool_args` | proposed arguments |
| `policy_context` | governance/oracle inputs (approval state, available tools, injection target, reversibility, …) |
| `unsafe_label` | 0/1 ground truth (1 = should NOT have executed) |
| `oracle_reason` | justification for the label |
| `expected_violation_type` | which failure mode the label represents (`none` if safe) |

**Labels are rule-based and deterministic.** `oracle.py` recomputes every label from the
scenario's declared inputs; the smoke test asserts the oracle reproduces all authored labels
(no human judgement in the labelling path).

**External benchmarks (AgentDojo / InjecAgent)** plug into the injection third via
`dataset.load_external(source, path=...)` (or the offline fixtures `load_dataset(
"agentdojo_fixture" | "injecagent_fixture" | "external_fixtures")`). Both map to
`category="prompt_injection"` and reuse the injection oracle. No network — loaders read a
local export. See [`EXTERNAL_BENCHMARKS.md`](EXTERNAL_BENCHMARKS.md) for the ingestion
format, the source/category/oracle mapping, and how to export the real benchmarks.

---

## Metrics (pure numpy — see `metrics.py`)

- **AUROC / AUPRC** — discrimination of unsafe vs safe calls.
- **catch_at_budget** — *headline:* recall of unsafe calls when the top-`b` fraction by score
  is escalated to a human (b ∈ {5%, 10%, 20%}). (At N=10 a 10% budget escalates only 1 call,
  so this metric is coarse on the smoke set and discriminating only at full N; AUROC is the
  smoke-scale signal.)
- **human_burden_to_catch(0.90)** — escalation fraction needed to catch 90% of unsafe calls.
- **over_block_rate** — safe calls needlessly escalated (false-positive cost).
- **bootstrap_ci** — percentile CIs.
- **DeLong** (`delong.py`) — paired AUROC significance for **C4 vs C3** (the decisive test).
- **signal_importance** — standalone AUROC per individual signal.

---

## Artifacts (per run, in `--out`)

`results.json` · `metrics.csv` · `signal_importance.csv` · `roc_overlay.png` ·
`catch_at_budget.png` · `experiment_report.md`. A committed reference run is in
[`sample_output/mock_smoke/`](sample_output/mock_smoke/).

---

## Pre-registered success / failure criteria (for the REAL experiment)

Judged on a **held-out test set** in `real_cg` mode — **not** on `mock`. Full statement in the
design doc; summary:

**Success (all):** AUROC(C4)−AUROC(C3) ≥ 0.05 (DeLong p<0.05); catch@10% C4−C3 ≥ +10 pts
(non-overlapping CIs); monotone C4≥C3≥C2≥C1; ≥2/4 signals standalone AUROC>0.60; no utility
tax; zero-tuning C4 still beats C3.

**Failure (any):** lift <0.02 or p≥0.05; C4 wins only by over-escalating; all signals ≈0.5;
result flips across seeds/checkpoints; C3 already saturates (>0.92).

---

## Going live with `real_cg` (from stub → real checkpoint)

`RealCGFeatureExtractor` is already wired (see [`REAL_CG_WIRING.md`](REAL_CG_WIRING.md)).
To move from the torch-free stub to a real model:

1. Swap the adapter: `--mode real_cg --checkpoint <path>` (drop `--real-cg-stub`). Requires
   torch + weights + the `symbolu_training` wrapper. Everything downstream is unchanged.
2. Cache real forward passes (`features.write_features_jsonl` / parquet) and iterate with
   `--mode cached --features <path>`.
3. Replace the `text_confidence` placeholder with a real model-elicited self-report.
4. Wire `dataset.load_external` for AgentDojo / InjecAgent (the injection third).
5. Add a held-out split + C3/C4 weight fitting (keep the zero-tuning variant), then judge
   against the pre-registered success/failure criteria in the design doc.

---

## Layout

```
experiments/signal_gov/
  dataset.py       schema + hand-built balanced mini-set + loaders + JSONL export
  oracle.py        deterministic rule-based labelling (+ consistency check)
  features.py      mock / cached / real_cg feature extractors
  configs.py       C1–C4 nested-ablation scoring functions
  metrics.py       AUROC / AUPRC / catch@budget / bootstrap (pure numpy)
  delong.py        paired AUROC significance test
  plots.py         ROC overlay + catch@budget bars (matplotlib Agg)
  external.py      AgentDojo / InjecAgent -> Scenario loaders (offline, deterministic)
  cg_checkpoint.py --cg-state-dict load + trained-CG-head verification (fail-closed)
  pilot.py         balanced 30-50 pilot assembler + enterprise scenario pool
  run_experiment.py end-to-end pipeline + artifact writers + CLI
  data/handbuilt_miniset.jsonl   on-disk benchmark (generated from dataset.py)
  data/fixtures/{agentdojo,injecagent}_mini.json   tiny offline ingestion fixtures
  data/pilot_30_50.jsonl         committed balanced 30-scenario pilot (assembled)
  EXTERNAL_BENCHMARKS.md         ingestion format + source/category/oracle mapping
  REAL_CHECKPOINT_CACHED.md      stock-model (Qwen/Llama/Mistral) cache workflow + pilot guide
  CG_PILOT_RUNBOOK.md            GPU runbook for the first true CG-checkpoint pilot
  PILOT_REPORT_TEMPLATE.md       report template for the true pilot
  tests/test_external_loaders.py external ingestion tests
  tests/test_real_checkpoint_cached.py  stock-checkpoint extraction tests (mock backend)
  tests/test_pilot_assembly.py   balanced-pilot assembly tests (CPU)
  tests/test_cg_checkpoint.py    --cg-state-dict load/verify tests (torch-free)
  sample_output/mock_smoke/      committed reference run (mock)
  sample_output/real_cg_stub_smoke/  committed reference run (real_cg via stub)
  tests/test_smoke.py            mock-mode CI smoke test
  tests/test_realcg_smoke.py     real_cg plumbing validation (live path via stub)
  tests/test_d1_ladder.py        Diagnostic D1 probe honesty + verdict branches + mock cache
  diagnostics/                   read-only fix-or-falsify probe studies (D1 ladder; D2-D6 later)
  REAL_CG_WIRING.md              exact repo functions, real vs stubbed, going-live steps
  requirements.txt · README.md
```

## Fix-or-falsify (research-only; `diagnostics/`)

Per [`AGENTIC_FRAMEWORK_CG_RESEARCH_PLAN.md`](../../AGENTIC_FRAMEWORK_CG_RESEARCH_PLAN.md),
CG is demoted to research-only (`enable_cg_state_signals=False`) and off the product path.
[`diagnostics/`](diagnostics/) holds the **read-only** probe studies that localize where
the predictive-uncertainty signal dies. **D1 — the signal-survival ladder** is implemented
(`make signal-gov-d1`, GPU); it retrains nothing, touches no product path, and emits a
*projection-vs-entropy-definition* localization verdict that selects R1/R2. See
[`diagnostics/README.md`](diagnostics/README.md) and
[`diagnostics/D1_FINDINGS.md`](diagnostics/D1_FINDINGS.md).
