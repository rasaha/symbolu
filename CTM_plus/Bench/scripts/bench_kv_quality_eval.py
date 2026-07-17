#!/usr/bin/env python3
# KV quality eval — does fp8 KV degrade model quality vs bf16? (latency is already GO: fp8 ~1.00x bf16)
#
# WHY NOT token-match: the greedy token-divergence proxy in bench_kv_tier_eval.py is CONFOUNDED. Greedy
# decoding diverges completely after a single early token flip, so a tiny (benign) fp8 rounding shows up
# as ~2% match even when the generated text is perfectly fine. It's a tripwire, not a quality measure.
#
# WHY PERPLEXITY: teacher-forced NLL over FIXED text scores the SAME tokens under each KV precision, so
# it is NOT confounded — a small fp8 error -> small PPL delta; a real degradation -> large PPL delta.
# That is the honest gate. We measure PPL over the TAIL of a long context (those tokens attend to the
# most quantized KV), so it stresses exactly what fp8 changes.
#
#   python CTM_plus/Bench/scripts/bench_kv_quality_eval.py --context-tokens 8000 --dtypes auto,fp8,fp8_e5m2
#   python CTM_plus/Bench/scripts/bench_kv_quality_eval.py --text-file heldout.txt   # real held-out text
#   python CTM_plus/Bench/scripts/bench_kv_quality_eval.py --selftest                # CPU, no GPU
#
# NOTE: uncalibrated fp8-e4m3 uses vLLM's DEFAULT KV scale. If the uncalibrated PPL delta is already
# tiny, fp8 quality is fine with ZERO calibration. If it's large, THEN invest in calibrated scales (or
# try e5m2) before ruling fp8 out. This measures prefill-KV PPL; a task-accuracy eval is the final gate.
from __future__ import annotations
import argparse, math, os, sys

# prompt_logprobs computes a rank over the FULL vocab for every prompt position (~[ctx x vocab], several
# GB at ctx=8000). Reduce allocator fragmentation so that peak allocates cleanly.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

PPL_GO = 0.01   # FROZEN before measurement: fp8 quality GO if perplexity within 1% of bf16 (delta <= 1%)

# Varied English so absolute PPL is meaningful; the bf16-vs-fp8 DELTA is the gate regardless of the text.
_PROSE = (
    "The harbor town woke slowly under a grey sky, its fishing boats knocking against the pier as gulls "
    "argued over the night's leftovers. In the capital, negotiators returned to the table after a recess "
    "that had lasted three days, each side claiming the other had moved first. A biologist studying the "
    "reef noted that the coral had begun to recover in patches where the water stayed cool, a small but "
    "genuine sign of resilience. Markets opened higher on news that inflation had eased for a second "
    "consecutive month, though analysts warned that a single quarter proves little. The old library, "
    "closed for renovation since spring, reopened with a modest ceremony and a new wing for local "
    "archives. On the mountain, the first heavy snow arrived early, stranding a group of hikers who were "
    "later guided down by a rescue team using thermal cameras. A software company announced that its next "
    "release would prioritize reliability over new features, a decision its engineers had privately urged "
    "for years. The orchestra rehearsed a symphony few had heard live, its conductor pausing often to "
    "coax a warmer tone from the strings. Farmers in the valley debated whether to plant early, weighing "
    "the risk of frost against the promise of a longer season. A historian uncovered letters suggesting "
    "the treaty had nearly collapsed over a clause about river rights, a detail absent from official "
    "accounts. The clinic reported that a new screening program had caught several cases early, when "
    "treatment is simplest and most effective. Late in the evening the power flickered once and held, and "
    "the town settled into an ordinary, unremarkable calm. "
    "A cartographer redrawing the coastline found that a small island had vanished from the latest survey, "
    "reclaimed by a decade of rising tides. The bakery on the corner switched to a slower fermentation, and "
    "regulars swore the bread tasted of patience. Engineers testing the new bridge loaded it with trucks "
    "full of water barrels, measuring how the deck flexed under a weight it might never carry. In the "
    "archive basement, a curator catalogued photographs whose subjects no one alive could name. The comet, "
    "visible for the first time in eighty years, drew crowds to rooftops who otherwise never looked up. A "
    "teacher in the mountain village taught forty children across six grades in a single room warmed by a "
    "wood stove. The startup abandoned its flagship feature after discovering that users wanted the opposite "
    "of what the founders had assumed. Divers surveying the wreck reported that the cold had preserved the "
    "ship's timbers far better than anyone expected. A court in the coastal province ruled that the ancient "
    "right to gather seaweed could not be sold to the new resort. The pianist practiced the same four bars "
    "for an hour, chasing a phrasing she could hear but not yet play. After the drought broke, the river "
    "carried so much silt that the water ran the color of weak tea for a week. A linguist recording the last "
    "fluent speakers of a dialect noticed they disagreed, gently, about the word for dusk. The observatory "
    "postponed its public night when smoke from distant fires turned the stars to smudges. Volunteers "
    "replanting the burned hillside chose species that would hold the soil before ones that would look "
    "beautiful. The auditor found the discrepancy not in the large accounts but in a rounding rule applied "
    "inconsistently for years. A chef known for excess surprised the critics with a menu of five plain "
    "dishes, each nearly perfect. The train was late again, and the commuters had long since stopped "
    "pretending to be surprised. Researchers found that the birds had learned to open the cafe's sugar "
    "packets, a skill that spread across the city in a single summer. The museum lit the sculpture from "
    "below, and a face that had looked stern for centuries suddenly seemed to be listening. A retired "
    "engineer spent his mornings fixing the neighborhood's broken radios, refusing payment but accepting "
    "coffee. The negotiators signed at dawn, too tired to smile for the single photograph that would outlast "
    "them all. "
)


def perplexity(nlls):
    """PPL = exp(mean NLL). nlls are per-token negative log-likelihoods in NATS. Empty -> inf."""
    if not nlls:
        return float("inf")
    return math.exp(sum(nlls) / len(nlls))


def ppl_delta(base, cand):
    """Relative PPL increase of cand vs base (0.01 = +1%). Invalid base -> inf."""
    if not base or base <= 0 or math.isinf(base) or math.isinf(cand):
        return float("inf")
    return (cand - base) / base


def verdict(rows):
    """rows[dtype] = {ppl, n}. Return (notes, fp8_quality_ok:bool)."""
    notes = []
    base = rows.get("auto", {}).get("ppl")
    if not base or math.isinf(base):
        return ["no bf16 (auto) PPL baseline"], False
    notes.append(f"auto (bf16): PPL {base:.4f}  (baseline, gate = within {PPL_GO*100:.0f}% )")
    fp8_ok = False
    for dt, r in rows.items():
        if dt == "auto":
            continue
        d = ppl_delta(base, r["ppl"])
        tag = "OK" if d <= PPL_GO else "DEGRADED"
        nll_txt = ""
        if "nll" in r and "nll" in rows.get("auto", {}):
            nll_txt = f"  ({r['nll'] - rows['auto']['nll']:+.4f} nats/tok abs)"
        notes.append(f"{dt}: PPL {r['ppl']:.4f} = {d*100:+.2f}% vs bf16 [{tag}]  (n={r.get('n','?')} tok){nll_txt}")
        if dt.startswith("fp8") and d <= PPL_GO:
            fp8_ok = True
    return notes, fp8_ok


def _selftest():
    fails = []
    def ck(n, c):
        print(f"  [{'PASS' if c else 'FAIL'}] {n}"); fails.append(n) if not c else None
    ck("PPL of zero-NLL -> 1.0", abs(perplexity([0.0, 0.0]) - 1.0) < 1e-12)
    ck("PPL of ln2-NLL -> 2.0", abs(perplexity([math.log(2)] * 5) - 2.0) < 1e-9)
    ck("empty -> inf", math.isinf(perplexity([])))
    ck("delta +0.5%", abs(ppl_delta(10.0, 10.05) - 0.005) < 1e-12)
    ck("delta of equal -> 0", abs(ppl_delta(7.0, 7.0)) < 1e-12)
    ck("delta bad base -> inf", math.isinf(ppl_delta(0.0, 1.0)))
    _, ok = verdict({"auto": {"ppl": 8.0}, "fp8": {"ppl": 8.05, "n": 100}})   # +0.6% -> OK
    ck("fp8 within 1% -> quality OK", ok)
    _, ok2 = verdict({"auto": {"ppl": 8.0}, "fp8": {"ppl": 8.5, "n": 100}})   # +6.25% -> DEGRADED
    ck("fp8 +6% -> not OK", not ok2)
    _, ok3 = verdict({"auto": {"ppl": 8.0},
                      "fp8": {"ppl": 8.5, "n": 9}, "fp8_e5m2": {"ppl": 8.02, "n": 9}})
    ck("any fp8* variant within 1% -> OK", ok3)
    print("ALL PASS" if not fails else f"{len(fails)} FAIL")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="KV quality eval: fp8 perplexity delta vs bf16 (not confounded by greedy drift)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--context-tokens", type=int, default=8000)
    ap.add_argument("--ppl-start-frac", type=float, default=0.5, help="measure PPL over tokens after this fraction (tail attends to the most KV)")
    # LOW by design: prompt_logprobs needs ACTIVATION headroom (ranks over the full vocab for every
    # prompt position, several GB), NOT a big KV pool — one sequence's KV is <1 GB. At high gpu_util
    # vLLM reserves ~40 GB of idle KV cache that starves the logprobs peak and OOMs.
    ap.add_argument("--gpu-util", type=float, default=0.30)
    ap.add_argument("--text-file", default=None, help="held-out text file; default = wikitext-2 (needs `datasets`), else tiled prose (INVALID)")
    ap.add_argument("--dtypes", default="auto,fp8", help="comma list: auto (bf16), fp8, fp8_e5m2")
    ap.add_argument("--calibrate", action="store_true",
                    help="fp8: compute KV scales at runtime (calculate_kv_scales=True). DEFAULT fp8 uses "
                         "scale=1.0, which SATURATES models with KV outliers (e.g. Qwen) -> catastrophic PPL. "
                         "This is the make-or-break lever for fp8 quality; compare a --calibrate run to a plain one.")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()

    import torch
    from vllm import LLM, SamplingParams
    from transformers import AutoTokenizer

    # Build ONE fixed prompt (same tokens for every dtype). REAL, non-repetitive text is REQUIRED:
    # tiling a short passage makes the tail a memorized loop -> bf16 PPL ~1.0 -> the relative delta
    # explodes for ANY perturbation (division by ~0) and the gate is meaningless. Default to wikitext-2
    # (the standard PPL benchmark); --text-file overrides; the built-in prose is a last resort and is
    # flagged INVALID because it must be tiled.
    tk = AutoTokenizer.from_pretrained(args.model)

    def _load_text():
        if args.text_file:
            with open(args.text_file, "r") as f:
                return f.read(), f"file:{args.text_file}"
        try:
            from datasets import load_dataset
            ds = load_dataset("wikitext", "wikitext-2-raw-v1", split="test")
            return "\n\n".join(t for t in ds["text"] if t.strip()), "wikitext-2-raw-v1"
        except Exception as e:
            print(f"  WARNING: could not load wikitext ({type(e).__name__}: {e}).\n"
                  "  Falling back to built-in prose, which must be TILED -> repetitive -> bf16 PPL ~1.0\n"
                  "  -> the delta metric is INVALID. Fix with:  pip install datasets   (or pass\n"
                  "  --text-file <a few thousand tokens of real held-out text>).")
            return _PROSE, "built-in prose (TILED — INVALID)"

    text, source = _load_text()
    full = tk(text)["input_ids"]
    # NEVER tile: repeating a short passage makes the tail a memorized loop -> degenerate baseline.
    # Cap the context to however much REAL text we have; a shorter valid test beats a long invalid one.
    eff_ctx = min(args.context_tokens, len(full))
    if eff_ctx < args.context_tokens:
        print(f"  NOTE: only {len(full)} real tokens available (< {args.context_tokens} requested) -> "
              f"measuring at ctx={eff_ctx} (still valid, just shallower). For a deeper long-context test, "
              "`pip install datasets` (wikitext) or pass a longer --text-file.")
    ids = full[:eff_ctx]
    prompt = tk.decode(ids)
    mml = eff_ctx + 64

    def _has_flashinfer():
        try:
            import flashinfer  # noqa: F401
            return True
        except Exception:
            return False

    def measure(dtype):
        # fp8 KV must run on FlashInfer (FA2 falls back to XFormers). prompt_logprobs are backend-agnostic
        # (they come from the LM-head logits), but the KV attention that feeds them uses this backend.
        if dtype.startswith("fp8"):
            if _has_flashinfer():
                os.environ["VLLM_ATTENTION_BACKEND"] = "FLASHINFER"
            else:
                print("  WARNING: flashinfer NOT installed -> fp8 will use XFormers; PPL still valid but "
                      "not the served path. `pip install flashinfer-python`")
        else:
            os.environ.pop("VLLM_ATTENTION_BACKEND", None)
        llm_kw = dict(model=args.model, max_model_len=mml, gpu_memory_utilization=args.gpu_util,
                      dtype="bfloat16", kv_cache_dtype=dtype, enforce_eager=True, max_num_seqs=1)
        if args.calibrate and dtype.startswith("fp8"):
            # runtime KV-scale calculation (vLLM 0.7.3+): rescues models whose KV outliers saturate the
            # default scale=1.0. Same lever bench_8bit_kv_gate.py used for fp8_e4m3.
            llm_kw["calculate_kv_scales"] = True
        llm = LLM(**llm_kw)
        try:
            blocks = llm.llm_engine.cache_config.num_gpu_blocks
        except Exception:
            blocks = None
        # prompt_logprobs=1 guarantees the actual token's logprob is returned at each position.
        out = llm.generate([prompt], SamplingParams(temperature=0.0, max_tokens=1, prompt_logprobs=1))[0]
        ptoks = list(out.prompt_token_ids)
        plps = out.prompt_logprobs or []
        n = len(ptoks)
        start = max(1, int(args.ppl_start_frac * n))
        nlls = []
        for i in range(start, n):
            d = plps[i] if i < len(plps) else None
            if not d:
                continue
            e = d.get(ptoks[i])
            if e is None:
                continue
            lp = getattr(e, "logprob", e)
            try:
                nlls.append(-float(lp))
            except (TypeError, ValueError):
                continue
        mean_nll = sum(nlls) / len(nlls) if nlls else float("inf")
        del llm
        torch.cuda.empty_cache()
        return {"ppl": perplexity(nlls), "nll": mean_nll, "n": len(nlls), "blocks": blocks}

    dtypes = [d.strip() for d in args.dtypes.split(",") if d.strip()]
    print(f"\nKV quality eval (perplexity) — {args.model.split('/')[-1]} ctx={eff_ctx} "
          f"tail>={args.ppl_start_frac:.0%}  source={source}")
    results = {}
    for dt in dtypes:
        r = measure(dt)
        results[dt] = r
        b = r["blocks"]
        calib = "[calib]" if (args.calibrate and dt.startswith("fp8")) else ""
        print(f"  {dt:<10}{calib:<8} PPL {r['ppl']:9.4f}  (NLL {r['nll']:.4f} nats/tok)  over {r['n']:>5} tok   "
              f"KV blocks {b if b is not None else '?':>7}")
    # Guard: a near-1.0 baseline means the text is too predictable (tiled/repetitive) -> the relative
    # delta is a division-by-~0 artifact, NOT a quality signal. Refuse to emit a verdict on it.
    base_ppl = results.get("auto", {}).get("ppl")
    if base_ppl is not None and not math.isinf(base_ppl) and base_ppl < 1.5:
        print("\n-- verdict --")
        print(f"  [INVALID] bf16 baseline PPL {base_ppl:.4f} < 1.5 -> text too predictable "
              "(tiled/repetitive).\n  The model memorizes it (NLL~0), so the relative delta explodes for "
              "any perturbation and says\n  NOTHING about fp8 quality. Re-run with real text: "
              "`pip install datasets` (wikitext default) or --text-file.")
        return 2
    print("\n-- verdict --")
    notes, fp8_ok = verdict(results)
    for nt in notes:
        print("  " + nt)
    print()
    if fp8_ok:
        print("fp8 quality OK (PPL within 1% of bf16) — with the 1.00x latency + 2x capacity already "
              "measured, fp8 clears every pre-registered gate as the SPEED tier. Final ship gate: a real "
              "task-accuracy eval (and calibrated scales only if a workload needs the last fraction).")
    else:
        print("fp8 PPL delta > 1% here (uncalibrated). Before ruling it out: (1) try --dtypes auto,fp8_e5m2, "
              "(2) add CALIBRATED kv scales, then re-measure. Only if calibrated fp8 still degrades is bf16 "
              "the speed path / int8-integer the fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
