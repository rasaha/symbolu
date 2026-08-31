"""TAP Control-Assurance adapter (RA-5 spec §4, §8, §9).

Adapts the **real** ``ugence-tap-provider`` assertion-support evaluator onto Risk
Authority's ``ControlAssurancePort``. It performs no evidence admission (it
consumes already-admitted evidence) and no authorization; it only answers *"does
the admitted evidence satisfy control C?"* and hands back a trusted, bound
:class:`ControlResult`.

    AdmittedEvidence
        │
        ▼
    TAP Control-Assurance adapter  (this module)
        │   build AssertionGovernanceRequest(evidence_refs=admitted ids, …)
        ▼
    ugence-tap-provider .evaluate()  (the real provider API/types)
        │   AssertionGovernanceResult(coverage, evidence_coverage)
        ▼
    explicit fail-closed outcome mapping (§9)
        ▼
    trusted ControlResult (bound to the case context)

Fail-closed (RA-5 §11): unavailable provider, malformed output, unknown outcome,
partial coverage, and missing evidence all resolve to *not PASS* — a genuine
``FAIL`` (evidence contradicts) denies; everything ambiguous is ``UNKNOWN`` and
the evaluator is flagged unavailable so the runtime can classify an infrastructure
failure as ERROR_NON_EXECUTABLE rather than a control DENY. Provider logic is
never duplicated here — the adapter only maps to/from the neutral contract.
"""

from __future__ import annotations

from typing import Mapping, Optional

from ugence_governance_contracts.contracts.assertion import (
    AssertionGovernanceRequest,
    AssertionGovernanceResult,
)
from ugence_governance_provider_framework.contracts import AssertionGovernanceProvider

from risk_authority.domain.enums import ControlStatus
from risk_authority.integrations.control_assurance import (
    ControlAssuranceRequest,
    ControlAssuranceResult,
    bind_control_result,
)

from .outcome_mapping import map_assertion_outcome

__all__ = ["TapControlAssurance"]

#: Marker the fail-safe provider stamps into ``explanation_refs`` when a native
#: infrastructure failure was normalized to INDETERMINATE (see TAP
#: ``indeterminate_result``). Its presence means "evaluator did not really run".
_PROVIDER_ERROR_MARK = "reason:provider_error"

#: Reason code the reference TAP engine stamps into ``explanation_refs`` when a
#: ``SUPPORTED`` outcome is *derived from evidence presence* via its default
#: fallback path — i.e. NO per-assertion rule matched. This is TAP's canonical,
#: un-annotated output (part of its frozen behavioral-equivalence baseline). The
#: *presumptive* judgement is made HERE, in this adapter, not inside the engine,
#: so TAP core stays observably unchanged (RA-5 audit H-1 detection relocated to
#: the integration layer to preserve TAP behavioral equivalence).
_DEFAULT_FALLBACK_MARK = "reason:evidence_supports"

#: Prefix of an ``explanation_refs`` entry naming a covered (supporting) evidence
#: id (e.g. ``supported:e1``); used to locate the evidence a SUPPORTED outcome
#: rested on so an explicit per-evidence stance can be recognized.
_SUPPORTED_PREFIX = "supported:"


class TapControlAssurance:
    """A ``ControlAssurancePort`` backed by a real assertion-governance provider."""

    def __init__(
        self,
        provider: AssertionGovernanceProvider,
        *,
        control_assertions: Optional[Mapping[str, str]] = None,
        engine_id: str = "tap-control-assurance",
        engine_version: str = "1",
        require_explicit_determination: bool = True,
    ) -> None:
        self._provider = provider
        self._control_assertions = dict(control_assertions or {})
        self._engine_id = engine_id
        self._engine_version = engine_version
        # H-1: in production, a PASS requires an *explicit* affirmative
        # determination (an evaluated rule/stance), never support presumed from
        # mere evidence presence. When True, a presumptive SUPPORTED is downgraded
        # to UNKNOWN and this port declares itself production-authoritative.
        self._require_explicit_determination = bool(require_explicit_determination)

    @property
    def is_production_authoritative(self) -> bool:
        """True iff this port refuses presumptive support as PASS (production-safe).

        The RA production composition (``RiskAuthorityApplication`` in production
        mode) rejects a Control-Assurance port that is not production-authoritative
        — a permissive/reference evaluator cannot silently mint PASS (RA-5 H-1).
        """

        return self._require_explicit_determination

    def evaluate(self, request: ControlAssuranceRequest) -> ControlAssuranceResult:
        # No admitted evidence for the control ⇒ MISSING (never PASS), without
        # even consulting the provider (§11: missing mandatory control → DENY).
        if not request.admitted_evidence:
            result = bind_control_result(
                request,
                status=ControlStatus.MISSING,
                engine_id=self._engine_id,
                engine_version=self._engine_version,
                reason="no admitted evidence for control",
            )
            return ControlAssuranceResult(
                control_result=result,
                engine_id=self._engine_id,
                engine_version=self._engine_version,
                available=True,
                detail="missing_evidence",
                raw_outcome="MISSING",
            )

        agr = self._build_request(request)
        try:
            provider_result = self._provider.evaluate(agr)
        except Exception as exc:  # noqa: BLE001 - evaluator error ⇒ UNKNOWN, unavailable
            result = bind_control_result(
                request,
                status=ControlStatus.UNKNOWN,
                engine_id=self._engine_id,
                engine_version=self._engine_version,
                reason=f"provider raised {type(exc).__name__}",
            )
            return ControlAssuranceResult(
                control_result=result,
                engine_id=self._engine_id,
                engine_version=self._engine_version,
                available=False,
                detail=f"provider_error:{type(exc).__name__}",
                raw_outcome="ERROR",
            )

        available = not _looks_like_infrastructure_failure(provider_result)
        status = map_assertion_outcome(
            provider_result.coverage, provider_result.evidence_coverage
        )
        if not available:
            # Infrastructure failure normalized to INDETERMINATE by the fail-safe
            # provider — never a control determination; force UNKNOWN and flag it.
            status = ControlStatus.UNKNOWN

        presumptive = _looks_presumptive(agr, provider_result)
        reason = (
            f"tap outcome={provider_result.coverage.value} "
            f"coverage={provider_result.evidence_coverage}"
        )
        if (
            self._require_explicit_determination
            and status is ControlStatus.PASS
            and presumptive
        ):
            # H-1: support presumed from mere evidence presence (no explicit
            # rule/stance) is NOT an explicit affirmative determination and can
            # never satisfy a mandatory control in production ⇒ UNKNOWN.
            status = ControlStatus.UNKNOWN
            reason = (
                "presumptive support (no explicit determination) downgraded to "
                "UNKNOWN in production (RA-5 audit H-1); " + reason
            )

        result = bind_control_result(
            request,
            status=status,
            engine_id=self._engine_id,
            engine_version=self._engine_version,
            reason=reason,
        )
        return ControlAssuranceResult(
            control_result=result,
            engine_id=self._engine_id,
            engine_version=self._engine_version,
            available=available,
            detail=provider_result.provider_trace_id,
            raw_outcome=provider_result.coverage.value,
        )

    def _build_request(
        self, request: ControlAssuranceRequest
    ) -> AssertionGovernanceRequest:
        assertion = self._control_assertions.get(
            request.control_id, request.control_id
        )
        context: dict[str, str] = {
            "tenant_id": request.tenant_id,
            "risk_case_id": request.risk_case_id,
            "workflow_ir_digest": request.workflow_ir_digest,
            "policy_digest": request.policy_digest,
            "control_id": request.control_id,
        }
        # Carry any caller-provided neutral context (e.g. per-evidence stance a
        # deterministic reference engine reads) without letting it override the
        # binding context above.
        for key, value in request.context.items():
            context.setdefault(str(key), str(value))
        return AssertionGovernanceRequest(
            assertion=assertion,
            assertion_type="control",
            evidence_refs=tuple(e.evidence_id for e in request.admitted_evidence),
            source_identity=request.subject_id,
            policy_refs=(request.policy_digest,) if request.policy_digest else (),
            context=context,
            correlation_id=f"{request.risk_case_id}:{request.control_id}",
        )


def _looks_like_infrastructure_failure(result: AssertionGovernanceResult) -> bool:
    return any(ref.startswith(_PROVIDER_ERROR_MARK) for ref in result.explanation_refs)


def _looks_presumptive(
    agr: AssertionGovernanceRequest, result: AssertionGovernanceResult
) -> bool:
    """True iff a ``SUPPORTED`` outcome is *default-fallback* (presumptive) support.

    Presumptive support is support the engine **derived from mere evidence
    presence** through its default fallback path — no per-assertion rule matched,
    and no explicit per-evidence ``stance:<id>`` determination was supplied by the
    caller. It is NOT an explicit affirmative determination, so in production it can
    never satisfy a mandatory control (RA-5 audit H-1).

    Detection is done entirely from TAP's **canonical, un-annotated** output, so the
    engine's observable behavior stays frozen (TAP behavioral-equivalence
    preserved — the engine no longer stamps any RA-specific marker):

    * the derive/default-fallback path emits ``reason:evidence_supports``; a
      rule-matched ``SUPPORTED`` instead carries the rule's own reason code (or
      ``reason:supported``) and so is treated as an explicit determination and is
      never flagged here;
    * an explicit per-evidence ``stance:<covered_id>`` in the request context is
      itself an explicit determination and lifts the flag — mirroring the reference
      engine's own stance handling. (RA's production pipeline supplies no stance, so
      production default-fallback support is always presumptive.)
    """

    if _DEFAULT_FALLBACK_MARK not in result.explanation_refs:
        return False
    covered_ids = [
        ref[len(_SUPPORTED_PREFIX):]
        for ref in result.explanation_refs
        if ref.startswith(_SUPPORTED_PREFIX)
    ]
    # If any covered (supporting) evidence carried an explicit stance, the support
    # rested on an explicit determination, not mere presence ⇒ not presumptive.
    if any(f"stance:{cid}" in agr.context for cid in covered_ids):
        return False
    return True
