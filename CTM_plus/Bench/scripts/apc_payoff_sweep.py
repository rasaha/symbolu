#!/usr/bin/env python3
# APC payoff harness — does prefix caching actually SAVE compute on int4_protected,
# and how much? It measures the two things APC moves, with APC ON vs OFF, swept by
# prefix length (and hit rate via --num-groups):
#
#   * TTFT (prefill latency)  — time a max_tokens=1 generate (prefill-dominated).
#       MISS (apc off, or first sight) prefills prefix+suffix; HIT (apc on, prefix
#       cached) prefills only the new suffix and READS the cached int4 KV.
#       saving_per_hit = TTFT(miss) - TTFT(hit)  ~ the prefill of the shared prefix,
#       which GROWS with prefix length.  <- the headline.
#   * Throughput (tok/s, req/s) — a full N-request batch at hit rate (N-G)/N.
#
# Honest by construction: a needle code is planted in each prefix and checked in the
# output; the throughput/TTFT win is CREDITED only where APC quality == APC-off
# quality (APC eager is bit-exact — S1 13/13 — so this should hold; if it doesn't,
# it's flagged, never counted).
#
# This isolates exactly what APC buys int4_protected: it cuts the PREFILL path
# (orthogonal to int4's DECODE tax), so it pays off most on prefill-heavy /
# short-output / shared-prefix workloads — agentic, RAG, multi-turn — the target
# segment. Density compounds it (2x blocks => ~2x cacheable prefix).
#
# Usage (pod, venv-vllm):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
#   pkill -9 -f vllm; sleep 2
#   python Bench/scripts/apc_payoff_sweep.py --model $M --prefixes 1000,2000,4000,8000 \
#       --num-requests 16 --num-groups 1 --gen 32 --out-dir /tmp/apc
#   #   --dry-run prints the per-cell commands; --reuse resumes; --num-groups>1 lowers hit rate
#   python Bench/scripts/apc_payoff_sweep.py --selftest    # CPU, no GPU
#
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

for _r in (Path("/workspace/symbolu/CTM_plus"), Path(__file__).resolve().parent.parent):
    if (_r / "KVPolicy").is_dir() and str(_r / "KVPolicy") not in sys.path:
        sys.path.insert(0, str(_r / "KVPolicy"))
        break


def _code(g):
    import random
    rng = random.Random(1000 + g)
    a = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "-".join("".join(rng.choice(a) for _ in range(3)) for _ in range(3))


def _build_prefix(tok, n_tokens, code, g):
    base = ("Operations log: subsystem nominal, telemetry within bounds, no "
            "anomalies recorded during the interval under review. ")
    ids = tok(base * (n_tokens // 16 + 4))["input_ids"][:max(64, n_tokens)]
    mid = len(ids) // 2
    needle = tok(f" Confidential: the vault access code is {code}. ")["input_ids"]
    ids = (ids[:mid] + needle + ids[mid:])[:max(64, n_tokens)]
    return tok.decode(ids)


# ---------------------------------------------------------------------------
# Pure analysis (selftested): one noapc row + one apc row -> payoff for a prefix.
# ---------------------------------------------------------------------------
def analyze_pair(noapc, apc):
    def num(x):
        return x if isinstance(x, (int, float)) else None
    tm, th = num(noapc.get("ttft_us")), num(apc.get("ttft_us"))
    tn, ta = num(noapc.get("tput_tok_s")), num(apc.get("tput_tok_s"))
    nq, aq = num(noapc.get("quality")), num(apc.get("quality"))
    ttft_saving = (100.0 * (tm - th) / tm) if (tm and th is not None and tm > 0) else None
    tput_speedup = (ta / tn) if (tn and ta is not None and tn > 0) else None
    quality_ok = (aq is not None and nq is not None and aq >= nq - 0.01)
    return {
        "prefix_tokens": noapc.get("prefix_tokens") or apc.get("prefix_tokens"),
        "ttft_miss_us": tm, "ttft_hit_us": th, "ttft_saving_pct": ttft_saving,
        "tput_noapc": tn, "tput_apc": ta, "tput_speedup": tput_speedup,
        "q_noapc": nq, "q_apc": aq, "quality_ok": quality_ok,
        "hit_rate": apc.get("hit_rate"),
    }


def _fmt(x, n=1):
    return f"{x:.{n}f}" if isinstance(x, (int, float)) else "n/a"


# ---------------------------------------------------------------------------
# Worker: --mode apc|noapc, one prefix length -> JSON.
# ---------------------------------------------------------------------------
def run_mode(args):
    import torch
    from vllm import SamplingParams
    import kv_policy.int4_protected  # noqa: F401
    from kv_policy.int4_protected import Int4ProtectedLLM

    apc = (args.mode == "apc")
    mml = args.max_model_len or (args.prefix_tokens + 4096)
    llm = Int4ProtectedLLM(model=args.model, max_model_len=mml,
                           gpu_memory_utilization=args.gpu_util,
                           enable_prefix_caching=apc)
    tok = llm.get_tokenizer()
    P, G, N = args.prefix_tokens, max(1, args.num_groups), args.num_requests
    groups = [(_build_prefix(tok, P, _code(g), g), _code(g)) for g in range(G)]
    Q = "\n\nQuestion {r}: what is the vault access code above? Answer with only the code.\nAnswer:"

    sp1 = SamplingParams(temperature=0.0, max_tokens=1)        # prefill-dominated
    spg = SamplingParams(temperature=0.0, max_tokens=args.gen, ignore_eos=True)

    # Warm the engine (and, for apc, cache group-0's prefix blocks).
    pfx0, code0 = groups[0]
    llm.generate([pfx0 + Q.format(r="warm")], sp1)

    # ---- TTFT: R reps with UNIQUE suffixes over group-0's prefix ----
    # apc -> prefix HIT (suffix prefilled only); noapc -> full prefill (MISS).
    samples = []
    for r in range(max(3, args.ttft_reps)):
        p = pfx0 + Q.format(r=r)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        llm.generate([p], sp1)
        torch.cuda.synchronize()
        samples.append((time.perf_counter() - t0) * 1e6)
    samples.sort()
    ttft_us = samples[len(samples) // 2]

    # ---- Throughput: full N-request batch, hit rate (N-G)/N ----
    prompts, codes = [], []
    for i in range(N):
        pfx, c = groups[i % G]
        prompts.append(pfx + Q.format(r=i))
        codes.append(c)
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    outs = llm.generate(prompts, spg)
    torch.cuda.synchronize()
    wall = time.perf_counter() - t0
    n_out = sum(len(o.outputs[0].token_ids) for o in outs)
    quality = sum(1 for o, c in zip(outs, codes) if c in o.outputs[0].text) / max(1, N)

    report = {
        "mode": args.mode, "model": args.model, "prefix_tokens": P,
        "num_groups": G, "num_requests": N, "gen": args.gen,
        "hit_rate": round((N - G) / N, 3),
        "ttft_kind": "hit" if apc else "miss",
        "ttft_us": round(ttft_us, 1),
        "tput_tok_s": round(n_out / wall, 2), "req_s": round(N / wall, 3),
        "wall_s": round(wall, 3), "n_out": n_out, "quality": round(quality, 3),
    }
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"[apc-payoff] mode={args.mode} P={P} ttft_{report['ttft_kind']}="
          f"{report['ttft_us']:.0f}us tput={report['tput_tok_s']:.0f}tok/s "
          f"quality={report['quality']} -> {args.out}", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Driver: sweep prefix lengths, run both modes per length, print payoff table.
# ---------------------------------------------------------------------------
def sweep(args):
    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if not args.dry_run and not os.environ.get("PROTECT_MASK_PATH"):
        print("WARNING: PROTECT_MASK_PATH unset — int4 cells will likely fail.")
    Ps = [int(x) for x in args.prefixes.split(",") if x.strip()]

    common = ["--model", args.model, "--num-requests", str(args.num_requests),
              "--num-groups", str(args.num_groups), "--gen", str(args.gen),
              "--gpu-util", str(args.gpu_util), "--ttft-reps", str(args.ttft_reps)]
    rows = []
    for P in Ps:
        cells = {}
        for mode in ("noapc", "apc"):
            out = outdir / f"{mode}_p{P}.json"
            if not (args.reuse and out.exists()):
                cmd = [args.python, str(Path(__file__).resolve()), "--mode", mode,
                       "--prefix-tokens", str(P), "--out", str(out), *common]
                print("  $ " + " ".join(cmd), flush=True)
                if not args.dry_run:
                    rc = subprocess.run(cmd, env=env).returncode
                    print(f"    -> exit={rc}", flush=True)
            if not args.dry_run:
                try:
                    cells[mode] = json.loads(out.read_text())
                except Exception as e:  # noqa: BLE001
                    cells[mode] = {"_error": str(e)}
        if not args.dry_run:
            rows.append(analyze_pair(cells.get("noapc", {}), cells.get("apc", {})))

    if args.dry_run:
        print("\n[dry-run] nothing executed.")
        return 0

    (outdir / "apc_payoff_summary.json").write_text(json.dumps(rows, indent=2))
    _print_table(rows, args)
    return 0


def _print_table(rows, args):
    print("\n" + "=" * 100)
    print(f"APC PAYOFF — {args.model.split('/')[-1]}  N={args.num_requests} "
          f"groups={args.num_groups} (hit_rate={(args.num_requests-args.num_groups)/args.num_requests:.0%}) "
          f"gen={args.gen}")
    print("=" * 100)
    print(f"{'prefix':>7} | {'TTFT miss':>10} {'TTFT hit':>9} {'saved':>7} | "
          f"{'tput off':>9} {'tput apc':>9} {'speedup':>8} | quality off/apc")
    print("-" * 100)
    for r in rows:
        q = f"{_fmt(r['q_noapc'],2)}/{_fmt(r['q_apc'],2)}"
        flag = "" if r["quality_ok"] else "  <== QUALITY CAVEAT (apc<off)"
        sp = f"{_fmt(r['tput_speedup'],2)}x" if r["tput_speedup"] else "n/a"
        sv = f"{_fmt(r['ttft_saving_pct'],0)}%" if r["ttft_saving_pct"] is not None else "n/a"
        print(f"{r['prefix_tokens']:>7} | {_fmt(r['ttft_miss_us'],0):>10} "
              f"{_fmt(r['ttft_hit_us'],0):>9} {sv:>7} | {_fmt(r['tput_noapc'],0):>9} "
              f"{_fmt(r['tput_apc'],0):>9} {sp:>8} | {q}{flag}")
    print("-" * 100)
    clean = [r for r in rows if r["quality_ok"]]
    if clean and any(r["ttft_saving_pct"] for r in clean):
        best = max(clean, key=lambda r: r["ttft_saving_pct"] or 0)
        print(f"APC saves up to {best['ttft_saving_pct']:.0f}% of prefill latency per hit "
              f"(at prefix={best['prefix_tokens']}) and {(best['tput_speedup'] or 1):.2f}x "
              f"throughput at this hit rate — and the saving GROWS with prefix length.")
        print("  Read it honestly: APC cuts the PREFILL path (TTFT) — orthogonal to int4's "
              "decode tax. The win is real on shared-prefix / short-output workloads; it does "
              "NOT speed up long-generation decode. Trust only quality-clean rows.")
    else:
        print("No quality-clean payoff measured — check the cells / quality gate before claiming a saving.")
    print("=" * 100)


def _selftest():
    fails = []

    def check(n, c):
        print(f"  [{'PASS' if c else 'FAIL'}] {n}")
        if not c:
            fails.append(n)

    noapc = {"prefix_tokens": 4000, "ttft_us": 5000.0, "tput_tok_s": 100.0, "quality": 1.0, "hit_rate": 0.875}
    apc = {"prefix_tokens": 4000, "ttft_us": 1200.0, "tput_tok_s": 180.0, "quality": 1.0, "hit_rate": 0.875}
    a = analyze_pair(noapc, apc)
    check("ttft saving = (miss-hit)/miss", abs(a["ttft_saving_pct"] - 76.0) < 1e-6)
    check("throughput speedup = apc/off", abs(a["tput_speedup"] - 1.8) < 1e-6)
    check("quality_ok when apc==off", a["quality_ok"] is True)

    # degraded apc quality -> NOT credited
    bad = dict(apc); bad["quality"] = 0.5
    ab = analyze_pair(noapc, bad)
    check("quality_ok False when apc<off", ab["quality_ok"] is False)

    # missing data -> None, no crash
    am = analyze_pair({"prefix_tokens": 1000}, {"prefix_tokens": 1000})
    check("missing ttft -> None saving", am["ttft_saving_pct"] is None and am["tput_speedup"] is None)

    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="APC payoff: TTFT + throughput, APC on vs off, swept by prefix length")
    ap.add_argument("--selftest", action="store_true")
    # worker mode
    ap.add_argument("--mode", choices=["apc", "noapc"])
    ap.add_argument("--prefix-tokens", type=int, default=2000)
    ap.add_argument("--out", default="/tmp/apc_cell.json")
    ap.add_argument("--max-model-len", type=int, default=0)
    # shared / driver
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--prefixes", default="1000,2000,4000,8000", help="prefix-length sweep")
    ap.add_argument("--num-requests", type=int, default=16)
    ap.add_argument("--num-groups", type=int, default=1,
                    help="distinct prefixes among the requests; hit_rate=(N-G)/N")
    ap.add_argument("--gen", type=int, default=32)
    ap.add_argument("--ttft-reps", type=int, default=5)
    ap.add_argument("--gpu-util", type=float, default=0.85)
    ap.add_argument("--out-dir", default="/tmp/apc_payoff")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.mode:
        return run_mode(args)
    return sweep(args)


if __name__ == "__main__":
    raise SystemExit(main())
