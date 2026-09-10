"""The draft record — the only thing this package holds.

A :class:`WorkflowDraft` says *this tenant kept this exact, validated Workflow IR
document, under this title, as an unapproved DRAFT, in this lineage*. It says nothing
else, and it can prove nothing the digest inside it cannot.

**What is kept is the validated, normalized document, not the file that was brought.**
The studio validates the document through the composer's adapter before anything
reaches here, and what is recorded is its canonical encoding and the digest of that
encoding — never an uploaded n8n or BPMN export, never text the operator typed.

**The record is a DRAFT and can be nothing else.** ``lifecycle`` is a constant, not a
field: there is no status column, no transition table and no method that could carry
a draft towards approval, compilation, publication, export or a runtime. The Policy
Workflow Compiler's own refusal to compile a ``DRAFT`` pack stands untouched, because
nothing here is a pack and nothing here reaches the compiler.

**Any owner is a claim.** ``claimed_owner_ref`` is a typed opaque handle recorded as
presented, with the constant assurance ``PRESENTED_UNPROVEN``; it confers no read,
write, approval or execution authority, and a proven owner waits for phase 3B behind
AP-3.

**A link to a registration is a reference plus a digest.** The studio resolves the
reference against the deployment's own tenant-bound system registry before recording
it; this package records the pair and resolves nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from ._canon import (
    bounded_text,
    canonical_text,
    digest,
    domain_digest,
    optional_text,
    require_nonempty,
    workflow_digest,
)
from .errors import ContractViolation, DraftSupersessionError
from .version import CLAIMED_OWNER_ASSURANCE, CONTRACT_VERSION, LIFECYCLE

__all__ = [
    "WorkflowDraft", "DRAFT_ID_PREFIX", "LIMITS", "SUPPORTED_WORKFLOW_CONTRACTS",
    "draft_id_for", "revision_digest_of", "build_draft", "draft_record", "draft_from_record",
    "supersession_refusals", "require_admissible_supersession", "revision_digest",
]

DRAFT_ID_PREFIX = "wfd_"

#: The two Workflow IR contract versions a draft may declare — the same two the
#: composer's adapter supports and the Bring Your Workflow gate admits (BW-2). Anything
#: else is refused by name; a version is never inferred from field presence.
SUPPORTED_WORKFLOW_CONTRACTS: Tuple[str, ...] = ("workflow_ir.v1", "workflow_ir.v2")

#: Structural limits on one record. ``workflow_bytes`` is the owner's BW-2 figure over
#: the canonical encoding; the rest bound the record's own text fields so a draft can
#: never become a place to keep something other than a workflow.
LIMITS: Dict[str, int] = {
    "workflow_bytes": 1024 * 1024,
    "title_chars": 200,
    "ref_chars": 512,
    "notes_chars": 2000,
}


def _require_document(document: object) -> Mapping[str, Any]:
    if not isinstance(document, Mapping) or not document:
        raise ContractViolation("workflow must be a non-empty JSON object")
    try:
        text = canonical_text(document)
    except (TypeError, ValueError) as exc:
        raise ContractViolation(f"workflow is not JSON-encodable: {exc}") from exc
    size = len(text.encode("utf-8"))
    if size > LIMITS["workflow_bytes"]:
        raise ContractViolation(
            f"workflow: {size} bytes exceed the limit of {LIMITS['workflow_bytes']}")
    return document


def _require_digest(value: object, name: str) -> str:
    text = require_nonempty(value, name)
    if not text.startswith("sha256:") or len(text) != 71 or any(
            c not in "0123456789abcdef" for c in text[7:]):
        raise ContractViolation(f"{name} must be 'sha256:' followed by 64 lowercase hex characters")
    return text


def revision_digest_of(*, title: str, contract_version: str, workflow_digest_value: str,
                       claimed_owner_ref: str = "", registration_ref: str = "",
                       registration_digest: str = "", notes: str = "") -> str:
    """Digest of everything a revision may change: the document, its declared contract,
    the title, the claimed owner, the registration link and the notes."""

    return digest({
        "title": title, "contract_version": contract_version,
        "workflow_digest": workflow_digest_value, "claimed_owner_ref": claimed_owner_ref,
        "registration_ref": registration_ref, "registration_digest": registration_digest,
        "notes": notes,
    })


def draft_id_for(tenant_id: str, revision: str, supersedes: str = "") -> str:
    """Deterministic draft id: no UUID, no clock.

    Derived from the tenant, the revision digest (:func:`revision_digest_of`) and the
    predecessor, so keeping the same revision twice in the same lineage position is the
    same draft (and refused as a duplicate), while a revision that changes anything, or
    that supersedes a different predecessor, is a new record.
    """

    return DRAFT_ID_PREFIX + domain_digest("draft_id", {
        "tenant_id": require_nonempty(tenant_id, "tenant_id"),
        "revision": require_nonempty(revision, "revision"),
        "supersedes": optional_text(supersedes, "supersedes"),
    })[:32]


@dataclass(frozen=True)
class WorkflowDraft:
    """One kept, unapproved Workflow IR document for one tenant."""

    #: Derived by :func:`draft_id_for`. ``""`` at construction means "derive it"; any
    #: other value is verified against the derivation and refused if it differs.
    draft_id: str
    tenant_id: str
    title: str
    #: Which Workflow IR contract the document declares; one of
    #: :data:`SUPPORTED_WORKFLOW_CONTRACTS`, validated by the studio before recording.
    contract_version: str
    #: The validated, normalized document itself. Recorded as the studio's canonical
    #: encoding; never the uploaded file.
    workflow: Mapping[str, Any]
    #: ``sha256:`` digest of the canonical encoding of ``workflow`` — the studio's
    #: ``computed_digest`` for the same document. Re-verified at construction.
    workflow_digest: str
    #: A typed opaque handle the caller presented. Assurance is always
    #: :data:`CLAIMED_OWNER_ASSURANCE`; it confers nothing.
    claimed_owner_ref: str = ""
    #: An ai-system-registry registration id and its record digest, both or neither.
    #: The studio matches the pair against the tenant's own registry before recording;
    #: this package resolves nothing.
    registration_ref: str = ""
    registration_digest: str = ""
    #: The draft this one revises, or ``""`` for the first of a lineage.
    supersedes: str = ""
    #: The composition that recorded the draft (deployment name and version), never a
    #: caller's claim.
    recorded_by: str = ""
    #: Which validator the studio ran before recording, as ``<distribution>/<version>``.
    validated_by: str = ""
    notes: str = ""
    record_version: str = CONTRACT_VERSION
    _canonical: str = field(default="", init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_nonempty(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "title", bounded_text(self.title, "title", LIMITS["title_chars"], required=True))
        version = require_nonempty(self.contract_version, "contract_version")
        if version not in SUPPORTED_WORKFLOW_CONTRACTS:
            raise ContractViolation(
                f"contract_version {version!r} is not one of {', '.join(SUPPORTED_WORKFLOW_CONTRACTS)}")
        object.__setattr__(self, "contract_version", version)
        document = _require_document(self.workflow)
        object.__setattr__(self, "_canonical", canonical_text(document))
        computed = workflow_digest(document)
        declared = _require_digest(self.workflow_digest, "workflow_digest")
        if declared != computed:
            raise ContractViolation(
                "workflow_digest does not match the canonical encoding of workflow; the "
                "digest is derived from the document and never asserted over it")
        object.__setattr__(self, "claimed_owner_ref",
                           bounded_text(self.claimed_owner_ref, "claimed_owner_ref", LIMITS["ref_chars"], required=False))
        ref = bounded_text(self.registration_ref, "registration_ref", LIMITS["ref_chars"], required=False)
        reg_digest = optional_text(self.registration_digest, "registration_digest")
        if bool(ref) != bool(reg_digest):
            raise ContractViolation(
                "registration_ref and registration_digest travel together: a link is a "
                "reference plus the digest of the record it names, never one alone")
        if reg_digest and (len(reg_digest) != 64
                           or any(c not in "0123456789abcdef" for c in reg_digest)):
            raise ContractViolation("registration_digest must be 64 lowercase hex characters")
        object.__setattr__(self, "registration_ref", ref)
        object.__setattr__(self, "registration_digest", reg_digest)
        supersedes = optional_text(self.supersedes, "supersedes")
        if supersedes and not supersedes.startswith(DRAFT_ID_PREFIX):
            raise ContractViolation(f"supersedes must name a draft id ({DRAFT_ID_PREFIX}…)")
        object.__setattr__(self, "supersedes", supersedes)
        object.__setattr__(self, "recorded_by", bounded_text(self.recorded_by, "recorded_by", LIMITS["ref_chars"], required=False))
        object.__setattr__(self, "validated_by", bounded_text(self.validated_by, "validated_by", LIMITS["ref_chars"], required=False))
        object.__setattr__(self, "notes", bounded_text(self.notes, "notes", LIMITS["notes_chars"], required=False))
        if self.record_version != CONTRACT_VERSION:
            raise ContractViolation(f"record_version must be {CONTRACT_VERSION!r}")
        expected = draft_id_for(self.tenant_id, revision_digest(self), self.supersedes)
        if self.draft_id == "":
            object.__setattr__(self, "draft_id", expected)
        elif self.draft_id != expected:
            raise ContractViolation(
                "draft_id is derived from the tenant, the revision and the predecessor; "
                "it is never chosen")
        if self.supersedes == self.draft_id:
            raise ContractViolation("a draft cannot supersede itself")

    # -- constants every answer carries, as properties so nothing can set them -- #
    @property
    def lifecycle(self) -> str:
        return LIFECYCLE

    @property
    def claimed_owner_assurance(self) -> str:
        return CLAIMED_OWNER_ASSURANCE

    @property
    def workflow_text(self) -> str:
        """The canonical encoding that ``workflow_digest`` was computed over."""

        return self._canonical

    def to_dict(self) -> dict:
        """The draft's own fields, without the document (see :func:`draft_record`)."""

        return {
            "draft_id": self.draft_id,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "contract_version": self.contract_version,
            "workflow_digest": self.workflow_digest,
            "lifecycle": self.lifecycle,
            "claimed_owner_ref": self.claimed_owner_ref,
            "claimed_owner_assurance": self.claimed_owner_assurance,
            "registration_ref": self.registration_ref,
            "registration_digest": self.registration_digest,
            "supersedes": self.supersedes,
            "recorded_by": self.recorded_by,
            "validated_by": self.validated_by,
            "notes": self.notes,
            "record_version": self.record_version,
        }

    def record_digest(self) -> str:
        """SHA-256 over the complete record (fields plus the document's own digest)."""

        return domain_digest("draft_record", draft_record(self))


def build_draft(*, tenant_id: str, title: str, contract_version: str, workflow: Mapping[str, Any],
                claimed_owner_ref: str = "", registration_ref: str = "",
                registration_digest: str = "", supersedes: str = "", recorded_by: str = "",
                validated_by: str = "", notes: str = "") -> WorkflowDraft:
    """Derive the document digest and the id, then construct the record."""

    document = _require_document(workflow)
    document_digest = workflow_digest(document)
    return WorkflowDraft(
        draft_id="",
        tenant_id=tenant_id, title=title, contract_version=contract_version,
        workflow=document, workflow_digest=document_digest,
        claimed_owner_ref=claimed_owner_ref, registration_ref=registration_ref,
        registration_digest=registration_digest, supersedes=supersedes,
        recorded_by=recorded_by, validated_by=validated_by, notes=notes,
    )


def draft_record(draft: WorkflowDraft) -> dict:
    """The complete, reconstructible record: the draft's fields and the document, under
    two keys so neither can be mistaken for the other."""

    if not isinstance(draft, WorkflowDraft):
        raise ContractViolation("draft_record takes a WorkflowDraft")
    return {"draft": draft.to_dict(), "workflow": dict(draft.workflow)}


def draft_from_record(record: Any) -> WorkflowDraft:
    """Rebuild a draft from :func:`draft_record`. The derived id and the document digest
    are re-verified at construction, so a tampered record cannot reconstruct."""

    if not isinstance(record, Mapping) or "draft" not in record or "workflow" not in record:
        raise ContractViolation("a draft record carries 'draft' and 'workflow'")
    fields = record["draft"]
    if not isinstance(fields, Mapping):
        raise ContractViolation("draft must be a mapping")
    if fields.get("lifecycle", LIFECYCLE) != LIFECYCLE:
        raise ContractViolation(
            f"a draft record's lifecycle is {LIFECYCLE!r} and nothing else; "
            f"{fields.get('lifecycle')!r} is not a state this package can hold")
    if fields.get("claimed_owner_assurance", CLAIMED_OWNER_ASSURANCE) != CLAIMED_OWNER_ASSURANCE:
        raise ContractViolation(
            f"a claimed owner's assurance is {CLAIMED_OWNER_ASSURANCE!r} and nothing else")
    try:
        return WorkflowDraft(
            draft_id=fields.get("draft_id", ""), tenant_id=fields.get("tenant_id", ""),
            title=fields.get("title", ""), contract_version=fields.get("contract_version", ""),
            workflow=record["workflow"], workflow_digest=fields.get("workflow_digest", ""),
            claimed_owner_ref=fields.get("claimed_owner_ref", ""),
            registration_ref=fields.get("registration_ref", ""),
            registration_digest=fields.get("registration_digest", ""),
            supersedes=fields.get("supersedes", ""), recorded_by=fields.get("recorded_by", ""),
            validated_by=fields.get("validated_by", ""), notes=fields.get("notes", ""),
            record_version=fields.get("record_version", CONTRACT_VERSION),
        )
    except ContractViolation:
        raise
    except (TypeError, ValueError) as exc:
        raise ContractViolation(f"draft refused: {exc}") from exc


def revision_digest(draft: WorkflowDraft) -> str:
    """What a revision may change. Two drafts with the same revision digest differ in
    nothing an operator chose, so one superseding the other would record no revision."""

    return revision_digest_of(
        title=draft.title, contract_version=draft.contract_version,
        workflow_digest_value=draft.workflow_digest, claimed_owner_ref=draft.claimed_owner_ref,
        registration_ref=draft.registration_ref, registration_digest=draft.registration_digest,
        notes=draft.notes)


def supersession_refusals(successor: WorkflowDraft, predecessor: Optional[WorkflowDraft],
                          predecessor_successor_id: str = "") -> Tuple[str, ...]:
    """Why ``successor`` may not supersede ``predecessor``; empty means admissible.

    Lineage is linear and append-only: a predecessor must be recorded, be the same
    tenant's, not already be superseded, and the successor must change something.
    """

    reasons = []
    if not successor.supersedes:
        return ()
    if predecessor is None:
        reasons.append(f"supersedes names {successor.supersedes!r}, which is not recorded for this tenant")
        return tuple(reasons)
    if predecessor.draft_id != successor.supersedes:
        reasons.append("the predecessor handed is not the one supersedes names")
    if predecessor.tenant_id != successor.tenant_id:
        reasons.append("a draft never supersedes another tenant's draft")
    if predecessor_successor_id:
        reasons.append(
            f"{predecessor.draft_id} is already superseded by {predecessor_successor_id}; "
            "revise the head of the lineage, records are never rewritten")
    if revision_digest(successor) == revision_digest(predecessor):
        reasons.append("the revision changes nothing: the document, title, claimed owner, "
                       "registration link and notes are those of the predecessor")
    return tuple(reasons)


def require_admissible_supersession(successor: WorkflowDraft, predecessor: Optional[WorkflowDraft],
                                    predecessor_successor_id: str = "") -> None:
    reasons = supersession_refusals(successor, predecessor, predecessor_successor_id)
    if reasons:
        raise DraftSupersessionError("; ".join(reasons))
