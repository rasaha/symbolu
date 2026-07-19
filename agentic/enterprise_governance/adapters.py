"""
Read-only, source-schema-shaped adapters.

Each adapter maps ONE source system's record shape to neutral GovernanceEvidence.
Adapters never invent data: a field the source does not carry is emitted as
``EvidenceStatus.MISSING`` so downstream gaps stay explicit.

The source dataclasses are shaped like real systems (CRM opportunity, ERP
invoice, IAM grant, ...) but are populated with SYNTHETIC fixtures — this is not
real production data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Protocol, Tuple

from agentic.enterprise_governance.model import (
    AuthorityRole as AR, CapabilityGroup as C, EvidenceStatus as S,
    GovernanceEvidence, Verification as V,
)


class ReadOnlyAdapter(Protocol):
    """A source adapter emits neutral evidence; it never mutates the source."""
    def evidence(self) -> Tuple[GovernanceEvidence, ...]: ...


def _ev(cap, source, subject, payload, *, status=S.PRESENT, verify=V.DECLARED,
        authority=AR.SUPPORTING, refs=()):
    return GovernanceEvidence(cap, source, subject, payload, status, verify, authority,
                              tuple(refs))


# --- Sales / CRM -------------------------------------------------------------

@dataclass(frozen=True)
class CRMOpportunity:
    opp_id: str
    owner: str
    stage: str
    discount_pct: float
    quote_form: Optional[str]           # may be None (missing)
    stated_purpose: Optional[str]


class CRMAdapter:
    def __init__(self, opp: CRMOpportunity):
        self.opp = opp

    def evidence(self) -> Tuple[GovernanceEvidence, ...]:
        o = self.opp
        out = [
            _ev(C.IDENTITY_AUTHORITY, "CRM", f"actor:{o.owner}", {"role": "sales_agent"},
                verify=V.VERIFIED, authority=AR.SUPPORTING),
        ]
        if o.stated_purpose:
            out.append(_ev(C.PURPOSE_POLICY_BASIS, "CRM", f"purpose:{o.opp_id}",
                {"objective": o.stated_purpose}, verify=V.DECLARED, authority=AR.ADVISORY))
        else:
            out.append(_ev(C.PURPOSE_POLICY_BASIS, "CRM", f"purpose:{o.opp_id}",
                {}, status=S.MISSING, verify=V.UNKNOWN))
        if o.quote_form:
            out.append(_ev(C.AUTHORIZED_FORM, "CRM", f"form:{o.opp_id}",
                {"form": o.quote_form}))
        else:
            out.append(_ev(C.AUTHORIZED_FORM, "CRM", f"form:{o.opp_id}", {},
                status=S.MISSING))
        return tuple(out)


# --- Policy registry ---------------------------------------------------------

@dataclass(frozen=True)
class PolicyRecord:
    name: str
    version: str
    vertical: str


class PolicyRegistryAdapter:
    def __init__(self, records: Tuple[PolicyRecord, ...]):
        self.records = records

    def evidence(self) -> Tuple[GovernanceEvidence, ...]:
        return tuple(
            _ev(C.DECISION_DERIVATION, f"PolicyRegistry:{r.vertical}",
                f"policy:{r.vertical}:{r.name}", {"policy_versions": (f"{r.name}@{r.version}",)},
                verify=V.VERIFIED, authority=AR.AUTHORITY_BEARING)
            for r in self.records)


# --- Finance / ERP -----------------------------------------------------------

@dataclass(frozen=True)
class FinanceMarginDecision:
    opp_id: str
    margin_floor: float
    projected_margin: float
    approver: Optional[str]             # None = missing approval


class FinanceAdapter:
    def __init__(self, dec: FinanceMarginDecision):
        self.dec = dec

    def evidence(self) -> Tuple[GovernanceEvidence, ...]:
        d = self.dec
        out = [
            _ev(C.PURPOSE_POLICY_BASIS, "ERP", f"margin_floor:{d.opp_id}",
                {"objective": "preserve_margin", "margin_floor": d.margin_floor},
                verify=V.VERIFIED, authority=AR.AUTHORITY_BEARING),
        ]
        preserved = d.projected_margin >= d.margin_floor
        out.append(_ev(C.PROTECTED_INVARIANTS, "ERP", f"margin_invariant:{d.opp_id}",
            {"invariant": "margin_floor", "preserved": preserved},
            verify=V.VERIFIED, authority=AR.AUTHORITY_BEARING))
        if d.approver:
            out.append(_ev(C.IDENTITY_AUTHORITY, "ERP", f"approval:{d.opp_id}",
                {"approver": d.approver}, verify=V.VERIFIED, authority=AR.AUTHORITY_BEARING))
        else:
            out.append(_ev(C.IDENTITY_AUTHORITY, "ERP", f"approval:{d.opp_id}", {},
                status=S.MISSING, verify=V.UNKNOWN))
        return tuple(out)


# --- IAM ---------------------------------------------------------------------

@dataclass(frozen=True)
class IAMGrant:
    principal: str
    granted_permissions: Tuple[str, ...]
    revoked_permissions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovedRole:
    principal: str
    role: str
    permitted_permissions: Tuple[str, ...]
    prohibited_permissions: Tuple[str, ...] = ()
    approval_required_permissions: Tuple[str, ...] = ()
    approvals_present: Tuple[str, ...] = ()


class IAMAdapter:
    """Maps IAM grants vs approved role into the capability-space evidence — the
    same shape the deploy-agent pilot used, showing invariant reuse."""

    def __init__(self, grant: IAMGrant, role: ApprovedRole):
        self.grant = grant
        self.role = role

    def evidence(self) -> Tuple[GovernanceEvidence, ...]:
        g, r = self.grant, self.role
        payload = {
            "available": g.granted_permissions,
            "permitted": r.permitted_permissions,
            "prohibited": r.prohibited_permissions,
            "revoked": g.revoked_permissions,
            "approval_required": r.approval_required_permissions,
            "approvals_present": r.approvals_present,
        }
        return (
            _ev(C.IDENTITY_AUTHORITY, "IAM", f"principal:{g.principal}",
                {"role": r.role}, verify=V.VERIFIED, authority=AR.SUPPORTING),
            _ev(C.CAPABILITY_SPACE, "IAM", f"capabilities:{g.principal}", payload,
                verify=V.VERIFIED, authority=AR.SUPPORTING),
        )
