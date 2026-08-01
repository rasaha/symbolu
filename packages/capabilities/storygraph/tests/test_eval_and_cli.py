"""The evaluation harness is honest, and the CLI paths run."""

from __future__ import annotations

from ugence_storygraph import cli
from ugence_storygraph.evaluation import harness


def test_harness_marks_enterprise_metrics_not_run():
    m = harness.evaluate()["metrics"]
    # metrics that require enterprise/labeled data must NOT be fabricated
    assert m["escalation_lead_time_before_completion"]["value"] == "REQUIRES ENTERPRISE DATA"
    assert m["alerts_per_tenant_day"]["value"] == "REQUIRES ENTERPRISE DATA"
    assert m["peak_state_per_tenant"]["value"] == "REQUIRES ENTERPRISE DATA"
    assert m["runtime_per_event"]["value"] == "NOT RUN"
    assert m["entity_linkage_error_rate"]["value"] == "NOT RUN"


def test_harness_synthetic_metrics_are_labeled():
    rep = harness.evaluate()
    assert rep["evidence_label"] == "Measured — synthetic corpus"
    assert "NOT enterprise performance" in rep["disclaimer"]
    m = rep["metrics"]
    # synthetic metrics are measured and labeled, never presented as enterprise
    assert m["true_positive_rate_encoded"]["label"] == "Measured — synthetic corpus"
    assert m["unknown_threat_detection"]["value"] in (0.0, "NOT RUN")
    assert m["determinism_across_replay"]["value"] == "PASS"


def test_harness_breaks_down_by_family_and_split():
    rep = harness.evaluate()
    assert len(rep["breakdown_by_family"]) == 25
    assert set(rep["breakdown_by_split"]) == {"dev", "calibration", "final"}


def test_cli_demo_exfiltration_exit_code_escalates(capsys):
    assert cli.main(["demo", "exfiltration"]) == 1


def test_cli_demo_benign_exit_code_clean(capsys):
    assert cli.main(["demo", "benign"]) == 0


def test_cli_ontologies_specs_manifest_freeze(capsys):
    assert cli.main(["ontologies"]) == 0
    assert cli.main(["specs"]) == 0
    assert cli.main(["manifest"]) == 0
    assert cli.main(["freeze", "--commit", "abc123"]) == 0
    assert cli.main(["eval"]) == 0
