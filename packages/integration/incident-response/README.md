# ugence-incident-response

**Records only. Not enforcement-ready, and not an operational incident system.**
Incident records, containment requests and remediation proposals over the neutral
audit reference. Scoped and ratified by
`docs/architecture/ADR_UGENCE_INCIDENT_RESPONSE_SCOPING.md`; sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 3, line 58) — the
wave's only new package.

> This package records and proposes. It **never revokes**, executes, rolls back, or
> lifts its own containment. A recorded incident is an input to somebody else's
> decision, not a decision.

## Deliberately **not an orchestrator**

The sequencing row calls it one. That word is defined here as a service that
"coordinates configured workflows and **does not acquire authority** from the
capabilities it invokes"
(`ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md:61`), and the one
package that took the name reached infrastructure mutation and needed a containment
ADR to pull it back. This package composes no workflow, so it is named for what it
records. A test forbids `Orchestrator` and `…Authority` from appearing in any class
name, and `orchestrat` from appearing in the code at all.

## Every actor that could act already exists

| Who acts | What this package does instead |
|---|---|
| **RA-6** revokes. `AuthorityLifecycleService` is "the sole mutator" and the only authenticated writer (`risk-authority-status-runtime/README.md:14-27`) | Builds the neutral `AuthorityReassessmentSignal` payload — and **never delivers it**. It holds no writer and no client, so it cannot mutate authority state even by mistake |
| **Decision Authority** governs the remedial action. `CompensationRequirement` is already "a governed proposal, not an auto-rollback" (`decision-authority/.../execution/compensation.py:1-7`) | Cites a `CompensationRequirement` **by id**. Mints no compensation type and forks no status vocabulary |
| **A human** decides whether anything resumes | Records that decision as its own `ContainmentLift`, with its own author and justification |

## The records

- **`IncidentRecord`** — tenant, subject, an uninterpreted `severity_label`, and **at
  least one `AuditReference`** (from G4) naming where to read what was observed. It
  carries no diagnosis and no cause. The id is derived from the evidence and the
  instant, so re-recording the same observation is the same incident, and a
  hand-picked id is refused.
- **`ContainmentRequest`** — the `PilotKillSwitchState` shape as a *request*: a
  target, a reason, an instant, who asked. It stops nothing itself.
- **`ContainmentLift`** — a separate record for a separate decision, bound by digest
  to the request it answers.
- **`RemediationProposal`** — what somebody proposes, optionally citing a
  compensation requirement. A proposal, never an instruction.

All four are frozen and digest-bound. **No clock is read anywhere** — an incident is
opened *at* an instant somebody observed, never at the instant the record happened
to be constructed — asserted over the AST of every source file.

## The asymmetry, and why it is the point

```
incident closes   ─────────────────►   containment unchanged
containment lifts ─────────────────►   incident unchanged
```

Closing an incident **does not** lift containment. `closed()` leaves the containment
field exactly as it was, and a test asserts it. This is the
`PilotKillSwitchState` rule — clearing the switch **"does not restart the pilot"**
(`code-governance/.../pilot_operator/api.py:270`) — carried forward, because an
incident that closes itself and silently restores service is how a containment
becomes theatre.

`contained_incidents()` is deliberately **not** filtered to open incidents: a closed
incident whose containment was never lifted is exactly the case an operator must
see, and the one a lifecycle-driven view would hide.

A lift must answer a specific request — same tenant, same target, same incident,
matching digest, and not before the containment it lifts. It is never justified by
the incident being closed.

Those rules are an **invariant, not a method**. An `IncidentRecord` holds the
`ContainmentRequest` and `ContainmentLift` themselves, and re-runs the admissibility
rules in `__post_init__`, so `dataclasses.replace(record, containment=LIFTED)` is
refused exactly like the named path. `__setstate__` re-runs them on unpickling, and
subclassing is refused outright — a subclass could replace the invariant with
nothing. Reaching `LIFTED` therefore requires a real, admissible `ContainmentLift`,
and constructing one is writing the decision down, with its own author and
justification.

None of that defends against code that steps around Python's object model outright:
`object.__setattr__` on a live instance, `__dict__` assignment onto a raw `__new__`,
or a `copyreg` reducer registered for this class — which, once registered, corrupts
even an ordinary `pickle` round-trip. No frozen dataclass can stop these, because
they bypass the methods a dataclass defines.

So the guarantee is stated as a class rather than a list: **every route through the
type** — construction, `replace`, the mutators, unpickling, subclassing — refuses an
unjustified `LIFTED`; and **anything already executing arbitrary code in the process
can fabricate a record**, which this package does not claim to prevent.

## The RA-6 payload

`signal_for_containment()` builds a `ReassessmentSignalPayload`: neutral, carrying no
authority field, naming evidence by digest rather than carrying it. It is
**field-compatible** with RA-6's `AuthorityReassessmentSignal` without importing it —
both are `str` enums, so values compare equal — but it is not the same object and
does not cross verbatim: RA-6 nests `target_type`/`target_id` in a `SignalTarget` and
`isinstance`-checks its own change-type enum, so a composition root constructs those
two and passes the rest from `as_signal_fields()`.

That adaptation is the whole integration, and it is pinned rather than asserted:
`tests/integration/test_ra6_signal_contract.py` imports RA-6, performs it, and checks
`validation_errors() == ()`. If RA-6 renames a field or a spelling, it fails.

The change types are a deliberate **subset**. `TENANT_EMERGENCY_STOP` is privileged —
RA-6 admits it only over a stronger emergency-authorized write path — and this
package has no write path at all, so it may not name it. Categories owned by other
observers are excluded too: reporting one would claim an observation this package
never made.

**Nothing here can deliver the payload.** A test walks every callable reachable from
the curated surface and asserts none takes a transport-shaped argument or is named
for sending — and the import boundary independently forbids every HTTP, queue and
database client that delivering one would need. A composition root that
never delivers is a valid deployment — the incident record stands on its own.

## No store

Records, refusal reasons and one read-only `IncidentJournalPort` Protocol, with no
implementation. The platform already has six durable append-only event stores plus
the kernel's audit port; a seventh, for a package whose entire output is a record
somebody else acts on, would deepen exactly the fragmentation G4 had to work around.
An incident's durability is its `AuditReference` into a store that already exists.

## Dependencies

`ugence-governance-contracts>=0.5.0` and the Python standard library. Nothing else —
no Risk Authority, no Decision Authority, no code-governance, no sibling wave 2 or 3
package, no store, no network client, no cloud SDK, no pydantic. Composition roots,
products and applications may import it; no capability package may, enforced by
`scripts/check_package_import_boundaries.py`.

## Gaps that survive this release

- **Nothing here detects anything.** An incident is opened by a caller who already
  noticed; there is no monitor, no rule engine, and no correlation across incidents.
- No delivery: the signal payload is built, never sent.
- No store, so nothing persists.
- Severity stays an uninterpreted label until an owner ratifies a taxonomy.
- The control plane the wave 3 rows assume still does not exist, so nothing here
  composes into an operational surface.
