# Phase 6B.1 — GPU smoke runbook

Status: **code landed, awaiting first GPU pod execution.** The CPU
portion of G_PRE-WRITE is GREEN
(`verify_phase6_b_pre5_write_equiv.py` 36/36; AST+runtime capture-safe
GREEN; pointer audit 15/15 STABLE; orthogonality G5a/G5b/G5c/G6a
PASS). This runbook is the operator script for the one remaining
G_PRE-WRITE item — confirming the refactored write path produces
byte-identical generated tokens vs the legacy partition+loop path on
a real Qwen-7B + vLLM 0.7.3 + forked vllm-flash-attn pod.

Pairs with:
* `PHASE_6B1_WRITE_PREFLIGHT_DESIGN.md` §7 Day 3 GPU smoke spec
* `PHASE_6B_CUDA_GRAPHS_PLAN.md` §"Phase 6B.1" acceptance gate
* `bench_phase6_b_pre5_gpu_smoke.py` — the driver this runbook
  invokes
* `tier5a_orthogonality_gate.py` — pre+post orthogonality gate
  (G6b load-bearing wheel SHA pin runs here)

## What this proves

The refactored `PagedKVWriter.write_decode_batched` (the graph-capture
-friendly path) produces **byte-identical generated tokens** to the
legacy partition+loop `writer.write(seq_id=...)` path on the same
inputs. Confirms the 36-cell CPU bit-equivalence verify generalizes
to the production vLLM stack with the real forked vllm-flash-attn
kernel.

Forces the comparison via `PHASE6B1_USE_DECODE_BATCHED` env var:
* Cell **legacy** — `PHASE6B1_USE_DECODE_BATCHED=0`; dispatch fork
  in `Int4ProtectedAttentionImpl.forward()` always falls through to
  the legacy partition+loop path. Equivalent to pre-refactor
  behavior.
* Cell **refactored** — `PHASE6B1_USE_DECODE_BATCHED=1` (default);
  dispatch fork routes pure-decode writes through
  `write_decode_batched`.

Both cells generate the same prompts with the same seed +
`temperature=0.0` greedy decode. Byte-identity is the only
acceptable bar.

## Acceptance gates

| Gate | What it checks | Pass criterion |
|------|----------------|----------------|
| **G_PRE-WRITE.5** | Bit-identical generated tokens | every prompt's `completion_token_ids` byte-equal across both cells |
| **G_PRE-WRITE.6** | Refactored cell exercised the new path | refactored `write_decode_batched_calls > 0` |
| **G_PRE-WRITE.7** | Legacy cell stayed on the legacy path | legacy `write_decode_batched_calls == 0` AND `write_legacy_loop_calls > 0` |
| **G_PRE-WRITE.8** | Zero fallbacks in both cells | `write_path_fallback == 0` AND `decode_calls_fallback == 0` for both |
| **G5a/G5b/G5c/G6a** | Orthogonality (CPU + pod-runnable) | gate exits 0 (G6b included; see Step 1 below) |
| **G6b** | Load-bearing forked-wheel SHA pin | pod's vllm_flash_attn matches the TIER5A.3 frozen baseline |

**Overall PASS** requires every gate above. The driver exits 1 on
any check failure; the runbook treats `exit 1` as RED.

## Pod spec

* **GPU**: H100 80 GB or A100 80 GB. The smoke uses
  `gpu_memory_utilization=0.5` and `max_model_len=4096` — same shape
  as the brief's headline measurements.
* **PyTorch**: ≥ 2.5 + cu124.
* **vLLM**: the int4_protected **forked** 0.7.3 build that includes
  the in-tree-modified vllm_flash_attn wheel — same wheel TIER5A.3
  froze.
* **Disk**: ≥ 100 GB ephemeral for Qwen-2.5-7B-Instruct weights.
* **Per-model protect mask artifact**: present at
  `/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt`
  (or override via `$PROTECT_MASK_PATH`).

Verify before running:

```bash
python -c "import vllm; print('vllm', vllm.__version__)"
# expected: vLLM 0.7.3 (forked)
python -c "import vllm_flash_attn; print('wheel ok', vllm_flash_attn.__file__)"
# OR (some builds nest):
python -c "from vllm import vllm_flash_attn; print('wheel ok', vllm_flash_attn.__file__)"
# expected: a path under site-packages
ls "${PROTECT_MASK_PATH:-/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt}"
# expected: file exists, ~17-50 KB
```

## Step 1 — pre-run orthogonality gate (load-bearing G6b)

Confirm the pod's forked wheel + the in-tree int4_protected files
match the frozen baselines BEFORE spending GPU time. This is the
same pattern TIER5A.3 used.

```bash
cd /workspace/symbolu/CTM_plus/Bench
PYTHONPATH=../KVPolicy:. /workspace/venv-vllm/bin/python3 \
    -m ctm_bench.scripts.tier5a_orthogonality_gate
```

Expected output:

```
verdict: pass
  g5a (class fingerprint): pass (0 violations)
  g5b (tier5a ast):        pass (0 violations)
  g5c (int4 python sha):   pass (0 violations)
  g6a (cuda fork sha):     pass (0 violations; in-tree defensive)
  g6b (wheel sha pin):     pass (0 violations; load-bearing)
```

**STOP** if any track is non-PASS. G5c FAIL means the pod's checkout
diverges from the design-doc-authorized edits — re-clone the
branch. G6b FAIL means the installed forked wheel is different
from the TIER5A.3 freeze — restore the right wheel before
proceeding.

## Step 2 — run the smoke

One command runs both cells (legacy + refactored) as separate
subprocesses, then emits the comparison report.

```bash
cd /workspace/symbolu/CTM_plus/Bench
PYTHONPATH=../KVPolicy /workspace/venv-vllm/bin/python3 \
    scripts/bench_phase6_b_pre5_gpu_smoke.py \
    --output-dir /workspace/symbolu/bench_out/phase6b1_gpu_smoke
```

Expected wall time: ~60-90 seconds total. Each cell:
* ~25-35 s engine init (model load)
* ~5-10 s warmup + main generate (B=2, max_tokens=32)

Cost: ~$0.02 GPU at H100/A100 pod rates.

## Step 3 — interpret the report

The driver prints the comparison summary to stdout AND writes:

```
$OUTPUT_DIR/cell_legacy.json       — token IDs + call_stats for legacy cell
$OUTPUT_DIR/cell_refactored.json   — same shape for refactored cell
$OUTPUT_DIR/smoke_report.json      — comparison verdict + per-prompt diffs
$OUTPUT_DIR/smoke_report.txt       — human-readable summary
```

A GREEN run looks like:

```
==============================================================================
Phase 6B.1 GPU smoke — comparison report
==============================================================================
Model:      Qwen/Qwen2.5-7B-Instruct
Prompts:    2    max_tokens: 32
Verdict:    GREEN

Checks:
  [PASS] completion_token_ids_byte_equal                  all prompts byte-equal
  [PASS] refactored_cell_used_write_decode_batched        write_decode_batched_calls=N>0
  [PASS] legacy_cell_used_only_legacy_loop                write_decode_batched_calls=0, write_legacy_loop_calls=N>0
  [PASS] legacy_zero_fallbacks                            write_path_fallback=0, decode_calls_fallback=0
  [PASS] refactored_zero_fallbacks                        write_path_fallback=0, decode_calls_fallback=0

Phase 6B.1 GPU smoke: GREEN
```

Driver exits 0.

## Step 4 — post-run orthogonality gate (verify no inadvertent edit)

Re-run Step 1's command. Same expected output. Confirms the smoke
itself did not modify any baselined file (it shouldn't, but the
gate is cheap; this is the canonical post-spend confirmation).

## Step 5 — record the finding

Append a row to `INT4_PROTECTED_VC_BRIEF.md` Page 6 "Measured"
table? **No** — Phase 6B.1 is STRUCTURAL PREP, not a quality /
throughput finding. The brief stays unchanged. Phase 6B.4
(throughput bench, gated on 6B.1/6B.2/6B.3 completion) is the
trigger for any brief edit.

Record the GPU smoke artifact paths in
`PHASE_6B_CUDA_GRAPHS_PLAN.md` Status snapshot row for Phase 6B.1
("GPU smoke complete; see $OUTPUT_DIR/smoke_report.json").

## Troubleshooting

### G_PRE-WRITE.5 (token byte-identity) RED

The most diagnostic failure mode. Open `smoke_report.json` and
inspect `per_prompt_diffs`:

* Tokens diverge at position 0: legacy cell didn't run through
  `Int4ProtectedAttentionImpl` at all (look at `prefill_calls`;
  if 0, the backend swap didn't fire). Check vLLM init args.
* Tokens diverge mid-sequence: refactor introduced a quantization
  numerics difference. Re-run `verify_phase6_b_pre5_write_equiv.py`
  on CPU; if CPU is GREEN but GPU is RED, the difference is in
  the V quant or K splice paths under the CUDA backend
  (vs CPU's reference path). Diagnose with `verify_phase5b_4c_2_read.py`.

### G_PRE-WRITE.6 (refactored exercised new path) RED

`write_decode_batched_calls == 0` in refactored cell — the
dispatch fork never routed through the new path. Check:

* `PHASE6B1_USE_DECODE_BATCHED` env var is NOT set to "0" in the
  refactored worker's environment.
* The forward()'s dispatch sees `_is_pure_decode_write()` returning
  True. Inspect the warmup call (4-token prompt; B=1; pure decode
  after the prefill chunk).

### G_PRE-WRITE.8 (zero fallbacks) RED

`write_path_fallback > 0` or `decode_calls_fallback > 0` in either
cell. This means a shape mismatch routed away from
`use_paged_writer` — usually `kv_cache_dtype` wasn't "int4_protected"
or the engine didn't init through `Int4ProtectedLLM`. Re-check vLLM
init.

### G6b (wheel SHA pin) RED

The pod's vllm_flash_attn wheel diverges from the TIER5A.3 freeze.
DO NOT regenerate the G6b baseline on this pod unless the wheel was
explicitly upgraded with operator approval (TIER5A.3 freeze pattern).
Restore the pinned wheel and retry.

### Engine load fails (out-of-memory at init)

Drop `--gpu-memory-utilization` to 0.4 or 0.3. The smoke is
intentionally tiny (max_model_len=4096, B=2) so should fit on
40 GB+; if it doesn't, something else on the pod is holding HBM.

## Reference: minimum cells to PASS

| Cell | Engine | Env var | Pure-decode write path | Expected refactored stat |
|---|---|---|---|---|
| legacy     | Qwen-7B, eager, B=2 | `PHASE6B1_USE_DECODE_BATCHED=0` | NEVER | `write_decode_batched_calls=0` |
| refactored | Qwen-7B, eager, B=2 | `PHASE6B1_USE_DECODE_BATCHED=1` | ALWAYS (for B=2 decode steps) | `write_decode_batched_calls>0` |

Both cells: `temperature=0.0`, `max_tokens=32`, B=2, two distinct
prompts (the Greendell needle + a short translation prompt).
Byte-identity verifies the dispatch fork produces equivalent
generated tokens.
