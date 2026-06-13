# KVPro Snapshot Round-Trip — Pod Runbook (Phase-0 gate)

Proves `kv_policy.tier5b_snapshot` (snapshot/restore of int4_protected KV) is **byte-faithful on
real hardware**, on KV produced by `Qwen/Qwen2.5-7B-Instruct`. This is the gate the warm-tier
protocol (`docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md` §Phase 0) requires **before** any CacheGen
comparison and before wiring `cachegen_warmtier_eval roundtrip --backend kvpro`.

Script: `scripts/verify_kvpro_snapshot_roundtrip.py` (fails loudly if the live writer / kv_cache /
written blocks can't be obtained — it never fakes tensors).

## Prerequisites (on the RunPod A100/H100 pod)
- The pod that already runs int4_protected: `vllm` (0.7.3 V0 fork), the `int4_protected_C` CUDA
  extension built, and `torch` with CUDA.
- The repo checked out; `kv_policy` importable. The script auto-adds `CTM_plus/KVPolicy` to
  `sys.path` when run from the repo root.
- The **calibrated protect mask** for Qwen2.5-7B present (this is the usual gotcha).

## Required env vars
| var | value | why |
|---|---|---|
| `PROTECT_MASK_PATH` | path to `qwen2_5_7b_protect_mask_4pct.pt` | Int4ProtectedLLM needs the calibrated mask; default is `/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt` |
| `INT4_PROTECTED_DUMP_BLOCKS` | e.g. `/tmp/kvpro_native_dump.pt` | arms the writer's **native** block dump as corroboration that the int4 write path fired (the script sets this by default if unset) |
| `INT4_PROTECTED_PROT_INT8` | `1` *(optional)* | also exercise the prot-int8 protect format; the round-trip must still be byte-clean (quantize∘dequant is identity on the code lattice) |
| `HF_TOKEN` / `HF_HUB_ENABLE_HF_TRANSFER` | as usual | model download |

## Exact command
```bash
cd /workspace/symbolu                       # repo root
git checkout claude/nand-llm-decode-optimization-kl74bm && git pull

export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
export INT4_PROTECTED_DUMP_BLOCKS=/tmp/kvpro_native_dump.pt

python scripts/verify_kvpro_snapshot_roundtrip.py \
    --model Qwen/Qwen2.5-7B-Instruct \
    --max-model-len 1024 \
    --n-blocks 8 \
    --snapshot-path /tmp/kvpro_prefix_snapshot.pt
```
Optional second run to cover the int8 protect format:
```bash
INT4_PROTECTED_PROT_INT8=1 python scripts/verify_kvpro_snapshot_roundtrip.py --n-blocks 8
```

## Expected PASS output (shape)
```
[1/6] building Int4ProtectedLLM(model=Qwen/Qwen2.5-7B-Instruct, max_model_len=1024) ...
[2/6] short prefill+decode (max_tokens=8) to populate KV ...
      generated: '...'
[ok] native writer dump produced at /tmp/kvpro_native_dump.pt (write path confirmed firing)
[3/6] acquiring live writer + paged kv_cache ...
[ok] paired layer '...self_attn.attn': NB=... BS=32 H=... D=128 n_protect=5 prot_int8=False
[ok] round-tripping 8 written block_ids: [...]
[4/6] DISK round-trip: save -> zero -> load -> restore_prefix (/tmp/kvpro_prefix_snapshot.pt) ...
      saved 8 blocks, NNNNN bytes (NNNN B/block)
[5/6] in-memory verify_roundtrip (built-in byte-gate) ...

================ RESULT ================
DISK   save/load/restore_prefix : PASS
MEMORY verify_roundtrip         : PASS
per-tensor (memory): {'packed_k': True, 'packed_v': True, 'k_scale': True, 'k_xmin': True, 'k_protect': True, 'v_scale': True, 'v_xmin': True}

PASS — KVPro snapshot/restore is byte-faithful on this writer; Phase-0 gate cleared.
========================================
```
Exit code `0` on PASS, `1` on a byte-mismatch FAIL, `2` on a loud acquisition failure.

## Expected failure modes (and what each means)
| Symptom | Meaning / fix |
|---|---|
| `[FAIL] torch not importable` (exit 2) | not on a GPU pod — run on the int4_protected pod, not a CPU box. |
| `Int4ProtectedLLM construction failed ... protect mask is missing` (exit 2) | set `PROTECT_MASK_PATH` or run Phase 5B.0 calibration. |
| `no int4_protected writer found on any attention layer` (exit 2) | the model isn't on the int4 backend — `int4_protected_C` didn't build/import, or `kv_cache_dtype` isn't `int4_protected`. Check the build. |
| `writer/kv_cache geometry mismatch` (exit 2) | layer pairing is off for this vLLM version — paste the printed shapes; the `_pair_writer_kv` order assumption needs adjusting. |
| `no written blocks found (all k_scale_ext zero)` (exit 2) | prefill didn't write through the int4 path — increase `--prompt` length / `--max-model-len`, confirm the write path. |
| `DISK ... FAIL` / `verify_roundtrip FAIL` (exit 1) | a real byte-mismatch — the per-(block, tensor, shape, max_abs_diff) lines name exactly which tensor diverged. **Do NOT proceed to the CacheGen comparison.** |
| `could not reach the model (no driver_worker.model_runner.model)` (exit 2) | vLLM internals moved — paste `type(llm.llm_engine.model_executor)` and `dir(driver_worker)`. |

## What to paste back
1. The **full stdout** from `[1/6]` through the `==== RESULT ====` block (or the `[FAIL] ...` line + exit code).
2. If FAIL on bytes: the **per-tensor mismatch lines** (block_id, tensor, shape, max_abs_diff).
3. `nvidia-smi | head -20` and the vLLM startup banner (engine version, `kv_cache_dtype`, block_size).
4. Whether `/tmp/kvpro_native_dump.pt` was produced (the `[ok] native writer dump ...` line).
5. The `[ok] paired layer ...` line (NB/BS/H/D/n_protect/prot_int8) — confirms the writer geometry.

## After PASS
Only then wire the warm-tier backend: implement `kvpro_snapshot_backend`'s live-engine glue
(get a prefix's writer+kv_cache+block_ids; allocate fresh blocks; `restore_prefix` into them) and
flip `cachegen_warmtier_eval roundtrip --backend kvpro` on. **Do not wire it before this passes.**
