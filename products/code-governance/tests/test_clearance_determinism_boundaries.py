"""MVP 1B acceptance tests 56-73: determinism and boundary guarantees."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cg_clearance_helpers import (
    EVAL, REQUIRED, drive_to_action_evaluated, full_1b, profile, projection, snapshot,
)
from ugence_code_governance import CodeGovernanceService
from ugence_code_governance.clearance.adapter import ActionClearanceShadowAdapter
from ugence_code_governance.clearance.intervention import (
    InterventionRoutingPolicy, assess_intervention,
)
from ugence_code_governance.clearance.signal_adapter import build_trusted_signals
from ugence_action_clearance import ClearanceStatus, evaluate_clearance


def _fixed_request(action, shadow, *, snap=None):
    """Build a ClearanceRequest from fixed inputs (deterministic-replay basis)."""
    adapter = ActionClearanceShadowAdapter()
    bundle = build_trusted_signals(
        snap or snapshot(action), projection(), tenant_id="acme", subject_ref=action.repository,
        authorization_ref=shadow.result_fingerprint, action_fingerprint=action.fingerprint,
        required_signal_types=REQUIRED)
    authz = adapter.authorization_context(shadow, action, actor_ref="user:approver",
                                          authorization_issued_at=action.expiry)
    ident = adapter.action_identity(action, actor_ref="user:approver")
    ctx = adapter.policy_context(profile())
    req = adapter.build_request(request_id="fixed", tenant_id="acme", evaluation_time=EVAL,
                                authorization=authz, action=ident, signals=bundle, policy=ctx)
    return req, bundle


def _ctx():
    svc = CodeGovernanceService()
    change, rid, action, shadow = drive_to_action_evaluated(svc)
    return action, shadow


# 56. identical inputs -> identical signal fingerprints
def test_identical_signal_fingerprints():
    action, shadow = _ctx()
    _, b1 = _fixed_request(action, shadow)
    _, b2 = _fixed_request(action, shadow)
    assert b1.fingerprint == b2.fingerprint
    assert [s.content_fingerprint for s in b1.signals] == [s.content_fingerprint for s in b2.signals]


# 57. identical inputs -> identical request fingerprint
def test_identical_request_fingerprint():
    action, shadow = _ctx()
    r1, _ = _fixed_request(action, shadow)
    r2, _ = _fixed_request(action, shadow)
    assert r1.fingerprint == r2.fingerprint


# 58. identical inputs -> identical result fingerprint
def test_identical_result_fingerprint():
    action, shadow = _ctx()
    r1, _ = _fixed_request(action, shadow)
    r2, _ = _fixed_request(action, shadow)
    res1 = evaluate_clearance(r1, profile().to_clearance_policy())
    res2 = evaluate_clearance(r2, profile().to_clearance_policy())
    assert res1.result_fingerprint == res2.result_fingerprint
    assert res1.status is ClearanceStatus.CLEAR


# 59. identical inputs -> identical intervention fingerprint (full pipeline)
def test_identical_intervention_fingerprint():
    _, _, _, _, _, hia1, _ = full_1b()
    _, _, _, _, _, hia2, _ = full_1b()
    assert hia1.fingerprint == hia2.fingerprint


# 60. reason ordering stable
def test_reason_ordering_stable():
    action, shadow = _ctx()
    r1, _ = _fixed_request(action, shadow, snap=snapshot(action, change_freeze_active=True,
                                                         target_available=False))
    res = evaluate_clearance(r1, profile().to_clearance_policy())
    assert list(res.reason_codes) == sorted(res.reason_codes)


# 61. authority routing ordering stable
def test_authority_routing_ordering_stable():
    _, _, _, _, _, hia, _ = full_1b(snap_overrides={"incident_active": True},
                                    classification=__import__(
                                        "ugence_code_governance", fromlist=["RepositoryClassification"]
                                    ).RepositoryClassification.CRITICAL, incident_escalate=True)
    assert list(hia.required_authorities) == sorted(hia.required_authorities)
    assert list(hia.intervention_types) == sorted(hia.intervention_types)


# 62-63. no hidden clock read / no random dependency in the integration
def test_no_clock_or_random_in_clearance_module():
    import inspect
    import ugence_code_governance.clearance as pkg
    root = Path(pkg.__file__).parent
    for p in root.rglob("*.py"):
        src = p.read_text()
        assert "datetime.now(" not in src, p
        assert ".utcnow(" not in src, p
        assert "time.time(" not in src, p
        assert "import random" not in src, p


# --- boundaries (64-73) ---------------------------------------------------
_CLEARANCE = Path(__file__).resolve().parents[1] / "src" / "ugence_code_governance"
_AC_PKG = Path(__file__).resolve().parents[3] / "packages" / "capabilities" / "action-clearance"


def _imported_roots(path: Path):
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


# 64. no Action Clearance source modified (checked at commit time; here: not imported privately)
def test_no_action_clearance_internals_imported():
    for p in (_CLEARANCE / "clearance").rglob("*.py"):
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                # only the public top-level ugence_action_clearance is allowed
                assert not node.module.startswith("ugence_action_clearance."), \
                    f"{p} imports Action Clearance internals: {node.module}"


# 65-72. no forbidden imports / drivers / providers anywhere in the product.
# stdlib ``sqlite3`` is the sanctioned MVP 1C durable backend and is permitted
# ONLY inside the ``persistence/`` boundary; external DB drivers / network / infra
# clients remain forbidden everywhere in the product.
def test_no_forbidden_imports():
    forbidden = {"requests", "httpx", "sqlalchemy", "psycopg2", "mysql", "redis",
                 "kafka", "boto3", "github", "kubernetes", "symbolu_robotics", "acp"}
    persistence_only = {"sqlite3"}
    for p in _CLEARANCE.rglob("*.py"):
        in_persistence = "persistence" in p.parts
        for root in _imported_roots(p):
            assert root not in forbidden, f"{p} imports {root}"
            if root in persistence_only:
                assert in_persistence, f"{p} imports {root} outside persistence/"


def test_no_execution_or_reservation_tokens():
    banned = ("reserve_once", "def dispatch", "def execute", "def merge(",
              "persist_enforcement_receipt", "subprocess", "os.system")
    for p in (_CLEARANCE / "clearance").rglob("*.py"):
        text = p.read_text()
        for token in banned:
            assert token not in text, f"{p} contains {token!r}"


def test_no_new_provider_kind():
    # Precise check: no product source DEFINES or INSTANTIATES a ProviderKind
    # (a docstring may legitimately say "adds no ProviderKind").
    for p in _CLEARANCE.rglob("*.py"):
        text = p.read_text()
        assert "class ProviderKind" not in text
        assert "ProviderKind(" not in text


def test_action_clearance_package_not_modified_by_import_direction():
    # the AC package must not import Code Governance
    for p in (_AC_PKG / "src").rglob("*.py"):
        assert "ugence_code_governance" not in _imported_roots(p)


# 73. Code Governance execution remains disabled
def test_execution_remains_disabled():
    svc, rid, a, s, rec, hia, res = full_1b()
    assert svc.execution_status() == "DISABLED"
