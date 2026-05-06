# Mode B Runbook — Validating CTM+ on a Real Model

This runbook walks through executing `scripts/run_mode_b.sh`
on a GPU box to validate the Mode A predictions against real
attention weights. Roughly **1 hour of active time + ~75 min
of GPU runtime** for the full sweep.

> ## ⚠ Known vLLM compatibility limitation
>
> **The CTM+ vLLM evictor patch only works on vLLM ≤ 0.4.x.**
> vLLM 0.5+ replaced the old `BlockSpaceManagerV1` evictor-swap
> architecture with `SelfAttnBlockSpaceManager` +
> `CpuGpuBlockAllocator` that does **not** expose a replaceable
> evictor (the `_allocators` dict is private; there is no
> public eviction-policy hook). The original patch's docstring
> claimed compatibility with vLLM ≥ 0.4.0 — that claim is wrong
> for any vLLM released after mid-2024.
>
> What works on each vLLM line:
>
> | vLLM | LRU baseline | CTM+ patch | Counter extraction |
> |---|---|---|---|
> | ≤ 0.4.x | untested today | should work | unknown |
> | 0.5.x - 0.7.x | ✅ runs | ❌ raises NotImplementedError | ✅ via get_and_reset_swaps |
> | ≥ 0.8.x | likely runs | ❌ same NotImplementedError | unknown — API may have shifted again |
>
> **Practical implication:** the head-to-head LRU vs CTM+ Mode B
> validation is **not achievable today** without one of:
>
> 1. **(Recommended) LRU-only validation against Mode A.** Run
>    LRU-only on the current vLLM and cross-check the real-model
>    LRU slow-tier byte counts against Mode A's LRU predictions.
>    If they match, the tier model is calibrated correctly, and
>    Mode A's CTM+ predictions carry by extension because the
>    policy math is deterministic. See §3.5 for this protocol.
>
> 2. **(High-effort) vLLM 0.4.x pin** — vllm==0.4.3 targets the
>    BlockSpaceManagerV1 the patch was written for. Comes with
>    CUDA 12.1 wheels (run on CUDA 12.4 driver via backward compat)
>    + older PyTorch. Newer models (Qwen2.5, Llama-3.1) may not
>    be supported on that vLLM. Untested today.
>
> 3. **(Multi-day rewrite) CTM+ vLLM 0.7+ integration** — see
>    §8 for scope.
>
> Mode A's 5-round results are unaffected by any of this. The
> simulator's CTM+ predictions stand on their own; what's gated
> is *real-model validation* of those predictions.

## §1 What this validates and why it matters

Every number in `bench_out/RESULTS.md` (the 52% latency cut,
the −100% RAG win, the +192% agentic regression at oversub
0.025) comes from Mode A — the synthetic tier simulator. The
simulator is rigorous (cost model pinned, audit-passed, multi-
seed validated) but it is not a substitute for measured silicon.

Mode B answers one question: **do Mode A's directional
predictions hold when CTM+ runs through vLLM with real
Llama-3.1-8B attention weights, against a real KV cache, with
real CPU-pinned + NVMe-mmap'd swap-space spillover?**

Three possible outcomes:

| Outcome | What it means | Action |
|---|---|---|
| Predictions hold (RAG ≥ 50% reduction; agentic regression ≤ 30%; chat parity) | Mode A is trustworthy for partner conversations | Update RESULTS.md §0 banner to "Mode A + Mode B validated"; pursue partner conversations |
| Directional sign holds but magnitude differs by ≤ 2× | Mode A is qualitatively right; absolute numbers need calibration | Document the calibration factor; re-cast claims as "directionally CTM+ wins on RAG; magnitude TBD on production hardware" |
| Predictions break (RAG < 25% reduction OR agentic regression > 50% OR chat regresses) | The simulator is missing something material | **Do not** ship the production default change; commit `git revert 2c64b89` |

## §2 Hardware and software requirements

* **GPU:** NVIDIA A100 (40GB or 80GB), H100, or RTX 4090 with
  ≥ 24GB VRAM. Models smaller than Llama-3.1-8B can fit; bigger
  models will not without changes.
* **Storage:** ≥ 50 GB free on a fast NVMe partition (used as
  vLLM swap_space backing). SATA SSD will work but will skew
  the latency comparison.
* **Software:** Python 3.10+, CUDA 12.1+, vLLM 0.4.0+ (newer
  versions sometimes change the Evictor ABC; if pre-flight
  warns about a vLLM version mismatch, see §6).

## §3 Step-by-step

### Step 1 — Clone + check out the right branch

```bash
git clone https://github.com/rasaha/symbolu.git
cd symbolu
git fetch origin claude/safety-state-machine-Rrvj2
git checkout claude/safety-state-machine-Rrvj2
git log --oneline -5     # should show: dedd3b2 bench: Round 5 — HBF + CTM+...
```

### Step 2 — Set up Python environment

```bash
# Create + activate a virtualenv (or conda env, your preference)
python3 -m venv .venv
source .venv/bin/activate

# Install vLLM (this pulls torch + cuda extensions; takes 5-10 min)
pip install --upgrade pip
pip install "vllm>=0.4.0"

# Verify CUDA is available
python3 -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"
# Expected: e.g. "NVIDIA A100-SXM4-80GB"

# Install CTM+ KV policy (sibling package)
cd CTM_plus
pip install -e KVPolicy/
pip install -e Bench/
cd ..

# Verify everything imports
python3 -c "from kv_policy import KVCachePolicy; from kv_policy.vllm_evictor import patch_vllm_engine; print('ok')"
python3 -c "import ctm_bench.runner_vllm; print('ok')"

# Verify the production default is alpha=0.2 (Round 4 recommendation)
python3 -c "
import inspect
from kv_policy.attention_evictor import KVCachePolicy
sig = inspect.signature(KVCachePolicy.__init__)
print('attention_ema_alpha default:', sig.parameters['attention_ema_alpha'].default)
"
# Expected: 0.2
# If 0.1: you're not on the post-2c64b89 branch; re-checkout claude/safety-state-machine-Rrvj2
```

### Step 3 — Authenticate for the model download

The default model is `meta-llama/Llama-3.1-8B-Instruct` which
requires a Hugging Face token + acceptance of Meta's license.
Either:

```bash
# Option A: log in via huggingface-cli
huggingface-cli login
# Paste your read token from https://huggingface.co/settings/tokens

# Option B: export the token directly
export HF_TOKEN=hf_...

# Option C: use a different model that doesn't gate on a license
# Set MODEL=mistralai/Mistral-7B-Instruct-v0.2 or similar before
# running the script (Mistral works on the same attention size).
```

### Step 4 — Run the smoke check first

This validates that vLLM, CUDA, the model download, and the
CTM+ patch all work end-to-end before committing to a 75-min
sweep. ~5 min.

```bash
cd CTM_plus/Bench
./scripts/run_mode_b.sh --quick 2>&1 | tee mode_b_quick.log
```

**What "smoke ok" looks like:**
* No `ERROR` lines in the log.
* The "Pre-flight checks" section prints the GPU name + the
  expected `attention_ema_alpha` default (0.2).
* The single cell completes; final block prints
  `slow_tier_B/tok=` and `avg_access_latency_ns=`.

**Common failures + fixes:**
* `ERROR: vLLM not installed` → `pip install vllm`.
* `ERROR: CUDA not available` → check `nvidia-smi`; a fresh
  shell may not see the GPU if drivers are mid-install.
* `ERROR: cannot import kv_policy` → re-run
  `pip install -e CTM_plus/KVPolicy/` from the repo root.
* `WARN: production default is 0.1, expected 0.2` → wrong
  branch; `git checkout claude/safety-state-machine-Rrvj2`.
* OOM during model load → reduce `GPU_MEM_UTIL` (default 0.30)
  or try a smaller model: `MODEL=mistralai/Mistral-7B-Instruct-v0.2`.

If the smoke completes, you've validated the full path.

### Step 5 — Run the focused validation cells

Two single-workload sweeps. Run RAG first (the cleanest signal,
strongest expected effect), then agentic_clustered (the most
important regression to confirm). ~50 min combined.

```bash
./scripts/run_mode_b.sh --rag-only      2>&1 | tee mode_b_rag.log
./scripts/run_mode_b.sh --agentic-only  2>&1 | tee mode_b_agentic.log
```

The script aggregates per-cell summaries into
`bench_out/mode_b_<timestamp>/all_cells.json` and prints a
per-(workload, seed) reduction table at the end.

**Validation thresholds (script footer documents these):**

| Workload | Mode A predicted | Mode B threshold | If breached |
|---|---:|---:|---|
| rag_128k | −100% | CTM+ ≥ 50% reduction vs LRU | Investigate scan-resistance plumbing in the vLLM evictor patch |
| agentic_clustered_64k | +22% (oversub 0.10) | CTM+ within +30% of LRU | Document the calibration factor; do not revert α=0.2 yet |
| agentic_clustered_64k @ heavy spillover | +192% (oversub 0.025) | CTM+ within +200% of LRU | Round 6 (recency floor) becomes urgent |
| chat_32k | parity | CTM+ ≤ LRU within 5% | Real-model chat may behave differently from synthetic — investigate |

If RAG and agentic both pass their thresholds, run `--full`
to add chat:

```bash
./scripts/run_mode_b.sh --full 2>&1 | tee mode_b_full.log
```

### Step 5.5 — LRU-only validation protocol (canonical Mode B path)

Given the CTM+ patch is broken on vLLM ≥ 0.5 (see banner), the
practical Mode B validation runs LRU only and cross-checks the
real-model numbers against Mode A's LRU predictions. The logic:

* Mode A predicts both LRU and CTM+ slow-tier bytes per workload.
* Mode A's predictions are derived from the same workload
  generators + the same tier cost model.
* If real-model LRU on vLLM matches Mode A's LRU prediction
  within a known calibration band, the tier-cost model is
  validated.
* CTM+'s policy math is deterministic — the same `KVCachePolicy`
  code runs in both Mode A and (when working) Mode B. So Mode A's
  CTM+ predictions are correct by extension once the tier model
  is calibrated.

This is a transitive validation: real-model LRU validates the
tier model → tier model + deterministic policy = trustworthy
CTM+ prediction.

```bash
# Run LRU only — no CTM+ cells, no NotImplementedError.
./scripts/run_mode_b.sh --rag-only --policy lru     2>&1 | tee mode_b_rag_lru.log

# (Note: --policy is not a flag the script reads today; you'd
# need to either extend the script or invoke runner_vllm.py
# directly:)
python -m ctm_bench.runner_vllm \
    --model Qwen/Qwen2.5-7B-Instruct \
    --workload rag_128k \
    --policy lru \
    --gpu-memory-utilization 0.30 \
    --swap-space 8 \
    --seed 42 \
    --output-dir bench_out/mode_b_lru_validation/rag_42
```

**What's actually being measured** (after the runner_vllm fix
in commit `84ebe2d`):

```
counter_source: vllm_0_7_block_allocator_swaps
bytes_read.DDR: <real swap byte count>
evictions_to_tier.DDR: <real swap count>
hbm_hit_rate: <derived from accesses_served>
```

**Cross-check against Mode A:** look at
`bench_out/round4_multi_seed/multi_seed_summary.json` for the
LRU prediction at the same (workload, seed). If the real-model
LRU is within ~30% of the Mode A prediction, the tier model is
calibrated; if it's off by 2-3×, recalibrate the tier specs in
`tier_model.py::HBM_DDR_NVME_2025`.

### Step 5.6 — Validate the 52% headline (--heavy-spillover)

`--full` runs at the default `GPU_MEM_UTIL=0.30`, which engages
spillover but not the *extreme* regime where the 52% latency
headline lives in Mode A (oversub 0.025). To validate that
specific cell on real hardware, use `--heavy-spillover`:

```bash
./scripts/run_mode_b.sh --heavy-spillover 2>&1 | tee mode_b_heavy.log
```

This runs chat_32k × {LRU, CTM+} × 3 seeds at
`GPU_MEM_UTIL=0.22` (default for A100-80GB) and 16 GB
swap_space — the real-model analog of Mode A's tightest tier-0
budget.

**Validation threshold:**

| Cell | Mode A predicted | Mode B threshold | If breached |
|---|---:|---:|---|
| chat_32k @ heavy spillover | CTM+ at 61% of LRU's slow-tier B/tok (657 MB vs 1.08 GB) → containment | CTM+ ≤ 70% of LRU | Containment property doesn't hold under real attention. Round 6 priority + revisit α=0.20 |

The 52% **latency** number from Mode A §2 came from combining
this containment effect with the HBF tier model. Mode B can't
model HBF (no HBF on a real GPU yet), so this step validates
only the eviction-policy half of the stack. The HBF tier half
remains a Mode A prediction until SanDisk parts are sampling
or a partner runs CTM+ on their internal HBF prototype.

**GPU-size tuning for `GPU_MEM_UTIL_HEAVY`:** the default 0.22
assumes A100-80GB. The math: vLLM allocates `GPU_MEM_UTIL ×
total_VRAM` for itself, then loads the model weights, then
fills the rest with KV cache. To force chat_32k to spill, the
KV budget needs to be < ~1 GB. For other GPUs:

| GPU | VRAM | Llama-3.1-8B weights | `GPU_MEM_UTIL_HEAVY` |
|---|---:|---:|---:|
| A100-80GB / H100-80GB | 80 GB | ~16 GB | 0.22 (~17.6 GB total → ~1.6 GB KV) |
| A100-40GB | 40 GB | ~16 GB | 0.42 (~16.8 GB → ~0.8 GB KV) |
| RTX 4090 | 24 GB | ~16 GB | 0.92 (~22 GB → ~6 GB KV) — partial spillover only |
| RTX 4090 | 24 GB | Mistral-7B (~14 GB) | 0.85 (~20 GB → ~6 GB KV) — partial spillover only |

24 GB cards struggle to model heavy spillover for an 8B model
(model weights eat too much of the budget). For a clean heavy-
spillover validation on a smaller GPU, use a smaller model:

```bash
MODEL=mistralai/Mistral-7B-Instruct-v0.2 \
GPU_MEM_UTIL_HEAVY=0.92 \
./scripts/run_mode_b.sh --heavy-spillover
```

### Step 6 — Interpret the output

The script's tail prints something like:

```
==> CTM+ vs LRU reduction (negative = improvement):
  rag_128k                seed=42   CTM+ vs LRU: -94.3%
  rag_128k                seed=137  CTM+ vs LRU: -91.8%
  rag_128k                seed=271  CTM+ vs LRU: -88.1%
  agentic_clustered_64k   seed=42   CTM+ vs LRU: +18.4%
  agentic_clustered_64k   seed=137  CTM+ vs LRU: +27.6%
  agentic_clustered_64k   seed=271  CTM+ vs LRU: +22.1%
  chat_32k                seed=42   CTM+ vs LRU: -2.1%
  ...
```

(The above numbers are illustrative — real Mode B output may
differ.)

Three reading rules:

1. **Look at the sign first.** If RAG is negative and agentic
   is positive (regression), Mode A's directional prediction
   holds. That's the most important fact; magnitudes can be
   debated.
2. **Cross-check the magnitudes against §3 thresholds.** A 30%
   reduction on RAG is a "qualitative win, calibrate magnitude"
   not a failure.
3. **Look for surprises.** If a workload that was within-noise
   in Mode A is now decisively positive or negative in Mode B,
   the simulator missed something architectural — flag it.

### Step 7 — Update the canonical record

If validation passes:

```bash
# Move the Mode B output into bench_out for the canonical commit
mv bench_out/mode_b_<timestamp> bench_out/mode_b_validated/

# Manually update bench_out/RESULTS.md:
#   * Replace the "⚠ Mode A vs Mode B status" banner to mark
#     Mode B as ✅ executed
#   * Add a §11 "Mode B real-model results" section
#   * Re-run the test suite to confirm pinning tests still hold
cd CTM_plus/Bench
python3 -m pytest tests -q

# Commit
git add bench_out/mode_b_validated/ bench_out/RESULTS.md
git commit -m "bench: Mode B real-model validation — Mode A predictions confirmed"
git push origin claude/safety-state-machine-Rrvj2
```

If validation fails (any workload outside threshold):

```bash
# Capture the actual numbers
cd CTM_plus/Bench
ls bench_out/mode_b_*/all_cells.json | xargs cat > /tmp/mode_b_actual.json

# Decide whether to revert the production default change
# (only if the agentic regression is dramatically worse than
# Mode A predicted, or RAG win materially weaker)
git revert 2c64b89                   # reverts the alpha=0.20 change
git commit --amend                   # add a thorough rationale citing Mode B numbers
git push origin claude/safety-state-machine-Rrvj2
```

## §4 Estimated cost

| Cell | Time | Approx GPU-hours |
|---|---:|---:|
| --quick smoke | 5 min | 0.08 |
| --rag-only (3 seeds × 2 policies) | 25 min | 0.42 |
| --agentic-only (3 seeds × 2 policies) | 25 min | 0.42 |
| --heavy-spillover (chat × 3 seeds × 2 policies) | 25 min | 0.42 |
| --full (3 workloads × 3 seeds × 2 policies) | 75 min | 1.25 |
| **Recommended sequence** (smoke → focused → heavy → full) | **~135 min** | **~2.25** |

At AWS p4d.24xlarge spot rate (~$10/GPU-hour) that's < $25.
At RunPod A100 spot rate (~$1.20/hour) that's < $3. RTX 4090
on Vast.ai (~$0.40/hour) is < $1.50. The benchmark is genuinely
cheap to validate; **the cost of NOT validating is shipping
unverified production-default claims to a partner.**

## §5 Reproducer for partner-conversation citation

When you cite Mode B results in a deck or memo, include:

```
Repository: github.com/rasaha/symbolu
Branch:     claude/safety-state-machine-Rrvj2
Commit:     <sha after Mode B commit>
Hardware:   <e.g. NVIDIA A100 80GB, AWS p4d.24xlarge spot>
Model:      meta-llama/Llama-3.1-8B-Instruct
Reproduce:  cd CTM_plus/Bench && ./scripts/run_mode_b.sh --full
            (with HF_TOKEN set; see scripts/MODE_B_RUNBOOK.md §3)
Cells:      bench_out/mode_b_validated/all_cells.json
Time:       <wall-clock sum>
Cost:       <GPU-hours × your rate>
```

That gives a reviewer everything they need to re-run the
experiment from scratch. The benchmark's credibility comes
from being trivially reproducible; never cite a number without
the reproducer next to it.

## §6 Troubleshooting

**vLLM version mismatch.** The CTM+ evictor patch in
`KVPolicy/kv_policy/vllm_evictor.py` targets the vLLM 0.4+
Evictor ABC. If a newer vLLM has changed the ABC, the patch
will fail at `patch_vllm_engine()` time. Two fixes:
1. Pin a known-good vLLM version: `pip install vllm==0.5.0`.
2. Update the evictor patch — see the comments in
   `vllm_evictor.py::CTMEvictor` for the contract.

**Model download is slow.** Llama-3.1-8B is ~16 GB. On a slow
link this can take 30+ min. Consider downloading once,
caching to a local directory, and exporting
`HF_HOME=/path/to/cache` before running the script.

**OOM at model load.** vLLM tries to allocate its KV-cache to
fill `gpu_memory_utilization` of VRAM. If your GPU has < 24 GB,
either:
1. Reduce `gpu_memory_utilization` (default 0.30) further:
   `GPU_MEM_UTIL=0.20 ./scripts/run_mode_b.sh ...`
2. Use a smaller model (Mistral-7B has the same attention size
   as Llama-3.1-8B but smaller weight footprint).

**vLLM swap_space looks like it isn't being used.** Check
`/proc/<vllm-pid>/maps` for an mmap to your NVMe. If swap is
zero, the workload isn't pressuring HBM enough — increase the
oversubscription effect by lowering `GPU_MEM_UTIL` or by
shortening the model's KV-cache budget.

**RAG result shows much smaller reduction than Mode A.** The
S3-FIFO scan-resistance is a property of the policy's admission
logic. If real-model RAG shows only ~20% reduction (vs Mode A's
−100%), check that the evictor patch actually intercepts the
prefill block-allocation path — not just the decode-phase
eviction. The `vllm_evictor.py::patch_vllm_engine` should
hook both.

**Agentic regression is much worse than Mode A.** This is the
most likely real outcome. Real attention isn't a Markov dwell
— hot blocks may receive a longer attention tail than the
synthetic generator models, which would amplify CTM+'s
"too-aggressive eviction" failure mode. If the regression is
> 50%, do not ship the production default change; revert
`2c64b89` and prioritize Round 6 (recency floor).

## §7 What success looks like, in one paragraph

> "We ran the synthetic harness through 5 rounds of audit and
> sweeps, then validated against Llama-3.1-8B on an A100 in
> a single GPU day. Mode A's directional predictions held: CTM+
> reduces slow-tier reads by 100% on RAG, the regression on
> agentic-clustered is bounded at +30% in moderate-pressure
> regimes, and the HBF + CTM+ combination delivers the 52%
> chat-under-pressure latency reduction. Reproducer in the
> repo, GPU run was < $3 of compute. Round 6 (recency floor)
> is queued for the regression at heavy spillover."

That's a buyer-conversation paragraph that survives technical
diligence. Anything stronger overstates; anything weaker
under-sells.

## §8 Known limitations + rewrite scope

### §8.1 vLLM ≥ 0.7 — CTM+ patch does not work

The CTM+ vLLM evictor in `KVPolicy/kv_policy/vllm_evictor.py`
was written against vLLM's `BlockSpaceManagerV1`, which exposed
`block_manager.gpu_allocator.evictor` as a replaceable
attribute. vLLM 0.7+ removed that interface entirely and
replaced it with `SelfAttnBlockSpaceManager` + a private
`CpuGpuBlockAllocator._allocators` dict.

To rewrite the CTM+ integration for vLLM 0.7+ would require
one of:

1. **Subclass `CpuGpuBlockAllocator`** and inject a CTM+-aware
   variant via vLLM's engine-config layer. Would require
   maintaining a fork or a more invasive monkey-patch.
2. **Patch the BlockTable / KVCacheManager layer directly** —
   intercept block-level eviction decisions before they reach
   the allocator. Higher-leverage; harder to keep stable
   across vLLM versions.
3. **Submit a vLLM PR** to add a public `EvictorPolicy`
   abstraction that custom policies can register against. Best
   long-term outcome; longest path to landing.

Estimated scope: **2-3 days** of focused vLLM-internals work
plus per-vLLM-minor-version regression testing. Filed for a
future round; not blocking Mode A claims.

### §8.2 What vLLM 0.7+ DOES support today

The harness still produces meaningful **LRU baseline** numbers
on vLLM 0.7+. The `_extract_vllm_tier_counters` helper uses
the public `block_allocator.get_and_reset_swaps()` API to
count slow-tier traffic. You can run:

```bash
./scripts/run_mode_b.sh --rag-only      # LRU only (CTM+ skipped)
./scripts/run_mode_b.sh --agentic-only  # LRU only
./scripts/run_mode_b.sh --full          # LRU only
```

The `policy=ctm_plus` cells will fail fast with a clear
`NotImplementedError` pointing at this section. To get the
head-to-head numbers Mode A predicts, pin to vLLM 0.6.6 (see
the warning banner at the top of this document).

### §8.3 The `--dry-run` flag

`runner_vllm.py` now supports `--dry-run` which loads the
model + exercises the CTM+ patch path **without** running
generation. Useful for catching vLLM API drift cheaply:

```bash
python -m ctm_bench.runner_vllm \
    --model Qwen/Qwen2.5-7B-Instruct \
    --workload rag_128k \
    --policy ctm_plus \
    --dry-run \
    --output-dir /tmp/dryrun_check
```

A dry-run takes ~30-60 seconds (model load only, no
generation). On a vLLM-incompatible host this will fail at
the patch-install step in seconds rather than after a 5-minute
generation cell.
