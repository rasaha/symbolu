# ugence-workflow-drafts

**Reference-grade. Records only; confers nothing.** The unapproved Workflow IR drafts
a tenant keeps: one record type, its refusal reasons, pure selectors, one read-only
Protocol and the one ruled local store. **Version:** 0.1.0. Ruled by the owner's decision
on Bring Your Workflow phase 3
(`docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §24): phase 3A — save,
retrieve, list and supersede — authorized for immediate implementation; phase 3B —
verified owners, directory grants, submit-for-approval — blocked on AP-3.

> This package keeps what an operator validated, as a `DRAFT`, for one tenant. It
> **never** approves, compiles, publishes, exports, clears, authenticates or executes.
> A draft is a record, not a permission, and a claimed owner is a claim.

## What a draft is

A `WorkflowDraft` says: *this tenant kept this exact, validated Workflow IR document,
under this title, as an unapproved draft, in this lineage.* It records:

| Field | What it is | What it is not |
|---|---|---|
| `workflow`, `workflow_digest` | the **validated, normalized** document in the studio's canonical encoding and its `sha256:` digest — the same digest `validate_workflow` reports and the Bring Your Workflow screen computes in the browser | the uploaded n8n or BPMN file, or the text the operator typed |
| `tenant_id` | the tenant the composing deployment configured | anything a caller named |
| `claimed_owner_ref` | a typed opaque handle, assurance **`PRESENTED_UNPROVEN`** (a constant, not a field) | an authenticated identity; a grant of any read, write, approval or execution authority |
| `registration_ref`, `registration_digest` | a link to an AI-system registration: a reference **plus** the digest of the record it names, both or neither; matched by the studio against the tenant's own registry | anything this package resolves |
| `supersedes` | the draft this one revises; lineage is linear and append-only | an edit |
| `lifecycle` | the constant **`DRAFT`** | a state that could move |

`draft_id` is derived from the tenant, the revision digest and the predecessor
(`draft_id_for`) — no UUID, no clock, never chosen. `record_digest()` covers the whole
record and is re-verified on every read from the store.

## The one ruled local store

`SqliteWorkflowDrafts(path, tenant_id=..., production_mode=...)`: a sqlite file under a
writable volume in the studio's seam-5 posture — no server, no driver, no DSN, no
network. Bound to one tenant at first open and never re-bound; a read or write for
another tenant is a typed refusal, never an empty answer. Its only write is `save`,
which refuses a duplicate derived id and an inadmissible supersession
(`supersession_refusals`: predecessor not recorded, already superseded, or nothing
changed). Records survive restart and are never edited or deleted.

## What is absent from every answer, by construction

No approval, compilation, publication, export, clearance or runtime consumption has a
method, a field or a transition here. The Policy Workflow Compiler's refusal to compile
a `DRAFT` pack is untouched because nothing here is a pack and nothing here imports the
compiler. Nothing here reads a clock, opens a network connection or imports anything
outside the standard library; `tests/test_boundaries.py` asserts each of these over the
source and the AST.

## Maturity

`REFERENCE_GRADE`, `ENFORCEMENT_ENABLED = False` (`version.py`). Suitable for synthetic
and demonstration content until the production identity and data-handling posture is
separately verified.
