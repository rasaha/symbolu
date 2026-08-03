"""Accountability report (H6 §12) — human- and machine-readable, redaction-aware.

Assembles the end-to-end governed record for one executed hiring action into a
single report with two renderings:

- :meth:`AccountabilityReport.to_dict` — a stable, machine-readable structure.
- :meth:`AccountabilityReport.render_text` — a plain-text human summary.

The report is **derived read-only** from the platform's own reconstruction
(:class:`~ugence_ai_hiring.services.hiring_action_reconstruction_service.ActionReconstruction`);
it adds no new facts, no scoring, and no conclusions. It surfaces exactly the
chain the platform can already prove: recommendation → TAP claims → human
decision → ActionGate authorization → execution → reconciliation → compensation,
plus audit-chain integrity.

PII discipline: when ``redact`` is on (the product default), candidate subject
references and human/AI actor identifiers are replaced by stable, salted
pseudonyms so a report can be shared for audit without exposing personal or
identity data. Redaction is deterministic (same input → same pseudonym) so
chains remain internally correlatable while de-identified.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Optional

from .version import PRODUCT_VERSION


def _pseudonym(kind: str, value: str) -> str:
    if not value:
        return ""
    digest = hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()[:12]
    return f"{kind}:{digest}"


def _maybe(value, redact: bool, kind: str):
    return _pseudonym(kind, str(value)) if (redact and value) else value


@dataclass(frozen=True)
class AccountabilityReport:
    product_version: str
    tenant_id: str
    action_proposal_id: str
    redacted: bool
    # decision chain
    recommendation: dict = field(default_factory=dict)
    claims: tuple = ()
    human_decision: dict = field(default_factory=dict)
    authorization: dict = field(default_factory=dict)
    execution: dict = field(default_factory=dict)
    reconciliation: dict = field(default_factory=dict)
    compensation: dict = field(default_factory=dict)
    # integrity
    integrity: dict = field(default_factory=dict)
    audit: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def render_text(self) -> str:
        lines: list[str] = []
        a = lines.append
        a(f"ACCOUNTABILITY REPORT  (product {self.product_version})")
        a(f"  tenant: {self.tenant_id}")
        a(f"  action proposal: {self.action_proposal_id}")
        a(f"  redacted: {self.redacted}")
        a("")
        a("Decision chain")
        rec = self.recommendation
        a(f"  1. Recommendation {rec.get('recommendation_id','-')} "
          f"[{rec.get('status','-')}] outcome={rec.get('outcome','-')} "
          f"advisory={rec.get('advisory','-')} confidence={rec.get('confidence','-')}")
        a(f"     material claims: {len(self.claims)} "
          f"(TAP-evaluated via {rec.get('provider_id','-')})")
        for c in self.claims:
            a(f"       - {c.get('claim_id','-')}: {c.get('assertion_outcome','-')} "
              f"(material={c.get('material','-')})")
        d = self.human_decision
        a(f"  2. Human decision {d.get('decision_id','-')} outcome={d.get('outcome','-')} "
          f"authority={d.get('authority_type','-')} by={d.get('decided_by','-')} "
          f"override={d.get('override','-')}")
        au = self.authorization
        a(f"  3. ActionGate authorization {au.get('authorization_id','-')} "
          f"outcome={au.get('outcome','-')} authorized={au.get('authorized','-')} "
          f"constraints={au.get('constraint_count','-')} obligations={au.get('obligation_count','-')}")
        ex = self.execution
        a(f"  4. Execution {ex.get('attempt_id','-')} status={ex.get('execution_status','-')} "
          f"adapter={ex.get('adapter_id','-')} transport_accepted={ex.get('transport_accepted','-')}")
        rc = self.reconciliation
        a(f"  5. Reconciliation outcome={rc.get('outcome','-')} "
          f"matched={rc.get('matched_count','-')} mismatched={rc.get('mismatched_count','-')}")
        cp = self.compensation
        a(f"  6. Compensation entries={cp.get('count',0)}")
        a("")
        a("Integrity")
        i = self.integrity
        a(f"  hiring hash chain valid: {i.get('hiring_hash_chain_valid','-')}")
        a(f"  links intact:            {i.get('links_intact','-')}")
        a(f"  tenant scope consistent: {i.get('tenant_scope_consistent','-')}")
        a(f"  fully reconstructed:     {i.get('reconstructed','-')}")
        if i.get("issues"):
            a("  issues:")
            for issue in i["issues"]:
                a(f"    ! {issue}")
        a("")
        a("Audit")
        a(f"  hiring-domain events:   {self.audit.get('hiring_event_count','-')}")
        a(f"  governance (kernel) events: {self.audit.get('governance_event_count','-')}")
        return "\n".join(lines)


def _val(obj, name, default=None):
    return getattr(obj, name, default)


def build_accountability_report(
    product, action_proposal_id: str, *, redact: Optional[bool] = None
) -> AccountabilityReport:
    """Build the accountability report for one executed action.

    ``product`` is a :class:`~ugence_ai_hiring.product.composition.HiringProduct`. When
    ``redact`` is ``None`` the product's configured ``redact_pii`` is used.
    """
    redact = product.config.redact_pii if redact is None else redact
    rc = product.reconstruct(action_proposal_id)

    rec = rc.recommendation
    rec_d: dict = {}
    if rec is not None:
        rec_d = {
            "recommendation_id": _val(rec, "recommendation_id"),
            "status": getattr(_val(rec, "status"), "value", _val(rec, "status")),
            "outcome": getattr(_val(rec, "outcome"), "value", _val(rec, "outcome")),
            "advisory": _val(rec, "advisory"),
            "confidence": getattr(_val(rec, "confidence"), "value", _val(rec, "confidence")),
            "provider_id": _val(rec, "provider_id"),
            "candidate_subject_ref": _maybe(_val(rec, "candidate_subject_ref"), redact, "subject"),
            "correlation_id": _val(rec, "correlation_id"),
        }

    claims_d = tuple(
        {
            "claim_id": _val(c, "claim_id"),
            "material": _val(c, "material"),
            "assertion_outcome": getattr(_val(c, "assertion_outcome"), "value", _val(c, "assertion_outcome")),
            "review_status": getattr(_val(c, "review_status"), "value", _val(c, "review_status")),
        }
        for c in rc.claims
    )

    d = rc.human_decision
    dec_d: dict = {}
    if d is not None:
        dec_d = {
            "decision_id": _val(d, "decision_id"),
            "outcome": getattr(_val(d, "outcome"), "value", _val(d, "outcome")),
            "authority_type": getattr(_val(d, "authority_type"), "value", _val(d, "authority_type")),
            "decided_by": _maybe(_val(d, "decided_by"), redact, "actor"),
            "override": bool(_val(d, "override_record_id")),
        }

    auths = rc.authorizations
    au = auths[-1] if auths else None
    au_d: dict = {}
    if au is not None:
        au_d = {
            "authorization_id": _val(au, "authorization_id"),
            "outcome": _val(au, "outcome"),
            "authorized": _val(au, "authorized"),
            "constraint_count": len(_val(au, "constraints", ()) or ()),
            "obligation_count": len(_val(au, "obligations", ()) or ()),
            "provider_id": _val(au, "provider_id"),
            "bound_actor": _maybe(_val(au, "bound_actor"), redact, "actor"),
        }

    attempts = rc.attempts
    at = attempts[-1] if attempts else None
    ex_d: dict = {}
    if at is not None:
        ex_d = {
            "attempt_id": _val(at, "attempt_id"),
            "execution_status": _val(at, "execution_status"),
            "adapter_id": _val(at, "adapter_id"),
            "transport_accepted": _val(at, "transport_accepted"),
            "attempt_number": _val(at, "attempt_number"),
        }

    recons = rc.reconciliations
    r = recons[-1] if recons else None
    rc_d: dict = {}
    if r is not None:
        rc_d = {
            "outcome": getattr(_val(r, "outcome"), "value", _val(r, "outcome")),
            "matched_count": len(_val(r, "matched_fields", ()) or ()),
            "mismatched_count": len(_val(r, "mismatched_fields", ()) or ()),
            "compensation_required": _val(r, "compensation_required"),
        }

    comp_d = {"count": len(rc.compensations)}

    integrity = {
        "hiring_hash_chain_valid": rc.hiring_hash_chain_valid,
        "links_intact": rc.links_intact,
        "tenant_scope_consistent": rc.tenant_scope_consistent,
        "reconstructed": rc.reconstructed,
        "issues": list(rc.issues),
    }
    audit = {
        "hiring_event_count": len(rc.hiring_audit_events),
        "governance_event_count": len(rc.governance_audit_events),
    }

    return AccountabilityReport(
        product_version=PRODUCT_VERSION,
        tenant_id=rc.tenant_id,
        action_proposal_id=action_proposal_id,
        redacted=redact,
        recommendation=rec_d,
        claims=claims_d,
        human_decision=dec_d,
        authorization=au_d,
        execution=ex_d,
        reconciliation=rc_d,
        compensation=comp_d,
        integrity=integrity,
        audit=audit,
    )
