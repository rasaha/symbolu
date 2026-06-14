# CacheGen (LMCache) Setup + Level Sweep — Pod Runbook

**Goal:** get the ONE missing input to answer "is KVPro better than CacheGen" — CacheGen's
**measured bytes/token and hard-tail quality** on `Qwen/Qwen2.5-7B-Instruct`, across its
compression levels. We already have the KVPro side:
- KVPro warm-reuse quality = near-bf16, **proven lossless on reuse** (Phase-0: restore is byte-identical
  to resident KV — see `KVPRO_SNAPSHOT_ROUNDTRIP_POD_RUNBOOK.md`).
- KVPro snapshot footprint ≈ ~6 KB/token full-model (measured, conservative).

So the verdict reduces to: **at the CacheGen level whose bytes match KVPro's, does CacheGen still hold
the hard tail?** (RELIABILITY-EDGE if KVPro holds where CacheGen drops; DOMINATED if CacheGen matches
quality at ≤ bytes.) Decision rule: `docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md`.

> ⚠️ **Version-verify.** LMCache moves fast and exact flags differ by version (V0 vs V1 connector, env
> names, CacheGen config keys). The shapes below are canonical; confirm each against the installed
> version's docs (https://docs.lmcache.ai) before trusting. Treat this as a starting recipe, not a
> guaranteed copy-paste — same "measure, don't cite" discipline as the SAW protocol.

## 0. Prereqs
```bash
pip install lmcache                       # record the version: python -c "import lmcache; print(lmcache.__version__)"
mkdir -p /nvme/lmcache                    # local-disk (NVMe) backend dir
```

## 1. Launch vLLM + LMCache with CacheGen (server on :8100)
LMCache plugs into vLLM via the KV-transfer connector + an LMCache config file. CacheGen is the
compression codec selected in that config.

`lmcache_cachegen.yaml` (canonical — verify keys against your version):
```yaml
chunk_size: 256
local_device: "disk"           # offload KV to disk/NVMe
local_disk: "/nvme/lmcache"
max_local_disk_size: 50        # GB
# --- CacheGen compression ---
enable_cachegen: true
cachegen_config:
  # the quality<->size knob to SWEEP (name is version-specific; common forms below)
  # e.g. quantization bins / cdf bits per channel. Higher compression = fewer bytes, more loss.
  compression_level: "default"    # sweep: e.g. low / default / high  (or a numeric bit budget)
```
Launch (V0; the connector class name is version-specific — verify):
```bash
LMCACHE_CONFIG_FILE=$PWD/lmcache_cachegen.yaml \
LMCACHE_USE_EXPERIMENTAL=True \
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct --port 8100 --max-model-len 8192 \
    --kv-transfer-config '{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}'
# wait for the server to report ready
```

## 2. Smoke test (de-risk before the sweep, like we did for SAW)
Confirm reuse actually engages: send the SAME long prefix twice; the 2nd request should hit the
CacheGen cache (lower TTFT) and `/nvme/lmcache` should grow.
```bash
curl -s http://127.0.0.1:8100/v1/models | head        # server up?
du -sb /nvme/lmcache                                    # note size BEFORE
# fire a long-prefix request twice (any client); then:
du -sb /nvme/lmcache                                    # size grew => KV offloaded to disk
```
If the disk dir doesn't grow, CacheGen/offload isn't engaging — fix the config before measuring
(otherwise bytes/quality are meaningless).

## 3. Sweep CacheGen levels + a bf16 reference (using the existing client)
For EACH compression level (restart the server with that level in the yaml), run the warm-tier arm.
Replace `LVL` with the level name/value (e.g. `low`, `default`, `high`):
```bash
cd /workspace/symbolu
python -m ndol.experiments.cachegen_warmtier_eval run --backend cachegen --arm cachegen_LVL \
    --opt base_url=http://127.0.0.1:8100/v1 --opt model=Qwen/Qwen2.5-7B-Instruct \
    --opt disk_dir=/nvme/lmcache --out cg_LVL.json
```
Also a bf16 reference (plain vLLM, no LMCache, on :8000) for the quality ceiling:
```bash
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct --port 8000 --max-model-len 8192 &
python -m ndol.experiments.cachegen_warmtier_eval run --backend bf16 --arm bf16 \
    --opt base_url=http://127.0.0.1:8000/v1 --opt model=Qwen/Qwen2.5-7B-Instruct --out bf16.json
```
Each run prints `bytes/tok needle hard ttft_p99` and writes the json.

## 4. The verdict
Compare the CacheGen levels to KVPro's measured point:
```bash
python -m ndol.experiments.cachegen_warmtier_eval compare --arms bf16.json,cg_low.json,cg_default.json,cg_high.json
```
Then read off against KVPro:
- **KVPro point:** bytes ≈ ~6 KB/token (full-model snapshot), hard-needle = near-bf16 (lossless reuse).
- Find the CacheGen level whose **bytes/token ≈ KVPro's** (iso-bytes).
  - If at that level CacheGen's **hard-needle drops ≥5 pts below bf16** while KVPro holds → **RELIABILITY-EDGE (KVPro wins the tail).**
  - If CacheGen **matches bf16 hard-needle at ≤ KVPro's bytes** → **DOMINATED (CacheGen wins as a pure storage codec).**
  - Mixed → **PARITY**, differentiate on integration / lossless-guarantee.

> **Note on the KVPro bytes number:** the current ~6 KB/token is `torch.save`-bound and single-layer-extrapolated.
> For a fair iso-bytes comparison, first refine it with an all-layer + safetensors snapshot (faster
> serializer) so KVPro's footprint is production-representative, not pickle-inflated.

## What this resolves (and doesn't)
- **Resolves:** quality-at-iso-bytes — the decider. Does NOT need the KVPro decode FA fork (KVPro warm
  quality is already proven = hot = near-bf16).
- **Still open:** KVPro serving TTFT (needs the decode fork + scheduler injection) — secondary per the
  protocol. CacheGen TTFT IS captured here (its serving path works on stock vLLM).

## What to paste back
1. LMCache version + whether the smoke test grew `/nvme/lmcache` (reuse engaged Y/N).
2. The `compare` table (bytes/tok, needle, hard per level) + bf16 row.
3. Which CacheGen level matched KVPro's bytes, and its hard-needle vs bf16.
