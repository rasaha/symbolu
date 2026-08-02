"""Claim requirements and non-compensatory mandatory-gate evaluation.

A required claim that is missing, stale, failed, conflicting, unsupported, or
inadmissible **must not** be compensated for by high aggregate coverage, many
successful optional claims, a high confidence score, or passing tests in another
category. This module encodes that rule structurally: the mandatory verdict is
computed only from mandatory claims and never inspects optional coverage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Tuple

from ..models.enums import ClaimStatus, ClaimType, ValidatorTrustLevel
from .manifest import ClaimManifest

#: Statuses that satisfy a mandatory claim. NOT_APPLICABLE satisfies because the
#: claim does not apply to this change; every other status blocks.
_SATISFYING = frozenset({ClaimStatus.SATISFIED, ClaimStatus.NOT_APPLICABLE})


@dataclass(frozen=True)
class ClaimRequirement:
    """A policy requirement for a claim family at a given risk tier."""

    claim_type: ClaimType
    mandatory: bool


@dataclass(frozen=True)
class ClaimEvaluation:
    """The non-compensatory verdict over a manifest against its requirements."""

    mandatory_claims_complete: bool
    mandatory_claims_satisfied: bool
    missing_required_claims: Tuple[ClaimType, ...]
    failed_required_claims: Tuple[ClaimType, ...]
    stale_required_claims: Tuple[ClaimType, ...]
    conflicting_required_claims: Tuple[ClaimType, ...]
    unsupported_required_claims: Tuple[ClaimType, ...]
    inadmissible_required_claims: Tuple[ClaimType, ...]
    incomplete_required_claims: Tuple[ClaimType, ...]
    optional_claim_summary: Mapping[str, int]

    @property
    def proceed(self) -> bool:
        """True only when every mandatory claim is present AND satisfied.

        This is the fail-closed gate. It can never be flipped by optional
        claims or by any aggregate coverage score.
        """
        return self.mandatory_claims_complete and self.mandatory_claims_satisfied


def evaluate_claim_requirements(
    manifest: ClaimManifest,
    requirements: Tuple[ClaimRequirement, ...],
) -> ClaimEvaluation:
    """Evaluate ``manifest`` against ``requirements`` (non-compensatory)."""
    missing: list[ClaimType] = []
    failed: list[ClaimType] = []
    stale: list[ClaimType] = []
    conflicting: list[ClaimType] = []
    unsupported: list[ClaimType] = []
    inadmissible: list[ClaimType] = []
    incomplete: list[ClaimType] = []

    for req in requirements:
        if not req.mandatory:
            continue
        entry = manifest.entry_for(req.claim_type)
        if entry is None:
            missing.append(req.claim_type)
            continue
        # Evidence bound to an old head cannot satisfy the current head.
        if not entry.is_current_for(manifest.head_sha):
            stale.append(req.claim_type)
            continue
        # An untrusted validator makes a mandatory claim inadmissible.
        if entry.validator_trust_level is ValidatorTrustLevel.UNTRUSTED:
            inadmissible.append(req.claim_type)
            continue
        status = entry.status
        if status is ClaimStatus.FAILED:
            failed.append(req.claim_type)
        elif status is ClaimStatus.STALE:
            stale.append(req.claim_type)
        elif status is ClaimStatus.CONFLICTING:
            conflicting.append(req.claim_type)
        elif status is ClaimStatus.UNSUPPORTED:
            unsupported.append(req.claim_type)
        elif status is ClaimStatus.INCOMPLETE:
            incomplete.append(req.claim_type)
        elif status not in _SATISFYING:  # defensive
            incomplete.append(req.claim_type)

    # Completeness: every mandatory claim present and not incomplete/missing.
    mandatory_present_ok = not missing and not incomplete
    # Satisfaction: no mandatory claim in any blocking bucket.
    blocking = missing + failed + stale + conflicting + unsupported + inadmissible + incomplete
    mandatory_satisfied = not blocking

    # Optional summary is purely descriptive — it never affects the gate.
    optional_summary: Dict[str, int] = {}
    for entry in manifest.optional_entries():
        key = entry.status.value
        optional_summary[key] = optional_summary.get(key, 0) + 1

    return ClaimEvaluation(
        mandatory_claims_complete=mandatory_present_ok,
        mandatory_claims_satisfied=mandatory_satisfied,
        missing_required_claims=tuple(missing),
        failed_required_claims=tuple(failed),
        stale_required_claims=tuple(stale),
        conflicting_required_claims=tuple(conflicting),
        unsupported_required_claims=tuple(unsupported),
        inadmissible_required_claims=tuple(inadmissible),
        incomplete_required_claims=tuple(incomplete),
        optional_claim_summary=optional_summary,
    )


__all__ = ["ClaimRequirement", "ClaimEvaluation", "evaluate_claim_requirements"]
