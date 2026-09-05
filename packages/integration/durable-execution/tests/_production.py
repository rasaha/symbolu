"""The production governance hook, wired for the matrix re-run.

The matrix was first proven with ``AllowAllGovernanceHook`` — an explicitly unsafe test
helper that CLEARs everything — because the rows are about *durability*, and a hook that
always clears isolates the durable-execution behaviour from governance behaviour.

Re-running the same rows against the real hook answers the other half: that the
durability properties survive when clearance is genuinely composed and can genuinely be
withheld. Note what changes and what does not. A row like "duplicate delivery executes
once" must hold identically. A row like "clearance expires during a retry" now has its
expiry produced by a real envelope's ``expires_at`` flowing through composition, rather
than injected — stronger evidence, since it also proves the hook projects expiry onto the
runtime's wall-clock base correctly.

Every hook here records its evaluations to Postgres on its own connection, so the crash
rows can compare what was proposed before a SIGKILL with what is proposed after recovery
in a different process.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import sqlalchemy as sa

from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_risk_authority_runtime.contracts import (
    GovernanceRestrictions,
    GovernanceVetoResult,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
    VetoDisposition,
)

from ugence_agent_runtime_governance import CompositionInputs, GovernedExecutionHook

from _hooks import EVAL_LOG_DDL

ENVELOPE_ID = "rae_matrix_0001"


class _Scope:
    """The RA scope the restriction algebra reads. Deliberately minimal — this module
    supplies composition *inputs*, and never any composition behaviour."""

    purposes = ("matrix",)
    tools_allow = frozenset({"recorder"})
    tools_deny = frozenset()
    data_allow = frozenset({"d"})
    data_deny = frozenset()
    destinations = frozenset({"dest"})
    jurisdictions = frozenset({"eu"})
    max_autonomy_level = 2
    max_amount_minor_units = 10_000
    required_approvals = frozenset()


class MatrixInputSource:
    """Produces composition inputs for the matrix workflow.

    A deployment's real source would resolve an envelope, key ring and canonical action.
    This one supplies the three per-source results directly, which is the same boundary:
    the hook still composes them through the ratified engine and still cannot decide
    anything itself.
    """

    def __init__(
        self,
        *,
        ra_disposition: RiskAuthorityDisposition = RiskAuthorityDisposition.ALLOW,
        da: VetoDisposition = VetoDisposition.NO_VETO,
        ag: VetoDisposition = VetoDisposition.NO_VETO,
        expires_at: Optional[datetime] = None,
        required_approvals: frozenset = frozenset(),
        envelope: Any = None,
        tier: Any = None,
    ) -> None:
        self._ra_disposition = ra_disposition
        self._da = da
        self._ag = ag
        self._expires_at = expires_at
        self._required_approvals = required_approvals
        self._envelope = envelope
        self._tier = tier

    def inputs_for(self, proposal: TransitionProposal) -> CompositionInputs:
        expires = self._expires_at or (
            datetime.now(timezone.utc) + timedelta(hours=1)
        )
        ra = RiskAuthorityMachineResult(
            disposition=self._ra_disposition,
            reason_codes=("RA_ALLOW",)
            if self._ra_disposition is RiskAuthorityDisposition.ALLOW
            else ("RA_DENY",),
            envelope_id=ENVELOPE_ID,
            action_digest=proposal.fingerprint[:16],
            scope=_Scope(),
            expires_at=expires,
            source_version="matrix",
        )
        return CompositionInputs(
            risk_authority=ra,
            decision_authority=GovernanceVetoResult(
                source="decision_authority",
                disposition=self._da,
                reason_codes=(f"DA_{self._da.value}",),
                restrictions=GovernanceRestrictions(
                    required_approvals=self._required_approvals
                ),
                source_version="matrix",
            ),
            actiongate=GovernanceVetoResult(
                source="actiongate",
                disposition=self._ag,
                reason_codes=(f"AG_{self._ag.value}",),
                source_version="matrix",
            ),
            action=None,
            envelope=self._envelope,
            tier=self._tier,
        )


class RecordingProductionHook:
    """The real ``GovernedExecutionHook``, with evaluations recorded durably.

    Delegates every decision to the production hook; the only thing added is the
    Postgres write the crash rows read back. It never inspects or alters the result.
    """

    def __init__(self, url: str, source: MatrixInputSource, *, process_tag: str = "p1") -> None:
        self._engine = sa.create_engine(url)
        self._hook = GovernedExecutionHook(source=source)
        self._tag = process_tag
        with self._engine.begin() as c:
            c.execute(sa.text(EVAL_LOG_DDL))

    def evaluate(self, proposal: TransitionProposal, evaluation_time: float):
        result = self._hook.evaluate(proposal, evaluation_time)
        with self._engine.begin() as c:
            c.execute(
                sa.text(
                    "INSERT INTO governance_evaluations "
                    "(instance_id, task_id, fingerprint, disposition, process_tag) "
                    "VALUES (:i, :t, :f, :d, :p)"
                ),
                {
                    "i": proposal.instance_id,
                    "t": proposal.task_id,
                    "f": proposal.fingerprint,
                    "d": result.disposition.value,
                    "p": self._tag,
                },
            )
        return result

    # The recheck resolver keys off the underlying hook's record.
    def envelope_for(self, proposal: TransitionProposal):
        return self._hook.envelope_for(proposal)


def clearing_hook(url: str, **kwargs: Any) -> RecordingProductionHook:
    """A hook whose composition genuinely GRANTs."""
    return RecordingProductionHook(url, MatrixInputSource(**kwargs))


def expiring_hook(url: str, *, seconds_ago: float = 1.0) -> RecordingProductionHook:
    """GRANTs, but with an envelope expiry already in the past.

    The expiry travels the real path: envelope ``expires_at`` -> effective constraints ->
    the hook's epoch-seconds projection -> ``validate_clearance``. Nothing is injected.
    """
    return RecordingProductionHook(
        url,
        MatrixInputSource(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
        ),
    )


def escalating_hook(url: str) -> RecordingProductionHook:
    """A composed HOLD carrying a required approval, which the hook projects to ESCALATE."""
    return RecordingProductionHook(
        url,
        MatrixInputSource(
            da=VetoDisposition.HOLD, required_approvals=frozenset({"reviewer-1"})
        ),
    )


def denying_hook(url: str) -> RecordingProductionHook:
    """Risk Authority DENY — absorbing, nothing downstream upgrades it."""
    return RecordingProductionHook(
        url, MatrixInputSource(ra_disposition=RiskAuthorityDisposition.DENY)
    )
