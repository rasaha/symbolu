"""The Phase 5 / Phase 6 boundary — structural, not merely behavioral.

Phase 4C ends at a non-executable ``SubjectRiskDecision`` or a typed non-evaluation. The
tests here prove the boundary two ways, because either alone would be weak:

* **Structurally** — the package's import graph and call graph contain no envelope
  issuer, ActionGate, credential broker, cloud-provider client, execution or
  effect-verification path. A behavioral test could only show that today's inputs did
  not reach one; the structural test shows there is nothing to reach.
* **Behaviorally** — sentinels that fail loudly if any such collaborator is invoked
  during a real end-to-end evaluation.
"""

from __future__ import annotations

import ast
import inspect
import pkgutil

import pytest

import ugence_cloud_scaling_risk_integration as pkg
from conftest import INSIDE_WINDOW, fixed_clock, reference_seam
from risk_authority.integrations import SubjectRiskDisposition

from ugence_cloud_scaling_risk_integration import (
    CloudScalingRiskAdapter,
    NonExecutableInvariantError,
)


def package_modules():
    for info in pkgutil.iter_modules(pkg.__path__):
        yield __import__(f"{pkg.__name__}.{info.name}", fromlist=["_"])


# --- structural containment -----------------------------------------------------------


FORBIDDEN_IMPORTS = (
    "risk_authority.services.envelope_issuer",
    "risk_authority.services.envelope_verifier",
    "risk_authority.integrations.actiongate",
    "ugence_actiongate_provider",
    "ugence_decision_authority",
    "kubernetes",
    "boto3",
    "google.cloud",
    "azure",
    "requests",
    "urllib",
    "socket",
    "subprocess",
)


def test_no_module_imports_an_execution_or_authorization_dependency():
    for module in package_modules():
        tree = ast.parse(inspect.getsource(module))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for name in imported:
            for forbidden in FORBIDDEN_IMPORTS:
                assert not name.startswith(forbidden), (
                    f"{module.__name__} imports {name}, which reaches {forbidden}"
                )


FORBIDDEN_CALLS = frozenset(
    {
        "issue_envelope",
        "verify_envelope",
        "authorize_action",
        "issue_credential",
        "mint_credential",
        "broker_credential",
        "execute",
        "actuate",
        "apply_scaling",
        "scale",
        "verify_effect",
        "reconcile_effect",
        "learn",
        "update_policy",
    }
)


def test_no_module_calls_an_execution_or_authorization_operation():
    for module in package_modules():
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = (
                    func.attr
                    if isinstance(func, ast.Attribute)
                    else func.id if isinstance(func, ast.Name) else None
                )
                assert name not in FORBIDDEN_CALLS, (
                    f"{module.__name__} calls {name!r}, which is Phase 5/6 capability"
                )


def test_the_package_declares_exactly_two_first_party_dependencies():
    import pathlib
    import re

    pyproject = (
        pathlib.Path(pkg.__file__).resolve().parents[2] / "pyproject.toml"
    ).read_text(encoding="utf-8")
    block = re.search(r"^dependencies = \[(.*?)\]", pyproject, re.S | re.M).group(1)
    declared = sorted(re.findall(r'"\s*([A-Za-z0-9._-]+)', block))
    assert declared == ["ugence-cloud-scaling-controller", "ugence-risk-authority"]


def test_the_adapter_is_a_one_way_leaf():
    """Neither dependency may import this package back."""

    import pathlib

    repo = pathlib.Path(pkg.__file__).resolve().parents[5]
    for tree in (
        repo / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
        repo / "packages" / "risk_authority" / "src",
    ):
        assert tree.exists(), tree
        for path in tree.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "ugence_cloud_scaling_risk_integration" not in text, (
                f"{path} imports the adapter — the dependency direction must stay one-way"
            )


def test_the_controller_still_has_no_risk_authority_import():
    """The controller must remain an advisory leaf (ADR acceptance invariant)."""

    import pathlib

    tree = (
        pathlib.Path(pkg.__file__).resolve().parents[5]
        / "packages" / "capabilities" / "cloud-scaling-controller" / "src"
    )
    for path in tree.rglob("*.py"):
        source = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(source):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("risk_authority"), path
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("risk_authority"), path


# --- behavioral sentinels ----------------------------------------------------------------


def test_a_full_evaluation_never_invokes_the_envelope_issuer(monkeypatch, recommendation):
    from risk_authority.api.dependencies import RiskAuthorityApplication

    def _forbidden(*args, **kwargs):  # pragma: no cover - reaching it IS the failure
        raise AssertionError("issue_envelope was invoked during a Phase 4C evaluation")

    monkeypatch.setattr(RiskAuthorityApplication, "issue_envelope", _forbidden)
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    assert outcome.decision.envelope_issued is False


def test_a_full_evaluation_never_invokes_action_authorization(monkeypatch, recommendation):
    from risk_authority.api.dependencies import RiskAuthorityApplication

    if hasattr(RiskAuthorityApplication, "authorize_action"):
        def _forbidden(*args, **kwargs):  # pragma: no cover
            raise AssertionError("authorize_action was invoked during Phase 4C")

        monkeypatch.setattr(RiskAuthorityApplication, "authorize_action", _forbidden)

    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    assert outcome.decision.actiongate_invoked is False


def test_every_execution_flag_is_false_on_every_outcome(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                 "credential_issued", "actuation_performed", "effect_verified",
                 "executable"):
        assert getattr(outcome, flag) is False
    for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                 "actuation_performed", "effect_verified", "executable"):
        assert getattr(outcome.decision, flag) is False


def test_a_risk_pass_is_not_an_authorization(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    if outcome.disposition is SubjectRiskDisposition.RISK_PASSED:
        assert outcome.grants_authority is False
        assert outcome.decision.authorization_performed is False
        assert outcome.decision.executable is False


def test_the_public_api_exposes_no_execution_surface():
    surface = set(pkg.__all__)
    for forbidden in ("issue_envelope", "authorize", "authorize_action", "execute",
                      "actuate", "scale", "credential", "broker", "ActionGate"):
        assert not any(forbidden.lower() in name.lower() for name in surface), forbidden


def test_no_outcome_status_can_express_authorization():
    from ugence_cloud_scaling_risk_integration import AdapterOutcomeStatus

    assert {status.value for status in AdapterOutcomeStatus} == {
        "RISK_DECISION",
        "PROJECTION_ABSTAINED_UPSTREAM",
        "PROJECTION_REJECTED",
    }
