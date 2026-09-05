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
- `signal_for_containment` builds a payload **field-compatible** with RA-6's neutral
  `AuthorityReassessmentSignal` — not that type — and never delivers it. `target` and
  `change_type` are the composition root's two constructor calls;
  `as_signal_fields()` supplies the rest, and
  `tests/integration/test_ra6_signal_contract.py` imports the real RA-6 and asserts
  `validation_errors() == ()`. The change types are a deliberate subset excluding the
  privileged `TENANT_EMERGENCY_STOP` (D-2).
- Containment evidence is held as the `ContainmentRequest` and `ContainmentLift`
  records themselves, and the lift rules re-run in `__post_init__`. Reaching
  `LIFTED` therefore requires a real, admissible lift by every route that constructs
  or revives a record — `dataclasses.replace` and `pickle` included — rather than
  only by the named method, and subclassing is refused so the invariant cannot be
  inherited away. Routes that step around Python's object model — `object.__setattr__`,
  `__dict__` assignment onto a raw `__new__`, a registered `copyreg` reducer — remain
  outside any frozen dataclass's reach; the README states that as a class rather than
  claiming otherwise (D-5).
- `IncidentJournalPort`, a read-only Protocol with no implementation, and pure
  selectors over a caller-held collection. No store ships (D-4).
- Not an orchestrator and not an `…Authority`; mints no `AuditReference` and no
  compensation type; reads no clock — all asserted over the AST.
- Neighbours unmodified: governance-contracts 0.5.0, Risk Authority, Decision
  Authority, code-governance.
