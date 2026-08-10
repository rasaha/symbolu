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


class TapControlAssurance:
    """A ``ControlAssurancePort`` backed by a real assertion-governance provider."""

    def __init__(
        self,
        provider: AssertionGovernanceProvider,
        *,
        control_assertions: Optional[Mapping[str, str]] = None,
        engine_id: str = "tap-control-assurance",
        engine_version: str = "1",
    ) -> None:
        self._provider = provider
        self._control_assertions = dict(control_assertions or {})
        self._engine_id = engine_id
        self._engine_version = engine_version

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

        result = bind_control_result(
            request,
            status=status,
            engine_id=self._engine_id,
            engine_version=self._engine_version,
            reason=(
                f"tap outcome={provider_result.coverage.value} "
                f"coverage={provider_result.evidence_coverage}"
            ),
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
