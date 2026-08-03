"""Permission-bounding tests (§31 Permission bounding; P2-I11,I12,I13)."""
from __future__ import annotations

from ugence_agent_workforce_composer.composition_contracts import PermissionCategory
from ugence_agent_workforce_composer.permissions import (
    PROPOSAL_NOTICE,
    PermissionBoundingPolicy,
    propose_permission_bound,
)
from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
from ._helpers import enterprise, make_profile, make_role


def _policy(**kw):
    return stamp_fingerprint(PermissionBoundingPolicy(policy_id="p", policy_version="1", **kw),
                             "policy_digest")


def test_only_required_permissions_proposed():
    role = make_role(required_permissions=("read_context",))
    prof = make_profile(requested_permissions=("read_context", "write_draft", "call_tool"))
    prop = propose_permission_bound(role, prof, enterprise(maximum_permission_scope=(
        "read_context", "write_draft", "call_tool")), _policy())
    assert prop.feasible
    assert prop.proposed_permissions == ("read_context",)          # least privilege
    excessive = {p.permission for p in prop.categorized
                 if p.category is PermissionCategory.EXCESSIVE_REQUESTED}
    assert excessive == {"write_draft", "call_tool"}


def test_prohibited_permission_makes_infeasible():
    role = make_role(required_permissions=("delete_all",),
                     prohibited_permissions=("delete_all",))
    prof = make_profile(requested_permissions=("delete_all",))
    prop = propose_permission_bound(role, prof, enterprise(maximum_permission_scope=("delete_all",)),
                                    _policy())
    assert prop.feasible is False
    assert any(p.category is PermissionCategory.PROHIBITED for p in prop.categorized)


def test_governance_owned_permission_never_proposed():
    role = make_role(required_permissions=("approve_binding",))
    prof = make_profile(requested_permissions=("approve_binding",))
    prop = propose_permission_bound(role, prof, enterprise(maximum_permission_scope=("approve_binding",)),
                                    _policy(governance_owned_permissions=("approve_binding",)))
    assert prop.feasible is False
    assert "approve_binding" not in prop.proposed_permissions


def test_unsupported_required_permission_infeasible():
    role = make_role(required_permissions=("call_tool",))
    prof = make_profile(requested_permissions=("read_context",))  # cannot do call_tool
    prop = propose_permission_bound(role, prof, enterprise(maximum_permission_scope=(
        "read_context", "call_tool")), _policy())
    assert prop.feasible is False
    assert any(p.category is PermissionCategory.UNSUPPORTED for p in prop.categorized)


def test_enterprise_scope_ceiling():
    role = make_role(required_permissions=("call_tool",))
    prof = make_profile(requested_permissions=("call_tool",))
    prop = propose_permission_bound(role, prof, enterprise(maximum_permission_scope=("read_context",)),
                                    _policy())
    assert prop.feasible is False  # call_tool exceeds enterprise scope


def test_authority_bounded_by_ceilings():
    role = make_role(required_permissions=("read_context",), authority_ceiling=2)
    prof = make_profile(requested_permissions=("read_context",), maximum_authority_scope=9)
    prop = propose_permission_bound(role, prof, enterprise(maximum_authority_scope=3), _policy())
    assert prop.proposed_authority_scope <= 2       # min(role ceiling, enterprise, agent)
    assert prop.proposed_authority_scope <= 3


def test_human_review_flag():
    role = make_role(required_permissions=("write_draft",))
    prof = make_profile(requested_permissions=("write_draft",))
    prop = propose_permission_bound(role, prof, enterprise(maximum_permission_scope=("write_draft",)),
                                    _policy(human_review_permissions=("write_draft",)))
    assert prop.requires_human_review is True


def test_proposal_carries_no_grant_language():
    role = make_role(required_permissions=("read_context",))
    prof = make_profile(requested_permissions=("read_context",))
    prop = propose_permission_bound(role, prof, enterprise(maximum_permission_scope=("read_context",)),
                                    _policy())
    assert prop.notice == PROPOSAL_NOTICE
    assert "does not grant" in prop.notice
    # no field or method claims a grant
    assert not any(k in prop.model_dump() for k in ("granted", "authorized", "provisioned"))


def test_least_privilege_invariants():
    role = make_role(required_permissions=("read_context",), prohibited_permissions=())
    prof = make_profile(requested_permissions=("read_context", "extra"))
    prop = propose_permission_bound(role, prof, enterprise(maximum_permission_scope=(
        "read_context", "extra")), _policy())
    proposed = set(prop.proposed_permissions)
    assert proposed <= set(role.required_permissions)          # ⊆ required
    assert proposed <= set(prof.requested_permissions)         # ⊆ agent-supported
    assert not (proposed & set(role.prohibited_permissions))   # ∩ prohibited = ∅
