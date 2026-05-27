# Phase 6B.3 — capture-enable GPU smoke runbook

Status: **code landed, awaiting GPU pod execution.** The CPU portion
of G_CAPTURE prep is GREEN — `Int4ProtectedLLM` constructor flipped
to default `enforce_eager=False` with `PHASE6B3_FORCE_EAGER` kill-
switch; 99 pytest + 36+36 equivalence verifiers still PASS as
regression. This runbook drives the operator-runnable smoke +
verify sweep that finishes G_CAPTURE on real hardware.

Pairs with:
* `PHASE_6B3_CAPTURE_DESIGN.md` §9 acceptance criteria
* `bench_phase6_b3_capture_gpu_smoke.py` — the smoke driver
* `tier5a_orthogonality_gate.py` — pre+post orthogonality gate

## What this proves

vLLM 0.7.3 V0's CUDA Graphs capture works end-to-end with the
int4_protected backend after 6B.1 + 6B.2's structural preflight.
Captured-mode decode produces **byte-identical generated tokens**
to eager mode at multiple batch sizes; multi-batch determinism is
preserved; existing correctness verifies stay GREEN under capture.

Bisection primitive: `PHASE6B3_FORCE_EAGER` env var.
* `cell eager`    — `PHASE6B3_FORCE_EAGER=1`; constructor forces
  `enforce_eager=True`. Reference. Matches 6B.1 + 6B.2 baseline.
* `cell captured` — env unset; constructor default
  `enforce_eager=False`. vLLM captures decode forwards at its
  default ~35-batch-size curve.

Both cells run the SAME workload with the SAME hook installed
(6B.2's hook is the default; the 6B.3 work is the capture flip).
Byte-identity is the load-bearing correctness check.

## Acceptance gates

| Gate | What it checks | Pass criterion |
|---|---|---|
| **G_CAPTURE.1** | Capture phase ran without crash | engine init completed; load_seconds finite |
| **G_CAPTURE.2** | Eager vs captured tokens byte-equal across B in {1,2,4,8} | per-B `tokens_byte_equal=True` |
| **G_CAPTURE.3** | Multi-batch determinism (run1==run2) preserved in BOTH cells | per-B `deterministic=True` for both cells |
| **G_CAPTURE.4** | Zero fallbacks both cells across the sweep | aggregate fallback counters == 0 |
| **G_CAPTURE.5** | 6B.2 hook still firing | captured cell `stash_call_count > 0` |
| **G_CAPTURE.6** | HBM overhead within budget | captured `capture_overhead_gb ≤ 5.0` (informational; logged) |
| **G_CAPTURE.7** | 5 LLM-dependent verifies GREEN under capture (Step 4) | each verify exits 0 |
| **G5a/G5b/G5c/G6a/G6b** | TIER5A orthogonality | gate exits 0 with all in-tree tracks GREEN (G5c regen'd) |

**Overall PASS** requires gates 1-5 + 7 + orthogonality. Gate 6 is
informational (>5 GB logged as a concern for 6B.4 shape tuning, but
not blocking).

## Pod spec

Same as 6B.1 + 6B.2:
* GPU: H100 80 GB or A100 80 GB.
* PyTorch: ≥ 2.5 + cu124.
* vLLM: int4_protected **forked** 0.7.3 build with TIER5A.3-frozen
  vllm_flash_attn wheel.
* Disk: ≥ 100 GB ephemeral.
* Protect mask: `/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt`.

## Step 1 — pre-run orthogonality gate

```bash
cd /workspace/symbolu/CTM_plus/Bench
PYTHONPATH=../KVPolicy:. /workspace/venv-vllm/bin/python3 \
    -m ctm_bench.scripts.tier5a_orthogonality_gate
```

Expected:

```
verdict: pass
  g5a (class fingerprint): pass (0 violations)
  g5b (tier5a ast):        pass (0 violations)
  g5c (int4 python sha):   pass (10 files; int4_protected.py SHA updated for 6B.3 constructor flip)
  g6a (cuda fork sha):     pass (0 violations; in-tree defensive)
  g6b (wheel sha pin):     pass (0 violations; load-bearing)
```

**STOP** on any non-PASS.

## Step 2 — run the smoke

```bash
PYTHONPATH=../KVPolicy /workspace/venv-vllm/bin/python3 \
    scripts/bench_phase6_b3_capture_gpu_smoke.py \
    --output-dir /workspace/symbolu/bench_out/phase6b3_gpu_smoke
```

Expected wall time: ~150-180 seconds (capture phase adds ~15-20s to
the captured cell's load time). Cost: ~$0.07.

Driver spawns two cells as separate subprocesses:
1. **cell eager**    (`PHASE6B3_FORCE_EAGER=1`) — forces eager mode.
   Reference behavior.
2. **cell captured** (env unset) — `enforce_eager=False` triggers
   vLLM's automatic capture phase.

Each cell runs B ∈ {1, 2, 4, 8} × 2 runs each = 8 sub-trials,
recording tokens + call_stats + HBM stats + hook stats.

## Step 3 — interpret the report

A GREEN run shows:

```
==============================================================================
Phase 6B.3 GPU smoke — eager vs captured comparison
==============================================================================
Model: Qwen/Qwen2.5-7B-Instruct    Batch sizes: [1, 2, 4, 8]
Verdict: GREEN

Load times:    eager=13.5s    captured=30.0s (capture phase = +16.5s)
HBM overhead:  captured cell = 3.5 GB
Hook stash:    eager=N    captured=M

Checks:
  [PASS] B1_eager_vs_captured_tokens_byte_equal
  [PASS] B1_eager_deterministic_run1_eq_run2
  ...
  [PASS] eager_zero_fallbacks_across_sweep
  [PASS] captured_zero_fallbacks_across_sweep
  [PASS] captured_cell_hook_stash_positive
  [PASS] captured_cell_hbm_overhead_within_5gb
```

If RED: the per-B diff section shows per-prompt text and which
check failed. Common failure modes are in §Troubleshooting below.

## Step 4 — verify-under-capture sweep (Qwen-only)

After smoke GREEN, re-run the 5 LLM-dependent verifies with
capture enabled:

```bash
cd /workspace/symbolu/CTM_plus/Bench
# Constructor default is now enforce_eager=False, so simply running
# the existing verify scripts exercises the captured path.
for v in verify_phase5b_4c_2_read.py \
         verify_phase5b_4c_3_e2e.py \
         verify_phase5b_5_needle.py \
         verify_phase5b_6_batch.py \
         verify_phase5c_api.py; do
    echo "=== $v ==="
    PYTHONPATH=../KVPolicy /workspace/venv-vllm/bin/python3 scripts/$v
    rc=$?
    echo "EXIT_CODE=$rc"
    if [ $rc -ne 0 ]; then
        echo "STOP — verify $v failed under capture."
        break
    fi
done
```

Expected: each exits 0. Total wall time ~3-4 minutes; ~$0.07.

If a verify diverges from its eager baseline, that's a captured-
graph correctness bug — STOP and diagnose:
1. Re-run the verify with `PHASE6B3_FORCE_EAGER=1` to confirm it
   passes eager.
2. If yes → captured-graph regression. Use
   `diagnose_phase6_b_pre5_write_state.py --live` to inspect.
3. If no → unrelated regression; investigate independently.

## Step 5 — opportunistic Mistral needle (optional)

After Qwen verifies GREEN, run cross-family needle under capture:

```bash
PROTECT_MASK_PATH=/workspace/dev/build-logs/mistral_7b_instruct_v0_3_protect_mask_4pct.pt \
PYTHONPATH=../KVPolicy /workspace/venv-vllm/bin/python3 \
    scripts/verify_phase5b_5_needle.py \
    --model mistralai/Mistral-7B-Instruct-v0.3
```

Expected: 15/15 needle retrieval under capture (matches 6B.1's
Mistral baseline). Cost: ~$0.05.

If Mistral needle is < 15/15 under capture but Qwen is GREEN → log
as a partner-credible cross-family edge case for 6B.4; doesn't
gate 6B.3.

## Step 6 — post-run orthogonality gate

Re-run Step 1's command. Same expected output. Confirms the smoke
didn't modify any baselined file.

## Troubleshooting

### G_CAPTURE.1 (capture crash at init)

Engine init hangs or crashes with `operation not permitted when
stream is capturing`. This means 6B.1 + 6B.2 missed a host sync
or pointer-churn somewhere in the captured forward.

Diagnostic:
1. Run the diagnostic inspect-only check first to confirm hook
   integration is correct:
   ```bash
   PYTHONPATH=../KVPolicy /workspace/venv-vllm/bin/python3 \
       scripts/diagnose_phase6_b_pre5_write_state.py
   ```
2. Re-run the smoke with `--max-model-len 1024` to reduce capture
   surface; isolates the failure to a specific batch size.
3. If still crashes, set `PHASE6B3_FORCE_EAGER=1` in production
   (eager mode is the v1 ship state; 6B.3 capture is the v2
   enhancement). 6B.3.1 follow-up handles the fix.

### G_CAPTURE.2 (eager vs captured tokens diverge)

The most diagnostic failure mode. Open `smoke_report.json` →
`per_b_diffs`:
* Diverges at token 0: backend swap or hook integration differs
  between cells. Compare `hook_total_stash_calls` per cell.
* Diverges mid-sequence: captured-graph math diverged. Sometimes
  this is bf16 rounding differences from kernel selection (e.g.,
  capture-pool allocations triggered a different cuBLAS algorithm);
  inspect the FIRST divergent token for proximity to bf16 boundary.

### G_CAPTURE.3 (multi-batch determinism RED)

run1 ≠ run2 in one cell. Likely cause:
* Eager cell RED: pre-existing non-determinism in vLLM/torch. Not
  6B.3-caused. Document as known limitation.
* Captured cell only RED: captured-graph memory pool reuse issue.
  Investigate `cudagraph_num_of_warmups` and memory pool flags.

### G_CAPTURE.6 (HBM overhead > 5 GB)

Captured cell allocated > 5 GB. Not a fail; logged for 6B.4 shape
tuning:
1. Reduce `gpu_memory_utilization` to 0.4 or 0.3 for the captured
   cell to leave more room.
2. In 6B.4, narrow `cudagraph_capture_sizes` to a subset (e.g.,
   only B ∈ {1, 8}).
3. Re-measure HBM after the narrow.

## Reference: minimum cells to PASS

| Cell | Env var | enforce_eager | Reference |
|---|---|---|---|
| eager    | `PHASE6B3_FORCE_EAGER=1` | True | matches 6B.1 + 6B.2 baseline |
| captured | (unset) | False (constructor default) | NEW v2 behavior |

Both cells: hook installed via 6B.2 path; B ∈ {1, 2, 4, 8} × 2 runs
each; temperature=0.0; max_tokens=32; same 2 prompts.

Byte-identity across cells + within each cell across runs = capture
is correct.
