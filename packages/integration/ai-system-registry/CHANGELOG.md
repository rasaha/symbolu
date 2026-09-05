# Changelog — ugence-ai-system-registry

## 0.1.0 — wave 2, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_AI_SYSTEM_REGISTRY_SCOPING.md`.

- `SystemRegistration`: one `AssessedSystemBinding` re-exported from
  governance-contracts (never redefined), an `owner_ref`, an uninterpreted
  `classification_label` (D-2), a `Validity` window and an optional `supersedes`.
- A derived `registration_id` — no UUID, no clock — bound to the binding's own
  canonical digest, so a different configuration or version can never share one.
- `Validity`-bounded registration evaluated with `status_at(as_of)`: outside its
  window a registration is **absent from every answer**, not flagged. No clock is
  read anywhere, asserted over the AST.
- `supersession_refusals` / `require_admissible_supersession` (D-3): a superseding
  registration must bind a different system identity, in the same tenant, naming its
  predecessor. `supersession_chain` reconstructs history, walks **only admissible
  links**, and terminates on a cycle.
- The derived `registration_id` is **verified at construction**, so a caller can
  never choose one and two registrations can never collide.
- `SystemRegistryPort`, a read-only Protocol with **no implementation** (D-4), and
  the pure selectors `registered_at`, `select_for_tenant`, `select_for_system`,
  `select_by_classification`.
- Contracts only (D-5): no store, adapter, connector or admission engine, asserted
  by boundary tests over module names and code identifiers.
- Not an `…Authority`, not a `…Portfolio`, and no class of its own named
  `…SystemBinding` — all three asserted over the class definitions.
- Neighbours unmodified: governance-contracts, agent-runtime, approval-workflow
  0.1.0, authority-directory 0.1.0.
