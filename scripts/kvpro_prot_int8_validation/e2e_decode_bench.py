"""KVPro prot-int8 — END-TO-END decode B vs C benchmark (POD-ONLY, real vLLM int4_protected path).

Answers the narrow question: does INT8 protected sidecar (C) change REAL end-to-end decode speed
vs BF16 protected sidecar (B), holding everything else identical?

  B = INT4 main KV + BF16 protected sidecar  (INT4_PROTECTED_PROT_INT8 unset)
  C = INT4 main KV + INT8 protected sidecar  (INT4_PROTECTED_PROT_INT8=1)

Drives the PRODUCTION path: Int4ProtectedLLM (vLLM + the forked flash_attn_with_int4_kvcache decode
kernel). NOT fake-quant, NOT the isolated read-path microbench. One vLLM engine per process (cell),
to avoid cross-engine global-state leakage — mirrors phase6n_prot_int8_gate.py's --cell off/on pattern.

Prefill/decode separation WITHOUT vLLM internals: differential timing.
  t1 = generate(max_tokens=1)   ~= prefill + 1 token  (TTFT)
  tN = generate(max_tokens=N)   ~= prefill + N tokens
  decode_time = tN - t1 ;  decode_tokens = (N-1)*batch ;  decode_tps = decode_tokens / decode_time
Output length is PINNED (min_tokens=N, ignore_eos=True) so B and C do identical decode work.

Confounder guards (reported, not hidden):
  - prot_int8 active-layer count: C must be active==total (else silent bf16 fallback = fake result).
  - call_stats: decode_calls_packed>0 and decode_calls_fallback==0 for BOTH (the fused kernel fired).
  - enforce_eager setting recorded (CUDA-graph mode is a separate axis).

Usage (pod), one cell per process then compare:
  P=/workspace/venv-vllm/bin/python3
  $P e2e_decode_bench.py --cell off --model /workspace/models/mistral-7b-instruct-v0.3 \
       --mask "$PROTECT_MASK_PATH" --out artifacts/prot_int8_speed/raw_B.json
  $P e2e_decode_bench.py --cell on  --model /workspace/models/mistral-7b-instruct-v0.3 \
       --mask "$PROTECT_MASK_PATH" --out artifacts/prot_int8_speed/raw_C.json
  $P e2e_decode_bench.py --compare artifacts/prot_int8_speed/raw_B.json artifacts/prot_int8_speed/raw_C.json \
       --outdir artifacts/prot_int8_speed/
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
import time
from pathlib import Path

PROT_ENV = "INT4_PROTECTED_PROT_INT8"
NEUTRAL_BAND = 0.03           # +/-3% engineering gate (stated, not a universal law)

# Test matrix (kept modest so a full B+C sweep fits a session; widen via CLI).
CONTEXT_LENS = [512, 2048, 8192]
GEN_TOKENS = [64, 256]
BATCH_SIZES = [1, 4, 8]
PROMPTS = {
    "factual":   "The capital of Australia is",
    "summarize": "Summarize the following in one sentence: The field report logged a measurement, "
                 "a checksum, and a timestamp before the shift change, then the operator signed off. ",
    "code":      "def fibonacci(n):\n    # return the n-th Fibonacci number\n",
    "arithmetic":"Compute 347 + 589 step by step. ",
    "retrieval": "The access code is 7F3-QX9. Remember it. ",
    "repeated":  "na na na na ",
}
_FILLER = ("The field report logged a measurement, a checksum, and a timestamp "
           "before the shift change. ")


def _pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def _stats(xs):
    if not xs:
        return {}
    m = st.mean(xs)
    sd = st.pstdev(xs) if len(xs) > 1 else 0.0
    ci = 1.96 * sd / (len(xs) ** 0.5) if len(xs) > 1 else 0.0
    return {"mean": m, "median": st.median(xs), "std": sd, "p95": _pct(xs, 0.95),
            "ci95": ci, "cv_pct": (100.0 * sd / m) if m else 0.0, "n": len(xs)}


def _build_prompt(tokenizer, ctx_len, seed_text):
    """Build a prompt of ~ctx_len tokens: seed + filler repeated, truncated to ctx_len tokens."""
    text = seed_text + _FILLER * (max(1, ctx_len // 12))
    ids = tokenizer(text).input_ids
    if len(ids) < ctx_len:
        ids = (ids * (ctx_len // max(1, len(ids)) + 1))[:ctx_len]
    else:
        ids = ids[:ctx_len]
    return ids


def run_cell(args):
    import torch
    from vllm import SamplingParams
    from vllm.inputs import TokensPrompt
    from kv_policy.int4_protected import Int4ProtectedLLM, get_backend_info
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    sys.path.insert(0, str(Path(args.model_scripts)))
    from phase6n_prot_int8_gate import _prot_int8_layer_counts

    if args.cell == "on":
        os.environ[PROT_ENV] = "1"
    else:
        os.environ.pop(PROT_ENV, None)
    os.environ["PROTECT_MASK_PATH"] = args.mask

    tok_import = __import__("transformers").AutoTokenizer.from_pretrained(args.model)

    llm = Int4ProtectedLLM(model=args.model, max_model_len=args.max_model_len,
                           gpu_memory_utilization=args.gpu_mem_util,
                           enforce_eager=args.enforce_eager)
    info = get_backend_info(llm)
    active, total = _prot_int8_layer_counts(llm)
    gpu = torch.cuda.get_device_name(0)

    # Confounder guard: ON must be fully active; OFF must be fully inactive.
    guard_ok = (active == total and total > 0) if args.cell == "on" else (active == 0)

    matrix, raw = [], []
    quality = []
    for ctx in args.context_lens:
        for batch in args.batch_sizes:
            ids = _build_prompt(tok_import, ctx, PROMPTS["retrieval"])
            prompts = [TokensPrompt(prompt_token_ids=list(ids)) for _ in range(batch)]
            for N in args.gen_tokens:
                sp1 = SamplingParams(temperature=0.0, max_tokens=1, min_tokens=1, ignore_eos=True)
                spN = SamplingParams(temperature=0.0, max_tokens=N, min_tokens=N, ignore_eos=True)

                for _ in range(args.warmup):
                    llm.generate(prompts, spN, use_tqdm=False)
                torch.cuda.synchronize()

                t1s, tNs = [], []
                Int4ProtectedAttentionImpl.reset_call_stats()
                torch.cuda.reset_peak_memory_stats()
                for _ in range(args.iters):
                    torch.cuda.synchronize(); a = time.perf_counter()
                    llm.generate(prompts, sp1, use_tqdm=False)
                    torch.cuda.synchronize(); t1s.append(time.perf_counter() - a)
                    torch.cuda.synchronize(); a = time.perf_counter()
                    outN = llm.generate(prompts, spN, use_tqdm=False)
                    torch.cuda.synchronize(); tNs.append(time.perf_counter() - a)
                stats_calls = Int4ProtectedAttentionImpl.get_call_stats()
                peak = torch.cuda.max_memory_allocated()
                reserved = torch.cuda.memory_reserved()

                ttft = _stats(t1s)
                tot = _stats(tNs)
                dec_times = [max(1e-9, tn - t1) for tn, t1 in zip(tNs, t1s)]
                dec_tps = [((N - 1) * batch) / dt for dt in dec_times]
                dstat = _stats(dec_times)
                tps = _stats(dec_tps)
                # per-token decode latency (ms)
                lat_ms = [1000.0 * dt / ((N - 1) * batch) for dt in dec_times]
                lstat = _stats(lat_ms)

                row = {
                    "cell": args.cell, "context_len": ctx, "batch": batch, "gen_tokens": N,
                    "ttft_s_mean": ttft["mean"], "ttft_s_median": ttft["median"],
                    "total_s_mean": tot["mean"],
                    "decode_s_mean": dstat["mean"], "decode_s_median": dstat["median"],
                    "decode_lat_ms_per_tok_mean": lstat["mean"], "decode_lat_ms_p95": lstat["p95"],
                    "decode_tps_mean": tps["mean"], "decode_tps_median": tps["median"],
                    "decode_tps_ci95": tps["ci95"], "decode_tps_cv_pct": tps["cv_pct"],
                    "peak_mem_bytes": peak, "reserved_mem_bytes": reserved,
                    "decode_calls_packed": stats_calls.get("decode_calls_packed", 0),
                    "decode_calls_fallback": stats_calls.get("decode_calls_fallback", 0),
                    "write_path_calls": stats_calls.get("write_path_calls", 0),
                    "write_path_fallback": stats_calls.get("write_path_fallback", 0),
                }
                matrix.append(row)
                raw.append({"cell": args.cell, "context_len": ctx, "batch": batch, "gen_tokens": N,
                            "t1_s": t1s, "tN_s": tNs})
                # quality sanity (one capture per point at batch position 0)
                txt = outN[0].outputs[0].text
                ntok = len(outN[0].outputs[0].token_ids)
                quality.append({"cell": args.cell, "context_len": ctx, "batch": batch,
                                "gen_tokens": N, "out_tokens": ntok, "text_head": txt[:80]})
                print(f"[{args.cell}] ctx={ctx} b={batch} N={N}  decode_tps={tps['mean']:.1f} "
                      f"(cv {tps['cv_pct']:.1f}%)  ttft={ttft['mean']*1000:.1f}ms  "
                      f"packed={row['decode_calls_packed']} fb={row['decode_calls_fallback']} "
                      f"wfb={row['write_path_fallback']}")

    out = {
        "cell": args.cell, "gpu": gpu, "model": args.model, "mask": args.mask,
        "enforce_eager": args.enforce_eager, "max_model_len": args.max_model_len,
        "prot_int8_active": active, "prot_int8_total": total, "guard_ok": guard_ok,
        "backend_marker": info.get("marker"), "layers_swapped": info.get("layers_swapped"),
        "iters": args.iters, "warmup": args.warmup,
        "matrix": matrix, "raw": raw, "quality": quality,
        "versions": _versions(),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\nwrote {args.out}  (guard_ok={guard_ok}, active={active}/{total})")
    if not guard_ok:
        print("[WARN] confounder guard FAILED — result is NOT a clean B/C isolation.", file=sys.stderr)
    return 0


def _versions():
    v = {}
    for mod in ("torch", "vllm", "transformers"):
        try:
            v[mod] = __import__(mod).__version__
        except Exception:
            v[mod] = "unknown"
    try:
        import torch
        v["cuda"] = torch.version.cuda
        v["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return v


def compare(args):
    import csv
    B = json.loads(Path(args.compare[0]).read_text())
    C = json.loads(Path(args.compare[1]).read_text())
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    def key(r):
        return (r["context_len"], r["batch"], r["gen_tokens"])
    Bm = {key(r): r for r in B["matrix"]}
    Cm = {key(r): r for r in C["matrix"]}

    rows, verdicts = [], []
    for k in sorted(Bm.keys() & Cm.keys()):
        b, c = Bm[k], Cm[k]
        sr = c["decode_tps_mean"] / b["decode_tps_mean"] if b["decode_tps_mean"] else float("nan")
        lr = c["decode_lat_ms_per_tok_mean"] / b["decode_lat_ms_per_tok_mean"] if b["decode_lat_ms_per_tok_mean"] else float("nan")
        # CI overlap on decode_tps: does C's interval exclude B's mean?
        c_lo, c_hi = c["decode_tps_mean"] - c["decode_tps_ci95"], c["decode_tps_mean"] + c["decode_tps_ci95"]
        excludes_parity = not (c_lo <= b["decode_tps_mean"] <= c_hi)
        delta = sr - 1.0
        if abs(delta) <= NEUTRAL_BAND or not excludes_parity:
            v = "NEUTRAL"
        elif delta > NEUTRAL_BAND:
            v = "FASTER"
        else:
            v = "SLOWER"
        noisy = (b["decode_tps_cv_pct"] > 5.0 or c["decode_tps_cv_pct"] > 5.0)
        verdicts.append(v)
        rows.append({
            "context_len": k[0], "batch": k[1], "gen_tokens": k[2],
            "B_decode_tps": round(b["decode_tps_mean"], 2), "C_decode_tps": round(c["decode_tps_mean"], 2),
            "speed_ratio_C_over_B": round(sr, 4), "decode_delta_pct": round(100 * delta, 2),
            "latency_ratio_C_over_B": round(lr, 4),
            "B_ttft_ms": round(b["ttft_s_mean"] * 1000, 2), "C_ttft_ms": round(c["ttft_s_mean"] * 1000, 2),
            "B_cv_pct": round(b["decode_tps_cv_pct"], 2), "C_cv_pct": round(c["decode_tps_cv_pct"], 2),
            "ci_excludes_parity": excludes_parity, "noisy_gt5pct": noisy, "point_verdict": v,
            "B_peak_mem_MiB": round(b["peak_mem_bytes"] / 2**20, 1),
            "C_peak_mem_MiB": round(c["peak_mem_bytes"] / 2**20, 1),
            "B_packed": b["decode_calls_packed"], "C_packed": c["decode_calls_packed"],
            "B_fallback": b["decode_calls_fallback"], "C_fallback": c["decode_calls_fallback"],
            "C_write_fallback": c["write_path_fallback"],
        })

    with open(outdir / "benchmark_matrix.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    # overall verdict
    ratios = [r["speed_ratio_C_over_B"] for r in rows]
    mean_ratio = sum(ratios) / len(ratios)
    uniq = set(verdicts)
    if uniq == {"NEUTRAL"}:
        overall = "C NEUTRAL TO B"
    elif uniq <= {"SLOWER", "NEUTRAL"} and "SLOWER" in uniq:
        overall = "C SLOWER THAN B"
    elif uniq <= {"FASTER", "NEUTRAL"} and "FASTER" in uniq:
        overall = "C FASTER THAN B"
    else:
        overall = "MIXED BY WORKLOAD"
    guard = B.get("guard_ok") and C.get("guard_ok")
    if not guard:
        overall += " (CONFOUNDER: prot_int8 activation guard failed — see raw JSON)"
    summary = {
        "overall_verdict": overall, "mean_speed_ratio_C_over_B": round(mean_ratio, 4),
        "mean_decode_delta_pct": round(100 * (mean_ratio - 1), 2),
        "neutral_band_pct": NEUTRAL_BAND * 100,
        "B_guard_ok": B.get("guard_ok"), "C_guard_ok": C.get("guard_ok"),
        "B_prot_int8_active": f"{B.get('prot_int8_active')}/{B.get('prot_int8_total')}",
        "C_prot_int8_active": f"{C.get('prot_int8_active')}/{C.get('prot_int8_total')}",
        "enforce_eager": C.get("enforce_eager"),
        "any_decode_fallback": any(r["B_fallback"] or r["C_fallback"] for r in rows),
        "any_C_write_fallback": any(r["C_write_fallback"] for r in rows),
        "versions": C.get("versions"), "points": len(rows),
        "per_point_verdicts": {f"{r['context_len']}/{r['batch']}/{r['gen_tokens']}": r["point_verdict"] for r in rows},
    }
    (outdir / "profiler_summary.json").write_text(json.dumps(summary, indent=2))
    # raw timings jsonl
    with open(outdir / "raw_timings.jsonl", "w") as f:
        for cell in (B, C):
            for r in cell["raw"]:
                f.write(json.dumps(r) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"\nwrote benchmark_matrix.csv, profiler_summary.json, raw_timings.jsonl -> {outdir}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="End-to-end decode B vs C benchmark (real int4_protected)")
    ap.add_argument("--cell", choices=["off", "on"], help="off=B (bf16 protect), on=C (int8 protect)")
    ap.add_argument("--compare", nargs=2, metavar=("RAW_B", "RAW_C"))
    ap.add_argument("--model", default="/workspace/models/mistral-7b-instruct-v0.3")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--model-scripts", default="/workspace/symbolu/CTM_plus/Bench/scripts")
    ap.add_argument("--max-model-len", type=int, default=16384)
    ap.add_argument("--gpu-mem-util", type=float, default=0.85)
    ap.add_argument("--enforce-eager", action="store_true", default=True)
    ap.add_argument("--no-enforce-eager", dest="enforce_eager", action="store_false")
    ap.add_argument("--context-lens", default=",".join(map(str, CONTEXT_LENS)))
    ap.add_argument("--gen-tokens", default=",".join(map(str, GEN_TOKENS)))
    ap.add_argument("--batch-sizes", default=",".join(map(str, BATCH_SIZES)))
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--out", default="artifacts/prot_int8_speed/raw_cell.json")
    ap.add_argument("--outdir", default="artifacts/prot_int8_speed")
    args = ap.parse_args(argv)
    args.context_lens = [int(x) for x in str(args.context_lens).split(",")]
    args.gen_tokens = [int(x) for x in str(args.gen_tokens).split(",")]
    args.batch_sizes = [int(x) for x in str(args.batch_sizes).split(",")]

    if args.compare:
        return compare(args)
    if args.cell is None:
        ap.error("provide --cell off|on (one engine per process) or --compare RAW_B RAW_C")
    if not args.mask or not os.path.isfile(args.mask):
        print(f"[FAIL] mask missing: {args.mask!r}", file=sys.stderr); return 3
    return run_cell(args)


if __name__ == "__main__":
    raise SystemExit(main())
