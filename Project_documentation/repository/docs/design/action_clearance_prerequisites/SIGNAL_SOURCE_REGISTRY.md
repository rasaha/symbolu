# Signal Source Registry

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Companion to `TRUSTED_SIGNAL_PROVENANCE.md`.

## Does Action Clearance need a source registry?

**Yes — but only as an immutable, read-only projection consumed by the evaluator, not as a store it
owns.** The provenance fail-closed rules in `TRUSTED_SIGNAL_PROVENANCE.md` (unknown source, unapproved
adapter, adapter-version mismatch) require a deterministic answer to "is this `source_id`/`adapter_id`/
`adapter_version` approved to emit this `signal_type` for this tenant, at this trust level?" That answer
comes from a **source-trust projection**.

## Registry fields (the projection the evaluator reads)

| Field | Purpose |
|---|---|
| `source_id` | source instance identity |
| `source_kind` | class of source |
| `adapter_id` | adapter that normalizes this source |
| `approved_versions` | adapter versions permitted to emit (closed set) |
| `allowed_signal_types` | signal types this source may assert |
| `tenant_scope` | tenants this source serves (`*` or an explicit set) |
| `trust_level` | the integrity level this source is certified to (`L1`/`L2`/`L3`) |
| `policy_refs` | the policy/version that admits this source |
| `status` | `ACTIVE` / `SUSPENDED` / `RETIRED` |
| `valid_from` / `valid_until` | activation window of the registry entry |

The evaluator receives an **immutable snapshot** of the relevant rows (content-addressed, versioned) as
part of the clearance policy context. It performs a pure lookup; it never mutates, subscribes to, or
network-fetches the registry.

## Ownership (decision)

| Candidate owner | Verdict |
|---|---|
| Action Clearance package | **rejected** — would make the package an integration-management system, violating the scope discipline in `TRUSTED_SIGNAL_MODEL.md` §Scope |
| Workflow Service | plausible carrier of the *projection*, but not the source of truth |
| Policy configuration | where per-tenant trust levels and freshness limits are declared |
| Integration registry / existing platform registry | **authoritative owner** — the enterprise integration configuration (which adapters exist, which versions are approved) is mutable operational config that already belongs to the platform integration layer |

**Preferred boundary (chosen):** the **integration/platform registry owns** the mutable enterprise
configuration; the **Workflow Service projects** an immutable, versioned source-trust snapshot into the
`ClearancePolicyContext`; the **Action Clearance core consumes** that snapshot read-only. Action
Clearance does **not** own adapter lifecycle, key rotation, or onboarding — it consumes their result.

## Why not own it

Owning a mutable registry would (1) reintroduce nondeterminism (the evaluator's answer would depend on
live registry state, not its inputs), (2) require the core to hold write access and network I/O, and
(3) turn a pure clearance evaluator into an integration console. The projection pattern keeps the
evaluator deterministic and content-addressed while still enforcing source trust.

## Closure

The registry requirement is **CLOSED_BY_FUTURE_ADAPTER_CONTRACT** for the mutable store (owned by the
platform integration layer) and **CLOSED_BY_NEW_PRODUCT_INTERFACE** for the immutable projection the
evaluator consumes. No registry is built in this phase.
