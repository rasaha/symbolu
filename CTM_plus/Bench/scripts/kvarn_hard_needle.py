#!/usr/bin/env python3
# KVarN HARD-needle eval -- the long-context hard tail KVarN's 0.98 free-gen number
# does NOT cover. Run in venv-kvarn (vLLM 0.22.0).
#
# WHY: kvarn_eval.py measured 4K free-gen agreement (0.9818 on Llama). That is the
# EASY regime. int4_protected earns its keep on the HARD tail -- long context + a
# needle the model must selectively retrieve, the regime where Qwen-1M broke. This
# script measures KVarN there.
#
# HOW (the key design choice): it REUSES phase6k12_hard_needle's build_item +
# classify + MODES verbatim -- the exact same haystack construction, the same 4
# adversarial modes (multi / distractor / conflict / qa), the same failure-bucket
# classifier (HIT / NEAR_V / MISS_K / COLLAPSE / FORMAT), and the SAME rng seed
# (1234). So at a given --mml the needles are byte-identical to the ones
# int4_protected was validated on, and KVarN's retrieval_accuracy drops straight
# into the same table as protect's. The ONLY thing that changes is the engine cell:
#   bf16   -- full-precision KV in vLLM 0.22 (the shared anchor)
#   kvarn  -- kvarn_k4v2_g128 in vLLM 0.22 (same LLM(...) call that made the 0.9818)
#
# Cross-stack caveat: this is vLLM 0.22 (V1); int4_protected's table is 0.7.3 (V0).
# bf16 is the shared anchor -- compare KVarN's GAP-to-bf16 here against protect's
# GAP-to-bf16 there, not the absolutes. If KVarN's bf16 anchor tracks the 0.7.3
# bf16 at the same mml, the comparison is sound.
#
# Usage (venv-kvarn):
#   python kvarn_hard_needle.py --selftest                         # CPU, no model
#   # apples-to-apples vs int4_protected's canonical table:
#   python kvarn_hard_needle.py --mml 8192  --items 6 --model NousResearch/Meta-Llama-3.1-8B-Instruct
#   # the HARD tail the 0.98 free-gen number does not cover:
#   python kvarn_hard_needle.py --mml 32768 --items 4 --model NousResearch/Meta-Llama-3.1-8B-Instruct
#   # single cell (debug):
#   CELL=kvarn python kvarn_hard_needle.py --worker --mml 8192 --items 6 --model <M>
#
# NB Qwen2.5-7B CRASHES under KVarN (GQA 28/4=7 not power-of-2 -> tl.arange). Use a
# power-of-2-GQA model: Llama-3.1 (32/8=4), Mistral (32/8=4).

import argparse
import json
import os
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Reuse the CANONICAL hard-needle harness verbatim (pure stdlib at import time --
# no torch/vllm pulled in, verified). Same needles + same scoring as the
# int4_protected validation, so the rows line up.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase6k12_hard_needle import build_item, classify, MODES  # noqa: E402

CELLS = ["bf16", "kvarn"]
DEFAULT_MODEL = "NousResearch/Meta-Llama-3.1-8B-Instruct"


# ----------------------------------------------------------------------- worker
def run_worker(args):
    cell = os.environ.get("CELL", "kvarn")
    from vllm import LLM, SamplingParams
    import vllm

    kw = dict(model=args.model, dtype="float16",
              gpu_memory_utilization=args.gpu_util,
              max_model_len=args.mml, max_num_seqs=args.max_num_seqs)
    if cell == "kvarn":
        kw["kv_cache_dtype"] = args.kvarn_dtype
        kw["block_size"] = args.block_size
    cdt = kw.get("kv_cache_dtype", "auto")
    print(f"[kvarn-needle {cell}] vllm={vllm.__version__} kv_cache_dtype={cdt} "
          f"mml={args.mml} model={args.model}", flush=True)
    llm = LLM(**kw)

    sp = SamplingParams(temperature=0.0, max_tokens=16)   # greedy, short answer
    rng = random.Random(1234)                             # SAME seed as 6k12
    buckets = defaultdict(lambda: defaultdict(int))
    samples, qa_outputs = [], []
    try:
        tok = llm.get_tokenizer()
    except Exception:
        tok = None
    _logged = False

    for mode in MODES:
        for _ in range(args.items):
            # IDENTICAL call to phase6k12: prompt ~= mml//2 tokens, needle buried.
            prompt, expected, distractors, _ = build_item(mode, args.mml // 2, rng)
            if not _logged and tok is not None:
                try:
                    plen = len(tok.encode(prompt))
                    print(f"[kvarn-needle {cell}] first prompt ~= {plen} tok "
                          f"(mml={args.mml}, gen={sp.max_tokens}, "
                          f"headroom={args.mml - plen - sp.max_tokens})", flush=True)
                except Exception:
                    pass
                _logged = True
            try:
                text = llm.generate([prompt], sp)[0].outputs[0].text
            except Exception as e:
                buckets[mode]["ERROR"] += 1
                if len(samples) < 8:
                    samples.append({"mode": mode, "expected": expected,
                                    "bucket": "ERROR", "out": str(e)[:70]})
                continue
            b = classify(text, expected, distractors, mode)
            buckets[mode][b] += 1
            if mode == "qa":
                qa_outputs.append({"expected": expected, "distractors": distractors,
                                   "bucket": b, "output": text})
            if len(samples) < 8:
                samples.append({"mode": mode, "expected": expected,
                                "bucket": b, "out": text[:60]})

    n_total = args.items * len(MODES)
    tot = {k: sum(buckets[m].get(k, 0) for m in MODES)
           for k in ("HIT", "NEAR_V", "MISS_K", "COLLAPSE", "FORMAT", "ERROR")}
    n_hit, n_format = tot["HIT"], tot["FORMAT"]
    summary = {
        "cell": cell, "vllm": vllm.__version__, "model": args.model,
        "kv_cache_dtype": cdt, "mml": args.mml, "items_per_mode": args.items,
        "n_total": n_total,
        # SAME three metrics phase6k12 reports, so rows line up exactly.
        "strict_accuracy": round(n_hit / max(1, n_total), 3),
        "retrieval_accuracy": round(n_hit / max(1, n_total - n_format), 3),
        "retrieved_or_present_accuracy": round((n_hit + n_format) / max(1, n_total), 3),
        "buckets": {m: dict(buckets[m]) for m in MODES},
        "totals": tot, "qa_outputs": qa_outputs, "samples": samples,
    }
    out = os.environ.get("OUTPUT", f"/tmp/kvarn_needle_{cell}_mml{args.mml}.json")
    Path(out).write_text(json.dumps(summary, indent=2))
    print(f"\n[kvarn-needle {cell} mml{args.mml}] "
          f"strict={summary['strict_accuracy']} "
          f"retrieval={summary['retrieval_accuracy']} "
          f"ret+p={summary['retrieved_or_present_accuracy']} totals={tot}")
    for m in MODES:
        print(f"    {m:10s}: {dict(buckets[m])}")
    print(f"[kvarn-needle] wrote {out}", flush=True)
    return 0


# ----------------------------------------------------------------------- driver
def run_driver(args):
    rows = []
    for cell in CELLS:
        out = f"/tmp/kvarn_needle_{cell}_mml{args.mml}.json"
        env = dict(os.environ)
        env.update({"CELL": cell, "OUTPUT": out})
        print(f"\n=== kvarn-needle driver: cell={cell} mml={args.mml} "
              f"model={args.model} ===", flush=True)
        subprocess.run([sys.executable, __file__, "--worker",
                        "--mml", str(args.mml), "--items", str(args.items),
                        "--model", args.model, "--gpu-util", str(args.gpu_util),
                        "--max-num-seqs", str(args.max_num_seqs),
                        "--block-size", str(args.block_size),
                        "--kvarn-dtype", args.kvarn_dtype],
                       env=env, check=False)
        try:
            rows.append(json.loads(Path(out).read_text()))
        except Exception as e:
            rows.append({"cell": cell, "error": str(e)[:60]})

    print("\n" + "=" * 96)
    print(f"KVarN HARD needle (mml={args.mml}, {args.items}/mode, {len(MODES)} modes, "
          f"{args.model})")
    print("  -- same build_item/classify/seed as phase6k12; bf16 = shared anchor --")
    print("=" * 96)
    print("  strict   = HIT / total                 (FORMAT counts AGAINST)")
    print("  retrieval= HIT / (total - FORMAT)       (FORMAT EXCLUDED as ambiguous)")
    print("  ret+p    = (HIT+FORMAT) / total         (FORMAT adjudicated as retrieved)")
    print(f"  {'cell':>8} | {'strict':>6} {'retr':>6} {'ret+p':>6} | {'HIT':>4} "
          f"{'NEAR_V':>6} {'MISS_K':>6} {'COLLAPSE':>8} {'FORMAT':>6} {'ERROR':>5}")
    print("  " + "-" * 86)
    retr_a = {}
    for r in rows:
        if "error" in r:
            print(f"  {r.get('cell','?'):>8} | ERROR {r['error']}")
            continue
        t = r["totals"]
        retr_a[r["cell"]] = r["retrieval_accuracy"]
        print(f"  {r['cell']:>8} | {r['strict_accuracy']:>6.3f} "
              f"{r['retrieval_accuracy']:>6.3f} "
              f"{(r.get('retrieved_or_present_accuracy') or 0):>6.3f} | "
              f"{t['HIT']:>4} {t['NEAR_V']:>6} {t['MISS_K']:>6} {t['COLLAPSE']:>8} "
              f"{t['FORMAT']:>6} {t.get('ERROR',0):>5}")
    if "bf16" in retr_a and "kvarn" in retr_a:
        gap = retr_a["kvarn"] - retr_a["bf16"]
        print(f"\n  kvarn-bf16 retrieval gap = {gap:+.3f}   "
              f"(0.00 => KVarN keeps the hard tail; negative => it loses it)")
    print("  NEAR_V-heavy => V-bound; MISS_K-heavy => K-bound; COLLAPSE => degeneration.")
    print("=" * 96, flush=True)
    return 0


def _selftest():
    # Pure-CPU: confirms the cross-import is intact and the harness is wired.
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("kvarn_hard_needle selftest")
    check("MODES reused from phase6k12", MODES == ["multi", "distractor", "conflict", "qa"])
    check("cells = bf16 + kvarn", CELLS == ["bf16", "kvarn"])
    rng = random.Random(1234)
    pr, exp, dis, tag = build_item("distractor", 4096, rng)
    check("build_item returns a needle prompt", "Question:" in pr and bool(exp))
    check("classify HIT on expected", classify(f" The code is {exp}.", exp, dis, "distractor") == "HIT")
    check("classify MISS on filler",
          classify(" Routine operations continued.", exp, dis, "distractor") in ("MISS_K", "NEAR_V"))
    # determinism: same seed -> same first needle (so bf16 & kvarn see identical items)
    r1, r2 = random.Random(1234), random.Random(1234)
    e1 = build_item("multi", 4096, r1)[1]
    e2 = build_item("multi", 4096, r2)[1]
    check("seed 1234 deterministic across cells", e1 == e2)
    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVarN hard-needle eval (vLLM 0.22, reuses phase6k12)")
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--mml", type=int, default=8192)
    ap.add_argument("--items", type=int, default=6, help="items per mode")
    ap.add_argument("--kvarn-dtype", default="kvarn_k4v2_g128")
    ap.add_argument("--block-size", type=int, default=128)
    ap.add_argument("--gpu-util", type=float, default=0.85)
    ap.add_argument("--max-num-seqs", type=int, default=8)
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.worker:
        return run_worker(args)
    return run_driver(args)


if __name__ == "__main__":
    raise SystemExit(main())
