#!/usr/bin/env python3
"""TP smoke worker — build Int4ProtectedLLM at a given tensor_parallel_size, greedy-generate a
fixed prompt, and record the output + rank-0 writer geometry. One TP setting per process (running
TP=1 and TP=2 in the same process would conflict two vLLM engines). Writes a JSON record.

This MEASURES whatever actually happens: if int4_protected is not TP-aware, construction or
generation fails and that failure IS the measured result (TP not yet supported). Nothing is faked.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "CTM_plus", "KVPolicy"))


def _rank0_writer_geometry(llm):
    try:
        worker = llm.llm_engine.model_executor.driver_worker
        mr = getattr(worker, "model_runner", None)
        model = getattr(mr, "model", None) if mr is not None else getattr(worker, "model", None)
        for name, mod in model.named_modules():
            impl = getattr(mod, "impl", None)
            w = getattr(impl, "_phase5b_paged_writer", None) if impl is not None else None
            if w is not None:
                return {"layer": name, "H_per_rank": int(w.H), "D": int(w.D),
                        "NB": int(getattr(w, "NB", -1)), "n_protect": int(getattr(w, "n_protect", -1))}
    except Exception as e:  # noqa: BLE001
        return {"introspect_error": str(e)}
    return {"introspect_error": "no int4_protected writer found"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="int4_protected TP smoke worker")
    ap.add_argument("--tp", type=int, required=True)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=2048)
    ap.add_argument("--gpu-mem-util", type=float, default=0.5)
    ap.add_argument("--max-tokens", type=int, default=16)
    ap.add_argument("--prompt", default="List the first five prime numbers in order, comma separated.")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    rec = {"tp": args.tp, "model": args.model, "ok": False}
    try:
        from kv_policy.int4_protected import Int4ProtectedLLM
        from vllm import SamplingParams
        llm = Int4ProtectedLLM(
            model=args.model, max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_mem_util, enforce_eager=True,
            tensor_parallel_size=args.tp,
        )
        out = llm.generate([args.prompt], SamplingParams(temperature=0.0, max_tokens=args.max_tokens))
        rec["output_text"] = out[0].outputs[0].text
        rec["writer_geometry"] = _rank0_writer_geometry(llm)
        rec["ok"] = True
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback_tail"] = traceback.format_exc()[-1800:]

    with open(args.out, "w") as fh:
        json.dump(rec, fh, indent=2)
    print(json.dumps({k: rec.get(k) for k in ("tp", "ok", "error", "writer_geometry")}))
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
