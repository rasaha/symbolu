# Phase 6M/6N/6O — Session summary (2026-06-01 / 06-02)

Briefing for the next session. The full arc, what's proven, what's blocked, and
the exact next moves. All work on branch
`claude/phase-6m-throughput-recovery-UeaIR` (27 commits, `f313f01`..`c3c954e`).

## Mission (evolved over the session)

Started as: execute the Phase 6M throughput-recovery test plan (Test 1 roofline,
Test 2 hardware, Test 3 kernel fusion). Grew into: re-validate density+quality on
fresh hardware, reframe the throughput story honestly, prove the weight-quant
stacking claim, and scope the two-tier/eviction future.

## Headline outcomes (all measured this session unless noted)

| Claim | Status | Evidence |
|---|---|---|
| **Density 1.83× net seq/GB** (2.02× raw, 117 vs 58 live) | ✅ REPLICATED on a fresh A100 | `bench_out/phase6m6/A100_report.json` |
| **Sidecar tax 4.38 GB** | ✅ re-measured, matches locked | same |
| **Quality: MMLU 200 Q = bf16 (63.5%=63.5%, 0.0pt)** | ✅ | `bench_out/phase6n/mmlu_report.json` |
| **Quality: MMLU 1,000 Q = bf16 (73.9%=73.9%, 0.0pt, 100% per-question agreement, net_flips=0)** | ✅ STRONGEST quality result | `bench_out/phase6n2/mmlu_1k.json` |
| **Quality: hard-needle 4/4, COLLAPSE=0** | ✅ on recalibrated mml=8192 mask | pod `/tmp/needle.json` |
| **Throughput = a CURVE, 0.22×–0.54×** (workload-dependent) | ✅ | `bench_out/phase6m_opsweep/opsweep_summary.tsv` |
| **Attribution: gather ~25%, attn ~21%, host <1%** | ✅ re-confirmed (6M.4) | `bench_out/phase6m6/A100_kernel_diff.txt` |
| **AWQ weights + int4_protected KV COMPOSE** (was: untested brief assertion) | ✅ fixed + validated this session | `bench_out/phase6o/stack_fixed.json` |

## The new findings (beyond the original mid-session summary)

1. **Throughput is workload-dependent (0.22–0.54×), not one number.** gen=128 →
   0.54×; gen=512 → 0.32×; deep-sat → 0.22× (the worst case). Density invariant
   ~1.83×. **Short-output high-concurrency workloads** (embeddings, classification,
   scoring, agentic routing, RAG, eval) get full density at only ~2× slowdown =
   the target segment. Best NO-CODE lever: deploy at short generation.

2. **MMLU at 1,000 Q with 100% per-question agreement.** Not just equal aggregate
   accuracy — int4 chose the *identical* answer on all 1,000 questions. The
   agreement diagnostic (built to catch compensating flips) found zero. Honest
   residual: 100% MC agreement proves argmax unchanged, not bitwise-identical
   logits; HumanEval/LongBench tooling committed but not yet executed.

3. **AWQ stacking: assertion → crash → fix → validated.** The brief claimed
   AWQ/GPTQ "stack with int4_protected." Tested: it CRASHED (fp16 activations vs
   bf16-dequant K → "query and key must have the same dtype"). Wrote a one-commit
   **dtype bridge** (e06dd26), gated on `query.dtype != bf16`. Re-ran: stack
   LOADS, MMLU 56% vs 55% (within noise), **byte-eq 15/15 GREEN** (bf16 path
   untouched). Integration + quality COMPOSE, validated. Open: clean combined-
   *memory* number (the stack bench's HBM proxy is unreliable → use phase6l).

4. **Two-tier KV: CPU-modeled → DON'T build compression-demotion.**
   `simulate_two_tier_kv.py` at measured anchors → "LIKELY NOT WORTH IT". Density
   and throughput-gain are in DIRECT TENSION (cold tokens pay the int4 tax every
   step, so keeping density ≈ all-int4 cost). Compression-demotion is a
   speed↔density DIAL, not a win. The only upside variant is true EVICTION
   (cold tokens read *less often*, H2O/StreamingLLM) — which is the Phase 4/8
   work that died on the −20% integration tax, gated on Route-A.

## What's BLOCKED / open

- **Test 1 (roofline / 6M.5):** BLOCKED — `ERR_NVGPUCTRPERM` (GPU perf counters
  locked). RunPod has no documented profiling-enabled instance; their AI support
  said it needs a human to route to a privileged host. Needs a profiling-enabled
  pod. Gates the compute-vs-bandwidth split.
- **Test 2 axis attribution:** OPEN — needs Test 1's verdict + an H100/H200 leg.
  A100 baseline + 6D buckets ARE captured.
- **Test 3 (6F kernel fusion):** PENDING — gated on Test 1 + funding. Tooling
  prepped (oracle + acceptance + runbook).
- **AWQ combined-memory number:** the integration+quality compose; the *memory*
  saving wasn't cleanly measured (HBM proxy unreliable). Small phase6l follow-up.
- **HumanEval pass@1 / LongBench:** tooling committed; not run (HumanEval needs a
  sandbox for code execution).

## Decisions on record

- **Tier 2 / Triton (throughput kernel work): DEFER.** Tier-0 bound: ~0.26–0.30×
  realistic, 0.41× theoretical max — below the ≥0.70×/user interactive bar even at
  the ceiling. Product is a density play; short-gen already gets 0.54× free.
- **Triton ≠ a new lever** — same bounded ceiling, just a different language for
  the same gated 6F work.
- **Two-tier compression-demotion: DON'T build** (CPU model: a dial, not a gain).
  Eviction/read-skip variant is the only upside, gated on Route-A.
- **Cheapest-first roadmap:** MMLU ✅ done → multi-GPU/TP validation (unlocks 70B;
  the highest-value hardware bet; budget as validation-WITH-debug-risk) →
  throughput kernel work deferred.
- **VC brief reframed honestly:** throughput as a curve + target segment;
  withdrew the overturned "graph capture → 2× throughput" claim (6M.3); added MMLU
  1K + 100% agreement; corrected the AWQ-stacking claim to measured+fixed.

## Hard lessons → hardened in the scripts (the fresh-pod marathon)

A from-scratch rebuild this session hit a cascade; all fixed + committed:
- **Dep cascade:** a kernel build silently swapped torch 2.5.1→2.4.0, which
  dragged transformers/tokenizers/numpy/triton. Fixed: `rebuild_all_kernels.sh`
  uses `--no-deps` + a torch-restore guard. **Pins:** torch 2.5.1+cu121,
  transformers 4.48.3, tokenizers 0.21.1, numpy 1.26.4, triton 3.1.0, vllm 0.7.3.
- **Vendored-slot:** `pip install -e .` left the int4 read symbol out of vLLM's
  vendored flash-attn slot → must build a WHEEL + copy over the slot. Fixed +
  asserted in the rebuild script.
- **`$TMPDIR`:** cleaning `/workspace/tmp` made nvcc fail ("could not open output
  file"). Fixed: `mkdir -p $TMPDIR`.
- **Mask:** calibrate at FULL context (mml=8192) — the mml=1024 shortcut
  COLLAPSES int4 output (a mask problem, not a method failure).
- **venv discipline:** install torch/vllm INTO `/workspace/venv-vllm`, not system
  Python (a build against system Python had torch but no vllm → failed).
- **Ctrl-C, never Ctrl-Z** — suspended (state T) builds/git held locks repeatedly.
- **`bootstrap_fresh_pod.sh`** now encodes the entire correct sequence.

## Tooling added this session (all CPU-self-tested)

| Script | Purpose | Test |
|---|---|---|
| `analyze_phase6m5_roofline.py` | ncu SoL → bound verdict (Test 1) | 7/7 + 10/10 |
| `roofline_ncu_runner.sh` | Test 1 pod runbook (ncu probe first) | — |
| `analyze_phase6m6_hardware.py` | per-GPU ratio + axis attribution | 8/8 + 12/12 |
| `hardware_test_runner.sh` | Test 2 per-GPU runner | — |
| `analyze_phase6f_acceptance.py` + 2 oracles | Test 3 gates | 7/7 + 9/9 |
| `estimate_phase6m_headroom.py` | Tier-0 no-ncu headroom bound | 7/7 |
| `phase6m_operating_point_sweep.sh` | Tier-1 no-ncu op-point sweep | — |
| `bench_phase6n_mmlu_quality.py` | MMLU quality bench | 7/7 + 13/13 |
| `bench_phase6n2_quality_suite.py` | MMLU-large-N + HumanEval + LongBench + agreement | 5/5 + 15/15 |
| `bench_phase6o_weight_kv_stack.py` | AWQ × int4 stacking test | 4/4 + 10/10 |
| `simulate_two_tier_kv.py` | two-tier prize-sizing MODEL | 7/7 |
| `preflight_gpu_pod.sh` / `bootstrap_fresh_pod.sh` | pod readiness / from-scratch | — |

Plus the dtype-bridge FIX in `phase5b_backend_install.py` (byte-eq 15/15).

## Next session — exact moves (cheapest-first)

1. **AWQ combined-memory** (no profiling pod): re-run the stack via phase6l live
   introspection to get the real weight+KV footprint → completes the stacking story.
2. **Highest-value hardware bet:** free CPU audit of the paged-writer TP sharding,
   then a multi-GPU TP validation sprint (unlocks 70B; budget as debug-possible).
3. **Test 1 → Test 3 unblock:** a profiling-enabled pod → `roofline_ncu_runner.sh`.
4. **Quality at scale:** HumanEval (sandboxed) + LongBench via `bench_phase6n2`.
5. **Always on a fresh pod:** `bootstrap_fresh_pod.sh`; recalibrate mask at mml=8192.

## Reproduce headlines (CPU, no GPU)

```bash
python CTM_plus/Bench/scripts/estimate_phase6m_headroom.py            # throughput prize
python CTM_plus/Bench/scripts/simulate_two_tier_kv.py                 # two-tier model
cat CTM_plus/Bench/bench_out/phase6m6/A100_report.json               # density 1.83x
cat CTM_plus/Bench/bench_out/phase6n2/mmlu_1k.json                    # MMLU 1K, 100% agreement
cat CTM_plus/Bench/bench_out/phase6o/stack_fixed.json                # AWQ stacking (fixed)
cat CTM_plus/Bench/bench_out/phase6m_opsweep/opsweep_summary.tsv      # throughput curve
```
