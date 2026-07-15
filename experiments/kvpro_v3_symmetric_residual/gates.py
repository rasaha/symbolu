"""KVPro V3 Gate-1 — PRE-REGISTERED decision gates + verdict.

Thresholds are fixed HERE, before results are viewed, and justified against existing KVPro acceptance
standards. Do NOT loosen after seeing results. Emits exactly one verdict:
  GO_KERNEL_PROTOTYPE | GO_WITH_MODIFICATION | NO_GO_QUALITY | NO_GO_SYSTEMS_VALUE | INCONCLUSIVE
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import accounting as A                       # noqa: E402

# ---------------- PRE-REGISTERED THRESHOLDS (justification inline) ---------------- #
# Quality (offline attention proxy) — affine is the shipped, quality-validated baseline.
TH_ATTN_OUT_COS_MIN = 0.999          # kernel-correctness standard in-repo uses cosine >= 0.999
TH_ATTN_OUT_MSE_VS_AFFINE_MAX = 1.25 # symmetric must stay within 25% of affine's attn-output error
TH_SOFTMAX_KL_MAX = 0.02             # nats; guards logit distortion MSE misses
# Quality (end-to-end, if available) — mirror phase6n (tol 1.0pt) + needle non-regression.
TH_HARDNEEDLE_ABS_DROP = 0.02        # vs affine AND vs bf16
TH_TOKEN_AGREE_DROP_PT = 1.0
TH_MMLU_DROP_PT = 1.0
# Systems value — decode is bandwidth-bound; >=5% read-bandwidth reduction maps to the >=5% TPS floor.
TH_SYSTEMS_PCT = 5.0

_CANDS = ("S1", "S2", "S3", "S4")


def _load(path):
    return json.load(open(path)) if path and os.path.exists(path) else None


def quality_offline(attn, cand):
    """Offline attention-proxy quality gate for one candidate. Returns (pass, reasons)."""
    if attn is None:
        return None, ["attention-error eval NOT RUN"]
    s = attn["summary"][cand]
    reasons, ok = [], True
    if s["attn_out_cos_min"] < TH_ATTN_OUT_COS_MIN:
        ok = False; reasons.append(f"attn_out_cos_min {s['attn_out_cos_min']:.6f} < {TH_ATTN_OUT_COS_MIN}")
    if s["attn_out_mse_vs_affine_max"] > TH_ATTN_OUT_MSE_VS_AFFINE_MAX:
        ok = False; reasons.append(f"attn_out_mse x affine {s['attn_out_mse_vs_affine_max']:.2f} > {TH_ATTN_OUT_MSE_VS_AFFINE_MAX}")
    if s["softmax_kl_max_max"] > TH_SOFTMAX_KL_MAX:
        ok = False; reasons.append(f"softmax_kl_max {s['softmax_kl_max_max']:.4f} > {TH_SOFTMAX_KL_MAX}")
    # synthetic fixtures are never a verdict
    if attn.get("label") == "NOT_A_VERDICT_SYNTHETIC":
        return None, ["SYNTHETIC fixture — not a quality verdict"]
    return ok, reasons or ["within all offline thresholds"]


def quality_e2e(e2e, cand):
    if e2e is None:
        return None, ["end-to-end quality NOT RUN (needs pod)"]
    c = e2e.get(cand, {}); aff = e2e.get("affine", {}); bf16 = e2e.get("bf16", {})
    reasons, ok = [], True
    if "hard_needle" in c and "hard_needle" in aff:
        if c["hard_needle"] < aff["hard_needle"] - TH_HARDNEEDLE_ABS_DROP:
            ok = False; reasons.append(f"hard-needle {c['hard_needle']} < affine-{TH_HARDNEEDLE_ABS_DROP}")
        if bf16.get("hard_needle") is not None and c["hard_needle"] < bf16["hard_needle"] - TH_HARDNEEDLE_ABS_DROP:
            ok = False; reasons.append("hard-needle regressed vs bf16")
    else:
        return None, ["end-to-end hard-needle NOT RUN"]
    if "token_agree" in c and "token_agree" in aff and c["token_agree"] < aff["token_agree"] - TH_TOKEN_AGREE_DROP_PT:
        ok = False; reasons.append("token-agreement regressed > 1pt vs affine")
    if "mmlu" in c and "mmlu" in aff and c["mmlu"] < aff["mmlu"] - TH_MMLU_DROP_PT:
        ok = False; reasons.append("MMLU regressed > 1pt vs affine")
    return ok, reasons or ["within all end-to-end thresholds"]


def systems_value(cand, ctx=8192, geom=None):
    g = geom or A.QWEN2_5_7B
    acc = A.account(g, ctx)[cand]
    ok = (acc["pct_reduction_vs_affine"] >= TH_SYSTEMS_PCT
          and acc["affine_adds_removed_per_tok_head"] > 0)
    reason = f"{acc['pct_reduction_vs_affine']:.2f}% read-bw reduction (floor {TH_SYSTEMS_PCT}%); " \
             f"xmin_removed={acc['xmin_fully_removed']}"
    return ok, reason, acc


def verdict(recon, attn, e2e, ctx=8192, geom=None):
    per = {}
    for c in _CANDS:
        q_off, r_off = quality_offline(attn, c)
        q_e2e, r_e2e = quality_e2e(e2e, c)
        s_ok, s_reason, acc = systems_value(c, ctx, geom)
        per[c] = {"quality_offline": q_off, "quality_offline_reasons": r_off,
                  "quality_e2e": q_e2e, "quality_e2e_reasons": r_e2e,
                  "systems_pass": s_ok, "systems_reason": s_reason,
                  "pct_reduction": acc["pct_reduction_vs_affine"]}

    def full_quality(c):
        # PASS only if both available signals pass; None (not-run) is not a pass.
        return per[c]["quality_offline"] is True and per[c]["quality_e2e"] is True

    # Decision tree (pre-registered).
    any_offline_run = attn is not None and attn.get("label") != "NOT_A_VERDICT_SYNTHETIC"
    any_offline_fail = any(per[c]["quality_offline"] is False for c in _CANDS)
    both_xmin_quality = full_quality("S1") or full_quality("S2")
    both_xmin_systems = per["S1"]["systems_pass"] or per["S2"]["systems_pass"]
    only_v = (full_quality("S3") and not (full_quality("S1") or full_quality("S2") or full_quality("S4")))
    only_k = (full_quality("S4") and not (full_quality("S1") or full_quality("S2") or full_quality("S3")))

    if any_offline_run and any_offline_fail and not (full_quality("S1") or full_quality("S2")
                                                     or full_quality("S3") or full_quality("S4")):
        # offline proxy already kills every candidate that also lacks an e2e pass
        if e2e is None:
            label = "NO_GO_QUALITY" if all(per[c]["quality_offline"] is False for c in _CANDS) \
                    else "INCONCLUSIVE"
        else:
            label = "NO_GO_QUALITY"
    elif both_xmin_quality and both_xmin_systems:
        label = "GO_KERNEL_PROTOTYPE"
    elif both_xmin_quality and not both_xmin_systems:
        label = "NO_GO_SYSTEMS_VALUE"     # quality fine but <5% -> keep affine, do gather/layout
    elif only_k or only_v:
        label = "GO_WITH_MODIFICATION"    # asymmetric format (only K or only V symmetric)
    else:
        label = "INCONCLUSIVE"            # signals incomplete (e.g., e2e not run) or mixed

    return {"verdict": label, "per_candidate": per,
            "thresholds": {k: v for k, v in globals().items() if k.startswith("TH_")},
            "inputs_present": {"recon": recon is not None, "attn": attn is not None,
                               "e2e": e2e is not None,
                               "attn_is_synthetic": (attn or {}).get("label") == "NOT_A_VERDICT_SYNTHETIC"}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 Gate-1 verdict")
    ap.add_argument("--recon"); ap.add_argument("--attn"); ap.add_argument("--e2e")
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--model", default="qwen", choices=["qwen", "llama"])
    ap.add_argument("--out", default="verdict.json")
    args = ap.parse_args(argv)
    geom = A.QWEN2_5_7B if args.model == "qwen" else A.LLAMA3_1_8B
    v = verdict(_load(args.recon), _load(args.attn), _load(args.e2e), ctx=args.ctx, geom=geom)
    json.dump(v, open(args.out, "w"), indent=2)
    print(f"\nVERDICT: {v['verdict']}")
    for c, p in v["per_candidate"].items():
        print(f"  {c}: q_offline={p['quality_offline']} q_e2e={p['quality_e2e']} "
              f"systems={p['systems_pass']} ({p['pct_reduction']:.1f}%)")
    print(f"inputs: {v['inputs_present']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
