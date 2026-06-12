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
    ap.add_argument("--needle", action="store_true")
    ap.add_argument("--out", default="/tmp/savings_cap.json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        ok = (abs(density_ratio(900000, 450000) - 2.0) < 1e-9
              and density_ratio(1, 0) is None and density_ratio(1, None) is None)
        print("[PASS]" if ok else "[FAIL]", "density_ratio")
        return 0 if ok else 1

    if args.backend == "int4":
        import kv_policy.int4_protected  # noqa: F401
        from kv_policy.int4_protected import Int4ProtectedLLM
        llm = Int4ProtectedLLM(model=args.model, max_model_len=args.mml,
                               gpu_memory_utilization=args.gpu_util)
    else:
        from vllm import LLM
        llm = LLM(model=args.model, max_model_len=args.mml,
                  gpu_memory_utilization=args.gpu_util)

    rep = {"backend": args.backend, "model": args.model, "mml": args.mml,
           "gpu_util": args.gpu_util, **_capacity(llm)}
    if args.needle:
        rep["quality"] = _needle(llm, args.mml)
    Path(args.out).write_text(json.dumps(rep, indent=2))
    print(f"[probe] {args.backend}: {rep.get('total_token_slots')} token-slots "
          f"({rep.get('num_gpu_blocks')} blocks x bs={rep.get('block_size')})"
          + (f"  needle={'OK' if rep['quality']['retrieved'] else 'MISS'}"
             if args.needle else "")
          + f" -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
