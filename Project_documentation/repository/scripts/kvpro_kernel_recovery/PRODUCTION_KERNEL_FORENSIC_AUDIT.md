# KVPro — production INT4 decode kernel: FORENSIC AUDIT + recovery decision

> **Source-recovery gate → `SOURCE_RECOVERED_EXACT`. Decision → `OPTIMIZE_RECOVERED_PRODUCTION_KERNEL`.**
> The shipped kernel is the public vLLM flash-attention fork @ `720c948` + an **additive in-repo INT4
> patch set**; the base is a public pinned SHA and the INT4 source lives in this repo's
> `apply_phase*_patches.py`, with a documented reproducible build. The kernel **already has native paged
> gather + split-K + online softmax + GQA**; the measured ~15% gather + ~6% copy are a **host-side gather
> of the INT4 side-channels** that the kernel's existing paged machinery can absorb. Recovering and
> extending that kernel is cheaper and safer than rebuilding the production contract. **No kernel
> implemented — this is the plan + gate only.**

Companion machine-readable artifacts (same dir): `kernel_provenance.json`, `kernel_contract.json` +
`kernel_contract.schema.json`, RunPod scripts `00–03` + `run_recovery_audit.sh`, `validate_kernel_contract.py`.

---

## Phase A — provenance  [source-confirmed (in-repo patches) + binary-confirmed (documented build)]

| Field | Value | Evidence |
|---|---|---|
| Base repo | `github.com/vllm-project/flash-attention` | RUNBOOK, VC_BRIEF, README (×5 docs) |
| Base SHA | **`720c94869cf2e0ff5a706e9c7f1dce0939686ade`** (`720c948`, 2025-02-06) — vLLM 0.7.3-pinned | `KERNEL_6C3C_RUNBOOK.md:23` |
| INT4 source | **additive, IN-REPO**: `apply_phase*_patches.py` | patch bodies read directly |
| Files added | `int4_inline.h`, `int4_packed_load.h`, `flash_fwd_split_hdim128_bf16_int4kv{,_packed}_sm80.cu` | `apply_phase2_3_patches.py`, CODEREAD |
| Files modified | `flash_fwd_kernel.h`, `flash_fwd_launch_template.h`, `flash.h`, `flash_api.cpp`, `flash_api_torch_lib.cpp` | CODEREAD:156–256 |
| Torch op | `torch.ops._vllm_fa2_C.fwd_kvcache_int4` → `mha_fwd_kvcache_int4` | `apply_phase2_4_1a_patches.py:360` |
| Build | `TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 NVCC_THREADS=2 python setup.py bdist_wheel` | RUNBOOK:32 |
| Wheel | `vllm_flash_attn-2.7.2.post1+cu128-cp312-…whl` (~200 MB) | RUNBOOK:34 |
| Env | A100-80GB · CUDA 12.8 · torch 2.5.1+cu124 · py3.12 · vLLM 0.7.3 (V0) | RUNBOOK:30 |
| Build result | **GREEN 2026-05-20** (48 min, 198 steps; smoke PASS) | RUNBOOK:32–44 |

Full detail (recoverability matrix, SHAs, hashes) → `kernel_provenance.json`.

## Phase B — pod verification  [hardware-untested this session]

`run_recovery_audit.sh` (POD, `PYBIN=/workspace/venv-vllm/bin/python3`) inspects the *live* environment
and rolls up the gate from what the pod actually has: kernel importable (`fwd_kvcache_int4` op present) ·
base checkout at `720c948` present · wheel provenance match. Read-only metadata only (imports, `.so`
hashes, exported symbol names, dist-info) — **no binary reverse-engineering**. Every probe prints
`NOT_FOUND` rather than guessing.

## Phase C — contract  [code-traced]

`kernel_contract.json` freezes every argument (shape · dtype · role · ownership · lifetime · batch/paged/
GQA/partial-tail semantics · scale-`xmin` granularity · protected-sidecar mapping · output). Load-bearing
invariants, CPU-enforced by `validate_kernel_contract.py` (16/16 tests):
`S = n_blocks·BS` · packed last dim `= D/2` · `H_q % H_kv == 0` · **protect sidecar `= n_protect ≪ D`
(compact)** · K group `= BS` · `D % v_group_size == 0` · **the positional `k_cache` is a bf16 DUMMY
(content unused)**. This validator is the K1 gate: candidate/rebuilt inputs must pass it before any number
is trusted.

## Phase D — source-recovery gate → `SOURCE_RECOVERED_EXACT`

The kernel is reconstructible exactly as **(public base @ `720c948`) + (in-repo `apply_phase*_patches.py`)**
with the documented build. The only "pending" is a pod re-verification (Phase B) that the SHA still fetches,
patches apply, and the wheel rebuilds byte-comparably — a *confirmation*, not a recovery gap.

### Read-only architectural audit of the recovered source

| Component | Where | Notes |
|---|---|---|
| Paged gather | `GmemTiledCopyQKVPaged` (CUTLASS atom, `flash_fwd_kernel.h:~499`) | **native block-table paging already present** for the main KV |
| K/V unpack | `int4_packed_load.h` | packed-nibble load (2 ch/byte) |
| Scale/`xmin` dequant | `int4_inline.h` + packed side-channel | per-block K affine, per-token/group V affine |
| Compact-protect overlay | `k_packed_protect_bf16` + `protect_slot` | n_protect bf16 channels overlaid on dequant |
| QK tiling · softmax · PV | inherited flash-attn `compute_attn_1rowblock_splitkv` | online softmax, register/smem tiling |
| Split-K + combine | `num_splits` (flash-decoding) | present |
| GQA | flash-attn `h_h_k_ratio` | present |

**Ranked optimization surfaces (by measured/architectural leverage):**
1. **In-kernel paged gather of the INT4 side-channels — HIGH.** The kernel already pages the main KV, but
   the INT4 read path (`_read_decode_packed_batched`) gathers `k_packed_int4/scale/xmin/protect_bf16`
   **host-side** (`get_packed_view_batched`) into a contiguous view and passes that. Extending the existing
   paged copy atoms to the INT4 side-channels (consume `block_table` directly) removes the **~15% gather +
   ~6% copy** measured in 6M.4. This is an *extension of the recovered kernel*, not a rewrite.
2. **In-kernel dequant/unpack (part of the ~29%) — LOW/bounded.** Inherent to INT4 reconstruction (6M.4:
   "already cheap / at its bound"); little marginal room.
3. **Split-K/combine + GQA tiling — LOW.** Flash-attn internals, already tuned; `ncu`-blocked so
   unmeasured — do not speculate.

## Phase E — in-repo replacement feasibility (secondary; source IS recovered)

For completeness — why *rebuilding* in the in-repo Triton kernel is the worse path:

| Capability | Production external kernel | In-repo Triton kernel (as written) | Gap |
|---|:--:|:--:|---|
| Route-C packed K/V | ✅ | ✅ (route-A adapter) | reuse |
| Compact protected sidecar | ✅ | ⚠️ reads full fp16 K (route-A) | rework read |
| Paged block tables | ✅ (`GmemTiledCopyQKVPaged`) | ❌ (synthetic contiguous) | **build paging** |
| Batching | ✅ | ⚠️ single-seq focus | build |
| Mixed seq lengths | ✅ | ❌ | build |
| Partial blocks | ✅ (writer splice + mask) | ⚠️ | build |
| GQA | ✅ | ✅ (G_PAD) | reuse |
| Split-K | ✅ | ✅ | reuse |
| Online softmax | ✅ | ✅ | reuse |
| Exact output semantics | ✅ (oracle-locked) | ⚠️ cosine ~0.999 | re-lock |
| Snapshot/WarmTier compat | ✅ | ❌ | build |
| vLLM integration | ✅ (installed op) | ❌ | build |

- **Minimum correctness-equivalent replacement:** rebuild paging + batching + mixed-len + vLLM integration ≈
  *most of the production contract* — multi-week, high test burden, high hardware risk.
- **Performance-optimized replacement:** strictly more.
- **Verdict:** rebuilding re-implements capabilities the recovered kernel already ships. **No TPS claim.**

## Phase F — decision → `OPTIMIZE_RECOVERED_PRODUCTION_KERNEL`

Satisfies the rule: exact source recovered ✅ · ≥1 removable component plausibly justifies work (the ~21%
host gather+copy, absorbable by the kernel's existing paged path) ✅ · source builds reproducibly ✅. It is
the option that is both **actionable** (we own base @ known SHA + in-repo patches) and **measurement-
supported**, and it avoids rebuilding a contract the kernel already satisfies.

**Honest ceiling (unchanged, do not oversell):** even fully removing gather+copy projects to ~16–19%
aggregate — a **net loss vs bf16 remains** (~0.22× → ~0.26–0.30×); the ~66% model GEMMs and the inherent
INT4 reconstruction are untouched. This is a bounded, multi-week recovery, **not** throughput parity. The
strategic alternatives (`PIVOT_TO_INT8_KV`, `POSITION_INT4_AS_CAPACITY_ONLY`) remain the business fork if a
bounded recovery is not worth the maintenance of a V0-pinned fork.

## Phase G — correctness-first milestone plan (plan only; no implementation)

- **K0 — Reproducible build.** Reclone base @ `720c948`; apply `apply_phase*_patches.py`; build
  `TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16` → wheel; import gate (`fwd_kvcache_int4` op present);
  `sha256` manifest of the `.so` (`02_hash_installed_kernel.py`); A100 smoke vs the RUNBOOK baselines
  (FA p50@16k ±10%, Cell A@32k ±5%). **Gate:** GREEN + hash recorded.
- **K1 — Numerical contract.** Feed identical packed K/V + exact scale/`xmin` + compact sidecar + block
  tables + partial tails + batching + mixed lengths + GQA through `validate_kernel_contract.py`, then
  compare candidate vs current op: **max-abs · rel-err · cosine** on attention logits, softmax, and final
  output. **Gate:** cosine ≥ 0.999 and byte-eq where the current path is byte-eq.
- **K2 — Production integration.** No fallback to route-A; no hidden bf16 K backing; no silent Python-ref
  fallback; scheduler + block-table semantics preserved. **Gate:** end-to-end generation char-identical to
  the current shipped path.
- **K3 — Performance gate (measured, per ctx 4K/16K/32K).** current external kernel vs candidate vs bf16:
  kernel time, gather/copy time, aggregate + per-seq TPS, p95, max concurrency, memory. **No modeled TPS.**
- **K4 — Product gate. Continue only if:** correctness passes · **aggregate TPS ≥ +15% vs current Route-C**
  · quality unchanged · no density regression · no saturation regression. Otherwise stop and re-evaluate
  the strategic fork.

## Honest status

| Item | Status |
|---|---|
| Base fork repo + SHA `720c948` | **source-confirmed** (documented, multiply-corroborated); public fetch not re-verified this session |
| INT4 patch source (`apply_phase*_patches.py`) | **source-confirmed** (read in-repo) |
| Build recipe + wheel `2.7.2.post1+cu128` | **binary-confirmed** (documented GREEN 2026-05-20); not rebuilt this session |
| Kernel contract | **code-traced**; CPU-validated (16/16); not executed |
| Kernel internals (QK/PV/split-K %) | **inferred** from source map; `ncu`-blocked → no measured sub-split (not fabricated) |
| Pod artifacts on THIS container | **unavailable** (fresh container) → run Phase B to confirm |
| All timing/perf numbers | **hardware-untested this session**; 6M.4 shares are prior-measured, cited |

## Exact next RunPod commands

```bash
cd /workspace/symbolu && git pull origin claude/kvpro-v2-tier1-d8b4ae
# Phase B — confirm what THIS pod has (source? binary? wheel match?):
export PYBIN=/workspace/venv-vllm/bin/python3
bash scripts/kvpro_kernel_recovery/run_recovery_audit.sh
cat scripts/kvpro_kernel_recovery/runs/recovery_verdict.json
git add -f scripts/kvpro_kernel_recovery/runs/*.json     # record the pod's actual state

# CPU contract self-check (any env):
python3 scripts/kvpro_kernel_recovery/test_contract_cpu.py            # 16/16
python3 scripts/kvpro_kernel_recovery/validate_kernel_contract.py --demo

# If recovery_verdict != SOURCE_RECOVERED_EXACT, K0 rebuild (separate workspace, NOT /workspace/symbolu):
#   git clone https://github.com/vllm-project/flash-attention /workspace/dev/vllm-flash-attn-dev
#   git -C /workspace/dev/vllm-flash-attn-dev checkout 720c94869cf2e0ff5a706e9c7f1dce0939686ade
#   python CTM_plus/Bench/scripts/apply_phase2_2_patches.py   # + 2_3, 2_4_1a (apply the INT4 path)
#   TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 python setup.py bdist_wheel && install_dev_vllm_flash_attn.sh
```

**Constraints honored:** no Route-A timings for production; no full-BF16-K claim; no kernel implemented
before the recovery gate; no fabricated kernel-internal attribution; packaging the binary is not treated as
an optimization; modeled ≠ measured; mechanism specifics kept at the repo's existing documentation level.
Existing tests green; committed clean; no PR.
