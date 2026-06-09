# Hybrid bf16 / int4_protected KV — vLLM integration plan

> **Purpose.** Turn the cost-model decision (`hybrid_kv_scheduler.py`) into a serving
> change. **Read the decision gate first** — the measurement (`measure_int4_overhead.py`)
> determines *how much* of this you actually need to build. In the most likely regime,
> the answer is "almost nothing."

## 0. Decision gate — run the measurement BEFORE building anything

The cost model shows the bf16↔int4 crossover has two possible drivers, and which one
governs decides the whole architecture:

| if the measurement shows… | crossover is… | operative policy | build needed |
|---|---|---|---|
| per-slot staging **small** (<~4 MB/slot) — *the 6G-audit expectation* | **LOAD-driven** (`N*` total resident tokens) | **#6 load-switch** | **Tier 0** (config, no code) |
| per-slot staging **material** (tens of MB) | per-sequence (`L*` length) | **#4 per-seq routing** | Tier 2 (the fork) |

```bash
# pod, venv-vllm — pins per_token_frac, stage_per_slot_mb, fixed_tax_gb:
python Bench/scripts/measure_int4_overhead.py --run \
    --model Qwen/Qwen2.5-7B-Instruct --max-model-len 16384 --slots 8,64
# -> prints the regime ("LOAD-driven" / "PER-SEQUENCE-driven") and the scheduler flags
```

Everything below is an **engineering ladder**: stop at the lowest tier that meets your
workload. Do not build Tier 2 unless the measurement *and* a workload analysis justify it.

---

## Tier 0 — launch-time pool selection (NO code change) ✅ default recommendation

If the crossover is **load-driven** (expected), the hybrid collapses to a *per-deployment*
choice, not a runtime engine: **pick the cache dtype at launch from the service's load
profile.** The cost model gives the threshold.

- **Short-context / low-load service** (chat, autocomplete; resident KV below `N*`):
  launch **bf16**. int4_protected would only add the fixed tax with no density payoff.
- **Long-context / high-concurrency service** (RAG, agents, code; resident KV above `N*`):
  launch **int4_protected**. Past `N*` it's strictly denser (≈1.8×) and read-skip adds the
  long-context throughput win on top.

`N*` is concurrency-independent in tokens; from the model + measured flags:

```bash
python Bench/scripts/hybrid_kv_scheduler.py --crossover {measured flags}
python Bench/scripts/hybrid_kv_scheduler.py --workload <your-traffic> # confirms savings
```

**Why this is usually enough:** a given vLLM deployment already serves one workload class.
If it's uniformly above or below `N*`, a single launch-time dtype is optimal — and the
"never worse than bf16" guarantee is met by construction (you chose the smaller one). No
fork, no two pools, no per-request routing. **This is the honest first answer.**

---

## Tier 1 — admission router across two engine replicas (light, but double weights)

Only if a **single endpoint** must serve a genuinely **bimodal** mix (lots of tiny requests
*and* lots of long ones) and you can spare the memory: run a **bf16 replica** and an
**int4_protected replica** behind a router that sends each request to the cheaper engine
for the current load (the `total_*` policies in the cost model pick the target).

- **Pro:** zero changes to the vLLM fork — two stock engine instances + a thin router.
- **Con:** **two weight copies** (~14 GB × 2 for a 7B). The KV saving must beat the extra
  weights — only true on large GPUs or when the replicas sit on **separate GPUs** (then
  it's just normal fleet routing, and the cost model picks each box's dtype = Tier 0 per box).
- **Verdict:** rarely the right tier on a single GPU; it's really Tier 0 applied per-replica.

---

## Tier 2 — two paged pools in ONE engine, shared weights, per-sequence dispatch (the fork)

The real "mixed-dtype paged KV pool." Build this **only** if: single engine, single GPU,
a **bimodal** workload, **and** the measurement says per-sequence routing (#4) is material
(non-trivial per-slot staging) — i.e. you need to mix bf16 and int4 sequences concurrently
without paying double weights. It is weeks of fork work; the four insertion points in the
vLLM 0.7.3 V0 fork:

**(1) Cache allocation — two pools, one budget.** The backend already hooks `CacheConfig`
(see `phase5b_backend_install.py` "init-time selection via CacheConfig + get_attn_backend").
Extend `cache_engine` to allocate **two** block pools from the KV budget: a bf16 pool
(block bytes `b`) and an int4 pool (block bytes ≈ `b/4` + sidecars), with a **split ratio**
(start static, e.g. 50/50, tune later). `num_gpu_blocks` becomes a pair.

**(2) Block manager — pool tagging.** The block manager must track which pool each
sequence's blocks come from and free them back to the right pool. Add a `pool_id ∈ {bf16,
int4}` to the per-sequence block tables; keep two free-lists. Preemption/swap (we have
byte-clean swap-restore, TIER5A) must stay within a sequence's pool.

**(3) Attention dispatch — per-sequence backend.** Today `get_attn_backend` returns
`Int4ProtectedAttentionImpl` engine-wide. Make the impl **dispatch per sequence** on
`pool_id`: int4 sequences take the route-A int4 path (+ its `PagedKVWriter` slot, the
staging pool that #4 is sensitive to); bf16 sequences take stock FlashAttention. The
`forward` already branches on metadata — thread `pool_id` through `attn_metadata`.

**(4) Admission policy — the routing decision.** At schedule/admit time, pick a new
sequence's `pool_id`: route to int4 if its expected length > `L*` (and the int4 pool has
room), else bf16. Expected length can come from `max_tokens`, a prompt-length heuristic, or
a running per-route occupancy balance. This is the only *new policy* code; everything else
is plumbing. Mirror `hybrid_kv_scheduler.total_hybrid_guarded` so it can never do worse than
bf16 (fall back to bf16 if opening/feeding the int4 pool wouldn't pay).

### Tier 2 risks (and the gates that retire them)

| risk | why | gate |
|---|---|---|
| Block-size mismatch | int4 blocks ≠ bf16 block bytes; the manager assumes uniform | two free-lists + per-pool block bytes; unit test on alloc/free across pools |
| Scheduler assumptions | vLLM 0.7.3 V0 scheduler assumes one pool when computing `can_allocate` | per-pool budget checks; reuse the slot-lifecycle GC (`test_phase6k14_slot_gc`) |
| CUDA-graph capture | two attention paths under one captured graph | capture per pool, or run int4 path eager (read-skip already does); re-run `OPTION_B_PREFLIGHT` gates |
| Correctness regression | dual path must stay byte-equivalent on each side | the existing byte-eq suites (`verify_phase6e_fused_byte_eq`, 15/15) per pool |
| Split-ratio mis-set | static 50/50 wastes a pool under skewed load | start static; add occupancy-feedback resize only if measured to matter |

---

## Recommendation flow

```
run measure_int4_overhead.py
        │
        ├─ LOAD-driven (expected)  ─►  Tier 0: launch-time dtype per service.   STOP.
        │                              (build nothing; cost model sets the threshold)
        │
        └─ PER-SEQUENCE-driven  ─►  is the workload bimodal on one engine/GPU?
                                        ├─ no  ─►  Tier 0 still wins.  STOP.
                                        └─ yes ─►  Tier 2 fork (4 insertion points above),
                                                   gated on the risk table.
```

**Bottom line.** The cost model already delivers the user's goal ("never worse than bf16")
the moment the launch-time choice is informed by `N*` — that's Tier 0, no code. The
multi-week two-pool fork (Tier 2) is justified only by a measured per-sequence crossover
**and** a bimodal single-engine workload. The measurement is the cheap step that tells you
which, so run it before committing engineering.

## Pointers
- Cost model + policies: `hybrid_kv_scheduler.py` (`--crossover` shows `L*` and `N*`).
- Overhead measurement: `measure_int4_overhead.py` (`--run` on the pod).
- Backend hooks referenced: `KVPolicy/kv_policy/phase5b_backend_install.py`,
  `phase5b_4c_paged_writer.py` (slot pool), `int4_cache_kv_route_a.py` (int4 path),
  swap-restore `PHASE_TIER5A_SWAP_RESTORE_FINDINGS.md`, slot GC `test_phase6k14_slot_gc.py`.
