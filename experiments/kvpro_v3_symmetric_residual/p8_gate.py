"""KVPro V3 Step-0 (Part F) — P8 protected-INT8 quality verdict.

P8 keeps the INT4 residual + V byte-identical to the shipped affine arm and changes ONLY the protected-K
precision (exact/bf16 -> int8). So the baseline is "affine" and P8sym/P8aff are the candidates. Reuses
results.summarize + the SAME pre-registered gate thresholds (gates.quality_needle/hard_needle/mmlu) — no
new, looser bar. P8 is evaluated INDEPENDENTLY of S1-S4.

Verdict: P8_CLEAN (>=1 P8 variant passes needle+hard-needle+MMLU vs affine) | NO_GO_QUALITY | INCONCLUSIVE.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import results as R           # noqa: E402
import gates as G             # noqa: E402
import protected_int8 as P8   # noqa: E402

_P8_CANDS = ("P8sym", "P8aff")


def _load(p):
    return json.load(open(p)) if p and os.path.exists(p) else None


def verdict(needle, hard_needle, mmlu, n_protect=5):
    nsum = R.summarize(needle, "needle", group_keys=("seed", "context_len"))
    hsum = R.summarize(hard_needle, "hard_needle", group_keys=("seed", "mode"))
    msum = R.summarize(mmlu, "mmlu", group_keys=("seed",))
    per = {}
    for c in _P8_CANDS:
        # only evaluate cands actually present in the runs
        present = all(c in (s.get("agg") or {}) for s in (nsum, hsum, msum) if s.get("label") != "NOT_RUN")
        q_ndl = G.quality_needle(nsum, c)
        q_hn = G.quality_hard_needle(hsum, c)
        q_mm = G.quality_mmlu(msum, c)
        clean = (q_ndl[0] is True and q_hn[0] is True and q_mm[0] is True)
        per[c] = {"present": present, "needle": q_ndl[0], "hard_needle": q_hn[0], "mmlu": q_mm[0],
                  "clean": clean, "reasons": {"needle": q_ndl[1], "hard_needle": q_hn[1], "mmlu": q_mm[1]}}
    ran = all(s.get("label") != "NOT_RUN" for s in (nsum, hsum, msum))
    any_clean = any(per[c]["clean"] for c in _P8_CANDS)
    any_present = any(per[c]["present"] for c in _P8_CANDS)
    if not ran or not any_present:
        label = "INCONCLUSIVE"
    elif any_clean:
        label = "P8_CLEAN"
    else:
        label = "NO_GO_QUALITY"
    return {
        "verdict": label,
        "p8_quality_clean": bool(any_clean and ran),
        "recommended_variant": next((c for c in _P8_CANDS if per[c]["clean"]), None),
        "per_candidate": per,
        "protected_stream": P8.protected_stream_bytes(n_protect),
        "benchmarks": {"needle": nsum.get("label"), "hard_needle": hsum.get("label"), "mmlu": msum.get("label")},
        "note": "P8 changes ONLY protected-K precision vs the affine baseline; the INT4 residual + V are "
                "byte-identical. Systems value is the protected-stream byte reduction + coalescing, NOT a "
                "standalone TPS claim; combine with a dense-stream kernel, and only combine with S2 later.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 Step-0 P8 protected-INT8 verdict")
    ap.add_argument("--needle"); ap.add_argument("--hard-needle"); ap.add_argument("--mmlu")
    ap.add_argument("--n-protect", type=int, default=5)
    ap.add_argument("--out", default="p8_verdict.json")
    a = ap.parse_args(argv)
    v = verdict(_load(a.needle), _load(a.hard_needle), _load(a.mmlu), a.n_protect)
    json.dump(v, open(a.out, "w"), indent=2)
    print(f"\nP8 VERDICT: {v['verdict']}  (clean={v['p8_quality_clean']}, "
          f"recommended={v['recommended_variant']})")
    for c, p in v["per_candidate"].items():
        print(f"  {c}: needle={p['needle']} hard_needle={p['hard_needle']} mmlu={p['mmlu']} => clean={p['clean']}")
    ps = v["protected_stream"]
    print(f"  protected stream: bf16 {ps['protected_bytes_per_tok_head_layer_bf16']}B -> "
          f"int8 {ps['protected_bytes_per_tok_head_layer_int8']}B/tok/head/layer "
          f"({ps['protected_stream_reduction_pct']}% of the protected sidecar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
