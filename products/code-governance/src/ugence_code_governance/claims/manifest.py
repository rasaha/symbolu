"""Product-owned Claim Manifest (merged Change Intelligence design).

A Claim Manifest is a *structured* set of per-claim verdicts — never one blended
quality score. Each claim binds its own evidence references, validator identity
and version, trust level, and lifecycle status, so mandatory gates can stay
non-compensatory.

The manifest fingerprint is **order-independent**: entries are sorted by their
own fingerprints before hashing, so re-ordering claims does not change the
manifest fingerprint, while any change to a governed claim field does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from ..fingerprints import domain_hash
from ..models.enums import ClaimStatus, ClaimType, RiskTier, ValidatorTrustLevel

_ENTRY_DOMAIN = "claim_entry.v1"
_MANIFEST_DOMAIN = "claim_manifest.v1"
_VALIDATOR_DOMAIN = "validator_identity.v1"


@dataclass(frozen=True)
class ValidatorIdentity:
    """Identity + version + trust classification of an evidence-producing validator."""

    validator_id: str
    validator_version: str
    trust_level: ValidatorTrustLevel = ValidatorTrustLevel.UNVERIFIED

    @property
    def fingerprint(self) -> str:
        return domain_hash(
            _VALIDATOR_DOMAIN,
            {
                "validator_id": self.validator_id,
                "validator_version": self.validator_version,
                "trust_level": self.trust_level.value,
            },
        )


@dataclass(frozen=True)
class EvidenceReference:
    """A reference to an immutable evidence record, bound to its head SHA."""

    evidence_id: str
    content_digest: str
    head_sha: str
    validator_id: str
    validator_version: str

    @property
    def fingerprint(self) -> str:
        return domain_hash("evidence_reference.v1", self.__dict__)


@dataclass(frozen=True)
class ClaimEntry:
    """One claim: a required-or-optional assertion with its own admissibility."""

    claim_id: str
    claim_type: ClaimType
    required_by_policy: bool
    status: ClaimStatus
    tenant_id: str
    repository: str
    base_sha: str
    head_sha: str
    captured_at: datetime
    validator_id: str
    validator_version: str
    validator_trust_level: ValidatorTrustLevel
    policy_ref: str
    evidence_refs: Tuple[EvidenceReference, ...] = ()
    valid_until: Optional[datetime] = None

    @property
    def governed_fields(self) -> dict:
        """Fields that define the claim's identity (drive its fingerprint)."""
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type.value,
            "required_by_policy": self.required_by_policy,
            "status": self.status.value,
            "tenant_id": self.tenant_id,
            "repository": self.repository,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "validator_id": self.validator_id,
            "validator_version": self.validator_version,
            "validator_trust_level": self.validator_trust_level.value,
            "policy_ref": self.policy_ref,
            # order of evidence refs is not significant to identity
            "evidence_refs": sorted(r.fingerprint for r in self.evidence_refs),
        }

    @property
    def fingerprint(self) -> str:
        return domain_hash(_ENTRY_DOMAIN, self.governed_fields)

    def is_current_for(self, head_sha: str) -> bool:
        return self.head_sha == head_sha


@dataclass(frozen=True)
class ClaimManifest:
    """The structured manifest of all claims for one governed change revision."""

    manifest_id: str
    tenant_id: str
    repository: str
    pull_request_number: int
    base_sha: str
    head_sha: str
    risk_tier: RiskTier
    policy_ref: str
    captured_at: datetime
    change_fingerprint: str
    entries: Tuple[ClaimEntry, ...] = ()

    @property
    def fingerprint(self) -> str:
        """Order-independent manifest fingerprint."""
        return domain_hash(
            _MANIFEST_DOMAIN,
            {
                "tenant_id": self.tenant_id,
                "repository": self.repository,
                "pull_request_number": self.pull_request_number,
                "base_sha": self.base_sha,
                "head_sha": self.head_sha,
                "risk_tier": self.risk_tier.value,
                "policy_ref": self.policy_ref,
                "change_fingerprint": self.change_fingerprint,
                "entries": sorted(e.fingerprint for e in self.entries),
            },
        )

    def entry_for(self, claim_type: ClaimType) -> Optional[ClaimEntry]:
        for entry in self.entries:
            if entry.claim_type is claim_type:
                return entry
        return None

    def required_entries(self) -> Tuple[ClaimEntry, ...]:
        return tuple(e for e in self.entries if e.required_by_policy)

    def optional_entries(self) -> Tuple[ClaimEntry, ...]:
        return tuple(e for e in self.entries if not e.required_by_policy)


__all__ = [
    "ValidatorIdentity",
    "EvidenceReference",
    "ClaimEntry",
    "ClaimManifest",
]
