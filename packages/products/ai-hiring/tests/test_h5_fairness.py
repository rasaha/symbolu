"""H5 — fairness analysis (read-only), counterfactual leakage, protected-attr exclusion."""
from __future__ import annotations

from ugence_ai_hiring.validation import analyze, build_validation_env, run_pilot
from ugence_ai_hiring.validation.composition import build_validation_env as _bve
from ugence_ai_hiring.validation.fairness import counterfactual_invariance
from ugence_ai_hiring.validation.lifecycle import CaseSpec, run_lifecycle


def test_fairness_report_is_descriptive_and_warns_on_small_samples():
    fr = analyze(run_pilot())
    assert fr.groups and any(g.small_sample for g in fr.groups)
    assert fr.warnings
    # never a bare fair/unfair conclusion
    assert "unbiased" not in fr.interpretation.lower() and "compliant" not in fr.interpretation.lower()


def test_no_material_disparity_wording_when_balanced():
    # a balanced synthetic cohort (>= MIN_GROUP_SIZE per group, identical behavior)
    from ugence_ai_hiring.governance.outcomes import HiringDecisionIntent
    runs = []
    env = build_validation_env()
    for i in range(24):
        g = "group_a" if i % 2 == 0 else "group_b"
        runs.append(run_lifecycle(env, CaseSpec(case_id=f"bal{i}", group_label=g)))
    fr = analyze(runs)
    assert "No material disparity" in fr.interpretation


def test_counterfactual_invariance_group_label_does_not_change_inputs():
    base = CaseSpec(case_id="cf")
    assert counterfactual_invariance(_bve, base, ("group_a", "group_b", "group_c"))


def test_protected_attributes_never_enter_pipeline():
    # group label / protected attributes are analysis-only; the governed input
    # (evidence package fingerprint) is identical regardless of them.
    env1, env2 = build_validation_env(), build_validation_env()
    r1 = run_lifecycle(env1, CaseSpec(case_id="pa", group_label="A", protected_attributes={"x": "1"}))
    r2 = run_lifecycle(env2, CaseSpec(case_id="pa", group_label="B", protected_attributes={"x": "9"}))
    assert r1.package_fingerprint == r2.package_fingerprint
