#!/usr/bin/env python3
"""Phase-0 verification: KVPro snapshot/restore round-trip on a REAL writer + kv_cache.

Proves `kv_policy.tier5b_snapshot` is byte-faithful on hardware, on KV produced by
Qwen/Qwen2.5-7B-Instruct through the int4_protected backend. This is the gate the
warm-tier protocol (docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md §Phase 0) requires
BEFORE any CacheGen comparison or any `cachegen_warmtier_eval --backend kvpro` wiring.

It does NOT fake anything: if the live writer / kv_cache / written block_ids cannot be
obtained, it exits non-zero with a diagnostic. No mock tensors under this name.

Flow:
  1. build Int4ProtectedLLM(Qwen2.5-7B) (INT4_PROTECTED_DUMP_BLOCKS armed as corroboration)
  2. short prefill+decode to populate the KV cache
  3. acquire the first int4_protected layer's live writer + its paged kv_cache, paired and
     geometry-checked (writer.NB/BS/D == kv_cache dims)
  4. block_ids = blocks the writer actually wrote (non-zero k_scale_ext)
  5. DISK round-trip via the real serializer: save_prefix_snapshot -> zero -> load ->
     restore_prefix -> byte-compare to the pre-zero reference
  6. the built-in in-memory verify_roundtrip as the canonical gate
  7. print PASS/FAIL with exact per-(block,tensor) mismatch + max-abs-diff
"""
from __future__ import annotations

import argparse
import os
import sys

# Make `kv_policy` importable when run from the repo root (CTM_plus/KVPolicy on path).
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KVPOLICY_ROOT = os.path.join(_REPO, "CTM_plus", "KVPolicy")
if os.path.isdir(_KVPOLICY_ROOT) and _KVPOLICY_ROOT not in sys.path:
    sys.path.insert(0, _KVPOLICY_ROOT)


def _die(msg: str, code: int = 2) -> "None":
    print(f"\n[FAIL] {msg}", file=sys.stderr)
    sys.exit(code)


def _get_model(llm):
    worker = llm.llm_engine.model_executor.driver_worker
    mr = getattr(worker, "model_runner", None)
    model = getattr(mr, "model", None) if mr is not None else getattr(worker, "model", None)
    if model is None:
        _die("could not reach the model (no driver_worker.model_runner.model). "
             "vLLM internal layout differs — inspect llm.llm_engine.model_executor.")
    return worker, model


def _get_gpu_cache(worker):
    ce_list = getattr(worker, "cache_engine", None)
    if not ce_list:
        _die("worker.cache_engine is empty/None — the engine did not allocate a KV cache.")
    gpu_cache = getattr(ce_list[0], "gpu_cache", None)
    if not gpu_cache:
        _die("cache_engine[0].gpu_cache is empty/None.")
    return gpu_cache


def _int4_writers(model):
    """[(layer_name, writer)] for every attention layer carrying an int4_protected writer."""
    out = []
    for name, mod in model.named_modules():
        impl = getattr(mod, "impl", None)
        writer = getattr(impl, "_phase5b_paged_writer", None) if impl is not None else None
        if writer is not None:
            out.append((name, writer))
    return out


def _pair_writer_kv(model, gpu_cache):
    """First int4_protected layer's (writer, kv_cache), paired by layer order and
    validated against the kv_cache geometry. Fails loudly on any mismatch."""
    writers = _int4_writers(model)
    if not writers:
        _die("no int4_protected writer found on any attention layer "
             "(impl._phase5b_paged_writer is None everywhere). The model is NOT running the "
             "int4_protected backend — check kv_cache_dtype='int4_protected' and that the "
             "backend installed (Int4ProtectedLLM). Did the build/import of int4_protected_C fail?")
    if len(writers) != len(gpu_cache):
        print(f"[warn] {len(writers)} int4 writers but {len(gpu_cache)} gpu_cache tensors — "
              "using layer 0 and validating geometry.")
    name, writer = writers[0]
    kv = gpu_cache[0]
    # geometry pairing check: kv_cache is [2, NB, BS, H, D]
    try:
        shp = tuple(kv.shape)
        nb, bs, h, d = shp[1], shp[2], shp[3], shp[4]
    except Exception as e:  # noqa: BLE001
        _die(f"unexpected kv_cache shape {getattr(kv, 'shape', '?')}: {e}")
    if (int(writer.NB), int(writer.BS), int(writer.D)) != (int(nb), int(bs), int(d)):
        _die(f"writer/kv_cache geometry mismatch on layer '{name}': "
             f"writer(NB={writer.NB},BS={writer.BS},D={writer.D}) vs "
             f"kv_cache(NB={nb},BS={bs},D={d}) — wrong layer pairing, refusing.")
    print(f"[ok] paired layer '{name}': NB={nb} BS={bs} H={h} D={d} "
          f"n_protect={writer.n_protect} prot_int8={getattr(writer, '_prot_int8_active', False)}")
    return writer, kv


def _written_block_ids(writer, n_blocks):
    """Blocks the writer actually populated = non-zero k_scale_ext (zero-initialized)."""
    import torch
    ks = writer.k_scale_ext                      # (NB, H, D)
    per_block = ks.detach().abs().reshape(ks.shape[0], -1).sum(dim=1)
    nz = torch.nonzero(per_block > 0, as_tuple=True)[0].tolist()
    if not nz:
        _die("no written blocks found (all k_scale_ext blocks are zero) — the prefill did not "
             "go through the int4_protected write path. Increase prompt length / check the backend.")
    return nz[:n_blocks]


def _compare(before, after, keys):
    """[(block_id, tensor_key, shape, max_abs_diff)] for every mismatching tensor."""
    import torch
    mism = []
    for i, (a, c) in enumerate(zip(before, after)):
        for k in keys:
            ta, tc = a[k], c[k]
            if ta.shape != tc.shape or not torch.equal(ta, tc):
                try:
                    diff = (ta.to(torch.float64) - tc.to(torch.float64)).abs().max().item()
                except Exception:  # noqa: BLE001
                    diff = float("nan")
                mism.append((a.get("block_id", i), k, tuple(ta.shape), diff))
    return mism


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase-0 KVPro snapshot round-trip verification (real writer)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=1024)
    ap.add_argument("--gpu-mem-util", type=float, default=0.5)
    ap.add_argument("--prompt", default="The secret access code is 60494. " * 40)
    ap.add_argument("--max-tokens", type=int, default=8)
    ap.add_argument("--n-blocks", type=int, default=8, help="how many written blocks to round-trip")
    ap.add_argument("--snapshot-path", default="/tmp/kvpro_prefix_snapshot.pt")
    args = ap.parse_args(argv)

    # Arm the writer's native block dump as corroboration (separate from our snapshot).
    os.environ.setdefault("INT4_PROTECTED_DUMP_BLOCKS", "/tmp/kvpro_native_dump.pt")
    native_dump = os.environ["INT4_PROTECTED_DUMP_BLOCKS"]

    try:
        import torch  # noqa: F401
    except Exception as e:  # noqa: BLE001
        _die(f"torch not importable — this script is pod-only (needs a GPU build): {e}")

    try:
        from kv_policy import tier5b_snapshot as t5b
    except Exception as e:  # noqa: BLE001
        _die(f"could not import kv_policy.tier5b_snapshot ({e}). Run from the repo root or set "
             f"PYTHONPATH to include {_KVPOLICY_ROOT}.")

    try:
        from kv_policy.int4_protected import Int4ProtectedLLM
        from vllm import SamplingParams
    except Exception as e:  # noqa: BLE001
        _die(f"could not import Int4ProtectedLLM / vllm ({e}). Install vllm + the int4_protected "
             "backend on this pod.")

    print(f"[1/6] building Int4ProtectedLLM(model={args.model}, max_model_len={args.max_model_len}) ...")
    try:
        llm = Int4ProtectedLLM(model=args.model, max_model_len=args.max_model_len,
                               gpu_memory_utilization=args.gpu_mem_util, enforce_eager=True)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "config" in msg.lower() or "couldn't connect" in msg.lower() or "Can't load" in msg:
            _die(f"model config could not be loaded ({type(e).__name__}: {e}).\n"
                 f"  The model '{args.model}' is not cached on this pod and/or HF is unreachable.\n"
                 "  Fix: download it, set HF creds, or pass a LOCAL path to --model. E.g.:\n"
                 "    export HF_HUB_ENABLE_HF_TRANSFER=0   # if hf_transfer isn't installed\n"
                 "    huggingface-cli download Qwen/Qwen2.5-7B-Instruct\n"
                 "  then re-run, or: --model /path/to/local/Qwen2.5-7B-Instruct")
        if "mask" in msg.lower() or "protect" in msg.lower() or os.environ.get("PROTECT_MASK_PATH", "") in msg:
            _die(f"protect mask problem ({type(e).__name__}: {e}).\n"
                 "  Set $PROTECT_MASK_PATH to the calibrated mask "
                 "(default /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt) or run Phase 5B.0.")
        _die(f"Int4ProtectedLLM construction failed ({type(e).__name__}: {e}).")

    print(f"[2/6] short prefill+decode (max_tokens={args.max_tokens}) to populate KV ...")
    out = llm.generate([args.prompt], SamplingParams(temperature=0.0, max_tokens=args.max_tokens))
    print(f"      generated: {out[0].outputs[0].text[:60]!r}")
    if os.path.exists(native_dump):
        print(f"[ok] native writer dump produced at {native_dump} (write path confirmed firing)")
    else:
        print(f"[warn] native dump {native_dump} not found — corroboration only; proceeding via writer scales")

    print("[3/6] acquiring live writer + paged kv_cache ...")
    worker, model = _get_model(llm)
    gpu_cache = _get_gpu_cache(worker)
    writer, kv = _pair_writer_kv(model, gpu_cache)

    block_ids = _written_block_ids(writer, args.n_blocks)
    print(f"[ok] round-tripping {len(block_ids)} written block_ids: {block_ids}")

    keys = t5b._TENSOR_KEYS

    print(f"[4/6] DISK round-trip: save -> zero -> load -> restore_prefix ({args.snapshot_path}) ...")
    reference = [t5b.snapshot_block(writer, kv, b) for b in block_ids]
    saved = t5b.save_prefix_snapshot(writer, kv, block_ids, args.snapshot_path)
    print(f"      saved {saved['n_blocks']} blocks, {saved['approx_bytes']} bytes "
          f"({saved['approx_bytes'] / max(1, len(block_ids)):.0f} B/block)")
    t5b._zero_blocks(writer, kv, block_ids)
    snap = t5b.load_prefix_snapshot(args.snapshot_path)
    t5b.restore_prefix(writer, kv, snap, block_ids)
    after = [t5b.snapshot_block(writer, kv, b) for b in block_ids]
    disk_mism = _compare(reference, after, keys)
    disk_clean = not disk_mism

    print("[5/6] in-memory verify_roundtrip (built-in byte-gate) ...")
    res = t5b.verify_roundtrip(writer, kv, block_ids)

    print("\n================ RESULT ================")
    print(f"DISK   save/load/restore_prefix : {'PASS' if disk_clean else 'FAIL'}")
    print(f"MEMORY verify_roundtrip         : {'PASS' if res['clean'] else 'FAIL'}")
    print(f"per-tensor (memory): {res['report']}")
    if not disk_clean:
        print("\nDISK mismatches (block_id, tensor, shape, max_abs_diff):")
        for m in disk_mism[:40]:
            print(f"  {m}")
    overall = disk_clean and res["clean"]
    print("\n" + ("PASS — KVPro snapshot/restore is byte-faithful on this writer; Phase-0 gate cleared."
                  if overall else
                  "FAIL — snapshot/restore is NOT byte-faithful; do NOT proceed to the CacheGen comparison."))
    print("========================================")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
