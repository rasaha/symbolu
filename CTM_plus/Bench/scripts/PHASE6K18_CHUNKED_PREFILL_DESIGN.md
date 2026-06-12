# PHASE 6K.18 — chunked prefill for int4_protected DESIGN

Status: SCOPED 2026-06-12. NOT implemented — chunked prefill is factory-
pinned OFF today (the 6K.17 guard). This doc locks the design + the
probes that must run BEFORE the build, in the 6N pattern (decision by
measurement, flag default OFF until every gate passes).

## Why (the honest prize — and its bound)

Chunking does NOT speed up a single request's prefill (same FLOPs,
sliced; total slightly worse). The measured pains it addresses:

1. **Prefill activation spike steals density.** Banked live (crossover
   task, A100-80G): the eager 44K prefill's activations live OUTSIDE
   gpu_memory_utilization — at util 0.85 the cell hit 76.3 GiB committed
   pre-prefill -> OOM; long-context cells run at util 0.55. We quote
   1.78x net density at util 0.85 but long-prompt onboarding can't run
   there. Chunking caps the activation peak at ~chunk size, protecting
   the headline number at long context.
2. **Mixed-batch TTFT fairness.** A monolithic 100K prefill stalls every
   concurrent decode for the whole prefill; chunking interleaves.
3. **mml > 32768 ergonomics.** vLLM V0 AUTO-enables chunked prefill above
   32768 — today the factory must pin it off and the 100K story runs
   single-request. Native support removes a deployment footgun.

PRIZE BOUND (probe P2 below measures it): if the long-prompt spike turns
out activation-dominated, chunking buys util 0.85 at 100K; if it is
KV/sidecar-dominated, the prize shrinks — measure before building.

## The gap (why the 6K.17 guard exists) — exact

Chunk 2+ of a chunked prompt arrives as PREFILL-WITH-CONTEXT and lands on
the same prefix-aware branch APC uses
(`phase5b_backend_install.py` ~1285-1334 -> `run_prefix_prefill`).
Two hard assumptions there are APC-only:

1. **Block alignment** (`phase6k16_prefix_prefill.py:112`):
   `ctx_len % 32 == 0` is asserted — TRUE for APC (only full immutable
   blocks are shared), FALSE for chunking (V0's token budget is shared
   with decodes, so chunk boundaries are arbitrary; a budget that is a
   multiple of 32 narrows but never eliminates the tail case).
2. **The K tail lives in the STAGING BUFFER, not the cache.** A chunk
   ending mid-block leaves its last `ctx_len % 32` K rows in
   `state.k_stage` (exact bf16, not yet quantized/finalized) — the
   dequant-context rebuild never needed them under APC. V and protect
   for those rows ARE already in the cache/sidecars (both are written
   per token), so only K needs the stage splice.

The WRITE path needs no changes: staging already spans write() calls
(`_write_into_state` partial-block continuation, `_stage_k_partial_blocks`
writer:2505 — `pb != state.k_stage_block_id` continues the same block),
which is exactly how a chunk-boundary write resumes. Identity across
chunks is the 6K.16c rid stash (same rid every chunk -> same SeqState ->
staged tail found again) — the same contract APC ships on.

## Locked design

- **D1 — context rebuild for non-aligned ctx_len** (the only new math):
  full blocks via the existing dequant (incl. 6N prot-int8 dequant);
  the trailing `tail = ctx_len % 32` K rows spliced from THIS sequence's
  `state.k_stage[:tail]` (exact bf16); V tail rows from the existing
  per-token dequant (valid for partial blocks by construction).
  CONTRACT: chunked output == monolithic within the context quant
  residual (chunk k attends to QUANTIZED full blocks where monolithic
  attends to exact bf16) — the same bounded S3 residual class as APC.
  The MACHINERY gate is byte-exactness of finalized blocks: K quant is
  block-local (group == block == 32), so the same 32 tokens must produce
  byte-identical nibbles/scale/xmin/protect REGARDLESS of chunk
  boundaries. That is the S1-style gate.
- **D2 — identity contract**: chunked mode requires the rid stash for
  prefill segments (refuse loudly if absent — C-ID extended from
  PHASE6K16_APC_CONTRACT.md §3). The factory arms chunked the way it
  arms APC: installs the 6B.2 hook + a `chunked_active` flag mirroring
  `apc_active` (`phase5b_4c_paged_writer.py:469-483`); the backend
  arming check at `phase5b_backend_install.py:~1302` accepts either.
- **D3 — rollout**: after gates, `Int4ProtectedLLM(enable_chunked_
  prefill=True)` becomes a SUPPORTED configuration (resolver
  `int4_protected.py:273` accepts explicit True and arms D2); the
  DEFAULT stays pinned False (no behavior change for existing deploys);
  `INT4_PROTECTED_ALLOW_CHUNKED_PREFILL` remains the raw-bypass dev
  override. Build additive.
- **D4 — exclusions**: APC+chunked simultaneously is its OWN gate cell —
  if it fails, the combination refuses loudly and chunked ships without
  APC (metadata is uniform: context = cached prefix + prior chunks, so
  it may just work — decide by the gate, not by hope). Swap stays
  refused (6K.15). Spec decode out of scope. Graphs unaffected (prefill
  is eager-coupled, as with APC).

## Touch points (exact)

| Site | Change |
|---|---|
| `int4_protected.py:273` `_resolve_chunked_prefill` + factory pin (~434) | accept explicit True post-gates; arm hook + `chunked_active`; default False unchanged |
| `phase5b_backend_install.py:~1302` arming check | `apc_active() or chunked_active() or override` |
| `phase6k16_prefix_prefill.py:112` alignment rail | replace refusal with the D1 tail path; `gather_context_kv` gains the seq's state (rid-resolved) for the k_stage splice |
| `phase6k16_prefix_prefill.py:197` `run_prefix_prefill` | resolve per-seq rid -> SeqState for tail splice (stash via `stashed_real_seq_ids(prefill=True)`, writer:405/:436) |
| `phase5b_4c_paged_writer.py` | NO write-path changes expected; small read accessor for `k_stage[:tail]` if needed |
| `phase6b2_precapture_hook.py` | verify prefill rid stash count under chunked batch shapes (chunk segments per step) |
| tests | tail-splice selftest section (6N pattern); update `test_phase6k17_chunked_guard.py` for the new resolver semantics (default-False cases MUST keep passing verbatim) |

## Probes BEFORE build (pod, ~30 min total)

- **P1 — empirical gap trace** (~10 min): run a >budget prompt with the
  dev overrides on CURRENT code; confirm the failure fires at the
  alignment rail / arming check as predicted (documents the gap with a
  stack trace, not a belief).
- **P2 — prize bound** (~20 min): STOCK bf16 engine (chunked works
  there), 44K + 100K prompts, chunked on/off: peak memory (incl.
  outside-budget), max sustainable gpu_util, TTFT, concurrent-decode
  stall. If chunking does not restore util 0.85 at 100K on bf16, the
  int4 prize is smaller than claimed — re-scope before building.

## Gate checklist (build session, pod; chunked ON vs OFF A/B)

1. Selftests + guard tests green (incl. new tail-splice selftest;
   6K.17 default-off tests unchanged).
2. **S1-chunked byte-gate**: same prompt monolithic vs chunked — every
   finalized block byte-identical (nibbles + all five sidecars; works
   under prot-int8 too via the 6N format marker).
3. Greedy: chunked vs monolithic, 6 prompts + one >2-chunk prompt —
   near-bar (residual-bounded; bit-exactness NOT expected, state why in
   the report: context quant residual).
4. Needle 32K + 100K WITH chunking at **util 0.85** (the prize cell):
   retrieved, no OOM; record peak memory + TTFT vs the unchunked
   util-0.55 baseline.
5. Mixed-batch TTFT: long prefill + concurrent decodes, chunked on/off —
   decode stall time (the fairness claim, measured).
6. APC+chunked cell (D4 decision) + 6N interaction cell
   (INT4_PROTECTED_PROT_INT8=1, chunked on).

Effort estimate: ~6N-sized — 1-2 days build + 1 day gates, dominated by
the tail-splice correctness and the rid plumbing through
`run_prefix_prefill`. Rules unchanged: default OFF until green; a win on
corrupted output never counts.
