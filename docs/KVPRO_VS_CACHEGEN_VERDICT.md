# KVPro vs CacheGen — Verdict (DIRECTIONAL, mechanism-grounded)

**Status: DIRECTIONAL VERDICT (2026-06-14).** Grounded in (a) CacheGen's *actual* mechanism read from
its shipped config, (b) three prior MEASURED head-to-heads against structurally-identical codecs, and
(c) KVPro's MEASURED lossless warm-reuse + footprint. **Not yet an end-to-end CacheGen run** — that is
blocked on this pod by an environment wall (below) and needs Option A. Companion:
`docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md`, `docs/KVPRO_SNAPSHOT_ROUNDTRIP_POD_RUNBOOK.md`.

## What CacheGen actually is (verified from lmcache 0.4.7 on the pod)
`lmcache/v1/storage_backend/naive_serde/cachegen_{encoder,decoder,basics}.py`. `CacheGenConfig` =
**per-layer-range quantization to `bins` levels** + **arithmetic coding**. The shipped 7B/8B presets:
- K: `bins=32` (layers 0–10), `bins=16` (10–32); V: `bins=32` (0–2), `bins=16` (2–32).
- `bins=16` ≈ 4 bits, `bins=32` ≈ 5 bits; arithmetic coding then compresses below nominal.
- **No channel protection** — uniform per-layer bins. **Lossy by construction.**

So CacheGen ≈ **dense, unprotected ~4–5-bit KV quant + entropy coding**, with coarse per-layer bin
tuning as its only sensitivity heuristic.

## Side-by-side
| axis | KVPro (int4_protected) | CacheGen |
|---|---|---|
| base | 4-bit + per-channel scales | ~4–5-bit (16–32 bins) + arithmetic coding |
| **high-magnitude K channels** | **protected at bf16 (4%)** | **none — uniform per-layer** |
| reuse fidelity | **lossless restore (MEASURED byte-exact, 8 prefixes, both protect formats)** | lossy (bins quant) |
| density | 1.8× vs bf16 (pays a sidecar tax) | **denser** (entropy-coded, no sidecars) |
| footprint (measured) | ~6 KB/token full-model snapshot (conservative, torch.save-bound) | not measured here |

## Verdict
CacheGen is **structurally the same class** as the three competitors already MEASURED to lose the hard
tail, for the same reason (dense + unprotected):
- **naive int4** — token-agreement vs bf16 collapsed to 0.533; K-bound hard-needle misses.
- **SAW-INT4 (BDR)** — **0% needle/hard-needle on Qwen2.5-7B-Instruct** (`SAW_INT4_QWEN_HEADTOHEAD_RESULTS.md`).
- **KVarN** — hard-needle **0.25 (8K) → 0.06 (32K)**, K-bound (VC brief Page 4).

All three were denser than int4_protected and dropped long-range / hard-tail retrieval exactly where
int4_protected's **protected channels** hold. CacheGen has **no channel-level protection** — the precise
moat — so it is expected to follow the same pattern. Its per-layer bin tuning is a *mild* mitigation,
not channel protection.

**Directional verdict (mechanism + 3 measured analogues + KVPro lossless reuse):**
- **CacheGen wins raw density** (entropy-coded, no sidecar tax).
- **KVPro wins the hard tail at iso-bytes** — its design target — and uniquely offers **lossless warm
  reuse** (proven byte-exact), so its reuse quality = its validated near-bf16 quality, *guaranteed*.
- Maps to the protocol's **QUALITY-EDGE** branch (KVPro holds the tail cheap unprotected quant misses),
  **pending end-to-end confirmation**.

## What is NOT yet measured (the confirming number)
- CacheGen's **measured bytes/token** on our prefixes, swept over `bins`.
- CacheGen's **hard-needle quality at the bins level whose bytes match KVPro** (the iso-bytes crossover).
- KVPro serving TTFT (needs the int4 decode FA fork).
Until these run, the verdict is directional, not a measured DOMINATED/QUALITY-EDGE stamp.

## Environment wall (why the end-to-end run is blocked here) + the A-path
- `pip install lmcache==0.4.7` pulls **vLLM 0.23.0**, whose torch is **2.11.0+cu130** (needs NVIDIA
  driver ≥13.0). This pod's driver is **12.8** → vLLM EngineCore fails at `torch._C._cuda_init()`. The
  CacheGen *server* cannot run here. (It also perturbed the base env — torchaudio cu124 vs torch cu121 —
  fixed by reinstalling `torchaudio==2.5.1+cu121`; **install lmcache only in an isolated venv**.)
- The standalone-serde path (encode/decode KV on CPU) is possible but needs constructing lmcache's
  internal `LMCacheEngineConfig` + `LMCacheMetadata` + `MemoryObj` in CacheGen's exact KV layout —
  deep, untestable internal-API work; **not recommended** as the next step.
- **Option A (recommended for the hard number):** a pod with driver ≥13.0 (or vLLM/torch matched to the
  driver). There the LMCache+CacheGen server + the arms in `ndol/experiments/cachegen_warmtier_eval.py`
  run directly — real bytes + hard-needle + TTFT, no internal-API guessing. Then map to the decision rule.

## Bottom line
On the evidence we have, **KVPro is the quality-safe choice and CacheGen the denser-but-lossy one**, and
the decider (does CacheGen's loss break the hard tail at iso-bytes?) points — by mechanism and by three
measured analogues — to **KVPro holding the tail where CacheGen would not.** A newer-driver pod converts
this directional verdict into a measured one.
