"""RI-3 — production ``MATCHED`` requires verified independent-observer provenance.

An executing-provider attestation proves which provider reported an effect. It
may support ``MISMATCH``, ``CONFLICTED``, ``PARTIAL``, ``UNKNOWN`` or
``MANUAL_REVIEW`` — adverse evidence is never suppressed — but provider-only
evidence must never make the positive production verdict ``MATCHED`` reachable. A
production ``MATCHED`` needs at least one admitted observation whose typed
provenance names the distinct ``INDEPENDENT_OBSERVER`` role **and** whose own
observed outcome is favorable and final. The role is read from the typed
:class:`~.contracts.EffectAttestationProvenance`, never from a string field.

The gate applies only when the composition's ``production_mode`` is exactly
``True``; the reference-grade path is unchanged. Under RI-4 no production
resolver exists in this repository, so the positive branch is exercisable only
against a labelled test double, and nothing here claims a production ``MATCHED``
flow exists.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from ugence_decision_authority.execution.status import BusinessOutcome, Finality
from ugence_risk_authority_effect_attestation import EffectAttesterRole

from .contracts import (
    EffectAttestationProvenance,
    EffectObservation,
    EffectReasonCode,
    EffectReconciliationOutcome,
)

__all__ = [
    "independent_observer_supports",
    "production_matched_gate",
    "INDEPENDENT_OBSERVER_REQUIRED_REASON",
]

INDEPENDENT_OBSERVER_REQUIRED_REASON = (
    "MATCHED withheld in production: no admitted observation carries verified "
    "independent-observer provenance with a favorable final outcome; provider "
    "self-attestation is provenance only (RI-3)"
)


def independent_observer_supports(observations: Sequence[EffectObservation]) -> bool:
    """True iff some admitted observation is observer-attested, favorable and final."""

    for obs in observations:
        if type(obs) is not EffectObservation:
            continue
        provenance = obs.provenance
        if type(provenance) is not EffectAttestationProvenance:
            continue
        if provenance.attester_role is not EffectAttesterRole.INDEPENDENT_OBSERVER:
            continue
        if obs.business_outcome is BusinessOutcome.SUCCEEDED and obs.finality is Finality.FINAL:
            return True
    return False


def production_matched_gate(
    outcome: EffectReconciliationOutcome,
    admitted: Sequence[EffectObservation],
    *,
    production_mode: object,
) -> Optional[Tuple[EffectReconciliationOutcome, EffectReasonCode, str]]:
    """Return the replacement verdict when a production ``MATCHED`` lacks observer support.

    ``None`` means the aggregate verdict stands. Only ``MATCHED`` is ever replaced,
    and only under ``production_mode is True``; every other verdict passes through
    so a provider-reported failure still surfaces.
    """

    if production_mode is not True:
        return None
    if outcome is not EffectReconciliationOutcome.MATCHED:
        return None
    if independent_observer_supports(admitted):
        return None
    return (
        EffectReconciliationOutcome.UNVERIFIABLE,
        EffectReasonCode.INDEPENDENT_OBSERVER_REQUIRED,
        INDEPENDENT_OBSERVER_REQUIRED_REASON,
    )
