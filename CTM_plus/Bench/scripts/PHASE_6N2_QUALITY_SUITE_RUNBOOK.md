# Phase 6N.2 — Extended quality suite (large-N MMLU + HumanEval + LongBench)

Extends Phase 6N (200-Q MMLU, 0.0pt) along the three benches the brief lists as
pending, and adds the diagnostic that matters most: **per-question agreement vs
bf16** (aggregate parity can hide compensating flips).

## Run (on a GPU pod with a FULL-CONTEXT calibrated mask)

```bash
source /workspace/venv-vllm/bin/activate
export HF_HUB_ENABLE_HF_TRANSFER=0 HF_HOME=/workspace/.cache/huggingface
pip install datasets   # if not present (pulls pandas/dateutil; does NOT touch torch — verify after)
python -c "import torch;print(torch.__version__)"   # confirm 2.5.1+cu121

# Large-N MMLU + agreement (the high-value run):
python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py \
    --evals mmlu --num-questions 1000 --cells bf16,protected \
    --out CTM_plus/Bench/bench_out/phase6n2/mmlu_1k.json

# HumanEval — GENERATE-ONLY (writes completions; does NOT execute):
python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py \
    --evals humaneval --num-questions 164 --cells bf16,protected \
    --out CTM_plus/Bench/bench_out/phase6n2/humaneval_gen.json

# LongBench F1 + agreement:
python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py \
    --evals longbench --num-questions 150 --cells bf16,protected \
    --out CTM_plus/Bench/bench_out/phase6n2/longbench.json
```

## The agreement diagnostic (why this beats 6N's 0.0pt)

Aggregate accuracy parity (63.5%=63.5%) can hide *compensating* per-question
flips. This suite reports, per eval:
- **agreement_pct** — fraction where int4's answer == bf16's answer
- (MMLU) flip breakdown: bf16-right/int4-wrong vs bf16-wrong/int4-right + net_flips

The gate now requires **both** |delta| ≤ 1.0pt **AND** agreement ≥ 95%. A run that
scores the same but agrees only 80% FAILs — that is fidelity loss the aggregate
would have hidden. (Demonstrated in the self-test.)

## ⚠ SECURITY — HumanEval execution

pass@1 requires **executing model-generated Python = arbitrary code execution.**
This script **defaults to GENERATE-ONLY** (writes completions to JSON; score them
with the official HumanEval harness in a sandbox). `--execute` runs each
completion in a subprocess with a timeout — that is **NOT a real security
boundary.** Use `--execute` ONLY on a throwaway/sandboxed pod with no
credentials/network you care about. Default path is safe.

## ⚠ MASK precondition

int4 quality is only meaningful with a **mml=8192-calibrated** mask. The mml=1024
shortcut collapses output. Run a hard-needle precheck first (4/4 HIT, COLLAPSE=0)
as in `PHASE_6N_MMLU_QUALITY_RUNBOOK.md` before trusting any score here.

## Verification (CPU, no GPU)

```bash
python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py --selftest        # 5/5
python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py --dry-run \
    --evals mmlu,humaneval,longbench                                            # schema
python CTM_plus/Bench/tests/test_phase6n2_quality_suite.py                      # 15/15
```

## Interpreting results

- **PASS (all evals, agreement ≥95%)** → the quality story extends from "MMLU 200Q
  parity" to "MMLU 1K + HumanEval + LongBench, high per-question agreement" — the
  strongest possible quality claim short of full lm-eval-harness.
- **FAIL on agreement (parity but <95% agree)** → real fidelity loss the aggregate
  hid; investigate (does NOT reopen closed quant tracks — it's a measurement).
- **COLLAPSE_SUSPECTED** → fix the mask first.

Paste the JSON(s) back to fold the numbers into the brief.
