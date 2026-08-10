# CTM+ KV Cache Policy module

This module contains two layered pieces of work:

1. **[int4_protected backend](INT4_PROTECTED_README.md)** *(current
   ship — Phase 5-7)* — a 4-bit KV-cache quantization backend for
   vLLM with quality-preserving "protected channels." Four
   model families validated at 100% needle-retrieval matching stock
   bf16. **For most users, start there.**

2. **Eviction Policy** *(legacy — Phase 4)* — a scoring-only policy
   for which KV-cache blocks to evict, intended as a signal source
   for serving engines that do their own block management.
   Documented below.

---

# CTM+ KV Cache Eviction Policy (Phase 4 legacy)

A scoring-only eviction policy for LLM KV cache blocks.

**This module does NOT manage memory, I/O, or block allocation.**
It only decides *which* blocks to evict, based on LLM-specific signals.
Actual block management is handled by the serving engine (e.g. vLLM's
`BlockSpaceManager`).

## Signals

1. **Attention value** — cumulative attention received by tokens in the block
2. **Position importance** — sink / entity / recent / filler classification
3. **Frequency** — Count-Min Sketch (4-bit, O(1)) for block access counts
4. **Recency** — exponential decay since last access
5. **Sequence priority** — user-set priority weighted by invested compute

Scoring weights are phase-aware (PREFILL vs DECODE).

## Scan Resistance

S3-FIFO admission (SOSP'23) prevents prefill floods from evicting useful
decode-phase blocks. One-hit-wonders are evicted from the small queue
without polluting the main queue.

## Usage

```python
from kv_policy import KVCachePolicy, InferencePhase

policy = KVCachePolicy(max_blocks=2048)
policy.register_sequence(seq_id=1)

# During attention computation
policy.on_token_access(
    token_id=0, position=0, sequence_id=1, block_id=0,
    attention_weight=0.15, seq_len=512,
)

# When GPU memory is full
victims = policy.select_victims(count=4)
for block_id in victims:
    # ... tell vLLM to evict this block ...
    policy.evict_block(block_id)
```

## Configuration

```python
from kv_policy import KVCachePolicyConfig

# Structural parameters only — phase weights are built-in
config = KVCachePolicyConfig.for_long_context()
policy = KVCachePolicy(
    max_blocks=2048,
    sink_tokens=config.sink_tokens,
    recent_window=config.recent_window,
    entity_attention_threshold=config.entity_attention_threshold,
)
```

## Integration Point

vLLM's `Evictor` abstract base class:

```python
class Evictor(ABC):
    def evict(self) -> Tuple[PhysicalTokenBlock, ...]: ...
```

A thin adapter would wrap `KVCachePolicy.select_victims()` to return
`PhysicalTokenBlock` tuples instead of block IDs.

## Benchmarking

`kv_cache_simulator.py` provides a standalone cache simulator with
LRU/FIFO/Random baselines and realistic LLM attention workloads.

## Optional C extension (`kv_policy._ctm_evictor`)

`CTMEvictorModern` has a Cython drop-in (`CTMEvictorModernC`)
backed by `_ctm_evictor.pyx`. It exists to close the per-call
Python-dispatch overhead the May 2026 GPU profiling identified in
`PHASE4_GPU_FINDINGS.md` §11. Semantically identical to the Python
class; selected at runtime via `--phase4-cython-evictor` in the
streaming runner.

**Build:**

```bash
cd CTM_plus/KVPolicy
python3 setup.py build_ext --inplace
# Verify:
python3 -c "from kv_policy._ctm_evictor import CTMEvictorModernC; print('ok')"
```

The `.so` lands next to the `.pyx`. With `setup.py build_ext
--inplace` (or `pip install -e .[ext]`) the runtime picks up the
compiled extension automatically. When the `.so` is absent
`CTMEvictorModernC` aliases to `CTMEvictorModern` — public API
stays stable, but the `--phase4-cython-evictor` flag becomes a
silent no-op (the runner logs a WARNING if so).

**Status:** the C port is semantically validated on real-model
GPU (v9 cell, May 2026) — every eviction outcome bit-identical to
the Python class. Throughput recovery from the port alone measured
at 0pp; the integration tax lives outside the leaf evictor.
See `Bench/bench_out/PHASE4_GPU_FINDINGS.md` §12.6 for the full
write-up.

**Regression tests:** `Bench/tests/test_vllm_protocol_fixture.py`
parametrizes every protocol test over both `[py]` and `[c]`
variants. An additional test
(`test_phase4_external_attr_writes_succeed_on_cdef_class`)
pins the authoritative list of `_phase4_*` attributes the
`triattention` install hooks set externally — adding a new write
site without updating that list will fail locally at $0 GPU.
