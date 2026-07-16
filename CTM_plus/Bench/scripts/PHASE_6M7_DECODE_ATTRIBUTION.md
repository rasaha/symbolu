# Phase 6M.7 — decode-time 5-bucket attribution + FROZEN decision thresholds

> **Status: TOOLING COMMITTED, CPU-self-tested; GPU numbers pending a pod run.**
> Diagnose-first extension of the 6M attribution. Companion to
> `PHASE_6M_ATTRIBUTION_FINDINGS.md` (6M.4, torch.profiler kernel-name buckets),
> `PHASE_6M5_ROOFLINE_FINDINGS.md` (Test 1, the gate — **ncu-BLOCKED**), and
> `PHASE_6M_THROUGHPUT_RECOVERY_TEST_PLAN.md`. **No optimization is authorized by
> this doc** — it produces a measured attribution + a frozen verdict; funding the
> read-path kernel rewrite (6F) is a separate decision gated on the roofline.

## Why this exists

6L proved density (**1.83× net seq/GB, quality-locked**) but measured a saturation
throughput tax: **0.22× bf16 aggregate tok/s** (~9× slower/user). The decision is
*which lever* recovers throughput. This extends the attribution into a clean
**code-region** split of decode time into five buckets and applies **frozen**
thresholds so the top lever is chosen by measurement, not preference.

## The five buckets (and how each is measured)

| Bucket | Source | ncu needed? |
|---|---|---|
| **write-path** | `batched.write` region (new; wraps `write_decode_batched`) | no |
| **decode-kernel** | `batched.kernel` / `one.kernel` region | no |
| **sidecar-access** | `batched.view_gather` (BUNDLED w/ packed gather; sidecar-only split → `audit_phase6g_sidecar_overhead.py`) | no |
| **scheduler/host** | per-region `cpu_us` (dispatch proxy) + 6M.4 GPU-busy% residual | no |
| **memory-bandwidth** | **Test-1 roofline (ncu SpeedOfLight)** — is the decode kernel compute- or bandwidth-bound | **YES — BLOCKED** |

The DecodeProfiler regions cover the int4 **read/write attention path only** (not
the model GEMMs), so a bucket's share of the int4 path is an **upper bound** on its
end-to-end share. The analyzer uses that: a write share below 10% on the int4 path
is *definitive* that write is below 10% end-to-end.

## FROZEN decision thresholds — DO NOT loosen post-hoc

Encoded as constants in `analyze_phase6m7_decode_attribution.py` (not CLI-tunable):

1. **write-path ≥ 10% of end-to-end decode → optimize the write kernels first**
   (`WRITE_PATH_MATERIAL_PCT = 10.0`). Enable via the Track-2 byte-eq gate.
2. **decode-kernel / sidecar traffic dominates (≥ 50% of the int4 path) → build the
   compact-sidecar in-repo decode kernel (6F)** (`READ_DOMINATES_PCT = 50.0`) —
   **GATED** on the Test-1 roofline verdict ∈ {compute-bound,
   bandwidth-bound-uncoalesced}. Roofline UNAVAILABLE → verdict `BLOCKED_ON_ROOFLINE`.
3. **capacity remains the aggregate limiter after throughput recovery → tighten the
   pool afterward** (the D/2 `get_kv_cache_shape` override + fold the ~4.38 GB
   sidecar tax). Evaluated from the 6L/6M.6 capacity harness, **not** this decode
   attribution. **Do NOT pursue tighter density first** — a 0.22× aggregate loss is
   too large for density alone to rescue.

**The deep kernel rewrite (6F) is gated on the measured top lever + the roofline.**
Report the attribution before starting it.

## What is ALREADY known (do not re-measure blindly)

- **6M.4 (decisive, long-context):** decode is **GPU-work-bound ~77%**; decode
  attention kernel **~29%**, paged gather **~15%**, copy ~6%, host-sync **<1%**; the
  **writer is "already at its lower bound."** ⟹ threshold (1) is *expected* to FAIL
  (write is not the dominant cost); the read path is the lever. 6M.7 CONFIRMS this
  rigorously with the clean write region + the upper-bound argument.
- **6M.3:** CUDA-graph capture is **~neutral at saturation** (not the ~2× that was
  once projected). So the graph half of any "write-path quick win" has a low ceiling.
- **6M.5 (Test 1, THE GATE):** the compute-vs-bandwidth roofline is **BLOCKED on
  `ERR_NVGPUCTRPERM`** on the available RunPod instances. This — not more CPU tooling
  — is the real blocker for greenlighting 6F. A profiling-enabled pod is the unblock.

## Track 1 — run the attribution (the pod runs this)

```bash
# 1) emit the per-B code-region CPU+GPU summary (profiler ON):
python CTM_plus/Bench/scripts/bench_phase6_decode_phase_profile.py \
    --batch-sizes 1,8,48 --max-model-len 8192 --max-tokens 96 \
    --json-out CTM_plus/Bench/bench_out/phase6m7/decode_phase_profile.json

# 2) attribute to the 5 buckets + apply the frozen thresholds (CPU; no ncu):
python CTM_plus/Bench/scripts/analyze_phase6m7_decode_attribution.py \
    --summary CTM_plus/Bench/bench_out/phase6m7/decode_phase_profile.json \
    --roofline-verdict unknown \
    --out CTM_plus/Bench/bench_out/phase6m7/PHASE_6M7_decode_attribution_report.txt
# When 6M.4's end-to-end GPU total is on hand, add --total-step-gpu-us <us> to test
# the 10% write threshold against end-to-end (not just the int4-path upper bound).
# When Test 1 finally runs, pass --roofline-verdict <compute-bound|...> to un-gate 6F.
```

Paste back the `VERDICT` block + the `.json`. Commit the artifacts with `git add -f`
(`bench_out/` is gitignored) so the conclusion is reproducible.

## Track 2 — enable the low-risk write kernels, correctness-gated (parallel, no-regret)

```bash
python CTM_plus/Bench/scripts/verify_and_enable_fused_writer.py --device cuda
# GO iff byte-eq GREEN *and* int4_protected_C actually loaded (else the fused path
# is the Python ref = no speedup). On GO it prints `export PHASE6E_FUSED_WRITER=1`.
# Gate-and-run atomically:
#   python .../verify_and_enable_fused_writer.py --device cuda \
#       --then python .../phase6l_capacity_demo.py --compare --mml 8192 --b-list 96,128
```

The shipped default stays **OFF** (`test_default_env_is_off`). Honest ceiling: 6M.4
puts the writer at its lower bound and 6M.3 makes graphs neutral, so expect a **small**
write-path gain — this is a no-regret parallel move, not the main lever.

## Decision tree

```
6M.7 attribution (Track 1, no ncu)
  ├─ write ≥10% end-to-end ───────► enable write kernels (Track 2 gate) FIRST
  └─ read path dominates (usual) ─► compact-sidecar decode kernel (6F) is the candidate
                                     └─ GATED on Test-1 roofline (ncu) ─┐
Test 1 roofline (6M.5) — BLOCKED on ncu perms ◄───────────────────────┘
  ├─ compute-bound / bw-uncoalesced ► fund 6F kernel rewrite (ceiling ~0.27–0.30×)
  ├─ bandwidth-bound-coalesced ─────► H200 HBM leg (Test 2); 6F low ceiling
  └─ (unavailable) ─────────────────► get a profiling-enabled pod; do NOT fund 6F yet
```

## Guardrails (inherited)

- **No fabricated numbers.** memory-bandwidth stays UNAVAILABLE until ncu runs.
- **Correctness first.** Any write/kernel change keeps byte-eq GREEN + COLLAPSE=0 +
  needle/token-agreement within noise. A faster-but-wrong path is a failure.
- **Closed tracks stay closed** (6G.2 RED): no int8-V, `n_protect`↓, xmin removal,
  sidecar diet. Throughput work is data-movement/compute only, never a quality change.
- **Density + quality are the proven product**; throughput recovery is bounded upside.

## Artifacts / self-tests (CPU, no GPU)

```bash
python CTM_plus/Bench/scripts/analyze_phase6m7_decode_attribution.py --selftest   # 9/9
python CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py                    # write byte-eq
python CTM_plus/Bench/scripts/verify_and_enable_fused_writer.py --device cpu      # gate dry-run (NO-GO)
```
