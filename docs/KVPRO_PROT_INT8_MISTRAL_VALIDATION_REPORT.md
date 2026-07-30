# KVPro `prot-int8` — Mistral Real-Model Validation Report

**Internal / NDA engineering evidence only. Not investor-facing. No patent or marketing claims.**

Frozen commit `cef376e9` · branch `claude/kvpro-prot-int8-validation-hkd4ff` · date 2026-07-30.

Scope: real-model A/B/C validation of the INT8 protected-channel sidecar vs the BF16 sidecar inside INT4-Protected KVPro, using an open **Mistral** model. This report documents the **compatibility assessment, the complete run harness, and the artifacts** prepared for the pod. It does **not** contain real-model measurements, because this environment has **no GPU and no model** — those are RESOURCE_BLOCKED and must be produced on the pod via `artifacts/prot_int8_mistral/run_commands.sh`.

Evidence labels: **MEASURED**, **TEST-BACKED**, **MODELED**, **INFERRED**, **RESOURCE_BLOCKED**, **UNSUPPORTED**.

---

## Executive verdict

**RESOURCE_BLOCKED** — the experiment harness is complete and the compatibility gate is defined and code-verified, but the decisive real-model run cannot be executed in this CPU-only environment. Run `run_commands.sh` on the GPU pod to produce the A/B/C evidence.

Nothing here should be read as a real-model result. The only positive claims that survive this environment are the harness-plumbing tests and the static compatibility analysis.

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

## 6–7. Quality / Memory / Performance tasks (all RESOURCE_BLOCKED here)

The full task matrix (greedy parity, logit comparison, perplexity, needle/hard-needle retrieval, representative prompts, memory, performance) is wired into `run_commands.sh` and the CSV templates. Every artifact currently carries a `RESOURCE_BLOCKED` row:

- `greedy_parity.csv`, `logit_comparison.csv` — need model forward passes.
- `perplexity_results.csv` — suggests wikitext-2-raw-v1; record exact n_samples + context_len on the pod.
- `retrieval_results.csv` — needle + hard-needle via the repo drivers.
- `memory_results.csv` — real `torch.cuda` allocated/reserved/peak on the pod; sidecar halving (2 B→1 B, 10 B→5 B/tok/head/layer at n_protect=5) is **MODELED** here; effective density ≈2.94% of the read stream at 4% is **MODELED**.
- `performance_results.csv` — prefill/decode latency, TPS, kernel launches; the int8→bf16 dequant cost is **INFERRED nonzero** (CPU proxy last cycle: 3–4× vs bf16 passthrough), GPU value RESOURCE_BLOCKED.
- `profiler_summary.json` — Nsight/torch-profiler RESOURCE_BLOCKED.

---

## 8. Evidence classification summary

| Item | Label |
|---|---|
| Harness plumbing (builders, gate, quant math) | **TEST-BACKED** (56 CPU tests pass) |
| KVPro↔Mistral-v0.3 architecture compatibility | **INFERRED** (static) + hard-gated on pod |
| Model license = Apache-2.0 open source | **INFERRED** (HF blocked here) → verify on pod |
| Config C materializes BF16 (not native INT8) | **INFERRED** (code) |
| Sidecar byte halving (10→5 B/tok/head/layer) | **MODELED** here (MEASURED as tensor bytes last cycle) |
| Real-model greedy parity / quality / PPL / retrieval | **RESOURCE_BLOCKED** |
| Real GPU memory & decode performance | **RESOURCE_BLOCKED** |
| "zero quality cost" on Mistral | **UNSUPPORTED** (no run) |

---

## 9. Limitations

1. No GPU / no model / HF blocked → no real-model numbers producible here.
2. Compatibility is static-inferred; the SWA and RoPE-symbol gates must pass on the pod.
3. Quality path is fake-quant; production memory/perf need the vLLM int4 backend.
4. License/config values are best-known, not fetched — the pod gate is authoritative.

---

## 10. Recommended next action

1. On the pod: run `artifacts/prot_int8_mistral/run_commands.sh`. It verifies model/license/SWA **before** download, builds the v2 mask, runs A/B/C quality (quick then full), and points at the memory/perf capture.
2. Fill the CSVs and re-issue this report with **MEASURED** rows and pre-registered equivalence margins for C−B.
3. Only then classify Mistral quality; until then it is **RESOURCE_BLOCKED**, not "zero cost".

---

## Final verdict

**RESOURCE_BLOCKED** — harness complete and compatibility-gated; decisive real-model execution not possible in this environment. No real-model validation is claimed.

*Artifacts: `artifacts/prot_int8_mistral/` (environment.json, model_metadata.json, compatibility_report.json, run_commands.sh, *.csv, profiler_summary.json, test_results.txt). Prior CPU/reference evidence: `docs/KVPRO_PROT_INT8_VALIDATION_REPORT.md`.*
