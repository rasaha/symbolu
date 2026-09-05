# ugence-vendor-dependency

**Contracts only. Not enforcement-ready, and not a vendor-risk engine.** The record
of declared vendor dependencies: a bounded declaration over the neutral system
identity and the neutral vendor-risk label governance-contracts already owns,
linked to a policy by reference. Scoped and ratified by
`docs/architecture/ADR_UGENCE_VENDOR_RISK_SCOPING.md` (VR-1 to VR-5); sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 4, line 62).

> This package records what a declarer asserted about a vendor dependency. It
> **never** resolves, verifies, scores, grades, contacts, persists or decides.
> A declaration is a record, not a permission.

## What "contracts only" means here

Record types, refusal reasons, pure selectors, and one read-only Protocol. **No
store, no connector, no gateway, no scorer, no questionnaire, no clock.** The lines
the rulings draw are held *structurally* rather than by discipline: there is
nothing in the distribution that could reach a vendor, a policy, a store or a
network, so "it does not evaluate" is not a promise this package could break. A
boundary test asserts it — no module named `store`, `adapter`, `connector`,
`client`, `gateway`, `scorer` or `engine`, and no `connect`, `session`, `url`,
`endpoint`, `socket`, `resolve`, `verify`, `fetch`, `score`, `grade`, `severity`,
`eligible` or `approve` anywhere in the code.

The shape follows `packages/integration/data-use-admission` (wave 4), which
follows `packages/integration/ai-system-registry` (wave 2).

## The five rulings, and what each forbids here

- **VR-1.** The package records vendor dependencies. It is not a **gateway** — Risk
  Authority's "Third-Party Gateway" is a connector milestone
  (`packages/risk_authority/README.md:32`) — not a **supplier** system — that noun
  is procurement's purchase counterparty (`packages/products/procurement/README.md:3`)
  — not a registry, and not an authority.
- **VR-2 `BINDING_ONLY`.** Each declaration binds directly to exactly one canonical
  `AssessedSystemBinding`. The package does not import AI System Registry, and a
  registry registration is neither required nor accepted as an alternative
  identity: a look-alike binding is refused at construction.
- **VR-3 `SEPARATE_OPAQUE_RISK_LABEL`.** The posture is a `VendorRiskLabel`, a
  different dimension from `DataClassificationLabel` and never interchangeable with
  it. It is uninterpreted: no grade, enum, taxonomy, ordering, severity, score,
  dominance or implied eligibility. `select_by_risk_posture` matches exactly and
  can neither widen nor narrow a query by reasoning about what a posture means.
- **VR-4 `POLICY_REF_STRING`.** One non-empty opaque `policy_ref`, in the shape of
  `policy_refs` on the neutral action request. The package does not resolve,
  verify, interpret or fetch it, and does not import Policy Authority — which
  declares itself the only one (`packages/policy-authority/README.md:5`).
- **VR-5.** `VendorRiskLabel` landed in governance-contracts first, so every engine
  carries the same type. `vendor_ref` stays an opaque package-local string.

## The identity and the vocabulary are borrowed, never minted

`AssessedSystemBinding` and `VendorRiskLabel` are **re-exported from
governance-contracts**, never redefined — the direction that package fixes itself
(`contracts/system_identity.py:17-18`). A test asserts each exported symbol *is* the
same class object, and that no class here is named `…SystemBinding` or `…Label`.

**And the ceilings come with them.** A binding proves internal consistency and
digest-bound identity only (`system_identity.py:36-45`); `authenticity_status` is
permanently `STRUCTURAL_UNVERIFIED`, and the declaration exposes it so no consumer
has to reach past the record to discover that nothing here is attested. A label is
the posture a declarer *assigned*, never a measure of risk.

## The declaration

`VendorDependencyDeclaration(declaration_id, tenant_id, binding, vendor_ref,
risk_posture, policy_ref, validity, supersedes, declared_by, correlation_id, notes)`.

- **`tenant_id`** must agree with the binding's tenant. A mismatch is **refused** at
  construction, never resolved either way; a declaration never crosses tenants.
- **`vendor_ref`** is an opaque, non-secret reference to the vendor in the caller's
  own spelling. Never an address, credential or endpoint: nothing here can reach it.
- **`risk_posture`** is what the declarer assigned, and it is **uninterpreted**
  (VR-3). A blank label is refused upstream; an unrecognized one is not, because
  there is no recognized set.
- **`policy_ref`** is recorded and compared as text, and never resolved (VR-4).
- **`declaration_id`** is derived from the binding's digest, the vendor reference,
  the label's digest, the policy reference and the window — no UUID, no clock — and
  the record **verifies** it at construction, so an id is never chosen by a caller.
  A different system, vendor, posture, policy or window is a different id, so a
  collection keyed by id can never silently lose a declaration.

## The window

Every declaration is bounded by a
`ugence_governance_contracts.contracts.validity.Validity`, evaluated with
`status_at(as_of)` at a caller-supplied, timezone-aware instant. **A declaration
outside its window is absent from every answer** — not returned with a flag — so a
lapsed declaration cannot be argued around downstream. **No clock is read
anywhere** (no `time.time()`, no `datetime.now`, no `uuid4`), asserted over the AST
of every source file.

## Supersession

A changed declaration is made **afresh**, carrying `supersedes`; the prior record is
never edited. `supersession_refusals()` is pure and refuses a supersession that
names no predecessor, crosses a tenant, concerns a **different vendor** (that is a
new declaration, not a replacement), or **changes nothing**.

`supersession_chain()` walks that history newest-first and is deliberately **not**
filtered by instant. It walks **only admissible links**; a cycle terminates rather
than looping.

## The read seam

`VendorDependencyPort` is a read-only Protocol with five methods —
`get_declaration`, `declarations_for_tenant`, `declarations_for_vendor`,
`declarations_for_system`, `declarations_by_risk_posture`. **No implementation
ships in 0.1.0**: a Protocol is a seam, not an adapter. There is no write method,
by construction, and a test pins the whole surface.

The pure selectors — `declared_at`, `select_for_tenant`, `select_for_vendor`,
`select_for_system`, `select_by_risk_posture`, `select_by_policy_ref` — answer over
a collection the caller holds. They filter to in-force declarations first, always,
and never return another tenant's declaration.

## What it is not

- **Not a vendor-risk engine.** It scores nothing, grades nothing and answers no
  "may we use this vendor" question, because it ships nothing that can answer
  anything.
- **Not a policy resolver.** `policy_ref` is text. Policy Authority stays the only
  thing that issues, resolves or verifies a policy version.
- **Not a gateway, a supplier system or a registry** (VR-1).
- **Not a second system identity or a second label type.** See above.
- **Not an `…Authority`.** It decides nothing.

## Dependencies

`ugence-governance-contracts>=0.7.0` and the Python standard library. Nothing else —
no Policy Authority, no Risk Authority, no AI System Registry, no Decision
Authority, no agent-runtime, no `sqlite3`, no network client, no cloud SDK, no
pydantic. Composition roots, products and applications may import it; no
capability package may — enforced repository-wide by
`scripts/check_package_import_boundaries.py` and
`tests/boundaries/test_package_import_boundaries.py`.

## Maturity ceiling

**Contracts only, with no operational vendor-risk evaluation.** Nothing here proves
that a declared vendor exists, that the assigned posture is apt, that the policy
reference resolves, or that the named system actually depends on the vendor. No
scoring, no grading, no questionnaire, no due-diligence workflow, no contact with
any vendor. `ENFORCEMENT_ENABLED` is `False` and stays so until a further ruling
authorizes an engine.

## Gaps that survive this release

- No store, so nothing persists; a composition root holds whatever it declares.
- The posture vocabulary is unratified, so the label stays uninterpreted until an
  owner fixes a taxonomy.
- A `policy_ref` that names nothing is indistinguishable here from one that names a
  real version; only Policy Authority can tell, and it is never asked.
- A dynamic `importlib.import_module(name)` cannot be caught by any static checker;
  that seam remains a reviewer's judgement.
