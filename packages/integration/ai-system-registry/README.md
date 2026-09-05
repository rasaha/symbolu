# ugence-ai-system-registry

**Contracts only. Not enforcement-ready, and not an operational registry.** The
inventory of registered AI systems: a bounded registration record over the neutral
system identity governance-contracts already owns. Scoped and ratified by
`docs/architecture/ADR_UGENCE_AI_SYSTEM_REGISTRY_SCOPING.md`; sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 2) and ruled
contracts-only by its decision D-5 (line 40) — the operational registry and its
systems-of-record connectors stay post-v1.

> This package records what an administrator asserted. It **never** admits,
> registers into a system of record, promotes, approves, gates, resolves or attests.
> A registration is a record, not a permission.

## What "contracts only" means here

Record types, refusal reasons, pure selectors, and one read-only Protocol. **No
store, no adapter, no connector, no admission engine, no clock.** D-5's post-v1 line
is held *structurally* rather than by discipline: there is nothing in the
distribution that could reach a system of record, so "the operational registry stays
post-v1" is not a promise this package could break. A boundary test asserts it —
no module named `store`, `adapter`, `connector` or `client`, and no `connect`,
`session`, `url`, `endpoint`, `cmdb`, `scim` or `ldap` anywhere in the code.

The shape follows BR-2A/BR-2B, which shipped registry contracts and then a kernel
explicitly unable to "admit, register, revoke or resolve"
(`packages/benchmark-registry-authority/README.md:49-50`).

## The identity is borrowed, never minted

`AssessedSystemBinding` is **re-exported from governance-contracts**, never
redefined — the direction that module fixes itself: engines bind the same system
identity "rather than minting a parallel one. Consumers re-export it; they never
redefine it"
(`packages/governance-contracts/src/ugence_governance_contracts/contracts/system_identity.py:17-18`).
A test asserts the exported symbol *is* the same class object, and that no class
here is named `AssessedSystemBinding` or anything ending in `SystemBinding`.

**And the ceiling comes with it.** A binding proves internal consistency and
digest-bound identity only — never that the named system was deployed, that its
configuration digest was computed over the real configuration, or that a manifest
reference resolves (`system_identity.py:36-45`). `authenticity_status` is
permanently `STRUCTURAL_UNVERIFIED`, and `SystemRegistration` exposes it so no
consumer has to reach past the record to discover that nothing here is attested.

## The registration

`SystemRegistration(registration_id, binding, owner_ref, classification_label,
validity, supersedes, registered_by, notes)`.

- **`owner_ref`** is a non-secret directory handle. Never a credential, never an
  authenticated identity, and never proof that anyone accepted the role.
- **`classification_label`** is the label an administrator declared, and it is
  **uninterpreted** (D-2). The package knows no taxonomy, no ordering and no
  severity, so `select_by_classification` matches exactly and can neither widen nor
  narrow a query by reasoning about what a label means. A blank label is refused; an
  unrecognized one is not, because there is no recognized set. There is no
  `severity`, `risk_level`, `tier` or `is_high_risk` anywhere on the record.
- **`registration_id`** is derived from the binding's own canonical digest, the
  owner and the window — no UUID, no clock — and the record **verifies** it at
  construction, so an id is never chosen by a caller. That is what makes the
  collision-freedom real: a different configuration, version, owner or window is a
  different id, so a collection keyed by id can never silently lose a registration.

## The window

Every registration is bounded by a
`ugence_governance_contracts.contracts.validity.Validity`, evaluated with
`status_at(as_of)` at a caller-supplied, timezone-aware instant. **A registration
outside its window is absent from every answer** — not returned with a flag — so a
lapsed registration cannot be argued around downstream. **No clock is read
anywhere** (no `time.time()`, no `datetime.now`, no `uuid4`), asserted over the AST
of every source file.

## Supersession

A registration binds **exactly one** `AssessedSystemBinding` (D-3). A new system
version is registered **afresh**, carrying `supersedes`; the prior record is never
edited. `supersession_refusals()` is pure and refuses a supersession that names no
predecessor, crosses a tenant, or rebinds the *same* identity — an unchanged system
has nothing to supersede.

`supersession_chain()` walks that history newest-first and is deliberately **not**
filtered by instant, because a superseded registration is normally outside its
window and the chain exists to reconstruct what was registered when. It walks
**only admissible links**: a `supersedes` pointing at a record the rule above
rejects — a different tenant, or the same identity — ends the chain there rather
than splicing an unrelated registration into a history. A cycle terminates rather
than looping.

## The read seam

`SystemRegistryPort` is a read-only Protocol with four methods —
`get_registration`, `registrations_for_tenant`, `registrations_for_system`,
`registrations_by_classification`. **No implementation ships in 0.1.0** (D-4): a
Protocol is a seam, not an adapter, and declaring it lets a composition root type
against a stable surface while the operational slice stays post-v1. There is no
write method, by construction, and a test pins the whole surface.

The pure selectors — `registered_at`, `select_for_tenant`, `select_for_system`,
`select_by_classification` — answer over a collection the caller holds. They filter
to in-force registrations first, always.

## What it is not

- **Not a portfolio ledger.** It holds no scheduling metadata, no budget, no
  priority or fairness state. `WorkflowPortfolio` in `packages/runtime/agent-runtime`
  remains the only one, and RA-7 keeps reading it rather than duplicating it
  (`docs/architecture/ADR_RISK_AUTHORITY_RA7_RUNTIME_TRAJECTORY_ASSURANCE.md:99`).
  A test forbids `portfolio`, `priority`, `fairness`, `quantum`, `budget` and
  `schedul` from appearing in the code at all.
- **Not a second system identity.** See above.
- **Not a lifecycle authority.** The promotion state machine is wave 4
  (`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md:61`).
- **Not a resolver.** It answers no "is this system allowed" question, because it
  ships nothing that can answer anything.

## Dependencies

`ugence-governance-contracts>=0.4.0` and the Python standard library. Nothing else —
no agent-runtime, no Decision Authority, no Risk Authority, no Policy Authority, no
approval workflow, no authority directory, no Model Selection, no Benchmark
Registry, no `sqlite3`, no network client, no cloud SDK, no pydantic. Composition
roots, products and applications may import it; no capability package may.

## Gaps that survive this release

- Nothing here proves organizational truth, deployment, or that a registered system
  is the running one.
- No systems-of-record connector, no discovery, no reconciliation against a CMDB or
  an HR system — all post-v1 under D-5.
- No store, so nothing persists; a composition root holds whatever it registers.
- The classification vocabulary is unratified, so the label stays uninterpreted
  until an owner fixes a taxonomy.
- The repository still has no test enforcing "no capability package may import it";
  that gap is shared with both other wave 2 packages.
