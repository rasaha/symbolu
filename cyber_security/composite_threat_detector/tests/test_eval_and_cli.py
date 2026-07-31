"""The evaluation harness is honest, and the CLI paths run."""

from __future__ import annotations

from composite_threat_detector import cli
from evaluation import harness


def test_harness_marks_population_rates_not_run():
    rep = harness.evaluate()
    m = rep["metrics"]
    for k in ("true_positive_rate", "false_escalation_rate", "miss_rate",
              "cross_session_detection_rate", "multi_actor_detection_rate",
              "escalation_lead_time_before_completion", "runtime_per_event"):
        assert str(m[k]).startswith("NOT RUN")


def test_harness_measures_determinism_and_explanation():
    m = harness.evaluate()["metrics"]
    assert m["determinism_repeated_runs"] == "PASS"
    assert 0.0 <= m["explanation_completeness_illustrative"] <= 1.0


def test_cli_demo_exfiltration_exit_code_escalates(capsys):
    rc = cli.main(["demo", "exfiltration"])
    assert rc == 1  # an ESCALATE was produced


def test_cli_demo_benign_exit_code_clean(capsys):
    rc = cli.main(["demo", "benign"])
    assert rc == 0  # look-alike must not escalate


def test_cli_ontologies_and_specs(capsys):
    assert cli.main(["ontologies"]) == 0
    assert cli.main(["specs"]) == 0
