# ugence-data-use-admission

**Contracts only. Not enforcement-ready, and not an admission engine.** The record
of declared data use at the admission seam: a bounded declaration over the neutral
system identity and the neutral data-classification label governance-contracts
already owns. Scoped and ratified by
`docs/architecture/ADR_UGENCE_DATA_EGRESS_AUTHORITY_SCOPING.md` (DE-1 to DE-5);
sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 4, line 60).

> This package records what a declarer asserted about data. It **never** inspects,
> classifies, redacts, minimizes, persists, admits, authorizes, selects, enforces
> or governs egress. A declaration is a record, not a permission.

## What "contracts only" means here

Record types, refusal reasons, pure selectors, and one read-only Protocol. **No
store, no adapter, no connector, no proxy, no redactor, no clock.** The lines the
rulings draw are held *structurally* rather than by discipline: there is nothing in
the distribution that could reach data, a context, a model or a network, so "it
does not admit" is not a promise this package could break. A boundary test asserts
it — no module named `store`, `adapter`, `connector`, `client`, `proxy` or
`redact`, and no `connect`, `session`, `url`, `endpoint`, `socket`, `payload`,
`admit`, `authorize`, `redact`, `minimize` or `egress` anywhere in the code.

The shape follows `packages/integration/ai-system-registry` (wave 2), which shipped
a contracts-only record over the same borrowed identity.

## The seam it fills, and the three rulings that bound it

Context Minimization says of itself that it "does **not** decide whether information
was permitted to enter the context (that is *admission*, which happens upstream)"
(`packages/capabilities/context-minimization/README.md:13-14`). This package is the
record a caller would make at that seam. It records; it does not decide.

- **DE-1 `ADMISSION_ONLY`.** A declaration describes data *before* it enters a
  governed context. **Result egress** — anything after model output — remains
  explicitly deferred and has no field, function or word here.
- **DE-2 `STAY_SPLIT`.** ActionGate keeps `allowed_region` as an action constraint
  (`packages/providers/actiongate/src/ugence_actiongate_provider/mapping/constraints.py:18`);
  Model Selection keeps residency compatibility as model eligibility
  (`packages/capabilities/model-selection/src/ugence_model_selection/gate.py:139-145`).
  This package imports neither, reinterprets neither and replaces neither. It may
  record a declared `residency_label`; it **cannot evaluate or enforce residency** —
  a recorded residency value is metadata, never a verdict.
- **DE-3 `UNINTERPRETED`.** The classification label is a non-empty opaque value.
  No enum, taxonomy, lattice, hierarchy, severity, ordering, dominance or implied
  compatibility. `select_by_classification` matches exactly and can neither widen
  nor narrow a query by reasoning about what a label means.

## The identity and the vocabulary are borrowed, never minted

`AssessedSystemBinding` and `DataClassificationLabel` are **re-exported from
governance-contracts**, never redefined — the direction that package fixes itself
(`contracts/system_identity.py:17-18`), and the reason DE-5 landed the label there
first. A test asserts each exported symbol *is* the same class object, and that no
class here is named `…SystemBinding` or `…Label`.

**And the ceilings come with them.** A binding proves internal consistency and
digest-bound identity only (`system_identity.py:36-45`); `authenticity_status` is
permanently `STRUCTURAL_UNVERIFIED`, and `DataUseDeclaration` exposes it so no
consumer has to reach past the record to discover that nothing here is attested. A
label is what the declarer *called* the data, never what that means.

## The declaration

`DataUseDeclaration(declaration_id, tenant_id, binding, data_ref, classification,
purpose_label, validity, residency_label, supersedes, declared_by, correlation_id,
notes)`.

- **`tenant_id`** must agree with the binding's tenant. A mismatch is **refused** at
  construction, never resolved either way; a declaration never crosses tenants.
- **`data_ref`** is an opaque, non-secret reference to the data or its subject in
  the caller's own spelling. Never the data: there is no field that could carry a
  payload, and a test pins the field set.
- **`classification`** and **`purpose_label`** are what the declarer said, and they
  are **uninterpreted** (DE-3). A blank label is refused; an unrecognized one is not,
  because there is no recognized set.
- **`residency_label`** is recorded and never evaluated (DE-2).
- **`declaration_id`** is derived from the binding's digest, the data reference, the
  label's digest, the purpose and the window — no UUID, no clock — and the record
  **verifies** it at construction, so an id is never chosen by a caller. That is
  what makes the collision-freedom real: a different system, data, label, purpose
  or window is a different id, so a collection keyed by id can never silently lose
  a declaration.

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
names no predecessor, crosses a tenant, concerns **different data** (that is a new
declaration, not a replacement), or **changes nothing** — an unchanged declaration
has nothing to supersede.

`supersession_chain()` walks that history newest-first and is deliberately **not**
filtered by instant. It walks **only admissible links**: a `supersedes` pointing at a
record the rule above rejects ends the chain there rather than splicing an unrelated
declaration into a history. A cycle terminates rather than looping.

## The read seam

`DataUseDeclarationPort` is a read-only Protocol with five methods —
`get_declaration`, `declarations_for_tenant`, `declarations_for_data`,
`declarations_for_system`, `declarations_by_classification`. **No implementation
ships in 0.1.0**: a Protocol is a seam, not an adapter. There is no write method,
by construction, and a test pins the whole surface.

The pure selectors — `declared_at`, `select_for_tenant`, `select_for_data`,
`select_for_system`, `select_by_classification`, `select_by_purpose` — answer over a
collection the caller holds. They filter to in-force declarations first, always, and
never return another tenant's declaration.

## What it is not

- **Not an admission engine.** It answers no "may this data enter" question,
  because it ships nothing that can answer anything.
- **Not a classifier, redactor or minimizer.** Context Minimization stays the only
  thing that reduces a context, and it stays downstream.
- **Not a residency authority.** See DE-2; both existing evaluations stand.
- **Not an egress governor.** See DE-1; nothing after model output is in scope.
- **Not a second system identity or a second label type.** See above.
- **Not an `…Authority`** (DE-4). It decides nothing.

## Dependencies

`ugence-governance-contracts>=0.6.0` and the Python standard library. Nothing else —
no context-minimization, no ActionGate, no Model Selection, no Decision Authority,
no Risk Authority, no Policy Authority, no agent-runtime, no `sqlite3`, no network
client, no cloud SDK, no pydantic. Composition roots, products and applications may
import it; no capability package may — enforced repository-wide by
`scripts/check_package_import_boundaries.py` and
`tests/boundaries/test_package_import_boundaries.py`.

## Gaps that survive this release

- Nothing here proves that the referenced data exists, that the declared label is
  apt, or that the named system is the one that will use the data.
- No store, so nothing persists; a composition root holds whatever it declares.
- No admission engine: the seam at `context-minimization/README.md:14` now has a
  record type, not a decision. Whether a context may be assembled is still nobody's
  answer.
- The classification and purpose vocabularies are unratified, so both labels stay
  uninterpreted until an owner fixes a taxonomy.
- Result egress and residency consolidation stay out of scope until a further
  ruling.
- A dynamic `importlib.import_module(name)` cannot be caught by any static checker;
  that seam remains a reviewer's judgement.
