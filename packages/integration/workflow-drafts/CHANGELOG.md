# Changelog — ugence-workflow-drafts

## 0.1.0 — Bring Your Workflow phase 3A: the draft record and its one ruled local store

Owner ruling on Bring Your Workflow phase 3
(`docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §24): phase 3 is split into
3A and 3B, and 3A — save, retrieve, list and supersede unapproved workflow drafts — is
authorized for immediate implementation. This package is its record.

- `WorkflowDraft`, a frozen record of the **validated, normalized** Workflow IR document
  (the studio's canonical encoding) and its `sha256:` digest, for one tenant. The digest
  is the same one the studio's `validate_workflow` operation reports and the Bring Your
  Workflow screen computes in the browser.
- `draft_id_for`: derived from the tenant, the revision (`revision_digest_of`) and the
  predecessor. No UUID, no clock, never chosen by a caller.
- `lifecycle` is the constant `DRAFT`; `claimed_owner_assurance` is the constant
  `PRESENTED_UNPROVEN`. Neither is a field, so neither can be set.
- `registration_ref` + `registration_digest`: a link to an AI-system registration is a
  reference plus a digest, both or neither; recorded here, resolved by the studio
  against the tenant's own registry, never here.
- `supersession_refusals`: linear, append-only lineage — a predecessor must be recorded,
  must not already be superseded, and the revision must change something.
- `SqliteWorkflowDrafts`, the one ruled local store: a file under a writable volume,
  tenant-bound at first open and never re-bound, whose only write is `save`. Every
  stored record's digest is re-verified on read.
- `WorkflowDraftPort`, the read-only seam, with the pure selectors `heads`, `lineage`,
  `select_for_tenant` and `superseded_by`.

Not here, by ruling: approval, compilation, publication, export, clearance, runtime
consumption, authentication of an owner. Phase 3B waits on AP-3.
