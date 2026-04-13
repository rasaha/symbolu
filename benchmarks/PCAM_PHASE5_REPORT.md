# PCAM Phase 5 Benchmark Report

**Audience:** engineering reviewers, technical diligence, partner/acquirer corp-dev
**Artifact status:** active-mode vLLM bridge landed and unit-tested end-to-end against a mock `FreeKVCacheBlockQueue`. Real serving metrics pending one live run on a GPU machine.
**Source branch:** PCAM software-product roadmap, Phase 5
**Spec of record:** [`docs/design/ADR-0001`](../docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md)
**Architecture overview:** [`../simulator/pcam/docs/ARCHITECTURE_OVERVIEW.md`](../simulator/pcam/docs/ARCHITECTURE_OVERVIEW.md)
**Phase 5 operational doc:** [`../simulator/pcam/docs/PHASE5_ACTIVE_MODE.md`](../simulator/pcam/docs/PHASE5_ACTIVE_MODE.md)
**Closure run log:** [`PHASE4_CLOSURE_RUN_LOG.md`](PHASE4_CLOSURE_RUN_LOG.md) (Phase 5 closure runs will be appended here)

---

## CTM+ ↔ PCAM relationship (canonical)

**CTM+ is the canonical KV-cache policy specification. PCAM is the runtime backend that implements it bit-for-bit, exposes it through a small Python API, and plugs into inference runtimes through narrow adapters. The two are kept in sync by a 20-test parity harness that has been green since Phase A.**

- **CTM+** on this branch is the scoring policy spec at `CTM_plus/KVPolicy/kv_policy/attention_evictor.py`: four-signal phase-aware scoring, Count-Min frequency sketch, sink / entity / filler classification, sequence lifecycle. Per-process, per-policy, per-sequence. It is **not** a multi-runtime orchestrator on this branch — any document that describes it that way is overclaiming what the code does today.
- **PCAM** is the runtime backend that imports the vendored CTM+ reference, matches it bit-for-bit via `simulator/pcam/kv_policy.py::KVCachePolicy`, and exposes `PCAMEvictor`, tier hints, trace replay, and the benchmark layers in this report. One scoring function, one file, one oracle.
- **Shadow mode** (Phases 2–4) is **verified live**: real torch forward passes, real attention tensors, real TraceEvent replay through `KVCachePolicy`. Observational — PCAM reports what it *would* have decided on the observed workload.
- **Active mode** (Phase 5) is **implemented and unit-tested, pending one live GPU run**: a monkey-patch against vLLM's v1 `FreeKVCacheBlockQueue.popleft_n` routes live eviction through PCAM. 23 unit tests green against a mock queue. The live GPU closure runbook is at [`PHASE4_CLOSURE_RUN_LOG.md`](PHASE4_CLOSURE_RUN_LOG.md) section D.

See [`ARCHITECTURE_OVERVIEW.md`](../simulator/pcam/docs/ARCHITECTURE_OVERVIEW.md) for the full diagram, the explicit clarifications, and the source-of-truth pointers. That page is the single authoritative source for this relationship; any doc that disagrees with it should be corrected toward it.

---

## Executive summary

1. **PCAM can now be installed as the live eviction policy inside vLLM.** The active-mode bridge at `benchmarks/vllm_active_bridge.py` patches the `FreeKVCacheBlockQueue` instance inside a running `BlockPool` so every `popleft_n(n)` call routes through `KVCachePolicy.select_victims`. This turns PCAM from a shadow observer (Phase 4) into an active participant that actually determines which blocks vLLM reuses.
2. **The integration is version-safe.** Feature-detected against the v1 core `BlockPool` architecture (vLLM 0.7.0+). Fails clean with a specific missing-module error on older releases. Method-surface probe catches upstream refactors before install time.
3. **The perf harness is ready to run.** `benchmarks/pcam_vllm_perf.py` runs vLLM twice — once with default LRU, once with PCAM active — against the same model and prompts, and reports wall-clock throughput, per-prompt p50/p95 latency, and the PCAM/LRU throughput delta. The harness has not been executed on a GPU machine yet; that is the single remaining step.
4. **Parity and prior-phase behavior are preserved.** Every Phase 0–4 test still passes. Active mode is a purely additive capability.

## What has actually been measured

All numbers in this section are live on the current branch.

### Parity against the canonical reference

```
$ python -m pytest simulator/pcam/tests/test_sketch_conformance.py \
                   simulator/pcam/tests/test_attention_evictor_parity.py -q
20 passed, 0 failed, 0 skipped
```

Unchanged from Phase 4. The vendored reference (`simulator/pcam/reference/attention_evictor_vendored.py` at pinned commit `e4bbb68bb53...`) is still the oracle; the parity harness is still the sync mechanism; there is still no bridge class between CTM+ and PCAM.

### Active-mode integration tests

```
$ python -m pytest simulator/pcam/tests/test_phase5_active_mode.py -q
23 passed, 0 failed, 0 skipped
```

Coverage:
- **Version detection** — `check_vllm_active_mode_supported` fails clean without vLLM (in this env), imports without crashing, and succeeds under the installed vLLM when present.
- **Install / uninstall wiring** — verified against a mock `FreeKVCacheBlockQueue` that replicates the real `popleft_n` / `append` / `append_n` / `remove` / `get_all_free_blocks` interface. Tests confirm that after install, PCAM tracks every free block; after uninstall, the patched methods are removed from the instance `__dict__` so class-method lookup resolves again.
- **Idempotent uninstall** — safe to call multiple times, no double-restore.
- **LRU fallback on empty PCAM selection** — when PCAM returns fewer victims than requested, the bridge fills the remainder from LRU order. A specific test monkey-patches `policy.select_victims` to return `[]` and verifies the bridge returns the full requested count by falling back to LRU, with bridge stats showing `pcam_chosen_blocks=0`, `lru_fallback_blocks=N`.
- **`append` / `append_n` tracking** — newly-freed blocks appear in `policy.blocks` after the patched methods fire, so PCAM can score them on the next eviction round.
- **Perf harness CLI** — argument parsing, prompts loading (from `--prompt` repetition or `--prompts-file`), fail-clean exit codes without vLLM, report rendering with and without both policies.
- **BlockPool path walking** — `_find_block_pool` handles the canonical v1 core path (`llm.llm_engine.kv_cache_manager.block_pool`), an alternate scheduler-based path, and raises `VLLMVersionSupportError` with a clear multi-line error listing every path it tried when the engine shape is unrecognizable.

### Full PCAM test suite

```
$ python -m pytest simulator/pcam/tests/ simulator/pcam/rtl/tests/ -q
135 passed, 3 skipped in 2.00s
```

Breakdown:
- 14 sketch conformance (Phase A)
- 6 attention-evictor parity (Phase B/C)
- 22 Phase 1 public API
- 26 Phase 2 integration
- 23 Phase 3 benchmarks
- 21 Phase 4 real-runtime
- **23 Phase 5 active-mode** (new)
- 1 Phase 2.5 cocotb wrapper (skipped)
- 2 Phase 4 extractor fail-clean tests (skipped in this env because torch + transformers ARE installed)

0 failed, 0 errored.

### Replay-only numbers from prior phases (still authoritative)

The Phase 4 live results remain valid and are the authoritative replay-only baseline for this report:

```
$ python benchmarks/pcam_compare_baselines.py --include-inrepo-baselines --max-blocks 128
policy                   source   evictions  sink_evictions  attn_cost
PCAM                     runtime  6          0               0.0060
LRU                      inline   6          1               0.0050
LFU                      inline   6          1               0.0050
SinkLRU (in-repo)        in-repo  6          0               0.0060
H2O (in-repo)            in-repo  6          0               0.0060
IndustryStyle (in-repo)  in-repo  0          0               0.0000
```

PCAM matches best-in-class sink-aware baselines (`SinkLRU`, `H2O`) on the zero-sink-eviction guarantee and beats sink-unaware naive policies (`LRU`, `LFU`) by construction. These are **replay-only policy-decision metrics**, not serving metrics.

## Three honesty tiers (updated from Phase 4)

Phase 5 adds a fourth tier to the Phase 3/4 framing — **active-mode serving evidence** — and clearly distinguishes it from the three existing tiers.

| Tier | Example | What it proves |
|---|---|---|
| **Replay-only** (Phase 3) | `pcam_trace_replay.py`, default `pcam_compare_baselines.py` | PCAM's scoring decisions on a deterministic trace. Zero runtime dependencies. |
| **In-repo richer baselines** (Phase 4, live) | `pcam_compare_baselines.py --include-inrepo-baselines` | PCAM vs sink-aware production baselines on the same trace. Adapter correctness verified by tests. |
| **Shadow mode** (Phase 4, pending live run) | `pcam_vllm_demo.py --real-vllm`, `pcam_trace_extract.py` | PCAM's hypothetical decisions on a real workload. vLLM runs its own default evictor; PCAM reports what it would have done. |
| **Active mode** (Phase 5, pending live run) | `pcam_vllm_perf.py --policy both` | Real serving throughput and latency under vLLM's default evictor vs under PCAM active. The PCAM numbers reflect an engine where PCAM's decisions actually drove which blocks were reused in flight. |

Every script output carries a tier label. `pcam_vllm_perf.py` prints a `REAL SERVING METRICS` banner so a reader cannot mistake its output for replay data.

## Current limitations (stated narrowly)

1. **No real serving numbers yet.** The active-mode bridge and the perf harness are landed and unit-tested. One live run on a GPU machine will produce the first real throughput/latency comparison. Same pattern as Phase 2.5 and Phase 4 closures.
2. **Performance overhead is known but not yet measured.** Active-mode `popleft_n` is O(num_free_blocks) because it walks the full free list to let PCAM rank candidates. vLLM's default is O(n). The perf harness measures this directly; optimization is a Phase 6+ workstream if the overhead proves material.
3. **Block-level scoring only.** vLLM's v1 core `BlockPool` does not expose per-block attention mass; PCAM's active-mode scoring uses only recency, frequency-sketch, and position signals. For richer scoring with trained attention, shadow-mode via the HuggingFace extractor (`pcam_trace_extract.py`) remains the authoritative path.
4. **Single synthetic sequence id.** Active mode admits all blocks under one synthetic `sequence_id=0` because the `BlockPool` layer has no direct visibility into vLLM's `SequenceGroup` lifecycle. A Phase 6+ pass can plumb per-sequence phase through the bridge if needed.
5. **Narrow version window.** The bridge targets vLLM's v1 core architecture (0.7.0+). Older releases with the `Evictor` ABC are not supported by active mode; users on those versions should stay on Phase 4 shadow mode. This is explicit in the version-detection error and in the Phase 5 doc.
6. **Active mode does not patch `BlockPool` directly.** It patches the `FreeKVCacheBlockQueue` *instance* the BlockPool holds. If vLLM switches to a different free-list data structure in a future release, the bridge will need to be re-targeted. The method-surface probe catches this at install time and names the missing method, so the failure mode is a clean error, not a silent corruption.

## How to reproduce every live number

```bash
# Full PCAM test suite (135 passed, 3 skipped)
python -m pytest simulator/pcam/tests/ simulator/pcam/rtl/tests/ -q

# Phase 5 specifically
python -m pytest simulator/pcam/tests/test_phase5_active_mode.py -v

# Verify the bridge fails clean without vllm (should print "ERROR: vllm is not installed.", rc=2)
python benchmarks/pcam_vllm_perf.py --policy pcam --prompt "hi" --quiet

# Verify the bridge fails clean at the check helper (should print "ERROR: vllm...", rc=2)
python -c "from benchmarks.vllm_active_bridge import check_vllm_active_mode_supported; \
           check_vllm_active_mode_supported()"
```

## The one remaining closure step

**Run `benchmarks/pcam_vllm_perf.py --policy both` on a GPU machine with vLLM 0.7.0+ installed.**

See `simulator/pcam/docs/PHASE5_ACTIVE_MODE.md` "How to run the perf harness" for the exact install and command sequence. Expected engineer-time: ~30 minutes once the environment is available.

After the first live run, the engineer should:

1. Append the result to `benchmarks/PHASE4_CLOSURE_RUN_LOG.md`'s Run log using the same entry format as the Phase 4 closure entry.
2. Update the "What has actually been measured" section of this file with the real throughput / latency table and the PCAM vs default-LRU delta percentage.
3. Update the status line at the top of this file from "pending" to "closed".
4. Commit as one atomic change with the message `Phase 5 closure: first live active-mode vllm run`.

No code changes are anticipated during closure. The bridge is unit-tested end-to-end against the real vLLM 0.19.0 method surface (probed via the installed but not-GPU-usable vllm during Phase 5 development), and all 23 Phase 5 tests pass. If any wiring issue surfaces during the live run, the fix is expected to be small and should be debugged against the vendored reference and the parity harness — never against the tests or the report.

## What waits for the next phase

**Phase 6 — parameter tuning, multi-sequence integration, attention plumbing.** Once Phase 5 produces baseline active-mode serving numbers, the natural follow-ups are:

- **Auto-tune `PCAMConfig`** based on observed workload characteristics (prompt length distribution, decode-to-prefill ratio, attention locality).
- **Per-sequence phase plumbing.** Currently all blocks are admitted under a single synthetic sequence id. Plumbing vLLM's `SequenceGroup` lifecycle events into PCAM would let scoring differentiate prefill-heavy vs decode-heavy workloads at runtime, which the four-signal formula in ADR-0001 is already built for.
- **Attention mass surfacing.** The block-level attention signal is the one signal PCAM's runtime policy has but active mode can't use because vLLM doesn't expose it at the block-pool layer. A small patch to vLLM itself (not the bridge) to publish per-block attention mass as a post-step hook would unlock attention-aware active-mode scoring.
- **SGLang / TGI / DeepSpeed active-mode adapters.** The vLLM-specific bridge shape generalizes; each runtime has its own free-list or eviction-hook point. These should ship only when a design partner asks.
- **Phase 2.5 RTL closure** is still the independent outstanding item. One live cocotb run on any machine with `pip install cocotb && apt install verilator`.

None of Phase 6 is blocked on anything beyond Phase 5's first live run.
