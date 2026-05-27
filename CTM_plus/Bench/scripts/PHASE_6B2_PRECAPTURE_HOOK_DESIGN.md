# Phase 6B.2 — vLLM pre-capture seq_id resolution hook (design doc)

> **Status:** Design doc only. CPU-first per discipline rule #4. No
> code lands without explicit user approval of this design.
>
> **Scope:** ONLY Phase 6B.2 of `PHASE_6B_CUDA_GRAPHS_PLAN.md`.
> Phases 6B.3 / 6B.4 stay gated on separate approvals each.
>
> **Builds on:** Phase 6B.1 CLOSED-positive (commits `433c4a4`..`f6804fa`).
> The decode write path is structurally graph-safe; the one remaining
> host sync inside `write_decode_batched`'s pre-capture region is the
> `slot_idx_t.cpu().tolist()` + `_sync_pool_counters_from_states`
> chain. Phase 6B.2 hoists this OUTSIDE the captured graph entirely.
>
> **Acceptance gate:** G_HOOK (see "Acceptance criteria" below).

---

## 1. What changed after 6B.1 — recap

`write_decode_batched(key, value, kv_cache, slot_mapping, slot_idx_t)`
takes `slot_idx_t` as an input parameter. In 6B.1's dispatch fork (in
`Int4ProtectedAttentionImpl.forward()` line 759-769), `slot_idx_t` is
resolved INSIDE the impl's forward method via:

```python
seq_ids = dec_meta.block_tables[:, 0].cpu().tolist()   # host sync
for sid in seq_ids:
    writer.ensure_seq_state(sid, kv_cache.device)       # dict lookup
slot_idx_list = writer.slot_indices_for(seq_ids)        # dict lookup
slot_idx_t = torch.tensor(slot_idx_list, ...).to(kv_cache.device)
writer.write_decode_batched(..., slot_idx_t=slot_idx_t)
```

The `.cpu().tolist()` + dict lookups + `torch.tensor(...)` chain runs
ON EVERY forward() call, ON EVERY attention layer. Inside graph
capture (`enforce_eager=False`), the captured graph would attempt to
record those ops — but `.cpu().tolist()` is a host sync that capture
explicitly forbids. The B-1 first attempt crashed exactly here on the
read path side; the write path inherits the same failure mode.

**Phase 6B.2's job:** install a hook BEFORE the captured forward
starts that resolves `slot_idx_t` once per step (not per layer), stashes
it on `attn_metadata`, and lets the per-layer dispatch fork read it
from there instead of self-resolving. Captured region then sees only
device-side ops.

## 2. Hook target — which vLLM 0.7.3 V0 entry point

Three candidates, picked by stability + access surface:

| Entry point | Pro | Con | Verdict |
|---|---|---|---|
| `ModelRunner.execute_model(model_input, kv_caches, ...)` | Runs once per step; receives the FULL prepared `model_input` (which carries `attn_metadata`). Mutating `attn_metadata` here propagates to every layer's `forward`. Stable across vLLM 0.7.x. | The captured region starts INSIDE this method (`model_executable(...)` call at line ~1724). Hook must run BEFORE that line. The cleanest way: wrap `execute_model` itself and resolve before delegating. | **PRIMARY TARGET** |
| `ModelRunner.prepare_model_input(seq_group_metadata_list, ...)` | Runs once per step; outputs `model_input` with `attn_metadata`. Hook could mutate the output dict. | Returns model_input; we'd need to add a post-processing step. Slightly more invasive (the returned dict's shape is internal vLLM contract). | **FALLBACK** if `execute_model` proves problematic |
| `Worker.execute_model(execute_model_req)` | One level higher; receives `ExecuteModelRequest` not `ModelInputForGPU`. | Wraps too much (scheduler RPC, distributed coordination). Mutating ExecuteModelRequest is the wrong layer. | **REJECTED** |

**Primary plan: wrap `ModelRunner.execute_model`.** The wrap intercepts
the `model_input` argument, walks it to `model_input.attn_metadata`,
and stashes the resolved slot_idx_t there before delegating to the
original method.

```python
def _wrapped_execute_model(model_input, kv_caches, *args, **kw):
    attn_metadata = getattr(model_input, "attn_metadata", None)
    if _is_pure_decode_step(attn_metadata):
        _stash_pre_capture_slot_idx(attn_metadata, writers, device)
    return original_execute_model(model_input, kv_caches, *args, **kw)
```

Bound-method wrap via `setattr(model_runner, "execute_model", wrapped)`
— same pattern as `swap_telemetry.install_swap_in_latency_probe` (a
TIER5A precedent already in-tree).

## 3. What gets stashed on `attn_metadata`

A single attribute. Single source of truth:

```python
attn_metadata._int4_protected_precapture = {
    "slot_idx_t":     <torch.long device tensor, shape (B,)>,
    "seq_ids":        <list[int], the seq_ids used to resolve>,
    "hook_version":   "6B.2_v1",
}
```

Naming: leading underscore to mark it private. The attribute name is
namespaced (`_int4_protected_*`) to avoid collisions with anything
vLLM may add later. The hook tags `hook_version` for forward
compatibility (a future 6B.x bump could detect stale stashes).

`attn_metadata` is a dataclass; setattr on it works (some attn
metadata implementations use `__slots__`, but vLLM 0.7.3 V0's
`FlashAttentionMetadata` is dataclass-based without slots — verified
by inspection). Defensive: wrap the setattr in try/except; on failure,
fall back to a thread-local module-level cache keyed by `id(attn_metadata)`.

## 4. The dispatch fork's modified contract

In `Int4ProtectedAttentionImpl.forward()`, the write block becomes:

```python
T_total = int(key.shape[0])
_pure_decode = _is_pure_decode_write(attn_metadata, T_total)
if _pure_decode:
    # 6B.2: prefer the hook-stashed slot_idx_t if present.
    stash = getattr(attn_metadata, "_int4_protected_precapture", None)
    if stash is not None and "slot_idx_t" in stash:
        slot_idx_t = stash["slot_idx_t"]
        # Pre-allocated SeqState ensured by the hook.
    else:
        # Fallback: self-resolve (6B.1 behavior). Keeps tests + non-
        # hook-installed environments working.
        dec_meta = attn_metadata.decode_metadata
        seq_ids = dec_meta.block_tables[:, 0].cpu().tolist()
        for sid in seq_ids:
            writer.ensure_seq_state(sid, kv_cache.device)
        slot_idx_list = writer.slot_indices_for(seq_ids)
        slot_idx_t = torch.tensor(slot_idx_list, dtype=torch.long,
                                  device=kv_cache.device)
    writer.write_decode_batched(...,  slot_idx_t=slot_idx_t)
    Int4ProtectedAttentionImpl._call_stats["write_decode_batched_calls"] += 1
else:
    # Legacy fallthrough unchanged.
    ...
```

**Critical property:** when the hook is NOT installed (CPU tests; pre-
hook deployments), the dispatch fork falls back to self-resolution.
This makes 6B.2 strictly additive — Phase 6B.1's behavior is
preserved when no hook is present.

The same stash also feeds the READ path (`_read_decode_packed_batched`
in the same file). Today's read path does its own
`torch.stack([cache_seqlens_orig.long(), block_table[:, 0].long()],
dim=0).cpu().tolist()` (line 388-390). Phase 6B.2 lets the read path
also prefer the stashed `slot_idx_t` for slot resolution — closing
the SAME pre-capture sync the write path closes. Net: zero host syncs
inside the captured region across both paths.

## 5. Pool-counter sync handling

Phase 6B.1's `write_decode_batched` opens with:

```python
slot_idx_list = slot_idx_t.cpu().tolist()    # CAPTURE-EXEMPT
self._sync_pool_counters_from_states(slot_idx_list)
```

This sync happens INSIDE `write_decode_batched`. For Phase 6B.2's
hook to truly eliminate ALL pre-capture host syncs from the captured
region, the sync must move BEFORE `execute_model` runs. Two options:

| Option | Where the sync runs | Pro | Con |
|---|---|---|---|
| **A (recommended).** Move the sync into the hook itself. The hook accepts the writers list (one per layer; same `_slot_map` keyed by seq_id), runs `_sync_pool_counters_from_states` for all writers once per step before delegating. | In the hook closure, BEFORE `original_execute_model`. | One sync covers all 28-32 layers in one Python pass. Truly captured-region-free. | The hook needs visibility into ALL writers. Resolved by walking `model.named_modules()` once at install time and caching writer references on the hook handle. |
| **B.** Keep the sync inside `write_decode_batched` but add a fast path that no-ops when the stashed slot_idx_t came from the hook (which means the counters were already synced). | In write_decode_batched, gated by a stash flag. | Less invasive to the hook. | The fast-path branch is data-dependent (sync vs no-op); could become a graph-capture issue. Option A is cleaner. |

**Recommendation: A.** The hook owns the per-step sync; `write_decode_batched`
drops its own sync when the stash is present, falls back to its own
sync when no stash. Same fallback pattern as §4.

## 6. Install / teardown API

Mirror `install_swap_in_latency_probe`'s shape:

```python
def install_int4_protected_precapture_hook(
    model_runner: Any,
    writers_by_layer: Dict[int, PagedKVWriter],
    *,
    enable: bool = True,
) -> Int4ProtectedPrecaptureHook:
    """Wrap model_runner.execute_model to stash a pre-resolved
    slot_idx_t on attn_metadata before the captured forward runs.

    Returns an Int4ProtectedPrecaptureHook handle with:
      .enabled               bool — False if no wrap target found
      .hook_target_name      str  — "execute_model" on success
      .install_time_writers  list[int] — layer indices the hook tracks
      .stash_call_count      int  — for verification (incremented per call)
      .teardown()            — LIFO revert, idempotent
    """
```

Discovery: `writers_by_layer` populated by walking `model.named_modules()`
post-`install_int4_protected_backend(model)`. Each
`Int4ProtectedAttentionImpl` carries a writer; the hook stores a list
of writer references.

LIFO teardown: restore the original `execute_model`, drop the writer
references, mark the handle torn-down.

**Convenience entry point** (analogous to TIER5A's full install):

```python
def install_int4_protected_with_precapture_hook(
    llm: Int4ProtectedLLM,
) -> Tuple[Int4ProtectedBackendManager, Int4ProtectedPrecaptureHook, Callable]:
    """One-call install: swap impls (6B.1's install) + install hook (6B.2).
    Returns (backend_manager, hook_handle, combined_teardown).
    """
```

This is the production API. Operators don't need to know about the
two-step install order; they call once and get a teardown that does
both in LIFO.

## 7. CPU test plan

Mirror `test_swap_telemetry.py` + `test_tier5a_composition_smoke.py`
patterns. No vLLM stack needed; use mock objects with the same
attribute shape vLLM emits.

### 7a. `test_precapture_hook_resolution.py` (~15 tests)

* Mock `attn_metadata` with `decode_metadata.block_tables` (the input
  to `slot_indices_for`). Mock writer with known `_slot_map`.
* Hook resolves seq_ids → slot_idx_t correctly across B in {1, 2, 4, 8}.
* Stashed slot_idx_t has the right shape, dtype, and values.
* `_sync_pool_counters_from_states` was called with the right slot_idx
  list (verified via a mock).
* Hook is a no-op for prefill-only steps (no decode_metadata).
* Hook is a no-op when `kv_cache_dtype` not int4_protected.
* Hook is a no-op when `_int4_protected_precapture` already set
  (idempotency / re-entry guard).

### 7b. `test_precapture_hook_install.py` (~10 tests)

* Mock `model_runner` exposes `execute_model` as a callable attribute.
* `install_int4_protected_precapture_hook` wraps it via setattr.
* Wrapped method delegates with correct arguments + return value.
* Teardown restores the original method object (identity check).
* Teardown is idempotent (second call no-ops).
* Install with `enable=False` returns inert handle.
* Install when `model_runner` lacks `execute_model` returns inert
  with a sensible `hook_target_name`.

### 7c. `test_paged_writer_decode_batched.py` additions (~5 tests)

Extend the existing 49-test suite:
* `write_decode_batched` correctly skips `_sync_pool_counters_from_states`
  when called with a stash-flag argument (or via the stash presence on
  a passed-in attn_metadata mock).
* Bit-equivalence vs the 36-cell baseline holds for both "hook-on"
  (stash present) and "hook-off" (stash absent) paths — they must
  produce the same kv_cache state.

### 7d. Integration with existing gates

| Gate | Expected impact |
|---|---|
| `verify_phase6_b_pre5_write_equiv.py` (36 cells) | UNCHANGED. Verifier calls `write_decode_batched` directly without a stash; goes through the fallback self-sync path. Still GREEN. |
| `verify_phase6_b_pre5_write_path_capture_safe.py` (AST + runtime) | EXTENDED. AST check now also walks `write_decode_batched`'s captured region in BOTH branches (stash-present + stash-absent). Runtime check confirms the stash-present path has ZERO host syncs from writer frames. |
| `audit_phase6_b_pre5_write_pointer_stability.py` (15/15 STABLE) | UNCHANGED — the new buffers (none) don't add scatter targets. |
| TIER5A orthogonality | G5a / G5b preserved (no class shape changes). G5c will regen for the authorized edits (new module + dispatch tweak). G6a / G6b unchanged. |

## 8. Anticipated GPU smoke shape

Mirror `bench_phase6_b_pre5_gpu_smoke.py`:

* Two cells, both with `Int4ProtectedLLM(...)`:
  - Cell **hook-off**: hook NOT installed; dispatch fork self-resolves
    (this IS Phase 6B.1's refactored behavior). Reference.
  - Cell **hook-on**: hook installed via
    `install_int4_protected_with_precapture_hook(llm)`.
    Each forward reads the stashed slot_idx_t.
* Identical workload (2 prompts, B=2, max_tokens=32, greedy).
* Compare: token IDs byte-identical; both cells `write_path_fallback=0`.
* New counter to verify: hook handle's `stash_call_count` matches
  `decode_calls_packed / num_layers` (i.e., one stash per decode step).

Budget: ~$0.05 GPU (same shape as 6B.1's smoke; just two more
subprocess runs).

## 9. Risk areas + mitigations

### R-1: vLLM 0.7.3 V0's `ModelRunner.execute_model` signature drift

**Concern:** vLLM 0.7.3 V0's exact `execute_model` signature could
differ from what we wrap. If we capture (model_input, kv_caches,
*args, **kw) but the real signature uses kwargs differently, the
delegation breaks silently.

**Mitigation:**
- Wrap closure uses `*args, **kwargs` passthrough verbatim (no
  positional repositioning); same pattern that worked for
  `install_swap_in_latency_probe`.
- Integration test: a CPU smoke that loads vLLM if available and
  asserts the wrap doesn't change the return value for a no-op
  step. (Optional; gated on vllm importable.)
- Fallback: if `execute_model` doesn't have an `attn_metadata`-bearing
  argument, the hook resolves to inert (returns
  `hook_target_name="model_input_shape_unknown"`) and the dispatch
  fork's self-resolve path runs. Same as 6B.1 — no regression.

### R-2: `attn_metadata` may not accept arbitrary setattr

**Concern:** Some attn metadata dataclasses define `__slots__` which
disallow new attributes.

**Mitigation:**
- Defensive code path: try `setattr(attn_metadata, "_int4_protected_precapture", stash)`;
  on AttributeError, fall back to a thread-local module-level dict
  keyed by `id(attn_metadata)`. The dispatch fork reads from the dict
  if the attribute is missing.
- Pin: regression test that exercises both branches (attr-accepting
  metadata vs slot-class metadata).

### R-3: Multi-step pipelines (chunked prefill, spec decode)

**Concern:** `num_scheduler_steps > 1` or `chunked_prefill_enabled`
splits one logical step into multiple `execute_model` calls. The hook
fires per call. If `decode_metadata` is sometimes absent on the
intra-step calls, the hook must no-op safely.

**Mitigation:**
- `_is_pure_decode_step` check inside the hook (same predicate as
  `_is_pure_decode_write` in 6B.1, factored into one module-level
  helper). When False, hook is a no-op; the dispatch fork's else
  branch (legacy partition+loop) runs.

### R-4: Hook installs BEFORE the writer pool is allocated

**Concern:** `PagedKVWriter._lazy_alloc` runs on first `write()`. If
the hook tries to call `_sync_pool_counters_from_states` before
`_lazy_alloc`, it crashes.

**Mitigation:**
- The hook only fires on decode steps; decode requires prefill to
  have run first; prefill triggers `_lazy_alloc` via the legacy
  write path. So by the time the hook ever stashes anything, all
  writers are allocated.
- Defensive: hook checks `writer._allocated` and no-ops the sync if
  False (deferring to the dispatch fork's fallback path).

### R-5: Hook's writer references go stale on engine reset

**Concern:** If the operator calls `llm.llm_engine.reset()` (or
similar), the model + writers may be re-instantiated. The hook's
captured writer list points at dead objects.

**Mitigation:**
- The hook handle's `teardown()` MUST be called on engine reset.
  The combined teardown closure from `install_int4_protected_with_precapture_hook`
  handles both backend swap restoration and hook teardown in LIFO.
- Documentation: runbook section on the install/reset lifecycle.

### R-6: Multi-instance LLM (rare; mostly applies to spec-decode or
draft models)

**Concern:** A single Python process with multiple `Int4ProtectedLLM`
instances would have multiple model_runners; the hook needs to attach
to each.

**Mitigation:**
- `install_int4_protected_precapture_hook` is per-model-runner; the
  convenience `install_int4_protected_with_precapture_hook(llm)` is
  per-llm. Operators with multi-LLM setups call once per llm. Same
  pattern as the backend install.

## 10. Files touched (concrete list)

| Path | Change type | G5c impact | G5a impact |
|---|---|---|---|
| `CTM_plus/KVPolicy/kv_policy/phase6b2_precapture_hook.py` (NEW) | New module: `Int4ProtectedPrecaptureHook` dataclass + `install_int4_protected_precapture_hook` + `install_int4_protected_with_precapture_hook` + helpers. | Will be added to G5c baseline if Pin'd. | n/a (no class fingerprint pin on this module) |
| `CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py` | Edit dispatch fork in `forward()` to prefer the stashed slot_idx_t. Add helper to read stash. Don't change class method list. | RED → regen | GREEN (method list unchanged) |
| `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py` | Add an optional `pre_synced=False` kwarg to `write_decode_batched`; when True, skips `_sync_pool_counters_from_states`. Same captured-region body otherwise. | RED → regen | n/a |
| `CTM_plus/Bench/scripts/verify_phase6_b_pre5_write_path_capture_safe.py` | Extend: also verify the stash-on path is host-sync-free. | n/a | n/a |
| `CTM_plus/Bench/tests/test_phase6b2_precapture_hook.py` (NEW) | ~25 CPU tests (mock-vLLM hook resolution + install + teardown). | n/a | n/a |
| `CTM_plus/Bench/scripts/bench_phase6_b2_hook_gpu_smoke.py` (NEW) | GPU smoke: hook-off vs hook-on cell comparison; both byte-equal. | n/a | n/a |
| `CTM_plus/Bench/scripts/PHASE_6B2_HOOK_GPU_SMOKE_RUNBOOK.md` (NEW) | Operator runbook. | n/a | n/a |
| `CTM_plus/Bench/ctm_bench/scripts/int4_protected_files_baseline.json` | REGEN. Add the new `phase6b2_precapture_hook.py` to the G5c pin set. | n/a | n/a |

**Code NOT touched (orthogonality contract):**
* `kv_policy/int4_protected.py` — backend public API. Untouched.
* The forked `vllm_flash_attn` wheel — kernel. Untouched.
* `Int4ProtectedAttentionImpl`'s class method list — no new methods.
* The protected-channel splice logic in `_read_decode_packed_*`.

## 11. Acceptance criteria — G_HOOK

Restated from `PHASE_6B_CUDA_GRAPHS_PLAN.md` §"Phase 6B.2 acceptance
gate", with the 6B.2-specific extensions:

1. **CPU resolution correctness.** Mock-vLLM tests verify the hook
   stashes the correct `slot_idx_t` for each (B, seq_id) combination
   across B ∈ {1, 2, 4, 8}.
2. **CPU install + teardown.** Install wraps `execute_model`;
   teardown restores it byte-for-byte (identity check on the
   restored callable). Teardown idempotent.
3. **Bit-equivalence with the hook OFF.** The hook-off path
   (dispatch fork self-resolves) produces byte-identical state to
   Phase 6B.1's 36-cell verifier. (Phase 6B.1's verifier extended to
   re-run with the hook installed but no stash; same result expected.)
4. **Bit-equivalence with the hook ON.** A new cell-pair verifier
   confirms the hook-on path produces byte-identical state to the
   hook-off path on the same workload.
5. **GPU smoke bit-identity.** Live engine B=2 decode produces
   byte-identical token IDs across hook-off and hook-on cells on
   Qwen-7B + A100.
6. **All existing verifies still GREEN.**
   - `verify_phase5b_4c_*.py`
   - `verify_phase5b_5_needle.py` (re-run; quality regression check)
   - `verify_phase5b_6_batch.py`
   - `verify_phase6_b_pre5_write_equiv.py` (the 36-cell verifier)
   - `verify_phase6_b_pre5_write_path_capture_safe.py` (extended)
7. **TIER5A orthogonality** G5a/G5b/G5c/G6a GREEN (CPU); G6b GREEN
   on the GPU pod.

## 12. Day-level timeline

Total: 2-3 engineer-days CPU + ~$0.05 GPU smoke at G_HOOK gate.

| Day | Deliverable | Acceptance |
|---|---|---|
| **Day 1 (CPU prototype + tests)** | Land `phase6b2_precapture_hook.py` (new module). Add the optional `pre_synced` kwarg to `write_decode_batched`. Land the dispatch-fork edit reading the stash. CPU tests: ~25 tests across the new module + the writer + the dispatch. | All 25 new tests + the existing 49 + the 36-cell equivalence GREEN. |
| **Day 2 (verifier extensions + integration)** | Extend `verify_phase6_b_pre5_write_path_capture_safe.py` to assert stash-on path is host-sync-free. Add a new `verify_phase6_b2_hook_equiv.py` (mirror of the 36-cell verifier but exercising the hook path). Regen G5c baseline with audit note. | Extended capture-safe verifier GREEN; new hook-equiv verifier 36/36 GREEN; G5c regenerated. |
| **Day 3 (GPU smoke + closure)** | Land `bench_phase6_b2_hook_gpu_smoke.py` + `PHASE_6B2_HOOK_GPU_SMOKE_RUNBOOK.md`. Operator runs smoke on A100 pod (~$0.05). Closure doc: `PHASE_6B2_PRECAPTURE_HOOK_FINDINGS.md`. Status snapshot in `PHASE_6B_CUDA_GRAPHS_PLAN.md` flipped to 6B.2 CLOSED. | G_HOOK gate GREEN. Phase 6B.2 closed. |

## 13. What this design does NOT cover (deferred to later phases)

* **`enforce_eager=False` flip + capture-enable.** Phase 6B.3. After
  6B.2 lands, capture should JustWork because every captured-region
  host sync is gone. But the actual flip + the re-verify of all gates
  under capture is a separate phase.
* **Throughput re-measurement.** Phase 6B.4.
* **Prefill graph capture.** Out of scope across all of Phase 6B
  (vLLM 0.7.3 V0 doesn't capture prefill).
* **Multi-GPU / TP graph capture.** Tier 1 v2 item #3; independent of
  CUDA Graphs.

## 14. Decision point for the user

Three options (same pattern as 6B.1's design doc):

| Option | What happens |
|---|---|
| **(A) Approve as written.** | I implement Day 1-3 per §12 timeline. Each day's deliverable lands as a small commit on `claude/phase-6b2-precapture-hook-...`. I report status at end of each day. Day 3 ends with G_HOOK GREEN + operator-runnable smoke; that's the PR-ready state. |
| (B) Approve with modifications. | User edits / questions on specific sections; I revise + re-submit. |
| (C) Reject / pause. | A risk in §9 looks load-bearing; I provide additional CPU-only proof before any code lands. |

**Recommendation: (A).** The pattern matches 6B.1 exactly; the
hook's design is a straight install-shape we've used successfully
twice (cache_aware_install + swap_telemetry); the bit-equivalence
discipline carries forward from 6B.1.

Phase 6B.3 (capture enable) stays gated on a separate approval after
this phase closes GREEN.
