"""Ground-truth isolation (Task 103) — expected labels never reach providers."""
from __future__ import annotations

import ast
import dataclasses
import pathlib

from enterprise_validation_pilot.datasets.build_dataset import build
from enterprise_validation_pilot.pilot import _substantive
from enterprise_validation_pilot.runners.workflow import run_scenario
from enterprise_validation_pilot.schemas.scenario import ExpectedOutcome

_PKG = pathlib.Path(__file__).resolve().parents[1]


def _imports(path: pathlib.Path):
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


def test_authoring_does_not_import_providers():
    mods = set(_imports(_PKG / "scenarios" / "authoring.py"))
    assert not any(m.split(".")[0] in ("tap_provider", "actiongate_provider") for m in mods)


def test_workflow_never_reads_expected_region():
    src = (_PKG / "runners" / "workflow.py").read_text()
    assert ".expected" not in src, "runner must never read the scenario expected region"


def test_expected_labels_do_not_affect_provider_output():
    """Mutating a scenario's expected region must not change actual outcomes."""
    ds = build()
    for sid in ("procurement-001", "procurement-002", "procurement-013",
                "procurement-017", "procurement-025"):
        s = ds.by_id(sid)
        garbage = ExpectedOutcome(tap_outcome="WRONG", actiongate_outcome="WRONG",
                                  dispatched=not s.expected.dispatched)
        mutated = dataclasses.replace(s, expected=garbage)
        assert _substantive(run_scenario(s)) == _substantive(run_scenario(mutated))


def test_expected_stored_before_execution():
    # every scenario carries an authored expected outcome independent of any run
    for s in build().scenarios:
        assert isinstance(s.expected, ExpectedOutcome)
        assert s.expected.tap_outcome in (
            "SUPPORTED", "UNSUPPORTED", "CONSTRAINED", "INDETERMINATE")
