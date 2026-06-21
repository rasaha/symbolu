#!/usr/bin/env python3
"""phase4_probe_eval.py — Phase 4 Stage-B (hidden-only baseline). Tests H1 only.

H1: can the last-prompt-token, PRE-generation hidden state linearly predict a Phase 3 audit outcome
(audit_fail, frame_violation)? CPU-only. NO learned Bhava directions, NO hidden_plus_bhava, NO
incremental-value claim, NO generation control, NO LLM rerun — this is the honest baseline that gates
whether the Bhava work (Stage-B2) is worth building.

Rigor: probes run PER ARM (base-only, framed-only) as the honest primary, because the arm is a strong
confound — base and framed prompts have very different hidden states AND different audit base-rates, so
a pooled probe could "predict audit_fail" merely by detecting base-vs-framed. A pooled probe is also
reported, guarded by an arm-confound leakage check. Grouped-by-term CV throughout; in-fold PCA;
bootstrap AUROC CIs.

  python phase4_probe_eval.py --run-dir runs/csr_phase4 \
    --targets audit_fail,frame_violation --exploratory rejected_domain_leak,secondary_promoted \
    --out runs/csr_phase4/phase4_probe_eval.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import phase4_probe as PB              # noqa: E402
from csr_match_filter.match import dominant_terms            # noqa: E402

DECISIONS = ("PHASE4_HIDDEN_STATE_PREDICTIVE", "PHASE4_NOT_PREDICTIVE",
             "PHASE4_INSUFFICIENT_LABEL_POWER", "PHASE4_LEAKAGE_SUSPECTED")
ZERO_DELTA = {"delta": 0.0, "ci_low": 0.0, "ci_high": 0.0, "excludes_zero": False}


# ---- load -----------------------------------------------------------------------------------------

def load_run(run_dir):
    run = Path(run_dir)
    d = np.load(run / "phase4_activations.npz", allow_pickle=True)
    X = np.asarray(d["X"], dtype=float)                       # [N, n_layers, d_model]
    layers = [int(l) for l in d["layers"]]
    rows = [json.loads(l) for l in (run / "phase4_metadata.jsonl").read_text().splitlines() if l.strip()]
    arms = np.array([r["arm"] for r in rows], dtype=object)
    return X, layers, arms, rows


def groups_for(rows):
    """Group-by-term: dominant term of the query (falls back to id) — prevents term leakage in CV."""
    g = []
    for r in rows:
        terms = dominant_terms(r.get("query", "")) if r.get("query") else []
        g.append(terms[0] if terms else r["id"])
    return np.array(g, dtype=object)


def labels_for(rows, key):
    """Returns (y or None). None if any row lacks a label (caller treats as unusable)."""
    if any(r.get("labels") is None for r in rows):
        return None
    return np.array([1 if r["labels"].get(key) else 0 for r in rows], dtype=int)


# ---- per-layer + nested honest AUROC --------------------------------------------------------------

def layer_sweep(X3d, y, groups, layers, n_pca, n_splits, seed):
    return {int(L): float(PB.evaluate_probe(X3d[:, i, :], y, groups, n_splits=n_splits,
                                            n_pca=n_pca, seed=seed)["auroc"])
            for i, L in enumerate(layers)}


def nested_layer_auroc(X3d, y, groups, layers, n_pca, n_splits, seed):
    """Honest AUROC with the best layer chosen INSIDE each outer-train fold (no global cherry-pick)."""
    y = np.asarray(y)
    groups = np.asarray(groups)
    oof = np.full(len(y), np.nan)
    chosen = []
    for tr, te in PB.group_kfold_indices(groups, n_splits, seed):
        if len(tr) == 0 or len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        best_i, best_auc = 0, -1.0
        for i, _L in enumerate(layers):
            s = PB.cv_oof_scores(X3d[tr][:, i, :], y[tr], groups[tr], n_splits=n_splits,
                                 n_pca=n_pca, seed=seed)
            m = ~np.isnan(s)
            a = PB.auroc(y[tr][m], s[m]) if m.any() else 0.5
            if a > best_auc:
                best_auc, best_i = a, i
        chosen.append(int(layers[best_i]))
        Xtr, Xte = X3d[tr][:, best_i, :], X3d[te][:, best_i, :]
        if n_pca and Xtr.shape[1] > n_pca:
            p = PB.pca_fit(Xtr, n_pca)
            Xtr, Xte = PB.pca_transform(p, Xtr), PB.pca_transform(p, Xte)
        mdl = PB.fit_logreg(Xtr, y[tr])
        oof[te] = PB.predict_proba(mdl, Xte)
    mask = ~np.isnan(oof)
    return oof, mask, chosen


def evaluate_unit(X3d, y, groups, layers, n_pca, n_splits, n_boot, seed, min_pos):
    pos, neg = int(y.sum()), int((y == 0).sum())
    n_groups = len(set(groups.tolist()))
    if pos < min_pos or neg < min_pos or n_groups < n_splits:
        return {"sufficient": False, "n_pos": pos, "n_neg": neg, "n_groups": n_groups,
                "reason": f"pos={pos}/neg={neg}/groups={n_groups} below min_pos={min_pos} "
                          f"or groups<{n_splits}"}
    sweep = layer_sweep(X3d, y, groups, layers, n_pca, n_splits, seed)
    best_layer = max(sweep, key=sweep.get)
    oof, mask, chosen = nested_layer_auroc(X3d, y, groups, layers, n_pca, n_splits, seed)
    ci = PB.bootstrap_auroc_ci(y[mask], oof[mask], n_boot=n_boot, seed=seed)
    return {"sufficient": True, "n_pos": pos, "n_neg": neg, "n_groups": n_groups,
            "n_splits": n_splits, "per_layer_auroc": sweep,
            "best_layer_sweep": int(best_layer), "best_layer_sweep_auroc": float(sweep[best_layer]),
            "honest_auroc": float(ci["auroc"]), "ci_low": float(ci["ci_low"]),
            "ci_high": float(ci["ci_high"]), "above_chance": bool(ci["above_chance"]),
            "chosen_layers_per_fold": chosen}


# ---- arm-confound leakage guard -------------------------------------------------------------------

def arm_confound(X3d, arm_bin, target_y, groups, layers, n_pca, n_splits, seed):
    """Two diagnostics: (1) can hidden states predict the ARM at all (they trivially should);
    (2) how well does ARM ALONE predict the target (the confound baseline a pooled probe must beat)."""
    hp = nested_layer_auroc(X3d, arm_bin, groups, layers, n_pca, n_splits, seed)
    hidden_predicts_arm = float(PB.auroc(arm_bin[hp[1]], hp[0][hp[1]])) if hp[1].any() else 0.5
    target_from_arm = float(PB.auroc(target_y, arm_bin.astype(float)))
    return {"hidden_predicts_arm_auroc": hidden_predicts_arm,
            "target_from_arm_only_auroc": max(target_from_arm, 1.0 - target_from_arm)}


# ---- decision -------------------------------------------------------------------------------------

def decide_target(units, confound, leak_margin=0.05, arm_floor=0.80, auroc_floor=0.55):
    """Headline H1 verdict, preferring confound-free PER-ARM evidence over the pooled probe."""
    arm_units = [u for k, u in units.items() if k in ("base", "framed") and u.get("sufficient")]
    pooled = units.get("pooled", {})
    any_sufficient = bool(arm_units) or pooled.get("sufficient")
    if not any_sufficient:
        return "PHASE4_INSUFFICIENT_LABEL_POWER"
    # genuine within-arm signal?
    predictive_arms = [u for u in arm_units if u["ci_low"] > 0.5 and u["honest_auroc"] >= auroc_floor]
    if predictive_arms:
        return "PHASE4_HIDDEN_STATE_PREDICTIVE"
    # only the (confounded) pooled probe shows signal?
    leak = (confound["hidden_predicts_arm_auroc"] >= arm_floor
            and (pooled.get("honest_auroc", 0.0) - confound["target_from_arm_only_auroc"]) < leak_margin)
    if pooled.get("sufficient") and pooled.get("ci_low", 0.0) > 0.5:
        return "PHASE4_LEAKAGE_SUSPECTED" if leak else "PHASE4_HIDDEN_STATE_PREDICTIVE"
    return "PHASE4_NOT_PREDICTIVE"


# ---- run ------------------------------------------------------------------------------------------

def reduce_layers(X3d, n_pca):
    """GLOBAL label-free PCA per layer, computed ONCE (33 SVDs, not 15k in-fold). Unsupervised — uses
    no labels, so there is NO target leakage; group-by-term CV still guards the probe. Returns
    [N, n_layers, n_pca]."""
    if not n_pca:
        return X3d
    outs = []
    for i in range(X3d.shape[1]):
        Xi = X3d[:, i, :]
        if Xi.shape[1] > n_pca:
            p = PB.pca_fit(Xi, n_pca)
            outs.append(PB.pca_transform(p, Xi))
        else:
            outs.append(Xi)
    return np.stack(outs, 1)


def run(run_dir, targets, exploratory, layers_arg, n_pca, n_splits, n_boot, seed, min_pos):
    X, all_layers, arms, rows = load_run(run_dir)
    layers = all_layers if layers_arg in (None, "all") else [int(x) for x in layers_arg.split(",")]
    lidx = [all_layers.index(L) for L in layers]
    X3d = X[:, lidx, :]
    Xred = reduce_layers(X3d, n_pca)                          # reduce once, then cheap 32-dim probes
    groups = groups_for(rows)
    arm_bin = (arms == "framed").astype(int)
    report = {"meta": {"run_dir": str(run_dir), "n_rows": len(rows), "layers": layers,
                       "n_pca": n_pca, "pca": "global_label_free_per_layer", "n_splits": n_splits,
                       "n_boot": n_boot, "seed": seed, "min_pos": min_pos, "stage": "B_hidden_only",
                       "tests": "H1_only"},
              "targets": {}}
    all_specs = [(t, "primary") for t in targets] + [(t, "exploratory") for t in exploratory]
    for key, role in all_specs:
        print(f"[phase4-probe] target={key} ({role}) …", flush=True)
        y = labels_for(rows, key)
        if y is None:
            report["targets"][key] = {"role": role, "decision": "PHASE4_INSUFFICIENT_LABEL_POWER",
                                      "note": "labels missing for some rows"}
            continue
        units = {}
        for unit, sel in (("base", arms == "base"), ("framed", arms == "framed"),
                          ("pooled", np.ones(len(rows), bool))):
            units[unit] = evaluate_unit(Xred[sel], y[sel], groups[sel], layers, None, n_splits,
                                        n_boot, seed, min_pos)   # Xred already PCA-reduced -> n_pca=None
        confound = arm_confound(Xred, arm_bin, y, groups, layers, None, n_splits, seed)
        decision = decide_target(units, confound)
        report["targets"][key] = {
            "role": role, "balance": {"pooled_pos": int(y.sum()), "pooled_neg": int((y == 0).sum()),
                                      "base_pos": int(y[arms == "base"].sum()),
                                      "framed_pos": int(y[arms == "framed"].sum())},
            "arm_confound": confound, "units": units, "decision": decision}
    return report


# ---- markdown -------------------------------------------------------------------------------------

def to_markdown(report):
    m = report["meta"]
    out = ["# Phase 4 Stage-B (hidden-only) — H1 results", "",
           f"Run `{m['run_dir']}` · n_rows={m['n_rows']} · layers={len(m['layers'])} · "
           f"PCA={m['n_pca']} · {m['n_splits']}-fold group-by-term CV · {m['n_boot']} bootstraps · "
           f"seed={m['seed']}.", "",
           "> Hidden-only baseline (H1). No Bhava, no incremental-value claim. **Per-arm is the honest "
           "verdict** (arm is a confound); pooled is shown with an arm-confound leakage guard.", "",
           "| target | role | decision | per-arm honest AUROC [95% CI] (base / framed) | pooled AUROC | "
           "pos/neg (b/f) | best layer | arm-confound |", "|---|---|---|---|---|---|---|---|"]
    for k, t in report["targets"].items():
        if "units" not in t:
            out.append(f"| {k} | {t['role']} | {t['decision']} | — | — | — | — | {t.get('note','')} |")
            continue
        u = t["units"]

        def cell(unit):
            x = u.get(unit, {})
            if not x.get("sufficient"):
                return "insufficient"
            return f"{x['honest_auroc']:.3f} [{x['ci_low']:.2f},{x['ci_high']:.2f}]"
        bal = t["balance"]
        cf = t["arm_confound"]
        bl = u.get("framed", {}).get("best_layer_sweep") or u.get("base", {}).get("best_layer_sweep") or "—"
        out.append(
            f"| {k} | {t['role']} | **{t['decision']}** | {cell('base')} / {cell('framed')} | "
            f"{cell('pooled')} | {bal['pooled_pos']}/{bal['pooled_neg']} "
            f"({bal['base_pos']}/{bal['framed_pos']}) | {bl} | "
            f"arm←hidden {cf['hidden_predicts_arm_auroc']:.2f}; tgt←arm "
            f"{cf['target_from_arm_only_auroc']:.2f} |")
    out += ["", "### Interpretation",
            "- `PHASE4_HIDDEN_STATE_PREDICTIVE` (within-arm, CI above 0.5) → proceed to Stage-B2 "
            "(learned Bhava directions + strict incremental-value gate).",
            "- `PHASE4_NOT_PREDICTIVE` → stop Phase 4 cheaply or expand the dataset before trying Bhava.",
            "- `PHASE4_LEAKAGE_SUSPECTED` → the only signal rides the base-vs-framed arm confound, not "
            "a genuine state→outcome read.",
            "- `PHASE4_INSUFFICIENT_LABEL_POWER` → too few positives/groups to decide (expected for the "
            "rare exploratory labels at n=110)."]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="runs/csr_phase4")
    ap.add_argument("--targets", default="audit_fail,frame_violation")
    ap.add_argument("--exploratory", default="rejected_domain_leak,secondary_promoted")
    ap.add_argument("--layers", default="all")
    ap.add_argument("--n-pca", type=int, default=32)
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-pos", type=int, default=15)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    expl = [t.strip() for t in args.exploratory.split(",") if t.strip()]
    report = run(args.run_dir, targets, expl, args.layers, args.n_pca, args.n_splits, args.n_boot,
                 args.seed, args.min_pos)
    out = Path(args.out) if args.out else Path(args.run_dir) / "phase4_probe_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    md = out.with_suffix(".md")
    md.write_text(to_markdown(report))
    print("=" * 80)
    print("PHASE 4 STAGE-B (hidden-only, H1)")
    for k, t in report["targets"].items():
        if "units" not in t:
            print(f"  {k:22} [{t['role']}]  {t['decision']}  ({t.get('note','')})")
            continue
        b, f, p = (t["units"].get(u, {}) for u in ("base", "framed", "pooled"))
        def fmt(x):
            return (f"{x['honest_auroc']:.3f}[{x['ci_low']:.2f},{x['ci_high']:.2f}]"
                    if x.get("sufficient") else "insuf")
        print(f"  {k:22} [{t['role']:11}] {t['decision']}")
        print(f'       base={fmt(b)}  framed={fmt(f)}  pooled={fmt(p)}  '
              f"(pos/neg={t['balance']['pooled_pos']}/{t['balance']['pooled_neg']})")
        print(f"       arm-confound: hidden→arm={t['arm_confound']['hidden_predicts_arm_auroc']:.2f}  "
              f"target←arm-only={t['arm_confound']['target_from_arm_only_auroc']:.2f}")
    print(f"\nwrote {out}\nwrote {md}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
