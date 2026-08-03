# Next Phases

This document **describes** the next phase of work. Nothing here is implemented in
the current `ugence-procurement` 0.1.0 distribution, and none of it may be claimed
as shipped. It exists to set direction and to make clear what the current bounded
extraction deliberately deferred.

## Phase: Procurement Canonical Governance Integration and Bounded Shadow-Pilot Readiness

The next phase would evaluate optional TAP and ActionGate composition, define
read-only SAP Ariba / Coupa / ServiceNow-style snapshot adapters, and prepare a
controlled enterprise shadow pilot **without enabling purchase-order writes**.

### 1. Optional TAP and ActionGate composition (evaluate, not adopt)

- The current reference workflow uses **neither** TAP nor ActionGate. `BudgetAuthorityAdapter` implements the kernel `ActionControlPlanePort` directly and is not relabeled as ActionGate.
- The next phase would **evaluate** a behavior-preserving, **optional** ActionGate integration (and TAP where relevant), gated behind an extra, without changing the default deterministic behavior. No such dependency is added today.

### 2. Read-only enterprise snapshot adapters

- Define **read-only-first** snapshot adapters modeled on SAP Ariba / Coupa / ServiceNow shapes, implemented against the kernel's neutral ports (see [INTEGRATION_PORTS.md](INTEGRATION_PORTS.md)).
- These adapters would read supplier/budget records only. **Purchase-order writes stay disabled.** Governance authority remains with the kernel and procurement services — never transferred to a connector.
- Fail-closed semantics must be preserved: unknown/timeout/unavailable connector responses map to neutral non-success outcomes; a connector acknowledgement is still not business completion.

### 3. Controlled enterprise shadow pilot

- Prepare a **bounded, controlled** shadow pilot in which the governed workflow runs alongside an enterprise system in read-only/observe mode, comparing outcomes without acting on the enterprise system.
- This aligns with the current readiness note `READY_FOR_BOUNDED_SHADOW_PILOT_DESIGN`, which is a design-readiness note only — **not** a validation claim.

## Guardrails for the next phase

- No purchase-order writes to any enterprise system.
- No transfer of decision/authorization/approval authority to any connector.
- No change to the hard maturity flags until real evidence exists: `pilot_validated` and `production_certified` stay `False` until a pilot and certification actually occur.
- The forbidden over-claims list in [MATURITY.md](MATURITY.md) continues to apply.
