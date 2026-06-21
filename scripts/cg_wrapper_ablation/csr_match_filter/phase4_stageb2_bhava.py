#!/usr/bin/env python3
"""phase4_stageb2_bhava.py — Stage-B2: does a TARGET-ORTHOGONAL learned Bhava read add incremental
value over the static-h0 hidden-only baseline? CPU-only, analysis-only.

Implements docs/CSR_MATCH_FILTER_PHASE4_STAGEB2_BHAVA.md exactly. NO Bhava wiring into CSR, NO model/
weight/logit/hidden-state modification, NO Phase 1-3 change. The "Bhava read" = low-dim learned linear
directions in hidden space, supervised by a PRE-DECLARED object-mode taxonomy (never a failure label,
never drift/template type), fit INSIDE train folds only. Verdict comes only from the primary taxonomy;
named ablation taxonomies are reported but not decisive.

  python phase4_stageb2_bhava.py --run-dir runs/csr_phase4_v3 \
    --targets frame_violation,rejected_domain_leak --out runs/csr_phase4_v3/phase4_stageb2_bhava.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import phase4_probe as PB              # noqa: E402
from csr_match_filter import phase4_probe_eval as PE         # noqa: E402
from csr_match_filter import phase4_subset_analysis as SA    # noqa: E402
from csr_match_filter.match import dominant_terms            # noqa: E402

LEAK_THR = 0.60          # supervision must NOT predict the target above this (orthogonality)
MIN_DELTA = 0.05         # incremental-value margin
HIDDEN_FLOOR = 0.60      # h0 "strong" threshold (-> HIDDEN_ONLY_SUFFICIENT vs NO_INCREMENTAL_SIGNAL)
EFF_RANK_MIN = 3.0       # Bhava collapse threshold
MIN_POS = 15

# ---- PRE-DECLARED primary object-mode taxonomy (7 classes) ---------------------------------------
PRIMARY_MODES = ("person_role", "substance_element", "artifact_tool", "abstract_role",
                 "biological_natural", "place_system_context", "other_unknown")

_TERM_MODE = {
    # person_role (occupations / roles)
    **{t: "person_role" for t in (
        "doctor", "nurse", "surgeon", "cardiologist", "clinician", "paramedic", "therapist", "healer",
        "physician", "judge", "lawyer", "king", "soldier", "priest", "teacher", "engineer", "farmer",
        "banker", "programmer", "biologist", "astronomer", "chemist")},
    "mercury": "substance_element", "fire": "substance_element",
    "antivirus": "artifact_tool",
    "apple": "biological_natural", "python": "biological_natural", "virus": "biological_natural",
    "river": "biological_natural",
    "bank": "place_system_context",
}
_DOMAIN_MODE = {
    "medicine": "person_role", "care": "person_role", "law": "person_role", "education": "person_role",
    "military": "person_role", "religion": "person_role", "engineering": "person_role",
    "finance": "place_system_context", "commerce": "place_system_context",
    "programming": "artifact_tool", "technology": "artifact_tool", "security": "artifact_tool",
    "biology": "biological_natural", "nature": "biological_natural", "astronomy": "biological_natural",
    "fruit": "biological_natural", "chemistry": "substance_element",
}


def primary_mode(term, primary_domains):
    if term in _TERM_MODE:
        return _TERM_MODE[term]
    for d in (primary_domains or []):
        if d in _DOMAIN_MODE:
            return _DOMAIN_MODE[d]
    return "other_unknown"


def abl_person_vs_not(term, primary_domains):
    return "person" if primary_mode(term, primary_domains) == "person_role" else "nonperson"


def abl_domain_family(term, primary_domains):
    return (primary_domains or ["unknown"])[0]


TAXONOMIES = {"primary": primary_mode, "abl_person_vs_not": abl_person_vs_not,
              "abl_domain_family": abl_domain_family}


def modes_for(rows, fn):
    out = []
    for r in rows:
        terms = dominant_terms(r.get("query", "")) if r.get("query") else []
        term = terms[0] if terms else r.get("id", "")
        primary = (r.get("csr_frame_summary") or {}).get("primary") or []
        out.append(fn(term, primary))
    return np.array(out, dtype=object)


# ---- surface prompt-token n-gram baseline (hashing; no learning) ---------------------------------
def ngram_features(queries, dim=512):
    X = np.zeros((len(queries), dim), dtype=float)
    for i, q in enumerate(queries):
        toks = re.findall(r"[a-z0-9]+", (q or "").lower())
        grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for g in grams:
            X[i, hash(g) % dim] += 1.0
    return X


# ---- in-fold Bhava directions (supervised by object-mode, never the target) ----------------------
def fit_mode_directions(Xrich_tr, mode_tr, min_count=8):
    mu = Xrich_tr.mean(0)
    sd = np.where(Xrich_tr.std(0) < 1e-8, 1.0, Xrich_tr.std(0))
    Xs = (Xrich_tr - mu) / sd
    modes = [m for m in sorted(set(mode_tr.tolist()))
             if (mode_tr == m).sum() >= min_count and (mode_tr != m).sum() >= min_count]
    W = []
    for m in modes:
        model = PB.fit_logreg(Xs, (mode_tr == m).astype(float))
        W.append(model["w"])
    return {"mu": mu, "sd": sd, "W": np.array(W) if W else np.zeros((0, Xrich_tr.shape[1])),
            "modes": modes}


def bhava_read(dirs, Xrich):
    if dirs["W"].shape[0] == 0:
        return np.zeros((len(Xrich), 0))
    return ((Xrich - dirs["mu"]) / dirs["sd"]) @ dirs["W"].T


# ---- one (target, arm) evaluation: OOF for the five feature sets ----------------------------------
def evaluate_bhava(Xrich, y, groups, mode, Xng, hidden_dim, n_splits, seed, n_boot):
    y = np.asarray(y)
    n = len(y)
    oof = {k: np.full(n, np.nan) for k in
           ("hidden", "bhava", "hb", "random", "ngram")}
    bdim_seen = []
    rng = np.random.default_rng(seed + 101)
    for tr, te in PB.group_kfold_indices(groups, n_splits, seed):
        if len(tr) == 0 or len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        dirs = fit_mode_directions(Xrich[tr], mode[tr])
        b_tr, b_te = bhava_read(dirs, Xrich[tr]), bhava_read(dirs, Xrich[te])
        bdim = b_tr.shape[1]
        bdim_seen.append(bdim)
        h_tr, h_te = Xrich[tr][:, :hidden_dim], Xrich[te][:, :hidden_dim]
        rp = rng.standard_normal((Xrich.shape[1], max(bdim, 1)))
        r_tr = (Xrich[tr] @ rp)[:, :bdim] if bdim else np.zeros((len(tr), 0))
        r_te = (Xrich[te] @ rp)[:, :bdim] if bdim else np.zeros((len(te), 0))
        feats = {
            "hidden": (h_tr, h_te),
            "bhava": (b_tr, b_te) if bdim else (h_tr[:, :1] * 0, h_te[:, :1] * 0),
            "hb": (np.hstack([h_tr, b_tr]), np.hstack([h_te, b_te])),
            "random": (np.hstack([h_tr, r_tr]), np.hstack([h_te, r_te])),
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
    auc = {k: PB.auroc(ym, oof[k][mask]) for k in oof}
    d_hidden = PB.bootstrap_auroc_delta(ym, oof["hb"][mask], oof["hidden"][mask], n_boot, seed)
    d_random = PB.bootstrap_auroc_delta(ym, oof["hb"][mask], oof["random"][mask], n_boot, seed)
    d_ngram = PB.bootstrap_auroc_delta(ym, oof["hb"][mask], oof["ngram"][mask], n_boot, seed)
    return {"auroc": {k: round(float(v), 3) for k, v in auc.items()},
            "bhava_dim": int(np.median(bdim_seen)) if bdim_seen else 0,
            "delta_vs_hidden": d_hidden, "delta_vs_random": d_random, "delta_vs_ngram": d_ngram,
            "oof": oof, "mask": mask}


def gate_passes(r):
    return (r["delta_vs_hidden"]["delta"] >= MIN_DELTA and r["delta_vs_hidden"]["excludes_zero"]
            and r["delta_vs_random"]["delta"] >= MIN_DELTA and r["delta_vs_random"]["excludes_zero"]
            and r["delta_vs_ngram"]["delta"] >= MIN_DELTA and r["delta_vs_ngram"]["excludes_zero"])


def decide_target(orth_auroc, eff_rank, configs, hidden_auroc, n_pos, n_neg):
    if n_pos < MIN_POS or n_neg < MIN_POS:
        return "PHASE4_INSUFFICIENT_LABEL_POWER"
    if orth_auroc is not None and orth_auroc > LEAK_THR:
        return "PHASE4_BHAVA_LEAKAGE_SUSPECTED"
    if eff_rank < EFF_RANK_MIN:
        return "PHASE4_BHAVA_COLLAPSE"
    if configs and sum(c["gate"] for c in configs) / len(configs) >= 0.80:
        return "PHASE4_BHAVA_ADDS_SIGNAL"
    return "PHASE4_HIDDEN_ONLY_SUFFICIENT" if (hidden_auroc or 0) >= HIDDEN_FLOOR \
        else "PHASE4_BHAVA_NO_INCREMENTAL_SIGNAL"


def pick_layer(Xrich_all, y, groups, arm_mask, n_layers_axis, hidden_dim, n_splits, seed):
    best_i, best = 0, -1.0
    for i in range(n_layers_axis):
        h = Xrich_all[:, i, :hidden_dim]
        r = SA.auroc_within_arm(h, y, groups, arm_mask, n_splits, seed)["auroc"]
        if r is not None and r > best:
            best, best_i = r, i
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
    queries = [r.get("query", "") for r in rows]
    Xng = ngram_features(queries, args.ngram_dim)
    # global label-free rich PCA per layer
    Xrich_all = np.stack([(lambda Xi: PB.pca_transform(PB.pca_fit(Xi, args.rich_dim), Xi)
                           if Xi.shape[1] > args.rich_dim else Xi)(X[:, i, :])
                          for i in range(len(layers))], axis=1)
    mode_vecs = {name: modes_for(rows, fn) for name, fn in TAXONOMIES.items()}

    report = {"meta": {"run_dir": args.run_dir, "arm": args.arm, "rich_dim": args.rich_dim,
                       "hidden_dims": hidden_dims, "seeds": seeds, "n_splits": args.n_splits,
                       "primary_taxonomy": "primary", "primary_modes": list(PRIMARY_MODES),
                       "leak_thr": LEAK_THR, "min_delta": MIN_DELTA,
                       "stage": "B2_bhava_incremental"},
              "orthogonality": {}, "targets": {}, "ablations": {}}

    spec = [(t, "primary") for t in targets] + [(t, "secondary") for t in secondary] \
        + [(t, "exploratory") for t in exploratory]
    print("=" * 86)
    print(f"PHASE 4 STAGE-B2 — learned Bhava incremental test  arm={args.arm}  "
          f"primary_taxonomy=7-class  rich_dim={args.rich_dim}")

    for tgt, role in spec:
        y = PE.labels_for(rows, tgt)
        if y is None:
            continue
        npos, nneg = int(y[arm_mask].sum()), int((y[arm_mask] == 0).sum())
        # pick layer on hidden-only baseline (smallest hidden_dim), report it
        li, base_auc = pick_layer(Xrich_all, y, groups, arm_mask, len(layers), min(hidden_dims),
                                  args.n_splits, seeds[0])
        Xrich = Xrich_all[:, li, :]

        # ---- orthogonality gate (PRIMARY taxonomy): does object-mode predict the target? ----
        m = mode_vecs["primary"]
        oh = np.zeros((len(rows), len(PRIMARY_MODES)))
        for j, name in enumerate(PRIMARY_MODES):
            oh[:, j] = (m == name).astype(float)
        orth = SA.auroc_within_arm(oh, y, groups, arm_mask, args.n_splits, seeds[0])["auroc"]
        report["orthogonality"][tgt] = {"primary_mode_predicts_target_auroc": orth,
                                        "leak_threshold": LEAK_THR}

        # ---- robustness over seeds x hidden_dim (within-arm) ----
        configs, last = [], None
        for hd in hidden_dims:
            for sd in seeds:
                r = evaluate_bhava(Xrich[arm_mask], y[arm_mask], groups[arm_mask], m[arm_mask],
                                   Xng[arm_mask], hd, args.n_splits, sd, args.n_boot)
                configs.append({"hidden_dim": hd, "seed": sd, "gate": bool(gate_passes(r)),
                                "auroc_hidden": r["auroc"]["hidden"], "auroc_hb": r["auroc"]["hb"],
                                "auroc_bhava": r["auroc"]["bhava"], "auroc_random": r["auroc"]["random"],
                                "auroc_ngram": r["auroc"]["ngram"],
                                "d_hidden": round(r["delta_vs_hidden"]["delta"], 3),
                                "d_random": round(r["delta_vs_random"]["delta"], 3),
                                "d_ngram": round(r["delta_vs_ngram"]["delta"], 3),
                                "bhava_dim": r["bhava_dim"]})
                last = r
        # collapse diagnostic: fit directions on full arm data, measure effective rank of the read
        dirs_full = fit_mode_directions(Xrich[arm_mask], m[arm_mask])
        eff = PB.effective_rank(bhava_read(dirs_full, Xrich[arm_mask])) if dirs_full["W"].shape[0] else 0.0
        hidden_auroc = float(np.mean([c["auroc_hidden"] for c in configs])) if configs else None
        decision = decide_target(orth, eff, configs, hidden_auroc, npos, nneg)

        # ---- row-type / stress-field breakdown (hidden vs hb on the last config) ----
        rowtype_bd = {}
        if last is not None:
            sub_rt = rtype[arm_mask][last["mask"]]
            ym = y[arm_mask][last["mask"]]
            for name, val in (("ordinary", 0), ("adversarial", 1)):
                sm = sub_rt == val
                if sm.sum() > 20 and len(set(ym[sm].tolist())) == 2:
                    rowtype_bd[name] = {
                        "auroc_hidden": round(float(PB.auroc(ym[sm], last["oof"]["hidden"][last["mask"]][sm])), 3),
                        "auroc_hb": round(float(PB.auroc(ym[sm], last["oof"]["hb"][last["mask"]][sm])), 3),
                        "n": int(sm.sum())}

        report["targets"][tgt] = {
            "role": role, "layer": int(layers[li]), "n_pos": npos, "n_neg": nneg,
            "orthogonality_auroc": orth, "bhava_effective_rank": round(float(eff), 2),
            "hidden_auroc_mean": round(hidden_auroc, 3) if hidden_auroc is not None else None,
            "configs": configs, "gate_pass_frac": round(sum(c["gate"] for c in configs) / len(configs), 3)
            if configs else 0.0, "by_row_type": rowtype_bd, "decision": decision}

        print("-" * 86)
        print(f"TARGET {tgt} [{role}]  layer={layers[li]}  pos/neg={npos}/{nneg}  "
              f"orthogonality(mode->target)={orth}  bhava_eff_rank={eff:.2f}")
        for c in configs:
            print(f"   hd={c['hidden_dim']} seed={c['seed']}: hidden={c['auroc_hidden']} "
                  f"hb={c['auroc_hb']} bhava={c['auroc_bhava']} rand={c['auroc_random']} "
                  f"ngram={c['auroc_ngram']}  d_h={c['d_hidden']} d_r={c['d_random']} "
                  f"d_n={c['d_ngram']}  gate={c['gate']}")
        if rowtype_bd:
            print(f"   by_row_type: {rowtype_bd}")
        print(f"   => DECISION: {decision}")

    # ---- ablation taxonomies: orthogonality only (reported, NOT decisive) ----
    for name in ("abl_person_vs_not", "abl_domain_family"):
        m = mode_vecs[name]
        report["ablations"][name] = {}
        for tgt, _role in spec:
            y = PE.labels_for(rows, tgt)
            if y is None:
                continue
            classes = sorted(set(m[arm_mask].tolist()))
            oh = np.stack([(m == c).astype(float) for c in classes], axis=1)
            a = SA.auroc_within_arm(oh, y, groups, arm_mask, args.n_splits, seeds[0])["auroc"]
            report["ablations"][name][tgt] = {"mode_predicts_target_auroc": a, "n_classes": len(classes)}

    primary_decisions = {t: report["targets"][t]["decision"] for t in targets if t in report["targets"]}
    ds = set(primary_decisions.values())
    if "PHASE4_BHAVA_ADDS_SIGNAL" in ds:
        overall = "PHASE4_BHAVA_ADDS_SIGNAL"
    elif "PHASE4_BHAVA_LEAKAGE_SUSPECTED" in ds:
        overall = "PHASE4_BHAVA_LEAKAGE_SUSPECTED"
    elif ds and ds == {"PHASE4_BHAVA_COLLAPSE"}:        # surface collapse rather than mask it
        overall = "PHASE4_BHAVA_COLLAPSE"
    elif "PHASE4_BHAVA_NO_INCREMENTAL_SIGNAL" in ds:
        overall = "PHASE4_BHAVA_NO_INCREMENTAL_SIGNAL"
    else:
        overall = "PHASE4_HIDDEN_ONLY_SUFFICIENT"
    report["overall_primary_verdict"] = overall

    out = Path(args.out) if args.out else Path(args.run_dir) / "phase4_stageb2_bhava.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # strip oof arrays before serialising
    for t in report["targets"].values():
        pass
    out.write_text(json.dumps(report, indent=2, default=lambda o: None))
    print("=" * 86)
    print(f"OVERALL PRIMARY VERDICT: {overall}")
    print(f"ablation orthogonality (reported, not decisive): "
          f"{json.dumps({k: {t: v['mode_predicts_target_auroc'] for t, v in d.items()} for k, d in report['ablations'].items()})}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
