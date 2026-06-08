# Phase 10 Step 3 — GPU-native retained index (kill the per-step `as_tensor`)

> **The profile verdict** (`--profile-ab`, ctx=30720, ms per decode-step section):
> ```
> section            off    retain_all  retention
> kernel_inputs    0.1424    3.2809      1.3091     <- THE bottleneck
> readskip_decision 0.0042   0.0450      0.4245     <- scoring + controller
> kernel_call      0.7434    0.7070      0.3983     <- skip SAVINGS are real
> ```
> `kernel_inputs` dominates — and it is **not** the gather compute (`index_select`
> of 28 873 rows is ~0.05 ms). It is `torch.as_tensor(python_list, device=cuda)`:
> converting a 6k–29k-element **Python list** of positions to a GPU tensor, **per
> layer, every step**. The skip savings in `kernel_call` (0.74 → 0.40 ms) are real
> but buried under it. This is why Step 2 (in-kernel gather) didn't help — it kept
> the `as_tensor` and added uncoalesced reads.

## What changed (CPU-side, committed)

- `readskip_select.py`:
  - `ReadSkipController.active_index(seq_len, device, block_scores)` — returns the
    retained positions as a **GPU int32 tensor**, expanded **on-device** from the
    SMALL retained-block set (`blocks[:,None]*bs + arange(bs)`, then filter
    `< seq_len`). No Python position list. Same cadence/EMA side-effects as
    `active_positions` (refactored to share `_step_and_select`).
  - **Correct by construction, CPU-proven:** the on-GPU expansion equals
    `blocks_to_positions` (the validated list path) — asserted in the selftest via
    a pure-Python mimic (`readskip_select.py` → "self-test: PASS").
- `int4_cache_kv_route_a.py`: the retention path now calls `active_index` (GPU
  tensor) when torch + a real cache are present; `retain_all` uses
  `torch.arange(s, device=…)` instead of `as_tensor(list(range(s)))`. CPU/stub
  fallback keeps the Python-list path. **Always-on — no flag** (pure win).
- `int4_protected_k_cache.py`: `kernel_inputs` / `kernel_inputs_gather` skip the
  per-step `int(min)/int(max)` **bounds-check sync** when the index is already a
  tensor (the controller guarantees the range), so the GPU index incurs no
  GPU→CPU stall per layer.

## Why this should finally flip retention

Per-layer math from the profile (retention − off), with Step 3 + Step 1 (kernel
scoring, already built) applied:

| term | before | after Step 3 (+1) |
|---|---:|---:|
| `kernel_inputs` (index) | +1.17 ms | **~+0.01 ms** (GPU arange/gather of n_ret < off's full) |
| `readskip_decision` (scoring+ctrl) | +0.42 ms | smaller (Step-1 kernel scoring) |
| `kernel_call` (skip savings) | −0.35 ms | −0.35 ms (unchanged, real) |

If the index term collapses, the **−0.35 ms kernel-call saving dominates** and
retention can cross *below* off's per-step time — a genuine win at density.

## Validate on the pod

Step 3 needs **no new correctness gate** (it's CPU-proven equal to the list path,
and the GPU port is checked inside `test_gather_decode_gpu.py` → "active_index ==
active_positions: PASS"). Re-run the **same decomposition** — Step 3 is already on:

```bash
cd /workspace/symbolu && git pull origin claude/bold-johnson-rXAd4 && cd CTM_plus
python Bench/scripts/test_gather_decode_gpu.py     # includes the active_index unit check

# Step 1 (kernel scoring) + Step 3 (GPU index, default), host compaction (inkernel OFF):
INT4_READSKIP_KERNEL_SCORES=1 \
python Bench/scripts/phase9_p3_fused_needle.py --ab \
  --ab-modes off,score_noskip,retain_all,retention \
  --context-tokens 30720 --max-model-len 32768 --ab-gen 128 \
  --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/decomp_ctx30k_step13.json
```

**Built-in sanity checks (vs the Step 0/2 runs):**
- `retain_all`: 7.95 / 8.33 → **should jump toward ~off (25)**. `as_tensor(list)` is
  gone; if it doesn't move, Step 3 isn't taking the GPU path.
- `retention`: 13.10 / 14.52 → **the number.** Reads 78 % less with the index cost
  gone → can cross above off.

Leave `INT4_READSKIP_INKERNEL` **off** — host compaction (coalesced reads) + a
cheap GPU index beats the in-kernel uncoalesced gather. Then re-profile
(`--profile-ab`) to confirm `kernel_inputs` dropped and to re-check the
`cache_append` +0.34 ms (likely an async-scoring attribution artifact that should
shrink once scoring is the kernel path).

## Decision

- `retention` crosses positive, quality green → read-skip is a per-watt-at-density
  **win**. (Ceiling unchanged: ~0.5× bf16; density play, not faster-than-bf16.)
- Still negative → re-profile; the residual is whatever section is now top
  (`readskip_decision` controller Python, or `cache_append`) — the next cut.
