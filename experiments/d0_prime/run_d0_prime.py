"""Run D0' on the frozen Stage A operators + synthetic controls; write a report.

STRUCTURAL / gauge / operator-algebra ONLY. Not semantic validation, not A',
not PASS/FAIL/bottom for Symbol-U semantics. Reproduces the frozen operators
read-only (never modifies Stage A).

    python3 experiments/d0_prime/run_d0_prime.py [out.md]
"""
from __future__ import annotations

import pathlib
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import config as _cfgmod, report as _report, repro as _repro  # noqa: E402
_CFG = _cfgmod.load_config(_cfgmod.D0Config, pathlib.Path(__file__).parent / "config.json")

from operator_algebra import (
    analyze_family, commuting_diagonal_family, generated_algebra_dimension,
    identity_family, load_stage_a_operators, random_orthogonal_family,
    TOL_ABELIAN, TOL_COMMUTE,
)


def _fmt(x: float) -> str:
    return f"{x:.3e}" if (x != 0 and abs(x) < 1e-3) else f"{x:.4f}"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else (Path(__file__).resolve().parent / "D0_PRIME_RESULT.md")

    t0 = time.perf_counter()
    units, ops, s0 = load_stage_a_operators()
    n, d = len(ops), ops[0].shape[0]

    stage = analyze_family("Stage A (frozen, feature-derived)", ops, s0=s0)
    ident = analyze_family("control: identity", identity_family(n, d))
    cdiag = analyze_family("control: commuting-diagonal", commuting_diagonal_family(n, d, seed=1))
    rorth = analyze_family("control: random-orthogonal", random_orthogonal_family(n, d, seed=2))
    fams = [stage, ident, cdiag, rorth]

    L = []
    L.append("# D0_PRIME_RESULT — Gauge-Invariant Operator-Algebra Analysis (measured)")
    L.append("")
    L.append("> **STRUCTURAL / gauge / operator-algebra ONLY.** Generated from actual execution "
             "of `experiments/d0_prime/run_d0_prime.py` on the frozen, feature-derived Stage A "
             "operators (reproduced read-only; Stage A unmodified). "
             "**NOT semantic validation · NOT A′ · NOT PASS/FAIL/⊥ for Symbol-U semantics.** "
             "A nontrivial result means only *nontrivial frozen operator algebra*; an abelian "
             "result would be a structural falsification of *this operator instance* only. "
             "No semantic `Y`, no L2 `F`, no decoder, no inference about meaning.")
    L.append("")
    L.append(f"Operator family: **n = {n}** units `{units}`, dimension **d = {d}** (SO(d)). "
             f"Pre-registered thresholds: TOL_COMMUTE={TOL_COMMUTE:g}, TOL_ABELIAN={TOL_ABELIAN:g}.")
    L.append("")
    L.append("## 1. Inventory (Stage A)")
    inv = stage.inventory
    L.append(f"- operators: {inv['n_operators']}, shapes: {inv['shapes']}")
    L.append(f"- Frobenius norm: [{_fmt(inv['frobenius_norm']['min'])}, {_fmt(inv['frobenius_norm']['max'])}]  "
             f"(√d = {d**0.5:.4f} expected for orthogonal)")
    L.append(f"- rank: [{inv['rank']['min']}, {inv['rank']['max']}]  · "
             f"condition number: [{_fmt(inv['condition_number']['min'])}, {_fmt(inv['condition_number']['max'])}]")
    L.append(f"- determinant: [{_fmt(inv['determinant']['min'])}, {_fmt(inv['determinant']['max'])}]  · "
             f"trace: [{_fmt(inv['trace']['min'])}, {_fmt(inv['trace']['max'])}]")
    L.append("")

    L.append("## 2. Cross-family comparison (Stage A vs controls)")
    L.append("")
    hdr = ("| family | max ‖[Mₐ,M_b]‖ (norm.) | near-commuting pairs | abelian off-diag defect (max) "
           "| algebra dim (≤ d²=%d) | trace order-sens. frac | order-separation frac | reach. rank (≤d) | verdict |" % (d*d))
    L.append(hdr)
    L.append("|" + "---|" * 9)
    for f in fams:
        c = f.noncommutativity; a = f.abelianity; alg = f.algebra
        tr = f.trace_order; rc = f.reachability; dec = f.decision
        verdict = "ABELIAN" if dec["is_effectively_abelian"] else "nontrivial"
        L.append("| {name} | {mc} | {npairs}/{tot} | {defect} | {adim} | {tof} | {osf} | {rr} | {v} |".format(
            name=f.name,
            mc=_fmt(c["normalized_commutator_norm"]["max"]),
            npairs=c["n_near_commuting_pairs"], tot=c["n_pairs"],
            defect=_fmt(a["offdiag_defect"]["max"]),
            adim=alg["final_dim"],
            tof=_fmt(tr["frac_order_sensitive"]),
            osf=_fmt(rc["order_separation_frac"]),
            rr=f"{rc['reachability_rank']}/{rc['d_ceiling']}",
            v=verdict))
    L.append("")

    L.append("## 3. Stage A detail")
    c = stage.noncommutativity
    L.append(f"- normalized commutator norm: min={_fmt(c['normalized_commutator_norm']['min'])}, "
             f"median={_fmt(c['normalized_commutator_norm']['median'])}, "
             f"max={_fmt(c['normalized_commutator_norm']['max'])}")
    L.append(f"- commutator rank range: [{c['commutator_rank']['min']}, {c['commutator_rank']['max']}] "
             f"(0 ⟺ exactly commuting)")
    L.append(f"- near-commuting pairs (< TOL_COMMUTE): {c['n_near_commuting_pairs']} of {c['n_pairs']}")
    if c["near_commuting_pairs"]:
        pairs = ", ".join(f"({units[i]},{units[j]})" for i, j, _ in c["near_commuting_pairs"])
        L.append(f"  - {pairs}")
    L.append(f"- generated-algebra dimension by word length: {stage.algebra['dim_by_length']} "
             f"(ceiling d²={stage.algebra['d2_ceiling']})")
    L.append(f"- abelian off-diagonal defect: mean={_fmt(stage.abelianity['offdiag_defect']['mean'])}, "
             f"max={_fmt(stage.abelianity['offdiag_defect']['max'])}")
    L.append(f"- trace-word order sensitivity: frac={_fmt(stage.trace_order['frac_order_sensitive'])}, "
             f"max |Δtr|={_fmt(stage.trace_order['max_abs_trace_diff'])} "
             f"(tr is conjugation-invariant ⇒ fully gauge-invariant witness)")
    L.append(f"- reachability (scalar Hankel) rank: {stage.reachability['reachability_rank']}/"
             f"{stage.reachability['d_ceiling']}; order-separation frac="
             f"{_fmt(stage.reachability['order_separation_frac'])}")
    L.append("")
    L.append("### Generated-algebra dimension vs abelian baseline")
    L.append(f"- Stage A: **{stage.algebra['final_dim']}** / {d*d}")
    L.append(f"- abelian baseline (commuting-diagonal control): {cdiag.algebra['final_dim']} / {d*d}")
    L.append(f"- full non-abelian reference (random-orthogonal control): {rorth.algebra['final_dim']} / {d*d}")
    sep = stage.algebra['final_dim'] - cdiag.algebra['final_dim']
    L.append(f"- **algebra-dimension separation above the abelian baseline: {sep}** "
             f"(> 0 ⇒ order/non-commutativity adds realizable structure the abelian model cannot)")
    L.append("")

    L.append("## 4. Structural decision (pre-registered, structural only)")
    L.append(f"> **{stage.decision['verdict']}**")
    L.append("")
    L.append("Interpretation guard: this verdict concerns ONLY the algebraic structure of the "
             "frozen, feature-derived Stage A operator instance. It is **not** evidence about "
             "meaning, dictionary prediction, or Sanskrit privilege; it does **not** validate the "
             "operators as the 'true' ones (they are a feature-derived benchmark proxy); and it is "
             "**not** an A′/semantic PASS/FAIL/⊥. A negative (abelian) verdict would structurally "
             "falsify this instance; the measured verdict above is reported with no further "
             "semantic inference.")
    L.append("")
    L.append("## 5. Sanity of controls (calibration)")
    for f in (ident, cdiag, rorth):
        L.append(f"- {f.name}: verdict = "
                 f"{'ABELIAN' if f.decision['is_effectively_abelian'] else 'nontrivial'}, "
                 f"algebra dim = {f.algebra['final_dim']}, "
                 f"order-sep = {_fmt(f.reachability['order_separation_frac'])}")
    L.append("")
    L.append("> structure, not validated meaning.")
    md = "\n".join(L) + "\n"
    md += "\n" + _report.metadata_markdown(_repro.collect_metadata(
        config=asdict(_CFG), seed=_CFG.generic_seed, runtime_s=time.perf_counter() - t0,
        outputs={"report_body": _repro.sha256_text(md)}))
    out.write_text(md)
    print(md)
    print(f"[written] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
