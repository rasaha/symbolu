# Phase 6N.2 — Extended quality suite (large-N MMLU + HumanEval + LongBench)

> ## ⚠ LongBench BLOCKED (2026-06-02): script-dataset incompatible with datasets>=3.0
> `THUDM/LongBench` is a **script-based dataset** (`LongBench.py`). The pod's
> `datasets` 4.8.5 removed script loading: `RuntimeError: Dataset scripts are no
> longer supported`. NOT fixable by loader flags (`trust_remote_code` is also
> removed). Options for a future LongBench run: (a) a Parquet-converted LongBench
> mirror (e.g. a `*-parquet` community copy or `LongBench-v2`), or (b) a pinned
> `datasets<3.0` in an ISOLATED venv (do NOT downgrade the main venv — breaks the
> rest of the stack). LongBench is CONFIRMATORY; MMLU (below) is the load-bearing
> quality result. The bench's loader now fails LOUDLY with this reason instead of
> crashing. **MMLU + HumanEval(generate-only) paths are unaffected.**


> ## ✅ RESULT — MMLU 1,000 Q (Qwen-7B, A100, 2026-06-01): PERFECT FIDELITY
> | cell | accuracy | | agreement |
> |---|---|---|---|
> | bf16 | 73.9% (739/1000) | | — |
> | int4_protected | 73.9% (739/1000) | | **100% (1000/1000), net_flips=0** |
>
> **0.0 pt delta AND 100% per-question agreement** — int4_protected chose the
> **identical A/B/C/D answer on all 1,000 questions** (bf16-right/int4-wrong = 0,
> bf16-wrong/int4-right = 0). The agreement diagnostic — built specifically to
> catch compensating flips that aggregate parity can hide — found **none.** Gate:
> PASS (≤1pt AND ≥95% agreement → hit 100%). Recalibrated mml=8192 mask; needle
> 4/4, COLLAPSE=0. Artifact: `bench_out/phase6n2/mmlu_1k.json`.
>
> **Honest residual:** 100% agreement on 4-way multiple choice proves int4 does not
> change the *argmax* answer — a very strong fidelity signal — but not that logits
> are bitwise-identical (they are not; it is lossy compression). HumanEval pass@1
> (generative, sandboxed) + LongBench F1 would test free-form generation; both are
> runner-ready below, not yet executed.


Extends Phase 6N (200-Q MMLU, 0.0pt) along the three benches the brief lists as
pending, and adds the diagnostic that matters most: **per-question agreement vs
bf16** (aggregate parity can hide compensating flips).

## ARC-Challenge + TruthfulQA (Parquet-native — load on datasets>=3.0, unlike LongBench)

Added as MMLU-style multiple-choice evals (with the same per-question agreement
diagnostic), but using a GENERIC parser for their variable choice counts (ARC has
3–5; TruthfulQA mc1 varies). Both are Parquet datasets, so they avoid the
script-loader ban that blocks LongBench.

```bash
source /workspace/venv-vllm/bin/activate
export HF_HUB_ENABLE_HF_TRANSFER=0 HF_HOME=/workspace/.cache/huggingface
python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py \
    --evals arc,truthfulqa --num-questions 200 --cells bf16,protected \
    --out CTM_plus/Bench/bench_out/phase6n2/arc_truthfulqa.json
```
Same gate as MMLU: |delta| ≤ 1.0pt AND agreement ≥ 95%. Confirmatory — corroborates
the MMLU 1K @ 100%-agreement result on two more academic benchmarks. Needs the
mml=8192 mask (int4 cell).

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
