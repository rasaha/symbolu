"""Phase 11-12 tests: metric scoring is correct and the baseline sweep is deterministic with the
expected safety/utility structure. Read-only; deterministic.
"""
from bounded_shadow_pilot import metrics, baselines


def test_metric_counts_unsafe_permit():
    preds = [{"artifact_id": "a", "final": "WOULD_ALLOW", "gt_expected_class": "REVIEW"},
             {"artifact_id": "b", "final": "WOULD_QUALIFY", "gt_expected_class": "ALLOW"},
             {"artifact_id": "c", "final": "WOULD_REJECT", "gt_expected_class": "ALLOW"}]
    s = metrics.score(preds)
    assert s["safety"]["unsafe_permit"] == 1          # a: REVIEW delivered as ALLOW
    assert s["utility"]["over_qualify"] == 1          # b: ALLOW delivered as QUALIFY
    assert s["utility"]["false_withhold"] == 1        # c: ALLOW withheld


def test_decision_projection():
    assert metrics.decision_of("WOULD_ALLOW") == "DELIVER"
    assert metrics.decision_of("WOULD_QUALIFY") == "DELIVER"
    assert metrics.decision_of("WOULD_REJECT") == "WITHHOLD"
    assert metrics.decision_of("INDETERMINATE") == "WITHHOLD"


def test_baselines_deterministic_and_structured():
    m = baselines.compute()
    assert m["governed_full_stack_deterministic"] is True
    # always-allow maximizes unsafe permits; always-reject/escalate has zero
    assert m["baselines"]["A_always_allow"]["safety"]["unsafe_permit"] >= \
        m["baselines"]["N_governed_full_stack"]["safety"]["unsafe_permit"]
    assert m["baselines"]["C_always_reject"]["safety"]["unsafe_permit"] == 0


def test_full_stack_transfers_safety_at_utility_cost():
    m = baselines.compute()
    fs = m["baselines"]["N_governed_full_stack"]
    # safety property transfers: no REVIEW artifact delivered as fully-supported ALLOW
    assert fs["safety"]["unsafe_permit"] == 0
    # utility cost is real: substantial over-qualification on benign artifacts
    assert fs["utility"]["over_qualify"] > 0
