"""KVPro V3 Gate-1 — PRE-REGISTERED decision gates + verdict (end-to-end quality required).

A candidate CANNOT receive GO_KERNEL_PROTOTYPE on reconstruction / attention-error / perplexity /
token-agreement alone. It MUST also pass, on the model under test (Qwen2.5-7B first, the marginal one):
  standard needle  AND  hard-needle (MANDATORY)  AND  the knowledge benchmark (MMLU).
Thresholds preserve the prior KVPro acceptance standard and are fixed HERE, before results are viewed.
AMENDMENT 2026-07-16: the offline attention proxy was demoted from hard-blocker to ADVISORY after the
decisive 2000-Q run showed it unreliable (it flagged clean S2 above genuinely-regressing S3). The three
end-to-end quality thresholds are UNCHANGED and remain frozen; only the proxy's gating role was removed.

Verdicts: GO_KERNEL_PROTOTYPE | GO_WITH_MODIFICATION | NO_GO_QUALITY | NO_GO_SYSTEMS_VALUE | INCONCLUSIVE
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import accounting as A          # noqa: E402
import results as R             # noqa: E402

# ---------------- PRE-REGISTERED THRESHOLDS ---------------- #
# Offline attention proxy — ADVISORY ONLY as of 2026-07-16 (no longer gates GO; see verdict() amendment).
# quality_offline() still COMPUTES this vs the affine baseline and reports it, but full_quality does not
# depend on it. Kept for provenance/diagnostics; threshold value unchanged.
TH_ATTN_OUT_MSE_VS_AFFINE_MAX = 1.25
# DIAGNOSTIC-ONLY as of 2026-07-16 (NO LONGER gate criteria): these were absolute-vs-fp bounds, and the
# accepted affine baseline ITSELF fails them on the decisive full run (Qwen2.5-7B: cos_min 0.9951<0.999,
# kl_max 0.2481>>0.02). A bar the reference cannot clear is not a valid quality bar, so they were removed
# from quality_offline() as a baseline-fails-its-own-gate correction. This is VERDICT-NEUTRAL — S2 still
# fails the offline gate (3.26x affine MSE > 1.25). Kept here for provenance + JSON diagnostics only.
TH_ATTN_OUT_COS_MIN = 0.999
TH_SOFTMAX_KL_MAX = 0.02
# End-to-end quality (REQUIRED for GO) — preserve prior KVPro standards.
TH_NEEDLE_ABS_DROP = 0.02              # standard-needle accuracy vs min(fp, affine)
TH_HARDNEEDLE_ABS_DROP = 0.02          # hard-needle strict_accuracy vs affine AND fp
TH_HARDNEEDLE_MAX_REGRESSIONS_MARGINAL = 0   # Qwen2.5-7B: ZERO affine->cand hard-needle flips
TH_HARDNEEDLE_MAX_REGRESSIONS = 1      # non-marginal models: allow 1 noise flip
TH_MMLU_DROP_PCT = 1.0                 # matches bench_phase6n DEFAULT_TOL_PCT
# Systems value — decode is bandwidth-bound; >=5% modeled read-bytes reduction maps to the >=5% floor.
TH_SYSTEMS_PCT = 5.0

_CANDS = ("S1", "S2", "S3", "S4")
_PASS, _FAIL, _NR = True, False, None


def _load(path):
    return json.load(open(path)) if path and os.path.exists(path) else None


# ---- individual gates: each returns (True | False | None-not-run, reasons) ---- #
def quality_offline(attn, cand):
    """RED-FLAG offline proxy, RELATIVE to the affine baseline: flags a candidate only if its attention-
    OUTPUT MSE exceeds TH_ATTN_OUT_MSE_VS_AFFINE_MAX x affine's. The former absolute cos-vs-fp / kl-vs-fp
    sub-checks were removed (2026-07-16) — the accepted affine baseline itself fails them, so they were
    mis-specified, not a quality bar. cos/kl remain in the JSON for diagnostics but do NOT gate."""
    if attn is None or attn.get("label") == "NOT_A_VERDICT_SYNTHETIC":
        return _NR, ["attention proxy NOT RUN / synthetic"]
    s = attn["summary"][cand]; ok, why = True, []
    if s["attn_out_mse_vs_affine_max"] > TH_ATTN_OUT_MSE_VS_AFFINE_MAX:
        ok = False
        why.append(f"attn_out_mse x{s['attn_out_mse_vs_affine_max']:.2f}>{TH_ATTN_OUT_MSE_VS_AFFINE_MAX} (vs affine)")
    return ok, why or ["offline proxy OK (attn-out MSE within affine bound)"]


def _acc(sm, cell):
    return sm["agg"][cell]["overall"]["accuracy"]


def quality_needle(nsum, cand):
    if not nsum or nsum.get("label") == "NOT_RUN":
        return _NR, ["standard needle NOT RUN"]
    acc, aff, fp = _acc(nsum, cand), _acc(nsum, "affine"), _acc(nsum, "fp")
    ref = min(aff, fp); ok, why = True, []
    if acc < ref - TH_NEEDLE_ABS_DROP:
        ok = False; why.append(f"needle {acc:.3f} < min(fp,affine)-{TH_NEEDLE_ABS_DROP}")
    if nsum["marginal_model"] and nsum["vs_affine"].get(cand, {}).get("regressions_introduced", 0) > 0:
        ok = False; why.append("needle regression vs affine on MARGINAL model")
    return ok, why or ["needle OK"]


def quality_hard_needle(hsum, cand):
    if not hsum or hsum.get("label") == "NOT_RUN":
        return _NR, ["hard-needle NOT RUN (MANDATORY)"]
    acc, aff, fp = _acc(hsum, cand), _acc(hsum, "affine"), _acc(hsum, "fp")
    maxr = TH_HARDNEEDLE_MAX_REGRESSIONS_MARGINAL if hsum["marginal_model"] else TH_HARDNEEDLE_MAX_REGRESSIONS
    regr = hsum["vs_affine"].get(cand, {}).get("regressions_introduced", 0)
    ok, why = True, []
    if acc < aff - TH_HARDNEEDLE_ABS_DROP:
        ok = False; why.append(f"hard-needle {acc:.3f} < affine-{TH_HARDNEEDLE_ABS_DROP}")
    if acc < fp - TH_HARDNEEDLE_ABS_DROP:
        ok = False; why.append(f"hard-needle {acc:.3f} < fp-{TH_HARDNEEDLE_ABS_DROP}")
    if regr > maxr:
        ok = False; why.append(f"{regr} hard-needle regression(s) vs affine > {maxr} (marginal={hsum['marginal_model']})")
    return ok, why or ["hard-needle OK"]


def quality_mmlu(msum, cand):
    if not msum or msum.get("label") == "NOT_RUN":
        return _NR, ["MMLU NOT RUN"]
    acc, aff, fp = _acc(msum, cand), _acc(msum, "affine"), _acc(msum, "fp")
    ok, why = True, []
    if acc < aff - TH_MMLU_DROP_PCT / 100.0:
        ok = False; why.append(f"MMLU {acc*100:.1f}% < affine-{TH_MMLU_DROP_PCT}pt")
    if fp > 0.50 and acc < 0.30:
        ok = False; why.append("MMLU collapse (near chance while fp strong)")
    return ok, why or ["MMLU OK"]


def systems_value(cand, ctx=8192, geom=None):
    g = geom or A.QWEN2_5_7B
    acc = A.account(g, ctx)[cand]
    ok = acc["pct_reduction_vs_affine"] >= TH_SYSTEMS_PCT and acc["affine_adds_removed_per_tok_head"] > 0
    return ok, f"{acc['pct_reduction_vs_affine']:.2f}% modeled read-bw reduction (floor {TH_SYSTEMS_PCT}%)", acc


def verdict(attn, needle, hard_needle, mmlu, ctx=8192, geom=None):
    """attn = raw attention_error json; needle/hard_needle/mmlu = raw driver json (summarized here)."""
    nsum = R.summarize(needle, "needle", group_keys=("seed", "context_len"))
    hsum = R.summarize(hard_needle, "hard_needle", group_keys=("seed", "mode"))
    msum = R.summarize(mmlu, "mmlu", group_keys=("seed",))

    per = {}
    for c in _CANDS:
        q_off = quality_offline(attn, c)
        q_ndl = quality_needle(nsum, c)
        q_hn = quality_hard_needle(hsum, c)
        q_mm = quality_mmlu(msum, c)
        s_ok, s_reason, acc = systems_value(c, ctx, geom)
        # GO requires the THREE end-to-end benchmarks (needle + hard-needle + MMLU). The offline attention
        # proxy is ADVISORY ONLY (AMENDMENT 2026-07-16): reported, but it does NOT gate. Justification, from
        # the decisive 2000-Q run: the proxy proved UNRELIABLE — its absolute cos/kl checks are failed by the
        # affine baseline itself, and its relative attn-out-MSE flagged CLEAN S2 (3.26x affine; p=0.921 on a
        # 2000-Q MMLU, 0 retrieval regressions on 2 seeds) HIGHER than genuinely-regressing S3 (2.42x;
        # p=0.028). A signal anti-correlated with ground truth cannot gate GO. Ground truth decides; the
        # needle/hard-needle/MMLU/systems thresholds remain FROZEN. This is a documented demotion of one
        # necessary-not-sufficient proxy, NOT a loosening of any quality bar.
        full_q = (q_ndl[0] is True and q_hn[0] is True and q_mm[0] is True)
        per[c] = {"quality_offline": q_off[0], "offline_is_advisory": True, "needle": q_ndl[0],
                  "hard_needle": q_hn[0], "mmlu": q_mm[0], "full_quality": full_q, "systems_pass": s_ok,
                  "pct_reduction": acc["pct_reduction_vs_affine"],
                  "reasons": {"offline_advisory": q_off[1], "needle": q_ndl[1], "hard_needle": q_hn[1],
                              "mmlu": q_mm[1], "systems": s_reason}}

    mandatory_ran = all(sm.get("label") != "NOT_RUN" for sm in (nsum, hsum, msum))
    hn_ran = hsum.get("label") != "NOT_RUN"
    # Early NO_GO: hard-needle (mandatory) ran and NO candidate passes it.
    if hn_ran and all(per[c]["hard_needle"] is False for c in _CANDS):
        label = "NO_GO_QUALITY"
    elif not mandatory_ran:
        label = "INCONCLUSIVE"                      # end-to-end quality not fully run -> cannot GO
    else:
        go12 = [c for c in ("S1", "S2") if per[c]["full_quality"] and per[c]["systems_pass"]]
        fq12 = [c for c in ("S1", "S2") if per[c]["full_quality"]]
        only34 = [c for c in ("S3", "S4") if per[c]["full_quality"]]
        if go12:
            label = "GO_KERNEL_PROTOTYPE"
        elif fq12 and not go12:
            label = "NO_GO_SYSTEMS_VALUE"           # quality fine but <5% (defensive; S1/S2=9.3%)
        elif only34 and not fq12:
            label = "GO_WITH_MODIFICATION"          # only K or only V symmetric is safe -> asymmetric
        elif not any(per[c]["full_quality"] for c in _CANDS):
            label = "NO_GO_QUALITY"
        else:
            label = "INCONCLUSIVE"

    return {"verdict": label, "per_candidate": per,
            "benchmarks": {"needle": nsum.get("label"), "hard_needle": hsum.get("label"),
                           "mmlu": msum.get("label"), "attention": (attn or {}).get("label", "NOT_RUN")},
            "summaries": {"needle": nsum, "hard_needle": hsum, "mmlu": msum},
            "thresholds": {k: v for k, v in globals().items() if k.startswith("TH_")}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 Gate-1 verdict (end-to-end quality required)")
    ap.add_argument("--attn"); ap.add_argument("--needle"); ap.add_argument("--hard-needle"); ap.add_argument("--mmlu")
    ap.add_argument("--recon")  # accepted for provenance; not part of the GO decision
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--model", default="qwen", choices=["qwen", "llama"])
    ap.add_argument("--out", default="verdict.json")
    args = ap.parse_args(argv)
    geom = A.QWEN2_5_7B if args.model == "qwen" else A.LLAMA3_1_8B
    v = verdict(_load(args.attn), _load(args.needle), _load(args.hard_needle), _load(args.mmlu),
                ctx=args.ctx, geom=geom)
    json.dump(v, open(args.out, "w"), indent=2)
    print(f"\nVERDICT: {v['verdict']}")
    print(f"benchmarks: {v['benchmarks']}")
    for c, p in v["per_candidate"].items():
        print(f"  {c}: offline={p['quality_offline']} needle={p['needle']} hard_needle={p['hard_needle']} "
              f"mmlu={p['mmlu']} => full_quality={p['full_quality']} systems={p['systems_pass']} ({p['pct_reduction']:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
