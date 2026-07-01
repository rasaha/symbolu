"""D0'.1 — run the adversarial structural-specificity test; write a measured report.

STRUCTURAL ONLY. No semantics, no Stage A modification, no new theory. Builds
null operator families through the frozen feature_operators constructor and
compares the EXACT D0' statistics against Stage A.

    python3 experiments/d0_prime/run_specificity.py [out.md]
"""
from __future__ import annotations

import pathlib
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import repro as _repro          # noqa: E402
from common.report import ReportBuilder      # noqa: E402
from specificity import (NULLS, STAT_KEYS, compare, load_frozen, sample_null,
                         stat_vector)         # noqa: E402

K = 200                       # null samples per ensemble
ALPHA = 0.05
ALPHA_BONF = ALPHA / len(STAT_KEYS)


def _fmt(x):
    return f"{x:.3e}" if (x != 0 and abs(x) < 1e-3) else f"{x:.4f}"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else (Path(__file__).resolve().parent / "D0_PRIME_1_SPECIFICITY_RESULT.md")
    t0 = time.perf_counter()

    units, F, feature_operators, s0 = load_frozen()
    stage = stat_vector(feature_operators(F), s0)

    per_null = {}
    for i, name in enumerate(NULLS):
        print(f"[{i+1}/{len(NULLS)}] sampling null {name} (K={K}) ...")
        arrays = sample_null(name, F, feature_operators, s0, K, seed=70000 + i)
        per_null[name] = compare(stage, arrays)

    # per-null distinguishability (Bonferroni across non-degenerate stats)
    verdicts = {}
    for name, comp in per_null.items():
        sig = [k for k in STAT_KEYS
               if not comp[k]["spread_zero"] and comp[k]["p_two_sided"] < ALPHA_BONF]
        degenerate = [k for k in STAT_KEYS if comp[k]["spread_zero"]]
        verdicts[name] = {"distinguishable": len(sig) > 0,
                          "outlier_stats": sig, "degenerate_stats": degenerate}

    indistinguishable = [n for n, v in verdicts.items() if not v["distinguishable"]]
    if not indistinguishable:
        decision = "SPECIFIC"
    elif len(indistinguishable) == len(NULLS):
        decision = "NOT SPECIFIC"
    else:
        # distinguishable from some, not all
        decision = ("NOT SPECIFIC" if indistinguishable else "SPECIFIC")
        decision = "PARTIALLY SPECIFIC"

    rb = ReportBuilder(
        "D0_PRIME_1_SPECIFICITY_RESULT — adversarial structural-specificity test (measured)",
        "STRUCTURAL ONLY — adversarial falsification; burden on Symbol-U. No semantics, no Stage "
        "A modification, no new theory. Operators built read-only via the frozen feature_operators "
        "constructor; only the feature matrix is replaced by null ensembles. NOT semantic "
        "validation, NOT A′, NOT PASS/FAIL/⊥ for Symbol-U semantics. Stage A frozen.")
    rb.decision(decision)
    rb.para(f"n_units={len(units)}, d=4, null samples K={K} per ensemble. "
            f"Distinguishable ⇔ ≥1 non-degenerate statistic with two-sided empirical "
            f"p < {ALPHA_BONF:.4f} (Bonferroni over {len(STAT_KEYS)} D0′ statistics). "
            f"Nulls: A permute-rows, B independent-global, C preserve-norms, "
            f"D preserve-cosines, E maxent-first-order.")

    rb.section("Stage A reference (exact D0′ statistics)")
    rb.table(["statistic", "value"], [(k, _fmt(stage[k])) for k in STAT_KEYS])

    for name in NULLS:
        comp = per_null[name]; v = verdicts[name]
        rb.section(f"Null {name} — "
                   f"{'DISTINGUISHABLE (outlier)' if v['distinguishable'] else 'INDISTINGUISHABLE'}")
        rows = []
        for k in STAT_KEYS:
            c = comp[k]
            note = "degenerate(const)" if c["spread_zero"] else (
                "OUTLIER" if c["p_two_sided"] < ALPHA_BONF else "")
            rows.append((k, _fmt(c["stage"]), f"{_fmt(c['null_mean'])}±{_fmt(c['null_std'])}",
                         f"{c['percentile']:.1f}", _fmt(c["p_two_sided"]), note))
        rb.table(["statistic", "stage A", "null mean±std", "pctl", "p(2-sided)", "flag"], rows)
        if v["outlier_stats"]:
            rb.bullets([f"outlier statistics: {', '.join(v['outlier_stats'])}"])
        if v["degenerate_stats"]:
            rb.bullets([f"degenerate (null has zero spread — set-invariant under this null, "
                        f"cannot discriminate): {', '.join(v['degenerate_stats'])}"])

    rb.section("Decision")
    if decision == "SPECIFIC":
        rb.para("Stage A is a statistically significant outlier against EVERY null ensemble.")
    elif decision == "NOT SPECIFIC":
        rb.para("Stage A is statistically INDISTINGUISHABLE from one or more null ensembles "
                f"({', '.join(indistinguishable)}). **This is a structural falsification of the "
                "specificity of the current feature construction**: comparable non-commutative "
                "operator algebra arises under alternative feature assignments, so the structure "
                "is not specific to the Symbol-U feature ontology. (Structural only — not a "
                "statement about semantics, which remain untested.)")
    else:
        distinguishable = [n for n in NULLS if n not in indistinguishable]
        unique = sorted({s for n in distinguishable for s in verdicts[n]["outlier_stats"]})
        rb.para(f"Stage A is distinguishable from {distinguishable} but INDISTINGUISHABLE from "
                f"{indistinguishable}. Structural properties on which Stage A remains an outlier "
                f"(against at least one null): {', '.join(unique) or '(none)'}.")
    rb.para("Interpretation guard: this concerns the algebraic structure of the frozen, "
            "feature-derived operators only; it is not evidence about meaning and does not "
            "validate the operators as the 'true' ones. A NOT-SPECIFIC result falsifies the "
            "structural specificity of the feature construction, nothing more.")

    body = rb.build()
    meta = _repro.collect_metadata(config={"K": K, "alpha_bonferroni": ALPHA_BONF,
                                           "nulls": list(NULLS)}, seed=70000,
                                   runtime_s=time.perf_counter() - t0,
                                   outputs={"report_body": _repro.sha256_text(body)})
    rb.repro_block(meta).footer()
    md = rb.write(out)
    print(md)
    print(f"[written] {out}  decision={decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
