"""Optional Decision Authority dependency boundary (kernel-bound adapters).

The canonical public API ``ugence_governance_provider_framework.api`` — including
the kernel-bound adapter symbols — imports WITHOUT Decision Authority installed.
Only *invoking* an adapter requires the optional ``[adapters]`` extra, and doing so
without it raises a precise, actionable error. When the extra is installed the
adapters behave exactly as before (equivalence preserved elsewhere).

The DA-absent scenarios run in a subprocess whose ``PYTHONPATH`` contains ONLY the
framework and the contracts leaf — no Decision Authority, no repository root — so
neither ``decision_governance`` nor ``ugence_decision_authority`` is importable.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
FRAMEWORK_SRC = REPO / "packages" / "governance-provider-framework" / "src"
CONTRACTS_SRC = REPO / "packages" / "governance-contracts" / "src"
DA_SRC = REPO / "packages" / "capabilities" / "decision-authority" / "src"


def _run_without_da(code: str) -> subprocess.CompletedProcess:
    """Run code with only framework + contracts on the path (Decision Authority absent)."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(FRAMEWORK_SRC), str(CONTRACTS_SRC)]))
    env.pop("PYTHONSAFEPATH", None)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=str(REPO.parent), env=env)


def test_canonical_api_imports_without_decision_authority():
    code = (
        "import importlib.util as u\n"
        "assert u.find_spec('decision_governance') is None\n"
        "assert u.find_spec('ugence_decision_authority') is None\n"
        "import ugence_governance_provider_framework\n"
        "import ugence_governance_provider_framework.api\n"
        "from ugence_governance_provider_framework.api import ("
        " ProviderRegistry, ProviderDescriptor, ProviderKind, ProviderCapabilities,"
        " ProviderCompatibility, ProviderHealth, ActionGovernanceControlPlaneAdapter,"
        " ExternalExecutionAdapter, AssertionAssessmentIntegration, AssertionLinkedRecordAdapter)\n"
        "assert len(ugence_governance_provider_framework.api.__all__) == 48\n"
        "print('ok')"
    )
    r = _run_without_da(code)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_core_symbols_usable_without_decision_authority():
    code = (
        "from ugence_governance_provider_framework.api import ProviderRegistry, ProviderKind\n"
        "from ugence_governance_provider_framework.reference import DeterministicActionGovernanceProvider\n"
        "from ugence_governance_provider_framework.resolution import resolve, ResolutionRequest\n"
        "reg = ProviderRegistry()\n"
        "reg.register(DeterministicActionGovernanceProvider().descriptor())\n"
        "p, rec = resolve(reg, ResolutionRequest(kind=ProviderKind.ACTION_GOVERNANCE))\n"
        "assert p.descriptor().provider_id == 'deterministic-action'\n"
        "print('ok')"
    )
    r = _run_without_da(code)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_adapter_invocation_without_extra_raises_precise_error():
    code = (
        "from ugence_governance_provider_framework.api import ("
        " ActionGovernanceControlPlaneAdapter, AssertionAssessmentIntegration)\n"
        "from ugence_governance_provider_framework.reference import DeterministicActionGovernanceProvider\n"
        "a = ActionGovernanceControlPlaneAdapter(DeterministicActionGovernanceProvider())\n"
        "try:\n"
        "    a.authorize(object(), object())\n"
        "    raise SystemExit('no error raised on authorize')\n"
        "except ModuleNotFoundError as e:\n"
        "    assert 'ugence-governance-provider-framework[adapters]' in str(e), str(e)\n"
        "try:\n"
        "    AssertionAssessmentIntegration.to_linked_record_snapshot(object(), tenant_id='t',"
        " record_type='r', record_id='i', subject_ref='s')\n"
        "    raise SystemExit('no error raised on snapshot projection')\n"
        "except ModuleNotFoundError as e:\n"
        "    assert 'ugence-governance-provider-framework[adapters]' in str(e), str(e)\n"
        "print('ok')"
    )
    r = _run_without_da(code)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_adapters_operate_when_decision_authority_present(registry):
    """With Decision Authority importable (this env), the kernel-bound adapter drives
    the full control-plane authorization end to end — unchanged behaviour."""
    from kernel_lifecycle import run_kernel_action_lifecycle
    from ugence_governance_provider_framework.api import ActionGovernanceControlPlaneAdapter
    from ugence_governance_provider_framework.reference import DeterministicActionGovernanceProvider

    control_plane = ActionGovernanceControlPlaneAdapter(DeterministicActionGovernanceProvider())

    class _LinkedRecord:
        def get_record(self, *, tenant_id, record_type, record_id, version=None):
            from decision_governance.api.ports import LinkedRecordSnapshot
            return LinkedRecordSnapshot(
                record_type=record_type, record_id=record_id, version=version or 1,
                tenant_id=tenant_id, status="FINALIZED", subject_ref="subject",
                content_hash="h", metadata={})

    status, events, resp = run_kernel_action_lifecycle(
        control_plane=control_plane, linked_record=_LinkedRecord())
    assert resp.outcome.value in ("AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS")
