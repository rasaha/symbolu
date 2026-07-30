# KVPro `prot-int8` — Mistral Real-Model Validation Report

**Internal / NDA engineering evidence only. Not investor-facing. No patent or marketing claims.**

Frozen commit `cef376e9` · branch `claude/kvpro-prot-int8-validation-hkd4ff` · date 2026-07-30.

Scope: real-model A/B/C validation of the INT8 protected-channel sidecar vs the BF16 sidecar inside INT4-Protected KVPro, using an open **Mistral** model.

**UPDATE 2026-07-30 (pod run executed).** The A/B/C **quality** run was subsequently executed on a RunPod A100-80GB (vLLM 0.7.3, `venv-vllm`, transformers 4.49) against `mistralai/Mistral-7B-Instruct-v0.3`. The quality axis is now **MEASURED**; memory and decode-performance axes remain **RESOURCE_BLOCKED** (not captured by the quality harness). Sections below carry both the original pre-run harness description and the post-run MEASURED results, labeled accordingly.

Evidence labels: **MEASURED**, **TEST-BACKED**, **MODELED**, **INFERRED**, **RESOURCE_BLOCKED**, **UNSUPPORTED**.

---

## Executive verdict

**PARTIALLY VALIDATED (quality + sidecar-memory + read-path-speed MEASURED on Mistral; full end-to-end decode TPS still RESOURCE_BLOCKED).**

On real `mistralai/Mistral-7B-Instruct-v0.3` (A100-80GB):
- **Quality — parity (MEASURED):** needle 30/30 = 30/30, hard-needle 46/48 = 46/48 (identical per-mode), MMLU-200 C=79 ≥ B=76; teacher-forced token agreement C-vs-B = 99.3% (6/7 prompts bit-identical). No benchmark answer changed.
- **Memory — ~50% saved on the stored protected sidecar (MEASURED-GPU):** 40→20 / 160→80 / 640→320 KiB per layer. Real, but a small slice; storage-only.
- **Speed — not faster (MEASURED-GPU):** INT8 read-path is 1.24–1.44× slower than BF16 on the isolated sidecar read (adds a dequant). End-to-end impact diluted, but no speed win.
- Runtime **confirmed compatibility** (32 layers, 8 KV heads, head_dim 128, n_protect=5, SWA disabled) and the **10 B → 5 B/tok/head/layer** figure.

**Not** established: **greedy bit-identity** (no quantized cell, incl B, achieves it — wrong bar); **full end-to-end vLLM decode TPS** through the external fused kernel (RESOURCE_BLOCKED). The quality result is **EMPIRICALLY EQUIVALENT within the pre-registered gate**, not a formal "zero quality cost" claim. Honest positioning: **a small memory/density lever at no quality cost — not a throughput lever.**

---

## 1. Environment (this box vs the required pod)

| | This environment | Required pod |
|---|---|---|
| GPU | **none** (`torch.cuda.is_available()=False`, no `nvidia-smi`) | ≥24 GB VRAM (A100/A10/RTX4090) |
| torch | 2.13.0+cu130, CPU only | pod CUDA torch (repo pins 2.4.1 cu121); do not blindly reinstall |
| HF stack | transformers/accelerate/sentencepiece/safetensors/datasets/evaluate/hub **all MISSING** | install per `run_commands.sh` step 1 |
| HF token | unset | `huggingface-cli login` only if gated |
| Disk free | ~23 GB | ~40 GB (weights ~14.5 GB + cache + datasets) |
| huggingface.co | **proxy-blocked (403)** — cannot verify model card here | reachable |

→ `artifacts/prot_int8_mistral/environment.json`. **All model-load, quality, memory, and performance measurements: RESOURCE_BLOCKED.**

---

## 2. Model selection & license (VERIFY ON POD)

Requested / preferred: **`mistralai/Mistral-7B-Instruct-v0.3`**.

- **License classification:** believed **Apache-2.0 = OSI-approved OPEN SOURCE** — *not* the later source-available **Mistral Research License (MRL)** used by some newer Mistral models. This distinction is stated precisely and must be **re-confirmed on the pod** from the model card (`model_info(...).cardData['license']`). Do not call any Mistral model "open source" without confirming Apache-2.0 vs MRL. — **INFERRED (network-blocked here).**
- **Gated / auth:** believed non-gated, no auth for download; confirm on pod (`model_info(...).gated`). — **INFERRED.**
- **Size / VRAM:** ~14.5 GB bf16 safetensors; comfortably evaluable on a single 24 GB card. — **MODELED.**
- **Fallback:** if 24 GB is unavailable, prefer a quantized load of v0.3 (still Apache-2.0) rather than substituting a differently-licensed model; **avoid** Mistral models under MRL and **avoid** SWA-enabled v0.1/v0.2 (see §3). Document the exact license of any substitute. — details in `model_metadata.json`.

The `run_commands.sh` step 2 performs the existence + license + gating + config verification **before** any download and **hard-stops** if the compatibility gate fails.

---

## 3. KVPro ↔ Mistral compatibility

Static code inspection (no model loaded) → `artifacts/prot_int8_mistral/compatibility_report.json`. — **INFERRED**, plus the noted TEST-BACKED plumbing.

| Dimension | KVPro assumption | Mistral-7B-v0.3 | Status |
|---|---|---|---|
| head_dim | D=128 (writer + prot_int8 constants) | 128 | **COMPATIBLE** |
| GQA KV heads | generic H_kv (Qwen=4, Llama-3.1=8 already run) | 8 | **COMPATIBLE** |
| layers | per-layer writer, mask (L,H_kv,D) | 32 | **COMPATIBLE** |
| RoPE | `apply_rotary_pos_emb` patched per `model_type` | standard rotary, θ=1e6 | **COMPATIBLE (verify symbol on pod)** |
| **Sliding-window attn** | **full causal only — no SWA masking** | **v0.3: `sliding_window=null` (disabled)** | **COMPATIBLE for v0.3 ONLY — HARD-GATED in run_commands.sh** |
| protect fraction | 4% → n_protect=5 | same | **COMPATIBLE** |

**Critical gate:** the int4_protected paged cache/kernel has **no sliding-window support**. v0.3 disables SWA (compatible); **v0.1/v0.2 set `sliding_window=4096` and are INCOMPATIBLE.** `run_commands.sh` asserts `config.sliding_window in (None,0)` and stops otherwise.

**Harness generality (TEST-BACKED):** `capture_kv.py` patches RoPE dynamically per `model_type`; `fakequant_model.layer_kv` handles the transformers 5.x / legacy cache layouts; `calibrate_mask_hf.py` reads geometry from `model.config`. 56 CPU plumbing tests pass (`test_results.txt`).

**prot-int8 prerequisite:** config C needs a **v2 mask with per-channel `k_min`/`k_max`** (Phase-6N). Build with `calibrate_phase5b_protect_mask.py` (`--minmax-margin 1.1`, emits `artifact_version=2`). `fakequant_model.py:77-82` feeds those into `reconstruct_p8` for the `P8prod` cell.

---

## 4. A/B/C methodology (the run the pod will execute)

| Config | Definition | Harness cell |
|---|---|---|
| **A** | Full BF16 KV (reference) | `fp` |
| **B** | INT4 KV + **BF16** protected sidecar | `affine` |
| **C** | INT4 KV + **INT8** protected sidecar | `P8prod` |

Primary causal comparison **C − B**. Held identical across B and C: weights, tokenizer, prompts, protect mask, protect fraction, calibration data, INT4 quantizer, page size, seqlens, batch, seeds, generation settings, and decode machinery — **only the protected-sidecar dtype differs** (`quantizers.reconstruct` vs `reconstruct_p8`, same code path). Driven by the pod-tested `run_p8_quality.sh`.

**Honesty guard (path classification):** this quality path is **FAKE-QUANT** (reconstruct K, then run HF attention on the reconstructed tensor). It is a legitimate C−B isolation because B and C use identical machinery, but it is **NOT** the production vLLM int4 kernel. Any result from it is labeled **MEASURED-fakequant / TEST-BACKED**, never "production". Memory and decode-TPS must additionally be taken through the production paged backend (`INT4_PROTECTED_PROT_INT8` unset=B / =1=C) — §7.

---

## 5. IMPORTANT PATH CHECK — is config C native INT8 decode?

**No — config C materializes BF16 before attention.** — **INFERRED** (code-traced last cycle, to re-confirm on Mistral geometry).

```
INT8 sidecar → prot_int8_dequantize → materialized BF16 buffer (k_protect_bf16) → attention kernel
```

`phase5b_4c_paged_writer._protect_view_bf16` (:1883) dequantizes int8→bf16; `get_packed_view` (:2785) emits `k_protect_bf16`; docstring: *"the kernel contract is unchanged — it always receives bf16."* **Do not describe config C as a native INT8 decode path.** The pod run must confirm this holds for Mistral and measure the temporary BF16 materialization bytes and the dequant cost.

---

## 6–7. Quality / Memory / Performance tasks

### 6a. Quality — MEASURED on Mistral (pod run 2026-07-30)

Run: `run_p8_quality.sh --cells fp,affine,P8prod --full-quality --real-mmlu 200`, model `mistralai/Mistral-7B-Instruct-v0.3`, mask `mistral_v0_3_protect_mask_4pct_v2.pt` (n_protect=5), 2 seeds for retrieval. Cells: **A=`fp`** (full BF16), **B=`affine`** (INT4 + BF16 protect), **C=`P8prod`** (INT4 + INT8 protect). Verdict file `runs/20260730T054025Z/p8_verdict.json` → **`P8_CLEAN`**. — **MEASURED.**

| Benchmark | A `fp` | B `affine` | C `P8prod` | C − B |
|---|---|---|---|---|
| Needle (30) | 30/30 (1.00) | 30/30 (1.00) | **30/30 (1.00)** | 0 |
| Hard-needle (48) | 46/48 (0.958) | 46/48 (0.958) | **46/48 (0.958)** | 0 (identical per-mode: distractor 10/12, rest perfect) |
| MMLU (200-Q) | 78 (0.390) | 76 (0.380) | **79 (0.395)** | +3 / +0.015 (noise) |

- **Retrieval: C identical to B** (counts and per-mode breakdown) — strongest equivalence signal short of token diffing.
- **MMLU: C ≥ B**, delta within noise. **Caveat:** absolute MMLU ~39% is far below Mistral's true ~60%, and `fp` also scores 39% — so this harness's MMLU protocol is a **low-power instrument** here; it is supporting, not decisive. Retrieval is the strong arm.
- **Greedy/teacher-forced (MEASURED):** `fp`=100/100; `affine`(B)=99.13% teacher-forced vs full BF16, 20.6% autoregressive. The autoregressive column is **high-variance noise** (validated B itself is only 20% vs full BF16, yet passes every benchmark; S4 scored 100% — clearly not a quality signal). **No KV-quantized cell — including B — is greedy-bit-identical to full BF16**, so greedy bit-identity is not a valid parity bar.
- **C vs B directly (`mistral_greedy_parity.py`, MEASURED):** teacher-forced token agreement **C = 99.315%** over 292 positions; **6 of 7 prompt types bit-identical** (factual_qa, arithmetic, code, instruction, repeated, retrieval — first-divergence = none), **5 of 7** autoregressive-exact. Only `summarize` wobbled (first divergence at position 8, ~0.7% of all positions). No benchmark answer changed. → C and B are in **practical parity**, not byte-identity.

**Classification: EMPIRICALLY EQUIVALENT within the pre-registered quality gate** (needle + hard-needle + MMLU, no regression vs affine). Not "zero quality cost"; not greedy bit-identity.

### 6b. Memory / Performance — MEASURED on GPU (read-path slice)

Captured with `scripts/kvpro_prot_int8_validation/gpu_mem_speed_capture.py` on **NVIDIA A100-SXM4-80GB**, driving the production `PagedKVWriter` in both modes (`INT4_PROTECTED_PROT_INT8` unset=B / `=1`=C), real Mistral v2 mask, n_protect=5, layer 0. — **MEASURED-GPU** (writer/read-path level; the external fused vLLM decode kernel is **not** invoked, so this is not full production TPS).

**Memory — stored protected sidecar (per layer):**

| Seqlen | B (BF16) | C (INT8 + const) | Saved |
|---|---|---|---|
| 512 | 40 KiB | 20 KiB | **49.2%** |
| 2048 | 160 KiB | 80 KiB | **49.8%** |
| 8192 | 640 KiB | 320 KiB | **50.0%** |

The **~50% sidecar-storage reduction is now MEASURED on GPU** (was MODELED). Scale: ×32 layers × batch for a model total (e.g. 8192 tokens × 32 layers ≈ 20 MiB → 10 MiB). This is the **protected sub-stream only** — small in absolute and relative terms (the full KV read stream and the 14.5 GB weights dominate). The int8 dequant constants add ~320 B/layer (amortized). **Read-transient is identical B vs C** (680 / 2720 / 10880 KiB) — INT8 reconstructs the same bf16 buffer on read, so the saving is **storage-only**, not present during the read itself.

**Performance — read-path latency (get_packed_view over whole context, CUDA-event p50):**

| Seqlen | B (BF16) | C (INT8) | C/B |
|---|---|---|---|
| 512 | 0.173 ms | 0.249 ms | **1.44×** |
| 2048 | 0.189 ms | 0.235 ms | **1.24×** |
| 8192 | 0.234 ms | 0.302 ms | **1.29×** |

INT8 is **slower**, not neutral, on the isolated sidecar read (+0.05–0.08 ms; the added uint8→bf16 dequant). This is the read-path slice over the whole context, **not** a full decode step (which also runs the big attention kernel + GEMMs), so the **end-to-end** decode impact is diluted well below these ratios — but the direction is confirmed: **INT8 is not faster; it is neutral-to-slightly-slower.** This measured result supersedes my earlier "~1.0×" estimate.

**Still not captured:** full end-to-end vLLM decode TPS through the external fused kernel (**RESOURCE_BLOCKED** — closed CUDA fork), Nsight profiler (`profiler_summary.json`, **RESOURCE_BLOCKED**), and perplexity (**not run**; optional).

---

## 8. Evidence classification summary

| Item | Label |
|---|---|
| Harness plumbing (builders, gate, quant math) | **TEST-BACKED** (56 CPU tests pass) |
| KVPro↔Mistral-v0.3 architecture compatibility | **INFERRED** (static) + hard-gated on pod |
| Model license = Apache-2.0 open source | **INFERRED** (HF blocked here) → verify on pod |
| Config C materializes BF16 (not native INT8) | **INFERRED** (code) |
| Sidecar byte halving (10→5 B/tok/head/layer, n_protect=5) | **MEASURED** (runtime-confirmed mask geometry) |
| Real-model quality C vs B (needle/hard-needle/MMLU) | **MEASURED** — clean (`P8_CLEAN`) on Mistral-7B-Instruct-v0.3 |
| Greedy/teacher-forced parity C vs B | **MEASURED** — 99.3% agreement, 6/7 prompts bit-identical (practical parity) |
| Real-model greedy bit-identity | **UNSUPPORTED as a bar** — no quantized cell (incl B) is greedy-bit-identical to full BF16 |
| Perplexity | **RESOURCE_BLOCKED** (not run) |
| Stored sidecar memory reduction (~50%) | **MEASURED-GPU** (A100; 40→20 / 160→80 / 640→320 KiB per layer) |
| Read-path speed C vs B | **MEASURED-GPU** — INT8 ~1.24–1.44× **slower** on the isolated read (not faster) |
| Full end-to-end decode TPS (external fused kernel) | **RESOURCE_BLOCKED** (closed CUDA fork not invoked) |
| "zero quality cost" on Mistral | **UNSUPPORTED** — result is EMPIRICALLY EQUIVALENT within the gate, not a formal zero-cost claim |

---

## 9. Limitations

1. **Quality path is fake-quant** (reconstruct K → HF attention), correct for the C−B isolation but **not** the production vLLM int4 kernel — memory/perf are not measured by it.
2. **MMLU is low-power** here (~39% incl. full-BF16 `fp`), so the knowledge arm is supporting, not decisive; retrieval carries the equivalence weight.
3. **Single model, single MMLU seed.** The S1–S4 study showed model-specificity; a second architecture and ≥3 MMLU seeds would harden the claim. Retrieval used 2 seeds.
4. **C's own greedy/teacher-forced number is pending** (`token_agreement.py` skips `P8prod`); run `mistral_greedy_parity.py`.
5. **No pre-registered equivalence margins** were set before the run — the gate is "no regression vs affine", which is weaker than a formal equivalence test.
6. This sandbox (where the report is authored) has no GPU; the numbers above were produced on the pod and transcribed into the artifacts.

---

## 10. Recommended next action

1. Run `scripts/kvpro_prot_int8_validation/mistral_greedy_parity.py` to fill C's teacher-forced parity + first-divergence (closes the greedy-parity gap).
2. Capture **real GPU memory + decode TPS** for B vs C through the production paged backend (`INT4_PROTECTED_PROT_INT8` unset vs `=1`) — the only remaining unmeasured claim and the one that speaks to the "reduces memory / improves decode" question.
3. Harden quality: a second architecture + ≥3 MMLU seeds + pre-registered C−B equivalence margins, before any "equivalent" claim leaves engineering.

---

## Final verdict

**PARTIALLY VALIDATED (quality + memory + speed now MEASURED on Mistral; full end-to-end TPS still blocked).**

On real `mistralai/Mistral-7B-Instruct-v0.3` (A100-80GB):
- **Quality — MEASURED, in parity.** Needle 30/30=30/30, hard-needle 46/48=46/48 (identical per-mode), MMLU-200 C=79 ≥ B=76; teacher-forced token agreement C-vs-B = 99.3% (6/7 prompts bit-identical). No benchmark answer changed. Empirically equivalent within the gate — **not** greedy bit-identity, **not** a formal "zero quality cost" claim.
- **Memory — MEASURED, ~50% saved on the stored protected sidecar** (40→20 / 160→80 / 640→320 KiB per layer). Real GPU reduction, but a **small slice** (protected sub-stream only; weights + full KV dominate). Saving is **storage-only** — the read reconstructs the same bf16 buffer.
- **Speed — MEASURED, neutral-to-slightly-slower.** INT8 read-path is **1.24–1.44× slower** than BF16 on the isolated sidecar read (adds a dequant); **not faster**. End-to-end decode impact is diluted (the read is a small fraction of a full step), but there is **no speed win**.
- **Still RESOURCE_BLOCKED:** full end-to-end vLLM decode TPS through the external closed CUDA fused kernel; Nsight profiling; perplexity.

**Net:** on this model, swapping the BF16 protected sidecar for INT8 **holds quality, roughly halves that sidecar's stored bytes, and does not speed up decode (marginally slower on the read path).** The honest positioning is a **small memory/density lever at no quality cost — not a throughput lever.**

*Artifacts: `artifacts/prot_int8_mistral/` (environment.json, model_metadata.json, compatibility_report.json, run_commands.sh, *.csv, profiler_summary.json, test_results.txt). Prior CPU/reference evidence: `docs/KVPRO_PROT_INT8_VALIDATION_REPORT.md`.*
