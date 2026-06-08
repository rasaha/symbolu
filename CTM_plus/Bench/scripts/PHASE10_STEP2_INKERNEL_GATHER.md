# Phase 10 Step 2 — in-kernel gather decode (remove the host gather)

> **Why:** Step 1 removes the observe-step *scoring* cost. Step 2 removes the
> *steady-step* gather cost. Today every steady step calls
> `kernel_inputs(active_positions=…)`, which does a host `index_select` of the
> retained positions **plus** three `permute(...).contiguous()` copies into the
> kernel's layout. Step 2 passes the **full, native, per-position buffers + a
> retained-position index** straight to the kernel, which reads K/V **in place** at
> `gather_idx[logical]` — no `index_select`, no permute-copy.

## What changed (CPU-side, committed)

- `int4_fused_attention_kernel.py`:
  - `_fused_protected_k_decode_attn_splitk_kernel` gains `gather_ptr`, `N_active`,
    and a `USE_GATHER` **constexpr**. The split iterates LOGICAL positions
    `[0, N_active)`; each logical position's PHYSICAL buffer row is `gather_ptr[s]`.
    Buffer offsets branch on `USE_GATHER`: native `(S, H, *)` (gather) vs the
    original permuted `(H, S, *)` (no gather). **`USE_GATHER=False` compiles to the
    original path byte-for-byte** — the existing decode is untouched.
  - `fused_protected_k_decode_attention_gather(...)` — wrapper taking the full
    native buffers + `gather_idx`, shares the kernel with `USE_GATHER=True`.
  - **Correctness is by construction + proven addressing.** The attention math is
    the *validated* kernel, unchanged; the only new surface is the native-vs-
    permuted offset arithmetic, proven equal in numpy (no GPU):
    ```
    python CTM_plus/KVPolicy/kv_policy/int4_fused_attention_kernel.py
    # -> gather addressing (native == permuted-compacted): PASS
    ```
    Attention output is order-independent (a sum over keys), and `gather_idx` is
    the same sorted set the compaction would use, so the two paths are identical.
- `int4_protected_k_cache.py`: `kernel_inputs_gather(active_positions)` returns the
  zero-copy `[:s]` native buffer views + the int32 index (no permute, no gather).
- `int4_cache_kv_route_a.py`: opt-in `INT4_READSKIP_INKERNEL=1`. The decode path
  uses the gather wrapper on steady steps (real retained subset, `k_group_size==1`)
  and the normal path on observe/`None`. Surfaced in `stats['readskip_inkernel']`
  and the `--ab` JSON/header.

## The coalescing trade-off (why GPU numbers decide, not theory)

The host path makes the kernel's K/V reads **coalesced** (it copies the retained
rows into a contiguous, permuted buffer) at the cost of that copy. Step 2 skips the
copy but reads the native buffers **strided** (per-position stride `H*D`). Because
the retained set is **block-aligned** (32-position contiguous runs), the strided
reads stay contiguous *within* a block, so the coalescing loss is small — but
whether (copy removed) beats (strided reads) is an empirical question. **Measure it.**

Also note: the host path's copy is O(n_active), and on steady steps `n_active` is
already ~6 % of `s`, so the gather is *not obviously* the bottleneck — the
`score_noskip`/`retain_all` decomposition (Step 1 doc, Gate C) tells you whether to
expect a win here at all. If `retain_all − off` is small, Step 2 will be marginal.

## Validate on the pod (gates, in order)

**Gate A — gather == compacted == off (correctness).** Self-contained, no vLLM:
```bash
cd /workspace/symbolu && git pull origin claude/bold-johnson-rXAd4 && git log -1 --oneline
cd CTM_plus
python Bench/scripts/test_gather_decode_gpu.py
# expect per s: |compacted-gather|~0, |off-gatherAll|~0 -> PASS
```
If the diffs aren't ~0, **stop** — the gather kernel diverges; no throughput number
from it is trustworthy.

**Gate B — quality holds with in-kernel gather.** Re-run the A/B at one length with
`INT4_READSKIP_INKERNEL=1` (combine with `INT4_READSKIP_KERNEL_SCORES=1` for the
full Step-1+2 stack); retention quality must stay green:
```bash
INT4_READSKIP_KERNEL_SCORES=1 INT4_READSKIP_INKERNEL=1 \
INT4_READSKIP_SINK=64 INT4_READSKIP_RECENT=512 INT4_READSKIP_BUDGET=512 \
python Bench/scripts/phase9_p3_fused_needle.py --ab \
  --ab-modes off,retention --context-tokens 16384 --max-model-len 18432 \
  --ab-gen 128 --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/ab_ctx16384_step1and2.json
# [ab] header should print kernel_scores=True inkernel=True
```

**Gate C — does removing the gather move throughput?** A/B retention with inkernel
off vs on (Step-1 scoring on for both, so this isolates the gather):
```bash
for IK in 0 1; do
  INT4_READSKIP_KERNEL_SCORES=1 INT4_READSKIP_INKERNEL=$IK \
  python Bench/scripts/phase9_p3_fused_needle.py --ab --ab-modes off,retention \
    --context-tokens 32768 --max-model-len 34816 --ab-gen 128 \
    --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
    --out Bench/bench_out/PHASE10_AB/ab_ctx32k_ik${IK}.json
done
```
Compare `retention` Δ% vs off across `ik0` and `ik1`. inkernel improving Δ% (less
negative / crossing positive) ⇒ the host gather was real cost and Step 2 removes it.
No change ⇒ the gather wasn't the floor (expected if `retain_all − off` was small).

## Decision

- Step 1 + Step 2 together flip `retention` Δ% positive at length, quality green →
  read-skip ships as a per-watt-at-density win. (Ceiling: ~0.6× bf16 even when
  winning over `off` — a density play, never faster-than-bf16.)
- Still negative after both → the software levers are exhausted; the residual is the
  per-step decode overhead / occupancy floor — the measured PCAM case that only
  hardware (or a fundamentally different kernel) breaks.

## Caveats

- **GPU-unvalidated from the authoring box** (no CUDA here). The addressing math is
  CPU-proven; Gate A is the kernel's first real run.
- `k_group_size == 1` only (production K config); other groupings keep the host path.
- Used only on steady steps; observe/refresh/prefill keep the original kernel.
