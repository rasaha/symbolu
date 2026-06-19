# CG Wrapper — Generation-Quality Ablation

Falsification-first ablation of the CG wrapper **purely as an LLM generation-quality modifier**.
This track is **separate from governance** — it does not touch trust observables, JEPA
governance, Vritti/Guna/Kosha *governance*, the shadow/parity machinery, or any Phase-2
governance work, and adds no governance code.

> Read `RESEARCH_PLAN.md` (pre-registered) and `TASK1_AUDIT_FINDINGS.md` (how the wrapper
> actually touches logits) first. The honest, expected default outcome is **inert** or
> **no-measurable-effect** unless a *trained* CG head with a non-trivial gate is supplied.

## Layout

```
scripts/cg_wrapper_ablation/
├── RESEARCH_PLAN.md          # pre-registered: arms, metrics, eval sets, seeds, kill criteria
├── TASK1_AUDIT_FINDINGS.md   # stage→tensor→load-bearing map; the 3 audit answers
├── RESULTS_TEMPLATE.md       # filled in after the GPU run (template until then)
├── README.md                 # this file
├── setup.sh                  # RunPod env setup (NO governance deps) + CPU sanity tests
├── smoke_generate.py         # one base-vs-wrapper generation + K0/K1 diagnostics
├── run_ablation.py           # full A/B(/C/D/E) run over the eval sets → runs/.../
├── metrics_report.py         # raw artifacts → summary.json + table + verdict (pure Python)
├── eval_sets/                # pre-registered JSONL eval sets (offline, version-controlled)
│   ├── gsm8k_style.jsonl
│   ├── format_constraints.jsonl
│   └── json_format.jsonl
└── cg_ablation/              # importable library (metrics, arms, runtime, diagnostics, stub)
```

CPU tests live at `tests/test_cg_wrapper_ablation.py` (Tier 1 pure-Python always runs; Tier 2
torch/wrapper tests skip cleanly without torch/GPU/checkpoint).

## Arms

| Arm | Config | Meaning |
|-----|--------|---------|
| `A_base` | raw backbone | base model, no wrapper |
| `B_full` | `ablation=None` | full CG wrapper |
| `C_phase_off` | `use_phase_sync=False` | phase signal into adapter zeroed |
| `D_gate0` | `use_guna_bias=False` | adapter_gate forced 0 (**must == base**, K0) |
| `E_csr` | — | **N/A**: CSR is not in the generation path (auto-skipped) |

## Environment variables (pre-registered)

| Var | Default | Meaning |
|-----|---------|---------|
| `MODEL_ID` | `mistralai/Mistral-7B-v0.3` | base backbone (HF id) |
| `CG_CHECKPOINT` | _(unset)_ | trained CG head state-dict (e.g. `checkpoints_unified/best_model.pt`) |
| `DEVICE` | `auto` | `device_map` |
| `DTYPE` | `bf16` | `bf16` \| `4bit` \| `8bit` |
| `SEEDS` | `0,1,2,3,4` | comma-separated seeds |
| `N_SAMPLES` | _(all)_ | cap examples per set (smoke only) |
| `MAX_NEW_TOKENS` | `256` | generation cap |
| `ALLOW_UNTRAINED_CG_HEAD` | `0` | `1` = run an untrained head (plumbing only; not a signal run) |

## RunPod workflow

```bash
# 1. setup (installs torch/transformers/accelerate/bnb; runs CPU sanity tests)
bash scripts/cg_wrapper_ablation/setup.sh

# 2. smoke: one prompt, base vs wrapper, prints K0/K1 diagnostics
export MODEL_ID=mistralai/Mistral-7B-v0.3
export CG_CHECKPOINT=/workspace/checkpoints_unified/best_model.pt
python scripts/cg_wrapper_ablation/smoke_generate.py "Q: 6 rows of 8 apples. How many? A:"

# 3. full ablation over the pre-registered eval sets (all arms, all seeds)
python scripts/cg_wrapper_ablation/run_ablation.py
#    -> runs/cg_wrapper_ablation/<timestamp>/ {config,raw_generations,per_example_scores,diagnostics}

# 4. parse → summary.json + table + verdict (applies kill criteria K0..K4)
python scripts/cg_wrapper_ablation/metrics_report.py runs/cg_wrapper_ablation/<timestamp>

# 5. transcribe the verdict into RESULTS_TEMPLATE.md and commit
```

## Verdict decisions (from `metrics_report.py`)

- `INVESTIGATE_K0_HIDDEN_COUPLING` — gate=0 ≠ base (the "off" switch doesn't fully turn it off).
- `INERT_STOP` — wrapper changes ~nothing (KL<1e-3, flip<0.5%, corr/hidden<1e-2). Stop.
- `NO_EFFECT_DEPRIORITIZE` — changes logits but no significant task-metric movement.
- `KILL_OR_RETRAIN` — significant regression on a task metric.
- `BENEFIT_RECORDED` — significant improvement, no regression. Only here is benefit claimed.

## What requires GPU

Everything up to and including the metrics parser + kill-criteria logic runs and is tested on
CPU. The **final verdict requires the GPU run** (real Mistral backbone + trained CG head); the
loader fails closed on an untrained head unless `ALLOW_UNTRAINED_CG_HEAD=1`.
