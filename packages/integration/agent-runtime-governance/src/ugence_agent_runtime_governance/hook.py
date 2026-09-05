"""The production ``GovernanceHook``: compose, then project.

    THIS HOOK MINTS NOTHING. It composes through the ratified engine and reports.

What it does, in order, for one proposed transition:

1. asks the deployment's :class:`GovernanceInputSource` for the three per-source results;
2. calls ``RiskAuthorityCompositionEngine.compose`` — the ratified composition, unchanged
   and un-reimplemented — to obtain one ``GovernedExecutionDecision``;
3. projects that decision onto a ``GovernanceEvaluation`` via
   :func:`~.dispositions.project_disposition`, binding the result to the exact proposal.

Every step fails closed. An exception anywhere becomes BLOCK, never a permit and never a
raise into the runtime's hot path: the runtime asked a question, and a hook that throws
would make "no answer" indistinguishable from "not asked" at the call site.

**On what a CLEAR carries.** The runtime will only act on a CLEAR that is bound to the
exact proposal fingerprint, carries at least one non-empty governance-produced reference,
and matches the proposal's correlation id. This hook supplies exactly those, and takes
the binding reference from Risk Authority's own ``envelope_id`` — a reference the
authority produced. It never fabricates one. If a GRANT arrives with no envelope id there
is nothing to bind the clearance to, so the hook refuses rather than inventing an
identifier that would make an unbindable permission look bindable.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
)
from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_risk_authority_runtime.composition import RiskAuthorityCompositionEngine

from .dispositions import project_disposition
from .interfaces import CompositionInputs, GovernanceInputSource

__all__ = ["GovernedExecutionHook", "REASON_SOURCE_UNAVAILABLE",
           "REASON_COMPOSITION_FAILED", "REASON_NOT_AUTHORITY_BOUND",
           "REASON_NO_AUTHORIZATION_REFERENCE", "REASON_MALFORMED_INPUTS"]

#: The input source raised, so no authority input exists. Not a denial — a missing
#: input — but never permission either.
REASON_SOURCE_UNAVAILABLE = "GOVERNANCE_INPUT_SOURCE_UNAVAILABLE"
#: The composition engine itself raised.
REASON_COMPOSITION_FAILED = "GOVERNANCE_COMPOSITION_FAILED"
#: The source returned ``None``: this proposal is not authority-bound in this deployment.
REASON_NOT_AUTHORITY_BOUND = "GOVERNANCE_PROPOSAL_NOT_AUTHORITY_BOUND"
#: A GRANT arrived with no envelope id, so there is nothing to bind the clearance to.
REASON_NO_AUTHORIZATION_REFERENCE = "GOVERNANCE_GRANT_WITHOUT_AUTHORIZATION_REFERENCE"
#: The source returned something that is not ``CompositionInputs``.
REASON_MALFORMED_INPUTS = "GOVERNANCE_INPUT_SOURCE_MALFORMED"


def _epoch_seconds(value: Any) -> Optional[float]:
    """Convert an effective-constraints expiry to the runtime's wall-clock base.

    The runtime compares ``valid_until`` against its injected clock, which under a
    durable deployment is epoch seconds (ADR §6.4). A naive datetime is read as UTC
    rather than as local time: guessing the host's zone could move an expiry by hours in
    the permissive direction, and UTC is what Risk Authority issues.

    Anything unconvertible yields ``None`` — no expiry claim — rather than a fabricated
    one. That is the conservative direction here: the clearance is still bound to the
    fingerprint, still requires a reference, and is still re-checked at the last mile.
    """
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    try:
        return value.timestamp()
    except (OverflowError, OSError, ValueError):
        return None


class GovernedExecutionHook:
    """Compose Risk Authority, Decision Authority and ActionGate; report the result.

    Satisfies Agent Runtime's ``GovernanceHook`` protocol structurally. It is safe to
    share across threads: the only mutable state is the envelope record consulted by the
    last-mile recheck, and it is guarded.
    """

    def __init__(
        self,
        *,
        source: GovernanceInputSource,
        engine: Optional[RiskAuthorityCompositionEngine] = None,
        source_version: str = "",
    ) -> None:
        self._source = source
        # The ratified composition engine, used as-is. This package contains no
        # composition logic of its own and must never grow any.
        self._engine = engine or RiskAuthorityCompositionEngine()
        self._source_version = source_version
        self._lock = threading.Lock()
        #: proposal fingerprint -> (envelope, tier), for the last-mile recheck. Recorded
        #: only for a proposal that actually reached composition, so the recheck can
        #: re-verify the same envelope the CLEAR rested on.
        self._envelopes: Dict[str, Tuple[Any, Any]] = {}

    # -- the GovernanceHook protocol ------------------------------------------
    def evaluate(
        self, proposal: TransitionProposal, evaluation_time: float
    ) -> GovernanceEvaluation:
        """Evaluate one proposed transition. Never raises; never widens."""
        try:
            inputs = self._source.inputs_for(proposal)
        except Exception as exc:  # noqa: BLE001 - a failed input is never permission
            return self._refuse(
                proposal,
                REASON_SOURCE_UNAVAILABLE,
                detail={"error": f"{type(exc).__name__}: {exc}"},
            )

        if inputs is None:
            return self._refuse(proposal, REASON_NOT_AUTHORITY_BOUND)
        if not isinstance(inputs, CompositionInputs):
            return self._refuse(
                proposal,
                REASON_MALFORMED_INPUTS,
                detail={"received": type(inputs).__name__},
            )

        try:
            decision = self._engine.compose(
                risk_authority=inputs.risk_authority,
                decision_authority=inputs.decision_authority,
                actiongate=inputs.actiongate,
                action=inputs.action,
                correlation_id=proposal.correlation_id or "",
            )
        except Exception as exc:  # noqa: BLE001 - fail closed on composition failure
            return self._refuse(
                proposal,
                REASON_COMPOSITION_FAILED,
                detail={"error": f"{type(exc).__name__}: {exc}"},
            )

        try:
            disposition, extra = project_disposition(decision)
        except Exception as exc:  # noqa: BLE001 - defence in depth; projection is
            # already total and non-raising, but a hook that threw would make "no
            # answer" indistinguishable from "not asked" at the runtime's call site.
            return self._refuse(
                proposal,
                REASON_COMPOSITION_FAILED,
                detail={"error": f"projection failed: {type(exc).__name__}: {exc}"},
            )
        try:
            reported = tuple(decision.reason_codes or ())
        except Exception:  # noqa: BLE001 - diagnostic only, never load-bearing
            reported = ()
        reason_codes = reported + extra

        if disposition is not GovernanceDisposition.CLEAR:
            return self._evaluation(
                proposal, disposition, reason_codes, decision=decision
            )

        # CLEAR: bind it, or refuse it. The reference must come from the authority.
        envelope_id = self._authorization_reference(decision)
        if not envelope_id:
            return self._refuse(
                proposal,
                REASON_NO_AUTHORIZATION_REFERENCE,
                extra_reasons=reason_codes,
                decision=decision,
            )

        with self._lock:
            self._envelopes[proposal.fingerprint] = (inputs.envelope, inputs.tier)

        return self._evaluation(
            proposal,
            GovernanceDisposition.CLEAR,
            reason_codes,
            decision=decision,
            authorization_reference=envelope_id,
            valid_until=_epoch_seconds(
                getattr(
                    getattr(decision, "effective_constraints", None), "expires_at", None
                )
            ),
        )

    # -- what the last-mile recheck resolves against --------------------------
    def envelope_for(self, proposal: TransitionProposal) -> Optional[Tuple[Any, Any]]:
        """The ``(envelope, tier)`` a CLEAR for this proposal rested on, if any.

        Returns ``None`` for a proposal that never reached a CLEAR — in which case there
        is nothing for the recheck to re-verify, and no provider call to guard.
        """
        with self._lock:
            return self._envelopes.get(getattr(proposal, "fingerprint", ""))

    # -- internals ------------------------------------------------------------
    @staticmethod
    def _authorization_reference(decision: Any) -> str:
        """Risk Authority's own envelope id. Never minted here."""
        try:
            return str(decision.risk_authority_result.envelope_id or "")
        except Exception:  # noqa: BLE001 - an uninspectable decision has no reference
            return ""

    def _evaluation(
        self,
        proposal: TransitionProposal,
        disposition: GovernanceDisposition,
        reason_codes: Tuple[str, ...],
        *,
        decision: Any = None,
        authorization_reference: Optional[str] = None,
        valid_until: Optional[float] = None,
        detail: Optional[dict] = None,
    ) -> GovernanceEvaluation:
        payload = dict(detail or {})
        if decision is not None:
            try:
                payload["governed_decision"] = decision.to_dict()
            except Exception:  # noqa: BLE001 - detail is diagnostic, never load-bearing
                payload["governed_decision"] = "<unserializable>"
        return GovernanceEvaluation(
            disposition=disposition,
            # Bound to the EXACT proposal. The runtime re-checks this before invoking,
            # and re-fingerprints the invocation immediately before the provider call.
            proposal_fingerprint=proposal.fingerprint,
            reason_codes=reason_codes,
            authorization_reference=authorization_reference,
            correlation_reference=proposal.correlation_id,
            valid_until=valid_until,
            required_resolution=self._required_resolution(disposition),
            detail=payload,
        )

    @staticmethod
    def _required_resolution(disposition: GovernanceDisposition) -> Optional[str]:
        if disposition is GovernanceDisposition.HOLD:
            return "GOVERNANCE_HOLD_RELEASE"
        if disposition is GovernanceDisposition.ESCALATE:
            return "EXTERNAL_APPROVAL"
        return None

    def _refuse(
        self,
        proposal: TransitionProposal,
        reason: str,
        *,
        extra_reasons: Tuple[str, ...] = (),
        decision: Any = None,
        detail: Optional[dict] = None,
    ) -> GovernanceEvaluation:
        """BLOCK, with the reason recorded. Deliberately carries no reference: a refusal
        that shipped a binding reference would be a clearance shaped like a denial."""
        return self._evaluation(
            proposal,
            GovernanceDisposition.BLOCK,
            extra_reasons + (reason,),
            decision=decision,
            detail=detail,
        )
