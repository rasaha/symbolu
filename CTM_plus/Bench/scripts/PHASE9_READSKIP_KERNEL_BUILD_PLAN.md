# Phase 9 → Build: read-skip / sparse-decode kernel — implementation scope

> **Greenlit by** `PHASE9_FINAL_VERDICT.md`: decode-time attention retention
> preserves quality (GREEN, both needle tasks) and read-skip wins throughput
> (~10× proxy). This doc scopes the actual kernel build. **Not built yet** — this
> is the engineering plan, phased with hard gates. int4_protected (the shipped
> product) is untouched; read-skip sits on top of it as a cold store.

## 1. What we're building (one line)

A decode path that keeps the full KV **stored in int4_protected** (density
preserved) but **physically reads only the retained blocks** each step — retained
= sink + recent + decode-attention-selected high-attention blocks (+neighbors) —
so the cold majority stops costing per-step decode work.

This is exactly the policy the quality harness validated; the build turns the
**mask** (correctness proxy) into a **compacted read** (throughput).

## 2. Architecture — where it plugs in (all anchors confirmed)

```
route-A decode (int4_cache_kv_route_a.py, fused_v2 wrapper ~610-665, decode ~756)
   │  per decode step:
   ├─ append K/V to ProtectedKINT4Cache (int4_protected_k_cache.py)          [exists]
   ├─ block scores ← decode-time attention via the bridge:
   │     install_attention_capture → AttentionAggregator.forward_block_attention
   │     (vllm_evictor.py) — Day-5b proved non-zero scores flow                [exists]
   ├─ retained = select_retained_blocks(scores, sink, recent, budget, nbr)    [PORT from harness]
   └─ kernel_inputs(active_blocks=retained) → COMPACTED buffers               [BUILD: §3]
         → fused_protected_k_decode_attention iterates only n_retained tiles  [BUILD: §4]
```

The selection logic (`select_retained_blocks`, sink/recent sets, EMA, neighbors)
is **already written and CPU-tested** in `phase9_decode_retention_harness.py` —
port it verbatim; it's the validated policy.

## 3. The cache change — `kernel_inputs(active_blocks)` (the core of v1)

`int4_protected_k_cache.py:467 kernel_inputs()` today slices the WHOLE sequence
(`[:s]`, lines 502-516). Add an optional `active_blocks: list[int] | None`:

- Build a retained-**position** index from the block ids (`block→positions`).
- **Gather** every per-position tensor by that index instead of `[:s]`:
  `k_packed/k_fp16/v_packed` (permute+gather+contiguous), `k_scale/v_scale`
  (`k_offset/v_offset`) — all gathered by the SAME index so they stay aligned.
- Return reduced buffers of length `n_retained` plus the gathered count.

Why this is the right v1: the fused kernel already loops `s_start→s_end` over
whatever length it's handed (`int4_fused_attention_kernel.py:100`), and **rotary
is baked into the stored K at write time** — so gathering positions preserves
positional encoding for free. Cold blocks remain stored in int4 (density intact);
they're simply not gathered → not read.

**Watch (Phase-1 gate catches it):** the scale-group index `gk = s // GS_k`
(kernel line 109) and `v` group index assume contiguous positions. Scales are
per-position `(S,H,*)` so gathering-by-position keeps them aligned, but verify the
group arithmetic under a non-contiguous gather with the byte-eq gate (§6, Gate 1).

## 4. Kernel change (likely none for v1, maybe a block-skip mask for v2)

**v1 (compacted read):** if `kernel_inputs` returns compacted buffers, the kernel
needs **no change** — it iterates `n_retained` tiles. Cheapest correct path.

**v2 (in-kernel skip, optional optimisation):** instead of compacting on the host,
pass an `active_block_ids` array and have the kernel's tile loop skip
non-retained blocks (extend the existing per-position `valid` mask at line 123 to
a per-block gate). Avoids the host-side gather copy. Only pursue if the gather
copy shows up in the profile.

## 5. Selection + scoring (port + wire, mostly exists)

- **Scoring:** reuse the bridge's decode-time per-block attention
  (`AttentionAggregator`/`forward_block_attention`). Aggregate (sum heads, mean
  layers), EMA with `score_decay`, refresh every `refresh_every` — same knobs the
  harness used.
- **Selection:** port `select_retained_blocks(n_blocks, scores, sink, recent,
  budget, neighbor)` from the harness (already unit-tested: keeps the
  high-attention middle block + neighbors + pinned sink/recent).
- **Observe→retain→refresh** state machine: observe first `observe_steps` with the
  full set, then retain; re-observe every `refresh_every`. (Harness has the
  reference loop in `_masked_decode`.)

## 6. Phased plan with HARD gates (each must pass before the next)

| Phase | Deliverable | GATE (measured) |
|---|---|---|
| **P1 — compacted read, identity** | `kernel_inputs(active_blocks)`; wire route-A decode to pass `active_blocks=ALL` | **Byte-eq:** with `active_blocks=all`, decode output is *identical* (byte/logit) to today's full int4 path. No regression. |
| **P2 — selection + quality** | port `select_retained_blocks` + bridge scoring + observe/refresh | **Quality:** needle + MMLU under retention within noise of full (the harness's GREEN, now on the *real* pruned path, not the mask). COLLAPSE=0. |
| **P3 — throughput** | run the capacity/throughput harness, all-int4 vs read-skip vs bf16 | **Throughput:** read-skip materially beats all-int4 at long context (toward the proxy's ~10× / Step-0's ~1.9× net). |
| **P4 — attribution (PCAM gate)** | profile the per-step select+gather decision | **Dispatch:** is the gain Python-dispatch-bound (Phase-8 −20%)? If yes → fast-path (Cython/CUDA) or the empirical case for PCAM. If no → ships in software. |

## 7. Risks / open design points

- **Rotary under gather** — mitigated (rotary baked at write); confirm via Gate 1.
- **Scale-group indexing under non-contiguous gather** (§3 watch) — Gate 1.
- **Promotion / refresh thrash** — a block dropped then needed again: refresh
  re-observes, but a wrongly-evicted block's data is still STORED (int4), so it
  can be re-included on refresh (unlike true eviction — this is the two-tier
  advantage). Verify refresh recovers it.
- **Prefix caching interaction** — retained-set is per-sequence; confirm it
  composes with vLLM block sharing (or disable for v1).
- **The dispatch tax is the real bet** (P4 = the PCAM gate). Keep the host-side
  select+gather off the critical path or fast-path it.

## 8. Non-goals / invariants

- **int4_protected is unchanged** — it is the cold store; read-skip only changes
  *what is read*, never *how it's stored* or the protect-mask quality path.
- **Quality bar is non-negotiable** — same needle + MMLU (mml=8192) discipline;
  a faster-but-wrong skip is a failure.
- **No closed tracks** (int8-V / n_protect↓ / sidecar diet) sneak in via this work.
- **Start on `dequant_fallback`-equivalent correctness** (compacted read), then
  the fused path; mirror the Day-5 discipline.

## 9. First commit of the build (suggested)

P1 only: add `active_blocks` to `kernel_inputs` (host-side gather) + a CPU unit
test that the gathered buffers equal the `[:s]` buffers when `active_blocks=all`
(pure tensor logic, CPU-testable) — then the GPU byte-eq gate. Land that green
before any selection/throughput work.
