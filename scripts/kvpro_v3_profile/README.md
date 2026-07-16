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
| 4 | Parsed profile (JSON+CSV) | `04_parse_profile.py` → `stage_summary.{json,csv}` |
| 5 | Bottleneck table | `stage_summary.*` (per-stage % of kernel time) |
| 6 | Protected-INT8 harness + quality | `../../experiments/kvpro_v3_symmetric_residual/{protected_int8.py,p8_gate.py,run_p8_quality.sh}` |
| 7 | Cost accounting + 2 ceilings | `cost_accounting.py` → `cost_accounting.json` |
| 8 | Decision matrix + 1 recommendation | `05_decision_matrix.py` → `decision.json` |
| 9 | Correctness-gate spec | `CORRECTNESS_GATE.md` |
| 10 | RunPod command sequence | this file (below) |
| 11 | Honest status | this file (below) |

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
bash run_profile_all.sh                   # env -> nsys -> ncu -> cuda-events -> parse -> cost -> decision
#   (each profiler skips honestly if its tool/fork is absent; route-A Triton (03) needs NO fork)
cat runs/decision.json                    # ranked table + one recommendation

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
| Decode-pipeline map, cost accounting, decision matrix, env-gate logic, P8 quantizers + gate | **CPU-tested** (`test_profile_cpu.py`, `tests/test_protected_int8_cpu.py`, `tests/test_p8_gate_cpu.py`) |
| Format-change ceiling (bytes) | **Analytical** — modeled read-bytes, not TPS |
| Implementation-removal ceiling (time) | **UNAVAILABLE until a GPU profile exists** (never modeled/fabricated) |
| `01/02` nsys/ncu profiling, `run_profile_all.sh` | **HARDWARE-UNTESTED** — RunPod-ready, need GPU + Nsight (+ forked vLLM for the production kernel) |
| `03` route-A Triton timing | **HARDWARE-UNTESTED** — needs GPU; needs a route-A synthetic-input builder (emits `UNAVAILABLE` if absent) |
| P8 generation (`run_p8_quality.sh`, drivers) | **HARDWARE-UNTESTED** — GPU + model + mask (fake-quant; no fork) |
| **BLOCKED prerequisite** | production `flash_attn_with_int4_kvcache` = external forked vLLM wheel, **absent** — restore via `CTM_plus/Bench/scripts/apply_phase*_patches.py` on the pod, or profile the in-repo Triton route-A kernel instead |

**Recommendation state without a GPU profile:** the decision matrix returns `FIX_PREREQUISITES_FIRST`
(if nothing is profilable) or `INCONCLUSIVE` (profilable but not yet run) — **never** a guessed kernel
project. Run the sequence above to produce a measured recommendation.
