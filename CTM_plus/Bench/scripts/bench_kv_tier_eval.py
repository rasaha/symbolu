#!/usr/bin/env python3
# KV-tier evaluation — is 8-bit (fp8) KV a viable SPEED tier vs bf16, given int4 is the capacity tier?
#
# Post-K2-M1 (int4 decode is occupancy-bound and no cheap kernel fixes it), the speed problem is
# better solved by a cheaper compression. fp8 KV (kv_cache_dtype="fp8") is native in vLLM + the
# flash-attn fork: single-scale dequant, no nibble unpack / protect / per-group scale-xmin, NO custom
# kernel -> should be ~bf16 speed at 2x compression. This measures it, at matched operating points:
#   * decode latency (prefill-subtracted ms/tok, eager) vs bf16;
#   * KV capacity (# gpu blocks at fixed gpu-mem) — fp8 ~2x bf16, int4 ~4-8x;
#   * quality proxy: greedy token divergence vs bf16 (first-divergence + fraction-matching).
# The int4 number (from K2_M1_VERDICT.md, ~152 ms/tok ctx16k B=8) is printed for context.
#
#   python CTM_plus/Bench/scripts/bench_kv_tier_eval.py --context-tokens 16000 --batch 8 --gen 64
#   python CTM_plus/Bench/scripts/bench_kv_tier_eval.py --dtypes auto,fp8,fp8_e5m2
#   python CTM_plus/Bench/scripts/bench_kv_tier_eval.py --selftest   # CPU
#
# NOTE: fp8-e4m3 quality benefits from calibrated scales; without a scales file vLLM uses a default
# scale, so treat the token-divergence here as a fast proxy, not the final quality gate.
from __future__ import annotations
import argparse, os, sys, time

LAT_GO = 1.20            # fp8 "fast enough" if decode <= 1.2x bf16
INT4_REF_MS = 152.0      # measured int4-protected control (K2_M1_VERDICT.md, ctx16k B=8)


def token_match_frac(ref, cand):
    """Fraction of leading tokens that match ref (per sequence, averaged). 1.0 = identical."""
    if not ref or not cand:
        return 0.0
    fracs = []
    for r, c in zip(ref, cand):
        n = min(len(r), len(c))
        if n == 0:
            fracs.append(0.0); continue
        k = 0
        while k < n and r[k] == c[k]:
            k += 1
        fracs.append(k / n)
    return sum(fracs) / len(fracs)


def verdict(rows):
    """rows[dtype] = {decode_ms, match_frac(vs bf16)}. Return (notes, fp8_fast:bool)."""
    notes = []
    base = rows.get("auto", {}).get("decode_ms")
    if not base:
        return ["no bf16 (auto) baseline"], False
    fp8_fast = False
    for dt, r in rows.items():
        if dt == "auto":
            notes.append(f"{dt} (bf16): {r['decode_ms']:.2f} ms/tok  (baseline)"); continue
        ratio = r["decode_ms"] / base
        q = r.get("match_frac", 0.0)
        tag = "FAST" if ratio <= LAT_GO else "slow"
        notes.append(f"{dt}: {r['decode_ms']:.2f} ms/tok = {ratio:.2f}x bf16 [{tag}]  "
                     f"token-match {q*100:.0f}% (quality proxy)")
        if dt.startswith("fp8") and ratio <= LAT_GO:
            fp8_fast = True
    notes.append(f"(int4-protected ref: {INT4_REF_MS:.0f} ms/tok = {INT4_REF_MS/base:.1f}x bf16 — the capacity tier)")
    return notes, fp8_fast


def _selftest():
    fails = []
    def ck(n, c):
        print(f"  [{'PASS' if c else 'FAIL'}] {n}"); fails.append(n) if not c else None
    ck("identical tokens -> 1.0", token_match_frac([[1,2,3]], [[1,2,3]]) == 1.0)
    ck("first-token divergence -> 0.0", token_match_frac([[1,2,3]], [[9,2,3]]) == 0.0)
    ck("half match", abs(token_match_frac([[1,2,3,4]], [[1,2,9,9]]) - 0.5) < 1e-9)
    notes, fast = verdict({"auto": {"decode_ms": 100.0},
                           "fp8": {"decode_ms": 110.0, "match_frac": 0.95}})
    ck("fp8 within 1.2x -> fast", fast)
    notes2, fast2 = verdict({"auto": {"decode_ms": 100.0},
                             "fp8": {"decode_ms": 160.0, "match_frac": 0.9}})
    ck("fp8 1.6x -> not fast", not fast2)
    print("ALL PASS" if not fails else f"{len(fails)} FAIL")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="KV-tier eval: fp8 speed tier vs bf16 (int4 = capacity)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--context-tokens", type=int, default=16000)
    ap.add_argument("--gen", type=int, default=64)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--gpu-util", type=float, default=0.70)
    ap.add_argument("--n-runs", type=int, default=3)
    ap.add_argument("--dtypes", default="auto,fp8", help="comma list: auto (bf16), fp8, fp8_e5m2, fp8_e4m3")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()

    import torch
    from vllm import LLM, SamplingParams
    mml = args.context_tokens + 4096
    base = ("The quarterly logistics review noted that warehouse seven shipped on schedule "
            "while the northern depot lagged by two days. ")

    def measure(dtype):
        # stock vLLM, eager (so decode kernels are visible / comparable); fp8 needs no custom build.
        llm = LLM(model=args.model, max_model_len=mml, gpu_memory_utilization=args.gpu_util,
                  dtype="bfloat16", kv_cache_dtype=dtype, enforce_eager=True,
                  max_num_seqs=max(2, args.batch))
        tok = llm.get_tokenizer()
        ids = tok(base * max(2, args.context_tokens // 24 + 2))["input_ids"][:args.context_tokens]
        prompt = tok.decode(ids) + "\n\nWrite a brief summary:"
        prompts = [prompt] * args.batch
        sp = SamplingParams(temperature=0.0, max_tokens=args.gen, ignore_eos=True)
        sp1 = SamplingParams(temperature=0.0, max_tokens=1, ignore_eos=True)
        try:
            blocks = llm.llm_engine.cache_config.num_gpu_blocks
        except Exception:
            blocks = None
        llm.generate(prompts, sp1)  # warmup
        fulls, pres = [], []
        for _ in range(max(1, args.n_runs)):
            torch.cuda.synchronize(); t = time.perf_counter()
            outs = llm.generate(prompts, sp); torch.cuda.synchronize()
            fulls.append(time.perf_counter() - t)
            torch.cuda.synchronize(); t = time.perf_counter()
            llm.generate(prompts, sp1); torch.cuda.synchronize()
            pres.append(time.perf_counter() - t)
        fulls.sort(); pres.sort()
        decode_ms = (fulls[len(fulls)//2] - pres[len(pres)//2]) * 1e3 / max(1, args.gen)
        toks = [list(o.outputs[0].token_ids) for o in outs]
        del llm
        torch.cuda.empty_cache()
        return {"decode_ms": max(decode_ms, 0.0), "tokens": toks, "blocks": blocks}

    dtypes = [d.strip() for d in args.dtypes.split(",") if d.strip()]
    print(f"\nKV-tier eval — {args.model.split('/')[-1]} ctx={args.context_tokens} B={args.batch} gen={args.gen}")
    results, ref_tokens = {}, None
    for dt in dtypes:
        r = measure(dt)
        if dt == "auto":
            ref_tokens = r["tokens"]
        r["match_frac"] = token_match_frac(ref_tokens, r["tokens"]) if ref_tokens else float("nan")
        results[dt] = {"decode_ms": r["decode_ms"], "match_frac": r["match_frac"], "blocks": r["blocks"]}
        b = r["blocks"]
        print(f"  {dt:<10} decode {r['decode_ms']:7.2f} ms/tok   "
              f"KV blocks {b if b is not None else '?':>7}   "
              f"token-match {r['match_frac']*100:5.1f}% vs bf16")
    print("\n-- verdict --")
    notes, fp8_fast = verdict(results)
    for n in notes:
        print("  " + n)
    ab = results.get("auto", {}).get("blocks"); fb = results.get("fp8", {}).get("blocks")
    if ab and fb:
        print(f"  capacity: fp8 {fb} vs bf16 {ab} blocks = {fb/ab:.1f}x KV; int4 ~4-8x (capacity tier).")
    print()
    if fp8_fast:
        print("fp8 is FAST enough (<=1.2x bf16). SPEED-TIER candidate confirmed on latency -> next run a "
              "REAL quality eval (perplexity / task accuracy, ideally with calibrated fp8 scales) before shipping.")
    else:
        print("fp8 NOT within 1.2x bf16 here -> re-check calibration/config; if it holds, the 8-bit speed "
              "advantage is smaller than hoped and bf16 stays the speed path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
