# RunPod runbook — Track D + Track E (route B) on Qwen2.5-7B

Closes the §15.3 caveat in `Bench/bench_out/PHASE4_GPU_FINDINGS.md`
(real-value KV cosine) and answers the §15.4 quality-eval question
without requiring a vLLM `cache_kv` monkey-patch.

**Total expected GPU spend: ~$1.00–$1.50 spot. Total wall time: ~60–75 min including model download.**

All scripts in this runbook were dry-run-tested on CPU before
publication. Pin the dry-run-passing commit before running on GPU.

---

## 1. Pod spec

| Knob | Value | Why |
|---|---|---|
| GPU | A100 80 GB | Fits Qwen2.5-7B FP16 (~14 GB) plus KV cache + headroom |
| RAM | ≥ 32 GB | Tokenizer + datasets + Python overhead |
| Disk | ≥ 50 GB | ~14 GB model weights + ~5 GB caches |
| Image | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` (or any image with CUDA + torch ≥ 2.0) | |
| Pricing | Spot (~$1.20/hr) | This run is interruption-tolerant |

If A100 80 GB isn't available, an A100 40 GB or H100 also work; H100 is faster per dollar but harder to spot.

---

## 2. Setup (5 min, ~$0.10)

```bash
# Inside the pod
cd /workspace
git clone https://github.com/rasaha/symbolu.git
cd symbolu
git checkout claude/safety-state-machine-continued-Lr6oT

# Confirm the dry-run-passing commit is checked out (should be the
# tip of this branch as of the runbook publication).
git log --oneline -1

pip install --upgrade pip
pip install transformers accelerate datasets huggingface_hub

# HF model auth (Qwen models are gated only for some variants; the
# 7B-Instruct usually doesn't require a token, but set one if your
# pod's HF account asks for it).
# huggingface-cli login   # interactive
# OR:
# export HF_TOKEN=hf_xxx

# Sanity: tooling installed
python -c "import torch, transformers; print('torch', torch.__version__, '/ transformers', transformers.__version__); print('CUDA available:', torch.cuda.is_available())"
```

Expected output:
```
torch 2.x.x / transformers 5.x.x
CUDA available: True
```

---

## 3. (Optional, recommended) Dry-run on the pod (1 min, $0.02)

Verifies the scripts work end-to-end on the actual pod environment
before paying for the full Qwen runs. No model download.

```bash
cd /workspace/symbolu/CTM_plus/Bench

python -m ctm_bench.scripts.track_d_capture_kv \
    --dry-run \
    --output-dir bench_out/track_d_dryrun/

python -m ctm_bench.scripts.track_e_quality_eval \
    --dry-run --eval perplexity,mmlu \
    --output-dir bench_out/track_e_dryrun/
```

Both commands should finish in seconds and print a summary table. If
either errors, **stop here** and capture the traceback before paying
for the GPU runs.

---

## 4. Track D — Real-value KV cosine on Qwen2.5-7B (10 min, ~$0.20)

```bash
cd /workspace/symbolu/CTM_plus/Bench

python -m ctm_bench.scripts.track_d_capture_kv \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype float16 \
    --device cuda \
    --layers 0,7,14,21,27 \
    --backends numpy,torch \
    --output-dir bench_out/track_d/ \
    2>&1 | tee bench_out/track_d/run.log
```

**Expected output (the bottom summary block):**

```
============================================================
Track D summary — Qwen/Qwen2.5-7B-Instruct
============================================================
  Prompts:         5
  Layers sampled:  [0, 7, 14, 21, 27]
  Total rows:      50
  Cosine K mean:   0.95-0.97          ← real number, the actual deliverable
  Cosine K min:    0.92-0.96          ← per-layer floor
  Cosine V mean:   0.95-0.97
  Cosine V min:    0.92-0.96

  Architecture-doc target:           >= 0.95
  Synthetic-Gaussian baseline:        ~ 0.964

  PASS: real-value cosine meets architecture-doc target.
```

**Decision tree for Track D outcome:**

* **Mean cosine ≥ 0.95 AND min ≥ 0.93:**
  Real-value cosine matches synthetic-Gaussian. The §15.2 number
  generalises. Proceed to Track E with confidence; the Tier 2 quality
  story is durable.

* **Mean cosine ≥ 0.95 BUT min < 0.93 (one or two layers regress):**
  PolarQuant struggles on those specific layers. Note which layers in
  the JSON; consider a per-layer config sweep (4-bit on the bad
  layers) in a future session. Track E can still proceed but expect
  some quality cost.

* **Mean cosine < 0.95:**
  Real activation distribution is too far from PolarQuant's
  Gaussian-after-rotation assumption. **Pause Track E.** Investigate
  options: larger segment_dim (256), 4-bit angle indices (cuts
  compression ratio by 33% but recovers quality headroom), or
  per-channel scale normalisation as a pre-processing step.

`bench_out/track_d/results.json` has per-(prompt, layer, backend) detail.

---

## 5. Track E — Perplexity + MMLU subset (45-60 min, ~$0.90-$1.20)

Run only if Track D passed (mean cosine ≥ 0.95). If Track D regressed,
revisit the algorithm before paying for Track E.

```bash
cd /workspace/symbolu/CTM_plus/Bench

# Perplexity first (fast, ~5 min) so you get a quick gut-check
python -m ctm_bench.scripts.track_e_quality_eval \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype float16 \
    --device cuda \
    --eval perplexity \
    --turboquant-backend torch \
    --output-dir bench_out/track_e_perplexity/ \
    2>&1 | tee bench_out/track_e_perplexity/run.log

# Then MMLU subset (~40-50 min for 200 questions)
python -m ctm_bench.scripts.track_e_quality_eval \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype float16 \
    --device cuda \
    --eval mmlu \
    --mmlu-num-questions 200 \
    --turboquant-backend torch \
    --output-dir bench_out/track_e_mmlu/ \
    2>&1 | tee bench_out/track_e_mmlu/run.log
```

**Expected perplexity output:**

```
  Perplexity:
    baseline:    8-15 (depends on tokenizer; see baseline ppl)
    turboquant:  baseline × (1.00 - 1.04)
    ratio:       1.00-1.04  (gate ≤ 1.05)
```

**Expected MMLU output:**

```
  MMLU:
    baseline:    65-70%   (Qwen2.5-7B published MMLU is ~74%, subset variance applies)
    turboquant:  baseline ± (0-1)pt
    delta:       within ±0.5pt  → PASS
```

**Decision tree for Track E outcome:**

| Perplexity ratio | MMLU delta | Action |
|---|---|---|
| ≤ 1.02 | ≥ -0.5pt | **GREEN** — proceed to route-A `cache_kv` hook |
| ≤ 1.05 | ≥ -1.0pt | **YELLOW** — proceed cautiously; expect partner question on the gap |
| > 1.05 OR | < -1.0pt | **RED** — pause Tier 2; revisit algorithm config |

---

## 6. (Optional) Run sweep — bigger MMLU subset for partner artefact (~30 min, ~$0.60)

If Track E was green and you want a stronger partner-shareable number,
re-run MMLU with the full 1000-question subset:

```bash
python -m ctm_bench.scripts.track_e_quality_eval \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype float16 \
    --device cuda \
    --eval mmlu \
    --mmlu-num-questions 1000 \
    --output-dir bench_out/track_e_mmlu_1k/ \
    2>&1 | tee bench_out/track_e_mmlu_1k/run.log
```

This brings the MMLU subset accuracy std-error down to ~1.5pt (from
~3pt at 200 questions), making the ±0.5pt gate more meaningful.

---

## 7. Save artefacts back to the repo

```bash
cd /workspace/symbolu

# Stage the bench_out artefacts. They're small (few MB).
git add CTM_plus/Bench/bench_out/track_d/ \
        CTM_plus/Bench/bench_out/track_e_perplexity/ \
        CTM_plus/Bench/bench_out/track_e_mmlu/
# Optionally:
git add CTM_plus/Bench/bench_out/track_e_mmlu_1k/

git commit -m "feat(track-d-e): GPU-measured real-value cosine + quality-eval results"
git push origin claude/safety-state-machine-continued-Lr6oT
```

---

## 8. Update the findings doc

After the GPU run, add a new §17 to `Bench/bench_out/PHASE4_GPU_FINDINGS.md`
with the measured numbers. Template:

```markdown
## §17. Track D + Track E GPU run results (Qwen2.5-7B)

### §17.1 Track D — real-value KV cosine
- Mean cosine K: <number from track_d/results.json>
- Min cosine K:  <number>
- Verdict: <PASS/REGRESSION/PARTIAL per the §5 decision tree>

### §17.2 Track E — perplexity + MMLU
- Wikitext perplexity: baseline <a>, TurboQuant <b>, ratio <c>
- MMLU (200 / 1000 questions): baseline <a>%, TurboQuant <b>%, delta <c>pt
- Verdict: <GREEN/YELLOW/RED per the §5 decision tree>

### §17.3 Implications
- Whether to ship the cache_kv hook (route A) next.
- Whether the §14.2 cosine claim transfers (yes/no/partial).
- Updated partner-pitch language for the combined-stack story.
```

Cost summary for this run: actual spend / wall time.

---

## Troubleshooting

* **`OOM` on model load:** the pod's GPU has < 80 GB. Try `--dtype bfloat16` (still ~14 GB) on a 40 GB card with a smaller `--mmlu-num-questions`. Or rent A100 80 GB.
* **`HF download blocked`:** the pod's network blocks huggingface.co. Either switch pod region or set `HF_ENDPOINT` to a mirror your pod can reach.
* **`MMLU dataset load failed`:** the script falls back to its inline 5-question sample. Track E with 5 questions is not partner-shareable; note this and rerun on a pod with `datasets` access.
* **Perplexity number is `inf`:** the input text exceeded the model's context window or the cache.update() flow broke. Re-run with `--log-level DEBUG`.
* **Track E hangs on first MMLU question:** `--device auto` may have placed weights on CPU. Force `--device cuda`.

---

## What's deferred to a later session

* Route A — actual vLLM `cache_kv` monkey-patch + streaming-bench measurement (the production-path quality cell). Pre-requisite met by green Track E.
* Combined-stack measurement (CTM+ Phase 4 × TurboQuant on the same workload). Pre-requisite met by green route-A.
* CTXL tiering (HBM → CXL → NVMe). Independent work-track; not gated on Track D/E.
* Tier 3 (Triton/CUDA bit-packing kernel). Production realisation of the §14.2 compression-ratio number; not gated on quality.
