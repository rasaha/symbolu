# Phase 6B.2 — pre-capture hook GPU smoke runbook

Status: **code landed, awaiting GPU pod execution.** The CPU portion
of G_HOOK is GREEN — 27 hook unit tests + 36-cell hook-on vs hook-off
bit-equivalence + AST/runtime capture-safe + 99/99 pytest + 15/15
pointer stability + G5a/G5b/G5c (10 files)/G6a all PASS. This
runbook drives the operator-runnable smoke that finishes G_HOOK on
real hardware.

Pairs with:
* `PHASE_6B2_PRECAPTURE_HOOK_DESIGN.md` §11 acceptance criteria
* `bench_phase6_b2_hook_gpu_smoke.py` — the driver this runbook
  invokes
* `tier5a_orthogonality_gate.py` — pre+post orthogonality gate (G6b
  load-bearing wheel SHA pin runs here)

## What this proves

The Phase 6B.2 hook (`install_int4_protected_precapture_hook` wrapping
`ModelRunner.execute_model`) produces **byte-identical generated
tokens** vs the dispatch-fork's 6B.1 self-resolve path on the same
inputs. Confirms:

1. The hook's once-per-step `_resolve_and_stash` + sentinel-gated
   `_sync_pool_counters_from_states` chain is bit-equivalent to the
   per-layer self-resolve chain.
2. The dispatch fork's stash-reading code path produces correct
   output when the stash is present.
3. The hook integration with vLLM 0.7.3 V0's `ModelRunner.execute_
   model` actually fires on real workloads (the
   `write_decode_batched_via_hook_calls` counter advances).

Bisection primitive: `PHASE6B2_INSTALL_HOOK` env var.
* `cell hook-off` — `PHASE6B2_INSTALL_HOOK=0`; install returns inert;
  dispatch fork self-resolves. Equivalent to 6B.1's refactored
  behavior. Reference cell.
* `cell hook-on` — `PHASE6B2_INSTALL_HOOK=1` (default); install
  wraps `execute_model`; dispatch fork reads the stash.

Both cells run identical workloads + same seed + greedy decode.
Byte-identity is the only acceptable bar.

## Acceptance gates

| Gate | What it checks | Pass criterion |
|------|----------------|----------------|
| **G_HOOK.1** | Bit-identical generated tokens | every prompt's `completion_token_ids` byte-equal across both cells |
| **G_HOOK.2** | Hook-on cell exercised the hook path | `write_decode_batched_via_hook_calls > 0` |
| **G_HOOK.3** | Hook-off cell self-resolved | hook-off `write_decode_batched_via_hook_calls == 0` |
| **G_HOOK.4** | Both cells used the new write path | both `write_decode_batched_calls > 0` |
| **G_HOOK.5** | Zero fallbacks in both cells | `write_path_fallback == 0` AND `decode_calls_fallback == 0` |
| **G_HOOK.6** | Hook handle reports stash activity | hook-on `stash_call_count > 0` |
| **G5a/G5b/G5c/G6a** | Orthogonality | gate exits 0 with all in-tree tracks GREEN |
| **G6b** | Load-bearing forked-wheel SHA pin | pod's vllm_flash_attn matches the TIER5A.3 freeze |

**Overall PASS** requires every gate above. Driver exits 1 on any
RED.

## Pod spec

Same as `PHASE_6B1_GPU_SMOKE_RUNBOOK.md`:
* **GPU**: H100 80 GB or A100 80 GB.
* **PyTorch**: ≥ 2.5 + cu124.
* **vLLM**: the int4_protected **forked** 0.7.3 build with the
  TIER5A.3-frozen vllm_flash_attn wheel.
* **Disk**: ≥ 100 GB ephemeral.
* **Per-model protect mask artifact** at
  `/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt`.

Pod-side verification (run BEFORE the smoke):

```bash
python -c "import vllm; print('vllm', vllm.__version__)"
python -c "import vllm_flash_attn; print('wheel ok', vllm_flash_attn.__file__)"
ls "${PROTECT_MASK_PATH:-/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt}"
```

## Step 1 — pre-run orthogonality gate

```bash
cd /workspace/symbolu/CTM_plus/Bench
PYTHONPATH=../KVPolicy:. /workspace/venv-vllm/bin/python3 \
    -m ctm_bench.scripts.tier5a_orthogonality_gate
```

Expected (note: G5c now covers 10 files, including
`phase6b2_precapture_hook.py`):

```
verdict: pass
  g5a (class fingerprint): pass (0 violations)
  g5b (tier5a ast):        pass (0 violations)
  g5c (int4 python sha):   pass (0 violations)
  g6a (cuda fork sha):     pass (0 violations; in-tree defensive)
  g6b (wheel sha pin):     pass (0 violations; load-bearing)
```

**STOP** on any non-PASS. G5c FAIL = checkout dirty; G6b FAIL = wheel
mismatch.

## Step 2 — diagnostic pre-flight

Cheap inspect-only check that the dispatch + stash machinery is
wired correctly without spending GPU time:

```bash
PYTHONPATH=../KVPolicy /workspace/venv-vllm/bin/python3 \
    scripts/diagnose_phase6_b_pre5_write_state.py
```

Verify the output shows:
* `G5c drift check: ok=True  match=10  drift=0` (now 10 files
  including the hook module)
* dispatch verdicts correct

## Step 3 — run the smoke

```bash
PYTHONPATH=../KVPolicy /workspace/venv-vllm/bin/python3 \
    scripts/bench_phase6_b2_hook_gpu_smoke.py \
    --output-dir /workspace/symbolu/bench_out/phase6b2_gpu_smoke
```

Expected wall time: ~60-90 seconds (same shape as 6B.1's smoke).
Cost: ~$0.05 GPU.

Driver spawns two cells as separate subprocesses:
1. **cell hook-off** (`PHASE6B2_INSTALL_HOOK=0`) — install_int4_
   protected_precapture_hook returns inert; dispatch fork falls back
   to self-resolve. Writes `cell_hook_off.json`.
2. **cell hook-on** (`PHASE6B2_INSTALL_HOOK=1`) — hook actually
   wraps `model_runner.execute_model`. Writes `cell_hook_on.json`.

After both cells finish, driver compares + emits `smoke_report.json`
+ `smoke_report.txt`.

## Step 4 — interpret the report

A GREEN run looks like:

```
==============================================================================
Phase 6B.2 GPU smoke — hook-on vs hook-off comparison
==============================================================================
Model:      Qwen/Qwen2.5-7B-Instruct
Prompts:    2    max_tokens: 32
Verdict:    GREEN

Checks:
  [PASS] completion_token_ids_byte_equal              all prompts byte-equal
  [PASS] hook_on_cell_used_hook_path                  write_decode_batched_via_hook_calls=N>0
  [PASS] hook_off_cell_self_resolved                  write_decode_batched_via_hook_calls=0
  [PASS] both_cells_used_write_decode_batched         hook-off=N, hook-on=N
  [PASS] hook-off_zero_fallbacks                      write_path_fallback=0, decode_calls_fallback=0
  [PASS] hook-on_zero_fallbacks                       write_path_fallback=0, decode_calls_fallback=0
  [PASS] hook_on_stash_call_count_positive            stash_call_count=K>0

Hook handle (hook-on cell):
  enabled=True, target=execute_model, stash_calls=K, skipped=...
```

Expected: hook-on's `write_decode_batched_via_hook_calls` == hook-off
+ hook-on's `write_decode_batched_calls` (both should be equal because
the same decode-step count). The hook's `stash_call_count` should be
roughly `n_decode_steps` (one per step, NOT per layer — hook runs at
ModelRunner level, not per-impl).

## Step 5 — post-run orthogonality gate

Re-run Step 1. Same expected output. Confirms the smoke didn't
modify any baselined file.

## Troubleshooting

### G_HOOK.1 (token byte-identity) RED

The most diagnostic failure mode. Inspect `smoke_report.json` →
`per_prompt_diffs`:
* Diverges at token 0: backend swap didn't fire on one of the
  cells. Look at `prefill_calls`; if 0, the int4_protected backend
  install failed (the env var doesn't affect that — it only
  affects the hook install).
* Diverges mid-sequence: hook math diverged from self-resolve.
  Run `verify_phase6_b2_hook_equiv.py` on CPU; if CPU is GREEN but
  GPU is RED, the issue is in the hook's interaction with the live
  vLLM stack. Use `diagnose_phase6_b_pre5_write_state.py --live` to
  inspect writer state mid-run.

### G_HOOK.2 (hook-on didn't use the hook path) RED

`write_decode_batched_via_hook_calls == 0` on hook-on cell. Means
the hook is installed but the dispatch fork doesn't see the stash.
Check:
* Hook handle: `cell_hook_on.json` → `hook_enabled` should be True;
  `hook_target_name` should be "execute_model".
* `hook_stash_call_count` should be > 0 (hook fired). If it's 0,
  `_is_pure_decode_step` returned False — likely an attn_metadata
  shape we didn't anticipate.
* `phase6b2_install_hook_env` should be "1".

### G_HOOK.3 (hook-off used the hook path) RED

`write_decode_batched_via_hook_calls > 0` on hook-off cell. Means
the env override didn't take effect. Check:
* `cell_hook_off.json` → `phase6b2_install_hook_env` should be "0".
* `hook_enabled` should be False, `hook_target_name` should be
  "disabled".

### G_HOOK.6 (stash_call_count == 0 on hook-on) RED

Hook installed but never fired. Likely `_is_pure_decode_step`
rejecting every step. Check `cell_hook_on.json` → `hook_skipped_
step_count`; if it's large and `stash_call_count == 0`, every step
was rejected. The predicate may need adjustment for this vLLM
build's attn_metadata shape.

### Engine load OOM at init

Drop `--gpu-memory-utilization` to 0.4 or 0.3.

## Reference: minimum cells to PASS

| Cell | Env var | Hook installed? | Dispatch fork reads stash? | Expected stat |
|---|---|---|---|---|
| hook-off | `PHASE6B2_INSTALL_HOOK=0` | NO (inert) | NO (stash absent) | `write_decode_batched_via_hook_calls=0` |
| hook-on  | `PHASE6B2_INSTALL_HOOK=1` | YES | YES | `write_decode_batched_via_hook_calls > 0` |

Both cells: temperature=0.0, max_tokens=32, B=2, two distinct
prompts (Greendell needle + short translation). Byte-identity
verifies the hook path produces equivalent generated tokens.
