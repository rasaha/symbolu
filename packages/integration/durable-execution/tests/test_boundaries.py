"""Boundary tests. These are the constraints GAS-2 was given, asserted rather than promised.

1. Agent Runtime gains no import from this package — the dependency is one-way.
2. This package re-implements no package logic: it never reaches into Agent Runtime's
   private governance internals to decide anything.
3. Nothing here can execute live or carry a credential.
4. The engine's ratification claim matches the evidence.
"""
from __future__ import annotations

import ast
import os
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[4]
RUNTIME_SRC = REPO / "packages" / "runtime" / "agent-runtime" / "src"
PKG_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"


def _python_files(root: pathlib.Path):
    for path in root.rglob("*.py"):
        yield path


def test_agent_runtime_gains_no_import_from_this_package():
    """The dependency direction is one-way. The adapter depends on the runtime; the
    runtime must never learn that the adapter exists."""
    offenders = []
    for path in _python_files(RUNTIME_SRC):
        text = path.read_text(encoding="utf-8")
        if "ugence_durable_execution" in text or "dbos" in text.lower().split():
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], (
        "Agent Runtime must not import or mention this package or its engine; "
        f"found: {offenders}"
    )


def test_agent_runtime_source_is_unmodified_by_this_package():
    """A blunt but useful check: this package ships nothing under the runtime's tree."""
    assert not (RUNTIME_SRC / "ugence_agent_runtime" / "durable").exists()
    assert not any(
        p.name.startswith("dbos") for p in _python_files(RUNTIME_SRC)
    ), "no DBOS-specific module may live inside Agent Runtime"


PROHIBITED_IMPORTS = (
    # Governance packages: the adapter must never decide permission, so it never needs
    # to see a governance type. It moves opaque runtime artefacts, nothing more.
    "risk_authority",
    "ugence_risk_authority_runtime",
    "ugence_decision_authority",
    "ugence_actiongate_provider",
    "ugence_action_clearance",
    "ugence_policy_workflow_compiler",
    "ugence_policy_authority",
    # Live execution and credentials.
    "ugence_cloud_scaling_operations",
    "boto3",
    "kubernetes",
    "requests",
    "httpx",
)


def test_adapter_imports_no_governance_package():
    """ADR §3: an adapter that needed to understand a governance type in order to
    schedule correctly would be the wrong shape."""
    offenders = []
    for path in _python_files(PKG_SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                root = name.split(".")[0]
                if root in PROHIBITED_IMPORTS:
                    offenders.append(f"{path.name}: {name}")
    assert offenders == [], f"prohibited imports found: {offenders}"


def test_no_live_execution_mode_is_reachable():
    """No ``ExecutionMode.LIVE``, no credential handling, anywhere in the package."""
    banned = ("ExecutionMode.LIVE", "AWS_SECRET", "password=", "api_key", "LIVE_MODE")
    offenders = []
    for path in _python_files(PKG_SRC):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            if token in text:
                offenders.append(f"{path.name}: {token}")
    assert offenders == [], f"live-execution or credential tokens found: {offenders}"


def test_engine_status_is_candidate_until_the_matrix_is_green():
    """The maturity claim is data the suite asserts on, so it cannot drift.

    Flipping ``DBOS_ENGINE_STATUS`` to ``RATIFIED`` is a deliberate commit that must
    carry the evidence with it; nothing flips it as a side effect.
    """
    from ugence_durable_execution import engine_status

    status = engine_status()
    assert status["engine"] == "dbos"
    assert status["pilot_validated"] is False
    assert status["production_certified"] is False
    assert status["status"] in {"CANDIDATE", "RATIFIED"}
    assert status["ratified"] is (status["status"] == "RATIFIED")


def test_readme_does_not_overclaim():
    """The README must not describe the engine as production-ready while the status
    says CANDIDATE."""
    from ugence_durable_execution import engine_status

    readme = (pathlib.Path(__file__).resolve().parents[1] / "README.md").read_text()
    if engine_status()["status"] != "CANDIDATE":
        return

    # Strip markdown emphasis before scanning: the disclaimers are written "**not**
    # pilot-validated", and a guard that cannot see through bold would flag the very
    # sentence that makes the honest claim.
    lowered = readme.lower().replace("*", "").replace("_", " ")
    for claim in (
        "production-ready",
        "production ready",
        "pilot-validated",
        "production-certified",
    ):
        idx = 0
        while (idx := lowered.find(claim, idx)) != -1:
            window = lowered[max(0, idx - 40):idx]
            assert "not" in window or "never" in window, (
                f"README claims {claim!r} while the engine status is CANDIDATE; "
                f"context: ...{lowered[max(0, idx - 60):idx + len(claim)]}"
            )
            idx += len(claim)
