"""Branch D — phoneme-identity semantic UPPER-BOUND test (real semantic measurement).

Estimates  I(Y ; phoneme-identity | phonology)  as the incremental cross-validated
R² of phoneme-identity counts (E_max) over a PanPhon articulatory baseline (PHON),
for Y = Warriner VAD. By the data-processing inequality this UPPER-BOUNDS the
incremental value of any deterministic phoneme-level essence table (linear/additive
model class). NOT Symbol-U validation: it can only falsify or bound the essence
effect. A′ remains halted; no Stage A modification; no L2 F; no decoders.

    python3 experiments/branch_d/run_branch_d.py [out.md]
    (reads CMUdict/PanPhon/Warriner from $BRANCH_D_DATA; emits DATA_BLOCKED if absent)
"""
from __future__ import annotations

import os
import pathlib
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import repro as _repro, stats           # noqa: E402
from common.report import ReportBuilder              # noqa: E402
from data import build_dataset                       # noqa: E402

K_PERM = 200
ALPHA = 0.05
MIN_PARTIAL_R = 0.10          # meaningful incremental effect (matches A′ pre-reg)
N_EFF_FLOOR = 800
ENDPOINTS = ["valence", "arousal", "dominance"]
DATA_DIR = Path(os.environ.get(
    "BRANCH_D_DATA",
    "/tmp/claude-0/-home-user-symbolu/e6c5059c-bd37-54fe-a8ea-d7b7bc12b135/scratchpad/branchD"))


def _partial_r(delta, r2_base):
    denom = 1.0 - r2_base
    return float(np.sqrt(max(delta, 0.0) / denom)) if denom > 1e-9 else 0.0


def incremental(BASE, EXTRA, y, K, seed):
    r2_base = stats.ridge_oof_r2(BASE, y, seed=seed)
    r2_test = stats.ridge_oof_r2(np.hstack([BASE, EXTRA]), y, seed=seed)
    delta = r2_test - r2_base
    rng = stats.rng(seed)
    null = np.array([stats.ridge_oof_r2(np.hstack([BASE, EXTRA[rng.permutation(len(y))]]),
                                        y, seed=seed) - r2_base for _ in range(K)])
    gate = stats.percentile_gate(delta, null, 95)
    return {"r2_base": r2_base, "r2_test": r2_test, "delta": delta,
            "partial_r": _partial_r(delta, r2_base), "null_p95": gate["threshold"],
            "p": stats.permutation_pvalue(delta, null)}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else (Path(__file__).resolve().parent / "BRANCH_D_RESULT.md")
    t0 = time.perf_counter()

    cmu, pp, war = DATA_DIR / "cmudict.dict", DATA_DIR / "ipa_all.csv", DATA_DIR / "warriner.csv"
    if not (cmu.exists() and pp.exists() and war.exists()):
        rb = ReportBuilder("BRANCH_D_RESULT — phoneme-identity semantic upper bound",
                           "Reachable-data semantic upper-bound test. NOT Symbol-U validation.")
        rb.decision("DATA_BLOCKED")
        rb.para(f"Required inputs not found in {DATA_DIR} (cmudict.dict, ipa_all.csv, "
                f"warriner.csv). Fetch from reachable GitHub mirrors and re-run.")
        rb.write(out); print("DATA_BLOCKED"); return 0

    ds = build_dataset(cmu, pp, war)
    n = ds["n"]
    feasible = n >= N_EFF_FLOOR
    res = {}
    if feasible:
        for j, name in enumerate(ENDPOINTS):
            res[name] = incremental(ds["PHON"], ds["E_max"], ds["Y"][:, j], K_PERM, seed=13)
        # random-E control on valence
        rng = stats.rng(99)
        randE = rng.integers(0, 3, size=ds["E_max"].shape).astype(float)
        rand_ctrl = incremental(ds["PHON"], randE, ds["Y"][:, 0], K_PERM, seed=13)

    # decision (valence primary)
    if not feasible:
        decision = "UPPER_BOUND_INCONCLUSIVE"
    else:
        v = res["valence"]
        significant = v["delta"] > v["null_p95"] and v["p"] < ALPHA
        if significant and v["partial_r"] >= MIN_PARTIAL_R:
            decision = "UPPER_BOUND_POSITIVE"
        elif v["partial_r"] < 0.05 or not significant:
            decision = "UPPER_BOUND_NULL"
        else:
            decision = "UPPER_BOUND_POSITIVE"   # significant + marginal (0.05–0.10); flagged

    rb = ReportBuilder(
        "BRANCH_D_RESULT — phoneme-identity semantic upper bound (measured)",
        "Reachable-data semantic measurement; UPPER-BOUND / necessary-condition test on the "
        "LINEAR/additive model class. **Not Symbol-U validation, not A′ PASS/FAIL/⊥.** It can "
        "only falsify or bound a phoneme-level essence effect. A′ remains halted; Stage A "
        "untouched; no L2 F; no decoders. Y = Warriner VAD (academic norms; not redistributed).")
    rb.decision(decision)
    rb.section("Datasets & join")
    rb.bullets([
        "E (phoneme identity): CMUdict v0.7b ARPABET, stress-stripped (BSD-2).",
        "Phonology: PanPhon articulatory features via frozen ARPABET→IPA map (MIT).",
        "Y: Warriner et al. (2013) VAD means (academic norms; local only, not committed).",
        f"joined N = {n} words (Warriner {ds['n_warriner']} ∩ CMUdict {ds['n_cmudict']}); "
        f"N_eff floor {N_EFF_FLOOR} → {'met' if feasible else 'NOT met'}.",
        f"uncovered phonemes: {ds['missing_phonemes'] or 'none'}.",
        f"features: PHON = {ds['PHON'].shape[1]} (mean articulatory + n_phonemes + n_syllables); "
        f"E_max = {ds['E_max'].shape[1]} phoneme-identity counts. NUIS=length included in PHON; "
        f"frequency omitted (not in Warriner/CMUdict).",
    ])
    if feasible:
        rb.section("Incremental predictive test  (Y ~ PHON  vs  Y ~ PHON + E_max)")
        rows = []
        for name in ENDPOINTS:
            r = res[name]
            rows.append((name, f"{r['r2_base']:.4f}", f"{r['r2_test']:.4f}",
                         f"{r['delta']:.4f}", f"{r['partial_r']:.3f}",
                         f"{r['null_p95']:.4f}", f"{r['p']:.3g}"))
        rb.table(["endpoint", "R²(PHON)", "R²(PHON+E_max)", "ΔR²", "partial r",
                  "perm-null p95", "perm p"], rows)
        rb.section("Controls")
        rb.bullets([
            f"random-E control (valence): ΔR² = {rand_ctrl['delta']:.4f}, "
            f"partial r = {rand_ctrl['partial_r']:.3f}, p = {rand_ctrl['p']:.3g} "
            f"(should be ≈ 0 / non-significant).",
            "relabel/column-permutation of phoneme identities: a linear-probe column permutation "
            "→ R² invariant by construction (degenerate; reported transparently, as in D₀′.1).",
            "primary null = row-permutation of E_max vs (Y, PHON), K=%d." % K_PERM,
        ])
    rb.section("Interpretation")
    if decision == "UPPER_BOUND_NULL":
        rb.para("**No deterministic phoneme-level essence table can improve prediction of this Y "
                "beyond the chosen phonology representation, under this dataset and (linear) model "
                "class.** The necessary condition for a phoneme-level semantic essence fails here.")
    elif decision == "UPPER_BOUND_POSITIVE":
        v = res["valence"]
        marg = "" if v["partial_r"] >= MIN_PARTIAL_R else " (MARGINAL: 0.05 ≤ partial r < 0.10)"
        rb.para(f"**A necessary condition survives{marg}: phoneme identity contains residual "
                f"information about Y (valence partial r = {v['partial_r']:.3f}) beyond articulatory "
                f"phonology.** This does NOT validate Symbol-U; it only means a specific E table is "
                f"still worth testing, with this value as its upper bound. Caveat: the bound also "
                f"absorbs morphological/etymological systematicity, so it OVER-estimates any purely "
                f"sound-symbolic essence effect (a conservative upper bound).")
    else:
        rb.para("Underpowered / not feasible: joined sample below the N_eff floor.")
    rb.para("Model-class caveat: linear ridge on additively-aggregated counts; the DPI upper bound "
            "holds for linear/additive essence aggregations (the pre-registered A1.4 branch). "
            "English lexicon testbed; not a Sanskrit-privilege claim.")

    body = rb.build()
    meta = _repro.collect_metadata(
        config={"K_perm": K_PERM, "min_partial_r": MIN_PARTIAL_R, "n_eff_floor": N_EFF_FLOOR,
                "endpoints": ENDPOINTS, "data_dir": str(DATA_DIR)},
        seed=13, runtime_s=time.perf_counter() - t0,
        outputs={"report_body": _repro.sha256_text(body)})
    rb.repro_block(meta).footer()
    md = rb.write(out)
    print(md); print(f"[written] {out}  decision={decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
