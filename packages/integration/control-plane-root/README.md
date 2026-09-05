# Ugence Control Plane Root

**The audit-ledger service — and nothing else.** Distribution
`ugence-control-plane-root` · namespace `ugence_control_plane_root` · version
**0.1.0** · maturity **reference-grade**.

> Append one entry, at one caller-supplied instant, into one tenant's chain.
> Return the `AuditReference` naming it. This package decides nothing, owns no
> policy, issues no envelope, brokers no credential, and **unifies no existing
> audit store**.

Scoped and ratified by `docs/architecture/ADR_UGENCE_CONTROL_PLANE_ROOT_SCOPING.md`.

## What this is, and what it deliberately is not

This is a **composition root**, not a capability (D-2). It wires packages that
already exist and adds nothing to the platform's capability count.

It is **not the AI Control Plane**. That noun names a product with its own
documentation tree (`Project_documentation/control_plane/`) and a shipped console
(`ugence_console_api/`, classified `CANONICAL_IMPLEMENTATION`). This is a root
*under* that product, never the thing itself — and three shipped packages
(`governance-provider-framework`, `decision-authority`, `model-selection`) each
disclaim the noun as belonging elsewhere.

## Why the ledger, and not another shared service

Roadmap §3 names six shared services. The ledger is the only one that is **both
unowned and composable from `packages/`**:

| §3 service | Why not this root |
|---|---|
| Identity & tenancy | The IdP owns it, outside this repository |
| Policy service | `packages/policy-authority` — "there is exactly **one** Policy Authority in Ugence; this is it" |
| Canonical contract layer | `packages/governance-contracts` already is it |
| **Evidence & audit** | **Nobody owns it** — seven stores, none of them the service |
| Console | Already built, outside `packages/`, and already *the* AI Control Plane console |
| Connector framework | Split between `products/code-governance` and the cloud-scaling ladder |

## It unifies nothing

Seven audit stores already exist — the kernel's `AuditRepository` port, storygraph's
durable log, and append-only tables in policy-authority, risk_authority,
execution-reservation, approval-workflow and authority-directory. This is an
**eighth**, deliberately. No existing store is read, migrated, mirrored or changed;
G4's `AuditReference` remains the only thing that correlates across them, exactly as
that contract says of itself: *"This contract does not unify them."*

A root that absorbed the seven would be performing the migration G4 refused.

## The seam: injected, never imported

`AuditReference` arrives as a **callable argument**, not an import:

```python
from ugence_governance_contracts.api import AuditReference   # the caller's import
reference = ledger.append(entry, reference_factory=AuditReference)
```

The package declares **no runtime dependency at all** — standard library only — and
`tests/test_boundaries.py` asserts it names `ugence_governance_contracts` nowhere. A
root one import from the contract layer is one import from a capability.

## Durability

SQLite, WAL, per-tenant hash-linked, schema-versioned — the shape of
`packages/capabilities/storygraph/src/ugence_storygraph/durable_audit.py`, **copied
and never imported**, as decision D-3 of the sequencing ADR already ruled for Policy
Authority's registry.

`UPDATE` and `DELETE` are refused by database triggers, not by convention, and
`verify_chain()` recomputes a tenant's chain from its rows. The chain is
**tamper-evident**: it detects modification. It is **not tamper-proof**, and this
package never says otherwise. A store written at another schema version is refused
rather than migrated — silently migrating somebody's audit store is the one thing an
append-only ledger must never do.

Appends run under `BEGIN IMMEDIATE`, so the read of a chain head and the write that
extends it are one transaction and two concurrent appends cannot fork a tenant.

## No clock, no vocabulary

Every instant is a caller input — an entry is recorded *at* an instant somebody
observed, never at the instant the row happened to be written. Asserted over the AST.

The `kind` is a free string the caller chooses. This package ships **no event-type
vocabulary**: Decision Authority's `AuditEventType` is frozen at 1.0.0 and owns those
names, and a neutral second catalog here would fork them.

## Coverage

`python3 scripts/mutation_sweep.py` disables each refusal in `src/` in turn and
reports the ones no test catches. It ships rather than being described, so the
coverage claim can be run instead of believed.

## Gaps stated up front

- Reference-grade, composing reference-grade parts (D-1). **Not production-ready.**
- No console, no connector, no reconstruction API — the rest of roadmap §3 is that
  product's scope, not a root's.
- Nothing here observes or notifies. The ledger records what a caller already decided
  to record, and says nothing about whether it is true or whether the writer was
  entitled to write it — the same limit `AuditReference` states about itself.
