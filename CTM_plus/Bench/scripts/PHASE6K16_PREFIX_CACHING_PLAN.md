# Phase 6K.16 — prefix caching (APC) for int4_protected: feasibility + plan

> **Status: Tier 0 LANDED (guards + this plan). Tier 1 is pod work (GPU-validated).**
> Verdict up front: **the storage layer is already prefix-cache-compatible by
> construction** — the blocker is ONE attention path (prefill-with-context reads the
> int4-packed cache as bf16) plus a writer bookkeeping init. This is **days of
> Tier-1 work, not a redesign**, and the payoff compounds with int4's density:
> 2× the blocks at the same budget ⇒ the cache holds ~2× more prefix ⇒ higher hit
> rate, and every cache hit *skips prefill compute entirely* — the first lever in
> this project that REDUCES the throughput tax instead of paying it.

## Why the storage layer is APC-compatible by construction (the good news)

vLLM V0 APC shares **full, immutable blocks** between sequences by content hash;
the last partial block stays private. Three int4_protected design locks line up
with that exactly:

1. **Block-local quantization state.** `group_size == block_size == kInt4GroupSize
   == 32` (the 5B.4c lock). A *full* block is always a whole number of K quant
   groups (exactly one) — no cross-block scale coupling. A cached block's packed
   bytes are self-contained.
2. **Deterministic content.** Per-channel K scales are computed over the 32 tokens
   *inside the group/block*; V is per-token within the block. Same prefix tokens at
   the same positions ⇒ same K/V ⇒ **byte-identical packed block + sidecars** for
   every sequence that would share it. Sharing is sound.
3. **Sidecars are keyed by global `block_id`** (`k_scale_ext`/`k_xmin_ext`/
   `k_protect_ext`/`v_scale_ext`/`v_xmin_ext`, parallel to the block table). A
   shared block automatically carries its scales/xmin/protect with it — no
   per-sequence sidecar duplication, no migration. Eviction-then-reuse is also
   consistent: a reallocated block_id is a cache MISS, so the new owner re-prefills
   and the writer overwrites that block's sidecars before anything reads them.

## The actual gaps (what Tier 1 must build)

### Gap 1 — prefill-with-context attention (the guarded branch)
`phase5b_backend_install.py`, prefill branch with non-empty `block_tables`
(fires only under APC / chunked prefill): inherited code passes
`key_cache/value_cache` — **packed uint8 nibbles** — to `flash_attn_varlen_func`
as if bf16. Neither the vendored FA patches (decode-path `int4_packed_load_*`)
nor the Triton 6c kernel support varlen-prefill-over-packed.
**Now guarded:** raises `RuntimeError` unless `INT4_PROTECTED_ALLOW_PREFIX_CACHING=1`
(Phase 6K.16 Tier 0). NB the spec-decode varlen path has the same packed-cache
problem — spec decode is already unsupported; noting for completeness.

**Tier-1 fix (no kernel work): dequant-context prefill.**
For each prefill-with-context batch: gather the cached blocks via `block_table`
(the decode bridge's gather/dequant helpers already assemble contiguous bf16 K
from packed + protect-merge + staging — reuse them), build transient bf16 K/V for
[context ∥ new tokens], and call **plain** `flash_attn_varlen_func` (explicit K/V,
no `block_table=`) with `cu_seqlens_k` = context+query lengths.
Transient cost: `prefix_len · H_kv · D · 2B · 2(KV)` per seq ≈ **33 MB @ 8K /
134 MB @ 32K prefix (Llama-3.1-8B)** — prefill-batch-bounded, freed immediately.
Tier 2 (perf polish, only if the spike/latency matters): teach the vendored FA
varlen kernel to read packed int4 directly, like the decode reader.

### Gap 2 — writer SeqState init for cache-hit sequences
Today `ensure_seq_state` assumes a sequence streams from position 0. Under APC a
hit sequence's prefill feeds only the *suffix*; the writer must initialize
`s_curr = 32 · n_computed_blocks`. Because hits are **block-aligned = group-
aligned**, the staging buffer starts EMPTY (no partial group to reconstruct) —
this is the same alignment luck as Gap 1's reuse of full-block dequant. Plumbing:
the model runner exposes `computed_block_nums` in the seq-group metadata; thread
it (or just the cached-token count = context_len at first write) to the writer's
prefill-boundary init.

### Gap 3 — validation gates (pod, in order)
1. **Byte gate:** two sequences sharing a 4-block prefix → assert packed bytes +
   all five sidecars byte-equal on the shared blocks.
2. **Equivalence gate:** same batch with APC on vs off → greedy token agreement
   (expect = the no-APC run, i.e. ~1.0 prefix overlap; this is the same harness
   discipline as the KVarN head-to-head).
3. **Hard gate:** needle placed INSIDE the cached prefix at 8K/32K → retrieval
   must match the no-APC protected cell (0.955 / 1.000 on Llama).
4. **Hit-rate sanity:** `prefix_hit_probe.py` (Phase 3A — already built for vLLM
   0.7.3's `PrefixCachingBlockAllocator`) confirms hits actually occur and counts
   blocks; also reuse the evictor/pinning line's counters if needed.

## Why this is worth Tier-1 funding (the strategic case)

- **Hit-rate compounding:** int4 fits ~2× the blocks per GB ⇒ at a fixed budget
  the prefix pool retains ~2× more distinct prefixes before eviction. Density
  doesn't just add capacity — it multiplies APC's effectiveness. (The in-repo
  cache-aware-scheduler work already showed hit rate is the lever worth buying.)
- **It attacks the throughput weakness:** every hit skips prefill compute. For
  system-prompt / RAG / few-shot workloads (exactly the long-shared-prefix
  segment int4 targets), this is the first feature that makes int4_protected
  FASTER, not just denser.
- **Risk is low:** no CUDA changes in Tier 1; the dequant-context path reuses the
  existing, GPU-validated gather/dequant/protect-merge helpers.

## Out of scope (explicitly)

- **Chunked prefill** — different metadata shape through the same branch; revisit
  after APC lands (the guard covers it too, since it routes through the same
  prefix-enabled branch).
- **Spec-decode varlen** — same packed-cache issue, separate feature, unsupported.
- **V1-engine APC** — belongs to the eventual 0.7.3→V1 port, not this phase.

## Tier 0 (LANDED with this doc)

- Backend guard at the exact unsound branch (`RuntimeError`, env-bypassable):
  `phase5b_backend_install.py` prefix-enabled prefill.
- Factory guard at init: `Int4ProtectedLLM(enable_prefix_caching=True)` refused
  with the same message/escape hatch (`INT4_PROTECTED_ALLOW_PREFIX_CACHING=1`);
  default now passes an explicit `enable_prefix_caching=False` so engine logs are
  self-documenting.
- CPU tests: `tests/test_phase6k16_prefix_guard.py`.
