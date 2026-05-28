# Phase 6H — High-load capacity bench (design)

> **Status:** DESIGN ONLY. Bench script written but unrun until
> Phase 6G's sidecar audit (Step 1) has measured numbers that tell
> us whether int4's `max_concurrency` claim is honest or
> bookkeeping-only.
>
> **Trigger:** Phase 6 long-context bench (commit `1fb05f6`) showed
> vLLM's `max_concurrency` reports int4_protected = 2× stock bf16
> at every `max_model_len`, but the bench only swept B=1..8 which
> is well below the smaller cell's (bf16) max_concurrency. The 2×
> advantage was unmeasured under load.
>
> **Goal:** Determine whether int4's reported 2× `max_concurrency`
> translates into 2× completed-load capacity in practice — or
> whether the sidecars (Phase 6G) cause int4 to OOM before reaching
> its bookkeeping limit.
>
> **Acceptance**:
> * **JUSTIFIED**: int4 completes ≥1.5× the requests bf16 completes
>   at high load (B ≥ bf16's max_concurrency) at one or more tested
>   max_model_lens, with quality intact. Validates the protect-mask
>   design as a **server-capacity** backend.
> * **PARTIAL**: int4 completes more than bf16 but less than 2×
>   (e.g., 1.2-1.4×). vLLM's max_concurrency is partially honest;
>   sidecars eat some but not all of the advantage.
> * **NOT_JUSTIFIED**: int4 OOMs at or below bf16's max_concurrency.
>   The 2× max_concurrency is purely bookkeeping; sidecars consume
>   the budget int4 thinks it has.

## What this bench answers that the existing one doesn't

`bench_phase6_long_context_gpu.py` (Phase 6 long-context bench)
sweeps B ∈ {1, 2, 4, 8}. At those values, both cells have huge
concurrency headroom — bf16's max_concurrency is 55 at 8K, 26 at
16K, 12 at 32K. We never get close to saturation; the 2× advantage
doesn't show up in throughput.

The high-load bench pushes B toward and beyond bf16's max_concurrency
to find:

1. The B value where bf16 starts preempting / OOMing.
2. Whether int4 keeps serving at that B.
3. The B value where int4 starts preempting / OOMing.
4. The ratio of those two saturation points.

## Sweep design

Per user spec:

| max_model_len | bf16 max_conc | int4 max_conc | Sweep B values |
|---|---|---|---|
| 8192 | 55.3 | 110.6 | **64, 96** |
| 16384 | 26.4 | 52.8 | **32, 48** |
| 32768 | 12.0 | 23.9 | **16, 20** |

The values are chosen to:
* Just exceed bf16's reported max_concurrency (the lower B per row).
* Approach but not exceed int4's reported max_concurrency (the higher B per row).

If int4's reported 2× is honest, the low row in each pair should
preempt bf16 but not int4; the high row should preempt or OOM
int4 too.

If int4's reported 2× is dishonest (sidecar overhead), int4 should
preempt earlier than its reported max_concurrency.

## What gets measured per (cell, max_model_len, B)

* **completed_requests**: count of requests that returned an
  output (not preempted to abort, not OOM-killed).
* **preempted_requests**: count tracked via vLLM's
  `RequestOutput.metrics.preempted_count` summed across the batch
  (best-effort across vLLM versions; falls back to the scheduler
  stats delta from Phase 6 long-context bench).
* **OOM_events**: 1 if the `llm.generate(...)` call raised
  `torch.cuda.OutOfMemoryError`, else 0.
* **end_to_end_wall_s**: total time for the burst to complete.
* **completed_tps**: `total_output_tokens / wall_s` — only counts
  successfully completed requests.
* **peak_HBM_during_burst**: `torch.cuda.max_memory_allocated()`
  taken after burst, before cleanup.
* **quality_pass_rate**: same factual-answer check the long-context
  bench uses (look for "1742" in output). Soft check.

## Prompts

Same long-prompt generator as `bench_phase6_long_context_gpu.py`
(`_make_long_prompt(max_model_len // 2)`). For high-load runs, all
B prompts are the same (so prefill batching maxes out and KV cache
fills uniformly).

## Bench scaffold

New script: `bench_phase6_h_high_load_gpu.py`. Borrows the
subprocess-per-(cell, mml) pattern from
`bench_phase6_long_context_gpu.py` (so each run gets a fresh HBM
snapshot + clean engine state).

Key differences from the long-context bench:

* **`max_num_seqs` must equal the largest B in the sweep** (not
  the bench's 16 default). At B=96 with max_model_len=8K, vLLM
  needs to capture graphs for B=96. This implies max_num_seqs=96
  for the 8K cell.
* **Per-B retry on OOM**: if `llm.generate` OOMs, record the event
  and move to the next B (don't retry the same B). This is
  different from the long-context bench's "skip" behavior.
* **Single B per subprocess** (vs the long-context bench's full
  B sweep per subprocess). High-load runs at the OOM boundary
  can leak HBM that a `torch.cuda.empty_cache()` doesn't fully
  recover; safer to restart the engine for each B.

Subprocess matrix: 2 cells × 3 mml × 2 B values = **12 subprocess
invocations**. With graph capture overhead at high B (capture for
B=96 will be noticeably slower than B=8), expect **20-40 min** total
pod time. Higher than the long-context bench because of the larger
captured shapes.

## Verdict tree

After all subprocesses complete:

```
For each (max_model_len, lower_B, higher_B):
    bf16_completed_at_lower  = ...
    int4_completed_at_lower  = ...
    if int4_completed_at_lower / max(1, bf16_completed_at_lower) >= 1.5:
        verdict_for_this_mml = JUSTIFIED
    elif int4_completed_at_lower > bf16_completed_at_lower:
        verdict_for_this_mml = PARTIAL
    else:
        verdict_for_this_mml = NOT_JUSTIFIED
```

Overall verdict: aggregate across max_model_lens with worst-case
priority (NOT_JUSTIFIED dominates PARTIAL dominates JUSTIFIED).

## Risk flags

1. **OOM during graph capture at high B**: the Phase 6 long-context
   bench's first run OOM'd at default `max_num_seqs=256`; the high-
   load bench by definition NEEDS large captured shapes. Mitigation:
   set `gpu_memory_utilization` conservatively (0.4 — even lower
   than the long-context bench's 0.5) to leave room for the captured
   gather intermediates. Risk: lower KV budget might artificially
   suppress max_concurrency below the reported value.

2. **Sidecar overhead breaks int4's reported max_concurrency**: if
   Phase 6G hasn't shrunk the sidecars first, int4 may OOM at
   B ~= 55 at 8K (same as bf16) instead of B = 110. That's the
   NOT_JUSTIFIED outcome — and a useful one. Mitigation: run 6H
   BOTH before and after 6G, so we have the delta. **Recommendation:
   run 6H first with the current (no-diet) build; this gives the
   baseline. After 6G ships a diet, re-run 6H to measure the
   improvement.**

3. **vLLM scheduler behavior at saturation**: vLLM may
   preempt/swap rather than OOM. This affects the "completed
   requests" metric — preempted requests are still scheduled
   eventually; OOMed requests are aborted. The bench distinguishes
   these via vLLM's scheduler counters (preempted vs aborted).

4. **Quality regression at high load**: cache pressure may degrade
   long-context retrieval. Quality sanity check guards against
   this. Quality_pass_rate must stay equal across cells at the
   same B.

## What this DOES NOT measure

* Per-request latency under load (would need a streaming-aware
  bench).
* Multi-tenant fairness (would need varied prompt lengths /
  multi-batch interleaving).
* Cold-start vs steady-state behavior (single burst per
  subprocess).
* Real production traffic shape (synthetic same-prompt burst).

These are deferred to a future Phase 6I if the 6H result motivates
production-level deployment work.

## Out of scope

* **VC brief edits**: blocked until 6G + 6H measured outcomes both
  land. The user has explicitly halted this until evidence is in.
* **Kernel surgery (Phase 6F)**: still halted. Decision depends on
  6G's HBM gate AND 6H's capacity gate.
* **Cross-family verification** (Mistral, Llama): deferred.

## Estimated effort

| Step | Work | Time |
|---|---|---|
| `bench_phase6_h_high_load_gpu.py` (~400 LOC, based on 6 long-context bench) | Python | 1 day |
| First run, pre-Phase-6G | GPU bench | 0.5 day |
| Findings doc draft, pre-diet | Doc | 0.5 day |
| Re-run post-Phase-6G | GPU bench | 0.5 day |
| Findings doc final | Doc | 0.5 day |
| **Total** | | **~3 days** |

## Decision tree this feeds into

The combination of 6G's HBM outcome and 6H's capacity outcome
determines the project's framing:

| 6G outcome | 6H outcome | Project framing |
|---|---|---|
| HBM ≤ bf16 at 16K/32K | int4 completes ≥1.5× at high B | **Memory + capacity backend**. VC brief: int4 wins on both per-token cost AND high-load capacity. Phase 6F kernel work justified to close the throughput gap. |
| HBM ≤ bf16 at 16K/32K | int4 OOMs ≈ bf16 (sidecar fail) | **Memory backend only**. Per-token win is real; the 2× max_conc was bookkeeping. Brief: long-context cost-per-token, not capacity. |
| HBM > bf16 still | int4 completes ≥1.5× at high B | **Capacity backend, expensive idle.** Brief: high-load production deployments only; not for low-utilization. |
| HBM > bf16 still | int4 OOMs ≈ bf16 | **No memory advantage measurable.** Brief: quality-only framing (protect-mask precision narrative). Halt 6F. |
