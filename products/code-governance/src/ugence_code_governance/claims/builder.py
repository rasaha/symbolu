"""Build a :class:`ClaimManifest` from validator verdicts + evidence records.

The product accepts *normalized external evidence* and the validator's per-claim
verdict; it does not itself detect. The builder binds each claim to its evidence
references (by immutable id + digest + head SHA), stamps validator identity and
version, and marks whether the claim is required by the active policy tier.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from ..evidence.records import EvidenceRecord
from ..fingerprints import domain_hash
from ..models.change_identity import GovernedChangeIdentity
from ..models.enums import ClaimStatus, ClaimType, ValidatorTrustLevel
from ..policies.profiles import RepositoryPolicy
from ..models.enums import RiskTier
from .manifest import ClaimEntry, ClaimManifest, EvidenceReference, ValidatorIdentity


@dataclass(frozen=True)
class ClaimInput:
    """A validator's per-claim verdict plus the evidence backing it."""

    claim_type: ClaimType
    status: ClaimStatus
    evidence: Tuple[EvidenceRecord, ...] = ()
    validator: Optional[ValidatorIdentity] = None
    valid_until: Optional[datetime] = None


def _validator_for(claim: ClaimInput) -> ValidatorIdentity:
    if claim.validator is not None:
        return claim.validator
    if claim.evidence:
        first = claim.evidence[0]
        return ValidatorIdentity(
            validator_id=first.validator_id,
            validator_version=first.validator_version,
            trust_level=first.validator_trust_level,
        )
    return ValidatorIdentity(validator_id="unknown", validator_version="0",
                             trust_level=ValidatorTrustLevel.UNVERIFIED)


def build_claim_manifest(
    *,
    change: GovernedChangeIdentity,
    policy: RepositoryPolicy,
    risk_tier: RiskTier,
    claim_inputs: Tuple[ClaimInput, ...],
    captured_at: datetime,
) -> ClaimManifest:
    """Assemble an immutable Claim Manifest for one governed change revision."""
    mandatory_types = set(policy.mandatory_claim_types(risk_tier))
    entries: list[ClaimEntry] = []
    for claim in claim_inputs:
        validator = _validator_for(claim)
        refs = tuple(
            EvidenceReference(
                evidence_id=ev.evidence_id,
                content_digest=ev.content_digest,
                head_sha=ev.head_sha,
                validator_id=ev.validator_id,
                validator_version=ev.validator_version,
            )
            for ev in claim.evidence
        )
        claim_id = domain_hash(
            "claim_id.v1",
            {"change": change.fingerprint, "claim_type": claim.claim_type.value},
        )
        entries.append(
            ClaimEntry(
                claim_id=claim_id,
                claim_type=claim.claim_type,
                required_by_policy=claim.claim_type in mandatory_types,
                status=claim.status,
                tenant_id=change.tenant_id,
                repository=change.repository,
                base_sha=change.base_sha,
                head_sha=change.head_sha,
                captured_at=captured_at,
                validator_id=validator.validator_id,
                validator_version=validator.validator_version,
                validator_trust_level=validator.trust_level,
                policy_ref=policy.policy_ref,
                evidence_refs=refs,
                valid_until=claim.valid_until,
            )
        )

    manifest_id = domain_hash(
        "claim_manifest_id.v1",
        {"change": change.fingerprint, "policy": policy.policy_ref, "tier": risk_tier.value},
    )
    return ClaimManifest(
        manifest_id=manifest_id,
        tenant_id=change.tenant_id,
        repository=change.repository,
        pull_request_number=change.pull_request_number,
        base_sha=change.base_sha,
        head_sha=change.head_sha,
        risk_tier=risk_tier,
        policy_ref=policy.policy_ref,
        captured_at=captured_at,
        change_fingerprint=change.fingerprint,
        entries=tuple(entries),
    )


__all__ = ["ClaimInput", "build_claim_manifest"]
