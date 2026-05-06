# Mode B on vLLM 0.4 — Validation Roadmap #2

**Status:** code + runbook complete (this session).
**Execution:** requires GPU; deferred until you have RunPod or
similar.
**Audience:** internal. The partner-facing version is the
`PARTNER_VALIDATION_NOTE.md` §4 Path B specification.

This runbook walks through executing a real-model CTM+ vs LRU
comparison on a **vLLM 0.4.x pinned** environment. It is
distinct from `MODE_B_RUNBOOK.md`:

| | `MODE_B_RUNBOOK.md` | this runbook (#2) |
|---|---|---|
| vLLM version | any | pinned 0.4.x |
| Policies that run | LRU only on 0.5+ | both LRU and CTM+ |
| Status | harness validated; CTM+ NOT exercised | CTM+ actually runs through the patch |
| Defensible claim | timing/harness | calibration on a historical stack |
| Production relevance | direct | indirect (vLLM 0.4 is no longer in production use) |

The point of #2 is to **eliminate "we never ran CTM+ on a real
model" as a claim risk** — at the cost of running on a vLLM
version partners don't deploy. Modern-stack validation
(roadmap #3 or Path B) remains gated on the allocator-architecture
rewrite or a partner-specific serving harness.

## §1 Scope of evidence #2 produces

**It does:**

* Run CTM+ end-to-end through vLLM with real attention weights
  and real KV-cache eviction events.
* Produce real-model swap-byte measurements (the
  `block_allocator.swap_in/out` counters that vLLM 0.4.x exposes).
* Settle the question "does CTM+'s scoring math hold up under
  real attention" cleanly — not as a yes/no, but with measured
  CTM+ vs LRU deltas on each canonical workload.
* Provide a calibration constant between Mode A's
  `avg_access_latency_ns` predictions and observed swap traffic.

**It does not:**

* Validate any modern vLLM version. vLLM 0.4.x has known issues
  with newer model architectures (Llama-3, Qwen2.5) and lacks
  features partners rely on in production (chunked prefill,
  prefix caching, modern speculative decoding).
* Validate non-vLLM serving stacks. TGI, SGLang, internal
  forks all have their own integration surfaces (Path B).
* Substitute for partner-deployment validation. Real production
  workloads have request-arrival patterns and queue-discipline
  interactions that synthetic harness runs don't capture.

## §2 Hardware and software requirements

* **GPU:** NVIDIA A100 / H100 / RTX 4090. ≥ 24 GB VRAM. Llama-2
  / Mistral-v0.1 fit on 24 GB; Llama-3.1 + Qwen2.5 may not load
  at all on vLLM 0.4.x.
* **CUDA:** 11.8 or 12.1 (vLLM 0.4.3 supports both).
* **PyTorch:** 2.1.x or 2.2.x (vLLM 0.4.3's pin range).
* **Python:** 3.10 or 3.11. Newer Python may not have wheels
  for vLLM 0.4.3.
* **Storage:** ≥ 50 GB free on a fast NVMe partition (used as
  vLLM `swap_space` backing).

## §3 Step-by-step

### Step 1 — Clone + checkout the right branch

```bash
git clone https://github.com/rasaha/symbolu.git
cd symbolu
git fetch origin claude/safety-state-machine-EXAlZ
git checkout claude/safety-state-machine-EXAlZ
git log --oneline -5     # should show recent bench: ... commits
```

### Step 2 — Set up Python environment with pinned vLLM 0.4.3

```bash
# Create a fresh virtualenv. Do NOT reuse the current vLLM 0.7
# environment — vLLM 0.4 has different torch/CUDA pins and
# dependency conflicts will surface as cryptic CUDA errors at
# runtime.
python3.10 -m venv .venv-vllm04
source .venv-vllm04/bin/activate

pip install --upgrade pip

# Pin vLLM to 0.4.3 — known-good for the CTM+ evictor patch.
# This will pull torch 2.1.x or 2.2.x (matching vLLM 0.4.3's
# requirements) and the CUDA libraries.
pip install "vllm==0.4.3"

# Verify CUDA is available (should print the GPU name).
python3 -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"

# Install CTM+ KVPolicy (provides the evictor patch).
pip install -e CTM_plus/KVPolicy/
pip install -e CTM_plus/Bench/

# Verify everything imports.
python3 -c "from kv_policy.vllm_evictor import patch_vllm_engine; print('patch_vllm_engine ok')"
python3 -c "import ctm_bench.runner_vllm; print('runner ok')"

# Run the version-check (must pass).
python3 -m ctm_bench.scripts.vllm_version_check
# Expected: "OK: vLLM 0.4.3 is in the supported 0.4.x band ..."
# If this fails, the rest of the runbook will not work.
```

### Step 3 — Authenticate model download

vLLM 0.4.3 supports Llama-2 and Mistral-v0.1 cleanly. **Do not
use Llama-3 or Qwen2.5 on this path.**

```bash
# Llama-2 requires a HuggingFace token + Meta license acceptance.
huggingface-cli login

# Mistral-v0.1 is gated but easy to access.
# Either model works; Mistral is faster to download.
export MODEL=mistralai/Mistral-7B-Instruct-v0.1
```

### Step 4 — Smoke check

```bash
cd CTM_plus/Bench
./scripts/run_mode_b_vllm04.sh --quick 2>&1 | tee mode_b_vllm04_quick.log
```

**Smoke ok:**

* Pre-flight prints `OK: vLLM 0.4.3 is in the supported 0.4.x band`.
* GPU info line shows the expected GPU.
* Production `attention_ema_alpha` default reads `0.2`.
* Both LRU and CTM+ cells complete; CTM+ does **not** raise
  `NotImplementedError` (it would on vLLM 0.5+).
* Final block prints `slow_tier_B/tok=` and `avg_access_latency_ns=`.

**Common failures:**

* `vllm version check failed` → re-pin: `pip install 'vllm==0.4.3'`.
* `model not supported` → use Mistral-v0.1 or Llama-2-7b; do not
  use Llama-3.1 or Qwen2.5 on vLLM 0.4.x.
* `CUDA out of memory` at load → reduce `GPU_MEM_UTIL` (default
  0.30) or use a smaller model.

### Step 5 — Focused validation cells

```bash
./scripts/run_mode_b_vllm04.sh --rag-only      2>&1 | tee mode_b_vllm04_rag.log
./scripts/run_mode_b_vllm04.sh --agentic-only  2>&1 | tee mode_b_vllm04_agentic.log
```

The runner aggregates per-cell summaries into
`bench_out/mode_b_vllm04_<timestamp>/all_cells.json` and prints
per-(workload, seed) reduction tables.

**Validation thresholds — same as `MODE_B_RUNBOOK.md` §3 Step 5
modulo the model:**

| Workload | Mode A predicted | Mode B threshold |
|---|---:|---:|
| `rag_128k` | −100% slow-tier B/tok | CTM+ ≥ 50% reduction vs LRU |
| `agentic_clustered_64k` | +12.5% to +29% (oversub 0.10) | CTM+ within +30% of LRU |
| `agentic_clustered_64k` heavy | +192% (oversub 0.025) | CTM+ within +200% of LRU |
| `chat_32k` | parity | CTM+ ≤ LRU within 5% |

If RAG and agentic both pass, run the full sweep:

```bash
./scripts/run_mode_b_vllm04.sh --full 2>&1 | tee mode_b_vllm04_full.log
```

### Step 6 — Heavy-spillover cell (the 52% headline)

```bash
./scripts/run_mode_b_vllm04.sh --heavy-spillover 2>&1 \
    | tee mode_b_vllm04_heavy.log
```

| Cell | Mode A predicted | Mode B threshold |
|---|---:|---:|
| `chat_32k` heavy spillover | CTM+ at 61% of LRU's slow-tier B/tok | CTM+ ≤ 70% of LRU |

This validates only the eviction-policy half of the 52%
headline. The HBF-tier half (commodity flash with high
bandwidth) remains a Mode A prediction; vLLM 0.4 has no HBF
analog.

### Step 7 — Interpret the output + decide what to update

The runner prints a tail like:

```
Workload               Policy     Seed  slow_B/tok    avg_lat_ns  hbm_hit  wall
rag_128k               lru          42       2,048         3,811  100.0%   ...
rag_128k               ctm_plus     42           0         3,810  100.0%   ...
...

==> CTM+ vs LRU reduction (negative = improvement):
  rag_128k                seed=42   CTM+ vs LRU: -100.0%
  rag_128k                seed=137  CTM+ vs LRU: -100.0%
  ...
```

**Three reading rules** (same as the modern runbook):

1. **Sign first.** RAG negative + agentic positive = directional
   prediction holds.
2. **Magnitude vs §3 thresholds.** A 30% reduction on RAG is a
   "qualitative win, magnitude calibration TBD" not a failure.
3. **Surprises.** Workloads that were within-noise in Mode A
   showing decisive movement in Mode B = simulator missed
   something architectural; flag, do not paper over.

### Step 8 — Update the canonical record

If validation passes:

```bash
mv bench_out/mode_b_vllm04_<timestamp> bench_out/mode_b_vllm04_validated/
cd CTM_plus/Bench
python3 -m pytest tests -q
git add bench_out/mode_b_vllm04_validated/ bench_out/RESULTS.md
git commit -m "bench: §13 vLLM 0.4 pin — real-model CTM+ vs LRU validation"
git push origin claude/safety-state-machine-EXAlZ
```

The §13 write-up should:

* Lead with the **conservative framing**: "Real-model evidence
  on a historical (vLLM 0.4.3) stack. Modern serving stacks
  remain gated on roadmap #3 / Path B."
* Cite Mistral-7B (or Llama-2) by name; do not claim Llama-3
  or Qwen2.5 results — those models don't load on vLLM 0.4.
* Surface any disagreement between Mode A predictions and
  Mode B measurements as a real finding, not a calibration
  caveat.

If validation fails (CTM+ regression > Mode A predicts):

```bash
# Capture the actual numbers; do NOT silently re-run.
ls bench_out/mode_b_vllm04_*/all_cells.json | xargs cat > /tmp/mode_b_vllm04_actual.json

# If regression is dramatically worse, the production default
# change (alpha=0.2) may need to be revisited.
git revert 2c64b89   # reverts the alpha=0.20 change
# Add a thorough rationale citing the Mode B numbers in the
# revert commit message; do not amend.
git push origin claude/safety-state-machine-EXAlZ
```

## §4 Estimated cost

| Cell | Time | GPU-hours |
|---|---:|---:|
| `--quick` smoke | 5 min | 0.08 |
| `--rag-only` (3 seeds × 2 policies) | 25 min | 0.42 |
| `--agentic-only` (3 seeds × 2 policies) | 25 min | 0.42 |
| `--heavy-spillover` (3 seeds × 2 policies) | 25 min | 0.42 |
| `--full` (3 workloads × 3 seeds × 2 policies) | 75 min | 1.25 |
| **Recommended sequence** (smoke → focused → heavy → full) | **~135 min** | **~2.25** |

At RunPod A100 spot (~$1.20/hour) that is < $3 of compute.
Cost of NOT running #2: shipping unverified claims about
"CTM+ has been validated on a real model" to a partner who
will then check.

## §5 Reproducer template for partner-conversation citation

```
Repository: github.com/rasaha/symbolu
Branch:     claude/safety-state-machine-EXAlZ
Commit:     <sha after the #2 commit lands>
Hardware:   <e.g. NVIDIA A100 80GB, RunPod spot>
Model:      mistralai/Mistral-7B-Instruct-v0.1  (vLLM 0.4-compatible)
vLLM:       0.4.3 (pinned; modern vLLM is roadmap #3)
Reproduce:  cd CTM_plus/Bench && ./scripts/run_mode_b_vllm04.sh --full
Cells:      bench_out/mode_b_vllm04_validated/all_cells.json
Wall:       <sum of cell durations>
Cost:       <GPU-hours × your rate>
Caveat:     vLLM 0.4 is not the version anyone deploys today.
            These numbers calibrate CTM+'s scoring math against
            real attention; they do NOT validate modern serving
            performance. See PARTNER_VALIDATION_NOTE.md §4 Path B
            for the modern-stack validation gate.
```

The caveat line is not optional. Citing real-model numbers on a
historical stack as if they were modern-stack numbers does not
survive technical diligence.

## §6 Why we built #2 even though it's a historical stack

Three reasons:

1. **It eliminates a claim risk.** Without #2, the strongest
   honest claim is "two simulators agree on the shape." After #2
   it becomes "two simulators agree on the shape, and the policy
   has been measured on a real model under real attention" — even
   if the real model is on an old vLLM. That gap-closure is
   meaningful in a technical-diligence conversation.
2. **It surfaces simulator vs real-model disagreement cheaply.**
   If Mode A's RAG prediction (−100% slow-tier B/tok) holds on
   real attention, that's strong corroboration. If it softens to
   −60% or −20%, that's a real, actionable finding — and we
   would never have surfaced it without running on real
   attention.
3. **It gives partners an offer.** "Run our reproducer on your
   GPU" is a tangible thing partners can act on within their own
   compliance / hardware constraints, with a small fixed cost
   (< $3 in GPU-spot). It moves the conversation from "trust our
   simulators" to "verify yourself in 2 hours."

The audit-pass framing applies: the conclusion of #2 is what we
*measure*, not what we hope. If CTM+'s real-model behaviour
disagrees with Mode A's predictions, the §13 write-up surfaces
the disagreement honestly and the production-default
recommendation is revisited.
