#!/usr/bin/env python3
"""Live-engine wiring (storage path): measure KVPro warm-tier snapshot systems metrics.

Builds a real Int4ProtectedLLM, and for each of N prefixes: prefill -> snapshot the
written blocks + sidecars to NVMe (save_prefix_snapshot) -> zero -> reload
(load_prefix_snapshot + restore_prefix), measuring the SYSTEMS axis of the warm-tier
protocol on REAL KV:
  - bytes/token + bytes/block stored
  - encode (save) time + throughput
  - reload (load+restore) time + throughput, p50/p95
  - transfer volume (NVMe file bytes)
plus a per-prefix byte-clean sanity check (snapshot == restore).

This is the half of `kvpro_snapshot_backend` that does NOT need the int4 decode FA fork
or scheduler injection. The serving half (reload_query generating tokens over restored
KV -> TTFT + quality-after-reuse) DOES need both and is intentionally not built here —
see docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md. Fails loudly if the live writer /
kv_cache / written blocks can't be obtained; never fakes tensors.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KVPOLICY_ROOT = os.path.join(_REPO, "CTM_plus", "KVPolicy")
if os.path.isdir(_KVPOLICY_ROOT) and _KVPOLICY_ROOT not in sys.path:
    sys.path.insert(0, _KVPOLICY_ROOT)


def _die(msg: str, code: int = 2):
    print(f"\n[FAIL] {msg}", file=sys.stderr)
    sys.exit(code)


# --- live-engine access (mirrors scripts/verify_kvpro_snapshot_roundtrip.py, proven) --- #
def _get_model(llm):
    worker = llm.llm_engine.model_executor.driver_worker
    mr = getattr(worker, "model_runner", None)
    model = getattr(mr, "model", None) if mr is not None else getattr(worker, "model", None)
    if model is None:
        _die("could not reach the model (driver_worker.model_runner.model).")
    return worker, model


def _get_gpu_cache(worker):
    ce_list = getattr(worker, "cache_engine", None)
    if not ce_list:
        _die("worker.cache_engine is empty/None.")
    gpu_cache = getattr(ce_list[0], "gpu_cache", None)
    if not gpu_cache:
        _die("cache_engine[0].gpu_cache is empty/None.")
    return gpu_cache


def _pair_writer_kv(model, gpu_cache):
    writers = []
    for name, mod in model.named_modules():
        impl = getattr(mod, "impl", None)
        w = getattr(impl, "_phase5b_paged_writer", None) if impl is not None else None
        if w is not None:
            writers.append((name, w))
    if not writers:
        _die("no int4_protected writer found — model is not on the int4_protected backend "
             "(check kv_cache_dtype + that int4_protected_C built).")
    name, writer = writers[0]
    kv = gpu_cache[0]
    shp = tuple(kv.shape)
    if (int(writer.NB), int(writer.BS), int(writer.D)) != (int(shp[1]), int(shp[2]), int(shp[4])):
        _die(f"writer/kv_cache geometry mismatch on '{name}': writer(NB={writer.NB},BS={writer.BS},"
             f"D={writer.D}) vs kv_cache{shp}.")
    return writer, kv


def _written_block_ids(writer, n_blocks):
    import torch
    ks = writer.k_scale_ext
    per_block = ks.detach().abs().reshape(ks.shape[0], -1).sum(dim=1)
    nz = torch.nonzero(per_block > 0, as_tuple=True)[0].tolist()
    if not nz:
        _die("no written blocks (all k_scale_ext zero) — prefill did not write through int4 path.")
    return nz[:n_blocks]


def _prompts(n, reps):
    base = ("The field archive recorded a measurement, a checksum, and a timestamp for the "
            "overnight batch run; the operator filed the report before the shift change. ")
    return [f"Session {i}. " + base * reps + f" The session reference code is {10000 + i}."
            for i in range(n)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KVPro warm-tier snapshot SYSTEMS measurement (real writer)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=2048)
    ap.add_argument("--gpu-mem-util", type=float, default=0.5)
    ap.add_argument("--n-prefixes", type=int, default=8)
    ap.add_argument("--reps", type=int, default=60, help="filler repetitions per prefix (context length knob)")
    ap.add_argument("--n-blocks", type=int, default=16, help="written blocks to snapshot per prefix")
    ap.add_argument("--snapshot-dir", default="/tmp/kvpro_warmtier_snaps")
    ap.add_argument("--out", default="kvpro_snapshot_systems.json")
    ap.add_argument("--label", default="kvpro_snapshot")
    args = ap.parse_args(argv)

    os.environ.setdefault("INT4_PROTECTED_DUMP_BLOCKS", "/tmp/kvpro_native_dump.pt")
    os.makedirs(args.snapshot_dir, exist_ok=True)

    try:
        import torch
    except Exception as e:  # noqa: BLE001
        _die(f"torch not importable — pod-only script: {e}")
    try:
        from kv_policy import tier5b_snapshot as t5b
        from kv_policy.int4_protected import Int4ProtectedLLM
        from vllm import SamplingParams
    except Exception as e:  # noqa: BLE001
        _die(f"import failed ({e}). Run from repo root with vllm + int4_protected on this pod.")

    print(f"[build] Int4ProtectedLLM({args.model}, max_model_len={args.max_model_len}) ...")
    try:
        llm = Int4ProtectedLLM(model=args.model, max_model_len=args.max_model_len,
                               gpu_memory_utilization=args.gpu_mem_util, enforce_eager=True)
    except Exception as e:  # noqa: BLE001
        _die(f"Int4ProtectedLLM construction failed ({type(e).__name__}: {e}). "
             "Check the model is cached and $PROTECT_MASK_PATH points at the calibrated mask.")

    worker, model = _get_model(llm)
    recs = []
    keys = t5b._TENSOR_KEYS
    prompts = _prompts(args.n_prefixes, args.reps)

    for i, prompt in enumerate(prompts):
        try:
            out = llm.generate([prompt], SamplingParams(temperature=0.0, max_tokens=1))
            n_tok = len(out[0].prompt_token_ids)
        except Exception as e:  # noqa: BLE001
            if "flash_attn_with_int4_kvcache" in str(e) or "_read_decode" in str(e):
                # prefill already wrote KV before the (absent) decode kernel raised.
                n_tok = None
            else:
                _die(f"prefill {i} failed ({type(e).__name__}: {e}).")

        gpu_cache = _get_gpu_cache(worker)
        writer, kv = _pair_writer_kv(model, gpu_cache)
        block_ids = _written_block_ids(writer, args.n_blocks)
        if n_tok is None:
            n_tok = len(block_ids) * int(writer.BS)         # fallback estimate
        path = os.path.join(args.snapshot_dir, f"prefix_{i}.pt")

        ref = [t5b.snapshot_block(writer, kv, b) for b in block_ids]
        t0 = time.time()
        saved = t5b.save_prefix_snapshot(writer, kv, block_ids, path)
        encode_s = time.time() - t0
        file_bytes = os.path.getsize(path)

        with torch.inference_mode():
            t5b._zero_blocks(writer, kv, block_ids)
            t1 = time.time()
            snap = t5b.load_prefix_snapshot(path)
            t5b.restore_prefix(writer, kv, snap, block_ids)
            reload_s = time.time() - t1
            after = [t5b.snapshot_block(writer, kv, b) for b in block_ids]
        clean = all(torch.equal(a[k], c[k]) for a, c in zip(ref, after) for k in keys)

        recs.append({"prefix": i, "n_blocks": len(block_ids), "n_tokens": n_tok,
                     "file_bytes": file_bytes, "approx_tensor_bytes": saved["approx_bytes"],
                     "encode_s": encode_s, "reload_s": reload_s, "clean": clean})
        print(f"  prefix {i}: tok={n_tok} blocks={len(block_ids)} file={file_bytes}B "
              f"encode={encode_s*1e3:.1f}ms reload={reload_s*1e3:.1f}ms clean={clean}")

    tok = sum(r["n_tokens"] for r in recs) or 1
    fb = sum(r["file_bytes"] for r in recs)
    nb = sum(r["n_blocks"] for r in recs) or 1
    reloads = [r["reload_s"] for r in recs]
    enc_s = sum(r["encode_s"] for r in recs)
    rel_s = sum(r["reload_s"] for r in recs)
    summary = {
        "label": args.label, "model": args.model, "n_prefixes": len(recs),
        "all_clean": all(r["clean"] for r in recs),
        "bytes_per_token": fb / tok,
        "bytes_per_block": fb / nb,
        "encode_MBps": (fb / 1e6) / enc_s if enc_s > 0 else float("nan"),
        "reload_MBps": (fb / 1e6) / rel_s if rel_s > 0 else float("nan"),
        "reload_s_per_1k_tokens": 1000.0 * rel_s / tok,
        "reload_s_p50": statistics.median(reloads) if reloads else float("nan"),
        "reload_s_p95": (sorted(reloads)[max(0, int(0.95 * (len(reloads) - 1)))] if reloads else float("nan")),
        "transfer_bytes_per_token": fb / tok,
        "quality_note": "N/A on this pod — quality-after-reuse + TTFT-with-serving need the int4 "
                        "decode FA fork + scheduler prefix-injection (not built here).",
        "records": recs,
    }
    with open(args.out, "w") as fh:
        json.dump(summary, fh, indent=2)

    print("\n============== KVPro warm-tier SYSTEMS ==============")
    print(f"all byte-clean         : {summary['all_clean']}")
    print(f"bytes/token            : {summary['bytes_per_token']:.2f}")
    print(f"bytes/block            : {summary['bytes_per_block']:.0f}")
    print(f"encode throughput      : {summary['encode_MBps']:.1f} MB/s")
    print(f"reload throughput      : {summary['reload_MBps']:.1f} MB/s")
    print(f"reload s/1k tokens      : {summary['reload_s_per_1k_tokens']:.4f}")
    print(f"reload p50 / p95 (s)   : {summary['reload_s_p50']:.4f} / {summary['reload_s_p95']:.4f}")
    print(f"quality                : {summary['quality_note']}")
    print(f"-> {args.out}")
    print("====================================================")
    return 0 if summary["all_clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
