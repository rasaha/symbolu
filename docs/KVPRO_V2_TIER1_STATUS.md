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
- **Phase-1 pod-ready code** (`kv_policy/phase6f_read_fusion.py`): the int4 read-path
  gather+splice+dequant-prep as a pure-PyTorch **reference** + a single-pass **fused** variant
  proven **byte-equal** on CPU — the numerical oracle the GPU kernel must match. **HARDWARE-UNTESTED
  on GPU; no throughput number claimed.**
- **Phase-3 pod-ready code** (`kv_policy/tier5c_warmtier_serving.py`): the WarmTier **serving**
  orchestration (prefix keying, snapshot store + manifest, reuse-plan + computed-token accounting,
  eviction policy) on top of the proven tier5b primitive. Host logic CPU-tested incl. an end-to-end
  snapshot→store→plan→restore byte-clean round-trip; the vLLM/GPU serving steps are isolated and
  **HARDWARE-UNTESTED** (fail loudly, never silently fake).
- A **CPU regression test suite for the WarmTier snapshot/restore primitive** (`tier5b_snapshot.py`)
  — the Phase-3 "gate on `verify_roundtrip` byte-clean first" requirement, validated at the
  **logic/plumbing level** (both protect formats), plus its guard behavior. **MEASURED (CPU,
  logic-level), this session.**
- Confirmation that the **existing CPU-runnable test suite stays green** (196 tests pass: 45 new +
  151 existing CPU-runnable; only genuine CUDA-only paths skip).
- This honest STATUS doc + a prior-measured baseline table (clearly labeled, **not** reproduced here).

> **Per-session direction:** after the Phase-0 stop-and-report, the user chose
> *"write untested pod-ready code"* — so Phase-1 and Phase-3 are now implemented as
> HARDWARE-UNTESTED, CPU-logic-tested code for later pod execution (above). The remaining
> **measurements** are still **blocked on hardware/toolchain prerequisites**, enumerated below.

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

### Phase 1 — Decode-throughput recovery (read-path fusion) → **CODE DELIVERED; GPU measurement BLOCKED**
- **Delivered (pod-ready, CPU-validated):** `kv_policy/phase6f_read_fusion.py` implements the lever —
  the pre-kernel gather+splice+dequant-prep (~42–60% of the B=1 read path) — as a pure-PyTorch
  reference + a single-pass fused variant, **byte-equal on CPU** (`test_phase6f_read_fusion_cpu.py`,
  11 tests). It matches the production pack/quant convention exactly, so it is the **numerical oracle**
  for the GPU kernel and a drop-in host-fused prep for `_read_decode_packed_batched`.
- **Still BLOCKED (needs GPU):** building/wiring the kernel, the CUDA-event B=1 headroom run, the
  perf-counter roofline (no `ERR_NVGPUCTRPERM`-cleared pod), and the throughput curve.
- **Honest ceiling remains ~0.27–0.30×, NOT full-precision parity** — unchanged, and **not measured
  this session**. No throughput number is claimed.

### Phase 2 — Tensor parallelism → **BLOCKED (no multi-GPU; no single GPU)**
Nothing validated. Still **single-GPU-only** as a claim; TP correctness/sharding/density are open.

### Phase 3 — WarmTier SERVING → **STORAGE half exists; SERVING half BLOCKED; gate validated on CPU**
- The **storage** half (snapshot a prefix's blocks+sidecars to NVMe, reload into fresh blocks) is
  implemented: `kv_policy/tier5b_snapshot.py`, `scripts/measure_kvpro_warmtier_snapshot.py`,
  `scripts/verify_kvpro_snapshot_roundtrip.py`. The systems-metrics script is pod-only.
- **Serving orchestration DELIVERED (pod-ready, host logic CPU-tested):**
  `kv_policy/tier5c_warmtier_serving.py` adds prefix keying (block-aligned chained hash),
  a snapshot store + JSON manifest with collision-guarded longest-prefix match, the eviction
  snapshot policy (threshold + dedup), the reuse plan + **computed-token accounting**
  (`num_computed_tokens = n_blocks·block_size`), and writer-backed snapshot/restore that inherits
  tier5b's byte-faithful guarantee. `test_tier5c_warmtier_serving_cpu.py` (21 tests) covers all of
  it incl. an **end-to-end snapshot→store→plan→restore byte-clean round-trip** on a mock writer.
- **Still BLOCKED (needs GPU/vLLM):** `mark_prefix_computed` (scheduler "already-computed" signal)
  and `serve_with_warmtier_reuse` (generate over restored KV with the int4 decode kernel) are
  isolated and **raise loudly off-pod** — never a silent fake. The reuse economics (TTFT-vs-cold,
  bytes/token, p95/p99) are **MEASURED on a pod**, not here.
- **Phase-3 gate** ("byte-clean first") is also covered by `tests/test_tier5b_snapshot_cpu.py`
  (both protect formats, disk round-trip, guards). **MEASURED (CPU, logic-level), this session.**
  This does not replace the pod byte-gate on the live vLLM writer.

### Phase 4 — Broader quality bench → **BLOCKED (no GPU)**
HumanEval pass@1 (sandboxed) and LongBench F1 vs full precision both need GPU inference. Runner-ready
per prior status; not executed here.

### Stretch (CacheGen e2e, SAW-INT4 breadth) → **BLOCKED**, unchanged
CacheGen e2e needs an LMCache server on a driver ≥13.0 pod; verdict remains
codec-fidelity-directional, e2e OPEN (`docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md`).

---

## What is now MEASURED (this session) vs still PROJECTED / OPEN

**Newly MEASURED (CPU, logic-level only):**
- **Phase-1 read-fusion numerics:** the fused dequant-prep is **byte-equal** to the staged reference
  for K, V, and the whole-view prep; pack/unpack round-trips and the protect overlay are exact;
  4-bit reconstruction error is bounded by one step. 11/11 tests pass. (No throughput measured.)
- **Phase-3 WarmTier host logic:** prefix keying, store + manifest round-trip, longest-prefix match
  (collision-guarded), reuse-plan accounting, eviction policy, and an **end-to-end
  snapshot→store→plan→restore byte-clean round-trip** on a mock writer. 21/21 tests pass.
- WarmTier snapshot/restore round-trip is byte-clean at the logic level for **both** protect formats
  (bf16-passthrough strictly byte-equal; prot-int8 code-lattice identity), and the restore guards
  (1:1 count, geometry) refuse bad input before any tensor write. 13/13 tests pass.
- Existing CPU-runnable test suite is green (**196 tests pass: 45 new + 151 existing**; CUDA-only
  paths skip).

**Still PROJECTED / OPEN (need a GPU pod — unchanged from prior status):**
- Decode-throughput recovery to the **~0.27–0.30× bounded ceiling** (PROJECTED; never parity) — the
  Phase-1 fusion code is ready; the kernel build + throughput curve are the open GPU work.
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

## Pod-ready code delivered this session (Phase 1 + Phase 3)

| File | What | CPU-validated | Pod-only (HARDWARE-UNTESTED) |
|---|---|---|---|
| `kv_policy/phase6f_read_fusion.py` | int4 read-path dequant-prep: reference + fused | nibble codec, quant round-trip, protect overlay, **fused≡reference byte-eq** (K/V/prep) | the inline CUDA/Triton kernel + throughput curve |
| `kv_policy/tier5c_warmtier_serving.py` | WarmTier serving orchestration | prefix keying, store/manifest, reuse-plan + computed-token accounting, eviction policy, **e2e snapshot→store→plan→restore byte-clean** | `mark_prefix_computed` (scheduler signal), `serve_with_warmtier_reuse` (decode over restored KV) |

**Integration points for the pod engineer** (in code comments too):
- Phase 1: drop `fused_read_dequant_prep` into `phase5b_backend_install._read_decode_packed_batched`
  (B=1: `_read_decode_packed_one`); the CUDA path is the existing
  `int4_fused_attention_kernel.fused_protected_k_decode_attention`. `PHASE6F_FUSED_READ=0` forces the
  reference for a byte-eq gate (mirrors `PHASE6E_FUSED_WRITER`).
- Phase 3: compose `plan_reuse → restore_prefix_into_blocks → mark_prefix_computed → generate`;
  gate on `scripts/verify_kvpro_snapshot_roundtrip.py` first, then measure TTFT-vs-cold / p95 / p99.

## How to run the delivered CPU subset

```bash
# This session's new pod-ready code + its CPU logic tests (45 tests)
python3 -m unittest CTM_plus.KVPolicy.tests.test_tier5b_snapshot_cpu \
                    CTM_plus.KVPolicy.tests.test_phase6f_read_fusion_cpu \
                    CTM_plus.KVPolicy.tests.test_tier5c_warmtier_serving_cpu -v

# Existing CPU-runnable guard suites (must stay green)
python3 -m unittest CTM_plus.KVPolicy.tests.test_phase6k15_swap_guard \
                    CTM_plus.KVPolicy.tests.test_phase6k16_prefix_guard \
                    CTM_plus.KVPolicy.tests.test_phase6k17_chunked_guard
```
(`torch` CPU build is sufficient for the round-trip/byte-eq tests; the pure-helper tests need no deps.)
