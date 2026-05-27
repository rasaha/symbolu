# Phase 6B.3 — enforce_eager=False flip + capture enable (design doc)

> **Status:** Design doc only. CPU prep where possible; GPU smoke is
> the load-bearing acceptance step. No code lands without explicit
> user approval of this design.
>
> **Scope:** ONLY Phase 6B.3 of `PHASE_6B_CUDA_GRAPHS_PLAN.md`.
> Phase 6B.4 (throughput re-measurement + brief edit) stays gated
> on a separate approval after 6B.3 closes GREEN.
>
> **Builds on:** Phase 6B.1 + 6B.2 both CLOSED-positive. The write
> path's captured region is host-sync-free and produces byte-
> identical generated tokens to the legacy path with the hook
> installed. All four structural prerequisites for graph capture
> (per 6B.2 finding doc §Implication for Phase 6B.3) are met.
>
> **Acceptance gate:** G_CAPTURE (per plan §"Phase 6B.3 acceptance
> gate").

---

## 1. What 6B.3 actually changes

ONE line in `Int4ProtectedLLM` constructor — flip `enforce_eager=False`
(or expose it as a constructor arg with the previous default). Everything
else is already wired:

* 6B.1 made the write path's captured region host-sync-free.
* 6B.2 hoisted the remaining per-call slot resolution to one
  pre-capture sync per step.
* The read path's preflight (B-pre-1..4, landed before this branch
  series) already made the read side captured-region-clean.
* Pool counters + sidecars are pointer-stable per the pointer audit.

What we DON'T do in 6B.3:
* Custom `compilation_config.cudagraph_capture_sizes`. vLLM 0.7.3 V0
  uses its DEFAULT capture-size curve when `enforce_eager=False`.
  Shape tuning is a 6B.4 follow-up if throughput numbers warrant.
* Prefill capture. V0 doesn't capture prefill; out of scope.
* Multi-GPU TP capture. Independent of CUDA Graphs; Tier 1 v2 item.

## 2. vLLM 0.7.3 V0 capture mechanism — what to expect

When the engine inits with `enforce_eager=False`:
1. Engine loads the model + creates the KV cache.
2. Engine warms up the model (runs a forward pass eagerly).
3. Engine enters a capture phase: for each batch size in the
   internal default curve, it captures a CUDA graph of the decode
   forward (varlen prefill doesn't capture).
4. After capture completes, runtime decode dispatches to the captured
   graph for matching batch shapes; off-curve sizes fall through to
   eager.

V0's default curve is approximately `[1, 2, 4, 8, 16, ..., 256]` (35
discrete batch sizes per the prior B-1 attempt's log). Each captured
graph allocates its own memory pool inside `torch.cuda.graph()`'s
allocator context — that's the source of the "sidecar memory growth"
budget. Empirically (from the brief's HBM math) we expect ~3-5 GB
of capture-pool overhead on Qwen-7B at gpu_memory_utilization=0.5.

The capture phase will surface ANY remaining host syncs, data-
dependent branches, or pointer-churn issues by crashing
("operation not permitted when stream is capturing"). 6B.1 + 6B.2
together close every host sync we've identified; the empirical
question is whether the ENTIRE captured forward (model embedding
layer + 28 attention layers + LM head) is now graph-safe.

## 3. Scope of changes

### 3a. `Int4ProtectedLLM` constructor

Currently (or as called by the smokes) `enforce_eager=True` is the
default. We change the constructor to:
* Default `enforce_eager` to the vLLM stock default (False).
* Existing callers that explicitly pass `enforce_eager=True` still
  work (smokes do this; the 6B.1 + 6B.2 smoke drivers pass it).
* New env var `PHASE6B3_FORCE_EAGER` for ops-level kill-switch
  (set to "1" to override and force eager mode even when the caller
  passes False). Same bisection-primitive pattern as 6B.1/6B.2's
  env vars.

Files touched:
* `KVPolicy/kv_policy/int4_protected.py` — the LLM constructor.
* The 6B.1 + 6B.2 smoke drivers DON'T change (they pass
  `enforce_eager=True` explicitly; capture-mode smoke is a new
  driver).

### 3b. New GPU smoke: `bench_phase6_b3_capture_gpu_smoke.py`

Same subprocess pattern as 6B.1 + 6B.2. Two cells:

| Cell | enforce_eager | Hook installed? | What's captured? |
|---|---|---|---|
| `eager`    | True (override `PHASE6B3_FORCE_EAGER=1`)  | Yes (6B.2 default) | Nothing — eager mode |
| `captured` | False (vLLM default with our patch)       | Yes (6B.2 default) | All decode forwards |

Both cells:
* Same model: Qwen-2.5-7B-Instruct (matching 6B.1 + 6B.2)
* Same prompts (Greendell + translation; max_tokens=32 greedy)
* Same hook install pattern as 6B.2

Comparison checks:
1. `completion_token_ids` byte-equal across cells (THE load-bearing
   correctness gate).
2. Both cells `write_path_fallback == 0`, `decode_calls_fallback == 0`.
3. Captured cell records peak HBM delta; reported in the smoke report
   (NOT a pass/fail gate — informational; budget reference is 5 GB).
4. Per-cell, run the workload TWICE; assert run1 == run2 token IDs
   (multi-batch determinism check; both cells separately).

### 3c. Multi-batch determinism check

For B ∈ {1, 2, 4, 8}, run the same prompt-set TWICE in the SAME
cell (no re-init between runs). Assert byte-equal completion tokens
across the two runs. This catches:
* Non-deterministic kernel ops triggered under capture
* Captured-graph memory pool reuse issues
* Allocator races

Implementation: extend the smoke driver to run B sweeps as a sub-
mode. Light addition to the existing 2-cell driver; ~30 LOC.

### 3d. Verify-under-capture sweep

Re-run the 7 existing verify scripts with `enforce_eager=False`.
Most of these scripts construct their own `Int4ProtectedLLM`; the
constructor flip propagates automatically. Specifically:

| Verify | What it covers | Re-run cost |
|---|---|---|
| `verify_phase5b_4c_1_write.py`         | Write path; uses bare PagedKVWriter, no LLM. **Skip** — not affected by capture flip. | $0 |
| `verify_phase5b_4c_2_read.py`          | Read path with int4 packed view. Uses LLM. Re-run under capture. | ~$0.02 |
| `verify_phase5b_4c_3_e2e.py`           | Full int4_protected E2E generation. Re-run under capture. | ~$0.02 |
| `verify_phase5b_5_needle.py`           | Needle-in-haystack quality bench. Re-run under capture on Qwen-7B + optional Mistral cross-family. | ~$0.05 + $0.05 |
| `verify_phase5b_6_batch.py`            | Multi-batch determinism gate at B in {2,4,8}. Re-run under capture. | ~$0.02 |
| `verify_phase5c_api.py`                | API shape contract. Re-run under capture. | ~$0.01 |
| `verify_phase6_d_step1_splice_equiv.py` | Splice equivalence. Bare paths, no LLM. **Skip**. | $0 |

Total GPU spend for the verify sweep: ~$0.12 (Qwen-only) or ~$0.17
(cross-family Mistral). Adds to 6B.3's headline GPU budget.

**Critical:** if any verify produces output divergent from its eager
baseline, that's a captured-graph correctness bug and 6B.3 RED.
Diagnose with:
1. AST + runtime capture-safe re-verify (CPU; should still GREEN).
2. Run the new `bench_phase6_b3_capture_gpu_smoke.py` at a single
   batch size and inspect the per-prompt diffs.
3. Live diagnostic dump from `diagnose_phase6_b_pre5_write_state.py
   --live` to see writer state pre/post a single captured forward.

### 3e. HBM growth measurement

Inside the captured cell of the new smoke:
```python
# Pre-capture: vLLM has loaded the model + KV cache but hasn't
# captured any graphs yet.
hbm_before = torch.cuda.memory_allocated()

llm = Int4ProtectedLLM(..., enforce_eager=False)
# vLLM init triggers capture automatically.

hbm_after_init = torch.cuda.memory_allocated()
hbm_after_warmup = ... # after the warmup generate

# Generate
...

hbm_after_generate = torch.cuda.memory_allocated()
```

Report `hbm_after_init - hbm_before` as the "capture overhead"
estimate. Budget reference: 5 GB. Above 5 GB → log as a sidecar
concern for 6B.4 (the brief's HBM budget at gpu_memory_utilization
=0.5 leaves ~40 GB; 5 GB of capture overhead is fine, 10 GB is
not).

Subtlety: `memory_allocated()` measures PyTorch's allocator only,
not the graph's memory pool which is separate. May need to also
sample `torch.cuda.memory_reserved()` (allocator reserved bytes)
or `torch.cuda.mem_get_info()` (raw free / total). The smoke
should report all three.

## 4. CPU work (minimal)

* Adjust `Int4ProtectedLLM` constructor (3a above) — one default
  change + env var gate. ~20 LOC.
* Build `bench_phase6_b3_capture_gpu_smoke.py` (3b + 3c + 3e
  combined). ~400 LOC; subprocess pattern + HBM measurement +
  multi-batch determinism check.
* Build `verify_phase6_b3_capture_under_eager_off.py` — a thin
  wrapper script that re-runs the 5 LLM-dependent verifies in
  sequence with the env override flipped, collecting tokens per
  verify and asserting they match a pre-saved eager reference.
  (Optional; the verifies themselves already run as standalone
  scripts. The wrapper is convenience.)
* Update `PHASE_6B_CUDA_GRAPHS_PLAN.md` status snapshot row.
* `PHASE_6B3_CAPTURE_GPU_SMOKE_RUNBOOK.md` (NEW) — operator runbook.

No new pytest tests (capture is GPU-only; everything we'd want to
test is GPU-side).

## 5. Test plan

### 5a. CPU pre-flight (run anywhere)

* Verify `Int4ProtectedLLM` constructor compiles + the env override
  works (smoke test: import + introspect signature).
* Verify the existing 36-cell verifiers + 27 hook tests + 99 pytest
  tests stay GREEN (regression after the constructor edit).

### 5b. GPU smoke (operator-triggered on A100 pod)

Three steps:
1. Pre-run orthogonality gate (Step 1 of the runbook; ~5 sec).
2. Run `bench_phase6_b3_capture_gpu_smoke.py` (~90 sec; ~$0.05).
   * 2 cells × 4 batch sizes × 2 runs each = 16 sub-trials.
3. Run the verify-under-capture sweep — five verify scripts each
   with capture enabled. ~$0.07.

Total budget: ~$0.12 (Qwen-only) to ~$0.17 (cross-family).

### 5c. Acceptance gate (G_CAPTURE)

Mirror the plan's gate:
1. ✅ All 5 LLM-dependent verifies GREEN under capture
   (`verify_phase5b_4c_2_read`, `verify_phase5b_4c_3_e2e`,
   `verify_phase5b_5_needle` on Qwen-7B, `verify_phase5b_6_batch`,
   `verify_phase5c_api`).
2. ✅ New smoke's `eager` vs `captured` cells produce byte-identical
   tokens at B in {1, 2, 4, 8}.
3. ✅ Multi-batch determinism: run1 == run2 in both cells at each B.
4. ✅ HBM growth (informational): reported in the smoke output.
   Optional pass/fail at ≤ 5 GB.
5. ✅ TIER5A orthogonality G5a/G5b/G5c/G6a/G6b all PASS (CPU + pod).
6. ✅ Cross-family sanity (optional): Mistral-7B needle 15/15
   under capture. NOT required to gate 6B.3 closure; opportunistic.

## 6. Anticipated GPU smoke shape

```
Phase 6B.3 GPU smoke — eager vs captured comparison
==============================================================================
Model: Qwen/Qwen2.5-7B-Instruct
Prompts: 2 (Greendell + translate)  max_tokens: 32

=== Cell EAGER ===
  enforce_eager=True (PHASE6B3_FORCE_EAGER=1)
  Hook: enabled, target=execute_model, stash_calls=N
  Loaded in 13.5s
  HBM after init:    14.6 GB
  HBM after warmup:  14.6 GB
  HBM after generate: 14.6 GB
  Generated in 2.0s
  call_stats: { write_path_fallback=0, decode_calls_fallback=0,
                write_decode_batched_calls=868, ... }

=== Cell CAPTURED ===
  enforce_eager=False
  Hook: enabled, target=execute_model, stash_calls=N
  Loaded in 32.4s   <-- includes capture phase
  HBM after init:    18.1 GB   <-- captures live here
  HBM after warmup:  18.1 GB
  HBM after generate: 18.1 GB
  Capture overhead: 3.5 GB (within 5 GB budget)
  Generated in 0.8s   <-- THIS is where 6B.4 measures throughput
  call_stats: same as eager except possibly fewer host syncs in
              the hot path (graphs are captured-eager replaced)

Checks:
  [PASS] completion_token_ids_byte_equal (B=1, prompt 0)
  [PASS] completion_token_ids_byte_equal (B=1, prompt 1)
  [PASS] multi_batch_determinism (B=2)  run1 == run2 byte-equal
  [PASS] multi_batch_determinism (B=4)  run1 == run2 byte-equal
  [PASS] multi_batch_determinism (B=8)  run1 == run2 byte-equal
  [PASS] both_cells_zero_fallbacks
  [PASS] capture_overhead_within_budget   (5 GB; informational)

Verdict: GREEN
```

If any check is RED → STOP; don't run the verify sweep until the
smoke is GREEN.

## 7. Risk areas + mitigations

### R-1: Capture crashes despite 6B.1 + 6B.2 preflights

**Concern:** there may be a host sync or pointer-churn issue in
non-write-path code (e.g., in the LM head, the embedding layer, or
a vLLM internal) that 6B.1 + 6B.2 didn't address. The first capture
attempt would crash with "operation not permitted when stream is
capturing" — the same error that gated B-1.

**Mitigation:**
* The smoke is designed to STOP on first crash. The
  diagnostic loop is well-rehearsed (AST verifier + live diagnostic
  + bisect by batch size).
* If capture crashes outside `Int4ProtectedAttentionImpl`'s code
  path, that's not a 6B.x issue — that's an upstream vLLM bug. We
  document and decide whether to:
  - Use a narrower `cudagraph_capture_sizes` curve to skip the
    bad shape
  - Submit a vLLM-side fix
  - Defer to 6B.4 V1-port escape hatch
* Two LOWER-COST fallback options (also in the plan-of-record):
  - Use vLLM V1 (Tier 2 work; 1-2 weeks separate)
  - Use Triton-fused-splice (Tier 3 fallback; ~$0.10)

### R-2: Sidecar memory growth exceeds 5 GB

**Concern:** V0's default ~35-shape curve allocates 35 captured-
graph memory pools. The total overhead could exceed 5 GB,
especially at gpu_memory_utilization=0.5 where only ~40 GB is
available for KV-cache + capture pools combined.

**Mitigation:**
* Smoke measures and reports HBM growth across multiple counters
  (allocated, reserved, free/total). Even if it exceeds 5 GB,
  the smoke proceeds — informational only.
* If HBM growth is enormous (>10 GB), we narrow the shape curve
  in a 6B.3.1 follow-up commit. vLLM V0 exposes
  `cudagraph_num_of_warmups` and related knobs.
* The 5 GB number is a budget reference (per the design doc §10
  of `PHASE_6B_CUDA_GRAPHS_PLAN.md`), not a hard fail.

### R-3: Multi-batch determinism RED under capture

**Concern:** captured graphs are deterministic by construction,
but some torch ops (e.g., reductions over non-power-of-2 batch
sizes) may use different kernels in capture pools vs eager — these
could be deterministic in isolation but introduce per-replay
variation if the memory pool reuses different addresses.

**Mitigation:**
* The smoke runs each cell TWICE (run1, run2) per batch size and
  asserts byte-equality. If RED, the root cause is in vLLM's
  capture-pool determinism, not our code.
* Workaround: report as a known limitation and continue 6B.4 if
  the magnitude is small (e.g., one token diverges at step 31
  but not earlier). Document the threshold.

### R-4: Byte-divergence between eager and captured cells

**Concern:** the eager and captured paths SHOULD produce byte-
identical tokens (greedy decode is deterministic given the same
KV state + same kernel math). If they diverge, that's a real
captured-graph correctness bug.

**Mitigation:**
* Inspect `per_prompt_diffs` to localize the first divergent
  token + which prompt.
* Run `diagnose_phase6_b_pre5_write_state.py --live` immediately
  post-divergence to compare writer state.
* AST verifier should still be GREEN — confirms captured-region
  source is clean.
* Worst case: ~1-2 days of capture-bisection (narrow shape curve,
  re-test). Same diagnostic loop B-1 prepared for.

### R-5: Per-verify GPU spend exceeds the $0.12 budget

**Concern:** running 5 verify scripts each requires its own engine
init (~$0.02 / verify). Total ~$0.10 + the smoke's $0.05 = $0.15.
Cross-family Mistral on needle adds another $0.05.

**Mitigation:**
* If needle is the dominant cost, run it last (after the other 4
  verifies pass). Drop cross-family from the gate; defer to 6B.4.
* If smoke is RED, ABORT verify sweep entirely — saves the $0.10.

### R-6: vLLM 0.7.3 V0 capture quirk we haven't seen

**Concern:** V0 is the older engine; capture has known limitations.
Specific issues that have surfaced in vLLM 0.7.3 V0:
* Capture doesn't work with `chunked_prefill_enabled=True`.
* Capture doesn't work with certain attention backends.
* Capture has issues with `num_scheduler_steps > 1`.

**Mitigation:**
* Smoke explicitly sets:
  - `chunked_prefill_enabled=False` (already default for V0)
  - `num_scheduler_steps=1` (default)
  - `enable_prefix_caching=False` (default)
* Use Int4ProtectedLLM's existing args; don't try V1-only knobs.

## 8. Files touched (concrete list)

| Path | Change type | G5c impact |
|---|---|---|
| `KVPolicy/kv_policy/int4_protected.py` | Edit: constructor default flip + env override. | RED → regen if int4_protected.py is in the G5c pin set (yes; already pinned). |
| `Bench/scripts/bench_phase6_b3_capture_gpu_smoke.py` (NEW) | New smoke driver. | n/a |
| `Bench/scripts/PHASE_6B3_CAPTURE_GPU_SMOKE_RUNBOOK.md` (NEW) | Operator runbook. | n/a |
| `Bench/scripts/PHASE_6B3_CAPTURE_DESIGN.md` (this file) | Design doc. | n/a |
| `Bench/scripts/PHASE_6B_CUDA_GRAPHS_PLAN.md` | Status snapshot row update for 6B.3. | n/a |
| `Bench/scripts/PHASE_6B3_CAPTURE_FINDINGS.md` (NEW; written post-GPU-smoke) | Closure finding doc. | n/a |
| `Bench/scripts/NEXT_SESSION_V2.md` | Closure entry for 6B.3. | n/a |
| `Bench/ctm_bench/scripts/int4_protected_files_baseline.json` (regen) | G5c baseline regen for int4_protected.py edit. | n/a (this IS the baseline) |

**Code NOT touched:**
* `kv_policy/phase5b_backend_install.py` — dispatch fork unchanged.
  Same code; just captured at runtime.
* `kv_policy/phase5b_4c_paged_writer.py` — write path unchanged.
* `kv_policy/phase6b2_precapture_hook.py` — hook unchanged.
* The forked `vllm_flash_attn` wheel — kernel. Unchanged.
* `Int4ProtectedAttentionImpl`'s class fingerprint. G5a preserved.

## 9. Acceptance criteria — G_CAPTURE

Restated from `PHASE_6B_CUDA_GRAPHS_PLAN.md` §"Phase 6B.3 acceptance
gate":

1. ✅ Capture succeeds for all 8 starter shapes (or vLLM V0's
   default ~35-shape curve) without error.
2. ✅ All 5 LLM-dependent existing verifies GREEN under capture.
3. ✅ Sidecar memory growth measured + reported. Pass at ≤ 5 GB;
   >5 GB logged as a concern for 6B.4 shape tuning.
4. ✅ Multi-batch determinism preserved: run1 == run2 byte-equal at
   B ∈ {2, 4, 8} both in eager AND captured cells.
5. ✅ New smoke's eager vs captured byte-equivalence at B=1 + B=8.
6. ✅ TIER5A orthogonality G5a/G5b/G5c (regen'd) /G6a/G6b all PASS.

## 10. Day-level timeline

Total: 1-2 engineer-days CPU + ~$0.12-0.17 GPU at G_CAPTURE gate
verification.

| Day | Deliverable | Acceptance |
|---|---|---|
| **Day 1 (CPU)** | Int4ProtectedLLM constructor flip + env override. Land smoke driver + runbook + design doc. CPU regression sweep stays GREEN. Update plan status. | 99 pytest + 36+36 equivalence verifiers GREEN. G5c regen'd. |
| **Day 2 (GPU)** | Operator-triggered smoke + verify sweep on A100. Capture either succeeds (G_CAPTURE GREEN) or surfaces a specific failure mode (diagnosed via the troubleshooting matrix). If GREEN: closure doc landed. | All 6 acceptance gates PASS on the pod. Closure finding doc records: capture overhead in GB; per-batch-size determinism; per-verify GREEN status. |

If Day 2 surfaces a capture failure that isn't on the troubleshooting
matrix, that's a 6B.3.1 follow-up commit (narrow shape curve, fix
specific issue) BEFORE re-attempting the gate.

## 11. What this design does NOT cover (deferred)

* **Throughput re-measurement.** Phase 6B.4 entirely. The smoke
  measures HBM but NOT tok/s — that's by design (throughput is the
  ship narrative; we don't co-mingle gates).
* **Brief edit.** Gated on 6B.4 throughput measurement.
* **Shape curve tuning.** If V0's default works, we don't customize.
  If it doesn't, that's a 6B.4 task.
* **vLLM V1 port.** Tier 2 v2 work; separate plan.
* **Prefill capture.** Not in V0's capability set.

## 12. Decision point for the user

Three options (same pattern as 6B.1 + 6B.2):

| Option | What happens |
|---|---|
| **(A) Approve as written.** | I implement Day 1 (CPU prep) per §10 timeline. Operator triggers Day 2 on the A100 pod. Closure either lands GREEN or surfaces a specific failure mode for follow-up. |
| (B) Approve with modifications. | User feedback on specific sections; I revise + re-submit. |
| (C) Reject / pause. | A risk in §7 looks load-bearing; I provide additional CPU-only proof before any code lands. |

**Recommendation: (A).** The pattern matches 6B.1 + 6B.2. The risk
surface is well-cataloged (R-1..R-6 all have mitigations). Worst
case is a known V0 capture limitation, which lands as a 6B.3.1
follow-up. Best case is a clean smoke + verify GREEN, taking us to
Phase 6B.4 (throughput) with no remaining capture work.

Phase 6B.4 (throughput re-measurement + brief edit proposal) stays
gated on a separate approval after this phase closes GREEN.
