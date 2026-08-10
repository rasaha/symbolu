# PCAM Phase 5 — Active-Mode vLLM Integration

**Status:** Active-mode bridge landed, tested end-to-end against a mocked `FreeKVCacheBlockQueue`, and ready to run against real vLLM. Real serving metrics require a GPU machine with vLLM installed and are not yet executed.
**Scope:** active-mode vLLM integration, version-compatibility feature detection, real throughput/latency harness.
**Contract:** [`docs/design/ADR-0001`](../../../../repository/docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md)
**Depends on:** Phase 0–4 (vendored reference, public API, integration surface, replay infrastructure, shadow-mode bridge).

---

## What Phase 5 ships

| Artifact | Role | Runs without a GPU? |
|---|---|---|
| `benchmarks/vllm_active_bridge.py` | Active-mode vLLM integration. Installs PCAM as the live eviction policy by monkey-patching `FreeKVCacheBlockQueue.popleft_n / append / append_n` on a running `BlockPool` instance. | Import and mock-driven wiring: **yes**. Real install against a real `LLM`: **no** (requires a GPU + vllm). |
| `benchmarks/pcam_vllm_perf.py` | Real throughput / latency harness. Runs `vllm.LLM.generate(prompts)` twice — once with the default LRU evictor, once with PCAM active — and reports wall-clock, tokens/sec, and per-prompt p50/p95 latency for both. | Argument parsing, prompts loading, report rendering: **yes**. Actual generation: **no** (requires a GPU + vllm). |
| `simulator/pcam/tests/test_phase5_active_mode.py` | 23 focused tests covering version detection, install/uninstall wiring against a mock `FreeKVCacheBlockQueue`, LRU fallback, append tracking, CLI argument parsing, fail-clean behavior, and `_find_block_pool` path walking. | **Yes.** All 23 green in the current sandbox. |

## Shadow mode vs active mode

Phase 4 shipped **shadow mode**: run vLLM with its default evictor, observe the sequence shapes, derive a trace, replay through PCAM, report what PCAM *would* have decided. Phase 5 ships **active mode**: run vLLM with PCAM's `select_victims` decisions actually driving which blocks get reused.

| Property | Shadow mode (Phase 4) | Active mode (Phase 5) |
|---|---|---|
| Changes live eviction? | No | **Yes** |
| Requires vllm install? | Yes (to run the model) | Yes (and a narrower supported window) |
| Changes observable serving metrics? | No — vllm's behavior is unchanged | **Yes** — throughput and latency reflect PCAM's decisions |
| Failure mode on unsupported vllm? | Full script still runs with synthetic derivation | Fails clean with a specific missing-module error |
| Can be shipped as a "runs alongside production" story? | **Yes** — zero impact on serving | No — changes in-flight block reuse |

Both modes are legitimate. Shadow mode is the corp-dev "proof of value with zero risk" story; active mode is the "here is the measurable win on throughput" story. Phase 4 and Phase 5 coexist; neither replaces the other.

## Supported vLLM version window

**Feature-detected**, not version-string-parsed.

`check_vllm_active_mode_supported()` imports the following modules in order and raises `VLLMVersionSupportError` with a specific missing-module hint on any failure:

1. `vllm` — the package itself must be importable.
2. `vllm.v1.core.block_pool.BlockPool` — the v1 core architecture must be present.
3. `vllm.v1.core.kv_cache_utils.FreeKVCacheBlockQueue` and `KVCacheBlock` — the free-block queue data structure must expose the expected interface.
4. Method surface probe on `FreeKVCacheBlockQueue` — `popleft_n`, `append`, `append_n`, `remove`, and `get_all_free_blocks` must all exist as attributes. Any missing method raises with a list of the offenders so the user knows exactly what drifted.

In practice this maps to **vLLM 0.7.0+** (when v1 core was introduced and became the default) and was verified against the concrete vLLM source tree at version 0.19.0 in this sandbox.

**Older releases** (vllm 0.4.x / 0.5.x / 0.6.x with `vllm.core.evictor[_v2]`) are explicitly **NOT supported** by active mode. They have a different integration point — the `Evictor` ABC — which would need a separate bridge module. Users on those versions should stay on Phase 4 shadow mode.

**Newer releases** (vllm beyond 0.19.0) are supported as long as the v1 core surface stays stable. If upstream refactors `FreeKVCacheBlockQueue`, the method-surface probe catches the breakage at install time and gives the user a specific error listing which methods are missing, so the bridge can be updated surgically.

## How active-mode integration works

The bridge patches three methods on the **instance** (not the class) of `FreeKVCacheBlockQueue` held by the live `BlockPool`:

### 1. `popleft_n(n)` — the eviction path

Default behavior: pop the `n` blocks at the head of the free list (LRU order).

Active-mode replacement:

1. Walk all currently-free blocks via `get_all_free_blocks()` (preserves LRU order).
2. Ask `KVCachePolicy.select_victims(n)` for PCAM's preferred victims.
3. Build a result list: first every PCAM-chosen block that is actually free, then fill any remaining slots from LRU order.
4. Physically unlink each chosen block via `queue.remove(block)`.
5. Reset each chosen block's `prev_free_block` / `next_free_block` pointers to `None` (matches the default `popleft_n`'s cleanup).
6. Increment bridge stats so the perf harness can report PCAM-chosen vs LRU-fallback ratios.

### 2. `append(block)` — the re-entry path

When a block is freed (made evictable), vLLM calls `append(block)`. The active-mode replacement calls the real `append` first, then calls `KVCachePolicy.ensure_block(block_id, ...)` so PCAM begins tracking the block and can consider it for future victim selection.

### 3. `append_n(blocks)` — the batched re-entry path

Same pattern as `append`, batched over a list of blocks.

### Initial admission

At install time, the bridge walks `queue.get_all_free_blocks()` once and admits every currently-free block to PCAM. Without this, PCAM would not know about any of the pre-existing blocks and every early `popleft_n` call would fall back to LRU.

## Safety guarantees

- **PCAM failures never break vLLM.** Every call to `policy.select_victims` and `policy.ensure_block` is wrapped in `try/except`. If PCAM raises for any reason, the bridge treats that as "PCAM returned no victims" and falls back to LRU order. Active mode is a best-effort overlay on vLLM's default behavior, not a replacement.
- **Uninstall is clean.** `uninstall_pcam_active_evictor(installation)` removes the bridge's instance attributes so the class methods resolve again. If the queue already had instance overrides before install, those are preserved. Idempotent — safe to call multiple times.
- **The bridge patches instance attributes, not the class.** Multiple `BlockPool` instances in the same process are unaffected; only the specific `FreeKVCacheBlockQueue` the bridge was installed on is patched.
- **No changes to ADR-0001, the parity harness, or the runtime policy.** Active mode consumes `KVCachePolicy` via the existing Phase 2 `PCAMEvictor` adapter; there is no second policy implementation, no bridge class between CTM+ and PCAM, no drift from the canonical reference.

## Known limitations

Stated narrowly so a reviewer cannot mistake "landed" for "proven":

1. **Performance overhead.** Active-mode `popleft_n` is O(num_free_blocks) per call because it walks the entire free list to let PCAM rank candidates. vLLM's default is O(n). The overhead is measured directly by `benchmarks/pcam_vllm_perf.py` and reported alongside the throughput delta; optimization is a follow-up workstream.
2. **Attention data is block-id-only.** vLLM's v1 core `BlockPool` does not expose per-block attention mass — the attention tensors are consumed inside the paged-attention kernel. PCAM scoring in active mode uses only recency, frequency sketch, and position signals. For attention-rich scoring, the Phase 4 `benchmarks/pcam_trace_extract.py` HuggingFace hook path remains the authoritative source of trained-attention data.
3. **Single synthetic sequence id.** Active mode operates at the physical-block level; blocks are admitted under a single synthetic `sequence_id=0`. Per-sequence phase (`PREFILL` / `DECODE`) is not tracked from the vLLM side. This is a known simplification; a more faithful multi-sequence integration would require deeper hooks into vLLM's `SequenceGroup` lifecycle.
4. **Live execution pending.** The bridge is landed and unit-tested against a mock `FreeKVCacheBlockQueue` (23/23 tests). The perf harness is ready to run but has NOT been executed against a real vLLM + GPU in the sandbox where Phase 5 was authored. Same closure pattern as Phase 2.5 / Phase 4 — documented in `benchmarks/PHASE4_CLOSURE_RUN_LOG.md` (the Phase 5 runbook appends to the same file).

## How to run the perf harness

Prerequisites (on a machine with the right environment):

- CUDA-capable GPU with ≥ 4GB VRAM
- `pip install vllm` in a clean virtualenv
- Network access to `huggingface.co` for the model download, or a pre-seeded HF cache

```bash
cd /path/to/symbolu
python -m venv .venv-vllm
source .venv-vllm/bin/activate
pip install vllm
cd /path/to/symbolu

python benchmarks/pcam_vllm_perf.py \
    --model facebook/opt-125m \
    --prompt "Explain PCAM in one sentence." \
    --prompt "Name three cache eviction algorithms." \
    --prompt "Summarize paged attention in one sentence." \
    --max-tokens 32 \
    --policy both \
    --json /tmp/pcam_phase5_perf.json
```

Expected output structure: a `REAL SERVING METRICS` banner, a table with `policy / tps / wall_sec / mean_ms / p50_ms / p95_ms / prompt_toks / completion_toks`, a throughput delta line (`PCAM throughput delta vs default LRU: +X.YZ%`), and a bridge-stats table for the PCAM row (`popleft_n_calls`, `blocks_evicted`, `pcam_chosen_blocks`, `lru_fallback_blocks`, `append_events`).

## What Phase 5 explicitly does NOT add

- **No new runtime adapters.** vLLM is still the only target. SGLang / TGI / DeepSpeed remain deferred to a future phase gated by design-partner interest.
- **No package-root API expansion.** Every Phase 5 symbol lives under `benchmarks/` or inside `simulator.pcam._report` (private). `simulator.pcam.*` public surface is unchanged.
- **No bridge class between CTM+ and PCAM.** Forbidden by ADR-0001.
- **No changes to the parity harness, the vendored reference, the Phase 1 public API, or the Phase 2 integration surface.**
- **No hard dependency on vllm, torch, transformers, or numpy.** The bridge module imports cleanly in a pure-Python environment; the vllm import is lazy and happens only inside `check_vllm_active_mode_supported` and downstream methods.
- **No automatic tuning** of PCAM's parameters based on vLLM's observed workload. The policy uses whatever `PCAMConfig` the caller supplies; parameter tuning is a Phase 6+ concern.
- **No cross-GPU or multi-engine active-mode coordination.** Each `BlockPool` instance gets its own PCAM policy; there is no shared state across engines.

## What remains after Phase 5

- **One live run of `pcam_vllm_perf.py --policy both` on a GPU machine.** Same closure pattern as Phase 2.5 / Phase 4. Documented in `benchmarks/PHASE4_CLOSURE_RUN_LOG.md` (Phase 5 closure commands will be appended alongside the existing runbook).
- **Real throughput / latency numbers for the acquisition report.** Once the live run happens, numbers get appended to `benchmarks/PCAM_PHASE5_REPORT.md` in the "What has actually been measured" section.
- **Phase 6 — parameter tuning and multi-sequence integration.** After Phase 5 produces baseline active-mode numbers, the natural next phase is (a) auto-tuning `PCAMConfig` based on observed workload and (b) plumbing per-sequence phase information from vLLM's `SequenceGroup` lifecycle into PCAM so scoring can differentiate prefill-heavy vs decode-heavy workloads at runtime.
- **Phase 2.5 RTL closure** remains independent. One live cocotb run on any machine with `pip install cocotb && apt install verilator`.
