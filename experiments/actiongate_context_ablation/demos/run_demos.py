"""Executable demonstrations (task "Required demonstrations", 10 items).

Run:  python -m demos.run_demos   (from the experiment root)
Each demo is deterministic and prints what it shows. Nothing here emits a
product/scientific verdict from synthetic data — demo 10 shows the lock.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from actiongate_context_ablation import (  # noqa: E402
    adapter, ablation, economics, effects, extractor, metrics, origin, runner, verdict,
)
from actiongate_context_ablation.corpus import tier1_fixtures as T1  # noqa: E402
from actiongate_context_ablation.corpus import tier3_heldout as T3  # noqa: E402

SP = adapter.default_signed_policy()


def _hdr(n, title):
    print(f"\n{'='*72}\nDEMO {n}: {title}\n{'='*72}")


def demo1_flip_deny_allow():
    _hdr(1, "One span flips DENY <-> ALLOW")
    ctx = T1.widened_scope()
    run = ablation.run_ablations(ctx, SP)
    rec = next(r for r in run.records if r.ablation_id == "single:scope")
    print(f"baseline (admin port open to world): {run.baseline_outcome}")
    print(f"remove 'scope' span -> {rec.oracle_effect.outcome_after} "
          f"[{sorted(rec.oracle_effect.labels)}]")


def demo2_assurance_only():
    _hdr(2, "One span changes an assurance requirement but NOT the final outcome")
    # extra (unneeded) credential permission: removing it changes credential_scope
    # (assurance-input field) while the outcome is unchanged.
    base = dict(tool="filesystem", verb="read", target=("file://secrets/db",),
                args={"export": True, "sink_approved": True},
                approvals=({"approver_policy": "single", "approvers": "single"},))
    with_extra = adapter.RequestSpec(permissions=("fs:read", "audit:tag"), **base)
    without = adapter.RequestSpec(permissions=("fs:read",), **base)
    b, a = adapter.evaluate(with_extra, SP), adapter.evaluate(without, SP)

    class _C:
        units = ()
    eff = effects.classify(b, a, ctx=_C(), removed_ids=set())
    print(f"outcome with extra perm : {b['decision']['outcome']}")
    print(f"outcome without         : {a['decision']['outcome']}  (unchanged)")
    print(f"changed envelope fields : {eff.changed_env_fields}")
    print(f"labels                  : {sorted(eff.labels)}  "
          f"(ASSURANCE, not DECISION)")


def demo3_duplicate_survives_single():
    _hdr(3, "Duplicate critical fact survives single ablation, fails redundancy ablation")
    run = ablation.run_ablations(T1.duplicated_critical_fact(), SP, dev=False)
    for uid in ("sink1", "sink2"):
        s = next(r for r in run.records if r.ablation_id == f"single:{uid}")
        print(f"single remove {uid}: {sorted(s.oracle_effect.labels)}")
    red = next(r for r in run.records if r.mode == ablation.REDUNDANCY)
    print(f"redundancy-set remove {red.removed_ids}: {sorted(red.oracle_effect.labels)} "
          f"-> flagged redundant: {sorted(run.redundant_units)}")


def demo4_rule_exception():
    _hdr(4, "Rule + exception pair interaction")
    run = ablation.run_ablations(T1.rule_plus_distant_exception(), SP)
    for uid in ("rule", "appr"):
        s = next(r for r in run.records if r.ablation_id == f"single:{uid}")
        print(f"single remove {uid:5}: {sorted(s.oracle_effect.labels)} "
              f"({s.oracle_effect.outcome_before}->{s.oracle_effect.outcome_after})")
    print("=> the approval (exception) only matters because the widening rule is present")


def demo5_extractor_instability():
    _hdr(5, "Extractor instability vs the structured oracle (paraphrase)")
    ctx = T3.credential_pull()
    ids = [u.id for u in ctx.units]
    o = extractor.extract_and_eval(ctx, ids, SP, mode=extractor.ORACLE)
    r = extractor.extract_and_eval(ctx, ids, SP, mode=extractor.REALISTIC)
    print(f"oracle    baseline outcome : {o['decision']['outcome']}")
    print(f"realistic baseline outcome : {r['decision']['outcome']}  "
          f"(diverges: extractor missed paraphrased spans)")
    print("paraphrases: 'cleared by infosec' (approved sink), 'gave the go-ahead' (approval)")


def demo6_low_fraction_high_protected():
    _hdr(6, "Low true-critical fraction but higher detector-protected fraction")
    cm = metrics.context_metrics(ablation.run_ablations(T1.coherent_one_commitment(), SP))
    print(f"true critical fraction  : {cm.f_critical_union:.1%}")
    print(f"protected fraction      : {cm.f_protected:.1%}  (detector over-marks)")
    print(f"oracle ceiling          : {cm.oracle_ceiling:.1%}")
    print(f"deployable ceiling      : {cm.deployable_ceiling:.1%}  "
          f"(precision {cm.precision_p0:.1%})")


def demo7_intrinsically_dense():
    _hdr(7, "Intrinsically dense context (little is removable)")
    run = ablation.run_ablations(T1.approval_and_backup(), SP)
    cm = metrics.context_metrics(run)
    agg = metrics.aggregate([run])
    econ = economics.model(agg)
    v = verdict.decide(agg, econ, [origin.FIELD_REAL])   # illustrate the branch
    print(f"true critical fraction : {cm.f_critical_union:.1%}  "
          f"(oracle ceiling {cm.oracle_ceiling:.1%})")
    print(f"if this were real data, verdict branch -> {v.verdict}")


def demo8_caching_erases_savings():
    _hdr(8, "Prompt caching + overhead erasing apparent savings")
    res = runner.run_study()
    cheap = economics.model(res.agg, economics.EconomicAssumptions(
        cacheable_fraction=0.0, overhead_ratio=0.0))
    real = economics.model(res.agg, economics.EconomicAssumptions(
        cacheable_fraction=0.8, overhead_ratio=0.15))
    print(f"naive savings (no cache, no overhead) : {cheap.cache_adjusted_savings_ratio:.1%}")
    print(f"cache+overhead-adjusted savings       : {real.cache_adjusted_savings_ratio:.1%}")
    print(f"clears {real.assumptions.min_net_savings_ratio:.0%} threshold: {real.clears_threshold}")


def demo9_favorable_path():
    _hdr(9, "Favorable opportunity path (decision logic, illustrative)")
    # A hand-set FAVORABLE aggregate + REAL origins -> SUPPORTED. This exercises the
    # decision branch; it is NOT a measurement.
    fav = metrics.AggregateMetrics(
        n_contexts=50, total_units=800, total_ablations=1500, total_tokens=100000,
        f_decision=0.06, f_envelope=0.03, f_assurance=0.02, f_critical_union=0.10,
        f_protected=0.14, recall_p0=1.0, precision_p0=0.71,
        oracle_ceiling=0.90, deployable_ceiling=0.86,
        interaction_miss_rate=0.01, extractor_instability_rate=0.03, per_context=[])
    econ = economics.model(fav, economics.EconomicAssumptions(cacheable_fraction=0.4))
    v = verdict.decide(fav, econ, [origin.FIELD_REAL] * 50)
    print(f"favorable metrics + real provenance -> {v.verdict} (scientific={v.scientific})")
    print(f"  recall={fav.recall_p0:.0%} ceiling={fav.deployable_ceiling:.0%} "
          f"instab={fav.extractor_instability_rate:.0%} "
          f"net_savings={econ.cache_adjusted_savings_ratio:.0%}")


def demo10_verdict_lock():
    _hdr(10, "No-scientific-verdict lock on synthetic corpus")
    res = runner.run_study()
    v = res.verdict
    print(f"emitted verdict            : {v.verdict}")
    print(f"scientific                 : {v.scientific}")
    print(f"pipeline_path_verified     : {v.pipeline_path_verified}")
    print(f"indicative-only (locked)   : {v.indicative_scientific_verdict}")
    print("=> synthetic data can verify the pipeline but NEVER decide the product.")


DEMOS = [demo1_flip_deny_allow, demo2_assurance_only, demo3_duplicate_survives_single,
         demo4_rule_exception, demo5_extractor_instability, demo6_low_fraction_high_protected,
         demo7_intrinsically_dense, demo8_caching_erases_savings, demo9_favorable_path,
         demo10_verdict_lock]


def main():
    for d in DEMOS:
        d()
    print()


if __name__ == "__main__":
    main()
