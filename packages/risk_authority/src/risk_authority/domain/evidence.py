"""Evidence metadata and admission records (spec §9; RA-5 spec §6).

Only *admissible* evidence may back a passing control. This module owns the
typed records; the admission decision itself is a contract (TAP-compatible)
consumed from ``integrations.tap`` and driven by the RA-5 evidence-runtime.

RA-5 (``RISK_AUTHORITY_RA5_SPEC.md`` §6) extends ``ControlEvidenceRecord`` into
the canonical **AdmittedEvidence** contract: the same record, now carrying the
trust-binding tuple (``workflow_ir_digest`` / ``policy_digest``), an explicit
``schema_version``, an ``admitted_at`` stamp, and producer attribution. The
contract is *extended, never forked* — every RA-5 field defaults to an
empty/None value so RA-1→RA-4 reference/conformance construction (and its
97-test suite) is unaffected, while production mode requires the fields to be
populated and integrity-bound (§12).

The record is:

* immutable (frozen dataclass);
* JSON-serializable (via the shared canonical serializer);
* validation-heavy and **fail-closed** on malformed authority-relevant values
  (unknown schema, impossible timestamps, negative freshness window, empty
  required identifiers) — a malformed record cannot be constructed at all, so it
  can never silently back a passing control.

Integrity: :func:`evidence_integrity_digest` is the deterministic content digest
over the record's bound fields (never over the ``digest``/``admission`` fields
themselves). A producer stamps ``digest`` with it; the RA-5 production admitter
recomputes and compares, so tampering with any bound field — or the digest —
fails admission (RA-5 spec §6 "integrity_digest: a mismatch fails admission").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional

from ..crypto.hashing import digest as _content_digest
from .enums import EvidenceState

__all__ = [
    "EvidenceAdmission",
    "ControlEvidenceRecord",
    "EVIDENCE_SCHEMA_VERSION",
    "SUPPORTED_EVIDENCE_SCHEMA_VERSIONS",
    "evidence_integrity_digest",
]

#: Current canonical AdmittedEvidence schema version (RA-5 spec §6).
EVIDENCE_SCHEMA_VERSION = "ra5-evidence-1"
#: Schema versions the admission path accepts; anything else fails closed (§9).
SUPPORTED_EVIDENCE_SCHEMA_VERSIONS = frozenset({EVIDENCE_SCHEMA_VERSION})


@dataclass(frozen=True)
class EvidenceAdmission:
    status: EvidenceState
    reason: str = ""


@dataclass(frozen=True)
class ControlEvidenceRecord:
    """Admissible evidence with provenance, validity and subject binding.

    This is the canonical **AdmittedEvidence** contract (RA-5 spec §6). Existing
    RA-1→RA-4 fields keep their names (``type``/``issuer``/``subject_id``/
    ``created_at``/``digest``); RA-5 spec field names are exposed as read-only
    aliases (``source_type``/``source_identity``/``subject``/``observed_at``/
    ``integrity_digest``) so both vocabularies resolve to one object.
    """

    # --- RA-1→RA-4 fields (unchanged names) --------------------------------
    evidence_id: str
    tenant_id: str
    type: str
    subject_id: str
    issuer: str
    created_at: datetime
    valid_until: Optional[datetime]
    digest: str
    admission: EvidenceAdmission
    provenance: Mapping[str, str] = field(default_factory=dict)

    # --- RA-5 trust-binding additions (default empty for reference mode) ----
    #: Reject unknown/incompatible schema fail-closed (§9).
    schema_version: str = EVIDENCE_SCHEMA_VERSION
    #: Evidence for WorkflowIR X may not satisfy Y (binding, §8).
    workflow_ir_digest: str = ""
    #: Evidence under policy A may not satisfy policy B (binding, §8).
    policy_digest: str = ""
    #: When admission decided (audit + monotonicity).
    admitted_at: Optional[datetime] = None
    #: Attribute the admission decision to its admitter (accountability).
    producer: str = ""
    producer_version: str = ""
    #: Evidence may legitimately back multiple cases in one context; when the
    #: producer scopes it to a case, carry the id (OPTIONAL, §6).
    risk_case_id: Optional[str] = None

    def __post_init__(self) -> None:
        # Fail-closed structural validation. These invariants must hold for ANY
        # well-formed record (reference or production); they never reject the
        # reference defaults, only genuinely malformed authority-relevant values.
        if not self.schema_version:
            raise ValueError("evidence schema_version must be non-empty")
        if self.schema_version not in SUPPORTED_EVIDENCE_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported evidence schema_version {self.schema_version!r} "
                f"(supported: {sorted(SUPPORTED_EVIDENCE_SCHEMA_VERSIONS)})"
            )
        if not self.evidence_id:
            raise ValueError("evidence_id must be a non-empty identifier")
        if not self.tenant_id:
            raise ValueError("tenant_id must be a non-empty identifier")
        _reject_impossible_timestamp("created_at", self.created_at)
        _reject_impossible_timestamp("valid_until", self.valid_until)
        _reject_impossible_timestamp("admitted_at", self.admitted_at)
        # A validity window that closes before the fact was observed is a
        # negative freshness window — impossible, fail closed.
        if self.valid_until is not None and self.valid_until < self.created_at:
            raise ValueError(
                "valid_until precedes created_at (negative freshness window)"
            )
        if self.admitted_at is not None and self.admitted_at < self.created_at:
            raise ValueError("admitted_at precedes created_at (impossible)")

    # --- RA-5 spec field-name aliases (read-only) --------------------------
    @property
    def source_type(self) -> str:
        return self.type

    @property
    def source_identity(self) -> str:
        return self.issuer

    @property
    def subject(self) -> str:
        return self.subject_id

    @property
    def observed_at(self) -> datetime:
        return self.created_at

    @property
    def integrity_digest(self) -> str:
        return self.digest

    @property
    def admission_result(self) -> EvidenceState:
        return self.admission.status

    @property
    def admission_reason(self) -> str:
        return self.admission.reason

    # --- predicates --------------------------------------------------------
    def is_admitted(self) -> bool:
        return self.admission.status is EvidenceState.ADMITTED

    def is_current(self, now: datetime) -> bool:
        return self.valid_until is None or now <= self.valid_until

    def expected_integrity_digest(self) -> str:
        """The digest this record's bound content *should* carry.

        Recomputed from the bound fields only (never from ``digest`` or
        ``admission``). Equality with ``digest`` proves the record was not
        tampered after its producer stamped it (RA-5 spec §6).
        """

        return evidence_integrity_digest(
            evidence_id=self.evidence_id,
            tenant_id=self.tenant_id,
            source_type=self.type,
            source_identity=self.issuer,
            subject=self.subject_id,
            observed_at=self.created_at,
            valid_until=self.valid_until,
            workflow_ir_digest=self.workflow_ir_digest,
            policy_digest=self.policy_digest,
            schema_version=self.schema_version,
            risk_case_id=self.risk_case_id,
            provenance=self.provenance,
        )

    def integrity_ok(self) -> bool:
        """True iff the carried ``digest`` matches the recomputed content digest."""

        return bool(self.digest) and self.digest == self.expected_integrity_digest()


def _reject_impossible_timestamp(name: str, value: Optional[datetime]) -> None:
    if value is None:
        return
    if not isinstance(value, datetime):
        raise ValueError(f"{name} must be a datetime")
    # ``datetime`` cannot represent NaN/inf, but a caller can pass a broken
    # subclass; a round-trip through isoformat catches non-representable values.
    try:
        value.isoformat()
    except Exception as exc:  # noqa: BLE001 - fail closed on any malformed instant
        raise ValueError(f"{name} is not a representable timestamp: {exc}") from exc


def evidence_integrity_digest(
    *,
    evidence_id: str,
    tenant_id: str,
    source_type: str,
    source_identity: str,
    subject: str,
    observed_at: datetime,
    valid_until: Optional[datetime],
    workflow_ir_digest: str,
    policy_digest: str,
    schema_version: str = EVIDENCE_SCHEMA_VERSION,
    risk_case_id: Optional[str] = None,
    provenance: Optional[Mapping[str, str]] = None,
) -> str:
    """Deterministic ``sha256:`` content digest over an evidence record's bound fields.

    The digest binds the identity, provenance, subject, freshness window and the
    workflow/policy context together. It deliberately excludes the ``digest`` and
    ``admission`` fields (those are the *decision*, not the *content*). Producers
    stamp ``ControlEvidenceRecord.digest`` with this value; the RA-5 admitter
    recomputes and compares to detect tampering.
    """

    return _content_digest(
        {
            "schema_version": schema_version,
            "evidence_id": evidence_id,
            "tenant_id": tenant_id,
            "source_type": source_type,
            "source_identity": source_identity,
            "subject": subject,
            "observed_at": observed_at,
            "valid_until": valid_until,
            "workflow_ir_digest": workflow_ir_digest,
            "policy_digest": policy_digest,
            "risk_case_id": risk_case_id,
            "provenance": dict(provenance or {}),
        }
    )
