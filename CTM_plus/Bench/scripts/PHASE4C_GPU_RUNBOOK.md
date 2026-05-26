# Phase 4C — Extended Pinning GPU runbook

> **Status:** Operational runbook. **Not yet run on a GPU pod.**
> Modeled on the Phase 3C measurement-path discipline. The
> Phase 4D decision artifact (ship signal / inconclusive /
> negative) will be drafted from the data produced by this
> runbook.

## 0. Environment assumptions

* **GPU pod** with one H100 (80 GB) or comparable.
* **vLLM 0.7.3** installed (canonical for Phase 0-4 work; the
  same version Phase 3C verified the V2 block-manager + LRUEvictor
  shapes against).
* **Model**: ``Qwen/Qwen2.5-7B-Instruct`` (the v2 working-point
  model; matches the workload the Phase 3 finding doc covers).
* **Prefix caching supported** by the engine
  (``enable_prefix_caching=True`` resolves to
  ``PrefixCachingBlockAllocator`` on the GPU allocator).
* **Branch checked out**: ``claude/magical-cannon-zDMkY`` at
  Phase 4B commit ``451d307`` or later.
* **Venv**: ``/workspace/venv-vllm/bin/python3`` (the same venv
  used by Phase 3C runs).
* **Disk**: ~50 MB free for ``bench_out/PHASE4C_SEED42/`` (3
  per-cell streaming summaries + comparison.json + logs).

## 1. Pre-run setup

```bash
cd /workspace/symbolu
git fetch origin claude/magical-cannon-zDMkY
git pull origin claude/magical-cannon-zDMkY
git log -1 --oneline
# Expect: at minimum 451d307 (Phase 4B). Latest commit
# (Phase 4C runbook + 4F design + bench --pin-first-n-blocks
# flag) is preferred.

cd CTM_plus/Bench
mkdir -p bench_out/PHASE4C_SEED42
```

**No calibration step.** Extended pinning operates at the
scheduler/allocator layer and does NOT require the
int4_protected protect-mask. The three cells use stock vLLM
with no int4 backend installed.

## 2. Three-cell measurement matrix

| Cell | ``enable_prefix_caching`` | ``extended_pinning`` | ``pin_first_n_blocks`` | Role |
|------|---------------------------|----------------------|------------------------|------|
| A | OFF | OFF | n/a | sanity floor (no prefix reuse possible) |
| B | ON | OFF | n/a | **stock vLLM competitor** (the realistic baseline) |
| C | ON | ON | 8 (CLI override) | **the proposal** (pinning protects first 8 blocks per request) |

Load-bearing comparison: **B vs C**. Cell A is the throughput
floor only.

## 3. Run command

```bash
cd /workspace/symbolu/CTM_plus/Bench

/workspace/venv-vllm/bin/python3 -m \
  ctm_bench.scripts.bench_phase4_extended_pinning \
  --model Qwen/Qwen2.5-7B-Instruct \
  --shared-prefix-length 256 \
  --n-shared-prefixes 4 \
  --n-requests 100 \
  --max-wall-seconds 60 \
  --pin-first-n-blocks 8 \
  --pin-max-budget-blocks 1024 \
  --output-dir bench_out/PHASE4C_SEED42 \
  2>&1 | tee bench_out/PHASE4C_SEED42.log
```

Parameter rationale:

* ``--shared-prefix-length 256`` — same workload shape as
  Phase 3C; 256-token shared prefix per cohort.
* ``--n-shared-prefixes 4`` — 4 cohorts × 25 requests each.
* ``--n-requests 100`` — Phase 3C precedent; bounded GPU time
  (~17s per cell).
* ``--max-wall-seconds 60`` — generous ceiling per cell; the
  workload typically completes in ~17s.
* ``--pin-first-n-blocks 8`` — pin the first 8 blocks of every
  admitted request. At vLLM's default ``block_size=16``, that's
  128 tokens per cohort prefix. With 4 cohorts the expected
  ``pinned_blocks_total`` ≈ 4 × 8 = 32 (vLLM reuses block_ids
  for matching content; cohort-mates share the same block_ids).
* ``--pin-max-budget-blocks 1024`` — global cap (~32K tokens at
  block_size=16, ~4% of a 24K-block cache). Well above the
  expected ~32 pinned blocks, so the cap is not the binding
  constraint on this workload — operators should see
  ``pin_budget_rejections=0``.

Total expected GPU spend: **~$0.20**, ~30 min (3 engine inits
× ~10s each + ~17s per cell run + comparison aggregation).

## 4. Required artifacts (what should appear in bench_out/)

After the command completes, this tree should exist:

```
bench_out/PHASE4C_SEED42/
├── cell_A/streaming_summary.json
├── cell_B/streaming_summary.json
├── cell_C/streaming_summary.json
├── comparison.json
└── PHASE4C_SEED42.log
```

* **streaming_summary.json** (per cell): full
  ``StreamingRunCellResult`` as JSON. Contains
  ``extended_pinning_stats`` (populated only for cell C),
  per-request latencies, prompt-builder attribution, swap
  counters.
* **comparison.json**: aggregate produced by
  ``build_comparison()``. Has ``cells.{A,B,C}`` per-cell
  metrics, ``comparison.B_vs_C`` ratios + C-only enrichment
  (``c_pinned_blocks_total``,
  ``c_pinned_evictions_avoided``, ``c_forced_pin_evictions``),
  and a ``warnings`` list.
* **PHASE4C_SEED42.log**: full stdout/stderr of the run.

## 5. Verifier script

Run this **after** the command completes:

```bash
/workspace/venv-vllm/bin/python3 -c "
import json
c = json.load(open('bench_out/PHASE4C_SEED42/comparison.json'))
print('=== Per-cell ===')
for name, cell in c['cells'].items():
    print(f'{name}:')
    print(f'  n_requests_completed: {cell[\"n_requests_completed\"]}')
    print(f'  tokens_per_second:    {cell[\"tokens_per_second\"]:.2f}')
    print(f'  ttft_p50_ms: {cell[\"ttft_p50_ms\"]:.2f} / ttft_p99_ms: {cell[\"ttft_p99_ms\"]:.2f}')
    print(f'  e2e_p50_ms:  {cell[\"e2e_p50_ms\"]:.2f}  / e2e_p99_ms:  {cell[\"e2e_p99_ms\"]:.2f}')
    if cell.get('extended_pinning_stats'):
        eps = cell['extended_pinning_stats']
        print(f'  extended_pinning_stats:')
        print(f'    enabled:                       {eps.get(\"enabled\")}')
        print(f'    evictor_path_taken:            {eps.get(\"evictor_path_taken\")}')
        print(f'    pinned_blocks_total:           {eps.get(\"pinned_blocks_total\")}')
        print(f'    pinned_evictions_avoided:      {eps.get(\"pinned_evictions_avoided\")}')
        print(f'    forced_pin_evictions:          {eps.get(\"forced_pin_evictions\")}')
        print(f'    pin_budget_rejections:         {eps.get(\"pin_budget_rejections\")}')
        print(f'    pinned_memory_overhead_bytes:  {eps.get(\"pinned_memory_overhead_bytes\")}')
        print(f'    per_spec_pinned_blocks:        {eps.get(\"per_spec_pinned_blocks\")}')
    print()
print('=== B_vs_C ratios ===')
print(json.dumps(c['comparison']['B_vs_C'], indent=2))
print()
print('=== Warnings ===')
for w in c.get('warnings', []) or ['(none)']:
    print(f'  * {w}')
"
```

## 6. Acceptance gates

| Gate | Pass criterion | What it proves |
|------|---------------|----------------|
| **G1** | All three cells produce ``streaming_summary.json`` | Engine init + run loop healthy under each config |
| **G2** | Each cell's ``n_requests_completed == 100`` | No engine deaths or task drops |
| **G3** | Cell B's ``extended_pinning_stats == {}`` | Flag-OFF path preserves stock behaviour |
| **G4** | Cell C's ``extended_pinning_stats`` has all 9 canonical keys + ``enabled=True`` | Install fired + stats() returns the contract |
| **G5** | Cell C's ``evictor_path_taken`` is one of the V1/V2 documented strings (NOT ``no_known_path`` and NOT ``+no_free_table``) | Real vLLM 0.7.3 exposes the evictor where the research note expected |
| **G6** | Cell C's ``pinned_blocks_total > 0`` | Allocate wrap fired + at least one PinSpec matched |
| **G7** | Cell C's ``pinned_evictions_avoided > 0`` | The evictor wrap actually filtered candidates under memory pressure |
| **G8** | Cell C's ``forced_pin_evictions / (pinned_evictions_avoided + 1) < 0.10`` | Pinning isn't saturating the free pool (operationally healthy) |
| **G9** | Cell C's ``pin_budget_rejections == 0`` | Budget cap of 1024 is well above demand (expected ~32 pinned) |
| **G10** | No ``Int4ProtectedAttentionImpl`` or kernel symbol referenced (AST grep on the bench script; runtime sys.modules check — both Phase 4B CPU tests cover this; trivially preserved by the GPU run since the bench source doesn't change between dry-run and real-vllm modes) | Discipline contract holds |

**G7 is the load-bearing gate**: if ``pinned_evictions_avoided``
is 0, either the workload didn't produce memory pressure (the
evictor never fired) or the wrap isn't intercepting correctly.
See §8 for diagnosis.

## 7. Decision thresholds (Phase 4D mapping)

From the verifier output + comparison.json, apply this matrix:

| Metric | Threshold | Status |
|--------|-----------|--------|
| **Realized-hit improvement** — currently the Phase 4 bench does NOT surface a realized-hit number per cell (no cache_aware_tree installed in cells A/B; pinning-only install). For now, the load-bearing C-vs-B signal is the **latency** improvement attributable to pinning + the **`pinned_evictions_avoided` > 0** evidence. | If a realized-hit signal is needed, re-run Phase 4C with ``--collect-native-prefix-hits`` (Phase 3A probe) added to the runner — that requires a small code change to the bench script (currently the bench does not expose the flag). Defer to Phase 4D analysis if no signal is found via latency alone. | — |
| **TPS regression** | C/B ≥ 0.95 | required (no throughput cliff) |
| **TTFT p99** | C/B ≤ 1.3 | required (no severe tail) |
| **E2E p99** | C/B ≤ 1.3 | required (no severe tail) |
| **pinned_evictions_avoided** | > 0 | required (pinning is doing work) |
| **forced_pin_evictions** | < 5% of evictions_avoided | required (pinning isn't saturating) |
| **TTFT p50 / E2E p50** | C/B ≤ 1.05 | required (no significant median regression) |

Outcome categories (Phase 4D will write the finding doc):

| Outcome | All required gates pass? | TPS / e2e behavior | Phase 4D action |
|---------|--------------------------|--------------------|-----------------|
| **Ship signal** | YES | C/B ≈ 1.0 on TPS; ≤ 1.0 on e2e p99 (i.e. pinning helps or is neutral) | Run Phase 4E replication (seed 43); update v2 brief with measured numbers; ship as v2 "Protected Prefix Cache Policy" feature |
| **Weak signal** | YES on gates; C/B between 1.0-1.1 on e2e p99 | mild regression but within thresholds | Phase 4E 2-seed; only ship if seed 43 confirms the latency picture |
| **Inconclusive** | YES on gates but B≈C across all latency metrics | No measurable benefit | Phase 4D writes Phase-3-style finding; cache-aware-style "no productionization on this workload" disposition |
| **Negative** | gate failure (G7, G8, G10, etc.) OR e2e p99 ratio > 1.3 | regression or no enforcement | Phase 4D writes retirement-style finding; CLI flag retained as experimental but not productionized; same disposition as Phase 3 |

**Two-seed replication is REQUIRED** before any partner-facing
mention. This matches Tier-A discipline from the VC brief +
the Phase 3 precedent.

## 8. Failure interpretation + recovery

### 8.1 ``evictor_path_taken`` resolves to ``no_known_path``

* **What it means**: the install couldn't find the LRUEvictor at
  any of the documented V1/V2 paths.
  ``PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md`` §"Recovery options"
  applies.
* **Diagnosis steps**:
  1. On the GPU pod, in a quick Python session inside the venv:
     ```python
     import vllm; from vllm import AsyncEngineArgs, AsyncLLMEngine
     args = AsyncEngineArgs(
         model='Qwen/Qwen2.5-7B-Instruct',
         enable_prefix_caching=True, gpu_memory_utilization=0.5,
     )
     engine = AsyncLLMEngine.from_engine_args(args)
     bm = engine.engine.scheduler[0].block_manager
     print('block_allocator type:', type(bm.block_allocator))
     print('block_allocator attrs:',
           [a for a in dir(bm.block_allocator) if not a.startswith('__')])
     ```
  2. Identify which attribute exposes the evictor on this vLLM
     0.7.3 instance.
  3. Add that path to ``_resolve_evictor`` in
     ``KVPolicy/kv_policy/extended_pinning.py`` (small CPU
     change; commit + re-run).
* **STOP gate**: do NOT continue to Phase 4D analysis with
  ``no_known_path`` — the result would be meaningless (the
  evictor wrap never fired). Open a follow-up task to extend the
  path-resolution logic, then re-run Phase 4C.

### 8.2 ``pinned_evictions_avoided == 0`` despite evictor path resolved

Two possible causes:

* **Workload doesn't produce memory pressure.** With 100 requests
  × ~18 blocks/request × 4 cohorts (with sharing), total live
  blocks ≈ 600 — well under the ~24K block capacity. vLLM never
  needs to evict, so the wrap never fires.
  * **Recovery**: re-run with ``--gpu-memory-utilization 0.10``
    (tighter cache → faster fill → eviction pressure). Or use
    ``--n-requests 500`` for a bigger workload.
* **Pinning hook not actually intercepting.** Possible if the
  evictor wrap installed but vLLM is calling a different evict
  method (e.g., ``evictor.evict_or_swap()`` instead of
  ``.evict()``).
  * **Recovery**: confirm via the diagnosis snippet in §8.1 that
    ``evictor.evict`` is the right method name; check
    ``evictor.evict_call_count`` (instrumentation in the
    research note's mock) — but real vLLM doesn't expose this.
    May require a small Python check in a separate REPL session.

### 8.3 Realized-hit ratio C/B < 1.5×

Inconclusive or negative. Phase 4D writes the finding doc.

### 8.4 Large e2e p99 regression (C/B > 1.3×)

* **Do NOT ship** even if other gates pass.
* **Likely cause**: ``forced_pin_evictions`` is high → pinning
  saturating the free pool → vLLM evicts pinned blocks anyway,
  but with extra wrap overhead and possible additional
  fragmentation.
* **Recovery**: lower ``--pin-first-n-blocks`` (e.g., 4 instead
  of 8) so fewer blocks are pinned; or raise
  ``--gpu-memory-utilization`` so the cache is bigger. If the
  e2e p99 regression persists at any setting, the conclusion is
  "deterministic pinning doesn't help this workload" — Phase 4D
  finding doc.

### 8.5 ``pin_budget_rejections > 0``

The 1024-block budget was hit. Either the workload is bigger
than expected, or the PinSpec is matching far more blocks than
the analysis suggested. **Diagnosis**: check
``per_spec_pinned_blocks`` and compare against the expected
``n_shared_prefixes × pin_first_n_blocks``.

If rejections are a small fraction (< 5% of allocated) of
``pinned_blocks_total + pin_budget_rejections``, the result is
still valid — just note in the finding doc that the budget cap
was binding. If rejections exceed 5%, re-run with a larger
``--pin-max-budget-blocks`` so the cap isn't the binding
constraint on the C-vs-B comparison.

### 8.6 Discipline-rule violation (G10)

The bench script's AST gate test runs on CPU before the GPU
run; if it had a violation, the test would have failed before
this runbook ran. If the GPU run somehow loads
``Int4ProtectedAttentionImpl`` or kernel modules anyway
(detected via stdout grep of the log), STOP the analysis,
investigate the import path, and fix before resuming.

## 9. Phase 4E — 2-seed replication (conditional)

If Phase 4C lands in **ship signal** or **weak signal**:

```bash
/workspace/venv-vllm/bin/python3 -m \
  ctm_bench.scripts.bench_phase4_extended_pinning \
  --model Qwen/Qwen2.5-7B-Instruct \
  --shared-prefix-length 256 \
  --n-shared-prefixes 4 \
  --n-requests 100 \
  --max-wall-seconds 60 \
  --pin-first-n-blocks 8 \
  --pin-max-budget-blocks 1024 \
  --seed 43 \
  --cells B,C \
  --output-dir bench_out/PHASE4C_SEED43 \
  2>&1 | tee bench_out/PHASE4C_SEED43.log
```

(Cell A omitted — the floor is already established at seed 42.)

Marginal GPU spend: ~$0.10.

**Tier-A discipline**: both seeds must show the same directional
result (C/B ratios consistent in sign + magnitude within ~20%)
before any partner-facing claim.

## 10. What to send back

After the seed=42 run completes, paste back to this session:

1. The verifier output from §5 (full per-cell + B_vs_C + warnings).
2. The ``workload=...`` summary line from the end of
   ``bench_out/PHASE4C_SEED42.log``.
3. The output of ``ls -la bench_out/PHASE4C_SEED42/`` confirming
   all artifacts landed.

I'll apply the §7 decision matrix and either:

* Issue the Phase 4E replication command (ship/weak signal), OR
* Draft ``PHASE4_EXTENDED_PINNING_FINDINGS.md`` (inconclusive/negative), OR
* Document the diagnosis + propose a follow-up CPU patch (any of §8.1-8.5).

## 11. Discipline reminders (durable)

* No ``Int4ProtectedAttentionImpl`` modifications.
* No vLLM-flash-attn kernel modifications.
* No protected-channel splice or sink-mechanism touched.
* No Phase 4 trig revival.
* No TurboQuant revival.
* No VC brief edits without 2-seed replicated ship signal AND
  explicit operator approval (matches the Phase 3 + Phase 4F
  policy).
* No combined-stack X× claims without explicit measurement
  (this run measures pinning ALONE; combined-with-int4_protected
  is a separate measurement track).

## 12. Pointers

| Doc / module | Purpose |
|---|---|
| ``PHASE3_CACHE_AWARE_FINDINGS.md`` | Precedent for inconclusive-finding template |
| ``PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md`` | Evictor-wrap design + recovery options |
| ``PHASE4F_PRIORITY_LRU_DESIGN.md`` | v2.1 elaboration; gated on this run's ship signal |
| ``KVPolicy/kv_policy/extended_pinning.py`` | Phase 4A install + manager (what the bench exercises) |
| ``Bench/ctm_bench/scripts/bench_phase4_extended_pinning.py`` | The bench script itself |
| ``Bench/tests/test_bench_phase4_extended_pinning.py`` | CPU test suite (gates apply pre-GPU) |
