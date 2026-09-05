# Ugence incident response — scoping record and ratification

**Status:** ratified 2026-09-05 by the repository owner. Scoping only: no package
exists yet, and this record amends no package ADR, port, test or manifest.
Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 3,
"Incident and remediation orchestrator", line 58) — the only wave 3 row marked a
new package. The audit-ledger row's contract half shipped as G4; the control-plane
and integration-hub rows are roadmap entries with no package. Wave 3's own logic is
that it **composes and mints no authority of its own** (line 81).

## The question

When something goes wrong — a revoked authority still in use, a duplicate effect, a
containment somebody tripped — what records it, what stops it, and what proposes the
fix? **This package records; it stops nothing and fixes nothing.** Every actor that
could stop or fix already exists and already owns that power, so the gap is a record
and a proposal, not a new authority.

The sequencing row calls it an *orchestrator*. That name is taken, and taken against
precisely this shape.

## What the repository already fixed

| Finding | Where |
|---|---|
| "Orchestrator" is a defined term: a service that "coordinates configured workflows and **does not acquire authority** from the capabilities it invokes", optional, and never an adjudicator `[V]` | `Project_documentation/repository/docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md:61`, `:119-122` |
| A package named orchestrator drifted into mutation once already, and needed a containment ADR to pull it back `[V]` | `ADR_CLOUD_SCALING_OPERATIONS_ORCHESTRATOR_CONTAINMENT_SCOPING.md:15-16,31` |
| RA-6 owns authority lifecycle exclusively: observers **signal**, Risk Authority **reassesses**, `AuthorityLifecycleService` is "the sole mutator" and the only authenticated writer, ActionGate enforces read-only `[V]` | `packages/integration/risk-authority-status-runtime/README.md:14-27` |
| The signal it consumes is explicitly authority-free: "no field carries authority" `[V]` | `packages/risk_authority/src/risk_authority/domain/authority_signal.py:86-98` |
| Compensation already exists and is already a proposal: "a governed proposal, not an auto-rollback … any compensating action must pass through the normal governance chain; rollback is never assumed possible" `[V]` | `packages/capabilities/decision-authority/src/ugence_decision_authority/execution/compensation.py:1-7`; statuses at `execution/status.py:118-122` |
| The kill-switch shape exists, and carries the asymmetry worth copying: clearing the switch "does NOT restart the pilot" `[V]` | `products/code-governance/src/ugence_code_governance/pilot_operator/api.py:257-279`, esp. `:270` |
| G4 landed `AuditReference`, a digest-bound pointer to one entry in one audit store `[V]` | `packages/governance-contracts/src/ugence_governance_contracts/contracts/audit.py` (0.5.0) |
| The platform already has six durable append-only event stores plus the kernel's audit port `[V]` | G4 scoping record, `ADR_UGENCE_AI_SYSTEM_REGISTRY_SCOPING.md` sibling analysis |
| "Incident" and "remediation" are reserved by no README or NEXT_PHASES, and no such package exists `[G]` | repository-wide search |

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Name and home | **`packages/integration/incident-response`, distribution `ugence-incident-response`.** Deliberately **not** an orchestrator: the term means optional workflow composition that acquires no authority, this package composes no workflow, and the one package that took the name drifted into mutation. Not an `…Authority` either — it decides nothing. |
| D-2 | How containment reaches RA-6 | **It produces a signal; it never delivers one.** The package builds a payload field-compatible with RA-6's neutral `AuthorityReassessmentSignal` — not that type, which it may not import — and records that it did. The composition root wraps the target and change type in RA-6's own types; `tests/integration/test_ra6_signal_contract.py` pins that adaptation against the real RA-6. A composition root hands it to RA-6's reassessor. The package holds no writer, no client and no reference to `AuthorityLifecycleService`, so it cannot mutate lifecycle state even by mistake. |
| D-3 | Relation to compensation | **`RemediationProposal` references Decision Authority's `CompensationRequirement` by id when one exists, and is otherwise a distinct, lighter record.** No second compensation type is minted, and no compensation status vocabulary is forked — Decision Authority 1.0.0 already spells both, and already forbids automatic rollback. |
| D-4 | Store in 0.1.0 | **None: records, refusal reasons and ports only.** The platform has six durable append-only event stores plus the kernel's audit port; a seventh, for a package whose whole output is a record somebody else acts on, would deepen exactly the fragmentation G4 had to work around. An incident's durability is its `AuditReference` into a store that already exists. |
| D-5 | What it may never do | **It never revokes, never executes, never rolls back, and never lifts its own containment.** It emits records and proposals. RA-6 revokes; Decision Authority governs the remedial action; a human resumes. |

## The three records

* **`IncidentRecord`** — an incident opened at a caller-supplied instant, with a
  tenant, a free uninterpreted `severity_label`, a `subject_ref`, and one or more
  `AuditReference`s naming the entries that evidenced it. It carries no diagnosis
  and no cause: it says *this was observed and here is where to read it*.
* **`ContainmentRequest`** — the kill-switch shape, as a request. It names what
  should stop and why, and records that the request was made.
* **`RemediationProposal`** — what somebody proposes doing, optionally citing a
  `CompensationRequirement` id. A proposal, never an instruction.

All three are frozen, digest-bound and bounded by
`ugence_governance_contracts.contracts.validity.Validity` where a window applies.
No clock is read; every instant is a caller input, asserted over the AST as the
wave 2 and wave 3 packages already do.

## The asymmetry, kept

Containment is requested and recorded. **Lifting containment is a separate decision
with its own record**, never an automatic consequence of an incident closing, and
never something this package can do. That is the `PilotKillSwitchState` rule —
"clearing the switch does NOT restart the pilot" (`pilot_operator/api.py:270`) —
carried forward deliberately, because an incident that closes itself and silently
restores service is how a containment becomes theatre.

Closing an incident therefore records only that the incident is closed. Whether
anything resumes is somebody else's decision, made and recorded elsewhere.

## Dependencies

`ugence-governance-contracts>=0.5.0` (`AuditReference`, `Validity`) and the Python
standard library. The risk-authority signal *shape* is reproduced structurally so
the package can build a payload without importing an authority package — the same
seam-without-import relationship `authority-directory` has to the approval
workflow's `ApproverEligibilityPort`. Nothing else: no Decision Authority, no
Risk Authority, no code-governance, no store, no network client, no cloud SDK.

Composition roots, products and applications may import it; **no capability package
may** — now mechanically enforced by `scripts/check_package_import_boundaries.py`
rather than asserted in prose.

## Gaps that survive this package `[G]`

- Nothing here detects anything. An incident is opened by a caller who already
  noticed; there is no monitor, no rule engine and no correlation across incidents.
- No delivery: the signal payload is built, never sent.
- No store, so nothing persists; durability is the `AuditReference` into a store
  that already exists.
- Severity stays an uninterpreted label until an owner ratifies a taxonomy — the
  same posture the AI system registry took for its classification label.
- The control plane the wave 3 rows assume still does not exist, so nothing here
  composes into an operational surface.

One prohibition: the package never revokes, never executes, never rolls back and
never lifts its own containment. A recorded incident is an input to somebody else's
decision, not a decision.

## Next step

Implement `packages/integration/incident-response` 0.1.0 under the decisions above.
