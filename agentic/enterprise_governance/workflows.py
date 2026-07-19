"""
Two schema-shaped cross-vertical workflows built via the read-only adapters.

They deliberately share the SAME invariant suite unchanged — demonstrating
shared-invariant reuse across different workflows (the scalability claim). Data
is synthetic (schema-shaped), not real production records.
"""

from __future__ import annotations

from typing import List, Tuple

from agentic.enterprise_governance.adapters import (
    ApprovedRole, CRMAdapter, CRMOpportunity, FinanceAdapter, FinanceMarginDecision,
    IAMAdapter, IAMGrant, PolicyRecord, PolicyRegistryAdapter,
)
from agentic.enterprise_governance.model import (
    AuthorityRole as AR, CapabilityGroup as C, EvidenceStatus as S,
    GovernanceDecision, GovernanceEvidence, GovernanceExecution, Verification as V,
    WorkflowDependency, WorkflowEvidence,
)


def _intg(subject, intended, observed, required, satisfied, source="Ops"):
    return GovernanceEvidence(
        C.INTEGRATION_CLOSURE, source, subject,
        {"intended": intended, "observed": observed,
         "required_closure": required, "satisfied_closure": satisfied},
        S.PRESENT, V.VERIFIED, AR.SUPPORTING)


# =============================================================================
# Workflow 1 — customer discount → contract activation
# =============================================================================

def discount_to_contract(*, clean: bool = False) -> WorkflowEvidence:
    opp = CRMOpportunity("OPP-1", "jdoe", "negotiation", 0.05 if clean else 0.20,
                         "quote", "increase_conversion")
    policies = ((PolicyRecord("commercial", "2.0", "sales"),
                 PolicyRecord("margin", "2.0", "finance"),
                 PolicyRecord("margin", "2.0", "legal"))
                if clean else
                (PolicyRecord("commercial", "2.0", "sales"),
                 PolicyRecord("margin", "1.0", "finance"),   # stale
                 PolicyRecord("margin", "2.0", "legal")))
    fin = FinanceMarginDecision("OPP-1", 0.15, 0.20 if clean else 0.12,
                                "VP_Finance" if clean else None)
    evidence: List[GovernanceEvidence] = list(
        CRMAdapter(opp).evidence() + PolicyRegistryAdapter(policies).evidence()
        + FinanceAdapter(fin).evidence())

    if clean:
        auth = GovernanceEvidence(C.IDENTITY_AUTHORITY, "ERP", "signoff:OPP-1",
            {"approver": "VP_Finance"}, S.PRESENT, V.VERIFIED, AR.AUTHORITY_BEARING)
        evidence.append(auth)
        decisions = (GovernanceDecision("d_sales", "jdoe", "allow",
                     supporting_refs=("signoff:OPP-1",)),)
        executions = (GovernanceExecution("ex_crm", "CRM", "quote:OPP-1", "quote",
                      "quote", {"discount": 0.05}),
                      GovernanceExecution("ex_erp", "ERP", "quote:OPP-1", "quote",
                      "quote", {"discount": 0.05}),)
        dependencies = (WorkflowDependency("CRM", "ERP", "signoff:OPP-1", True),)
        intg = _intg("contract:OPP-1",
                     [{"system": "CRM", "key": "effective_date", "value": "2026-01-01"}],
                     [{"system": "CRM", "key": "effective_date", "value": "2026-01-01"}],
                     ["dates_aligned"], ["dates_aligned"])
        evidence.append(intg)
        return WorkflowEvidence("wf-discount-clean", "discount_to_contract",
                                tuple(evidence), decisions, executions, dependencies,
                                marked_complete=True)

    # flawed
    decisions = (GovernanceDecision("d_sales", "jdoe", "allow",
                 supporting_refs=("purpose:OPP-1",), reason_code="SALES_DISCOUNT"),)
    executions = (
        GovernanceExecution("ex_crm", "CRM", "quote:OPP-1", "quote", "contract",
                            {"discount": 0.20}),
        GovernanceExecution("ex_erp", "ERP", "quote:OPP-1", "quote", "quote",
                            {"discount": 0.0}),
    )
    dependencies = (WorkflowDependency("CRM", "ERP", "approval:OPP-1", False,
                    description="discount needs finance approval"),)
    intg = _intg("contract:OPP-1",
        intended=[{"system": "CRM", "key": "effective_date", "value": "2026-01-01"},
                  {"system": "ERP", "key": "effective_date", "value": "2026-01-01"},
                  {"system": "Billing", "key": "invoice_schedule", "value": "created"},
                  {"system": "Finance", "key": "credit_hold", "value": "released"}],
        observed=[{"system": "CRM", "key": "effective_date", "value": "2026-01-01"},
                  {"system": "ERP", "key": "effective_date", "value": "2026-02-01"},
                  {"system": "Finance", "key": "credit_hold", "value": "on_hold"}],
        required=["invoice_created", "credit_released", "dates_aligned"],
        satisfied=[])
    evidence.append(intg)
    return WorkflowEvidence("wf-discount", "discount_to_contract", tuple(evidence),
                            decisions, executions, dependencies, marked_complete=True)


# =============================================================================
# Workflow 2 — IAM permissions vs approved role (+ offboarding closure)
# =============================================================================

def iam_role_access(*, clean: bool = False) -> WorkflowEvidence:
    if clean:
        grant = IAMGrant("svc-1", ("read_billing",))
        role = ApprovedRole("svc-1", "billing_service", ("read_billing",),
                            ("admin_all",), ("write_ledger",), ("write_ledger",))
        evidence = list(IAMAdapter(grant, role).evidence())
        auth = GovernanceEvidence(C.IDENTITY_AUTHORITY, "IAM", "grant_approval:svc-1",
            {"approver": "iam_lead"}, S.PRESENT, V.VERIFIED, AR.AUTHORITY_BEARING)
        evidence.append(auth)
        decisions = (GovernanceDecision("d_grant", "iam_admin", "allow",
                     supporting_refs=("grant_approval:svc-1",)),)
        intg = _intg("offboarding:svc-1",
                     [{"system": "IAM", "key": "access", "value": "active"}],
                     [{"system": "IAM", "key": "access", "value": "active"}],
                     ["access_consistent"], ["access_consistent"])
        evidence.append(intg)
        return WorkflowEvidence("wf-iam-clean", "iam_role_access", tuple(evidence),
                                decisions, marked_complete=True)

    grant = IAMGrant("svc-1", ("read_billing", "admin_all", "legacy_dr", "write_ledger"),
                     revoked_permissions=("legacy_dr",))
    role = ApprovedRole("svc-1", "billing_service", ("read_billing",),
                        ("admin_all",), ("write_ledger",), ())
    evidence = list(IAMAdapter(grant, role).evidence())
    # grant "approved" only by a non-authority supporting record → missing authority
    decisions = (GovernanceDecision("d_grant", "iam_admin", "allow",
                 supporting_refs=("principal:svc-1",), reason_code="GRANT"),)
    intg = _intg("offboarding:svc-1",
        intended=[{"system": "IAM", "key": "access", "value": "revoked"},
                  {"system": "VPN", "key": "access", "value": "revoked"},
                  {"system": "SaaS", "key": "access", "value": "revoked"}],
        observed=[{"system": "IAM", "key": "access", "value": "revoked"},
                  {"system": "VPN", "key": "access", "value": "active"}],
        required=["access_revoked_all_systems"], satisfied=[])
    evidence.append(intg)
    return WorkflowEvidence("wf-iam", "iam_role_access", tuple(evidence), decisions,
                            marked_complete=True)


def all_workflows(*, clean: bool = False):
    return [discount_to_contract(clean=clean), iam_role_access(clean=clean)]
