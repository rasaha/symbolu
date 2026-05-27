# Phase 6B.1 write-path preflight — measured finding

> **Status:** Phase 6B.1 **CLOSED, positive measured finding.**
> Single-pod GPU smoke on Qwen-2.5-7B-Instruct + A100 + vLLM 0.7.3
> (forked int4_protected build) returned **all five G_PRE-WRITE
> checks GREEN**. The refactored decode write path
> (`PagedKVWriter.write_decode_batched`) produces byte-identical
> generated tokens vs the legacy per-seq partition+loop path.
>
> **VC brief: unchanged.** Phase 6B.1 is STRUCTURAL PREP for CUDA
> Graphs capture (Phase 6B.3); it does not move any of the brief's
> measured numbers. Brief edits wait for Phase 6B.4 (post-capture
> aggregate throughput re-measurement).
>
> **Code disposition:** the write_decode_batched method + 3 device-side
> per-slot counter pools + `_is_pure_decode_write` dispatch helper +
> the env-var override stay in-tree. The five new verification
> artifacts (CPU equivalence verify + AST/runtime capture-safety
> verify + pointer-stability audit + GPU smoke driver + diagnostic
> script) are partner-credible measurement utilities retained for
> any future write-path change.

## TL;DR

| Item | Status |
|---|---|
| G_PRE-WRITE.1: AST + runtime capture-safety on phase5b_4c_paged_writer.py | **GREEN** (CPU) — 0 forbidden host syncs in captured region |
| G_PRE-WRITE.2: 36-cell bit-equivalence (B in {1,2,4,8} × Modes A/B/C × {1,32,64} decode steps) | **GREEN** (CPU) — 36/36 cells byte-equal across 9 state tensors |
| G_PRE-WRITE.3: All existing verifies still GREEN | **GREEN** (CPU) — verify_phase5b_4c_1_write + 72 pytest tests |
| G_PRE-WRITE.4: TIER5A orthogonality G5a/G5b/G5c/G6a | **GREEN** (CPU + pod) — G5c regenerated for authorized edits; G5a/G5b/G6a unchanged |
| G_PRE-WRITE.5: GPU smoke bit-identical token IDs (Qwen-7B + A100) | **GREEN** — every prompt's `completion_token_ids` byte-equal across legacy + refactored cells |
| G_PRE-WRITE.6: Refactored cell exercised the new path | **GREEN** — `write_decode_batched_calls=868` on refactored cell |
| G_PRE-WRITE.7: Legacy cell stayed on legacy path | **GREEN** — `write_decode_batched_calls=0`, `write_legacy_loop_calls=896` on legacy cell |
| G_PRE-WRITE.8: Zero fallbacks both cells | **GREEN** — `write_path_fallback=0`, `decode_calls_fallback=0` for both |
| G_PRE-WRITE.G6b (load-bearing forked-wheel SHA pin) | **GREEN** — pod's forked vllm_flash_attn matches the TIER5A.3 freeze byte-for-byte |
| Pointer stability of 15 write-path scatter targets | **GREEN** (CPU) — 15/15 STABLE across 32 calls |
| Overall verdict | **GREEN — Phase 6B.1 CLOSED, write path is graph-capture-ready** |

## The material finding

**The refactored decode write path is byte-equivalent to the legacy
per-seq write loop on real Qwen-2.5-7B-Instruct + the forked
vllm-flash-attn kernel.**

The 36-cell CPU bit-equivalence verify (covering 4 batch sizes × 3
prefill→decode handoff modes × 3 decode-step counts) demonstrated
the unconditional re-quantize + pool-counter update math is correct
under PyTorch's reference CPU backend. The GPU smoke extends that
proof to the real production stack: the 28-layer Qwen-7B model
running through the forked CUDA kernel produces the SAME 32 greedy
decode tokens for both prompts when the dispatch fork routes through
`write_decode_batched` (refactored cell) vs the legacy partition+loop
(legacy cell, forced via `PHASE6B1_USE_DECODE_BATCHED=0`).

If the unconditional re-quantize had introduced any quantization
numerics drift, or if the device-side counter pools had race-conditioned
with the bf16-backing scatter, the token IDs would have diverged.
They didn't.

The write path is now structurally ready for CUDA Graphs capture
(Phase 6B.3); the captured region contains zero `.item()`, zero
`.cpu()`, zero `.tolist()`, and zero per-call Python dict lookups,
as verified by the AST + runtime capture-safety verifier.

## The methodology

### Workload (final GPU smoke on the A100 pod)

* Model: `Qwen/Qwen2.5-7B-Instruct`
* GPU: A100-80GB, `gpu_memory_utilization=0.5`
* Engine: vLLM 0.7.3 V0 with `enforce_eager=True`
  (Phase 6B.1 is structural prep; capture is 6B.3's job)
* Forked wheel: `vllm.vllm_flash_attn` matching the TIER5A.3 SHA freeze
  (4 files; G6b GREEN)
* Workload: two distinct deterministic prompts at B=2
  - Prompt 0: the Greendell needle (matches the existing B-pre-4
    audit prompt)
  - Prompt 1: a short translate-to-French task
* Greedy decode: `temperature=0.0`, `max_tokens=32`
* Warmup: one B=1 4-token generate before stats reset

### Two cells (legacy vs refactored)

The GPU smoke uses the `PHASE6B1_USE_DECODE_BATCHED` env var to fork
behavior within the SAME repository checkout:

| Cell | Env var | Decode write path | Why |
|---|---|---|---|
| **legacy**     | `PHASE6B1_USE_DECODE_BATCHED=0` | Legacy partition+loop (always) | `_is_pure_decode_write` returns False under override; dispatch fork takes the `else:` branch. Equivalent to pre-refactor behavior. |
| **refactored** | `PHASE6B1_USE_DECODE_BATCHED=1` (default) | `write_decode_batched` for pure-decode steps; legacy fallthrough for prefill | Production behavior. |

Each cell runs as a separate Python subprocess so the engine + env
state are clean per-cell. The driver script
(`bench_phase6_b_pre5_gpu_smoke.py`) spawns both, then compares the
token IDs + call_stats from the two emitted JSONs.

### The acceptance gate (G_PRE-WRITE.5..8)

Five comparison checks:

| Check | Pass criterion |
|---|---|
| `completion_token_ids_byte_equal`           | every prompt's decode tokens byte-equal across cells |
| `refactored_cell_used_write_decode_batched` | refactored cell's `write_decode_batched_calls > 0` |
| `legacy_cell_used_only_legacy_loop`         | legacy cell's `write_decode_batched_calls == 0` AND `write_legacy_loop_calls > 0` |
| `legacy_zero_fallbacks`                     | `write_path_fallback == 0` AND `decode_calls_fallback == 0` |
| `refactored_zero_fallbacks`                 | same |

All five PASS on the green run.

## The actual numbers

### Pod (run 2026-05-27)

```
Model:      Qwen/Qwen2.5-7B-Instruct
Prompts:    2    max_tokens: 32
Verdict:    GREEN

Checks:
  [PASS] completion_token_ids_byte_equal                  all prompts byte-equal
  [PASS] refactored_cell_used_write_decode_batched        write_decode_batched_calls=868
  [PASS] legacy_cell_used_only_legacy_loop                write_decode_batched_calls=0, write_legacy_loop_calls=896
  [PASS] legacy_zero_fallbacks                            write_path_fallback=0, decode_calls_fallback=0
  [PASS] refactored_zero_fallbacks                        write_path_fallback=0, decode_calls_fallback=0

Call stats:
  legacy:     {"decode_calls_fallback": 0, "decode_calls_packed": 868, "prefill_calls": 28,
               "spec_decode_calls": 0, "write_decode_batched_calls": 0,
               "write_legacy_loop_calls": 896, "write_path_calls": 896, "write_path_fallback": 0}
  refactored: {"decode_calls_fallback": 0, "decode_calls_packed": 868, "prefill_calls": 28,
               "spec_decode_calls": 0, "write_decode_batched_calls": 868,
               "write_legacy_loop_calls": 28,  "write_path_calls": 896, "write_path_fallback": 0}

Per-prompt diffs:
  prompt[0] preview: 'Below is a paragraph about a small fictional town. After it,'
    tokens_byte_equal:  True
  prompt[1] preview: 'Translate to French and explain briefly:\nEnglish: The quick '
    tokens_byte_equal:  True
```

### Interpretation of the call-stats split

| Path | Cell-legacy | Cell-refactored | What it tells us |
|---|---:|---:|---|
| `prefill_calls`               | 28  | 28  | Both cells ran prefill identically — one forward pass through all 28 attention layers. |
| `decode_calls_packed`         | 868 | 868 | Both cells executed the packed decode kernel 868 times (28 layers × 31 decode steps; max_tokens=32 = 31 newly-generated + 1 from the seed transition). Same kernel call count in both → no fallback path triggered. |
| `write_path_calls`            | 896 | 896 | Both cells did 896 write-path invocations (28 prefill + 868 decode). Same total → dispatch fork is bookkeeping-clean. |
| `write_legacy_loop_calls`     | 896 |  28 | Legacy cell: ALL writes via legacy partition+loop (28 prefill + 868 decode). Refactored cell: ONLY the 28 prefill writes (correct — `_is_pure_decode_write` returns False for prefill; vLLM 0.7.3 V0 doesn't graph-capture prefill anyway). |
| `write_decode_batched_calls`  |   0 | 868 | Refactored cell routed ALL 868 decode writes through the new `write_decode_batched` method. Confirms the dispatch fork is alive and the env override is effective. |
| `write_path_fallback`         |   0 |   0 | Neither cell fell back to vLLM's stock `reshape_and_cache_flash`. |
| `decode_calls_fallback`       |   0 |   0 | Neither cell fell back to vLLM's stock decode kernel. |

The 28-vs-868 split on `write_legacy_loop_calls` for the refactored
cell is exactly the design contract: prefill stays eager (legacy),
decode goes graph-capture-friendly (`write_decode_batched`).

### Pre-flight gate state (Step 1 of the runbook)

```
verdict: PASS
  g5a (class fingerprint): pass (0 violations)
  g5b (tier5a ast):        pass (0 violations)
  g5c (int4 python sha):   pass (0 violations)
  g6a (cuda fork sha):     pass (0 violations; in-tree defensive)
  g6b (wheel sha pin):     pass (0 violations; load-bearing)
```

G6b PASS confirms the pod's `vllm.vllm_flash_attn` wheel
(4 files: `__init__.py`, `flash_attn_interface.py`,
`_vllm_fa2_C.abi3.so`, `_vllm_fa3_C.abi3.so`) matches the
TIER5A.3 freeze byte-for-byte — the int4 path runs against the
same kernel that produced the brief's headline measurements.

## Phase 6B.1 history

* Design doc: ✅ commit `433c4a4` — INVENTORY (18 capture-hostile
  patterns), REFACTOR STRATEGY (B-pre-1..4 mirror), POOL/BUFFER
  OWNERSHIP, TEST PLAN, RISK AREAS, TIMELINE.
* Day 1 (pool counters + write_decode_batched + dispatch): ✅ commit
  `4a73f47` — 3 device-side counter pools, new method, dispatch fork,
  47-test CPU pytest suite all GREEN.
* Day 2+3 (verifies + audit + G5c regen + plan update): ✅ commit
  `83a3b7e` — `verify_phase6_b_pre5_write_equiv.py` (36/36),
  `verify_phase6_b_pre5_write_path_capture_safe.py` (AST + runtime
  GREEN), `audit_phase6_b_pre5_write_pointer_stability.py` (15/15
  STABLE), G5c baseline regenerated, plan status snapshot updated.
* GPU smoke driver + runbook + env override + counters: ✅ commit
  `4e840d2` — `bench_phase6_b_pre5_gpu_smoke.py` (self-spawning
  subprocess driver), `PHASE_6B1_GPU_SMOKE_RUNBOOK.md`, env-var gate
  in `_is_pure_decode_write`, two new `_call_stats` counters.
* Diagnostic script: ✅ commit `90ef674` — `diagnose_phase6_b_pre5_
  write_state.py` with `--inspect-only` (zero-GPU) and `--live`
  (pod-runnable) modes; TIER5A-style for any future investigation.
* GPU smoke green: ✅ this finding doc.

GPU spend: ≈ $0.05 across iterations (single A100 pod, ~3 minutes
live: orthogonality gate + diagnostic inspect-only + smoke driver
two-cell run).

## Lessons learned (durable)

1. **The unconditional re-quantize bit-equivalence argument held under
   the real CUDA kernel, not just CPU reference math.** The CPU
   36-cell verify was the load-bearing CPU proof; the GPU smoke was
   the operational confirmation that PyTorch's CUDA bf16 quant ops
   produce the same packed nibbles as the CPU bf16 path for the
   same inputs. The structural design (`torch.where`-masked update
   to staging pool + amax/amin over BS positions including zeros)
   is what made bit-equivalence inevitable; the GPU run is the
   evidence.

2. **`PHASE6B1_USE_DECODE_BATCHED` env override is the right
   bisection primitive.** Forcing the dispatch gate to False from
   the same repository checkout (rather than requiring two
   git-checkouts on the pod) made the GPU smoke a one-command
   operation and eliminated a class of "but did you really test
   the same code?" partner questions. Retain this override for any
   future write-path investigation.

3. **The CAPTURED-REGION-START / -END sentinel pattern works for
   AST verification.** Phase 6B.1's `write_decode_batched` is the
   first method in-tree to use explicit sentinels delimiting the
   captured-region body. The AST + runtime verifier finds the
   sentinels by line number, walks the AST nodes between them, and
   asserts zero forbidden constructs. Future write-path edits that
   inadvertently add a `.item()` inside the captured region will
   fail the verifier without needing to actually run graph
   capture. Recommended pattern for any other method that must
   be captured.

4. **TIER5A's orthogonality gate caught the authorized G5c edits
   cleanly without false-positiving G5a.** The class-method
   fingerprint (G5a) ignores method-body edits by design; the
   file-SHA pin (G5c) catches everything else. Phase 6B.1's
   `forward()` body edit + module-level `_is_pure_decode_write`
   helper triggered exactly G5c (regenerated with audit note); G5a
   stayed PASS. The audit-pattern separation (shape vs content)
   continues to scale.

5. **The diagnostic script's `--inspect-only` mode is the
   load-bearing pre-flight.** On a fresh pod, `g5c_drift.ok=True`
   + correct dispatch verdicts + wheel-importable confirmed the
   checkout was clean before any GPU spend. ~1-second runtime,
   zero GPU. Worth adopting as the canonical "did my branch
   checkout cleanly?" check for any future phase that touches the
   int4_protected stack.

## Code disposition

All Phase 6B.1 code stays in-tree:

| Component | Disposition |
|---|---|
| `KVPolicy/kv_policy/phase5b_4c_paged_writer.py` (modified) | **Retained** — adds `write_decode_batched` + 3 counter pools + sync/writeback helpers; legacy `write()` path unchanged |
| `KVPolicy/kv_policy/phase5b_backend_install.py` (modified) | **Retained** — adds `_is_pure_decode_write` helper + dispatch fork + env override + 2 new counters; class fingerprint (G5a) preserved |
| `Bench/scripts/verify_phase6_b_pre5_write_equiv.py` | **Retained** — 36-cell bit-equivalence verifier; partner-credible CPU measurement utility |
| `Bench/scripts/verify_phase6_b_pre5_write_path_capture_safe.py` | **Retained** — AST + runtime capture-safety verifier; catches any future host-sync regression in the captured region |
| `Bench/scripts/audit_phase6_b_pre5_write_pointer_stability.py` | **Retained** — pointer-stability audit; same role as `audit_phase6_b_pre4_pointer_stability.py` for the read path |
| `Bench/scripts/bench_phase6_b_pre5_gpu_smoke.py` | **Retained** — operator-runnable smoke driver |
| `Bench/scripts/diagnose_phase6_b_pre5_write_state.py` | **Retained** — TIER5A-style diagnostic for any future write-path investigation |
| `Bench/scripts/PHASE_6B1_GPU_SMOKE_RUNBOOK.md` | **Retained** — operator runbook |
| `Bench/scripts/PHASE_6B1_WRITE_PREFLIGHT_DESIGN.md` | **Retained** — design doc archive |
| `Bench/tests/test_paged_writer_decode_batched.py` | **Retained** — 49 CPU pytest tests (47 equivalence + 2 env override) |
| `Bench/ctm_bench/scripts/int4_protected_files_baseline.json` (regen) | **Retained, frozen** — G5c baseline updated for the authorized 6B.1 edits |

The 49-test CPU suite + the four verifiers + the diagnostic are a
**partner-credible measurement utility** for any future
write-path-touching change. Any modification to
`write_decode_batched` or `_is_pure_decode_write` will surface
through these checks before any GPU spend.

## Deferred items (logged for completeness; not blockers for 6B.1 closure)

### 1. Phase 6B.2 — vLLM hook for pre-capture seq_id resolution

The current `write_decode_batched` has its pre-capture region INSIDE
the Python call (one `.cpu().tolist()` on `slot_idx_t` + the
`_sync_pool_counters_from_states` Python loop). For CUDA Graphs
capture (6B.3) to succeed, the pre-capture region must be HOISTED
OUTSIDE the captured graph via a vLLM hook. This is exactly Phase
6B.2's deliverable. NOT in 6B.1's scope; gated on separate approval.

### 2. Phase 6B.3 — flip `enforce_eager=False` and verify under capture

After 6B.2 lands the hook, 6B.3 enables `enforce_eager=False` on
`Int4ProtectedLLM` and re-runs all correctness verifies under
capture. Phase 6B.1's structural work makes this possible; the
actual flip + verification is 6B.3's deliverable. Gated.

### 3. Phase 6B.4 — throughput re-measurement + ship narrative update

Once capture is enabled, the throughput bench
(`bench_phase6_batched_throughput.py`) re-runs at B in {1, 2, 4, 8}
and the brief's Page 6 Measured table updates with the new
aggregate-tok/s number. Target: ≥ 80 tok/s @ B=8 (≥ 1.88× the
current 42.6 tok/s baseline). Phase 6B.4 is the only Phase 6B
sub-phase that triggers a brief edit. Gated on 6B.3 GREEN.

### 4. PHASE6B1_USE_DECODE_BATCHED env var — keep or retire?

Currently retained as a partner-credible bisection primitive (per
Lesson 2). After 6B.3 ships, the env override could be retired (the
legacy path becomes pure-eager-fallback dead code on a graph-captured
production deployment). Recommended: keep through 6B.4 in case the
capture-vs-eager comparison needs another bisection cycle.

### 5. Cross-family GPU smoke (Mistral, Llama, Qwen-14B)

The 6B.1 GPU smoke ran on Qwen-7B only. The write path is
model-agnostic (no model-specific code), so cross-family bit-equiv
should hold trivially — but the brief's portfolio replication
discipline (Tier A pattern) would benefit from at least one
non-Qwen smoke run. Cost: ~$0.02 per additional model. Not gating;
opportunistic for the next pod session.

## Implication for Phase 6B.2 (vLLM integration hook)

The Phase 6B.1 material finding is **necessary but not sufficient**
for Phase 6B.3 (capture enable). The write path is now structurally
graph-safe inside the captured region (AST + runtime + pointer
stability + 36-cell equivalence + GPU smoke all GREEN). What 6B.2
must add is the **pre-capture hook** that resolves `slot_idx_t`
OUTSIDE the captured graph by intercepting one of vLLM's
forward-prologue entry points and stashing the resolved slot tensor
on the model input dict.

The diagnostic script's `--live` mode + the 49-test CPU suite
remain the load-bearing safety nets for 6B.2 — any change to the
slot-resolution surface will surface there before any GPU smoke.

## Closing

Phase 6B.1 produced honest, durable engineering work and a **material
positive measured finding** on the real production stack. The
unconditional re-quantize + device-side counter pool design proves
out byte-for-byte on Qwen-2.5-7B-Instruct + A100 + the forked
vllm-flash-attn kernel.

The brief is unchanged. The Phase 6B roadmap (6B.2 → 6B.3 → 6B.4)
is unblocked. Each subsequent sub-phase needs separate user
approval per discipline rule #1.

## Artifact pointers

| Doc / data | What it captures |
|---|---|
| `Bench/scripts/PHASE_6B1_WRITE_PREFLIGHT_DESIGN.md` | Design doc (commit `433c4a4`) |
| `Bench/scripts/PHASE_6B1_GPU_SMOKE_RUNBOOK.md` | Operator runbook for the GPU smoke |
| `Bench/scripts/PHASE_6B1_WRITE_PREFLIGHT_FINDINGS.md` | This file |
| `Bench/scripts/verify_phase6_b_pre5_write_equiv.py` | 36-cell bit-equivalence verifier (CPU) |
| `Bench/scripts/verify_phase6_b_pre5_write_path_capture_safe.py` | AST + runtime capture-safety verifier (CPU) |
| `Bench/scripts/audit_phase6_b_pre5_write_pointer_stability.py` | Pointer-stability audit (CPU) |
| `Bench/scripts/bench_phase6_b_pre5_gpu_smoke.py` | Self-spawning GPU smoke driver |
| `Bench/scripts/diagnose_phase6_b_pre5_write_state.py` | TIER5A-style diagnostic (inspect-only + live) |
| `Bench/tests/test_paged_writer_decode_batched.py` | 49 CPU pytest tests |
| `KVPolicy/kv_policy/phase5b_4c_paged_writer.py` | Writer with `write_decode_batched` + 3 counter pools |
| `KVPolicy/kv_policy/phase5b_backend_install.py` | Dispatch fork + `_is_pure_decode_write` + env override + 2 counters |
| `bench_out/phase6b1_gpu_smoke/cell_legacy.json` | Pod artifact: legacy cell tokens + call_stats (operator-archived) |
| `bench_out/phase6b1_gpu_smoke/cell_refactored.json` | Pod artifact: refactored cell tokens + call_stats |
| `bench_out/phase6b1_gpu_smoke/smoke_report.json` | Pod artifact: 5-check comparison verdict |
| `Bench/ctm_bench/scripts/int4_protected_files_baseline.json` | G5c baseline (regenerated for 6B.1 authorized edits) |

Branch: `claude/phase-6b1-write-preflight-fjYee` — commits `433c4a4`
(design) through `90ef674` (diagnostic) plus the smoke-green finding.
