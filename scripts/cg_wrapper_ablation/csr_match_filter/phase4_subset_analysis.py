#!/usr/bin/env python3
"""phase4_subset_analysis.py — distinguish ordinary power gain from semantic-field stress.

Analysis-only (no Bhava, no model/runtime change). Operates on already-collected Stage-A activations.
Three tests on the expanded run (and, optionally, the old n=220 run as a baseline):

  1. DOWNSAMPLE the expanded field to the old size (110 examples x 2 arms) K times. If downsampled
     expanded subsets still beat the old n=220 set at the SAME size, the field has stronger examples
     (field stress), not merely more samples.
  2. WITHIN the expanded set, within-arm AUROC by ROW TYPE: original/v2, drift_onframe (control),
     drift_adversarial (minimal-pair stress), combined — N-matched so the comparison is power-fair.
  3. HIDDEN SEPARABILITY by row type: can hidden states distinguish ordinary vs adversarial rows, and
     do adversarial rows carry a larger failure-label margin (AUROC) than ordinary rows?

All probes: within-arm only (arm is a confound), group-by-term CV, global label-free PCA, bootstrap CIs.

  python phase4_subset_analysis.py --run-dir runs/csr_phase4_v3 \
    --baseline-run-dir runs/csr_phase4 --targets frame_violation,rejected_domain_leak,audit_fail
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import phase4_probe as PB              # noqa: E402
from csr_match_filter import phase4_probe_eval as PE         # noqa: E402

ARMS = ("base", "framed")


def reduce_at_layer(X3d, layer_idx, n_pca):
    Xi = X3d[:, layer_idx, :]
    if n_pca and Xi.shape[1] > n_pca:
        p = PB.pca_fit(Xi, n_pca)
        return PB.pca_transform(p, Xi)
    return Xi


def auroc_within_arm(X2d, y, groups, arm_mask, n_splits, seed):
    sel = arm_mask
    yy = y[sel]
    if int(yy.sum()) < 5 or int((yy == 0).sum()) < 5:
        return {"auroc": None, "n_pos": int(yy.sum()), "n_neg": int((yy == 0).sum())}
    res = PB.evaluate_probe(X2d[sel], yy, groups[sel], n_splits=n_splits, n_pca=None, seed=seed)
    return {"auroc": round(float(res["auroc"]), 3), "n_pos": int(yy.sum()),
            "n_neg": int((yy == 0).sum())}


def pick_layer(X3d, y, groups, arm_mask, layers, n_pca, n_splits, seed):
    """Best framed-arm layer for this target on the full set (one fixed layer used for all comparisons)."""
    best_i, best = 0, -1.0
    for i in range(len(layers)):
        X2d = reduce_at_layer(X3d, i, n_pca)
        a = auroc_within_arm(X2d, y, groups, arm_mask, n_splits, seed)["auroc"]
        if a is not None and a > best:
            best, best_i = a, i
    return best_i, layers[best_i], best


def row_type(rows):
    """0 = original/v2, 1 = drift_adversarial, 2 = drift_onframe (control)."""
    out = []
    for r in rows:
        c = r.get("category", "")
        out.append(1 if c == "drift_adversarial" else 2 if c == "drift_onframe" else 0)
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="runs/csr_phase4_v3")
    ap.add_argument("--baseline-run-dir", default=None, help="old n=220 run for the size-matched compare")
    ap.add_argument("--targets", default="frame_violation,rejected_domain_leak,audit_fail")
    ap.add_argument("--arm", default="framed", choices=["framed", "base"])
    ap.add_argument("--n-pca", type=int, default=32)
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--downsample-examples", type=int, default=110)
    ap.add_argument("--downsample-k", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]

    X, layers, arms, rows = PE.load_run(args.run_dir)
    groups = PE.groups_for(rows)
    rtype = row_type(rows)
    arm_mask = (arms == args.arm)
    ids = np.array([r["id"] for r in rows], dtype=object)

    base = None
    if args.baseline_run_dir:
        bX, blayers, barms, brows = PE.load_run(args.baseline_run_dir)
        base = {"X": bX, "layers": blayers, "arms": barms, "rows": brows,
                "groups": PE.groups_for(brows)}

    report = {"meta": {"run_dir": args.run_dir, "baseline": args.baseline_run_dir, "arm": args.arm,
                       "n_rows": len(rows), "n_pca": args.n_pca, "n_splits": args.n_splits,
                       "downsample_examples": args.downsample_examples, "downsample_k": args.downsample_k},
              "targets": {}}
    rng = np.random.default_rng(args.seed)

    print("=" * 84)
    print(f"PHASE 4 SUBSET ANALYSIS  arm={args.arm}  expanded n_rows={len(rows)}  "
          f"baseline={args.baseline_run_dir}")
    for tgt in targets:
        y = PE.labels_for(rows, tgt)
        if y is None:
            continue
        li, layer, full_auc = pick_layer(X, y, groups, arm_mask, layers, args.n_pca, args.n_splits,
                                         args.seed)
        X2d = reduce_at_layer(X, li, args.n_pca)
        tr = {"layer": int(layer), "full_within_arm_auroc": round(float(full_auc), 3)}

        # ---- Analysis 1: downsample expanded to old size, K times ----
        uniq = np.array(sorted(set(ids.tolist())), dtype=object)
        ds = []
        for k in range(args.downsample_k):
            pick = set(rng.choice(uniq, size=min(args.downsample_examples, len(uniq)),
                                  replace=False).tolist())
            m = np.array([i for i, _ in enumerate(rows) if ids[i] in pick])
            sub_arm = arm_mask[m]
            r = auroc_within_arm(X2d[m], y[m], groups[m], sub_arm, args.n_splits, args.seed + k)
            if r["auroc"] is not None:
                ds.append(r["auroc"])
        tr["downsample_n220"] = {"k": len(ds), "auroc_mean": round(float(np.mean(ds)), 3) if ds else None,
                                 "auroc_min": round(float(np.min(ds)), 3) if ds else None,
                                 "auroc_max": round(float(np.max(ds)), 3) if ds else None}
        if base is not None:
            by = PE.labels_for(base["rows"], tgt)
            bi = li if li < len(base["layers"]) else len(base["layers"]) - 1
            bX2d = reduce_at_layer(base["X"], bi, args.n_pca)
            bmask = (base["arms"] == args.arm)
            tr["baseline_old_n220"] = auroc_within_arm(bX2d, by, base["groups"], bmask,
                                                       args.n_splits, args.seed)

        # ---- Analysis 2: AUROC by row subset (N-matched) ----
        subsets = {"original_v2": rtype == 0, "drift_onframe": rtype == 2,
                   "drift_adversarial": rtype == 1, "combined": np.ones(len(rows), bool)}
        # N-match: cap each subset's within-arm rows to the smallest non-combined subset
        per = {}
        arm_counts = []
        for name, mask in subsets.items():
            if name == "combined":
                continue
            arm_counts.append(int((mask & arm_mask).sum()))
        cap = max(20, min(arm_counts)) if arm_counts else 0
        for name, mask in subsets.items():
            sm = mask & arm_mask
            idxs = np.where(sm)[0]
            full = auroc_within_arm(X2d, y, groups, sm, args.n_splits, args.seed)
            matched = None
            if name != "combined" and len(idxs) > cap:
                pick = rng.choice(idxs, size=cap, replace=False)
                mm = np.zeros(len(rows), bool); mm[pick] = True
                matched = auroc_within_arm(X2d, y, groups, mm, args.n_splits, args.seed)
            per[name] = {"full": full, "n_matched_cap": (None if name == "combined" else cap),
                         "matched": matched}
        tr["by_subset"] = per

        # ---- Analysis 3: hidden -> row_type separability + adversarial margin ----
        ord_adv = np.isin(rtype, (0, 1))
        rt_y = (rtype[ord_adv] == 1).astype(int)
        sep = auroc_within_arm(X2d[ord_adv], rt_y, groups[ord_adv], arm_mask[ord_adv],
                               args.n_splits, args.seed)
        tr["hidden_predicts_rowtype_auroc"] = sep
        tr["margin_adversarial_vs_original"] = {
            "adversarial_auroc": per["drift_adversarial"]["full"]["auroc"],
            "original_auroc": per["original_v2"]["full"]["auroc"]}

        # ---- per-target verdict ----
        dsm = tr["downsample_n220"]["auroc_mean"]
        oldb = (tr.get("baseline_old_n220") or {}).get("auroc")
        adv = per["drift_adversarial"]["full"]["auroc"]
        orig = per["original_v2"]["full"]["auroc"]
        bits = []
        if oldb is not None and dsm is not None:
            bits.append("field_stress" if dsm - oldb >= 0.04 else "size_only")
        if dsm is not None and full_auc - dsm >= 0.04:
            bits.append("sample_size")
        if adv is not None and orig is not None and adv - orig >= 0.04:
            bits.append("stronger_adversarial_rows")
        tr["verdict_bits"] = bits or ["inconclusive"]
        report["targets"][tgt] = tr

        # ---- print ----
        print("-" * 84)
        print(f"TARGET {tgt}  (layer={layer}, full {args.arm} AUROC={full_auc:.3f})")
        b = tr["downsample_n220"]
        print(f"  [1] downsample->n220 (k={b['k']}): mean {b['auroc_mean']} [{b['auroc_min']},{b['auroc_max']}]"
              + (f"   old n220 baseline: {oldb}" if oldb is not None else "   (no baseline)")
              + f"   full n{len(rows)}: {full_auc:.3f}")
        print("  [2] within-arm AUROC by subset (full | N-matched@%s):" % cap)
        for name in ("original_v2", "drift_onframe", "drift_adversarial", "combined"):
            p = per[name]; f = p["full"]; mt = p["matched"]
            mtxt = "" if mt is None else f"  matched={mt['auroc']}"
            print(f"      {name:18} auroc={f['auroc']}  pos/neg={f['n_pos']}/{f['n_neg']}{mtxt}")
        print(f"  [3] hidden->row_type AUROC: {sep['auroc']}  "
              f"(adversarial {adv} vs original {orig} on the failure label)")
        print(f"  => verdict: {', '.join(tr['verdict_bits'])}")

    out = Path(args.out) if args.out else Path(args.run_dir) / "phase4_subset_analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print("=" * 84)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
