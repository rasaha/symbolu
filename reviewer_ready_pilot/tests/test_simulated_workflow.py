"""M12 tests - simulated workflow test (Phase 18). SIMULATED_WORKFLOW_ONLY."""
from reviewer_ready_pilot import simulated_workflow as sw
from reviewer_ready_pilot import dataset, metrics as m


def test_runs_end_to_end_and_is_labeled_simulation():
    rep = sw.run(dataset.load_final(), limit=30)
    assert rep["mode"] == "SIMULATED_WORKFLOW_ONLY"
    assert rep["is_human_validation"] is False
    assert rep["records_produced"] > 0


def test_every_record_is_mock():
    rep = sw.run(dataset.load_final(), limit=30)
    assert rep["all_records_mock"] is True


def test_metrics_on_real_records_is_not_enough_human_evidence():
    """The crucial honesty check: a simulated run can NEVER yield a human-agreement number."""
    rep = sw.run(dataset.load_final(), limit=30)
    assert rep["metrics_on_real_records"]["status"] == m.STATUS_NO_HUMAN
    assert rep["metrics_on_real_records"]["reviewer_system_agreement"] == m.NOT_EVALUATED
    assert rep["metrics_on_real_records"]["human_validation"] == m.NOT_EVALUATED


def test_audit_chain_and_workflow_ok():
    rep = sw.run(dataset.load_final(), limit=30)
    assert rep["audit"]["chain_ok"] is True
    assert rep["audit"]["workflow_ok"] is True


def test_deterministic():
    a = sw.run(dataset.load_final(), limit=20)
    b = sw.run(dataset.load_final(), limit=20)
    assert a["records_produced"] == b["records_produced"]
    assert a["audit"]["workflow_ok"] == b["audit"]["workflow_ok"]


def test_no_enforcement_anywhere():
    rep = sw.run(dataset.load_final(), limit=20)
    assert rep["stop"]["should_stop"] is False or "enforcement_attempt" not in rep["stop"]["immediate_fired"]
