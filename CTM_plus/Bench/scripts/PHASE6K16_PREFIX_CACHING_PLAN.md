# Phase 6K.16 — prefix caching (APC) for int4_protected: feasibility + plan

> **Status: Tier 1 IMPLEMENTED (dequant-context prefill, CPU-verified) — pending the
> GPU gates below. Tier 0 (guards) LANDED earlier; the guard now gates an
> implemented path rather than a missing one.** Enable with
> `INT4_PROTECTED_ALLOW_PREFIX_CACHING=1` + `Int4ProtectedLLM(...,
> enable_prefix_caching=True)`; validate with
> `Bench/scripts/phase6k16_prefix_gates.py`; flip the factory default once all
> gates pass.
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

### Gap 2 — writer SeqState init: **COLLAPSED ON INSPECTION (no code needed)**
The plan originally scoped an `s_curr = 32·n_computed` offset init. Reading the
write path showed it is unnecessary: **every scatter is `slot_mapping`-derived**
(`block_ids = slots // BS`, `positions = slots % BS` — absolute, straight from
vLLM), so packed K/V, sidecars, protect, and staging land at correct absolute
positions for suffix-only prefills with no writer changes. The per-seq counters:
`k_stage_*` are block-keyed (correct, since cache-hit suffixes start
block-aligned); `seq_pos` is only consumed by the **legacy bf16 backing pool**
(suffix-relative indexing → WRONG under APC) — which is skipped by default since
Phase 6C. Accordingly the Tier-1 code **refuses APC when
`PHASE6C_BF16_BACKING_SKIP=0`** (`check_writer_apc_compatible`) instead of
patching SeqState. Less code, fewer regressions; the constraint is enforced, not
assumed.

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

## Tier 0 (LANDED)

- Backend guard at the exact unsound branch (`RuntimeError`, env-bypassable):
  `phase5b_backend_install.py` prefix-enabled prefill.
- Factory guard at init: `Int4ProtectedLLM(enable_prefix_caching=True)` refused
  with the same message/escape hatch (`INT4_PROTECTED_ALLOW_PREFIX_CACHING=1`);
  default now passes an explicit `enable_prefix_caching=False` so engine logs are
  self-documenting.
- CPU tests: `tests/test_phase6k16_prefix_guard.py`.

## Tier 1 (IMPLEMENTED — pending GPU gates)

- **`kv_policy/phase6k16_prefix_prefill.py`** — the dequant-context path:
  `gather_context_kv` (per-seq cached blocks → bf16 K/V; K per-channel-in-block
  dequant + **exact protect scatter-merge**; V per-token per-group dequant),
  `build_prefix_varlen_inputs` (interleave [ctx ∥ new] + `cu_seqlens_k`),
  `run_prefix_prefill` (orchestrator → plain `flash_attn_varlen_func`, explicit
  K/V, no `block_table=`), `check_writer_apc_compatible` (refuses legacy
  bf16-backing mode). CPU selftest: 13 checks incl. nibble round-trip exact,
  K within the principled bound (scale/2 + 15·|Δscale_bf16| + |Δxmin_bf16| +
  cast eps), **protect channels bit-exact**, V in-bound, interleave layout,
  alignment + backing rails. `python kv_policy/phase6k16_prefix_prefill.py`.
- **Branch wiring** — the stock varlen-over-packed call in
  `phase5b_backend_install.py`'s prefix branch is REPLACED by
  `run_prefix_prefill` (guard still fires without the env);
  `_call_stats["prefix_prefill_calls"]` counts invocations.
- **GPU gates** — `Bench/scripts/phase6k16_prefix_gates.py`:

```bash
# pod, venv-vllm; Llama mask already calibrated
M=NousResearch/Meta-Llama-3.1-8B-Instruct
export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
python Bench/scripts/phase6k16_prefix_gates.py --selftest                        # CPU
python Bench/scripts/phase6k16_prefix_gates.py --mode noapc --out /tmp/p6k16_noapc.json --model $M
python Bench/scripts/phase6k16_prefix_gates.py --mode apc   --out /tmp/p6k16_apc.json   --model $M
python Bench/scripts/phase6k16_prefix_gates.py --compare /tmp/p6k16_noapc.json /tmp/p6k16_apc.json
```

  - **GATE-HITS**: `cache_hit_blocks > 0` in the apc run (Phase 3A probe on the
    block manager) — proves the test actually exercised cache hits.
  - **GATE-AGREEMENT**: mean greedy token agreement apc-vs-noapc ≥ 0.90 over 6
    shared-prefix prompts. NOT expected to be 1.0: noapc prefill attends fresh
    bf16 context; apc attends dequant-int4 context — the gap is int4's prefill-
    attention quant error, the same magnitude class as protect-vs-bf16 (0.955).
  - **GATE-NEEDLE**: a code buried inside the CACHED prefix is retrieved under
    apc (and the noapc control) — the hard-tail check.
- **Flip criteria**: all three gates PASS → make `enable_prefix_caching=True`
  legal without the env (keep `False` as the default until a hit-rate +
  throughput win is measured); add an APC cell to the 6k12 hard-needle harness
  for the full-strength version of GATE-NEEDLE.

## First GPU run — FAILED (triage in progress; honest record)

First pod run (Llama-3.1-8B): **all three gates failed** — agreement 0.094,
needle apc=MISS with degenerate output ("old-old-old…"), probe
`cache_hit_blocks=0`. Read carefully, the evidence is internally inconsistent in
an informative way: NO exception fired (so if the prefix branch ran, ctx was
32-aligned and the writer present), outputs are garbage from token 1 (prefill
attention wrong), yet the allocator probe counted zero hits (either no hits —
then the apc engine corrupts WITHOUT our path — or the Phase 3A probe doesn't
count this allocator correctly).

**Instrumentation added for the decisive rerun** (one apc run localizes it):
1. `call_stats` in the gate payload — `prefix_prefill_calls` is the real
   "branch fired" signal; GATE-HITS now keys on it (probe demoted to info).
2. **Warm-call agreement** printed by `--compare` — warm has NO cached context
   in either mode, so divergence there means the APC engine/writer interaction
   is broken BEFORE any prefix-prefill involvement (bug NOT in the dequant path).
3. `INT4_PROTECTED_PREFIX_DEBUG=1` — per-hit-seq prints inside
   `run_prefix_prefill`: ctx lens, block ids, **`k_scale` stats of the first
   context block** (mean ~1e-8 ⇒ blocks never finalized by the writer ⇒ cache
   content is not what we assume), dequant norms, `cu_seqlens`.

Decision tree for the rerun:
- `prefix_prefill_calls == 0` **and** warm diverges → APC-allocator × writer
  interaction bug (block-id churn / dedup vs SeqState); prefix path exonerated.
- branch fired, `k_scale ≈ 1e-8` → context blocks unfinalized → write-path /
  hash-alignment investigation (which blocks does APC consider computed vs
  which did the writer finalize).
- branch fired, scales sane, norms sane → the varlen call itself (layout /
  causal alignment) — next probe: replace `causal=True` semantics check with a
  1-seq micro-test comparing against the no-cache branch on the same tokens.
