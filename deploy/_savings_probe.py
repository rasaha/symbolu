#!/usr/bin/env python3
# deploy/_savings_probe.py — capacity (density) + optional needle (quality) for ONE
# backend, mostly at init time. Called by customer_savings_demo.sh once per backend
# (bf16 vs int4) so a single process holds a single model. Writes a small JSON.
#
#   python deploy/_savings_probe.py --backend int4 --model $M --mml 32768 --needle --out cap_int4.json
#   python deploy/_savings_probe.py --backend bf16 --model $M --mml 32768           --out cap_bf16.json
#   python deploy/_savings_probe.py --selftest    # CPU
#
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

for _r in (Path("/workspace/symbolu/CTM_plus"), Path(__file__).resolve().parent.parent / "CTM_plus"):
    if (_r / "KVPolicy").is_dir() and str(_r / "KVPolicy") not in sys.path:
        sys.path.insert(0, str(_r / "KVPolicy"))
        break

_NEEDLE_CODE = "X7Q-K2M-9PD"


def density_ratio(int4_slots, bf16_slots):
    """Pure: token-capacity ratio int4/bf16 (selftested)."""
    if isinstance(int4_slots, (int, float)) and isinstance(bf16_slots, (int, float)) and bf16_slots:
        return int4_slots / bf16_slots
    return None


def net_density_ratio(int4_slots, bf16_slots, sidecar_bytes, budget_bytes):
    """Pure: pool ratio discounted by the OUT-OF-POOL sidecar tax (selftested).

    The int4 sidecars (scales/xmin/protect/backing/staging) are allocated
    OUTSIDE vLLM's gpu_memory_utilization budget, so the raw pool ratio
    overstates the win at equal total VRAM. Approximation: net = raw *
    (1 - sidecar/budget). Falls back to the raw ratio when unmeasured.
    """
    r = density_ratio(int4_slots, bf16_slots)
    if (r is None or not isinstance(sidecar_bytes, (int, float))
            or not isinstance(budget_bytes, (int, float)) or budget_bytes <= 0):
        return r
    frac = max(0.0, min(1.0, sidecar_bytes / budget_bytes))
    return r * (1.0 - frac)


def _sidecar_bytes(llm):
    """Sum the UNIQUE cuda tensor storages held by the int4 writers outside
    vLLM's paged pool (per-block scales/xmin/protect, bf16 backing, per-slot
    staging) — the honest density tax. None if the writers aren't found."""
    import torch
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    model = None
    for fn in (
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
    ):
        try:
            model = fn(llm)
            break
        except AttributeError:
            continue
    if model is None:
        return None

    seen, total = set(), 0

    def _add(t):
        nonlocal total
        if isinstance(t, torch.Tensor) and t.is_cuda:
            key = (t.untyped_storage().data_ptr(), t.untyped_storage().nbytes())
            if key not in seen:
                seen.add(key)
                total += key[1]

    n_writers = 0
    for _, sub in model.named_modules():
        impl = getattr(sub, "impl", None)
        if not isinstance(impl, Int4ProtectedAttentionImpl):
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is None:
            continue
        n_writers += 1
        for v in vars(w).values():
            _add(v)
            if isinstance(v, dict):  # eg. per-seq staging states
                for sv in v.values():
                    _add(sv)
                    for svv in vars(sv).values() if hasattr(sv, "__dict__") else ():
                        _add(svv)
    return total if n_writers else None


def _capacity(llm):
    cc = llm.llm_engine.cache_config
    nb = getattr(cc, "num_gpu_blocks", None)
    bs = getattr(cc, "block_size", None)
    return {"num_gpu_blocks": nb, "block_size": bs,
            "total_token_slots": (nb * bs) if (nb and bs) else None}


def _needle(llm, mml):
    from vllm import SamplingParams
    tok = llm.get_tokenizer()
    base = "Background note: routine operations continued without incident. "
    n = max(256, mml // 2)
    ids = tok(base * (n // 12 + 4))["input_ids"][:n]
    mid = len(ids) // 2
    ids = (ids[:mid] + tok(f" Confidential: the vault code is {_NEEDLE_CODE}. ")["input_ids"]
           + ids[mid:])[:n]
    prompt = (tok.decode(ids) +
              "\n\nQuestion: what is the vault code above? Answer with only the code.\nAnswer:")
    out = llm.generate([prompt], SamplingParams(temperature=0.0, max_tokens=16))
    text = out[0].outputs[0].text
    return {"context_tokens": n, "code": _NEEDLE_CODE,
            "retrieved": _NEEDLE_CODE in text, "answer": text[:48]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="capacity + optional needle for one backend")
    ap.add_argument("--backend", choices=["int4", "bf16"])
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--mml", type=int, default=32768)
    ap.add_argument("--gpu-util", type=float, default=0.85)
    ap.add_argument("--max-num-seqs", type=int, default=16,
                    help="cap scheduler concurrency; the probe is B=1")
    ap.add_argument("--graphs", action="store_true",
                    help="enable CUDA graphs (default eager — see comment)")
    ap.add_argument("--needle", action="store_true")
    ap.add_argument("--out", default="/tmp/savings_cap.json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        ok = (abs(density_ratio(900000, 450000) - 2.0) < 1e-9
              and density_ratio(1, 0) is None and density_ratio(1, None) is None
              and abs(net_density_ratio(800, 400, 0, 100) - 2.0) < 1e-9
              and abs(net_density_ratio(800, 400, 10, 100) - 1.8) < 1e-9
              and abs(net_density_ratio(800, 400, None, 100) - 2.0) < 1e-9
              and net_density_ratio(800, None, 10, 100) is None)
        print("[PASS]" if ok else "[FAIL]", "density_ratio + net_density_ratio")
        return 0 if ok else 1

    # EAGER by default, concurrency capped: the probe measures DENSITY +
    # QUALITY at B=1 (the contract-validated int4 config), not throughput.
    # Graph capture would warm dummy decode batches up to max_num_seqs,
    # inflating per-slot staging + capture workspace ON TOP of the
    # out-of-pool sidecar tax -> OOM at high gpu_util (seen at 0.85/A100-80G).
    # Pool size (the density number) is unaffected by eager/max_num_seqs.
    eng = dict(max_model_len=args.mml, gpu_memory_utilization=args.gpu_util,
               max_num_seqs=args.max_num_seqs, enforce_eager=not args.graphs)
    if args.backend == "int4":
        import kv_policy.int4_protected  # noqa: F401
        from kv_policy.int4_protected import Int4ProtectedLLM
        llm = Int4ProtectedLLM(model=args.model, **eng)
    else:
        from vllm import LLM
        llm = LLM(model=args.model, **eng)

    rep = {"backend": args.backend, "model": args.model, "mml": args.mml,
           "gpu_util": args.gpu_util, "max_num_seqs": args.max_num_seqs,
           "enforce_eager": not args.graphs, **_capacity(llm)}
    if args.needle:
        rep["quality"] = _needle(llm, args.mml)
    if args.backend == "int4":
        # Tiny generate first: the writers allocate sidecars lazily on
        # first forward (no-op if the needle already ran).
        from vllm import SamplingParams
        llm.generate(["Hello"], SamplingParams(temperature=0.0, max_tokens=2))
        import torch
        rep["sidecar_bytes"] = _sidecar_bytes(llm)
        rep["vllm_budget_bytes"] = int(
            args.gpu_util * torch.cuda.get_device_properties(0).total_memory)
    Path(args.out).write_text(json.dumps(rep, indent=2))
    print(f"[probe] {args.backend}: {rep.get('total_token_slots')} token-slots "
          f"({rep.get('num_gpu_blocks')} blocks x bs={rep.get('block_size')})"
          + (f"  needle={'OK' if rep['quality']['retrieved'] else 'MISS'}"
             if args.needle else "")
          + f" -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
