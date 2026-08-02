"""Immutable, product-owned evidence records.

An evidence record binds an external validator's output to the *exact head SHA*
it was produced against, with validator identity + version and a deterministic
content digest. Records are content-addressed and immutable; the raw artifact
bytes are never stored inside governance requests (only references/digests).

This is a **narrow** product record, not a generalized evidence platform. The
production durable store is out of scope for MVP 1A (see the persistence module
and the SHADOW_LIMITATIONS doc).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional

from ..errors import ContentDigestMismatchError
from ..fingerprints import content_digest as _content_digest
from ..fingerprints import domain_hash
from ..models.enums import ValidatorTrustLevel

_ID_DOMAIN = "evidence_record.v1"


def _freeze(mapping: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    return dict(mapping or {})


@dataclass(frozen=True)
class EvidenceRecord:
    """One immutable piece of validator evidence bound to a governed head SHA."""

    evidence_id: str
    tenant_id: str
    repository: str
    pull_request_number: int
    base_sha: str
    head_sha: str
    evidence_type: str
    source_id: str
    source_kind: str
    validator_id: str
    validator_version: str
    captured_at: datetime
    content_digest: str
    validator_trust_level: ValidatorTrustLevel = ValidatorTrustLevel.UNVERIFIED
    valid_until: Optional[datetime] = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    normalized_payload: Mapping[str, Any] = field(default_factory=dict)
    payload_ref: Optional[str] = None

    # --- construction ----------------------------------------------------
    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        repository: str,
        pull_request_number: int,
        base_sha: str,
        head_sha: str,
        evidence_type: str,
        source_id: str,
        source_kind: str,
        validator_id: str,
        validator_version: str,
        captured_at: datetime,
        normalized_payload: Optional[Mapping[str, Any]] = None,
        payload_ref: Optional[str] = None,
        validator_trust_level: ValidatorTrustLevel = ValidatorTrustLevel.UNVERIFIED,
        valid_until: Optional[datetime] = None,
        provenance: Optional[Mapping[str, Any]] = None,
        evidence_id: Optional[str] = None,
    ) -> "EvidenceRecord":
        """Build a record, computing the content digest and content-addressed id.

        ``evidence_id`` may be supplied (caller-generated ids are permitted) but
        the content digest is always content-derived, so identity and integrity
        remain deterministic and reproducible.
        """
        payload = _freeze(normalized_payload)
        digest = _content_digest(payload) if payload else _content_digest(
            {"payload_ref": payload_ref or ""}
        )
        identity_fields = {
            "tenant_id": tenant_id,
            "repository": repository,
            "pull_request_number": pull_request_number,
            "head_sha": head_sha,
            "evidence_type": evidence_type,
            "validator_id": validator_id,
            "validator_version": validator_version,
            "content_digest": digest,
        }
        eid = evidence_id or domain_hash(_ID_DOMAIN, identity_fields)
        return cls(
            evidence_id=eid,
            tenant_id=tenant_id,
            repository=repository,
            pull_request_number=pull_request_number,
            base_sha=base_sha,
            head_sha=head_sha,
            evidence_type=evidence_type,
            source_id=source_id,
            source_kind=source_kind,
            validator_id=validator_id,
            validator_version=validator_version,
            captured_at=captured_at,
            content_digest=digest,
            validator_trust_level=validator_trust_level,
            valid_until=valid_until,
            provenance=_freeze(provenance),
            normalized_payload=payload,
            payload_ref=payload_ref,
        )

    # --- integrity / staleness ------------------------------------------
    def verify_integrity(self) -> None:
        """Raise if the declared content digest no longer matches the payload."""
        expected = (
            _content_digest(dict(self.normalized_payload))
            if self.normalized_payload
            else _content_digest({"payload_ref": self.payload_ref or ""})
        )
        if expected != self.content_digest:
            raise ContentDigestMismatchError(
                f"evidence {self.evidence_id}: content digest mismatch"
            )

    def is_current_for(self, head_sha: str, at: Optional[datetime] = None) -> bool:
        """True iff bound to ``head_sha`` and not past ``valid_until`` (at ``at``)."""
        if self.head_sha != head_sha:
            return False
        if self.valid_until is not None and at is not None and at >= self.valid_until:
            return False
        return True

    def is_stale_for(self, head_sha: str, at: Optional[datetime] = None) -> bool:
        """Convenience inverse of :meth:`is_current_for`."""
        return not self.is_current_for(head_sha, at)

    @property
    def reference(self) -> str:
        """The immutable reference string TAP consumes (never raw content)."""
        return self.evidence_id


__all__ = ["EvidenceRecord"]
