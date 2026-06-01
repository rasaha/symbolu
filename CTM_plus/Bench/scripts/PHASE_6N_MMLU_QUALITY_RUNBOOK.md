# Phase 6N — MMLU quality bench (the cheapest high-value next step)

> **Why this first:** the VC brief's #1 open de-risker is "quality bench is needle
> + token-agreement only — MMLU/HumanEval/LongBench pending." MMLU is the standard
> academic bar enterprises ask for. This bench closes that gap with **no ncu, no
> multi-GPU, no kernel work** — ~30-45 min on any single A100. It is strictly
> higher-leverage than the bounded throughput-recovery arm (Tier 2/Triton), which
> chases a number that can't reach interactive viability.

## What it does

Runs **bf16 (quality ceiling)** vs **int4_protected** on the SAME held-out MMLU
questions (greedy 4-choice), reports accuracy per cell + the delta, and applies an
acceptance gate: **int4 within ±1.0 pt of bf16 = PASS.** A near-chance int4
accuracy while bf16 is high is flagged **COLLAPSE_SUSPECTED** (a mask problem, not
a method failure).

## Run it (on any GPU pod — no profiling counters needed)

```bash
source /workspace/venv-vllm/bin/activate
export HF_HUB_ENABLE_HF_TRANSFER=0 HF_HOME=/workspace/.cache/huggingface
pip install --no-deps datasets   # if not already present (MMLU loader)

python CTM_plus/Bench/scripts/bench_phase6n_mmlu_quality.py \
    --cells bf16,protected --num-questions 200 \
    --out CTM_plus/Bench/bench_out/phase6n/mmlu_report.json
```

Then paste back `mmlu_report.json` (or its `acceptance` block) and it gets folded
into the findings + brief.

## ⚠ HARD PRECONDITION — valid protect mask

int4 MMLU accuracy is only meaningful with a **correctly calibrated** protect
mask. The mask regenerated at mml=1024 on the throughput pod **collapsed output**
— a run with that mask will (correctly) report `COLLAPSE_SUSPECTED`. Before a real
quality run, either restore the original calibrated mask or recalibrate at full
context:

```bash
python CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py \
    --output /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt \
    --protect-fraction 0.04 --max-model-len 8192      # FULL context, not 1024
```

## Acceptance / decision

- **|bf16 − protected| ≤ 1.0 pt → PASS** → MMLU added to the quality story;
  strengthens the brief from "needle-only" to "needle + token-agreement + MMLU".
- **> 1 pt regression (not collapse) → FAIL** → real quality cost at this protect
  fraction; investigate per-layer sensitivity (does NOT reopen closed tracks).
- **COLLAPSE_SUSPECTED → fix the mask first**, it's not a method result.

## Verification (CPU, no GPU — runs anywhere)

```bash
python CTM_plus/Bench/scripts/bench_phase6n_mmlu_quality.py --selftest   # 7/7
python CTM_plus/Bench/scripts/bench_phase6n_mmlu_quality.py --dry-run    # fake-model schema check
python CTM_plus/Bench/tests/test_phase6n_mmlu_quality.py                 # 13/13
```

The prompt builder, answer parser (conservative — rejects prose like "I don't
know" → 'D'), scorer, and acceptance gate are all pure CPU functions tested above;
the GPU path is a thin driver. So the tool is fully validated before any pod time.

## Roadmap context

Cheapest-first ordering for what needs hardware:
1. **This (MMLU quality)** + restore/recalibrate mask — days, single GPU, highest
   adoption leverage.
2. **Multi-GPU / TP validation** — unlocks 70B (where density moves dollar
   economics most); budget as validation-WITH-debug-risk (pool sharding unverified).
3. **Throughput recovery (Tier 2 / 6F / Triton)** — DEFER: bounded ~0.26-0.30×,
   below the interactive bar; only revisit with an interactive customer + Test 1.
