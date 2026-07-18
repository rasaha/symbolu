#!/usr/bin/env python3
"""phase4d_residual_bhava.py — Phase 4D: Guna/Vritti-controlled residual Bhava test. CPU-only.

Implements docs/CSR_MATCH_FILTER_PHASE4D_RESIDUAL_BHAVA.md. NEW pre-registered experiment (NOT a
re-roll of the closed Stage-B2 taxonomy). Removes Guna-like (quality) and Vritti-like (drift) directions
from the hidden state (fit in train folds, projected out), then tests whether the UNSUPERVISED residual
(top PCs) adds diagnostic value for the failure targets beyond hidden-only / Guna / Vritti / Guna+Vritti
/ dimension-matched random / surface n-gram. No Bhava wiring, no model/weight/logit/hidden-state change,
no Phase 1-3 change.

  python phase4d_residual_bhava.py --run-dir runs/csr_phase4_v3 \
    --targets frame_violation,rejected_domain_leak --secondary audit_fail \
    --exploratory secondary_promoted --out runs/csr_phase4_v3/phase4d_residual_bhava.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import phase4_probe as PB              # noqa: E402
from csr_match_filter import phase4_probe_eval as PE         # noqa: E402
from csr_match_filter import phase4_subset_analysis as SA    # noqa: E402
from csr_match_filter import phase4_stageb2_bhava as B2      # ngram_features  # noqa: E402

LEAK_THR = 0.70
MIN_DELTA = 0.05
HIDDEN_FLOOR = 0.60
EFF_RANK_MIN = 3.0
GV_SUFF_MARGIN = 0.03
MIN_POS = 15
DRIFT = ("frame_violation", "rejected_domain_leak", "secondary_promoted")


def get_label(rows, key):
    if any(r.get("labels") is None for r in rows):
        return None
    return np.array([1 if r["labels"].get(key) else 0 for r in rows], dtype=int)


def guna_label(rows):
    if any(r.get("labels") is None for r in rows):
        return None
    return np.array([1 if (r["labels"].get("answer_too_generic")
                           or r["labels"].get("factuality_suspected")) else 0
                     for r in rows], dtype=int)


def vritti_label(rows, target):
    """Drift finding-types OR'd, MINUS the evaluated target (target-specific hygiene)."""
    if any(r.get("labels") is None for r in rows):
        return None
    keys = [k for k in DRIFT if k != target]
    return np.array([1 if any(r["labels"].get(k) for k in keys) else 0 for r in rows], dtype=int)


# ---- residualization primitives ------------------------------------------------------------------

def _std(Xtr, Xte):
    mu = Xtr.mean(0)
    sd = np.where(Xtr.std(0) < 1e-8, 1.0, Xtr.std(0))
    return (Xtr - mu) / sd, (Xte - mu) / sd


def orthobasis(vecs):
    """Gram-Schmidt orthonormal basis of the given direction vectors."""
    B = []
    for v in vecs:
        w = np.asarray(v, float).copy()
        for b in B:
            w = w - (w @ b) * b
        nrm = np.linalg.norm(w)
        if nrm > 1e-8:
            B.append(w / nrm)
    return np.array(B) if B else np.zeros((0, len(vecs[0]) if vecs else 0))


def residualize(Xs, B):
    if B.shape[0] == 0:
        return Xs
    return Xs - (Xs @ B.T) @ B


def _maxauroc(y, lab):
    a = PB.auroc(y, np.asarray(lab, float))
    return max(a, 1.0 - a)


# ---- one (target, arm) evaluation ----------------------------------------------------------------

def evaluate_residual(Xrich, y, guna, vritti, groups, Xng, hidden_dim, resid_dim, n_splits, seed,
                      n_boot):
    y = np.asarray(y)
    n = len(y)
    keys = ("hidden", "guna", "vritti", "gv", "residual", "hb", "random", "ngram")
    oof = {k: np.full(n, np.nan) for k in keys}
    rbdims = []
    rng = np.random.default_rng(seed + 211)
    for tr, te in PB.group_kfold_indices(groups, n_splits, seed):
        if len(tr) == 0 or len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        Xs_tr, Xs_te = _std(Xrich[tr], Xrich[te])
        gdir = PB.fit_logreg(Xs_tr, guna[tr].astype(float))["w"] if len(set(guna[tr].tolist())) > 1 \
            else np.zeros(Xs_tr.shape[1])
        vdir = PB.fit_logreg(Xs_tr, vritti[tr].astype(float))["w"] if len(set(vritti[tr].tolist())) > 1 \
            else np.zeros(Xs_tr.shape[1])
        B = orthobasis([gdir, vdir])
        res_tr, res_te = residualize(Xs_tr, B), residualize(Xs_te, B)
        p = PB.pca_fit(res_tr, resid_dim)
        rb_tr, rb_te = PB.pca_transform(p, res_tr), PB.pca_transform(p, res_te)
        rbdim = rb_tr.shape[1]
        rbdims.append(rbdim)
        h_tr, h_te = Xs_tr[:, :hidden_dim], Xs_te[:, :hidden_dim]
        gp = lambda M, d: (M @ d)[:, None]                     # noqa: E731
        # dimension-matched control = INDEPENDENT noise dims (the "more dims for free" null),
        # NOT a random projection of the data (which would leak the target signal).
        noise_tr = rng.standard_normal((len(tr), rbdim)) if rbdim else np.zeros((len(tr), 0))
        noise_te = rng.standard_normal((len(te), rbdim)) if rbdim else np.zeros((len(te), 0))
        feats = {
            "hidden": (h_tr, h_te),
            "guna": (gp(Xs_tr, gdir), gp(Xs_te, gdir)),
            "vritti": (gp(Xs_tr, vdir), gp(Xs_te, vdir)),
            "gv": (np.hstack([gp(Xs_tr, gdir), gp(Xs_tr, vdir)]),
                   np.hstack([gp(Xs_te, gdir), gp(Xs_te, vdir)])),
            "residual": (rb_tr, rb_te),
            "hb": (np.hstack([h_tr, rb_tr]), np.hstack([h_te, rb_te])),
            "random": (np.hstack([h_tr, noise_tr]), np.hstack([h_te, noise_te])),
            "ngram": (Xng[tr], Xng[te]),
        }
        for k, (Ftr, Fte) in feats.items():
            if Ftr.shape[1] == 0:
                oof[k][te] = float(y[tr].mean())
                continue
            m = PB.fit_logreg(Ftr, y[tr])
            oof[k][te] = PB.predict_proba(m, Fte)
    mask = ~np.isnan(oof["hb"])
    ym = y[mask]
    auc = {k: round(float(PB.auroc(ym, oof[k][mask])), 3) for k in keys}
    return {"auroc": auc, "resid_dim": int(np.median(rbdims)) if rbdims else 0,
            "delta_vs_hidden": PB.bootstrap_auroc_delta(ym, oof["hb"][mask], oof["hidden"][mask], n_boot, seed),
            "delta_vs_random": PB.bootstrap_auroc_delta(ym, oof["hb"][mask], oof["random"][mask], n_boot, seed),
            "delta_vs_ngram": PB.bootstrap_auroc_delta(ym, oof["hb"][mask], oof["ngram"][mask], n_boot, seed),
            "oof": oof, "mask": mask}


def gate_passes(r):
    return all(r[d]["delta"] >= MIN_DELTA and r[d]["excludes_zero"]
               for d in ("delta_vs_hidden", "delta_vs_random", "delta_vs_ngram"))


def decide(leak_auroc, eff_rank, configs, hidden_auroc, gv_auroc, n_pos, n_neg):
    if n_pos < MIN_POS or n_neg < MIN_POS:
        return "PHASE4D_INSUFFICIENT_LABEL_POWER"
    if leak_auroc is not None and leak_auroc > LEAK_THR:
        return "PHASE4D_LEAKAGE_SUSPECTED"
    if eff_rank < EFF_RANK_MIN:
        return "PHASE4D_RESIDUAL_BHAVA_COLLAPSE"
    if configs and sum(c["gate"] for c in configs) / len(configs) >= 0.80:
        return "PHASE4D_RESIDUAL_BHAVA_ADDS_SIGNAL"
    if gv_auroc is not None and hidden_auroc is not None and gv_auroc >= hidden_auroc - GV_SUFF_MARGIN \
            and gv_auroc >= HIDDEN_FLOOR:
        return "PHASE4D_GUNA_VRITTI_SUFFICIENT"
    if (hidden_auroc or 0) >= HIDDEN_FLOOR:
        return "PHASE4D_HIDDEN_ONLY_SUFFICIENT"
    return "PHASE4D_RESIDUAL_BHAVA_NO_INCREMENTAL_SIGNAL"


def pick_layer(Xrich_all, y, groups, arm_mask, n_layers, hidden_dim, n_splits, seed):
    best_i, best = 0, -1.0
    for i in range(n_layers):
        a = SA.auroc_within_arm(Xrich_all[:, i, :hidden_dim], y, groups, arm_mask, n_splits, seed)["auroc"]
        if a is not None and a > best:
            best, best_i = a, i
    return best_i, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="runs/csr_phase4_v3")
    ap.add_argument("--targets", default="frame_violation,rejected_domain_leak")
    ap.add_argument("--secondary", default="audit_fail")
    ap.add_argument("--exploratory", default="secondary_promoted")
    ap.add_argument("--arm", default="framed", choices=["framed", "base"])
    ap.add_argument("--rich-dim", type=int, default=256)
    ap.add_argument("--hidden-dims", default="32,64")
    ap.add_argument("--resid-dim", type=int, default=12)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--ngram-dim", type=int, default=512)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    secondary = [t.strip() for t in args.secondary.split(",") if t.strip()]
    exploratory = [t.strip() for t in args.exploratory.split(",") if t.strip()]
    hidden_dims = [int(x) for x in args.hidden_dims.split(",")]
    seeds = [int(s) for s in args.seeds.split(",")]

    X, layers, arms, rows = PE.load_run(args.run_dir)
    groups = PE.groups_for(rows)
    rtype = SA.row_type(rows)
    arm_mask = (arms == args.arm)
    Xng = B2.ngram_features([r.get("query", "") for r in rows], args.ngram_dim)
    Xrich_all = np.stack([(lambda Xi: PB.pca_transform(PB.pca_fit(Xi, args.rich_dim), Xi)
                           if Xi.shape[1] > args.rich_dim else Xi)(X[:, i, :])
                          for i in range(len(layers))], axis=1)
    guna = guna_label(rows)

    report = {"meta": {"run_dir": args.run_dir, "arm": args.arm, "rich_dim": args.rich_dim,
                       "hidden_dims": hidden_dims, "resid_dim": args.resid_dim, "seeds": seeds,
                       "leak_thr": LEAK_THR, "min_delta": MIN_DELTA, "stage": "4D_residual_bhava"},
              "targets": {}}
    spec = [(t, "primary") for t in targets] + [(t, "secondary") for t in secondary] \
        + [(t, "exploratory") for t in exploratory]
    print("=" * 90)
    print(f"PHASE 4D — Guna/Vritti-controlled residual Bhava  arm={args.arm}  rich_dim={args.rich_dim}")

    for tgt, role in spec:
        y = get_label(rows, tgt)
        if y is None or guna is None:
            continue
        vritti = vritti_label(rows, tgt)
        npos, nneg = int(y[arm_mask].sum()), int((y[arm_mask] == 0).sum())
        li, _ = pick_layer(Xrich_all, y, groups, arm_mask, len(layers), min(hidden_dims),
                           args.n_splits, seeds[0])
        Xrich = Xrich_all[:, li, :]
        am = arm_mask

        # leakage gate: do control labels predict the target (within-arm)?
        leak = {"guna": round(_maxauroc(y[am], guna[am]), 3),
                "vritti": round(_maxauroc(y[am], vritti[am]), 3),
                "guna_or_vritti": round(_maxauroc(y[am], ((guna | vritti)[am])), 3)}
        leak_auroc = max(leak.values())

        configs, last = [], None
        for hd in hidden_dims:
            for sd in seeds:
                r = evaluate_residual(Xrich[am], y[am], guna[am], vritti[am], groups[am], Xng[am],
                                      hd, args.resid_dim, args.n_splits, sd, args.n_boot)
                configs.append({"hidden_dim": hd, "seed": sd, "gate": bool(gate_passes(r)),
                                "resid_dim": r["resid_dim"], **{f"auroc_{k}": v for k, v in r["auroc"].items()},
                                "d_hidden": round(r["delta_vs_hidden"]["delta"], 3),
                                "d_random": round(r["delta_vs_random"]["delta"], 3),
                                "d_ngram": round(r["delta_vs_ngram"]["delta"], 3)})
                last = r
        # collapse diagnostic on full arm data
        Xs = (Xrich[am] - Xrich[am].mean(0)) / np.where(Xrich[am].std(0) < 1e-8, 1.0, Xrich[am].std(0))
        gd = PB.fit_logreg(Xs, guna[am].astype(float))["w"] if len(set(guna[am].tolist())) > 1 else np.zeros(Xs.shape[1])
        vd = PB.fit_logreg(Xs, vritti[am].astype(float))["w"] if len(set(vritti[am].tolist())) > 1 else np.zeros(Xs.shape[1])
        res_full = residualize(Xs, orthobasis([gd, vd]))
        rb_full = PB.pca_transform(PB.pca_fit(res_full, args.resid_dim), res_full)
        eff = PB.effective_rank(rb_full) if rb_full.shape[1] else 0.0
        hidden_auroc = float(np.mean([c["auroc_hidden"] for c in configs])) if configs else None
        gv_auroc = float(np.mean([c["auroc_gv"] for c in configs])) if configs else None
        decision = decide(leak_auroc, eff, configs, hidden_auroc, gv_auroc, npos, nneg)

        rowtype_bd = {}
        if last is not None:
            sub = rtype[am][last["mask"]]; ym = y[am][last["mask"]]
            for nm, val in (("ordinary", 0), ("adversarial", 1)):
                sm = sub == val
                if sm.sum() > 20 and len(set(ym[sm].tolist())) == 2:
                    rowtype_bd[nm] = {"hidden": round(float(PB.auroc(ym[sm], last["oof"]["hidden"][last["mask"]][sm])), 3),
                                      "hb": round(float(PB.auroc(ym[sm], last["oof"]["hb"][last["mask"]][sm])), 3),
                                      "n": int(sm.sum())}

        report["targets"][tgt] = {"role": role, "layer": int(layers[li]), "n_pos": npos, "n_neg": nneg,
                                  "leakage": leak, "leak_auroc": round(leak_auroc, 3),
                                  "residual_effective_rank": round(float(eff), 2),
                                  "hidden_auroc_mean": round(hidden_auroc, 3) if hidden_auroc else None,
                                  "gv_auroc_mean": round(gv_auroc, 3) if gv_auroc else None,
                                  "configs": configs, "by_row_type": rowtype_bd, "decision": decision}
        print("-" * 90)
        print(f"TARGET {tgt} [{role}] layer={layers[li]} pos/neg={npos}/{nneg}  leak(g/v/gv)="
              f"{leak['guna']}/{leak['vritti']}/{leak['guna_or_vritti']}  resid_eff_rank={eff:.2f}")
        for c in configs:
            print(f"   hd={c['hidden_dim']} seed={c['seed']}: hidden={c['auroc_hidden']} "
                  f"gv={c['auroc_gv']} residual={c['auroc_residual']} hb={c['auroc_hb']} "
                  f"rand={c['auroc_random']} ngram={c['auroc_ngram']}  "
                  f"d_h={c['d_hidden']} d_r={c['d_random']} d_n={c['d_ngram']} gate={c['gate']}")
        if rowtype_bd:
            print(f"   by_row_type: {rowtype_bd}")
        print(f"   => DECISION: {decision}")

    prim = {t: report["targets"][t]["decision"] for t in targets if t in report["targets"]}
    ds = set(prim.values())
    overall = ("PHASE4D_RESIDUAL_BHAVA_ADDS_SIGNAL" if "PHASE4D_RESIDUAL_BHAVA_ADDS_SIGNAL" in ds
               else "PHASE4D_LEAKAGE_SUSPECTED" if "PHASE4D_LEAKAGE_SUSPECTED" in ds
               else "PHASE4D_RESIDUAL_BHAVA_COLLAPSE" if ds == {"PHASE4D_RESIDUAL_BHAVA_COLLAPSE"}
               else "PHASE4D_GUNA_VRITTI_SUFFICIENT" if "PHASE4D_GUNA_VRITTI_SUFFICIENT" in ds
               else "PHASE4D_HIDDEN_ONLY_SUFFICIENT" if "PHASE4D_HIDDEN_ONLY_SUFFICIENT" in ds
               else "PHASE4D_RESIDUAL_BHAVA_NO_INCREMENTAL_SIGNAL")
    report["overall_primary_verdict"] = overall
    out = Path(args.out) if args.out else Path(args.run_dir) / "phase4d_residual_bhava.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=lambda o: None))
    print("=" * 90)
    print(f"OVERALL PRIMARY VERDICT: {overall}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
