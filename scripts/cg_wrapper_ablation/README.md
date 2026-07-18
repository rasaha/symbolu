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
| `C_phase_off` | `use_phase_sync=False` | phase/Bhava signal into adapter zeroed → **static offset only** (the B-vs-C reference) |
| `D_gate0` | `use_guna_bias=False` | adapter_gate forced 0 (**must == base**, K0) |
| `E_csr` | — | **N/A**: CSR is not in the generation path (auto-skipped) |

> **ORIGINAL vs Active-CG.** The as-designed wrapper (`--cg_bootstrap_mode original`, gate −2.0 +
> zero-init adapter) is **structurally inert** — it cannot bootstrap an active gate (proof:
> `BOOTSTRAP_ANALYSIS.md`). The ablation is run against a **trained Active-CG** head
> (`--cg_bootstrap_mode active`, gate −1.0 + N(0,1e-3) adapter; train via `train_cg_active.sh`).
> Active-CG only proves the wrapper *can participate* in generation — it does **not** prove
> usefulness. Usefulness is decided by B > A **and** B > C on objective metrics.

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
- `INVESTIGATE_K0_HIDDEN_COUPLING` — gate=0 (arm D) ≠ base.
- `INERT` — wrapper changes ~nothing (KL<1e-3, flip<0.5%, corr/hidden<1e-2). The ORIGINAL design
  lands here by construction (see BOOTSTRAP_ANALYSIS.md); a *trained Active-CG* head should not.
- `ACTIVE_NO_EFFECT` — wrapper changes logits but no significant task-metric movement vs base.
- `REGRESSION` — B significantly worse than A on a task metric (format/reasoning/constraint).
- `STATIC_OFFSET_NO_CG_DYNAMIC` — B moves metrics but **B ≈ C** (phase/Bhava off): the effect is a
  constant adapter offset, **not** CG dynamics.
- `WEAK_OBJECTIVE_GAIN` — B > A on something, but the B-vs-C picture is ambiguous.
- `CG_DYNAMIC_SIGNAL` — **B > A AND B > C**: the gain needs the phase/Bhava dynamics. Only this
  (and only on objective metrics) justifies continuing CG-wrapper research.

> **The decisive comparison is B vs C, not just B vs A.** A (base), B (full Active-CG), C (phase/
> Bhava dynamics off, static offset only), D (gate=0 ≡ base). If B≈C the wrapper is a constant
> offset; subjective "coherence" examples never count as success.

## What requires GPU

Everything up to and including the metrics parser + kill-criteria logic runs and is tested on
CPU. The **final verdict requires the GPU run** (real Mistral backbone + trained CG head); the
loader fails closed on an untrained head unless `ALLOW_UNTRAINED_CG_HEAD=1`.
