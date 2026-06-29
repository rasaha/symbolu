"""Branch D.1 — robustness & confound analysis of the Branch D positive.

Does the small phoneme-identity ΔR² over phonology survive (1) morphology + length
DECONFOUNDING and (2) rime-GROUPED, leakage-controlled cross-validation? Same
estimand / model class as Branch D. NOT Symbol-U validation; A′ halted; Stage A
untouched; no new theory.

    python3 experiments/branch_d/run_branch_d1.py [out.md]
"""
from __future__ import annotations

import os
import pathlib
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import repro as _repro, stats               # noqa: E402
from common.report import ReportBuilder                  # noqa: E402
from data import build_dataset                           # noqa: E402
from run_branch_d import incremental, _partial_r, K_PERM, MIN_PARTIAL_R, DATA_DIR  # noqa: E402

N_EFF_FLOOR = 800
ALPHA = 0.05
ENDPOINTS = ["valence", "arousal", "dominance"]


def _ridge_fit_predict(Xtr, ytr, Xte, lam=1.0):
    mu, sd = Xtr.mean(0), Xtr.std(0); sd[sd == 0] = 1.0
    Xtr = (Xtr - mu) / sd; Xte = (Xte - mu) / sd
    ymu = ytr.mean()
    A = Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1])
    beta = np.linalg.solve(A, Xtr.T @ (ytr - ymu))
    return Xte @ beta + ymu


def grouped_ridge_oof_r2(X, y, groups, k=5, lam=1.0, seed=0):
    """Out-of-fold R² with GROUP-disjoint folds (no group spans train & test)."""
    groups = np.asarray(groups)
    uniq = list(dict.fromkeys(groups.tolist()))
    order = stats.rng(seed).permutation(len(uniq))
    fold_of = {uniq[order[i]]: i % k for i in range(len(uniq))}
    fold_id = np.array([fold_of[g] for g in groups])
    pred = np.zeros(len(y))
    for f in range(k):
        te = np.where(fold_id == f)[0]
        tr = np.where(fold_id != f)[0]
        if te.size == 0 or tr.size == 0:
            continue
        pred[te] = _ridge_fit_predict(X[tr], y[tr], X[te], lam)
    ss_res = float(np.sum((y - pred) ** 2)); ss_tot = float(np.sum((y - y.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


def incremental_grouped(BASE, EXTRA, y, groups, K, seed):
    r2_base = grouped_ridge_oof_r2(BASE, y, groups, seed=seed)
    r2_test = grouped_ridge_oof_r2(np.hstack([BASE, EXTRA]), y, groups, seed=seed)
    delta = r2_test - r2_base
    rng = stats.rng(seed)
    null = np.array([grouped_ridge_oof_r2(np.hstack([BASE, EXTRA[rng.permutation(len(y))]]),
                                          y, groups, seed=seed) - r2_base for _ in range(K)])
    return {"r2_base": r2_base, "r2_test": r2_test, "delta": delta,
            "partial_r": _partial_r(delta, r2_base),
            "null_p95": float(np.percentile(null, 95)),
            "p": stats.permutation_pvalue(delta, null)}


def _sig(r):
    return r["delta"] > r["null_p95"] and r["p"] < ALPHA and r["partial_r"] >= 0.05


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else (Path(__file__).resolve().parent / "BRANCH_D1_RESULT.md")
    t0 = time.perf_counter()
    cmu, pp, war = DATA_DIR / "cmudict.dict", DATA_DIR / "ipa_all.csv", DATA_DIR / "warriner.csv"
    if not (cmu.exists() and pp.exists() and war.exists()):
        ReportBuilder("BRANCH_D1_RESULT", "robustness test").decision("INCONCLUSIVE").para(
            f"inputs absent in {DATA_DIR}").write(out); print("DATA_BLOCKED (inputs absent)"); return 0

    ds = build_dataset(cmu, pp, war)
    n = ds["n"]; PHON, NUIS, Emax, Y = ds["PHON"], ds["NUIS"], ds["E_max"], ds["Y"]
    DECONF = np.hstack([PHON, NUIS])
    rime = ds["rime_groups"]
    feasible = n >= N_EFF_FLOOR

    A = {}
    if feasible:
        for j, name in enumerate(ENDPOINTS):
            y = Y[:, j]
            A[name] = {
                "orig":        incremental(PHON, Emax, y, K_PERM, seed=13),       # Branch D
                "deconf":      incremental(DECONF, Emax, y, K_PERM, seed=13),     # +morph+length
                "grouped":     incremental_grouped(PHON, Emax, y, rime, K_PERM, seed=13),
                "deconf_grp":  incremental_grouped(DECONF, Emax, y, rime, K_PERM, seed=13),
            }

    if not feasible:
        decision = "INCONCLUSIVE"
    else:
        v = A["valence"]
        if _sig(v["deconf_grp"]) and _sig(v["deconf"]) and _sig(v["grouped"]):
            decision = "ROBUST_UPPER_BOUND_POSITIVE"
        elif not _sig(v["deconf"]) and not _sig(v["grouped"]):
            decision = "UPPER_BOUND_NULL_AFTER_CONTROLS"
        else:
            decision = "CONFOUNDED_POSITIVE"

    rb = ReportBuilder(
        "BRANCH_D1_RESULT — robustness & confound analysis (measured)",
        "Robustness of the Branch D phoneme-identity upper bound under morphology/length "
        "deconfounding and rime-grouped leakage-controlled CV. **Not Symbol-U validation, not A′ "
        "PASS/FAIL/⊥.** A′ halted; Stage A untouched; linear/additive model class; English lexicon. "
        "Y = Warriner VAD (academic norms; not redistributed).")
    rb.decision(decision)
    rb.section("Setup")
    rb.bullets([
        f"joined N = {n}; rime groups = {len(set(rime))} (leakage-controlled CV).",
        f"DECONF baseline adds n_letters + {NUIS.shape[1]-1} suffix/prefix morphology indicators "
        f"to the {PHON.shape[1]}-dim PHON baseline.",
        "duplicate pronunciations: first CMUdict entry per word (variants skipped).",
        "frequency (SUBTLEX) & concreteness (Brysbaert): not reachable on quick GitHub probe → "
        "omitted (stated).",
        "primary null: row-permutation of E_max, K=%d; grouped tests use rime-disjoint folds." % K_PERM,
    ])
    if feasible:
        for name in ENDPOINTS:
            rb.section(f"Endpoint: {name}")
            rows = []
            for cond, label in [("orig", "original (PHON, random CV) = Branch D"),
                                ("deconf", "deconfounded (PHON+morph+length, random CV)"),
                                ("grouped", "rime-grouped CV (PHON)"),
                                ("deconf_grp", "deconfounded + rime-grouped (decisive)")]:
                r = A[name][cond]
                rows.append((label, f"{r['r2_base']:.4f}", f"{r['r2_test']:.4f}",
                             f"{r['delta']:.4f}", f"{r['partial_r']:.3f}", f"{r['p']:.3g}",
                             "yes" if _sig(r) else "no"))
            rb.table(["condition", "R²(base)", "R²(base+E_max)", "ΔR²", "partial r", "perm p",
                      "survives"], rows)
    rb.section("Decision & interpretation")
    if decision == "ROBUST_UPPER_BOUND_POSITIVE":
        rb.para("The phoneme-identity increment survives BOTH morphology/length deconfounding AND "
                "rime-grouped leakage-controlled CV on valence. The (still small) upper bound is "
                "not explained by the obvious lexical confounds tested. Not Symbol-U validation.")
    elif decision == "CONFOUNDED_POSITIVE":
        rb.para("The Branch D increment is largely a lexical confound: it weakens or disappears "
                "under deconfounding and/or rime-grouped CV. The residual phoneme-level signal is "
                "smaller than Branch D suggested.")
    elif decision == "UPPER_BOUND_NULL_AFTER_CONTROLS":
        rb.para("After morphology/length controls and rime-grouped CV, phoneme identity adds no "
                "significant information about valence beyond phonology. The Branch D positive does "
                "not survive obvious confounds: no deterministic phoneme-level essence table can "
                "improve prediction here once lexical confounds are removed (this dataset, linear "
                "model class).")
    else:
        rb.para("Underpowered / not feasible.")
    rb.para("Caveat: morphology proxies are orthographic and coarse; rime grouping controls "
            "rhyme-family leakage, not all etymological structure; frequency/concreteness not "
            "included. Conclusions hold for the linear/additive model class and the English testbed.")

    body = rb.build()
    meta = _repro.collect_metadata(
        config={"K_perm": K_PERM, "n_eff_floor": N_EFF_FLOOR, "endpoints": ENDPOINTS,
                "deconf_dims": int(DECONF.shape[1]), "n_rime_groups": len(set(rime))},
        seed=13, runtime_s=time.perf_counter() - t0,
        outputs={"report_body": _repro.sha256_text(body)})
    rb.repro_block(meta).footer()
    md = rb.write(out); print(md); print(f"[written] {out}  decision={decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
