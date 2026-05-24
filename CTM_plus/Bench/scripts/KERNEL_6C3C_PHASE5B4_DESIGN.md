# Phase 5B.4 — design + sub-sub-phase sequencing

> **The phase that actually lands the memory-savings claim.** Phase
> 5B.3a registered `kv_cache_dtype="int4_protected"` as a vLLM
> config option but kept stock bf16 storage (delegate forward).
> 5B.4 replaces the storage + read/write paths so vLLM's BlockManager
> allocates the smaller INT4 layout, and the kernel attends to it
> correctly.
>
> Multi-step. Splitting into 5B.4a/b/c with separate acceptance gates
> because any single step alone produces either no savings or corrupt
> output — only the full chain landed together gives the headline.

## Why this is multi-step

Memory savings require three things in lockstep:

1. **`get_kv_cache_shape`** — return a smaller per-block shape so vLLM
   allocates less memory per block.
2. **CacheEngine byte-cost** — match the smaller shape's actual bytes
   so BlockManager's scheduling math is consistent.
3. **`Int4ProtectedAttentionImpl.forward`** — replace the FA delegate:
   - Writes go through `PartialGroupQuantizer` (no `reshape_and_cache_flash`).
   - Reads go through the Phase 2.4.1b packed kernel (no `flash_attn`
     reading bf16 from the smaller-shape tensor as if it were bf16).

Landing only #1 + #2 gives memory savings but the kernel reads garbage.
Landing only #3 gives no memory savings (existing 5B.3a state).
They must land together, but we can sequence:

| Sub-sub | Acceptance gate |
|---|---|
| **5B.4a — forward replacement on stock layout** | Replace forward; cache layout unchanged (stock bf16). Generation bit-equal to stock. Proves we can intercept write+read without corrupting. |
| **5B.4b — smaller cache shape + matching byte cost** | Override `get_kv_cache_shape` + CacheEngine byte cost. Verify KV reserve drops in engine init log. Generation may be CORRUPT (kernel reads from smaller-shape tensor as if it were stock) — that's expected and the next gate fixes it. |
| **5B.4c — bridge the read path to the smaller layout** | Adjust forward's read path to interpret the smaller shape correctly via the Phase 2.4.1b packed kernel. Generation back to correct. **THIS IS GREEN STATE — memory savings + correct output.** |

Each sub-sub has its own commit + verify.

## Probe needed before 5B.4a

The current probe pass-back is required to write 5B.4a. Sections of
interest:

| Probe section | Tells me |
|---|---|
| 1. `FlashAttentionImpl.forward` source | What the forward currently does — exact `reshape_and_cache_flash` call, the attention kernel call, branching logic |
| 2. `FlashAttentionImpl.__init__` | What state the impl maintains (attrs `kv_cache_dtype`, `num_heads`, `head_size`, etc.) — guides what we must preserve |
| 3. `FlashAttentionMetadata` fields | What's passed in `attn_metadata` (slot mapping, seq lengths, block tables) — required for write path |
| 4. `AttentionLayer` protocol | The "layer" first arg to forward (separate from `self`) — informs what we can access |
| 5. `reshape_and_cache_flash` schema | Op signature, dtype validation, what tensors it expects |
| 6. `flash_attn_with_kvcache` / `flash_attn_varlen_func` | The actual attention kernel call we'll need to replace |

Run probe_phase5b_4_forward.py and paste the output. Implementation
follows in subsequent commits.

## 5B.4a — forward replacement on stock layout

**Scope:** Override `Int4ProtectedAttentionImpl.forward` to do its own
write + attention, but with the SAME stock bf16 layout. Just changing
who writes to the cache, not what's in it.

**Steps:**
1. Read source of `FlashAttentionImpl.forward` from probe output.
2. Recreate the same logic in our subclass: extract slot_mapping from
   metadata, call `reshape_and_cache_flash` directly (bypassing the
   parent's call so we control args).
3. Verify generation bit-equal to stock.

**Acceptance:**
- `verify_phase5b_4a_forward.py`: install backend, generate, output ==
  stock baseline output (bit-equal).
- Forward is no longer a delegate — we control all the code paths.

**Why this step is valuable independent of 5B.4b:** it proves we can
intercept the forward without breaking generation. If 5B.4b/c fail,
we can fall back to 5B.4a as a known-good intermediate state.

## 5B.4b — smaller cache shape + matching byte cost

**Scope:** Override `Int4ProtectedAttentionBackend.get_kv_cache_shape`
and `CacheEngine.get_cache_block_size` to use INT4 sizing. Output is
EXPECTED TO BE INCORRECT at this stage (kernel reads garbage from the
smaller tensor) — that's the next sub-phase to fix.

**Steps:**
1. Subclass override:
   ```python
   @staticmethod
   def get_kv_cache_shape(num_blocks, block_size, num_kv_heads, head_size):
       # 5B.4b shape: halve head_size for INT4 packing (D/2 bytes per token
       # for K via uint8 packing). V stays full size until Phase 2.6.
       # Tuple is (K|V, num_blocks, block_size, num_kv_heads, packed_head_size).
       # Treating each element as uint8 (1 byte) instead of bf16 (2 bytes)
       # also halves bytes regardless.
       return (2, num_blocks, block_size, num_kv_heads, head_size // 2)
   ```
2. CacheEngine.get_cache_block_size: patch (via monkey-patch on the
   class) to return matching smaller bytes for `"int4_protected"`.
3. Verify engine init log shows KV reserve drop:
   - At gpu_memory_utilization=0.3, max_model_len=2048: stock 8.03 GiB → expected ~4 GiB.
   - At gpu_memory_utilization=0.5, max_model_len=4096: stock ~24 GiB → expected ~12 GiB.

**Acceptance:**
- `verify_phase5b_4b_memory.py`: engine init succeeds (no crash); KV
  reserve from log is roughly halved; generation IS CORRUPT (informational
  only — the next phase fixes it).

**Why this step is valuable independent of 5B.4c:** it proves
BlockManager respects our smaller layout. If 5B.4c hits unfixable
issues, we know exactly which step failed.

## 5B.4c — bridge the read path

**Scope:** With the smaller shape from 5B.4b, the kernel needs to read
the data CORRECTLY. Currently 5B.4a's forward calls
`reshape_and_cache_flash` which expects the FULL bf16 shape. With the
shape halved (5B.4b), reshape_and_cache_flash may crash OR silently
corrupt.

Three options:
- **Option A:** Patch our forward to skip `reshape_and_cache_flash` and
  write directly to the smaller paged cache via a Python writer (uses
  `PartialGroupQuantizer` from Phase 5B.1).
- **Option B:** Write a custom CUDA kernel that does what
  reshape_and_cache_flash does but for our layout. Bigger lift.
- **Option C:** Use the Phase 2.4.1b packed sidecar pattern in parallel
  with the smaller paged cache. Doesn't save memory beyond 5B.4b's
  paged-shape reduction.

**Lock:** Option A. Use the Python writer + read via Phase 2.4.1b kernel.

**Steps:**
1. Replace the `reshape_and_cache_flash` call in our forward with a
   PartialGroupQuantizer call that writes to the smaller paged cache.
2. Replace the attention kernel call with a Phase 2.4.1b packed kernel
   call. (May require adapting the kernel to read from
   `(num_blocks, block_size, ...)` layout instead of `(1, S_max, ...)` —
   either via gathering blocks into a contiguous view OR by patching
   the kernel's block-table-aware path.)
3. Verify generation correctness recovers.

**Acceptance:**
- `verify_phase5b_4c_full.py`: engine init shows KV reserve drop;
  generation is non-empty + needle-retrieval works; output cosine ≥
  0.995 vs stock (algorithm drift is the algorithm's drift, not
  bug-level).

**This is the GREEN state of Phase 5B.4** — memory savings + correct
output.

## Risks specific to 5B.4

1. **`reshape_and_cache_flash` rejects our smaller shape.** The C++ op
   has dtype + shape validation. Likely fails at 5B.4b's shape change.
   We'll need to bypass it entirely (Option A above), not just wrap.

2. **`flash_attn_varlen_func` reads paged cache.** If the attention
   call uses this op directly on the smaller-shape tensor, it'll
   misinterpret as bf16. Mitigation: skip it; use Phase 2.4.1b kernel
   instead.

3. **Block table interpretation.** vLLM's BlockManager uses block_tables
   to map per-sequence slots to physical blocks. Phase 2.4.1b kernel
   uses contiguous indexing. Either adapt the kernel to use block
   tables, or gather sequence's blocks to contiguous tensor per-step
   (slow but simple).

4. **MEMORY MEASUREMENT for the gate.** vLLM's engine init log line
   "the rest of the memory reserved for KV Cache is X GiB" is the
   ground-truth source. Our 5B.4b verify parses that.

5. **vLLM's auxiliary buffers may break.** Beyond the main paged cache,
   vLLM allocates auxiliary buffers (slot_mapping, block_table tensors,
   etc.) that might not handle our reshaped paged cache. Test
   incrementally.

## Estimated effort

- Probe + design lock (this commit): done.
- 5B.4a: ~1-2 days (forward source replication + verify).
- 5B.4b: ~1 day (shape + byte cost overrides + verify).
- 5B.4c: ~2-3 days (write/read replacement + correctness recovery + verify).

**Total: 4-6 engineer-days for Phase 5B.4 (matching the design doc's
2-3 day estimate for the "block-aware r/w path", split into clearer
sub-sub-phases).**

## Out of scope (deferred to 5C+)

- Per-block byte-cost optimization for V (still bf16 until Phase 2.6).
- Multi-batch correctness (Phase 5B.5).
- Quality re-acceptance with per-model mask (Phase 5B.5).
- First-class config polish (Phase 5C).
