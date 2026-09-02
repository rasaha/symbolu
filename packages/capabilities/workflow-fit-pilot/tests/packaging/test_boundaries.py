"""§8 rows A30 and A31, the version and API pins, and the CaptureAttemptStatus vocabulary pin."""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[5]
PKG = REPO / "packages" / "capabilities" / "workflow-fit-pilot"
SRC = PKG / "src" / "ugence_workflow_fit_pilot"
BOUNDARY = SRC / "boundary"

FORBIDDEN = {
    "agentic", "agentic_framework", "reasoning_workflows", "adaptive_prompts", "symbolu", "ugence_agentic_proposer", "ugence_agent_workforce_composer",
    "ugence_agent_runtime", "ugence_agent_value_readiness", "governed_value", "ugence_context_minimization", "ugence_policy_authority", "ugence_trusted_evidence_authority",
    "openai", "anthropic", "requests", "httpx", "urllib", "http", "random", "numpy",
}
ALLOWED = {"ugence_reasoning_method_governance", "ugence_readiness_comparison", "ugence_reasoning_method_advisor", "ugence_governance_contracts", "ugence_uvi_policy_contracts", "ugence_jcs",
           "__future__", "dataclasses", "datetime", "decimal", "enum", "re", "typing", "json"}
BOUNDARY_ONLY = {"socket", "subprocess", "importlib", "argparse", "sys", "os", "tempfile"}
RUNNER_ONLY = {"subprocess", "os", "sys", "tempfile", "time"}  # process start and the boundary-readiness wait live in runner.py
CLOCK_NEEDLES = ("datetime.now(", "utcnow(", "date.today(", "time.time(", "monotonic(", "perf_counter(", "time_ns(")


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names, calls = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "import_module":
                calls.append(("import_module", path.name))
            if isinstance(f, ast.Name) and f.id in ("__import__", "exec", "eval", "compile", "open", "input"):
                calls.append((f.id, path.name))
    return names, calls


def test_a30_import_boundary_and_single_dynamic_import():
    dyn = []
    for path in SRC.rglob("*.py"):
        names, calls = _imports(path)
        assert not names & FORBIDDEN, (path.name, names & FORBIDDEN)
        extra = names - ALLOWED
        if path.parent == BOUNDARY:
            assert extra <= BOUNDARY_ONLY, (path.name, extra)
        elif path.name == "runner.py":
            assert extra <= RUNNER_ONLY, (path.name, extra)
        else:
            assert not extra, (path.name, extra)
        dyn += calls
    assert dyn == [("import_module", "entry.py")], dyn


def test_a30_clock_reads_only_in_the_boundary():
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        hits = [n for n in CLOCK_NEEDLES if n in text]
        if path.parent == BOUNDARY and path.name in ("server.py", "attestation.py"):
            assert hits == ["datetime.now("], (path.name, hits)
        elif path.name == "runner.py":
            assert hits == ["monotonic("], (path.name, hits)  # the boundary start-up wait, not an evidence instant
        else:
            assert not hits, (path.name, hits)


def test_a30_capture_attempt_status_pinned_to_context_minimization():
    cm = pytest.importorskip("ugence_context_minimization.token_accounting")
    from ugence_workflow_fit_pilot.api import CaptureAttemptStatus

    assert [m.value for m in CaptureAttemptStatus] == [m.value for m in cm.AttemptStatus]


def test_a31_no_owner_supplied_numeric_default():
    from ugence_workflow_fit_pilot import api

    for n in api.__all__:
        obj = getattr(api, n)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                d = f.default
                assert d is dataclasses.MISSING or d is None or d == () or isinstance(d, str), f"{n}.{f.name} has a numeric-looking default {d!r}"
    text = "\n".join(p.read_text(encoding="utf-8") for p in SRC.rglob("*.py"))
    for needle in ("threshold =", "sample_size", "coverage_target", "acceptance", "tau ="):
        assert needle not in text, needle
    assert not re.search(r"(?<![\w.])0\.\d+(?![.\d])", text), "a decimal literal appears in src/"


def test_version_and_api_pins():
    from ugence_workflow_fit_pilot import api

    for n in api.__all__:
        assert hasattr(api, n), n
    text = (PKG / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "([^"]+)"', text, re.M).group(1) == api.__version__
    assert "ugence-context-minimization" not in text


def test_slice_1_and_2_do_not_import_the_pilot():
    for pkg in ("reasoning-method-governance", "readiness-comparison", "reasoning-method-advisor"):
        for path in (REPO / "packages" / "capabilities" / pkg / "src").rglob("*.py"):
            assert "ugence_workflow_fit_pilot" not in path.read_text(encoding="utf-8"), path
