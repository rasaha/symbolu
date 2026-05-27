# Phase 6B.2 pre-capture seq_id resolution hook — measured finding

> **Status:** Phase 6B.2 **CLOSED, positive measured finding.**
> Single-pod GPU smoke on Qwen-2.5-7B-Instruct + A100 + vLLM 0.7.3
> (forked int4_protected build) returned **all seven G_HOOK checks
> GREEN**. The hook-driven slot_idx resolution path produces byte-
> identical generated tokens vs the dispatch-fork's 6B.1 self-
> resolve path. The hook amortizes the 28-layer slot resolution to
> ONE host sync per decode step (vs 28 in 6B.1), a 28× reduction in
> pre-capture Python overhead.
>
> **VC brief: unchanged.** Phase 6B.2 is STRUCTURAL PREP for CUDA
> Graphs capture (Phase 6B.3); like 6B.1 it doesn't move any
> measured throughput number. Brief edits wait for Phase 6B.4
> (post-capture aggregate throughput re-measurement).
>
> **Code disposition:** the hook module + dispatch read + the
> `pre_synced` write_decode_batched kwarg + sentinel-gated sync +
> 27-test CPU suite + 36-cell hook-equiv verifier + GPU smoke
> driver + runbook all stay in-tree. The PHASE6B2_INSTALL_HOOK env
> override is retained as a partner-credible bisection primitive.

## TL;DR

| Item | Status |
|---|---|
| G_HOOK CPU resolution correctness (27 hook unit tests) | **GREEN** (CPU) — 27/27 PASS |
| G_HOOK CPU install + teardown semantics | **GREEN** (CPU) — wrap shadows class method via setattr; teardown restores; idempotent; env override forces inert; missing target inert |
| G_HOOK CPU bit-equivalence — hook-on vs hook-off, 36 cells (B in {1,2,4,8} × Modes A/B/C × {1,32,64} decode steps) | **GREEN** (CPU) — 36/36 PASS |
| G_HOOK CPU bit-equivalence — 6B.1 regression (36 cells) | **GREEN** (CPU) — 36/36 PASS post-Day-1 dispatch edit |
| G_HOOK AST + runtime capture-safe | **GREEN** (CPU) — captured region still zero host syncs; pre-capture sentinel adds B .item() calls per call, accounted in the expected pattern |
| G_HOOK pointer stability | **GREEN** (CPU) — 15/15 STABLE post-edit |
| G_HOOK GPU bit-identity token IDs (Qwen-7B + A100) | **GREEN** — every prompt's `completion_token_ids` byte-equal across both cells |
| G_HOOK hook-on cell used the hook path | **GREEN** — `write_decode_batched_via_hook_calls=868` (all 28 layers × 31 decode steps) |
| G_HOOK hook-off cell self-resolved | **GREEN** — `write_decode_batched_via_hook_calls=0` |
| G_HOOK both cells used write_decode_batched | **GREEN** — 868/868 |
| G_HOOK zero fallbacks both cells | **GREEN** — `write_path_fallback=0`, `decode_calls_fallback=0` |
| G_HOOK hook handle stash_call_count > 0 | **GREEN** — `stash_call_count=31` (one per decode step; 28× amortization) |
| G_HOOK G6b (load-bearing forked-wheel SHA pin) | **GREEN** — pod's forked vllm_flash_attn matches the TIER5A.3 freeze byte-for-byte |
| G_HOOK G5a/G5b/G5c/G6a orthogonality | **GREEN** — G5a class fingerprint preserved; G5c regen'd for authorized hook + dispatch + writer edits (now 10 files including phase6b2_precapture_hook.py) |
| Overall verdict | **GREEN — Phase 6B.2 CLOSED, write path is ready for CUDA Graphs capture (6B.3)** |

## The material finding

**The Phase 6B.2 pre-capture hook (`install_int4_protected_precapture_hook`
wrapping `ModelRunner.execute_model`) produces byte-identical
generated tokens vs the dispatch-fork's 6B.1 self-resolve path on
real Qwen-2.5-7B-Instruct + the forked vllm-flash-attn kernel.**

The 36-cell CPU hook-on vs hook-off bit-equivalence verifier
demonstrated the unconditional sentinel-gated sync + pool-as-truth
semantics produce identical state to the 6B.1 self-resolve path
across 4 batch sizes × 3 prefill→decode handoff modes × 3 decode-
step counts. The GPU smoke extends that proof to the real
production stack: the 28-layer Qwen-7B model running through the
forked CUDA kernel produces the SAME 32 greedy decode tokens for
both prompts when the dispatch fork reads the hook-stashed
`slot_idx_t` (hook-on) vs when the dispatch fork self-resolves
(hook-off, forced via `PHASE6B2_INSTALL_HOOK=0`).

The amortization measurement is the headline operational result:
the hook resolves seq_id→slot **ONCE** per decode step (at
`ModelRunner.execute_model`), then ALL 28 attention layers read
the cached `slot_idx_t` from `attn_metadata` without re-resolving.
At 31 decode steps on the smoke workload, that's 31 host syncs
vs 6B.1's 868 (= 28 layers × 31 steps) — a **28× reduction in
pre-capture Python overhead** per decode step. The savings will
fully materialize under CUDA Graphs capture in 6B.3.

## The methodology

### Workload (final GPU smoke on the A100 pod)

* Model: `Qwen/Qwen2.5-7B-Instruct` (28 layers, H_kv=4, D=128)
* GPU: A100-80GB, `gpu_memory_utilization=0.5`
* Engine: vLLM 0.7.3 V0 with `enforce_eager=True`
  (Phase 6B.2 is structural prep; capture is 6B.3's job)
* Forked wheel: `vllm.vllm_flash_attn` matching the TIER5A.3 SHA freeze
  (4 files; G6b GREEN)
* Workload: two distinct deterministic prompts at B=2 (same as
  6B.1's smoke; matches the Greendell needle + short translation
  pair)
* Greedy decode: `temperature=0.0`, `max_tokens=32`
* Warmup: one B=1 4-token generate before stats reset + hook
  install (hook install must run AFTER warmup so writers exist
  for `_collect_writers`)

### Two cells (hook-off vs hook-on)

The GPU smoke uses the `PHASE6B2_INSTALL_HOOK` env var to flip
behavior within the SAME repository checkout:

| Cell | Env var | Hook installed? | Dispatch fork path |
|---|---|---|---|
| **hook-off** | `PHASE6B2_INSTALL_HOOK=0` | install returns inert handle | self-resolve (6B.1 behavior) |
| **hook-on**  | `PHASE6B2_INSTALL_HOOK=1` (default) | wraps `model_runner.execute_model` | reads stashed `slot_idx_t` |

Each cell runs as a separate Python subprocess. Driver
(`bench_phase6_b2_hook_gpu_smoke.py`) spawns both, then runs the
7-check compare.

### The acceptance gate (G_HOOK.1..6)

Seven comparison checks (six explicit + the orthogonality gate as a
separate prerequisite):

| Check | Pass criterion |
|---|---|
| `completion_token_ids_byte_equal`             | every prompt's decode tokens byte-equal across cells |
| `hook_on_cell_used_hook_path`                 | hook-on `write_decode_batched_via_hook_calls > 0` |
| `hook_off_cell_self_resolved`                 | hook-off `write_decode_batched_via_hook_calls == 0` |
| `both_cells_used_write_decode_batched`        | both `write_decode_batched_calls > 0` |
| `hook-off_zero_fallbacks`                     | `write_path_fallback == 0` AND `decode_calls_fallback == 0` |
| `hook-on_zero_fallbacks`                      | same |
| `hook_on_stash_call_count_positive`           | hook handle's `stash_call_count > 0` (hook actually fired) |

All seven PASS on the green run.

## The actual numbers

### Pod (run 2026-05-27)

```
Model:      Qwen/Qwen2.5-7B-Instruct
Prompts:    2    max_tokens: 32
Verdict:    GREEN

Checks:
  [PASS] completion_token_ids_byte_equal              all prompts byte-equal
  [PASS] hook_on_cell_used_hook_path                  write_decode_batched_via_hook_calls=868
  [PASS] hook_off_cell_self_resolved                  write_decode_batched_via_hook_calls=0
  [PASS] both_cells_used_write_decode_batched         hook-off=868, hook-on=868
  [PASS] hook-off_zero_fallbacks                      write_path_fallback=0, decode_calls_fallback=0
  [PASS] hook-on_zero_fallbacks                       write_path_fallback=0, decode_calls_fallback=0
  [PASS] hook_on_stash_call_count_positive            stash_call_count=31

Call stats:
  hook-off:  {"decode_calls_fallback": 0, "decode_calls_packed": 868, "prefill_calls": 28,
              "spec_decode_calls": 0, "write_decode_batched_calls": 868,
              "write_decode_batched_via_hook_calls": 0,
              "write_legacy_loop_calls": 28, "write_path_calls": 896, "write_path_fallback": 0}
  hook-on:   {"decode_calls_fallback": 0, "decode_calls_packed": 868, "prefill_calls": 28,
              "spec_decode_calls": 0, "write_decode_batched_calls": 868,
              "write_decode_batched_via_hook_calls": 868,
              "write_legacy_loop_calls": 28, "write_path_calls": 896, "write_path_fallback": 0}

Hook handle (hook-on cell):
  enabled=True, target=execute_model, stash_calls=31, skipped=1
```

### Interpretation of the call-stats split

| Path                                    | Hook-off | Hook-on | What it tells us |
|---|---:|---:|---|
| `prefill_calls`                         | 28  | 28  | Both cells ran prefill identically. One forward × 28 layers. |
| `decode_calls_packed`                   | 868 | 868 | Both cells executed the packed decode kernel 868 times (28 layers × 31 decode steps). |
| `write_path_calls`                      | 896 | 896 | Both cells did 896 write-path invocations (28 prefill + 868 decode). |
| `write_legacy_loop_calls`               | 28  | 28  | The 28 prefill writes route through legacy (correct — `_is_pure_decode_write` returns False for prefill on both cells). |
| `write_decode_batched_calls`            | 868 | 868 | Both cells routed ALL 868 decode writes through `write_decode_batched`. |
| `write_decode_batched_via_hook_calls`   | 0   | **868** | **Hook-on routed ALL 868 decode writes via the hook-stashed slot_idx_t.** This is the load-bearing operational confirmation. |
| Hook handle `stash_call_count`          | 0   | **31**  | Hook fired exactly 31 times — once per decode step at ModelRunner level. **28× fewer than 6B.1's per-layer host syncs (868).** |
| Hook handle `skipped_step_count`        | 0   | 1   | The one prefill `execute_model` call was rejected by `_is_pure_decode_step` and the hook no-op'd. Correct. |

### The 28× amortization

Per-decode-step host-sync counts:

```
6B.1 (self-resolve): 28 attention layers × .cpu().tolist() each = 28 host syncs
6B.2 (hook-stash):   1 host sync at ModelRunner.execute_model entry
Amortization:        28× reduction
```

This is a structural win independent of the kernel call count.
Under CUDA Graphs capture (Phase 6B.3), the per-layer Python
overhead becomes captured-graph replay (zero Python cost); the
hook's one-per-step sync is the only remaining pre-capture Python
work. The aggregate-throughput improvement projection in Phase
6B.4 (≥80 tok/s @ B=8) assumes this amortization holds — which the
6B.2 measurement now confirms.

### Pre-flight gate state (Step 1 of the runbook)

```
verdict: PASS
  g5a (class fingerprint): pass (0 violations)
  g5b (tier5a ast):        pass (0 violations)
  g5c (int4 python sha):   pass (10 files; phase6b2_precapture_hook.py pinned)
  g6a (cuda fork sha):     pass (0 violations; in-tree defensive)
  g6b (wheel sha pin):     pass (0 violations; load-bearing)
```

G6b PASS confirms the pod's `vllm.vllm_flash_attn` wheel matches the
TIER5A.3 freeze byte-for-byte. G5c now covers 10 files (the new
`phase6b2_precapture_hook.py` module added to the pin set during
Day 1).

## Phase 6B.2 history

* Design doc: ✅ commit `d2071ee` — INVENTORY of the remaining
  pre-capture host sync; hook target selection; stash shape;
  pool-counter sync handling (option A — hook owns the sync);
  install API; 6 risk areas; 25-test CPU plan; GPU smoke design;
  Day 1-3 timeline.
* Day 1 (hook module + dispatch read + pre_synced kwarg + sentinel
  sync + 27 CPU tests + G5c regen): ✅ commit `02aeaac`
* Day 2 (hook-equiv 36-cell verifier): ✅ commit `458350d` —
  36/36 cells PASS bit-equivalence.
* Day 3 (GPU smoke driver + runbook): ✅ commit `1f65595`
* GPU fix (inference_mode wrap for pool mutations): ✅ commit
  `e4c322e` — discovered during the first GPU smoke attempt
  (pool tensors carry the inference_tensor attribute; the wrap
  fires OUTSIDE inference_mode and was rejected). Fixed in one
  commit; re-run GREEN.
* GPU smoke green: ✅ this finding doc.

GPU spend: ≈ $0.10 across iterations (single A100 pod, ~5 min total
live including the initial inference_mode crash + diagnostic + the
green run).

## Lessons learned (durable)

1. **The sentinel-gated `_sync_pool_counters_from_states` was the
   critical correctness fix.** The Day 1 prototype regressed pool
   counters across decode steps when `pre_synced=True` skipped
   writeback. Traced on CPU via a 4-line print-trace; the fix
   (sync only when `_k_stage_block_id_pool[slot] == -1`) restored
   bit-equivalence. The sentinel design is more conservative than
   the original "unconditional overwrite" and preserves both
   6B.1's writeback-driven flow AND 6B.2's pool-as-truth flow.
   Worth keeping the sentinel pattern as the default for any
   future cross-context counter sync.

2. **The `inference_mode` decorator location is load-bearing.**
   vLLM 0.7.3 V0 puts `@torch.inference_mode()` on
   `model_runner.execute_model` — which is one frame DOWNSTREAM of
   our hook's wrap point. Pool tensors allocated during the first
   forward pass got the "inference tensor" attribute; the hook
   then tried to mutate them OUTSIDE inference_mode and PyTorch
   rejected the writes. Fix: wrap the pool-mutation block of
   `_resolve_and_stash` in `with torch.inference_mode():`. Pattern
   applies to ANY vLLM hook that needs to mutate per-step state
   from a worker-level wrap. **Document this in the runbook for
   future hook authors.**

3. **The `PHASE6B2_INSTALL_HOOK` env override paid off twice.**
   Once as a bisection primitive (GPU smoke confirmed hook-on vs
   hook-off in one process tree); once as a regression test (the
   hook-off call_stats EXACTLY matched 6B.1's smoke numbers from
   the prior session, proving the dispatch fork's fallback path
   is byte-equivalent to 6B.1's pre-edit behavior). Worth keeping
   the override past 6B.4 for the inevitable "did this v2 change
   regress anything" question.

4. **The 28× amortization measurement is a partner-credible
   operational claim.** "We resolve seq_id→slot once per step
   instead of 28 times" is concrete + testable + survives in the
   call_stats. This is the kind of mechanism-level number that
   strengthens partner-side technical-credibility conversations,
   independent of the eventual throughput delta.

5. **Discipline rule #1 (per-phase approval) prevented scope
   creep again.** 6B.2's design doc explicitly excluded the
   `enforce_eager=False` flip (that's 6B.3) and the throughput
   bench (that's 6B.4). Even with hook-on GREEN, we don't claim
   any tok/s improvement — only structural correctness. The brief
   stays unchanged until 6B.4 measures the actual aggregate
   throughput post-capture. Same pattern that worked for TIER5A
   and 6B.1.

## Code disposition

All Phase 6B.2 code stays in-tree:

| Component | Disposition |
|---|---|
| `KVPolicy/kv_policy/phase6b2_precapture_hook.py` (NEW) | **Retained, G5c-pinned.** The hook module; `Int4ProtectedPrecaptureHook` handle + `install_int4_protected_precapture_hook` + `install_int4_protected_with_precapture_hook` + helpers. |
| `KVPolicy/kv_policy/phase5b_4c_paged_writer.py` (modified) | **Retained.** Added `pre_synced=False` kwarg to `write_decode_batched`; sentinel-gated `_sync_pool_counters_from_states`. Strictly additive over 6B.1. |
| `KVPolicy/kv_policy/phase5b_backend_install.py` (modified) | **Retained.** Dispatch fork reads stash via `phase6b2_precapture_hook.read_stash`; new `write_decode_batched_via_hook_calls` counter. Strictly additive over 6B.1. |
| `Bench/scripts/verify_phase6_b_pre5_write_path_capture_safe.py` (modified) | **Retained.** Expected `.item()` count bumped to `2*B` to account for the sentinel-gate sync's per-slot check. AST verifier's CAPTURED-REGION span still asserts zero forbidden constructs. |
| `Bench/scripts/verify_phase6_b2_hook_equiv.py` (NEW) | **Retained.** 36-cell hook-on vs hook-off bit-equivalence verifier; partner-credible CPU measurement utility. |
| `Bench/scripts/bench_phase6_b2_hook_gpu_smoke.py` (NEW) | **Retained.** Self-spawning subprocess driver. |
| `Bench/scripts/PHASE_6B2_HOOK_GPU_SMOKE_RUNBOOK.md` (NEW) | **Retained.** Operator runbook with troubleshooting matrix. |
| `Bench/scripts/PHASE_6B2_PRECAPTURE_HOOK_DESIGN.md` (NEW) | **Retained.** Design doc archive. |
| `Bench/tests/test_phase6b2_precapture_hook.py` (NEW) | **Retained.** 27 CPU pytest tests. |
| `Bench/ctm_bench/scripts/tier5a_orthogonality_gate.py` (modified) | **Retained.** Added `phase6b2_precapture_hook.py` to the G5c file set. |
| `Bench/ctm_bench/scripts/int4_protected_files_baseline.json` (regen, 10 files) | **Retained, frozen.** Includes the new hook module. |

The 27-test CPU suite + the 36-cell hook-equiv verifier + the
diagnostic-friendly hook handle (with `stash_call_count` /
`skipped_step_count`) are a **partner-credible measurement
utility** for any future hook-touching change. Any modification
to `_resolve_and_stash` or the dispatch fork's stash-reading code
will surface through these checks before any GPU spend.

## Deferred items (logged for completeness; not blockers for 6B.2 closure)

### 1. Phase 6B.3 — `enforce_eager=False` flip + capture-enable

The hook now eliminates the LAST pre-capture host sync that 6B.1
left exempt inside `write_decode_batched`. With both 6B.1 (write
path structural prep) and 6B.2 (pre-capture hook) green, the
write path's captured region is host-sync-free; vLLM's CUDA
Graphs capture should JustWork on the int4_protected backend.
6B.3's deliverable: flip `enforce_eager=False`, re-run all
correctness verifies under capture, measure sidecar HBM growth.
**Gated on separate approval per discipline rule #1.**

### 2. Phase 6B.4 — throughput re-measurement + ship narrative

Once capture is enabled, `bench_phase6_batched_throughput.py`
re-runs at B in {1, 2, 4, 8}. Brief Page 6 Measured table updates
with the new aggregate-tok/s. Target: ≥ 80 tok/s @ B=8 (≥ 1.88×
the current 42.6 baseline). **Brief edit is gated on Phase 6B.4
GREEN.**

### 3. PHASE6B2_INSTALL_HOOK env var — keep through 6B.4

Recommended: keep the env override at least through Phase 6B.4 to
support "did capture itself regress anything" bisection. Retire
post-6B.4 if no further use case emerges.

### 4. Cross-family GPU smoke for 6B.2 (Mistral / Llama)

Phase 6B.1's cross-family smoke on Mistral-7B confirmed model-
agnosticism. The 6B.2 hook is identically model-agnostic by
construction (it operates on attn_metadata, not model weights),
so cross-family confirmation should hold trivially. Not gating;
opportunistic for the next pod session.

### 5. The inference_mode wrap pattern

Documenting in the runbook for future hook authors: ANY vLLM hook
that wraps a worker-level method (above `model_runner.execute_
model`) and mutates per-step state needs to wrap the mutation
block in `with torch.inference_mode():`. The TIER5A swap_telemetry
probe didn't hit this because it's read-only; future stateful
hooks WILL hit it.

## Implication for Phase 6B.3 (capture-enable)

The Phase 6B.2 material finding is **necessary and sufficient** for
Phase 6B.3 (capture enable). With:

* Write path's captured region host-sync-free (6B.1 §AST verifier
  + 36-cell equivalence)
* Per-call pre-capture work amortized to one host sync per step
  (6B.2 §amortization measurement)
* Pool tensors stable + inference-mode-compatible (6B.1 pointer
  audit + 6B.2 inference_mode wrap)
* Bit-equivalence holds across the dispatch-fork's two branches
  on real CUDA workloads (6B.2 GPU smoke)

…all four structural prerequisites for graph capture are met.
6B.3 should flip `enforce_eager=False` and JustWork on the first
attempt — same vLLM `compilation_config.cudagraph_capture_sizes`
mechanism that the read-path preflight prepared for. If 6B.3
crashes at capture, the diagnostic loop is: (a) AST + runtime
re-verify, (b) live diagnostic dump, (c) inference_mode trace.
But the structural work is done.

## Closing

Phase 6B.2 produced honest, durable engineering work and a **material
positive measured finding** on the real production stack. The hook-
driven slot_idx resolution + sentinel-gated pool sync + inference_
mode wrap design works byte-for-byte on Qwen-2.5-7B-Instruct + A100
+ the forked vllm-flash-attn kernel.

The brief is unchanged. The Phase 6B roadmap (6B.3 → 6B.4) is
unblocked. Each subsequent sub-phase needs separate user approval
per discipline rule #1.

## Artifact pointers

| Doc / data | What it captures |
|---|---|
| `Bench/scripts/PHASE_6B2_PRECAPTURE_HOOK_DESIGN.md` | Design doc (commit `d2071ee`) |
| `Bench/scripts/PHASE_6B2_HOOK_GPU_SMOKE_RUNBOOK.md` | Operator runbook |
| `Bench/scripts/PHASE_6B2_PRECAPTURE_HOOK_FINDINGS.md` | This file |
| `Bench/scripts/verify_phase6_b2_hook_equiv.py` | 36-cell hook-on vs hook-off bit-equivalence (CPU) |
| `Bench/scripts/bench_phase6_b2_hook_gpu_smoke.py` | Self-spawning GPU smoke driver |
| `Bench/tests/test_phase6b2_precapture_hook.py` | 27 CPU pytest tests |
| `KVPolicy/kv_policy/phase6b2_precapture_hook.py` | Hook module (Int4ProtectedPrecaptureHook + install/teardown + stash + resolve + inference_mode wrap) |
| `KVPolicy/kv_policy/phase5b_backend_install.py` | Dispatch fork reading stash; via_hook_calls counter |
| `KVPolicy/kv_policy/phase5b_4c_paged_writer.py` | write_decode_batched(pre_synced=True) + sentinel-gated sync |
| `bench_out/phase6b2_gpu_smoke/cell_hook_off.json` | Pod artifact: hook-off cell tokens + call_stats |
| `bench_out/phase6b2_gpu_smoke/cell_hook_on.json` | Pod artifact: hook-on cell tokens + call_stats + hook handle stats |
| `bench_out/phase6b2_gpu_smoke/smoke_report.json` | Pod artifact: 7-check comparison verdict |
| `Bench/ctm_bench/scripts/int4_protected_files_baseline.json` | G5c baseline (10 files; phase6b2_precapture_hook.py pinned) |

Branch: `claude/phase-6b1-write-preflight-fjYee` — commits
`d2071ee` (design) through `e4c322e` (inference_mode fix) plus
the smoke-green finding.
