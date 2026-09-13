"""Ugence Workflow Drafts — unapproved Workflow IR drafts a tenant keeps.

    THIS PACKAGE KEEPS WHAT AN OPERATOR VALIDATED, AS A DRAFT, FOR ONE TENANT.
    IT NEVER APPROVES, COMPILES, PUBLISHES, EXPORTS, AUTHENTICATES OR EXECUTES.

Owner ruling on Bring Your Workflow phase 3 (``docs/architecture/
ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md`` §24): phase 3A is authorized for immediate
implementation, and this package is its record and its one ruled local store. A draft
records the validated, normalized Workflow IR document and its digest — never the
uploaded file — for the tenant the composing deployment configured, never one a
caller named. Every revision is a new immutable record linked through ``supersedes``.
A claimed owner is recorded with the constant assurance ``PRESENTED_UNPROVEN`` and
confers nothing. A link to an AI-system registration is a reference plus a digest,
matched by the studio against the tenant's own registry and resolved by nobody here.

``lifecycle`` is the constant ``DRAFT``: there is no field, transition or method that
could carry a record towards approval, compilation, publication, export or a runtime,
and the Policy Workflow Compiler's refusal to compile a ``DRAFT`` pack is untouched
because nothing here is a pack. Phase 3B — verified owners, directory grants and
submit-for-approval — waits on AP-3 and is not here.

Stdlib only: no dependency, no clock, no network. ``REFERENCE_GRADE``: suitable for
synthetic and demonstration content until the production data-handling posture is
separately verified.
"""

from __future__ import annotations

from .draft import (
    DRAFT_ID_PREFIX,
    LIMITS,
    SUPPORTED_WORKFLOW_CONTRACTS,
    WorkflowDraft,
    build_draft,
    draft_from_record,
    draft_id_for,
    draft_record,
    require_admissible_supersession,
    revision_digest,
    revision_digest_of,
    supersession_refusals,
)
from ._canon import canonical_text, workflow_digest
from .durable import SCHEMA_VERSION, SqliteWorkflowDrafts
from .errors import (
    ContractViolation,
    CrossTenantRefused,
    DraftProductionModeError,
    DraftStorageError,
    DraftSupersessionError,
    DuplicateDraftError,
    WorkflowDraftsError,
)
from .selectors import WorkflowDraftPort, heads, lineage, select_for_tenant, superseded_by
from .version import (
    CLAIMED_OWNER_ASSURANCE,
    CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    LIFECYCLE,
    MATURITY,
    __version__,
)

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED",
    "LIFECYCLE", "CLAIMED_OWNER_ASSURANCE",
    # the record
    "WorkflowDraft", "DRAFT_ID_PREFIX", "LIMITS", "SUPPORTED_WORKFLOW_CONTRACTS",
    "draft_id_for", "revision_digest_of", "build_draft", "draft_record", "draft_from_record",
    "supersession_refusals", "require_admissible_supersession", "revision_digest",
    # the studio's own canonical encoding and digest of a document
    "canonical_text", "workflow_digest",
    # the one ruled local store and its refusals
    "SqliteWorkflowDrafts", "SCHEMA_VERSION", "DraftStorageError",
    "DraftProductionModeError", "DuplicateDraftError", "CrossTenantRefused",
    # the read seam and its pure selectors
    "WorkflowDraftPort", "heads", "lineage", "select_for_tenant", "superseded_by",
    # errors
    "WorkflowDraftsError", "ContractViolation", "DraftSupersessionError",
]
