#!/usr/bin/env python3
# Phase 10 — int4+read-skip vs bf16 throughput CROSSOVER sweep (above 32K).
#
# The open question the VC brief cannot yet answer: does int4_protected, with
# read-skip, *cross* bf16 decode throughput in the long-context regime — and at
# what context length? Prior runs stopped at 32K (Qwen-7B's native window) and
# showed only the int4-vs-bf16 ratio NARROWING (0.56x@8K -> 0.67x@32K), never
# crossing. This driver answers it directly above 32K.
#
# It produces THREE curves on one axis at each context point, reusing the
# validated harness `phase9_p3_fused_needle.py` so nothing drifts:
#   * bf16            (vanilla vLLM)                 <- the bar to beat
#   * full-int4       (read-skip OFF, mode=off)      <- expected to plateau ~0.7x
#   * int4+read-skip  (read-skip ON, mode=retention) <- the lever that can cross
# ...with the needle hit-rate reported ALONGSIDE throughput at every cell.
#
# Honest by construction:
#   * The crossover is only credited where read-skip quality is NOT degraded vs
#     bf16 (a throughput win on broken output is flagged, never counted).
#   * The int4-quant-alone curve sits next to read-skip so "the quant plateaus,
#     read-skip is what crosses (or doesn't)" is self-evident in the data.
#
# Vehicle: Llama-3.1-8B-Instruct is 128K-native -> sweep 32-60K with NO YaRN/rope
# hacks (and its int4-KV long-context quality already held 1.0/1.0 to 60K).
#
# Usage (pod, venv-vllm):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
#   pkill -9 -f vllm; sleep 2
#   python Bench/scripts/phase10_crossover_sweep.py --model $M \
#       --contexts 32000,44000,52000,60000 --gen 128 --plot --out-dir /tmp/x10
#   #   add --dry-run first to print the exact per-cell commands without running
#   #   add --reuse to resume a partial sweep (skips cells whose JSON exists)
#   python Bench/scripts/phase10_crossover_sweep.py --selftest   # CPU, no GPU
#
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HARNESS_DEFAULT = str(Path(__file__).resolve().parent / "phase9_p3_fused_needle.py")
EPS = 1e-9


def _run(cmd, env, dry):
    print("  $ " + " ".join(cmd), flush=True)
    if dry:
        return 0
    t0 = time.time()
    rc = subprocess.run(cmd, env=env).returncode
    print(f"  -> exit={rc} ({time.time() - t0:.0f}s)", flush=True)
    return rc


def _load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{type(e).__name__}: {e}"}


def _min_quality(hit_by_depth):
    if not hit_by_depth:
        return None
    try:
        return min(float(v) for v in hit_by_depth.values())
    except Exception:  # noqa: BLE001
        return None


def _ratio(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b:
        return a / b
    return None


def _fmt(x, n=2):
    return f"{x:.{n}f}" if isinstance(x, (int, float)) else "n/a"


def analyze(rows):
    """Pure: rows -> (raw_crossover, valid_crossover, table_lines). Selftested."""
    raw_crossover = valid_crossover = None
    lines = []
    for row in rows:
        ri = _ratio(row.get("int4_tps"), row.get("bf_tps"))
        rr = _ratio(row.get("rs_tps"), row.get("bf_tps"))
        bf_q, rs_q = row.get("bf_q"), row.get("rs_q")
        q_ok = (isinstance(rs_q, (int, float)) and isinstance(bf_q, (int, float))
                and rs_q >= bf_q - 1e-3)
        if rr is not None and rr >= 1.0:
            if raw_crossover is None:
                raw_crossover = row["ctx"]
            if q_ok and valid_crossover is None:
                valid_crossover = row["ctx"]
        qflag = ""
        if (isinstance(rs_q, (int, float)) and isinstance(bf_q, (int, float))
                and rs_q < bf_q - 1e-3):
            qflag = "  <== QUALITY CAVEAT (read-skip < bf16)"
        skip = row.get("skip")
        lines.append(
            f"{row['ctx']:>7} | {_fmt(row.get('bf_tps')):>9} | "
            f"{_fmt(row.get('int4_tps')):>9} {('(' + _fmt(ri) + 'x)') if ri else '(n/a)':>9} | "
            f"{_fmt(row.get('rs_tps')):>8} {('(' + _fmt(rr) + 'x)') if rr else '(n/a)':>9} | "
            f"{(_fmt(skip * 100, 1) if isinstance(skip, (int, float)) else 'n/a'):>6} | "
            f"{_fmt(bf_q)}/{_fmt(row.get('int4_q'))}/{_fmt(rs_q)}{qflag}")
    return raw_crossover, valid_crossover, lines


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="int4+read-skip vs bf16 throughput crossover sweep (>32K)")
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--contexts", default="32000,44000,52000,60000",
                    help="comma-separated filler-token context lengths")
    ap.add_argument("--gen", type=int, default=128,
                    help="decode length for the A/B timing (passed as --ab-gen)")
    ap.add_argument("--depths", default="0.1,0.5")
    ap.add_argument("--items", type=int, default=2)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--warmup", type=int, default=2)
    # 0.55, deliberately NOT 0.85: this is a B=1 decode-timing sweep — tok/s
    # is pool-size-independent; the pool only needs ONE ctx+gen sequence
    # (~7-9 GiB at 52-68K). The route-A int4 store + eager long-prefill
    # activations allocate OUTSIDE the vLLM budget: at 0.85 the 44K AB cell
    # measured 76.3 GiB committed before the first prefill and OOMed.
    ap.add_argument("--gpu-util", type=float, default=0.55)
    ap.add_argument("--mml-headroom", type=int, default=8192,
                    help="max_model_len = context + headroom (per cell)")
    ap.add_argument("--harness", default=HARNESS_DEFAULT)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--out-dir", default="/tmp/phase10_crossover")
    ap.add_argument("--reuse", action="store_true",
                    help="skip a cell if its JSON already exists (resume a sweep)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the exact per-cell commands, run nothing")
    ap.add_argument("--plot", action="store_true",
                    help="write a 2-panel PNG (throughput + ratio-to-bf16)")
    ap.add_argument("--selftest", action="store_true",
                    help="CPU: exercise the parse/crossover/quality-gate logic")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    contexts = [int(x) for x in args.contexts.split(",") if x.strip()]
    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if not args.dry_run and not os.environ.get("PROTECT_MASK_PATH"):
        print("WARNING: PROTECT_MASK_PATH is not set — the int4 cells will likely "
              "fail. Export it before running (see usage header).", flush=True)

    common = ["--model", args.model, "--depths", args.depths,
              "--items", str(args.items), "--seeds", args.seeds,
              "--repeats", str(args.repeats), "--warmup", str(args.warmup),
              "--gpu-util", str(args.gpu_util), "--ab-gen", str(args.gen)]

    rows = []
    for L in contexts:
        mml = L + args.mml_headroom
        bf16_out = outdir / f"bf16_ctx{L}.json"
        ab_out = outdir / f"ab_ctx{L}.json"
        print(f"\n=== context {L}  (max_model_len={mml}) ===", flush=True)

        if not (args.reuse and bf16_out.exists()):
            _run([args.python, args.harness, "--bf16-ref",
                  "--context-tokens", str(L), "--max-model-len", str(mml),
                  *common, "--out", str(bf16_out)], env, args.dry_run)
        if not (args.reuse and ab_out.exists()):
            _run([args.python, args.harness, "--ab", "--ab-modes", "off,retention",
                  "--context-tokens", str(L), "--max-model-len", str(mml),
                  *common, "--out", str(ab_out)], env, args.dry_run)

        if args.dry_run:
            continue
        bf, ab = _load(bf16_out), _load(ab_out)
        pm = ab.get("per_mode", {})
        rows.append(dict(
            ctx=L,
            bf_tps=bf.get("tps_mean"),
            int4_tps=(pm.get("off") or {}).get("tps_mean"),
            rs_tps=(pm.get("retention") or {}).get("tps_mean"),
            bf_q=_min_quality(bf.get("hit_rate_by_depth")),
            int4_q=_min_quality((pm.get("off") or {}).get("hit_rate_by_depth")),
            rs_q=_min_quality((pm.get("retention") or {}).get("hit_rate_by_depth")),
            skip=(ab.get("skip_diag") or {}).get("steady_skip_frac"),
            bf_err=bf.get("_error"), ab_err=ab.get("_error")))

    if args.dry_run:
        print("\n[dry-run] nothing executed. Remove --dry-run to run the sweep.")
        return 0

    (outdir / "crossover_summary.json").write_text(
        json.dumps({"model": args.model, "gen": args.gen, "rows": rows}, indent=2))

    raw_x, valid_x, lines = analyze(rows)
    print("\n" + "=" * 96)
    print(f"int4 + read-skip vs bf16 — long-context throughput crossover  "
          f"(model={args.model.split('/')[-1]}, gen={args.gen})")
    print("=" * 96)
    print(f"{'ctx':>7} | {'bf16 tps':>9} | {'int4 tps':>9} {'/bf16':>9} | "
          f"{'rs tps':>8} {'/bf16':>9} | {'skip%':>6} | quality(min) bf/int4/rs")
    print("-" * 96)
    for ln in lines:
        print(ln)
    print("-" * 96)
    for row in rows:
        if row.get("bf_err") or row.get("ab_err"):
            print(f"  ! ctx={row['ctx']} cell error: bf16={row.get('bf_err')} "
                  f"ab={row.get('ab_err')}")
    if valid_x is not None:
        print(f"CROSSOVER (quality-clean): int4+read-skip first matches/exceeds bf16 "
              f"throughput at ctx={valid_x}  ->  the long-context throughput-positive "
              f"thesis is SUPPORTED, and this is a defensible headline.")
    elif raw_x is not None:
        print(f"RAW crossover at ctx={raw_x} BUT read-skip quality is degraded there "
              f"-> NOT a real win; widen the keep-set / re-validate before claiming.")
    else:
        maxL = max((r["ctx"] for r in rows), default=0)
        print(f"NO CROSSOVER up to ctx={maxL}: int4+read-skip stayed below bf16. "
              f"The thesis is NOT supported at these lengths — bound the story and "
              f"pivot to the density/niche framing rather than claim parity.")
    print("Read it honestly: 'int4 tps /bf16' is the QUANT ALONE (expect ~0.7x plateau); "
          "'rs tps /bf16' is read-skip (the lever). Trust a crossover ONLY where rs "
          "quality == bf16.")
    print("=" * 96)

    if args.plot:
        _plot(rows, outdir)
    return 0


def _plot(rows, outdir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # noqa: BLE001
        print(f"[plot] skipped ({type(e).__name__}: {e}); crossover_summary.json "
              f"has the data for external plotting.")
        return
    xs = [r["ctx"] for r in rows]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    a1.plot(xs, [r.get("bf_tps") for r in rows], "o-", label="bf16")
    a1.plot(xs, [r.get("int4_tps") for r in rows], "s-", label="full-int4")
    a1.plot(xs, [r.get("rs_tps") for r in rows], "^-", label="int4 + read-skip")
    a1.set(xlabel="context tokens", ylabel="decode tok/s", title="throughput")
    a1.legend(); a1.grid(True, alpha=.3)
    a2.axhline(1.0, color="k", ls="--", lw=1, label="bf16 parity")
    a2.plot(xs, [_ratio(r.get("int4_tps"), r.get("bf_tps")) for r in rows], "s-",
            label="int4 / bf16")
    a2.plot(xs, [_ratio(r.get("rs_tps"), r.get("bf_tps")) for r in rows], "^-",
            label="int4+read-skip / bf16")
    a2.set(xlabel="context tokens", ylabel="throughput / bf16",
           title="ratio to bf16  (crossover = above 1.0)")
    a2.legend(); a2.grid(True, alpha=.3)
    png = outdir / "crossover.png"
    fig.tight_layout(); fig.savefig(png, dpi=130)
    print(f"[plot] wrote {png}")


def _selftest():
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    # quant plateaus ~0.7x; read-skip crosses clean at 52K (quality holds)
    rows = [
        dict(ctx=32000, bf_tps=100.0, int4_tps=67.0, rs_tps=84.0,
             bf_q=1.0, int4_q=1.0, rs_q=1.0, skip=0.94),
        dict(ctx=44000, bf_tps=80.0, int4_tps=55.0, rs_tps=92.0,
             bf_q=1.0, int4_q=1.0, rs_q=1.0, skip=0.95),
        dict(ctx=52000, bf_tps=65.0, int4_tps=45.0, rs_tps=78.0,
             bf_q=1.0, int4_q=1.0, rs_q=1.0, skip=0.96),
    ]
    raw_x, valid_x, lines = analyze(rows)
    check("clean crossover detected at 44000", valid_x == 44000 and raw_x == 44000)
    check("table line count matches rows", len(lines) == 3)

    # crossover on DEGRADED read-skip quality must NOT count as valid
    rows_bad = [dict(ctx=52000, bf_tps=65.0, int4_tps=45.0, rs_tps=78.0,
                     bf_q=1.0, int4_q=1.0, rs_q=0.667, skip=0.96)]
    raw_b, valid_b, _ = analyze(rows_bad)
    check("raw crossover seen but quality-gated out",
          raw_b == 52000 and valid_b is None)

    # never crosses
    rows_none = [dict(ctx=60000, bf_tps=70.0, int4_tps=49.0, rs_tps=63.0,
                      bf_q=1.0, int4_q=1.0, rs_q=1.0, skip=0.95)]
    _, valid_n, _ = analyze(rows_none)
    check("no crossover -> valid_crossover None", valid_n is None)

    check("ratio + fmt helpers", _ratio(84.0, 100.0) == 0.84
          and _fmt(0.84) == "0.84" and _fmt(None) == "n/a"
          and _min_quality({"0.10": 1.0, "0.50": 0.667}) == 0.667)

    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
