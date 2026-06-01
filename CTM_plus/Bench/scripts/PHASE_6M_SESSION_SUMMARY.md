# Phase 6M/6N — Session summary (2026-06-01)

Briefing for the next session. What we set out to do, what we got, what's blocked,
and the exact next moves. All work is on branch
`claude/phase-6m-throughput-recovery-UeaIR` (17 commits, `f313f01`..`949f42e`).

## Mission

Execute the Phase 6M throughput-recovery test plan: (1) Test 1 roofline (the
gate), (2) Test 2 hardware, (3) Test 3 kernel fusion (gated). Plus re-confirm the
density/quality claims and keep the VC brief honest.

## Headline outcomes

| Claim | Status | Evidence |
|---|---|---|
| **Density 1.83× net seq/GB (2.02× raw, 117 vs 58 live)** | ✅ **REPLICATED** on a fresh A100 (rebuilt kernels, recalibrated mask) | `bench_out/phase6m6/A100_report.json` |
| **Sidecar tax 4.38 GB** (99.8% of HBM delta) | ✅ re-measured, matches locked | same |
| **Quality: MMLU 63.5% = bf16 63.5%, 0.0 pt** | ✅ **NEW, measured this session** (200 Q) | `bench_out/phase6n/mmlu_report.json` |
| **Quality: hard-needle 4/4, COLLAPSE=0** | ✅ on recalibrated mask | `/tmp/needle.json` (pod) |
| **Throughput = a CURVE, 0.22×–0.54×** | ✅ **NEW** — operating-point dependent | `bench_out/phase6m_opsweep/opsweep_summary.tsv` |
| **Attribution: gather #1 (~25%), attn #2 (~21%), host <1%** | ✅ re-confirmed (6M.4) | `bench_out/phase6m6/A100_kernel_diff.txt` |

## The two genuinely new findings

1. **Throughput is workload-dependent, not one bad number.** The "0.22× / ~9×
   slower" headline is the WORST case (deep saturation + long generation). The
   measured curve: **gen=128 → 0.54×, gen=512 → 0.32×, deep-sat → 0.22×**; density
   invariant ~1.83×. Short-output, high-concurrency workloads (embeddings,
   classification, scoring, agentic routing, RAG, eval) get full density at only
   **~2× slowdown** — the target segment. Deploy-at-short-gen is the best no-code
   lever. (`PHASE_6M_HEADROOM_NO_NCU.md` has the routing rubric.)

2. **No measurable MMLU accuracy loss** (0.0 pt at 200 Q). Closes the brief's #1
   adoption gap (quality was needle + token-agreement only). **Honest caveat:**
   200-Q multiple-choice proves the argmax answer is unchanged, NOT bitwise-
   identical logits; larger-N + HumanEval/LongBench still pending.

## What's BLOCKED and why

- **Test 1 (roofline / 6M.5):** BLOCKED on `ERR_NVGPUCTRPERM` — GPU perf counters
  are locked on the available RunPod A100 (host/driver permission, not fixable
  in-container). Needs a **profiling-enabled pod**
  (`NVreg_RestrictProfilingToAdminUsers=0`). Gates the compute-vs-bandwidth split.
- **Test 2 axis attribution:** consequently OPEN — `analyze_phase6m6_hardware.py`
  needs Test 1's `--bound-verdict`. The A100 baseline + 6D buckets ARE captured;
  only the H100/H200 legs + the axis call remain.
- **Test 3 (6F kernel fusion):** PENDING — gated on Test 1's verdict AND a funding
  decision. Tooling fully prepped (oracle + acceptance A/B + runbook).

## Decisions recorded this session

- **Tier 2 / Triton (throughput kernel work): RECOMMEND DEFER.** Tier-0 Amdahl
  bound shows realistic recovery ~0.26–0.30× (theoretical max 0.41×) — **below the
  ≥0.70×/user interactive bar even at the ceiling.** The product is a density play;
  short-gen deployment already gets 0.54× for free. Revisit only with an
  interactive customer + Test 1 verdict.
- **Cheapest-first roadmap:** (1) MMLU ✅ done + mask fixed; (2) **multi-GPU / TP
  validation** = the highest-value hardware bet (unlocks 70B where density moves
  dollar economics) — budget as validation-WITH-debug-risk (pool sharding
  unverified); (3) throughput kernel work = defer.
- **VC brief reframed honestly:** throughput as a curve + target segment; withdrew
  the overturned "graph capture → 2× throughput" claim (6M.3); added MMLU.

## Hard lessons → now hardened in the scripts

Fresh-pod bring-up hit a cascade; all fixed + committed so the next pod is clean:
- `rebuild_all_kernels.sh`: `--no-deps` + torch-restore guard (a kernel build
  silently swapped torch 2.5.1→2.4.0 and broke the stack); builds a WHEEL +
  installs into vLLM's **vendored** flash-attn slot (editable install left the
  int4 symbol missing); `mkdir -p $TMPDIR`; step-5 asserts the int4 symbol.
- `PREP_NEW_POD.md`: documents the full dep-pin set, the vendored-wheel
  requirement, the missing-protect-mask regen step, and `HF_HUB_ENABLE_HF_TRANSFER=0`.
- **Dependency pins that matter:** torch 2.5.1+cu121, transformers 4.48.3,
  tokenizers 0.21.x, numpy 1.26.4, triton 3.1.0, vLLM 0.7.3. `datasets` (for MMLU)
  is safe to add but pulls pandas/dateutil/etc.
- **Protect mask MUST be calibrated at full context** (mml=8192). The mml=1024
  shortcut collapses int4 output — a mask problem, NOT a method failure.

## Tooling added this session (all CPU-self-tested)

| Script | Purpose | Test |
|---|---|---|
| `analyze_phase6m5_roofline.py` | ncu SoL → bound verdict (Test 1) | 7/7 + 10/10 |
| `roofline_ncu_runner.sh` | Test 1 pod runbook (probes ncu first) | — |
| `analyze_phase6m6_hardware.py` | per-GPU ratio + axis attribution | 8/8 + 12/12 |
| `hardware_test_runner.sh` | Test 2 per-GPU runner | — |
| `analyze_phase6f_acceptance.py` | 6F gather A/B acceptance | 7/7 + 9/9 |
| `phase6f_correctness_oracle.sh` / `phase6f_acceptance_ab.sh` | Test 3 gates | — |
| `estimate_phase6m_headroom.py` | Tier-0 no-ncu headroom bound | 7/7 |
| `phase6m_operating_point_sweep.sh` | Tier-1 no-ncu op-point sweep | — |
| `bench_phase6n_mmlu_quality.py` | MMLU quality bench | 7/7 + 13/13 |
| `preflight_gpu_pod.sh` | layer-by-layer pod readiness check | — |

## Next session — exact moves

1. **For Test 1 → Test 3 unblock:** get a **profiling-enabled pod**, reattach the
   volume, `bash CTM_plus/Bench/scripts/preflight_gpu_pod.sh`, then
   `roofline_ncu_runner.sh` → paste the verdict → finalize `PHASE_6M5_*` and the
   Test 3 gate.
2. **For the highest-value growth bet:** free code audit of the paged-writer TP
   sharding (no GPU), then a multi-GPU TP validation sprint (unlocks 70B).
3. **For quality at scale:** larger-N MMLU + HumanEval/LongBench on a good mask.
4. **Always:** recalibrate the protect mask at mml=8192 on any fresh pod before
   trusting int4 output.

## Reproduce the headline numbers (CPU, no GPU)

```bash
python CTM_plus/Bench/scripts/estimate_phase6m_headroom.py            # throughput prize
python CTM_plus/Bench/scripts/bench_phase6n_mmlu_quality.py --selftest # quality harness
cat CTM_plus/Bench/bench_out/phase6m6/A100_report.json                # density
cat CTM_plus/Bench/bench_out/phase6n/mmlu_report.json                 # MMLU
cat CTM_plus/Bench/bench_out/phase6m_opsweep/opsweep_summary.tsv      # throughput curve
```
