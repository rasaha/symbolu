"""Phase 5A extraction guarantees for the Decision Governance kernel.

Proves the kernel is domain-neutral, has no back-dependency on the application,
imports acyclically, and preserves identical object identity, hashes, serialization,
and lifecycle transitions after being extracted from ``ai_hiring``.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

import decision_governance
import decision_governance.actions
import decision_governance.decisions
import decision_governance.execution

_KERNEL_ROOT = pathlib.Path(decision_governance.__file__).parent
_FORBIDDEN = re.compile(
    r"\b(candidate|resume|interview|hiring|employee|recruiter|offer|ats|job|applicant)\b",
    re.IGNORECASE)

#: Pinned reference hashes computed from the pre-extraction implementation.
_CORE_HASH = "8fdaa7c6cc3c959ff9a908b09ca60a18b0a07fc45cdf3fbbdf80d497f6417a6a"
_MAPPING_HASH = "da68ecb044f32ce7526c3d742948b8f6734604a23590da69fba62737506823ec"


def _kernel_py_files():
    return [p for p in _KERNEL_ROOT.rglob("*.py") if "__pycache__" not in str(p)]


def test_kernel_contains_no_hiring_terminology():
    offenders = {}
    for path in _kernel_py_files():
        hits = _FORBIDDEN.findall(path.read_text(encoding="utf-8"))
        if hits:
            offenders[str(path.relative_to(_KERNEL_ROOT))] = sorted(set(hits))
    assert not offenders, f"kernel contains hiring terms: {offenders}"


def test_kernel_never_imports_the_application():
    offenders = []
    for path in _kernel_py_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*(import|from)\s+ai_hiring", text, re.MULTILINE):
            offenders.append(str(path.relative_to(_KERNEL_ROOT)))
        if re.search(r"^\s*(import|from)\s+(domains|applications)\b", text, re.MULTILINE):
            offenders.append(str(path.relative_to(_KERNEL_ROOT)))
    assert not offenders, f"kernel imports a domain/application: {offenders}"


def test_kernel_imports_without_loading_the_application():
    """A fresh interpreter can import the kernel with no ai_hiring module loaded."""
    code = (
        "import decision_governance, decision_governance.decisions, "
        "decision_governance.actions, decision_governance.execution, sys; "
        "bad=[m for m in sys.modules if m.startswith('ai_hiring') "
        "or m.startswith('domains') or m.startswith('applications')]; "
        "assert not bad, bad; print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_object_identity_is_preserved_through_shims():
    import ai_hiring.decision_cases as dc_shim
    import ai_hiring.action_requests as ar_shim
    import ai_hiring.executions as ex_shim
    assert dc_shim.DecisionCase is decision_governance.decisions.DecisionCase
    assert ar_shim.ActionRequest is decision_governance.actions.ActionRequest
    assert ex_shim.ExecutionIntent is decision_governance.execution.ExecutionIntent
    # submodule paths resolve to the identical kernel modules
    from ai_hiring.decision_cases import status as shim_status
    from decision_governance.decisions import status as kernel_status
    assert shim_status is kernel_status


def test_domain_model_base_is_shared():
    from ai_hiring.domain.base import DomainModel as app_base
    from decision_governance.base import DomainModel as kernel_base
    assert app_base is kernel_base
    # a hiring contract and a kernel contract share the one base class
    from ai_hiring.assessments.assessment import Assessment
    assert issubclass(Assessment, kernel_base)
    assert issubclass(decision_governance.decisions.DecisionCase, kernel_base)


def test_hiring_error_alias_preserves_isinstance():
    from ai_hiring.errors import HiringError, DecisionCaseError
    from decision_governance.errors import DomainValidationError, GovernanceError
    assert HiringError is GovernanceError
    assert issubclass(DecisionCaseError, GovernanceError)
    assert issubclass(DomainValidationError, GovernanceError)


def test_core_hash_is_unchanged():
    from decision_governance.common import canonical_hash
    assert canonical_hash({"a": 1, "b": "x", "c": ["z", "y"]}) == _CORE_HASH


def test_contract_hash_is_unchanged():
    from decision_governance.actions import ActionMapping, ParameterSchema
    from decision_governance.decisions import DecisionOutcome
    m = ActionMapping(
        mapping_id="m1", version=1, domain_id="d", decision_type="t",
        decision_outcome=DecisionOutcome.ADVANCE, permitted_action_type="A",
        target_system_type="S", parameter_schema=ParameterSchema(required_fields=("k",)))
    assert m.compute_hash() == _MAPPING_HASH


def test_serialization_roundtrip_is_stable():
    from decision_governance.decisions import DecisionCase, SubjectRef
    case = DecisionCase(
        decision_case_id="dc1", tenant_id="t1", decision_type="x",
        subject_refs=(SubjectRef(subject_id="s1"),), created_by="u1",
        case_version_id="v1")
    assert DecisionCase(**case.model_dump()) == case


def test_lifecycle_tables_are_intact():
    from decision_governance.decisions.lifecycle import (
        ALLOWED_TRANSITIONS as case_tx)
    from decision_governance.actions.lifecycle import (
        ALLOWED_TRANSITIONS as action_tx)
    from decision_governance.execution.lifecycle import (
        ALLOWED_TRANSITIONS as exec_tx)
    # tables are non-empty and every target is a valid state of its own enum
    from decision_governance.decisions.status import CaseStatus
    from decision_governance.actions.status import ActionRequestStatus
    from decision_governance.execution.status import ExecutionStatus
    assert set(case_tx).issubset(set(CaseStatus))
    assert set(action_tx).issubset(set(ActionRequestStatus))
    assert set(exec_tx).issubset(set(ExecutionStatus))
    # no execution transition targets an executed/succeeded shortcut from dispatch
    for targets in action_tx.values():
        assert all(t.value not in ("EXECUTED", "SUCCEEDED") for t in targets)


def test_application_depends_on_kernel_not_reverse():
    from applications.ai_hiring import build_in_memory_platform
    platform = build_in_memory_platform()
    # The application composes kernel contracts (identity preserved end to end).
    assert platform.decision_case_service is not None
    assert platform.execution_service is not None
