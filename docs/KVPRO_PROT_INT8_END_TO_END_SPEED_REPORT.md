# KVPro `prot-int8` — End-to-End Decode Speed: BF16 vs INT8 Protected Sidecar (B vs C)

**Internal / NDA engineering evidence only. Not investor-facing. No patent/marketing claims.**

Branch `claude/kvpro-prot-int8-validation-hkd4ff`. Narrow question: **does swapping the BF16 protected sidecar (B) for INT8 (C) change real end-to-end decode speed** in KVPro, holding everything else identical? Primary comparison **C vs B** (full BF16 KV is *not* the baseline here).

Evidence labels: **MEASURED, TEST-BACKED, MODELED, INFERRED, RESOURCE_BLOCKED, UNSUPPORTED.**

---

## 1. Executive verdict

**C SLOWER THAN B — end-to-end decode TPS reduced by ~3.45% on average (range −1.9% to −5.5%). MEASURED-GPU on A100-80GB, all confounder guards passed.**

Real vLLM `int4_protected` decode path (not fake-quant, not the isolated read-path). INT8 protection (C) was **consistently a little slower** than BF16 protection (B) — never faster. The slowdown is **small and shrinks as load grows** (the heaviest point, ctx 8192 / batch 8, was within the neutral band). This confirms the going-in expectation: C dequantizes INT8→BF16 into the same buffer the kernel already consumed, so it adds a little decode work and removes none.

| ctx / batch / gen | B decode TPS | C decode TPS | ratio C/B | Δ | verdict |
|---|---|---|---|---|---|
| 2048 / 1 / 128 | 12.8 | 12.1 | 0.945 | −5.5% | SLOWER |
| 2048 / 8 / 128 | 69.6 | 67.2 | 0.966 | −3.4% | SLOWER |
| 8192 / 1 / 128 | 11.8 | 11.4 | 0.966 | −3.4% | SLOWER |
| 8192 / 8 / 128 | 41.3 | 40.5 | 0.981 | −1.9% | NEUTRAL |
| **mean** | | | **0.9655** | **−3.45%** | **SLOWER** |

**Guards (all passed):** C `prot_int8 active = 32/32` layers (INT8 genuinely engaged); both cells `decode_calls_packed>0` with **0 decode fallbacks** and **0 write fallbacks**; CV 0.4–1.8% (< 5%); **prefill/TTFT near-identical** B vs C (169.6/172.3, 4938.4/4937.0 ms) — so the write-path concern did **not** materialize and the effect is purely decode-side.

**Practical magnitude:** INT8 protection reduced end-to-end decode TPS by **3.45% on average, just outside the ±3% neutral band → C SLOWER THAN B**, but the effect is modest and load-dependent. Combined with the prior results: **INT8 holds quality, roughly halves the protected-sidecar storage, and costs a few % of decode throughput.** It is a small memory/density lever with a small throughput cost — **not** a speed win.

**Do NOT conflate:** the isolated read-path microbench (1.24–1.44× slower on `get_packed_view` alone) is a narrow op; the **end-to-end** slowdown is only ~3.45% because the attention kernel + GEMMs dominate a real decode step.

**Caveat:** measured with `enforce_eager=True` (CUDA graphs OFF, the validated path). CUDA-graph mode is a separate axis, not tested.

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

## 7–13. Results — MEASURED (A100-80GB, vLLM 0.7.3, `benchmark_matrix.csv`)

**Prefill / TTFT:** near-identical B vs C (169.6/172.3 ms at ctx2048/b1; 1261.7/1276.7 at b8; 623.9/622.6 at ctx8192/b1; 4938.4/4937.0 at b8). Enabling INT8 did **not** penalize prefill (`write_path_fallback = 0`). — **MEASURED.**

**Decode (primary):** `speed_ratio = C/B` = 0.945 / 0.966 / 0.966 / 0.981 → **mean 0.9655 (−3.45%)**. Slower at every point; the only NEUTRAL point is the heaviest (ctx8192/b8). `latency_ratio` is the inverse (~1.02–1.06×). Absolute TPS in the table above. — **MEASURED.**

**Throughput scaling:** batch 8 lifts TPS ~5× over batch 1 (both cells), and the C/B gap narrows with batch/context — the fixed per-read dequant is diluted by heavier attention/GEMM work. — **MEASURED.**

**Memory:** end-to-end process memory is dominated by 13.5 GB weights + KV cache; the INT8 sidecar storage saving (~50%, prior MEASURED result) is a small fraction of the total. Per-run peak/reserved are in `raw_B.json`/`raw_C.json` `matrix[]`. — **MEASURED / MODELED.**

**Profiler:** call_stats captured (`decode_calls_packed=60960`, 0 fallbacks both cells). Sub-kernel Nsight attribution not run (external closed kernel; `ERR_NVGPUCTRPERM` per prior audits). — **MEASURED (call_stats) / RESOURCE_BLOCKED (Nsight).**

**Quality sanity:** output length pinned (`min_tokens=N, ignore_eos`) so B and C did identical decode work; both packed, no fallbacks — the speed comparison is not distorted by early termination. — **MEASURED.**

**Statistics:** CV 0.4–1.8% (all < 5%, none flagged noisy). Points classified by ±3% band + CI-excludes-parity; 3 SLOWER, 1 NEUTRAL. — **MEASURED.**

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

**C SLOWER THAN B.** INT8 protection reduced end-to-end decode TPS by **3.45% on average** (range −1.9% to −5.5%; 3 of 4 workloads outside the ±3% neutral band, the heaviest workload within it). MEASURED on A100-80GB via the real vLLM `int4_protected` path with all confounder guards passing (INT8 active 32/32, 0 fallbacks, CV < 2%, prefill unchanged). The slowdown is small and load-dependent, and far smaller than the isolated read-path ratio (1.24–1.44×) because attention/GEMM work dominates a full decode step. **INT8 protection is not a decode speed win; it is a small, consistent decode cost** — the honest positioning remains: quality-neutral, ~50% smaller protected-sidecar storage, ~3% decode-throughput cost.

*Confirmatory follow-ups (optional): the full matrix (`run_commands.sh`) and CUDA-graph mode (`--no-enforce-eager`), the one untested axis. Artifacts: `artifacts/prot_int8_speed/` (benchmark_matrix.csv, decode_results.csv, end_to_end_results.csv, memory_results.csv, quality_sanity.csv, runtime_path.json, run_commands.sh; raw per-run JSON on the pod). Harness: `scripts/kvpro_prot_int8_validation/e2e_decode_bench.py`.*
