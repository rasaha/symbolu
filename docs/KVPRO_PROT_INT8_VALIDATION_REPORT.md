# KVPro `prot-int8` — INT8 Protected-Channel Sidecar Validation Report

**Internal / NDA engineering evidence only. Not investor-facing. No patent or marketing claims.**

Frozen commit `bfb2dfba70eb7c9d219b8d805a196062785d3798` · branch `claude/kvpro-prot-int8-validation-hkd4ff` · date 2026-07-30.

Scope: **only** INT8 as the *protected sidecar* inside INT4-Protected KVPro. BF16, FP8, and full-cache-INT8 questions are explicitly out of scope. The BF16-protected path is preserved as control and fallback.

Evidence labels used throughout: **MEASURED**, **TEST-BACKED**, **MODELED**, **INFERRED**, **RESOURCE_BLOCKED**, **UNSUPPORTED**.

---

## 1. Executive verdict

**FINAL VERDICT: PARTIALLY VALIDATED (mechanism real and storage-halving confirmed; production-path speed benefit absent by design; end-to-end quality unproven).**

The claim under review was, approximately:

> "prot-int8 reduces the protected sidecar from roughly 10 bytes to 5 bytes per token/head/layer, is shipped, preserves greedy output, has zero quality cost, and contributes to improving effective KV density."

Decomposed:

| Sub-claim | Status | Label |
|---|---|---|
| Reduces protected sidecar 10 B → 5 B per token/head/layer (n_protect=5) | **TRUE** | MEASURED + TEST-BACKED |
| Halves the *protected sidecar* storage | **TRUE** | MEASURED + TEST-BACKED |
| "is shipped" | **MISLEADING** — implemented but **flag-gated OFF by default**; not enabled in any config found | INFERRED (code) |
| Reduces **real allocated GPU memory** | **UNVERIFIED** — no GPU allocator measurement exists anywhere | RESOURCE_BLOCKED |
| "preserves greedy output" / bit-identical | **FALSE as bit-identity**; token-level parity **untested** | TEST-BACKED (not identical) / RESOURCE_BLOCKED (tokens) |
| "zero quality cost" | **UNSUPPORTED** — no real-model quality run for prot-int8; CPU proxy shows small but non-zero divergence | RESOURCE_BLOCKED + MEASURED (proxy) |
| Improves / does not worsen decode performance | **NOT SUPPORTED as a speedup**; read path *adds* a dequant; both paths converge to the same bf16 buffer | INFERRED + MEASURED (CPU directional) |
| Contributes to effective KV density | **TRUE but small** (~2.94% of the K/V read stream at 4%; far less of total model memory) | MODELED |

The mechanism is genuinely implemented and the storage-byte halving of the protected sidecar is real and test-backed. But the INT8 codes are **never consumed as INT8 by any kernel** — every read dequantizes to a materialized BF16 buffer before attention — so no decode-speed benefit can arise from the representation, and the memory win is confined to a sub-stream that is a small fraction of KV. "Zero quality cost" and "improves decode" are not substantiated by any evidence in the repo or reproducible here.

---

## 2. Frozen baseline

- **Commit:** `bfb2dfba70eb7c9d219b8d805a196062785d3798`; branch `claude/kvpro-prot-int8-validation-hkd4ff`; clean tree at session start.
- **Python** 3.11.15. **OS** Linux 6.18.5, Ubuntu 24.04 userspace, gcc 13.3.0.
- **CPU** Intel Xeon @ 2.10 GHz ×4; **RAM** 15 GiB; disk 252 G (22 G free).
- **GPU: none.** `nvidia-smi`/`nvcc` absent, `torch.cuda.is_available() == False`. → **all GPU experiments RESOURCE_BLOCKED.**
- **torch:** absent at start (repo pins `torch==2.4.1` cu121; pytorch.org wheel index proxy-blocked). Installed `torch 2.13.0+cu130` from PyPI for this session — imports and runs on CPU only. `numpy 2.4.6`, `pytest 9.1.1` installed. `transformers`, `triton`, `accelerate` absent.
- **KVPro modes:** (a) BF16 protected sidecar = default/shipped; (b) INT8 protected sidecar = Phase 6N `prot_int8`, **flag-gated OFF** via env `INT4_PROTECTED_PROT_INT8`; (c) INT4 affine residual (unchanged between a/b).
- **prot-int8-relevant CPU test suite:** **135 passed** (see §13 and `artifacts/prot_int8/test_results.txt`).

Full detail: `artifacts/prot_int8/environment.json`, `artifacts/prot_int8/baseline.json`.

---

## 3. Implementation trace

All paths in `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py` unless noted.

- **Protected-channel selection / calibration:** `experiments/kvpro_v3_symmetric_residual/calibrate_mask_hf.py` (`n_protect = max(1, round(D·protect_fraction))`, default 4% → 5 at D=128); `CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py` (signed min/max accumulator + `_widen_minmax`). Mask loaded `:804`; `n_protect` resolved from the mask `:1739`.
- **Sidecar math (production):** `prot_int8_enabled` `:742`; `prot_int8_constants` `:749` (`scale=((max−min)/255).clamp(1e-8)`); `prot_int8_quantize` `:759` (`round((x−min)/scale).clamp(0,255) → uint8`); `prot_int8_dequantize` `:768`.
- **Activation & allocation:** `:1744–1790` — flag + v2 artifact (with `k_min/k_max`) required; else warns once and stays BF16. `k_protect_ext` allocated `uint8` when active, else `bf16` (`:1784–1787`).
- **Store / view:** `_protect_store` `:1876` (identity for BF16; `quantize` for INT8); `_protect_view_bf16` `:1883` (identity for BF16; `dequantize → bf16` for INT8).
- **Write sites:** `write()` `:1082/2080`, `write_decode_batched` `:2442`. **Read sites:** `get_packed_view` `:2753`, `get_packed_view_batched` `:2811` — both emit key `k_protect_bf16`.
- **Kernels:** production decode = external forked-vLLM CUDA `flash_attn_with_int4_kvcache` (no in-repo source; consumes **bf16** protected sidecar). In-repo Triton `int4_fused_attention_kernel.py` (route-A, GPU-only, consumes `k_fp16`, **not** production). References: `phase6f_read_fusion.py`, `int4_fused_attention_sketch.py` (explicitly a "sketch"). CUDA write ext `CTM_plus/CUDA_int4_protected/csrc/*.cu` is **bf16-only, not built**, and **disabled when INT8 is active** (`:1003`).

---

## 4. Is INT8 truly in the production path?

Classification of the INT8 protected path (A–F):

- **(C) Stored in actual KV-cache pages — YES.** `k_protect_ext` `(NB,BS,H,n_protect)` is genuinely allocated and written as `uint8` (`:1784–1787`, `:2080/2442`). Not an in-place fake-quant.
- **(F) Reference/fallback-only on consumption — YES.** When INT8 is active the only real CUDA write kernel is deliberately turned off (`:1003`), and it is not even built in this repo.
- **(D) Consumed by production decode kernel as INT8 — NO.** **(E) Fully fused — NO.**

**Decisive:** `_protect_view_bf16` (`:1883–1890`) dequantizes INT8 → **bf16** on every read; the docstring states *"the kernel contract is unchanged — it always receives bf16."* `get_packed_view` comment (`:2781–2782`): *"Protect: dequant to bf16 under prot-int8 — the kernel contract is bf16 either way."* Both BF16 and INT8 modes converge to the identical `k_protect_bf16` gather buffer the kernel requires. **INT8 is an on-page storage/compression representation that is materialized back to BF16 before any attention math.** — Label: **INFERRED (code-traced, corroborated by two independent traces).**

Consequence: memory reduction of the *stored* sidecar can exist **without any decode-speed improvement**, because the kernel workload is byte-for-byte identical (it always sees bf16). This is exactly the caveat the investigation brief flags.

---

## 5. A/B methodology

Controlled isolation of the single variable — protected-sidecar representation — holding the INT4 residual byte-identical:

- **A (BF16 protection):** INT4 affine residual (production `quantizers.quantize_k_sequence`, "affine") for all channels; protected channels overlaid with the **exact bf16** key value.
- **B (INT8 protection):** identical INT4 residual; protected channels overlaid with the **production** `prot_int8` static-asym round-trip (`phase5b_4c_paged_writer.prot_int8_{constants,quantize,dequantize}`).
- **C (Full BF16 KV):** raw bf16 key, reference only.

Because the residual is identical in A and B, every A↔B delta is attributable purely to the protected sidecar. Primary comparison is **B − A** (not B − C). Harness: `scripts/kvpro_prot_int8_validation/numerical_ab.py`. Geometry D=128, H=4, BS=32. Sweep: protect % ∈ {0,1,2,4,8}, seqlen ∈ {128,512,2048}, seeds {0,1,2}, six distributions incl. adversarial. 270 configs (216 with protection). — Label: **MEASURED (CPU, real repo math).**

*Limitation:* the protect mask here is **random**, not calibration-selected. Production protects the salient (often high-magnitude) channels; the random mask includes such channels, so worst-case rows are representative of "a protected channel with large dynamic range."

---

## 6. Byte accounting

`artifacts/prot_int8/byte_accounting.csv`. Per token/head/layer (D=128, BS=32, H=4):

| protect % | n_protect | protect BF16→INT8 (B) | protect sub-stream saving | total read stream BF16→INT8 (B) | total saving |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0→0 | — | 160→160 | 0% |
| 1 | 1 | 2→1 | 50% | 162→161 | 0.62% |
| 2 | 3 | 6→3 | 50% | 166→163 | 1.81% |
| **4** | **5** | **10→5** | **50%** | **170→165** | **2.94%** |
| 8 | 10 | 20→10 | 50% | 180→170 | 5.56% |

- **"10 B → 5 B per token/head/layer" is exactly correct at the production 4% fraction (n_protect=5).** — **MEASURED** (tensor `.nbytes`, `test_p8_gate_cpu.py:73-74` asserts 10.0→5.0) + **TEST-BACKED**.
- The 50% is **only** of the protected sub-stream. The protected stream is ~6% of the 170 B total K/V read stream at 4%, so the **total** read-stream reduction is **~2.94%** (MODELED, `accounting.py`).
- INT8 adds per-model dequant constants `_prot_qmin`/`_prot_qscale` = `2·(H,n_protect)` f32 ≈ **320 B/layer**, amortized to ~0.0016 B/token over 2048 tokens — negligible per token but real. Net measured tensor-storage saving after metadata: **≈49.8–50.0%** of the sidecar payload (`memory_results.csv`).
- Do **not** infer total GPU-memory savings from element width: KV is only part of resident memory (weights dominate), and the halved stream is itself a small part of KV.

---

## 7. Numerical correctness (A vs B)

`artifacts/prot_int8/numerical_error.csv` (270 rows). — Label: **MEASURED (CPU, real repo math).**

| Level | Metric | Well-behaved (`normal`) | Worst across all distributions |
|---|---|---|---|
| L1 protected-value recon | max abs err | 0.031 | **16.0** (`high_dynamic_range`) |
| L2 full K | rel L2 | 0.0030 | 0.0040 |
| L3 logits | rel L2 | 0.0030 | 0.0046 |
| L3 logits | top-1 pos agreement | 1.000 | **0.75** (2/216 configs) |
| L4 softmax | KL(A‖B) | ~1e-4 | 0.0116 |
| L5 attn output | rel L2 | 0.0030 | **0.0368** (8% protect, S=2048) |
| L5 attn output | cosine | 0.999996 | **0.999387** (`high_dynamic_range`) |
| all | NaN/Inf | 0 | 0 |

Findings:
- **Not bit-identical anywhere** — `K_bitidentical_AB == False` for every protected config. INT8 static-asym round-trip is lossy vs exact BF16, as expected (error bounded ≈ channel-range/510 for in-range values).
- For **well-behaved** keys the sidecar swap is numerically very close (cosine ≈ 1, rel-L2 ≈ 0.3%, top-1 always agrees).
- For **extreme-dynamic-range / heavy-tailed** channels the error is materially larger: worst absolute recon error 16.0, worst attn-output rel-L2 3.7%, and **top-attended position flips in 2 of 216 configs** (both heavy-tailed at S=2048). Small, but **non-zero** — this is the direct counter-evidence to "zero quality cost."
- Adversarial degenerate/constant channels: scale clamps to 1e-8, output stays finite (TEST-BACKED, §13).

---

## 8. Greedy-output parity

`artifacts/prot_int8/greedy_parity.csv`. The brief's six candidate meanings of "greedy bit-identical" are **not** interchangeable; here:

- Identical masks / identical INT4 codes: **YES** (residual unchanged).
- Identical reconstructed FP tensors: **NO** (§7 — never byte-identical).
- Identical logits / attention outputs: **NO** (small deltas).
- **Identical generated tokens: RESOURCE_BLOCKED** — requires a real model (weights + `transformers` + GPU), unavailable here. The repo's `token_agreement.py` / `p8_gate.py` harnesses exist but were **never run for prot-int8**.

A CPU proxy — agreement of the argmax-attended position (single-query) — agrees in 214/216 configs. This is **not** token parity and must not be reported as such.

**Do not describe prot-int8 as "greedy bit-identical."** At best a future GPU run could establish *token-sequence* parity under deterministic greedy decoding; the *tensors* are provably not bit-identical.

---

## 9. Quality evaluation

`artifacts/prot_int8/quality_results.csv`.

- Real-model benchmarks (needle, hard-needle, MMLU, long-context) for prot-int8: **RESOURCE_BLOCKED** — need GPU + Qwen2.5-7B weights + calibrated mask + `transformers`. Harness (`p8_gate.py`, `gates.py`, drivers) is present and CPU-tested for *plumbing* but its generation stages are pod-only, and **no prot-int8 quality result exists in the repo**.
- The `STATUS.md` two-model results are for the **S1–S4 symmetric-residual** study (a different axis, xmin removal) — **not** prot-int8 — and closed NO-GO. They are not evidence for or against prot-int8.
- CPU numerical proxy (§7) classification: **NO MATERIAL DEGRADATION OBSERVED** for well-behaved inputs, **MIXED** including adversarial channels (top-1 flips exist). This is *not powered* to establish equivalence.

Pre-registered equivalence margins would be required *before* a real run to legitimately claim equivalence; none are established for prot-int8. Therefore **"zero quality cost" is UNSUPPORTED** under the brief's own definitions.

---

## 10. Memory results

`artifacts/prot_int8/memory_results.csv`.

- **MEASURED (tensor storage, CPU):** the `k_protect_ext` sidecar halves (BF16→INT8) — e.g. at 28 layers, 8192 tokens, batch 1: 9.18 MB → 4.59 MB (−49.95% incl. metadata). Scales linearly with layers·tokens·batch.
- **RESOURCE_BLOCKED:** actual GPU **allocator-requested / reserved / peak / steady-state** bytes, allocator granularity, padding, page-header overhead. No `torch.cuda` sidecar measurement exists in the repo (`benchmark_memory.py` measures an unrelated transformer-attention subject).
- **MODELED:** effective density — halving the protected sub-stream is ~2.94% of the K/V read stream at 4% (§6), a small contribution to overall KV density and smaller still to total resident memory.

---

## 11. Performance results

`artifacts/prot_int8/performance_results.csv`.

- **RESOURCE_BLOCKED:** decode-step latency, tokens/s, requests/s, achieved bandwidth, kernel launches/token, occupancy — no GPU; production kernel is closed external CUDA.
- **MEASURED (CPU, directional only):** the read path — BF16 = identity passthrough vs INT8 = uint8→bf16 dequant to the *same* buffer. INT8 read is **3.2–4.4× slower** than the BF16 passthrough on this CPU (it does strictly more work). This overstates GPU cost (no fusion, Python-level) but the **direction is correct**: INT8 **adds** a dequant on read; it removes no work the kernel sees.
- **INFERRED:** since both paths hand the kernel an identical bf16 buffer (§4), there is **no mechanism** by which prot-int8 speeds up decode. The best achievable is *neutral* decode with reduced storage — and only if the added read-side dequant is fully hidden (unmeasured on GPU).

---

## 12. Kernel / profiler evidence

`artifacts/prot_int8/profiler_summary.json`.

- Nsight Systems / Nsight Compute / CUDA-event decode profiling of prot-int8: **RESOURCE_BLOCKED** (no GPU; existing audits note `ncu` blocked by `ERR_NVGPUCTRPERM` even on pods).
- Existing repo audits (`scripts/kvpro_v3_profile/PRODUCTION_DECODE_AUDIT.md`, `scripts/kvpro_kernel_recovery/`) independently confirm the production kernel reads the **compact bf16** protected sidecar and that INT8 is not consumed by it. Consistent with §4.

---

## 13. Regression tests

- **Existing (verified, all pass):** `test_phase6n_prot_int8.py` (25), plus experiment suite `test_protected_int8_cpu.py`, `test_calibrate_mask_cpu.py`, `test_p8_gate_cpu.py`, `test_quality_gate_cpu.py`, `test_driver_builders_cpu.py`, `test_cache_api_cpu.py`, `test_symmetric_residual_cpu.py`; read-fusion, profile, kernel-contract, and tier5b snapshot CPU tests. **135 passed** (`test_results.txt`). These cover: flag-off BF16 backward-compat (identity converters), uint8 full-range + clamp-not-wrap, all-three-write-sites agree, read-path dequant bit-exact, degenerate/constant channel scale clamp, artifact v1/v2 loader + loud fallback, calibration accumulator + widen, snapshot round-trip under both formats. — **TEST-BACKED.**
- **Added (additive, non-weakening):** `scripts/kvpro_prot_int8_validation/test_prot_int8_edges_cpu.py` (7 pass) — zero / one / odd protected counts, NaN/Inf-safe degenerate calibration, out-of-range clamp, bf16/f32/f16 dtype round-trip, exact scale formula. No defect was found (all pass), so these document robustness rather than gate a fix.
- **Not added:** tensor-parallel and cache save/reload beyond existing snapshot tests were not exercised (no multi-device here).

---

## 14. Limitations

1. **No GPU** — all decode-speed, GPU-memory-allocator, and profiler evidence is RESOURCE_BLOCKED.
2. **No model weights / `transformers`** — all real-model quality and token-parity evidence is RESOURCE_BLOCKED.
3. **torch 2.13 (session)** differs from the repo pin 2.4.1; CPU tensor math is unaffected but not the shipped runtime.
4. **Random protect mask** in the numerical harness (not calibration-selected); representative of worst-case channels but not the exact production mask.
5. **CPU perf is directional only** and overstates the GPU dequant cost.
6. Numerical harness is single-query attention on synthetic K/V; it is a proxy, not full-model inference.

---

## 15. Evidence classification (summary)

| Conclusion | Label |
|---|---|
| INT8 sidecar implemented, flag-gated, stored on-page as uint8 | INFERRED (code) + TEST-BACKED |
| Protected sidecar 10 B → 5 B (n_protect=5); ~50% of protected sub-stream | MEASURED + TEST-BACKED |
| Total K/V read-stream saving ≈2.94% at 4% | MODELED |
| Real GPU allocated/reserved/peak memory saving | RESOURCE_BLOCKED |
| INT8 not consumed by any kernel; dequant→bf16 before attention | INFERRED (code, 2 independent traces) |
| Not bit-identical; small non-zero numerical divergence; rare top-1 flips | MEASURED (CPU) |
| Token-level greedy parity | RESOURCE_BLOCKED |
| Real-model "zero quality cost" | UNSUPPORTED (no run) |
| Decode speedup from INT8 | UNSUPPORTED (mechanism absent) / RESOURCE_BLOCKED (GPU) |
| Read path adds a dequant (no read-side speed win) | MEASURED (CPU directional) + INFERRED |

---

## 16. Claims that are SAFE to make (internal)

- "prot-int8 stores the protected-K sidecar as static-asymmetric uint8 (1 B) instead of bf16 (2 B), **halving the protected sidecar** — 10 B → 5 B per token/head/layer at the 4% / n_protect=5 configuration." (MEASURED + TEST-BACKED)
- "The mechanism is implemented, flag-gated (`INT4_PROTECTED_PROT_INT8`, **default OFF**), calibration-driven, and covered by 135 passing CPU tests including bit-exact write/read round-trip and BF16 backward-compat." (TEST-BACKED)
- "The stored sidecar tensor shrinks ~50% (measured tensor bytes); net of the amortized per-model dequant constants." (MEASURED)
- "INT8 protection is decode-**neutral by construction**: it is dequantized to the same bf16 buffer the kernel already consumed, so it neither speeds up nor is intended to speed up the decode kernel." (INFERRED)

## 17. Claims that are NOT SAFE to make

- ✗ "prot-int8 is shipped / on in production." (It is default-OFF, enabled nowhere found.)
- ✗ "Zero quality cost" / "preserves greedy output bit-identically." (Not bit-identical; no real-model quality or token-parity run exists; CPU proxy shows rare top-1 flips.)
- ✗ "Reduces GPU memory by ~50%." (Only the protected sub-stream halves — ~2.94% of the K/V read stream at 4%; real GPU allocator memory unmeasured.)
- ✗ "Improves decode performance." (No mechanism; read path adds a dequant.)
- ✗ Any statement deriving total GPU-memory or throughput savings from the 2 B→1 B element width.

## 18. Recommended next action

1. **Correct the internal claim wording now** (this report). Keep BF16 as default/fallback.
2. **Gate any quality claim on a real pod run**: calibrate the mask, run `p8_gate.py` (needle + hard-needle + MMLU) with **pre-registered equivalence margins**, ≥3 seeds, on Qwen2.5-7B *and* a second architecture (the S-study showed model-specificity). Until then, quality = **RESOURCE_BLOCKED**, not "zero cost."
3. **Only then** decide whether the storage win justifies keeping the feature: at ~2.94% of the KV read stream and **no decode benefit**, prot-int8's value is a modest capacity/density lever, not a speed or headline-memory lever. If a decode benefit is wanted, it requires a *fused* kernel that consumes INT8 directly (does not exist) — a separate, multi-week effort.

---

*Artifacts: `artifacts/prot_int8/{environment,baseline}.json`, `{byte_accounting,numerical_error,greedy_parity,quality_results,memory_results,performance_results}.csv`, `profiler_summary.json`, `test_results.txt`. Harness: `scripts/kvpro_prot_int8_validation/{numerical_ab,byte_accounting,perf_microbench,test_prot_int8_edges_cpu}.py`.*

*Phase 9 (contiguous-protection permutation experiment) was NOT run — it is a separate optimization and, per the brief, must not be conflated with the prot-int8 A/B result. It remains open for a dedicated GPU study.*
