"""Neutral Agent Runtime execution-event adapter (spec §5, §8, §11).

RA-8 derives execution-**attempt** evidence from the Agent Runtime's neutral,
duck-typed event/state contract — it never imports the Agent Runtime package (the
RA-7 pattern; invariant I13). The Agent Runtime owns attempt identity; RA-8 only
*reads* it to join the attempt to the governed correlation.

The reserved AR ``execution_reference`` / ``result_digest`` seam (spec §11) is
**optional**: when populated it is a first-class attempt receipt; when absent
(always ``None`` today) RA-8 falls back to the neutral event's other identity
fields (``instance_id`` / ``correlation_id`` / ``proposal_fingerprint`` /
``provider_id`` / ``idempotency_key`` / ``attempt``). RA-8 fabricates nothing —
absent fields stay absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .contracts import ExecutionCorrelation

__all__ = [
    "RuntimeAttemptEvidence",
    "RuntimeEventAdapter",
]


def _opt_str(value: Any) -> str:
    """Read a duck-typed string field, treating None/blank as absent (never fabricated)."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


@dataclass(frozen=True)
class RuntimeAttemptEvidence:
    """Neutral, read-only execution-attempt evidence derived from an AR event (§3, §11).

    This is **evidence**, not authority: it names what the runtime attempted (which
    provider, which authorized action fingerprint, which attempt), never a grant. It
    is the join input for correlating the governed authority context to the observed
    external effect.
    """

    workflow_instance_id: str
    correlation_id: str
    proposal_fingerprint: str
    provider_id: str = ""
    idempotency_key: str = ""
    attempt: int = 0
    task_id: str = ""
    execution_reference: str = ""
    result_digest: str = ""

    @property
    def attempt_id(self) -> str:
        """A stable attempt id from AR attempt identity (spec §5 ``attempt_id``).

        Prefers the reserved ``execution_reference`` receipt seam when populated;
        otherwise composes the neutral ``idempotency_key``/``attempt`` identity the
        runtime already owns. Never invents an attempt the runtime did not report.
        """

        if self.execution_reference:
            return self.execution_reference
        base = self.idempotency_key or self.correlation_id or self.workflow_instance_id
        return f"{base}#attempt-{self.attempt}"


class RuntimeEventAdapter:
    """Read a neutral, duck-typed Agent Runtime execution event/state (no AR import)."""

    def to_attempt_evidence(self, event: Any) -> RuntimeAttemptEvidence:
        """Duck-type an AR event/state into neutral attempt evidence.

        Accepts any object exposing the neutral AR execution-state field names. A
        malformed ``attempt`` (non-int / bool) is normalized to ``0`` rather than
        trusted (spec §29 malformed-return hardening).
        """

        attempt = getattr(event, "attempt", 0)
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 0:
            attempt = 0
        return RuntimeAttemptEvidence(
            workflow_instance_id=_opt_str(getattr(event, "instance_id", None)),
            correlation_id=_opt_str(getattr(event, "correlation_id", None)),
            proposal_fingerprint=_opt_str(getattr(event, "proposal_fingerprint", None)),
            provider_id=_opt_str(getattr(event, "provider_id", None)),
            idempotency_key=_opt_str(getattr(event, "idempotency_key", None)),
            attempt=attempt,
            task_id=_opt_str(getattr(event, "task_id", None)),
            execution_reference=_opt_str(getattr(event, "execution_reference", None)),
            result_digest=_opt_str(getattr(event, "result_digest", None)),
        )

    def join_mismatches(
        self, correlation: ExecutionCorrelation, evidence: RuntimeAttemptEvidence
    ) -> Tuple[str, ...]:
        """Verify the AR attempt joins to the governed correlation (spec §5 join key).

        The join key is ``correlation_id`` + ``proposal_fingerprint`` (==
        ``authorized_action_digest``). A mismatch means this runtime event is for a
        different governed execution and must not be correlated — fail closed.
        """

        reasons: list[str] = []
        if evidence.correlation_id != correlation.correlation_id:
            reasons.append("wrong correlation_id")
        if evidence.proposal_fingerprint != correlation.authorized_action_digest:
            reasons.append("wrong proposal_fingerprint")
        if (
            evidence.workflow_instance_id
            and evidence.workflow_instance_id != correlation.workflow_instance_id
        ):
            reasons.append("wrong workflow_instance_id")
        return tuple(reasons)
