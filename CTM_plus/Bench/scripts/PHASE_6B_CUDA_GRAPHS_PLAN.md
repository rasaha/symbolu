# Phase 6B CUDA Graphs — plan-of-record (no code yet)

> **Status:** Plan-of-record only. No code shall land on this plan
> without explicit per-phase user approval, per the project's
> discipline rules.
>
> **Builds on:** `OPTION_B_PREFLIGHT.md` (read-path preflight
> B-pre-1..4 COMPLETE; B-1 smoke test FAILED at the write path).
> See "Status snapshot" below for what's already done vs what's
> outstanding.
>
> **Why now:** TIER5A closed POSITIVE (warm-tier swap-restore is
> byte-clean — see `PHASE_TIER5A_SWAP_RESTORE_FINDINGS.md`). The
> next-highest-leverage Tier 1 v2 item per
> `INT4_PROTECTED_VC_BRIEF.md` Page 5 is **CUDA Graphs**, which
> directly addresses the 4.3× per-seq decode latency caveat — the
> single biggest objection in every partner conversation grounded
> in the current measured numbers.

## Status snapshot (where we are post-TIER5A)

| Sub-phase | Status | Reference |
|---|---|---|
| Phase 6 perf profile (justifies the project) | ✅ DONE | `PHASE6_PERF_REPORT.md` §"DECODE PHASE PROFILE" |
| B-pre-1: slot-pool storage on writer + device-indexed read API | ✅ DONE | commit `78e19c2` + sibling fixes |
| B-pre-2 + B-pre-3: device metadata + unconditional splice | ✅ DONE (bundled) | commit `7f1a168` |
| B-pre-4: pointer stability audit + persistent buffers | ✅ DONE | commits `54e4fc3`, `4b18fd8` |
| B-1 capture-enable smoke (first attempt) | ❌ FAILED at write-path `.item()` | commit `c2be606` |
| **Phase 6B.1 — Write-path preflight** | ✅ **CLOSED, GREEN** (GPU smoke Qwen-7B + Mistral-7B + A100) | `PHASE_6B1_WRITE_PREFLIGHT_FINDINGS.md` |
| **Phase 6B.2 — Pre-capture seq_id resolution hook** | ✅ **CLOSED, GREEN** (GPU smoke Qwen-7B + A100; 28× host-sync amortization) | `PHASE_6B2_PRECAPTURE_HOOK_FINDINGS.md` |
| **Phase 6B.3 — enforce_eager=False flip + capture-enable — CPU prep DONE** | CPU regression GREEN; GPU smoke awaiting operator on A100 | `PHASE_6B3_CAPTURE_DESIGN.md` + `bench_phase6_b3_capture_gpu_smoke.py` + `PHASE_6B3_CAPTURE_GPU_SMOKE_RUNBOOK.md` |
| Throughput bench + finding doc (Phase 6B.4) | NOT STARTED — gated on 6B.3 GREEN | this plan |

The read path is **graph-capturable today**. The write path runs
BEFORE the read path inside vLLM's captured forward, and it still
has the same anti-patterns the read-path preflight solved:
`.item()` calls, Python dict lookups by seq_id, conditional
partition loops. The B-1 smoke surfaced this immediately.

## Goal

**Measured target:** ≥ 80 tok/s aggregate at B=8 on Qwen-7B H100
(currently 42.6 tok/s). That's ≥ 1.88× — within the 2-3× projected
range. Hit this with `enforce_eager=False` and a curated multi-shape
capture configuration on vLLM 0.7.3 V0.

**Acceptance:** all six gates GREEN (defined below). Finding doc
records the measured throughput + any caveats (sidecar memory cost,
shape-bucket coverage, etc.).

**Brief update (gated on green):** the Page 6 Measured table's
"Per-seq decode latency ~4.3× bf16" caveat becomes "**Per-seq decode
latency ~Y× bf16; aggregate ~80-100 tok/s @ B=8** with CUDA Graphs"
where Y is the measured ratio post-capture. Approval required
before any brief edit (discipline rule).

## Why this is partner-credible work

1. Profile data EXISTS (`PHASE6_PERF_REPORT.md` §"DECODE PHASE PROFILE"
   shows 90% of decode time is launch overhead at B=8) — the projected
   2-3× has measurement backing the diagnosis, not just intuition.
2. The mechanism is **vLLM's documented optimization path**
   (`compilation_config.cudagraph_capture_sizes`) — no custom infra.
3. Read-path preflight is COMPLETE and gates GREEN, proving the
   structural refactor pattern works without correctness loss.
4. The write-path is the next instance of the SAME pattern; the
   discipline that landed B-pre-1..4 is reusable.
5. TIER5A's orthogonality gate (G5 + G6) catches any inadvertent
   touch to the int4_protected backend stack before GPU spend —
   provides the same safety net we used in TIER5A.

## Phased plan

Each phase has explicit deliverables + acceptance criteria. **No
phase advances without user approval of the prior phase's
deliverable.** CPU-first verification per discipline rule #4.

### Phase 6B.1 — Write-path preflight (CPU work; 2-3 days)

Mirror the read-path preflight (B-pre-1..4) on the write path.

**Deliverables:**
1. **Write-path slot resolution refactor.** Replace
   `_seq_id_from_block_table_row(bt_row) = int(bt_row[0].item())`
   with a pre-resolved slot tensor that's set OUTSIDE the captured
   region. Mirrors B-pre-1's read-path slot-pool pattern.
2. **Device-side write-partition derivation.** Replace
   `_derive_write_partitions`'s Python loop with device tensor ops
   producing per-seq write metadata (slot_idx, start_pos, length).
   Mirrors B-pre-2/3's unconditional-splice pattern.
3. **Pointer stability audit for write path.** Run
   `audit_phase6_b_pre4_pointer_stability.py`-style audit on the
   `PagedKVWriter.write` kernel args; pre-allocate any churning
   buffers. Mirrors B-pre-4.
4. **New CPU test:**
   `verify_phase6_b_pre5_write_path_capture_safe.py` — asserts
   write path uses zero `.item()` calls and zero dict lookups in
   the captured region (AST + runtime instrumentation).
5. **Equivalence verify:**
   `verify_phase6_b_pre5_write_equiv.py` — asserts new write path
   produces byte-identical KV cache state vs legacy path across the
   mixed workload from `verify_phase5b_4c_1_write.py`.

**Phase 6B.1 acceptance gate (G_PRE-WRITE):**
- AST + runtime checks: zero `.item()` calls in the write path's
  captured region; zero per-call dict lookups.
- Write equivalence: legacy and refactored write paths produce
  byte-identical KV state for a 64-step decode on B in {1, 2, 4, 8}.
- All existing verifies still GREEN
  (`verify_phase5b_4c_*.py`, `verify_phase5b_5_needle.py`,
  `verify_phase5b_6_batch.py`).
- TIER5A orthogonality gate (G5 + G6) GREEN — the write-path
  refactor MUST NOT modify `Int4ProtectedAttentionImpl`, the
  forked vLLM-FA kernel, or the protected-channel splice logic.

**Estimated:** 2-3 engineer-days CPU work + ~$0.02 GPU smoke to
confirm the refactored write path produces unchanged decode output
at one (B, model) pair. Total ~$0.02.

### Phase 6B.2 — vLLM integration: pre-capture seq_id resolution hook (CPU + small GPU; 2-3 days)

The captured graph is fixed at capture time. vLLM resolves seq_ids
fresh on every step. Bridge: a hook that resolves seq_id → slot
PRE-capture and feeds the device-side slot tensor INTO the captured
region.

**Deliverables:**
1. **Hook design doc** identifying which vLLM 0.7.3 V0 entry point
   to attach to. Candidates: `prepare_model_input`, worker forward
   prologue, scheduler step output. Pick one with the most stable
   integration surface.
2. **Hook implementation.** Monkey-patches vLLM's chosen entry point
   to call `writer.slot_indices_for(seq_ids)` and stash the result on
   the model input dict. The captured forward reads from there.
3. **Hook teardown** in LIFO order on engine shutdown (matches the
   TIER5A install pattern).
4. **CPU tests with mocked vLLM** asserting the hook's resolution
   logic matches the runtime expectations (similar pattern to
   TIER5A.2 composition smoke).

**Phase 6B.2 acceptance gate (G_HOOK):**
- Hook resolves seq_ids → slots correctly on a mock vLLM scheduler
  step output (CPU test).
- Hook teardown is idempotent (LIFO; safe to call twice — same
  pattern as TIER5A's install handles).
- Live engine smoke: a single B=2 decode step routes through the
  hook without error and produces correct output (compared against
  the eager baseline).
- TIER5A orthogonality gate (G5 + G6) GREEN.

**Estimated:** 2-3 engineer-days + ~$0.05 GPU smoke. Total ~$0.05.

### Phase 6B.3 — Capture-enable + correctness gates (~$0.10 GPU; 1-2 days)

Flip `enforce_eager=False` on `Int4ProtectedLLM`, configure
`compilation_config.cudagraph_capture_sizes` with a conservative
shape curve, re-run every correctness gate under capture.

**Conservative starter shape curve:**
`[(1, 1), (1, 4), (1, 16), (1, 64), (2, 64), (4, 64), (8, 64), (8, 128)]`

(Same as `OPTION_B_PREFLIGHT.md` §B-1; covers the existing bench
workload and decode-step shapes for B in {1, 2, 4, 8} up to
2048-token context.)

**Deliverables:**
1. Capture succeeds for all 8 starter shapes without error.
2. All existing verifies GREEN under capture:
   - `verify_phase5b_4c_1_write.py`
   - `verify_phase5b_4c_2_read.py`
   - `verify_phase5b_4c_3_e2e.py`
   - `verify_phase5b_5_needle.py` (re-run on Qwen-7B + at least one
     other model for cross-family confidence)
   - `verify_phase5b_6_batch.py`
   - `verify_phase5c_api.py`
   - `verify_phase6_d_step1_splice_equiv.py`
3. Sidecar memory growth measured + reported (compare HBM use
   pre/post capture; budget: ≤ 5 GB increase per the brief's
   80 GB total context).
4. Multi-batch determinism preserved under capture
   (run1 == run2 byte-identical at B ∈ {2, 4, 8}).

**Phase 6B.3 acceptance gate (G_CAPTURE):**
- All correctness verifies GREEN under `enforce_eager=False`.
- Any output divergence vs eager mode = STOP, diagnose. Most
  likely pointer-churn or data-dependent branch that escaped the
  preflight.
- HBM growth ≤ 5 GB; if larger, narrow the shape curve.
- TIER5A orthogonality gate G5 + G6 GREEN pre + post.

**Estimated:** 1-2 days + ~$0.10 GPU. Total ~$0.10.

### Phase 6B.4 — Throughput bench + finding doc (~$0.10 GPU; 1 day)

Measure the actual throughput delivery. Lock the new ship
narrative.

**Deliverables:**
1. `bench_phase6_batched_throughput.py` re-run at B ∈ {1, 2, 4, 8}
   with capture enabled. Same n_runs=5 median methodology used for
   the original Phase 6 baseline measurement.
2. `PHASE_6B_CUDA_GRAPHS_FINDINGS.md` — measured finding doc
   following the `PHASE_TIER5A_SWAP_RESTORE_FINDINGS.md` template:
   - TL;DR table (gates GREEN/RED; throughput numbers)
   - Methodology + cells
   - Per-B numbers vs the pre-capture baseline (eager mode)
   - Sidecar memory cost reported
   - Lessons learned (durable)
   - Code disposition
   - Deferred items
3. Update `NEXT_SESSION_V2.md` with the Phase 6B closure entry.
4. **Brief update proposal** (text only, NOT applied without
   explicit approval per discipline rule #4): Page 6 Measured
   table's per-seq-latency row updates with measured agg
   throughput; Page 5 Tier 1 CUDA Graphs row marks COMPLETE.

**Phase 6B.4 acceptance gate (G_THROUGHPUT):**
- Measured agg_tps @ B=8 ≥ 80 tok/s (≥ 1.88× the 42.6 baseline).
  Below this: STOP, diagnose. Either the projection was wrong
  (write up the actual factor; brief stays unchanged) or capture
  isn't covering the right shape bucket.
- Cross-family sanity: at least one non-Qwen model (e.g.,
  Mistral-7B or Llama-3.1-8B) re-verifies the 1.88×+ ratio.
  Otherwise: report Qwen-only; mark as "cross-family extension
  pending".
- TIER5A orthogonality gate G5 + G6 GREEN pre + post.

**Estimated:** 1 day + ~$0.10 GPU. Total ~$0.10.

## Acceptance gates (load-bearing — analogous to TIER5A G1..G6)

| Gate | What it checks | Pass criterion |
|---|---|---|
| **G_PRE-WRITE** | Write path is graph-capture-safe | Zero `.item()` / dict lookups in captured region; byte-equiv to legacy |
| **G_HOOK** | vLLM integration hook resolves seq_ids pre-capture | CPU smoke + B=2 live smoke produces correct output; teardown idempotent |
| **G_CAPTURE** | Captures succeed + correctness preserved | All 7 verifies GREEN under capture; HBM ≤ +5 GB; multi-batch determinism preserved |
| **G_THROUGHPUT** | Measured agg throughput @ B=8 | ≥ 80 tok/s (≥ 1.88× the 42.6 baseline); cross-family sanity on 1 non-Qwen model |
| **G_ORTHOGONALITY (TIER5A G5 + G6)** | int4_protected backend untouched | All four in-tree tracks (G5a/G5b/G5c/G6a) PASS; G6b PASS on the GPU pod after the wheel SHA is verified |

**Overall PASS = all five gates GREEN.**

## Effort + GPU $ summary

| Phase | Engineer days | GPU $ | Cumulative |
|---|---:|---:|---:|
| 6B.1 (write-path preflight) | 2-3 | ~$0.02 | $0.02 |
| 6B.2 (vLLM integration hook) | 2-3 | ~$0.05 | $0.07 |
| 6B.3 (capture-enable + verify) | 1-2 | ~$0.10 | $0.17 |
| 6B.4 (throughput bench + finding doc) | 1 | ~$0.10 | $0.27 |
| **Total** | **6-9 days** | **~$0.27** | |

Bracketed against the brief's original estimate of "4-7 days +
~$0.20 GPU" for CUDA Graphs. The wider day range reflects the
preflight surprise (read-path preflight took 3-4 weeks; write path
is structurally similar so 2-3 days is realistic but not
guaranteed).

## Risks + open questions

### Critical risks

1. **vLLM 0.7.3 V0 engine has limited graph-capture support.** The
   `compilation_config.cudagraph_capture_sizes` API is from V1 /
   newer vLLM. V0's capture surface is more limited and the B-1
   first attempt failed inside V0's capture loop.
   **Mitigation:** the failure mode in B-1 was a write-path issue,
   not a V0 limitation per se. Phase 6B.1 + 6B.2 address that. If
   V0 still won't capture after 6B.2, the fallback is **port to
   vLLM V1** (Tier 2 v2 work; 1-2 weeks). This is a known item in
   the roadmap and would be the right move regardless of capture
   for forward-compat reasons.

2. **Sidecar memory growth.** vLLM's graph capture allocates memory
   per captured shape. With 8 shapes in the conservative curve and
   our existing sidecars (k_scale_ext, etc.), 5 GB is a guess.
   **Mitigation:** start with a smaller shape curve
   `[(8, 64), (8, 128)]` for the smoke; expand if needed; monitor
   HBM use directly. If a single capture eats > 10 GB, narrow
   `cudagraph_capture_sizes` aggressively or use
   `cudagraph_num_of_warmups` tuning.

3. **Projection doesn't hold.** The 2-3× is based on phase profile
   showing 90% of decode is launch overhead. If real-world capture
   only collapses 50% of that overhead, agg_tps lifts ~1.5×, not
   ~2×.
   **Mitigation:** the G_THROUGHPUT gate sets the bar at 1.88×, not
   2× or 3×, to give honest room. If we hit 1.5×, the brief still
   gets a better story; we report the actual factor.

### Open questions (resolved as we go)

1. **Which vLLM entry point is the right hook target for pre-capture
   seq_id resolution?** Candidates listed in 6B.2 deliverable #1.
   Concrete pick is part of the 6B.2 design doc.

2. **Does `torch.cuda.graph()`'s memory pool tame the 4 CYCLE / 2
   CHURN allocator-rotation args** (`query_q`,
   `k_packed_protect_bf16`, `k_packed_scale`, `v_packed_xmin`,
   `k_packed_xmin`, `v_packed_scale` per the B-pre-4 audit)?
   **Resolved empirically by 6B.3.** If they break capture, the
   fallback is per-arg explicit pinning via `cudagraph_capture_sizes`
   tuning or — worst case — moving the gather into a separate
   pre-capture step.

3. **Should Phase 6B.4's finding doc be the trigger for the brief
   edit, or should the brief edit wait for cross-family completion
   (e.g., all 4 models re-verified under capture)?**
   **Recommendation:** finding doc captures the measured number;
   brief edit waits for at least one cross-family non-Qwen
   replication so we can claim "measured on 2+ models" rather than
   "measured on Qwen only". User approves the brief edit per
   discipline rule #4 regardless.

### Parallel-track alternatives (NOT in this plan; ARCHAEOLOGY)

These were mentioned in `OPTION_B_PREFLIGHT.md` §"Risks" as
possible substitutes. Captured here for completeness; not
recommended as the primary path because CUDA Graphs is the
documented vLLM mechanism and the higher-leverage win.

* **Triton-fused-splice** — fuse the read-path splice into a single
  Triton kernel. Estimated ~7 ms / step savings at B=8 (~+15-25%
  agg_tps). Worth exploring if capture delivers under 1.5× by
  itself, but it's a fallback, not a parallel track.
* **C++/extension fast paths** — even faster than Triton but
  significantly more engineering time. Out of scope for v2.

## Discipline rules + approvals (per project convention)

1. **No code lands without per-phase user approval.** Each of
   6B.1, 6B.2, 6B.3, 6B.4 requires a separate go-ahead.
2. **CPU-first verification** for 6B.1 and 6B.2 (CPU tests + mocks
   before GPU smoke).
3. **TIER5A orthogonality gate runs pre + post every GPU change**
   to guarantee no int4_protected backend modification.
4. **Brief edits require explicit user approval** post-G_THROUGHPUT
   measurement; the finding doc is the artifact.
5. **No combined-stack X× projections without measurement.**
   Report the actual measured factor; don't multiply with TIER5A's
   2× concurrency unless we explicitly measure the combined cell.
6. **Phase-gated execution.** If 6B.1's G_PRE-WRITE fails, the
   plan pauses. If 6B.2's G_HOOK fails, the plan pauses. Don't
   chain forward through a RED gate.

## Decision required from user before any code

Three options:

| Option | What happens | Estimate |
|---|---|---|
| **(A) Approve 6B.1 only** (recommended) | I draft a more detailed design doc for the write-path preflight + the CPU test plan, then implement 6B.1 to G_PRE-WRITE. 6B.2 / 6B.3 / 6B.4 stay gated on a separate approval each. | 2-3 days + ~$0.02 GPU |
| (B) Approve full 6B.1 → 6B.4 path | I implement the full plan with one approval; checkpoint at each gate but don't pause for user sign-off between phases. Higher risk if surprises surface mid-phase. | 6-9 days + ~$0.27 GPU |
| (C) Discuss the plan first | We refine the plan, identify edge cases, sequence vLLM V1 port if relevant. No code yet. | 0 GPU |

My recommendation: **(A).** Same per-phase approval pattern that
worked for TIER5A — small commit windows, easy to course-correct,
each gate has a clear pause point.

## What this plan does NOT cover (deferred)

- **vLLM V1 port.** Tier 2 v2 work; 1-2 weeks separate. If V0
  capture proves intractable in 6B.2 / 6B.3, V1 port becomes the
  blocker — handled as its own plan.
- **Cross-family throughput measurement** beyond Qwen-7B (Mistral,
  Llama, Qwen-14B). Phase 6B.4 includes ONE cross-family sanity
  check; full validation across the 4-model portfolio is a
  follow-up.
- **70B-class TP integration with graphs.** TP first (Tier 1 #2
  in the brief), then graphs-with-TP, sequenced after Phase 6B.
- **The other Tier 1 items** (Quality bench, Auto seq-eviction).
  Independent of CUDA Graphs; can land in parallel sessions if
  there's bandwidth.

---

*This plan is reviewable; no commitments until you approve a
specific phase. CPU-first verification preserves the discipline
that landed TIER5A cleanly.*
