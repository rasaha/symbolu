# Signal Ownership Matrix

The core **never fetches external state**. For each signal it either *receives*, *validates
structurally*, *evaluates*, *persists a reference*, or *has no ownership*.

| Signal | Authoritative owner | Action Clearance relationship | Receive | Validate | Evaluate | Ref-persist | No ownership |
|---|---|---|---|---|---|---|---|
| Authorization validity | ActionGate / authorization record | consumes projection | ✅ | ✅ | ✅ | ✅ (ref) | |
| Decision validity | Decision Authority (`DecisionRecord`) | references only | ✅ | ✅ | | ✅ (id) | ✅ (does not re-decide) |
| Actor status | identity provider | consumes normalized signal | ✅ | ✅ | ✅ | | ✅ (does not own identity) |
| Policy validity | policy authority | consumes | ✅ | ✅ | ✅ | ✅ (ref) | |
| Active incident | incident system | consumes | ✅ | ✅ | ✅ | | ✅ (no incident client) |
| Change freeze | change-management system | consumes | ✅ | ✅ | ✅ | | ✅ (no change-mgmt client) |
| Artifact identity | product workflow / action mapper | consumes | ✅ | ✅ | ✅ | ✅ (fp) | |
| Required check status | GitHub / evidence adapter | consumes | ✅ | ✅ | ✅ | | ✅ (no CI client) |
| Target availability | execution target adapter | consumes | ✅ | ✅ | ✅ | | ✅ (no target client) |
| Prior consumption | execution / idempotency ledger | consumes | ✅ | ✅ | ✅ | ✅ (ref) | ✅ (does not own ledger) |
| Current time | caller-supplied trusted evaluation time | evaluates | ✅ | ✅ | ✅ | | ✅ (no clock read) |
| Tenant scope | workflow / identity context | validates | ✅ | ✅ | ✅ | | |

## Reading

- Where Action Clearance **evaluates/receives**, the adapter has already fetched the fact and hands the
  core a normalized `TrustedSignal`. The core evaluates a neutral clearance policy over the bundle.
- Where it **references only** (`DecisionRecord`, `cer_id`, prior-consumption receipt), it carries an
  id/hash for reconstructability without owning the record or re-deriving it.
- The gaps the audit flagged (actor identity, incidents, prior-consumption) are all *received* here, not
  *owned*: the design defines receive-contracts for them and forbids building an incident client, an
  identity client, or an idempotency ledger inside the core.

## Anti-pattern to avoid

Do not centralize every pre-execution check into the core. Target-specific validation (a GitHub
merge-tree check, a K8s readiness probe, a DB replication check) lives in the **execution provider /
target adapter**, which surfaces a `TrustedSignal`; the core evaluates the neutral clearance policy over
that signal. This matches the live cloud/console code, which keeps target logic in adapters.
