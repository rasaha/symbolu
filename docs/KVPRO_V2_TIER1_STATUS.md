# KVPro v2 Tier-1 — Status & Phase-0 Baseline (honest scope)

**Date:** 2026-06-17 · **Branch:** `claude/kvpro-v2-tier1-d8b4ae`

> **Labeling discipline (non-negotiable):** every figure below is tagged
> **MEASURED** (with where/when), **MODELED**, or **PROJECTED**. Nothing in this document is a
> newly-measured GPU result from this session — see the environment gate. The KVPro compression
> mechanism is proprietary / patent-pending and is **not** described here; this is a results- and
> systems-status document only.

---

## TL;DR

This session ran in a **CPU-only container with no GPU, no CUDA toolkit, and no pre-installed ML
stack**. Every measurement deliverable in the v2 Tier-1 task — Phase-0 baseline reproduction
(quality battery, density, throughput curve), Phase-1 decode-fusion throughput, Phase-2 tensor
parallelism, Phase-3 WarmTier *serving* economics, Phase-4 HumanEval/LongBench — **requires a GPU
pod with the int4 flash-attention fork built**, and therefore **cannot be produced or reproduced
here**. Per the task's hard constraint, **no GPU result has been simulated or labeled measured.**

What **was** delivered, and is green on CPU:
- A **CPU regression test suite for the WarmTier snapshot/restore primitive** (`tier5b_snapshot.py`)
  — the Phase-3 "gate on `verify_roundtrip` byte-clean first" requirement, validated at the
  **logic/plumbing level** (both protect formats), plus its guard behavior. **MEASURED (CPU,
  logic-level), this session.**
- Confirmation that the **existing CPU-runnable test suite stays green** (164 tests pass; only
  genuine CUDA-only paths skip).
- This honest STATUS doc + a prior-measured baseline table (clearly labeled, **not** reproduced here).

The remaining work is **blocked on hardware/toolchain prerequisites**, enumerated precisely below.

---

## Environment gate (why the GPU work is blocked here)

| Probe | Result |
|---|---|
| GPU | **None.** `nvidia-smi` absent; no `/dev/nvidia*`. |
| CPU / RAM / disk | 4 vCPU · 15 GiB RAM · ~30 GiB free disk · Linux 6.18.5 x86_64. |
| CUDA toolkit / `nvcc` | **Absent.** Cannot compile any CUDA kernel. |
| ML stack at session start | **Absent:** no `torch`, `vllm`, `vllm_flash_attn`, `flash_attn`, `numpy`, `transformers`, `datasets`. |
| Installed this session | `torch 2.12.0` (CPU; `torch.cuda.is_available()==False`) + `numpy 2.4.6`, from PyPI — **solely to run the CPU logic tests**. Not a serving stack. |
| Network | PyPI reachable; `download.pytorch.org/whl/cpu` returns HTTP 403; Hugging Face model pull not attempted (no GPU to use weights). |

**Each unmet prerequisite, mapped to the deliverable it blocks:**

| Prerequisite (from the task) | Status here | Blocks |
|---|---|---|
| NVIDIA GPU (single) | ❌ none | Phases 0,1,3,4 (all inference/measurement) |
| Multi-GPU pod (≥2 ranks) | ❌ none | Phase 2 (tensor parallelism) |
| `flash_attn_with_int4_kvcache` int4 decode kernel built/importable | ❌ cannot build (no CUDA) | Any decode/serving: Phase-0 decode arm, Phase-1, Phase-3 serving, Phase-4 |
| vLLM 0.7.3 V0 + matched torch/CUDA driver | ❌ not installed; no driver | Phases 0–4 |
| Calibrated protect mask at `$PROTECT_MASK_PATH` (per model) | ❌ needs a GPU calibration run | Phases 0–4 |
| Model weights (Qwen2.5-7B/14B, Mistral-7B-v0.3, Llama-3.1-8B) | ❌ not present | Phases 0,2,4 |
| Profiling pod with perf counters unlocked (`ERR_NVGPUCTRPERM` cleared) | ❌ n/a | Phase-1 roofline (Test-1) |

> **Conclusion:** this environment can develop and unit-test **host-side / pure-logic** code and
> author docs. It cannot reproduce or advance any GPU measurement. The runnable subset is delivered;
> the rest is explicitly deferred to a GPU pod (see "Remaining gaps").

---

## Phase-0 baseline — PRIOR MEASURED numbers (NOT reproduced this session)

These are the starting baselines from the task brief and `KVPro_VC_brief.md`. They were
**MEASURED on real H100/A100 GPUs in a prior quarter**. They are reproduced here **as the reference
to beat**, **not** re-measured in this container. Do not read this table as a current-session result.

| Axis | Prior MEASURED baseline (H100/A100) | Notes / honesty flags |
|---|---|---|
| **Quality — needle (long-context retrieval)** | 15/15 == full precision on **3 of 4** models (2-of-2 seed replication) | **Qwen2.5-7B is AT-THE-MARGIN** under the 4% mask: one seed 13/15. State precisely; do not round to "parity on 4/4". |
| **Quality — Qwen2.5-7B, Mistral-7B-v0.3, Llama-3.1-8B, Qwen2.5-14B** | 4 models, 3 families, 7–14B | breadth claim |
| **Quality — MMLU / ARC / TruthfulQA** | **0.0-pt delta** vs full precision, identical answer on every question | MMLU done; ARC/TruthfulQA per brief |
| **Quality — token agreement vs naïve int4** | **+20.4 pt** | |
| **Quality — hard-needle** | **0.964** | multi-distractor |
| **Density** | **2.0× raw** KV slots; **~1.8× net** (1.83× Qwen util0.5 / 1.75× Llama util0.85) under saturation | net < raw because of the fixed sidecar tax |
| **Sidecar tax** | **4.38 GB, flat with context** | |
| **Throughput** | **0.13–0.67× full precision**, workload-dependent (0.22× worst: deep-saturation+long-gen; 0.54× short-gen) | **below full precision** — KVPro is a capacity/quality tool, routed accordingly |
| **Decode tax attribution (Phase 6M.4)** | GPU-work-bound: paged gather ~25% + decode attention ~21%; host syncs <1% | CUDA graphs **ruled out** as a lever (neutral at saturation) |
| **Decode recovery ceiling** | **bounded ~0.27–0.30×** via read-path kernel fusion — **never full-precision parity** | hard ceiling; do not claim parity |
| **WarmTier snapshot/restore** | byte-faithful (both protect formats) | see discrepancy note below |
| **APC (prefix caching)** | ships **eager-only** (6K.16); graphs+APC gated off | int4 FA kernel not graph-safe at B>1 |
| **Tensor parallelism** | **NOT validated** | open |
| **Broader bench** | MMLU done; **HumanEval/LongBench runner-ready, not executed** | open |

> **Discrepancy flagged honestly:** `kv_policy/tier5b_snapshot.py`'s header says
> "⚠️ HARDWARE-UNTESTED", while `docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md` §Phase 0 records a
> **MEASURED 2026-06-14 A100** byte-clean PASS (8 blocks @ 21,760 B/block, all 7 tensors) and the
> VC brief calls snapshot/restore "verified byte-faithful." The code header appears stale/
> conservative relative to the recorded pod result. The CPU test added this session corroborates the
> **logic** independently; the pod runbook remains the source of the **on-hardware** measurement.

---

## Per-phase status this session

### Phase 0 — Reproduce baseline → **BLOCKED (no GPU); reported, not simulated**
Cannot build the int4 FA fork, calibrate masks, or run vLLM. Baseline table above is prior-measured.
**STOP-and-report point reached as the task instructs.**

### Phase 1 — Decode-throughput recovery (read-path fusion) → **BLOCKED (no GPU/CUDA)**
The lever (fuse the pre-kernel gather+splice+dequant-prep of the int4 read path; ~42–60% of the B=1
read path) needs a built int4 kernel + GPU to measure. No roofline (no perf-counter pod) and no
CUDA-event B=1 headroom run is possible without a GPU. **Honest ceiling remains ~0.27–0.30×, NOT
parity** — unchanged, and unverified this session. No fusion kernel was written blind-and-untestable.

### Phase 2 — Tensor parallelism → **BLOCKED (no multi-GPU; no single GPU)**
Nothing validated. Still **single-GPU-only** as a claim; TP correctness/sharding/density are open.

### Phase 3 — WarmTier SERVING → **STORAGE half exists; SERVING half BLOCKED; gate validated on CPU**
- The **storage** half (snapshot a prefix's blocks+sidecars to NVMe, reload into fresh blocks) is
  implemented: `kv_policy/tier5b_snapshot.py`, `scripts/measure_kvpro_warmtier_snapshot.py`,
  `scripts/verify_kvpro_snapshot_roundtrip.py`. The systems-metrics script is pod-only.
- The **serving** half (allocate fresh blocks → restore → **generate tokens over restored KV** with
  scheduler "already-computed prefix" injection) needs the **int4 decode kernel + vLLM scheduler
  changes** → **BLOCKED here**. Not written blind.
- **Delivered:** the Phase-3 gate ("byte-clean first") is now covered by a **CPU logic test**
  (`tests/test_tier5b_snapshot_cpu.py`): both protect formats round-trip byte-clean, disk
  round-trip byte-clean, and the count-/geometry-mismatch guards refuse before touching tensors.
  **MEASURED (CPU, logic-level), this session.** This does not replace the pod byte-gate on the live
  vLLM writer; it guards the serialize/restore code against logic regressions without a GPU.

### Phase 4 — Broader quality bench → **BLOCKED (no GPU)**
HumanEval pass@1 (sandboxed) and LongBench F1 vs full precision both need GPU inference. Runner-ready
per prior status; not executed here.

### Stretch (CacheGen e2e, SAW-INT4 breadth) → **BLOCKED**, unchanged
CacheGen e2e needs an LMCache server on a driver ≥13.0 pod; verdict remains
codec-fidelity-directional, e2e OPEN (`docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md`).

---

## What is now MEASURED (this session) vs still PROJECTED / OPEN

**Newly MEASURED (CPU, logic-level only):**
- WarmTier snapshot/restore round-trip is byte-clean at the logic level for **both** protect formats
  (bf16-passthrough strictly byte-equal; prot-int8 code-lattice identity), and the restore guards
  (1:1 count, geometry) refuse bad input before any tensor write. 13/13 tests pass.
- Existing CPU-runnable test suite is green (164 tests pass; CUDA-only paths skip).

**Still PROJECTED / OPEN (need a GPU pod — unchanged from prior status):**
- Decode-throughput recovery to the **~0.27–0.30× bounded ceiling** (PROJECTED; never parity).
- TP correctness/density at 2-rank and 70B-class (OPEN).
- WarmTier **serving** TTFT-vs-cold, bytes/token on a real reuse workload, p95/p99 under concurrency
  (OPEN; storage-half script ready).
- HumanEval / LongBench deltas vs full precision (OPEN; runner ready).
- On-hardware re-confirmation of the snapshot byte-gate on the live writer (prior A100 PASS stands).

---

## Remaining gaps — exact prerequisites to unblock each deliverable

1. **GPU pod (single, ≥A100/H100-class)** with: vLLM 0.7.3 V0, torch matched to the pod's CUDA
   driver (keep KVPro on its working torch/vLLM — do **not** upgrade into the cu130-vs-driver-12.8
   wall), the **`flash_attn_with_int4_kvcache` int4 fork built and importable**, model weights
   cached, and a calibrated mask at `$PROTECT_MASK_PATH`
   (`CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py --output <path>` per model).
   → Unblocks Phase 0, Phase 1 (CUDA-event B=1 method even without perf counters), Phase 3 serving,
   Phase 4.
2. **Profiling pod** with perf counters unlocked (`ERR_NVGPUCTRPERM` cleared) → Phase-1 Test-1
   roofline (compute- vs bandwidth-bound split). Optional; the CUDA-event method works without it.
3. **Multi-GPU pod (≥2 ranks, then a 70B-class node)** → Phase 2 TP validation.
4. **LMCache server on a driver ≥13.0 pod** → the stretch CacheGen e2e arm.

**Verification gate to run first on any pod** (already wired, no new code needed):
`python scripts/verify_kvpro_snapshot_roundtrip.py` (the int4 decode kernel is **not** required for
this gate — prefill writes the KV before the decode read runs). It must print
`PASS — ... Phase-0 gate cleared` before trusting Phase-3 serving work.

---

## How to run the delivered CPU subset

```bash
# WarmTier snapshot/restore logic + guards (this session's new tests)
python3 -m unittest CTM_plus.KVPolicy.tests.test_tier5b_snapshot_cpu -v

# Existing CPU-runnable guard suites (must stay green)
python3 -m unittest CTM_plus.KVPolicy.tests.test_phase6k15_swap_guard \
                    CTM_plus.KVPolicy.tests.test_phase6k16_prefix_guard \
                    CTM_plus.KVPolicy.tests.test_phase6k17_chunked_guard
```
(`torch` CPU build is sufficient for the round-trip tests; the pure-helper tests need no deps.)
