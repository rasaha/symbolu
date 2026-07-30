# KVPro `prot-int8` — End-to-End Decode Speed: BF16 vs INT8 Protected Sidecar (B vs C)

**Internal / NDA engineering evidence only. Not investor-facing. No patent/marketing claims.**

Branch `claude/kvpro-prot-int8-validation-hkd4ff`. Narrow question: **does swapping the BF16 protected sidecar (B) for INT8 (C) change real end-to-end decode speed** in KVPro, holding everything else identical? Primary comparison **C vs B** (full BF16 KV is *not* the baseline here).

Evidence labels: **MEASURED, TEST-BACKED, MODELED, INFERRED, RESOURCE_BLOCKED, UNSUPPORTED.**

---

## 1. Executive verdict

**RESOURCE_BLOCKED (in this authoring environment) — harness complete and validated; the decisive end-to-end run executes on the GPU pod via `artifacts/prot_int8_speed/run_commands.sh`.**

This report is authored in a CPU-only sandbox (no GPU, no vLLM), so it contains **no end-to-end timings yet**. What is delivered: the real-path benchmark (`scripts/kvpro_prot_int8_validation/e2e_decode_bench.py`), the runtime-path trace, the methodology, and confounder guards. The pod run fills the results and the final verdict (one of C FASTER / C NEUTRAL / C SLOWER / MIXED / RESOURCE BLOCKED).

**Prior, related MEASURED facts (do not conflate with this experiment):**
- Isolated **read-path** microbench: INT8 was **1.24–1.44× slower** on `get_packed_view` alone (MEASURED-GPU, A100). That is a narrow op, **not** the full decode step — do **not** infer the model is 24–44% slower.
- Quality C≈B (parity), sidecar storage ~50% smaller (both MEASURED on Mistral).

**Expectation to test (INFERRED, must be measured):** because C dequantizes INT8→BF16 into the same buffer the decode kernel already consumed, the decode kernel workload is byte-identical B vs C; the only added decode work is the small per-read dequant. So end-to-end decode is expected **neutral-to-slightly-slower**, with the read-path 1.24–1.44× diluted by the attention kernel + GEMMs. A separate **prefill** confounder exists (C disables the CUDA K-write kernel → Python quantize on write), so prefill may move more than decode — measured separately.

---

## 2. Exact B/C definitions

| | B (control) | C (treatment) |
|---|---|---|
| Main KV | INT4-Protected | INT4-Protected (identical) |
| Protected mask | fixed v2 Mistral mask (n_protect=5) | **same mask** |
| Protected values | **BF16** sidecar | **INT8** (static-asym uint8) sidecar |
| Flag | `INT4_PROTECTED_PROT_INT8` unset | `INT4_PROTECTED_PROT_INT8=1` |
| Kernel | `flash_attn_with_int4_kvcache` | same kernel (receives bf16 either way) |

Only the protected-sidecar representation differs. Everything else (weights, tokenizer, prompts, pinned output length, calibration artifact, INT4 quantizer, scales, page/block size, batch, scheduler, TP, CUDA-graph mode, warmup, repetitions) is held constant.

---

## 3. Runtime-path trace

Full trace in `artifacts/prot_int8_speed/runtime_path.json` (INFERRED from source; confirmed live via `call_stats` on the pod). Key point — **C materializes a BF16 buffer before attention** (`_protect_view_bf16` → `prot_int8_dequantize` → `k_protect_bf16`; kernel contract bf16 either way, `phase5b_4c_paged_writer.py:1886`). Confounder: enabling INT8 **disables the CUDA K-write kernel** (`:1003`) → Python quantize on the **write/prefill** path. The harness measures prefill and decode separately and records `write_path_fallback` to expose this.

---

## 4. Hardware & software environment

Authoring sandbox: CPU-only (no CUDA). Pod (from prior study, to be re-recorded by the harness into `environment.json`): **NVIDIA A100-SXM4-80GB**, vLLM **0.7.3**, `venv-vllm`, transformers **4.49**, model `mistralai/Mistral-7B-Instruct-v0.3` (local `/workspace/models/…`), v2 mask `mistral_v0_3_protect_mask_4pct_v2.pt` (32 layers, 8 KV heads, head_dim 128, n_protect=5, SWA disabled). — **MEASURED on pod / RESOURCE_BLOCKED here.**

---

## 5. Benchmark methodology

- **Real path:** `Int4ProtectedLLM` (vLLM + forked int4 decode kernel). Not fake-quant, not the read-path microbench.
- **One engine per process** (`--cell off` = B, `--cell on` = C) → no cross-engine vLLM global-state leakage; `--compare` emits ratios + verdict.
- **Prefill/decode separation (no vLLM internals):** differential timing — `t1 = generate(max_tokens=1)` (≈ TTFT), `tN = generate(max_tokens=N)`; `decode_time = tN − t1`, `decode_tps = (N−1)·batch / decode_time`.
- **Pinned output length** (`min_tokens=N, ignore_eos=True`) so B and C do identical decode work.
- **Warmup 10, measured 30** per point (configurable).
- **Confounder guards (reported):** C `prot_int8 active==total` layers; both cells `decode_calls_packed>0` and `decode_calls_fallback==0`; `write_path_fallback` surfaced; `enforce_eager` recorded.
- **Statistics:** mean/median/std/P95/95%CI/CV per point; CV>5% flagged noisy; ±3% neutral band (engineering gate, not a statistical law); a point is NEUTRAL if |Δ|≤3% or the CI does not exclude parity.

---

## 6. Test matrix

Context lengths {512, 2048, 8192 (+16384 if memory permits)} × output {64, 256 (+512 where practical)} × batch {1, 4, 8, +max stable}. Six prompt types (factual, summarize, code, arithmetic, retrieval, repeated). Same prompt content for B and C. → `benchmark_matrix.csv`.

---

## 7–13. Results (prefill / decode / throughput / memory / profiler / quality / statistics)

**RESOURCE_BLOCKED here** — produced by the pod run into:
`prefill_results.csv`, `decode_results.csv`, `end_to_end_results.csv`, `memory_results.csv`, `quality_sanity.csv`, `profiler_summary.json`, `benchmark_matrix.csv`, `raw_timings.jsonl`. Primary metric: `speed_ratio = C_decode_tps / B_decode_tps`; also `latency_ratio`, with absolute timings. Quality sanity (fixed output length, first-divergence, exact-token agreement) confirms the speed comparison isn't distorted by early termination.

---

## 14. Confounders

1. **Write-path asymmetry:** C disables the CUDA K-write kernel → Python quantize on prefill. Mitigated by separating prefill from decode and reporting `write_path_fallback`.
2. **CUDA graphs off** (`enforce_eager=True`, matches the validated path). Graph-capture mode is a separate axis; prot_int8 ops are capture-safe per code but untested here.
3. **Silent bf16 fallback** would fake parity — guarded by the `prot_int8 active==total` and `decode_calls_packed>0 / fallback==0` checks. If a guard fails the verdict is tagged CONFOUNDER.
4. **External closed kernel:** sub-kernel attribution (Nsight) may be blocked (`ERR_NVGPUCTRPERM`); then profiler evidence is INFERRED/RESOURCE_BLOCKED.

---

## 15. Limitations

- Prompts are filler-padded to approximate context length (actual token count reported), not natural long-context documents.
- Differential (t1 vs tN) prefill/decode split assumes stable prefill cost across the two calls; validated by low CV.
- Single GPU, single model; results may not generalize across hardware/architectures.

---

## 16. Claims that will be SAFE (after the pod run)

- A measured `speed_ratio` with CI and neutral-band classification, per workload — e.g. "INT8 changed end-to-end decode TPS by X%, [within/outside] the ±3% band."
- Whether the fused decode kernel fired for both cells (no fallback) — a real-path guarantee.

## 17. Claims that are NOT SAFE

- ✗ "INT8 is 24–44% slower end-to-end" (that was the isolated read-path only).
- ✗ Any end-to-end speed claim before the pod run — currently RESOURCE_BLOCKED.
- ✗ Extrapolating CUDA-graph-mode behavior from the eager-mode run.

## 18. Recommended next step

Run `artifacts/prot_int8_speed/run_commands.sh` on the pod (smoke first — verify guards — then full sweep), then re-issue this report with the MEASURED tables and the final verdict.

---

## Final verdict

**RESOURCE BLOCKED** (this environment) — harness complete and its analysis logic validated; the decisive end-to-end B/C decode measurement runs on the pod. Expected direction (INFERRED, to be confirmed): **neutral-to-slightly-slower**, not a speed win, and far smaller than the isolated read-path 1.24–1.44×.

*Artifacts: `artifacts/prot_int8_speed/` (runtime_path.json, run_commands.sh; results CSV/JSON produced by the pod run). Harness: `scripts/kvpro_prot_int8_validation/e2e_decode_bench.py`.*
