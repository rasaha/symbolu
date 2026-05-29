#!/usr/bin/env python3
# Phase 6K.11 — needle failure-mode breakdown (K-bound vs V-bound).
#
# "Why did needle underperform, and where do we spend bits to improve it?"
# This is a CPU-only POST-PROCESSOR of bench_phase6j_quality_gpu.py's per-cell
# JSONs. Each needle_record carries {needle, output_text, score, collapse{...}},
# so we classify every item into:
#
#   HIT      — exact code retrieved (score 1.0).
#   NEAR_V   — attended but emitted a WRONG/near-miss code (needle prefix present,
#              or some code-shaped token emitted) => attention found it, int4 V
#              blurred the value. Lever: raise V precision (int8 V / protect V).
#   MISS_K   — no code-shaped output at all => attention never locked on. Lever:
#              finer K groups / retrieval-aware protect-channel calibration.
#   COLLAPSE — pérdida-style decode collapse (the 6K.9/6K.10 bug). Should be ~0
#              after the fixes; if not, the run predates them.
#
# This separates "the bug" from "intrinsic int4 retrieval loss" and tells you
# which surface (K vs V) carries the failure mass, per cell × mml.
#
# Usage (run the bench post-fix first, then point this at its output dir):
#   PHASE6K10_AUTO_HOOK=0 python CTM_plus/Bench/scripts/bench_phase6j_quality_gpu.py [--smoke]
#   python CTM_plus/Bench/scripts/phase6k11_needle_failuremode.py \
#       --dir bench_out/phase6j_quality            # or ..._smoke

import argparse
import glob
import json
import os
import re
from collections import defaultdict

# Needle values look like HORIZ4 / ZK7QM2 — 5-8 uppercase-alnum chars.
_CODE_RE = re.compile(r"[A-Z0-9]{5,8}")


def _is_collapse(rec) -> bool:
    """Use the bench's recorded collapse metrics; fall back to a text heuristic."""
    coll = rec.get("collapse") or {}
    if coll:
        if (coll.get("trigram_repeat_rate") or 0.0) > 0.30:
            return True
        if (coll.get("distinct_token_ratio") or 1.0) < 0.40:
            return True
        if (coll.get("longest_identical_run") or 0) >= 5:
            return True
        return False
    text = rec.get("output_text") or ""
    w = text.split()
    if len(w) >= 6 and len(set(w)) / len(w) < 0.40:
        return True
    return False


def classify(rec) -> str:
    needle = rec.get("needle") or ""
    text = rec.get("output_text") or ""
    score = rec.get("score") or 0.0
    if score >= 1.0:
        return "HIT"
    if _is_collapse(rec):
        return "COLLAPSE"
    # attended-but-wrong: needle prefix present, or any code-shaped token emitted
    if needle and needle[:3] and needle[:3] in text:
        return "NEAR_V"
    if any(m != needle for m in _CODE_RE.findall(text)):
        return "NEAR_V"
    return "MISS_K"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="bench_out/phase6j_quality",
                    help="6J output dir (the bench appends _smoke for --smoke runs).")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "cell_*_mml*.json")))
    if not files:
        # try the _smoke sibling for convenience
        alt = args.dir.rstrip("/") + "_smoke"
        files = sorted(glob.glob(os.path.join(alt, "cell_*_mml*.json")))
        if files:
            args.dir = alt
    if not files:
        print(f"No cell_*_mml*.json under {args.dir!r} (or its _smoke sibling).")
        print("Run bench_phase6j_quality_gpu.py first, then pass its --output-dir here.")
        return 1

    rows = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception as e:
            print(f"  skip {f}: {type(e).__name__}: {e}")
            continue
        recs = d.get("needle_records", []) or []
        cnt = defaultdict(int)
        for r in recs:
            cnt[classify(r)] += 1
        rows.append({
            "cell": d.get("cell", "?"),
            "mml": d.get("max_model_len", 0),
            "n": len(recs),
            "acc": d.get("needle_accuracy"),
            "cnt": cnt,
        })

    print("=" * 96)
    print("PHASE 6K.11 — needle failure-mode breakdown  (dir: %s)" % args.dir)
    print("  HIT=retrieved   NEAR_V=attended,wrong-code (raise V precision)   "
          "MISS_K=not retrieved (improve K)   COLLAPSE=decode bug (want 0)")
    print("=" * 96)
    print(f"  {'cell':>10} {'mml':>7} {'n':>3} | {'acc':>5} | "
          f"{'HIT':>4} {'NEAR_V':>7} {'MISS_K':>7} {'COLLAPSE':>8}")
    print("  " + "-" * 84)
    for r in sorted(rows, key=lambda x: (x["mml"] if isinstance(x["mml"], int) else 0, x["cell"])):
        c = r["cnt"]
        acc = f"{r['acc']:.3f}" if isinstance(r["acc"], (int, float)) else "  ?  "
        print(f"  {r['cell']:>10} {str(r['mml']):>7} {r['n']:>3} | {acc:>5} | "
              f"{c['HIT']:>4} {c['NEAR_V']:>7} {c['MISS_K']:>7} {c['COLLAPSE']:>8}")

    # Per-cell verdict on where the failure mass lives (int4 cells only).
    print("\n  --- where to spend bits (int4 cells, summed over mml) ---")
    by_cell = defaultdict(lambda: defaultdict(int))
    for r in rows:
        for k, v in r["cnt"].items():
            by_cell[r["cell"]][k] += v
    for cell in ("naive", "protected"):
        c = by_cell.get(cell)
        if not c:
            continue
        nearv, missk, coll = c["NEAR_V"], c["MISS_K"], c["COLLAPSE"]
        fails = nearv + missk
        if coll:
            verdict = f"{coll} COLLAPSE items — re-run with 6K.9/6K.10 fixes before trusting this."
        elif fails == 0:
            verdict = "no non-collapse failures (or no data)."
        elif nearv >= 2 * max(1, missk):
            verdict = "V-BOUND — attention finds the needle; int4 V blurs the code. Lever: int8 V / protect V."
        elif missk >= 2 * max(1, nearv):
            verdict = "K-BOUND — attention doesn't lock on. Lever: finer K groups / retrieval-aware protect calibration."
        else:
            verdict = f"MIXED (NEAR_V={nearv}, MISS_K={missk}) — both K and V contribute."
        print(f"    {cell:>10}: {verdict}")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
