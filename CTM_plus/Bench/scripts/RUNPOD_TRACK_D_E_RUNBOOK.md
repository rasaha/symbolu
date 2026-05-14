# RunPod runbook — Track D + Track E (route B) on Qwen2.5-7B

Closes the §15.3 caveat in `Bench/bench_out/PHASE4_GPU_FINDINGS.md`
(real-value KV cosine) and answers the §15.4 quality-eval question
without requiring a vLLM `cache_kv` monkey-patch.

**Total expected GPU spend: ~$1.00–$1.50 spot. Total wall time: ~60–75 min including model download.**

All scripts in this runbook were dry-run-tested on CPU before
publication. Pin the dry-run-passing commit before running on GPU.

> **Result (executed 2026-05-14, ~$0.45 spot, ~25 min wall):**
> Track D passed (cosine K mean 0.9657 on real Qwen2.5-7B
> activations — matches synthetic baseline). Track E perplexity
> **failed catastrophically at the architecture-doc default** (3-bit
> + QJL → 3052× perplexity blow-up). 4-bit also catastrophic (301×).
> 8-bit no-QJL within noise (0.94×, plumbing-correct). MMLU skipped.
> See `bench_out/PHASE4_GPU_FINDINGS.md` §17 for the full writeup.
> **Tier 2's ``cache_kv`` hook is on hold** until the algorithm is
> revisited (§17.7 lists three engineering directions).
>
> Lessons re-applied to this runbook: pre-create output directories
> before `tee`; redirect HF caches to a large volume *before*
> downloading; upgrade torch to ≥ 2.5 to avoid the transformers MoE
> `custom_op` import crash. All folded into the steps below.

---

## 1. Pod spec

| Knob | Value | Why |
|---|---|---|
| GPU | **A100 40 GB** (sufficient) or A100 80 GB / H100 | Qwen2.5-7B FP16 = 14 GB weights + ~7 MB KV cache per question. 40 GB has ample headroom for the default 200-question MMLU. Upgrade to 80 GB only if you bump `--mmlu-num-questions` to 1000+ and want extra margin. |
| RAM | ≥ 32 GB | Tokenizer + datasets + Python overhead |
| Disk | ≥ 50 GB | ~14 GB model weights + ~5 GB caches |
| Image | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` (or any image with CUDA + torch ≥ 2.0) | |
| Pricing | Spot (A100 40 GB ~$0.80/hr, A100 80 GB ~$1.20/hr) | This run is interruption-tolerant |

A100 40 GB is the cost-optimal pick. H100 is fastest per dollar in absolute terms but harder to spot. A6000 48 GB also works.

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
# transformers >= 5.0 is REQUIRED — the scripts use the DynamicCache.layers[i].keys
# 5.x API. The version check will hard-fail in dry-run if the pod ships
# transformers 4.x, so a stale image upgrades automatically here.
pip install --upgrade 'transformers>=5.0' accelerate datasets huggingface_hub

# IMPORTANT: torch >= 2.5 is also required. transformers 5.x's
# integrations/moe.py calls torch.library.custom_op with string-typed
# tensor annotations, and torch < 2.5 fails to resolve those at import
# time (the MoE module imports eagerly even for non-MoE models). If
# the pod ships torch 2.4 or older, upgrade now:
python -c "
import torch
major, minor = torch.__version__.split('.')[:2]
need = (int(major), int(minor)) < (2, 5)
print('torch', torch.__version__, '— upgrade required' if need else '— OK')
"
# If upgrade required:
# pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu121

# Install ctm_bench as an editable package (one-time)
pip install -e CTM_plus/Bench

# HF model auth (Qwen models are gated only for some variants; the
# 7B-Instruct usually doesn't require a token, but set one if your
# pod's HF account asks for it).
# huggingface-cli login   # interactive
# OR:
# export HF_TOKEN=hf_xxx

# Sanity: tooling installed, versions match
python -c "
import torch, transformers
print('torch', torch.__version__, '/ transformers', transformers.__version__)
print('CUDA available:', torch.cuda.is_available())
tmajor, tminor = (int(s) for s in torch.__version__.split('.')[:2])
assert (tmajor, tminor) >= (2, 5), 'torch >= 2.5 required'
assert int(transformers.__version__.split('.')[0]) >= 5, 'transformers >= 5.0 required'
print('Version gate: OK')
"
```

Expected output:
```
torch 2.5.x or later / transformers 5.x.x
CUDA available: True
Version gate: OK
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

# tee opens the log file before the script runs, so create the dir first.
mkdir -p bench_out/track_d bench_out/track_e_perplexity \
         bench_out/track_e_mmlu bench_out/track_e_mmlu_1k

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

## 5b. (Algorithm fix attempt) Per-channel scale (KIVI trick) — re-run Track E perplexity

After the initial Track E result showed catastrophic regression at the
architecture-doc default (§17), per-channel pre-quantisation
normalisation was added to test whether the K-outlier-channel failure
mode can be rescued (§17.7 direction 1). CPU smoke test on synthetic
outlier-channel data showed per-channel minimum cosine rising from
**−0.36** (sign-flipped channels!) to **+0.93** at 3-bit polar. If
the same mechanism rescues real-model perplexity, this is the path
to a partner-shareable combined-stack result.

Re-run cost: ~5 min, ~$0.07 spot per config.

```bash
cd /workspace/symbolu/CTM_plus/Bench
git pull origin claude/safety-state-machine-continued-Lr6oT   # picks up --per-channel-scale flag

# 3-bit + per-channel scale (most ambitious — was 3052× baseline)
mkdir -p /tmp/track_e_perplexity_3bit_pcs
python -m ctm_bench.scripts.track_e_quality_eval \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype float16 --device cuda \
    --eval perplexity \
    --angle-bits 3 \
    --per-channel-scale \
    --turboquant-backend torch \
    --output-dir /tmp/track_e_perplexity_3bit_pcs/ 2>&1 | tee /tmp/track_e_perplexity_3bit_pcs/run.log

# 4-bit + per-channel scale (most likely to be partner-shareable — was 301× baseline)
mkdir -p /tmp/track_e_perplexity_4bit_pcs
python -m ctm_bench.scripts.track_e_quality_eval \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype float16 --device cuda \
    --eval perplexity \
    --angle-bits 4 \
    --per-channel-scale \
    --turboquant-backend torch \
    --output-dir /tmp/track_e_perplexity_4bit_pcs/ 2>&1 | tee /tmp/track_e_perplexity_4bit_pcs/run.log
```

**Interpretation**:

| Result | What it means | Next step |
|---|---|---|
| 4-bit + PCS ratio ≤ 1.05 | KIVI mechanism works; 2.69× compression at quality parity is partner-shareable | Run MMLU 200 to harden the number, then plan cache_kv hook |
| 4-bit + PCS ratio 1.05–1.5 | Mechanism partial; might need sink-token skip on top | Try sink-skip (§17.7 direction 2) next |
| 4-bit + PCS ratio > 2 | Per-channel alone isn't enough | Investigate mixed-bit-depth or pause |
| 3-bit + PCS ratio ≤ 1.10 | Bonus win — 3.58× compression at quality parity | Strongest possible result |

Paste the bottom summary block from both runs. We decide next steps from there.

## 5c. INT4 per-channel KV cache (KIVI-style replacement for PolarQuant)

After both TurboQuant algorithm-fix attempts failed on Qwen2.5-7B
(per-channel scale: 7321× at 4-bit, sink-skip: 220× at 4-bit), the
forward path is to abandon PolarQuant's rotation-based approach
entirely and use the literature-validated alternative: INT4 with
per-channel K + per-token V (KIVI). No rotation. Each channel
quantized independently with its own scale.

**Expected**: perplexity ratio ≤ 1.05 (partner-shareable) at ~3.8×
compression vs FP16. Matches published KIVI results on Qwen-family.

Re-run cost: ~5 min, ~$0.07 spot.

```bash
cd /workspace/symbolu
git pull --ff-only origin claude/safety-state-machine-continued-Lr6oT

cd CTM_plus/Bench
mkdir -p /tmp/track_e_int4

python -m ctm_bench.scripts.track_e_quality_eval \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype float16 --device cuda \
    --eval perplexity \
    --quant int4-per-channel \
    --output-dir /tmp/track_e_int4/ 2>&1 | tee /tmp/track_e_int4/run.log
```

**Decision tree**:

| Ratio | Interpretation | Next step |
|---|---|---|
| ≤ 1.05 | ✅ **Partner-shareable.** ~3.8× compression at quality parity. | Run MMLU 200 to harden. |
| 1.05–1.5 | Helps but not full quality. | Try INT4 + group quantization (see §5d). |
| > 2 | Unexpected — KIVI's published numbers on Qwen-family are within 1.02×. | Investigate; likely an implementation bug. |

## 5d. INT4 per-channel + group quantization (KIVI proper, group_size=32)

Plain `--quant int4-per-channel` uses one scale per (head, head_dim)
channel covering all S sequence positions. The first 4 positions of
context have huge K magnitudes (attention sinks) which inflate the
per-channel scale, hurting reconstruction of the remaining ~280
non-sink positions. Group quantization splits the seq axis into
chunks of 32 and gives each chunk its own scale — sinks contained
in group 0, groups 1+ get appropriate scales for their actual
magnitudes.

This matches KIVI's published configuration on Qwen-family models.

Re-run cost: ~5 min, ~$0.07.

```bash
cd /workspace/symbolu
git pull --ff-only origin claude/safety-state-machine-continued-Lr6oT

cd CTM_plus/Bench
mkdir -p /tmp/track_e_int4_grp32

python -m ctm_bench.scripts.track_e_quality_eval \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype float16 --device cuda \
    --eval perplexity \
    --quant int4-per-channel \
    --k-group-size 32 \
    --v-group-size 32 \
    --output-dir /tmp/track_e_int4_grp32/ 2>&1 | tee /tmp/track_e_int4_grp32/run.log
```

CPU smoke test on synthetic outlier-position data: clean-group cosine
0.98+ (vs plain per-channel 0.85-0.93). Predicts perplexity ratio
close to baseline.

**Decision tree**:

| Ratio | Interpretation |
|---|---|
| ≤ 1.05 | ✅ **Partner-shareable.** ~3.5× compression at quality parity. Ship. |
| 1.05–1.20 | YELLOW — meaningful but with an asterisk. Try `--k-group-size 16` for finer scale. |
| > 1.30 | Group quant alone insufficient. Investigate asymmetric quant or accept INT5. |

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

## Scope note — what Tracks D and E actually compress

Two compression scopes appear in the documentation; they're related
but not identical.

| Where | Compression scope | Cosine number |
|---|---|---|
| `PHASE4_GPU_FINDINGS.md` §14.2 | One vLLM-style 16-token block: `(16, 4, 128)` per K and V | 0.964 (synthetic Gaussian) |
| `PHASE4_GPU_FINDINGS.md` §15.2 | Same as §14.2 — single 16-token block | 0.964–0.965 (cross-impl) |
| **Track D (this runbook)** | Same as §14.2 — script slices a 16-token block out of the prefill before compressing | comparable apples-to-apples to §14.2 |
| **Track E (this runbook)** | The **entire prefill** as one block. K is `(1, num_kv_heads, prefill_len, head_dim)` — typically 50–250 tokens. The kvstore treats the flattened tensor as one input. | should be similar to Track D (PolarQuant is segment-local at 128 elements, oblivious to block boundaries) but *measures a different scope* |

The Track E cosine is implicit (not reported as a number — what's
reported is the downstream MMLU / perplexity impact). If you want a
direct Track-E-scope cosine number for comparison to §14.2, run Track
D with `--block-size 100` and a long prompt.

This distinction matters for partner conversations: §14.2's "3.58×
compression at 0.965 cosine" applies to the production block-aligned
case. Track E's quality numbers apply to whole-prefill compression,
which is what a `cache_kv` hook would actually do at prefill time. A
production deployment with the route-A hook installed (next-session
work) would see the §14.2 per-block compression on decode tokens
specifically.

## What's deferred to a later session

* Route A — actual vLLM `cache_kv` monkey-patch + streaming-bench measurement (the production-path quality cell). Pre-requisite met by green Track E.
* Combined-stack measurement (CTM+ Phase 4 × TurboQuant on the same workload). Pre-requisite met by green route-A.
* CTXL tiering (HBM → CXL → NVMe). Independent work-track; not gated on Track D/E.
* Tier 3 (Triton/CUDA bit-packing kernel). Production realisation of the §14.2 compression-ratio number; not gated on quality.
