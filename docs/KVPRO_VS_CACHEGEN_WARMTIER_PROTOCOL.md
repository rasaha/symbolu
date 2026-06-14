# KVPro vs CacheGen — Warm-Tier KV Reuse Head-to-Head (Pre-Registered Protocol)

**Status:** experiment design (pre-registration). **Prereq:** GPU pod + LMCache + vLLM + KVPro backend.
**Companion:** `docs/SAW_INT4_QWEN_HEADTOHEAD_RESULTS.md` (the hot-tier head-to-head), `INT4_PROTECTED_VC_BRIEF.md`
§"Why hierarchical KV memory is the market" (the PROJECTED warm-tier pillar this protocol validates or kills).

> **The one decision this resolves:** in the vLLM/LMCache hierarchical-KV stack, is KVPro a *reliability
> layer* worth its bytes — does it preserve hard long-context retrieval through store→offload→reload→reuse
> where the incumbent (CacheGen) does not — or is CacheGen good-enough/smaller/native, leaving KVPro with
> no warm-tier role? Go in expecting it **may have no warm-tier role**; the protocol is designed to find
> the truth, not defend the pillar.

## Why CacheGen and not another competitor
- CacheGen is **LMCache's own** KV→bitstream codec, built for the exact job the brief's forward thesis
  claims (offload + reuse across CPU/NVMe). It is the **incumbent sitting in the seat KVPro wants**, inside
  the stack we cite as our integration edge. SAW was a *hot-tier decode* codec; CacheGen is a *storage/
  transport* codec — the on-thesis comparator.
- It answers the predictable due-diligence question ("LMCache already offloads + compresses KV — what does
  KVPro add?") with a measured number instead of a projection.

## Scope decision (make this on purpose before running)
Running this commits to positioning KVPro as a **storage/transport codec**, not only a decode codec.
CacheGen and KVPro were built for different jobs; the comparison only means something if KVPro is competing
for the warm-tier job at all. **Decision: [ YES / NO ] — record before Phase 0.**

## Competitor (has public code — measure, don't cite)
- **CacheGen** — `github.com/LMCache/LMCache` (paper: CacheGen, KV-cache compression + streaming for LLM
  serving, arXiv 2310.07240). Custom per-layer/per-channel quantization + arithmetic-coded bitstream tuned
  for **transport**; **configurable quality↔size knob** (multiple compression levels) and tolerates small
  accuracy loss for large size/bandwidth wins. **Verify provenance from the repo on the pod** (commit,
  submodules, default level) and record it, exactly as the SAW results doc does.

## Phase 0 — FEASIBILITY GATE (new vs the SAW protocol; run FIRST)
KVPro's reconstruction sidecars (`k_scale/xmin`, `v_scale/xmin`, `k_protect`, staging) live **outside**
vLLM's paged KV tensor — which is precisely why swap-preemption is hard-refused (6K.15: a migrated KV
without its sidecars is silently corrupt).

> **The serialize/restore primitive is implemented AND hardware-verified:** `kv_policy/tier5b_snapshot.py`
> (`save_prefix_snapshot` / `load_prefix_snapshot` / `restore_prefix` + a built-in `verify_roundtrip`
> byte-gate). It re-injects packed K/V + all 5 sidecars into a fresh paged allocation and re-encodes
> protect via the writer's `_protect_store` (byte-clean under prot-int8: quantize∘dequant is identity
> on the code lattice).
> **✅ Phase-0 PASSED (MEASURED 2026-06-14, Qwen2.5-7B-Instruct, A100-80GB):** DISK + in-memory
> round-trips byte-clean across all 7 tensors (8 blocks @ 21,760 B/block) — see
> `docs/KVPRO_SNAPSHOT_ROUNDTRIP_POD_RUNBOOK.md`. The remaining work is only the live-engine wiring
> (getting a prefix's writer + kv_cache + block_ids, and a fresh allocation to restore into).

So before any measurement:

1. **Can KVPro state be serialized + faithfully reloaded through an offload path?** TIER5A already proved
   byte-clean **CPU swap-restore** (matched-pressure swap vs recompute → bit-identical 64-token output).
   Extend that to a **disk/NVMe snapshot**: dump packed KV + all 5 sidecars to safetensors, free, reload,
   continue generation; gate on **bit-identical** continuation (reuse the TIER5A acceptance gates).
2. **Does KVPro plug into LMCache's connector, or must it use its own snapshot path?** Likely the latter
   at first (LMCache moves the paged tensor; KVPro's sidecars don't travel through its connector
   un-extended). **Record which.** If KVPro rides its own snapshot path and CacheGen rides LMCache, the
   comparison is **codec-to-codec on the systems axis** with a flagged transport-implementation asymmetry —
   acceptable, but stated.

**Phase-0 outcomes:** PASS (KVPro serialize/reload is byte-clean → proceed) · **INTEGRATION-BLOCKED**
(cannot faithfully round-trip KVPro state → record as a durable negative; the warm-tier pillar is blocked
on engineering, not measured down).

## Fairness rules (or the comparison is meaningless)
1. **Same models:** Qwen2.5-7B-Instruct first (where SAW collapsed and KVPro/bf16 hold), then a second
   (Mistral-7B-v0.3 or Llama-3.1-8B).
2. **Same prefixes, same hardware, same eval harness.** Reuse the needle/hard-needle/greedy client
   (`ndol.experiments.openai_kv_eval`) for the quality sanity check; reuse the TIER5A gates for byte-clean.
3. **Match on BYTES — the cardinal rule.** Codec comparisons are meaningless unless byte-matched: sweep
   CacheGen's compression level to KVPro's measured **~1.8×** AND report each at its own **default** level.
   Report **measured** bytes/token incl. *every* overhead (sidecars / bitstream headers / index / padding),
   never paper ratios.
4. **Same offload medium** (CPU DRAM and NVMe, separately) and **same concurrency** for the latency runs.

## Workload — warm-tier reuse (the production motion)
```
prefill a long shared prefix ONCE  →  compress (KVPro | CacheGen)  →  store (CPU DRAM | NVMe)
   →  evict from HBM  →  later: reload + reattach  →  continue generation / answer query
```
Drive it with: a large document/session prefix (8K / 16K / 32K) carrying planted needles, then N follow-up
queries that reuse the warm prefix (RAG / multi-turn / agent-memory shape). Compare against a **cold
recompute** baseline (no reuse) to size the TTFT win each codec actually delivers.

## Metrics — SYSTEMS first, quality as a sanity check
| axis | metric | why |
|---|---|---|
| **size** | measured bytes/token stored (all overhead) | $/GB of warm KV; iso-byte anchor |
| **reload** | encode time + decode/transfer time per 1K tokens | the TTFT-relevant cost |
| **TTFT** | TTFT with warm reuse **vs cold recompute** | the headline economic win |
| **transfer** | PCIe + NVMe bytes per reused context | the transport-bound bottleneck |
| **tail** | p95 / p99 TTFT under **concurrent** reuse | the latency-cliff guard |
| **cost** | derived $/reused-long-context-query | the buyer's number |
| **quality (SANITY)** | hard-needle + greedy after store→reload→reuse, vs the no-reuse baseline | guards storage-path bugs; see note |

> **Note (why quality is a sanity check, not the headline):** for a **fixed** codec, store→reload is byte
> round-tripping — quality after reload ≈ quality without it (already covered by the hot-tier needle
> results, since the needle lives in the reused prefix). The quality column mainly catches dtype / chunking
> / partial-load corruption. **The real contest is bytes × reload-time × tail-retention AT ISO-BYTES** —
> i.e. when CacheGen is squeezed to KVPro's byte budget, does *its* hard tail survive?

## Pre-registered decision rule
1. **RELIABILITY-EDGE → the warm-tier pillar is real.** At **iso-bytes** (CacheGen tuned to ~1.8×), KVPro
   preserves hard-needle after reuse while CacheGen drops it by **≥5 pts** (or shows a tail cliff KVPro
   doesn't), at comparable reload time → claim **tail-safe warm-tier reuse**, state the byte/throughput
   trade honestly.
2. **DOMINATED → drop the warm-tier pillar.** If CacheGen matches KVPro hard-tail quality (within 2 pts)
   **at ≤ bytes and ≤ reload time** → KVPro has no warm-tier role; keep it a hot-tier decode codec and
   remove the reliability-layer claim from the brief (record as a durable negative, like TurboQuant).
3. **PARITY/MIXED → differentiate on integration, not the codec.** Comparable → lean on vLLM-native
   posture + the hot-tier QUALITY-EDGE, not warm-tier codec superiority.
4. **INTEGRATION-BLOCKED (from Phase 0)** → the pillar is blocked on engineering; say so, scope the work.

## Wiring (on the GPU pod)
- Install LMCache + enable CacheGen (`github.com/LMCache/LMCache`); confirm vLLM offload to CPU + NVMe works
  on the base model (bf16) first — record commit + default level.
- **CacheGen arm:** run the reuse workload through LMCache with CacheGen at {default, iso-1.8×, and 1–2
  higher-loss levels}; capture all metrics above.
- **KVPro arm:** per Phase 0 — either through LMCache's connector (if it plugs in) or via KVPro's own
  snapshot/restore (TIER5A disk extension). Same workload, same metrics.
- Feed measured bytes/token back into `ndol/sim/kv_method_memory.py` (add a `CacheGen` entry) to replace
  any analytical estimate, same discipline as the SAW row.

## Honest framing / caveats
- **CacheGen quality is a knob, not a point** — sweep its compression levels; never cite one number.
- **Transport asymmetry** (KVPro snapshot vs CacheGen-in-LMCache) must be stated if Phase 0 forces it;
  it makes the *systems* numbers codec+transport, not codec-only — disclose, don't hide.
- **This validates or kills the brief's forward pillar** — unlike SAW-breadth (which only strengthens a
  banked result) — so run it deliberately, and record DOMINATED just as loudly as RELIABILITY-EDGE.

## What "done" looks like
A byte-matched table of `{stored bytes/token, reload time, TTFT-vs-cold, transfer volume, p95/p99,
quality-after-reuse}` for **bf16 / CacheGen(×levels) / KVPro** on ≥1 model (then a second), at CPU and NVMe
tiers, and a verdict mapped to rule 1/2/3/INTEGRATION-BLOCKED. If DOMINATED, the brief's warm-tier section
gets cut to an honest "CacheGen owns this; KVPro is a hot-tier codec" — do not defend the pillar.
