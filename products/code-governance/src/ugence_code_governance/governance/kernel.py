"""Decision Authority + CER kernel adapter.

This adapter wires the **existing** Decision Authority public services and drives
them to (a) record a binding ``DecisionRecord`` under an explicit authorized
actor, and (b) bind a canonical ``ContextEnvelopeRecord`` (``cer.v1``) that
references that decision. It reuses `DecisionRecord` and `ContextEnvelopeRecord`
verbatim — the product introduces no `MergeDecisionRecord` or
`CodeGovernanceDecisionRecord`, and no `cer.v2`.

The Workflow Service owns no authority; it calls this adapter only when an
explicit authorized actor is supplied. Without one, decision recording fails
closed (:class:`DecisionAuthorityRequiredError`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

# Decision Authority — public API surface only.
from ugence_decision_authority.api.audit import AuditService, InMemoryAuditRepository  # type: ignore
from ugence_decision_authority.api.contracts import (  # type: ignore
    ActionMapping,
    AuthorityContext,
    AuthorityType,
    ContextEnvelopeRecord,
    DecisionOutcome,
    DecisionRecord,
    ParameterSchema,
)
from ugence_decision_authority.api.identity import StaticIdentityProvider  # type: ignore
from ugence_decision_authority.api.policy import (  # type: ignore
    AccessGrant,
    EvidenceAccessPolicy,
    GrantStore,
    Permission,
)
from ugence_decision_authority.api.ports import FINALIZED_STATUS, LinkedRecordSnapshot  # type: ignore
from ugence_decision_authority.api.repositories import (  # type: ignore
    InMemoryActionRequestRepository,
    InMemoryDecisionCaseRepository,
)
from ugence_decision_authority.api.services import (  # type: ignore
    ActionRequestService,
    ActionRequestValidationService,
    CaseDecisionService,
    CaseValidationService,
    CERBindingService,
    DecisionCaseService,
)
from ugence_decision_authority.api.vocabulary import ReasonCode  # type: ignore

from ..errors import DecisionAuthorityRequiredError
from ..fingerprints import domain_hash
from ..models.change_identity import GovernedChangeIdentity

_ASSESSMENT = "assessment"

# Product decision outcome -> Decision Authority neutral outcome.
_OUTCOME_MAP = {
    "APPROVE": DecisionOutcome.ADVANCE,
    "ADVANCE": DecisionOutcome.ADVANCE,
    "DENY": DecisionOutcome.REJECT,
    "REJECT": DecisionOutcome.REJECT,
    "HOLD": DecisionOutcome.HOLD,
    "DEFER": DecisionOutcome.DEFER,
    "ESCALATE": DecisionOutcome.DEFER,
}

_AUTHORITY_MAP = {
    "HUMAN_REVIEWER": AuthorityType.HUMAN_REVIEWER,
    "HUMAN_APPROVER": AuthorityType.HUMAN_APPROVER,
    "DELEGATED_POLICY": AuthorityType.DELEGATED_POLICY,
    "COMMITTEE": AuthorityType.COMMITTEE,
    "EXTERNAL_AUTHORITY": AuthorityType.EXTERNAL_AUTHORITY,
}


@dataclass(frozen=True)
class AuthorizedActor:
    """An explicit authorized actor supplied to the decision-recording stage."""

    actor_id: str
    authority_id: str
    decision_scope: str
    authority_type: str = "HUMAN_APPROVER"


@dataclass(frozen=True)
class DecisionInput:
    """The caller-supplied decision the authorized actor is recording."""

    outcome: str
    reason_codes: Tuple[str, ...] = ()


class _LinkedRegistry:
    """Product-side finalized linked-record registry backing DA validation."""

    def __init__(self) -> None:
        self._records: dict = {}

    def register(self, *, tenant_id: str, record_id: str, version: int, subject_ref: str) -> None:
        self._records[(tenant_id, _ASSESSMENT, record_id, version)] = LinkedRecordSnapshot(
            record_type=_ASSESSMENT, record_id=record_id, version=version,
            tenant_id=tenant_id, status=FINALIZED_STATUS, subject_ref=subject_ref,
        )

    def get_record(self, *, tenant_id, record_type, record_id, version=None):
        if version is None:
            cands = [k for k in self._records if k[:3] == (tenant_id, record_type, record_id)]
            return self._records[sorted(cands)[-1]] if cands else None
        return self._records.get((tenant_id, record_type, record_id, version))


class DecisionCerKernel:
    """Wires the real Decision Authority services for the product (in-memory)."""

    def __init__(self) -> None:
        self._idp = StaticIdentityProvider()
        self._grants = GrantStore()
        self._policy = EvidenceAccessPolicy(self._grants)
        self._audit = AuditService(InMemoryAuditRepository())
        self._case_repo = InMemoryDecisionCaseRepository()
        self._action_repo = InMemoryActionRequestRepository()
        self._linked = _LinkedRegistry()
        self._validation = CaseValidationService(self._linked)
        self._cases = DecisionCaseService(
            self._case_repo, self._validation, self._audit, self._idp, self._policy)
        self._decisions = CaseDecisionService(
            self._case_repo, self._validation, self._audit, self._idp, self._policy)
        self._actions = ActionRequestService(
            self._action_repo, self._case_repo,
            ActionRequestValidationService(self._action_repo, self._case_repo),
            self._audit, self._idp, self._policy)
        self._cer = CERBindingService(
            self._action_repo, self._case_repo, self._audit, self._idp, self._policy)
        self._registered: set = set()

    # --- actor provisioning ---------------------------------------------
    def _ensure_actor(self, actor: AuthorizedActor, tenant_id: str) -> None:
        key = (actor.actor_id, tenant_id)
        if key in self._registered:
            return
        if actor.actor_id not in {a[0] for a in self._registered}:
            try:
                self._idp.register_human(actor.actor_id)
            except Exception:  # already registered in a prior tenant scope
                pass
        self._grants.add(AccessGrant(
            actor.actor_id, tenant_id, frozenset({
                Permission.CREATE_DECISION_CASE,
                Permission.LINK_ASSESSMENT,
                Permission.MAKE_DECISION,
                Permission.MANAGE_ACTION_MAPPING,
                Permission.CREATE_ACTION_REQUEST,
                Permission.VALIDATE_ACTION_REQUEST,
                Permission.BIND_CER,
            })))
        self._registered.add(key)

    @staticmethod
    def _subject(change: GovernedChangeIdentity) -> str:
        return f"{change.repository}#{change.pull_request_number}"

    @staticmethod
    def _reason_codes(codes: Tuple[str, ...]) -> Tuple[ReasonCode, ...]:
        mapped = []
        for c in codes:
            try:
                mapped.append(ReasonCode[c])
            except KeyError:
                continue
        return tuple(mapped) or (ReasonCode.NOT_APPLICABLE,)

    # --- decision recording ---------------------------------------------
    def record_authorized_decision(
        self,
        change: GovernedChangeIdentity,
        *,
        actor: Optional[AuthorizedActor],
        decision: DecisionInput,
        policy_refs: Tuple = (),
    ) -> DecisionRecord:
        """Record a binding ``DecisionRecord`` under an explicit authorized actor.

        Fails closed if no authorized actor is supplied — the Workflow Service
        cannot mint a binding decision on its own.
        """
        if actor is None:
            raise DecisionAuthorityRequiredError(
                "record_authorized_decision requires an explicit authorized actor"
            )
        tenant = change.tenant_id
        self._ensure_actor(actor, tenant)
        subject = self._subject(change)
        assessment_id = domain_hash("cg_assessment.v1", {"change": change.fingerprint})[:24]

        case = self._cases.create_case(
            tenant_id=tenant, decision_type="merge_pull_request",
            subject_ids=(subject,), created_by=actor.actor_id)
        self._linked.register(
            tenant_id=tenant, record_id=assessment_id, version=1, subject_ref=subject)
        self._cases.link_assessment(
            case_id=case.decision_case_id, assessment_id=assessment_id,
            version=1, actor=actor.actor_id)

        outcome = _OUTCOME_MAP.get(decision.outcome.upper())
        if outcome is None:
            raise DecisionAuthorityRequiredError(
                f"unknown decision outcome: {decision.outcome!r}")
        authority = AuthorityContext(
            authority_id=actor.authority_id,
            authority_type=_AUTHORITY_MAP.get(actor.authority_type, AuthorityType.HUMAN_APPROVER),
            decision_scope=actor.decision_scope or "merge_pull_request")
        return self._decisions.record_decision(
            case_id=case.decision_case_id,
            outcome=outcome,
            authority=authority,
            decided_by=actor.actor_id,
            reason_codes=self._reason_codes(decision.reason_codes),
            policy_refs=tuple(policy_refs),
        )

    # --- CER binding -----------------------------------------------------
    def bind_context_envelope(
        self,
        change: GovernedChangeIdentity,
        decision: DecisionRecord,
        *,
        actor: AuthorizedActor,
        requested_parameters: Mapping[str, str],
    ) -> ContextEnvelopeRecord:
        """Bind a canonical ``cer.v1`` CER referencing ``decision``.

        Exact SHA/merge values ride in the action request's ``requested_parameters``
        (and the product prepared-action envelope); the CER names which parameter
        keys are permitted and binds decision/tenant/policy/expiry + content hash.
        """
        tenant = change.tenant_id
        self._ensure_actor(actor, tenant)
        params = {str(k): str(v) for k, v in requested_parameters.items()}
        mapping_id = domain_hash("cg_action_mapping.v1", {"change": change.fingerprint})[:24]
        self._actions.publish_action_mapping(
            ActionMapping(
                mapping_id=mapping_id, version=1, domain_id="code-governance",
                decision_type="merge_pull_request", decision_outcome=DecisionOutcome.ADVANCE,
                permitted_action_type="merge_pull_request", target_system_type="github",
                parameter_schema=ParameterSchema(required_fields=tuple(sorted(params.keys())))),
            actor=actor.actor_id, tenant_id=tenant)
        req = self._actions.create_action_request(
            decision_id=decision.decision_id, mapping_id=mapping_id,
            target_system="github", created_by=actor.actor_id,
            requested_parameters=params)
        self._actions.validate_action_request(
            request_id=req.action_request_id, actor=actor.actor_id)
        return self._cer.bind_cer(request_id=req.action_request_id, actor=actor.actor_id)


__all__ = ["AuthorizedActor", "DecisionInput", "DecisionCerKernel"]
