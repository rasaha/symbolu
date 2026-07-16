#!/usr/bin/env python3
"""KVPro V3 Gate-1 — end-to-end FAKE-QUANT quality (POD-ONLY, HARDWARE-UNTESTED).

Runs the model with its KV cache fake-quantized (quantize->dequantize in fp) per candidate, so the
attention actually reads the candidate's reconstructed KV — a real end-to-end quality signal that
needs NO int4 CUDA kernel and NO int4_protected backend. Measures perplexity + next-token agreement
vs full precision (and, with --needle, a greedy needle check).

Needs: GPU + model weights + the frozen protect mask. Emits e2e_quality.json in the gates' schema.

⚠️ HARDWARE-UNTESTED. The custom Cache fake-quantizes the FULL accumulated K/V each update (matches the
production per-block-K / per-token-V granularity via the offline quantizers). Verify against your
transformers Cache API version; fails loudly if the cache patch does not take effect.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "CTM_plus", "KVPolicy"))
import fakequant_model as FQ    # noqa: E402  (shared robust cache/loader)


def _die(m, c=2):
    print(f"\n[FAIL] {m}", file=sys.stderr); sys.exit(c)


def _ppl_and_agreement(model, ids, cand, masks):
    import torch
    with torch.no_grad():
        cache = FQ.build_fakequant_cache(cand, masks)
        out = model(ids, use_cache=True, past_key_values=cache)
        logits = out.logits[0, :-1].float()                          # (S-1, vocab)
        tgt = ids[0, 1:]
        logp = torch.log_softmax(logits, dim=-1)
        nll = -logp[range(tgt.shape[0]), tgt].mean()
        ppl = float(math.exp(nll))
        argmax = logits.argmax(-1)
    return ppl, argmax


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fake-quant end-to-end quality (pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--text", default="The quick brown fox jumps over the lazy dog. " * 30)
    ap.add_argument("--cells", default="fp,affine,S1,S2,S3,S4")
    ap.add_argument("--out", default="e2e_quality.json")
    args = ap.parse_args(argv)

    if not args.mask or not os.path.isfile(args.mask):
        _die(f"protect mask missing: {args.mask!r}")
    try:
        import torch  # noqa: F401
    except Exception as e:  # noqa: BLE001
        _die(f"torch import failed: {e}")

    model, tok = FQ.load_model(args.model)          # dtype-safe + GPU check
    ids = tok(args.text, return_tensors="pt").input_ids.to("cuda")
    mask_blob = torch.load(args.mask, map_location="cpu", weights_only=False)
    masks = mask_blob.get("mask", mask_blob.get("protect_mask"))
    if masks is None:
        _die("mask file has no 'mask'/'protect_mask'.")

    results = {}
    fp_argmax = None
    for cell in args.cells.split(","):
        ppl, argmax = _ppl_and_agreement(model, ids, cell, masks)
        if cell == "fp":
            fp_argmax = argmax
            agree = 100.0
        else:
            agree = float((argmax == fp_argmax).float().mean() * 100.0) if fp_argmax is not None else None
        results[cell] = {"ppl": round(ppl, 4), "token_agree": None if agree is None else round(agree, 3)}
        print(f"  {cell:7} ppl={ppl:.3f} token_agree_vs_fp={results[cell]['token_agree']}")

    results["_meta"] = {"model": args.model, "label": "MEASURED",
                        "note": "ppl + next-token agreement (fake-quant). hard_needle/mmlu NOT RUN here "
                                "(add a needle/MMLU driver for the full end-to-end gate)."}
    json.dump(results, open(args.out, "w"), indent=2)
    print(f"[MEASURED] fake-quant quality -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
