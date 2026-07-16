# KVPro V3 — Step-0: decode profiling + protected-INT8 quality gate

**Goal:** measure the current decode path on a real GPU and decide which *removable* cost dominates —
gather/staging, splice, protect-scatter, dequant, or attention proper — **before** committing to a kernel
project. In parallel, a fake-quant quality arm (P8) tests whether protected-K can be stored INT8. This does
**not** implement any production kernel and does **not** modify production behavior.

**Hard rules honored:** profile first (no assuming gather *or* protect dominates); never fabricate Nsight
counters (blocked → `UNAVAILABLE`); never call modeled bytes a measured TPS; keep S2/xmin orthogonal;
evaluate P8 independently before combining with S2.

## Deliverables → files
| # | Deliverable | File |
|---|-------------|------|
| 1 | Decode-pipeline map (cited) | `DECODE_PIPELINE_MAP.md` |
| 2 | Env / prerequisite report | `00_env_gate.sh` → `env_gate.json` |
| 3 | Profiling scripts | `01_profile_nsys.sh` `02_profile_ncu.sh` `03_profile_cuda_events.sh` |
| — | Route-A input builder (Part A) | `route_a_builder.py` (writer-faithful packed view) |
| — | Mandatory correctness gate (Part B) | `06_correctness_gate.py` → `correctness.json` (gates profiling) |
| — | Frozen decision thresholds (Part E) | `DECISION_THRESHOLDS.md` |
| 4 | Parsed profile (JSON+CSV) | `04_parse_profile.py` → `stage_summary.{json,csv}` |
| 5 | Bottleneck table | `stage_summary.*` (per-stage % of kernel time) |
| 6 | Protected-INT8 harness + quality | `../../experiments/kvpro_v3_symmetric_residual/{protected_int8.py,p8_gate.py,run_p8_quality.sh}` |
| 7 | Cost accounting + 2 ceilings | `cost_accounting.py` → `cost_accounting.json` |
| 8 | Decision matrix + 1 recommendation | `05_decision_matrix.py` → `decision.json` |
| 9 | Correctness-gate spec | `CORRECTNESS_GATE.md` |
| 10 | RunPod command sequence | this file (below) |
| 11 | Honest status | this file (below) |
| H | **Unzip memory-vs-compute probe** (no `ncu`) | `07_unzip_bound_probe.sh` → `unzip_bound_probe.py` (fetch/math/full half-kernels) + `08_classify_unzip_bound.py` → `runs/unzip_bound_verdict.json` |
| H | Kernel correctness anchor (CPU, optional) | `validate_kernel_interp.py` (Triton interpreter, exact vs numpy) |
| 6F-A | **Page-local (store-as-consumed) layout probe + gates** | `unzip_bound_probe.py` LAYOUT variant + `08_classify_unzip_bound.py` `sixfa_pagelocal` (read≥20% / agg≥15% gates + projection) |
| 6F-A | **Append feasibility spike** (write-side delta) | `09_append_feasibility_spike.py` → `runs/append_spike.json` (write<25%-of-read-gain gate) |

## Part H — is the INT4 unzipper memory-bound or compute-bound?
`ncu` is blocked on the pod (`ERR_NVGPUCTRPERM`), so the fetch-vs-dequant split is measured **without
counters**: three specialisations of the *same* unzip inner loop are timed with CUDA events —
**FETCH**-only (issue every load + unpack, skip the affine), **MATH**-only (dequant affine + protect-select
on register-resident operands, no per-token HBM), and **FULL** (the real unzip). `FULL ≈ FETCH` ⇒
MEMORY-BOUND; `FULL ≈ MATH` ⇒ COMPUTE-BOUND; `FULL ≈ FETCH+MATH` ⇒ BOTH-TIGHTENABLE — cross-checked
against an analytical A100 roofline. Thresholds are **frozen in `DECISION_THRESHOLDS.md` (Part H) before any
GPU number is viewed**. The verdict maps straight to the lever: HBM-saturated → faster memory (H100/H200);
under-utilised → a compact-protect/coalesced read kernel (6F-style) first. The unzip is measured
production-faithfully (compact bf16 protected sidecar); one ablation times the route-A full-fp16-K load
(`int4_fused_attention_kernel.py:140`) so `FULL_full − FULL_compact` = the fp16-pool penalty.

**MEASURED RESULT (A100-80GB): `MEMORY-BOUND`, scatter-limited (~3% HBM used) — see
`UNZIP_BOUND_RESULT.md`.** The dequant math is ~7.5× under the fetch and fully hidden; the lever is a
6F-style coalesced/store-as-consumed read layout, NOT faster hardware and NOT cheaper math.

### 6F-A — page-local layout probe (the authorised next milestone)
The probe now also builds a per-head-contiguous **page-local** layout `(H, n_blocks, BS, *)` and times it
against the current `(S,H,*)` layout on **identical values** (oracle diff must be 0 — CPU-verified via the
interpreter). It reports, per context: read-only and full-unzip latency for both layouts, effective
bandwidth, the **≥20% read gate**, and a **MODELED aggregate-TPS projection** (labelled α/β share
scenarios) vs the **≥15%** gate. If the read gate passes, `07_unzip_bound_probe.sh` immediately runs the
**append feasibility spike** (`09_…`) which measures the write-side delta the layout imposes (per-token
appends become scattered-across-heads) against the **<25%-of-read-gain** gate — the four cases the reviewer
required: one-token append (no repack), block rollover, mixed tail lengths, saturation batch sweep.
**6F-C integration is authorised only if read ≥ 20% AND aggregate ≥ 15% (not FAIL) AND write < 25% AND
oracle exact** (frozen in `DECISION_THRESHOLDS.md` Part 6F-A). The route-A full-fp16 compact-sidecar swap is
a ~7% side-lever, deliberately **not** the primary Route-C optimisation.

**MEASURED RESULT (A100-80GB) — see `SIXFA_RESULT.md`:** read **+44.8%** (PASS), write **0.02%** of gain
(PASS), oracle **exact** (PASS), aggregate projection **10.2% central → PROVISIONAL** (clears only under
optimistic shares). **6F-C not yet authorised** — blocked on a *measured* decode-attention share (α·β) to
convert PROVISIONAL → PASS/FAIL. The write-regression risk that could have killed 6F is **falsified** (a
slot-write needs no repack; append cost is flat across concurrency).

## RunPod command sequence
```bash
cd /workspace/symbolu
git pull origin claude/kvpro-v2-tier1-d8b4ae
export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
# If profiling the PRODUCTION decode path, PYBIN must be the forked-vLLM env:
#   export PYBIN=/workspace/venv-vllm/bin/python3

# --- A) profiling (needs GPU; production path needs the forked vLLM wheel) ---
cd scripts/kvpro_v3_profile
bash 00_env_gate.sh                       # PASS/FAIL/UNAVAILABLE/NOT_REQUIRED -> env_gate.json
python3 06_correctness_gate.py            # Part B: Route-A builder vs oracle; MUST pass before profiling
bash run_profile_all.sh                   # env -> CORRECTNESS GATE -> nsys -> ncu -> cuda-events -> parse -> cost -> decision
#   (aborts if the correctness gate fails; each profiler skips honestly if its tool/fork is absent;
#    route-A Triton (03) needs NO fork; set KVV3_GPU_GATE=1 to also attempt the pod kernel-vs-oracle check)
cat runs/decision.json                    # ranked table + one recommendation (uses DECISION_THRESHOLDS.md)

# --- H + 6F-A) unzip probe + page-local layout gate + append spike (GPU + Triton; NO ncu, NO fork) ---
python3 validate_kernel_interp.py         # optional CPU anchor: addressing+dequant exact; page-local==current
CONTEXTS="4096 16384 32768" ITERS=100 bash 07_unzip_bound_probe.sh
#   -> prints the Part-H bound (MEMORY/COMPUTE) AND the 6F-A page-local read gate (>=20%) + aggregate
#      projection (>=15%); if the read gate passes it auto-runs the append spike (write<25%-of-gain).
#   optional measured shares for the projection: DECODE_ATTN_SHARE=<beta> UNZIP_SHARE=<alpha> bash 07_...
cat runs/unzip_bound_verdict.json         # verdict + sixfa_pagelocal gates + lever
cat runs/append_spike.json                # write-side delta + <25% gate (if the read gate passed)
git add -f runs/unzip_bound*.json runs/append_spike.json    # commit artifacts (pod push)

# --- F) protected-INT8 quality (fake-quant; needs GPU+model+mask, NOT the fork) ---
cd ../../experiments/kvpro_v3_symmetric_residual
bash run_p8_quality.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --quick-quality
# if quick is clean, harden knowledge like the S-study did:
bash run_p8_quality.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --full-quality --real-mmlu 2000
cat runs/*/p8_verdict.json

# --- feed the P8 verdict back into the decision ---
cd ../../scripts/kvpro_v3_profile
python3 05_decision_matrix.py --env runs/env_gate.json --stages runs/stage_summary.json \
    --cost runs/cost_accounting.json --p8 ../../experiments/kvpro_v3_symmetric_residual/runs/<ts>/p8_verdict.json \
    --out runs/decision.json
```

## Honest status (this container is CPU-only; the pod is where GPU work happens)
| Component | Status |
|-----------|--------|
| Decode map, cost accounting, decision matrix, env-gate, P8 quantizers + gate, **Route-A builder + correctness gate (Parts A/B), dynamic mask accounting (F), frozen thresholds (E), P8 production fidelity (I)** | **CPU-tested** (`test_profile_cpu.py` 21, `tests/test_protected_int8_cpu.py`, `tests/test_p8_gate_cpu.py`) |
| Route-A builder round-trips vs the writer's reference dequant (full+partial tails, bf16+prod-int8) | **CPU-verified** — 12-case gate PASS; NO GPU needed for the layout/correctness half |
| Format-change ceiling (bytes) | **Analytical** — modeled read-bytes, not TPS |
| Implementation-removal ceiling (time) | **UNAVAILABLE until a GPU profile exists** (never modeled/fabricated) |
| `01/02` nsys/ncu profiling, `run_profile_all.sh` | **HARDWARE-UNTESTED** — RunPod-ready, need GPU + Nsight (+ forked vLLM for the production kernel) |
| `03` route-A Triton timing | **HARDWARE-UNTESTED** — needs GPU; needs a route-A synthetic-input builder (emits `UNAVAILABLE` if absent) |
| **Part H unzip probe** (`07`/`08`) | **decision logic + byte/FLOP model CPU-tested** (`test_unzip_probe_cpu.py` 62); **kernel addressing+dequant CPU-verified exact** via Triton interpreter (`validate_kernel_interp.py`); **GPU-MEASURED on A100-80GB** — `MEMORY-BOUND`, scatter-limited (see `UNZIP_BOUND_RESULT.md`) |
| **6F-A page-local probe + append spike** (`07`/`08`/`09`) | **gates + projection + write-delta logic CPU-tested** (62 checks); **page-local == current byte-exact CPU-verified** (interpreter); **GPU timing HARDWARE-UNTESTED** — read/agg/write gates frozen in `DECISION_THRESHOLDS.md` Part 6F-A; emits `UNAVAILABLE` w/o GPU |
| P8 generation (`run_p8_quality.sh`, drivers) | **HARDWARE-UNTESTED** — GPU + model + mask (fake-quant; no fork) |
| **BLOCKED prerequisite** | production `flash_attn_with_int4_kvcache` = external forked vLLM wheel, **absent** — restore via `CTM_plus/Bench/scripts/apply_phase*_patches.py` on the pod, or profile the in-repo Triton route-A kernel instead |

**Recommendation state without a GPU profile:** the decision matrix returns `FIX_PREREQUISITES_FIRST`
(if nothing is profilable) or `INCONCLUSIVE` (profilable but not yet run) — **never** a guessed kernel
project. Run the sequence above to produce a measured recommendation.
