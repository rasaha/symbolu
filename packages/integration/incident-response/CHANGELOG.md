# Changelog — ugence-incident-response

## 0.1.0 — wave 3, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_INCIDENT_RESPONSE_SCOPING.md`.

- `IncidentRecord` — tenant, subject, uninterpreted `severity_label`, and at least
  one G4 `AuditReference` naming where to read what was observed. The id is derived
  from the evidence and the instant; a chosen id is refused.
- `ContainmentRequest`, `ContainmentLift`, `RemediationProposal` — the kill-switch
  shape as a request, the separate decision that ends it, and a proposal that cites
  a Decision Authority `CompensationRequirement` by id (D-3).
- The forward-only incident lifecycle, with containment tracked **apart** from it:
  closing an incident never lifts containment, and `contained_incidents()` keeps
  showing a closed-but-contained incident (D-5).
- `signal_for_containment` builds RA-6's neutral reassessment payload and never
  delivers it; the change types are a deliberate subset excluding the privileged
  `TENANT_EMERGENCY_STOP` (D-2).
- `IncidentJournalPort`, a read-only Protocol with no implementation, and pure
  selectors over a caller-held collection. No store ships (D-4).
- Not an orchestrator and not an `…Authority`; mints no `AuditReference` and no
  compensation type; reads no clock — all asserted over the AST.
- Neighbours unmodified: governance-contracts 0.5.0, Risk Authority, Decision
  Authority, code-governance.
