# Changelog — ugence-incident-response

## 0.2.0 — an incident names the vocabulary its severity label was written against

`CONTRACT_VERSION` moves to `incident_response.v2`. `ugence-governance-contracts` is
untouched and its `CONTRACT_VERSION` does not move, which is `VV-A` working as intended.

- `IncidentRecord.severity_vocabulary` —
  `VocabularyBinding(vocabulary, version, specification_digest)`, **required** on a v2
  record (`VV-E`). `""`, `latest` and `current` are refused by name.
- In `record_digest()` (`VV-B`) and deliberately **not** in the derived `incident_id`
  (`VV-C`): an incident's identity is its tenant, subject, evidence and instant, and the
  severity label never took part in it. Every incident id written before this is
  unchanged.
- The rule is re-run by `__setstate__` with every other invariant, so a record cannot be
  serialised, stripped of its binding in transit, and revived without one — the same
  bypass the containment asymmetry already had to close.
- **No store ships here** (D-4), so `LEGACY_CONTRACT_VERSION` exists for records whose
  digests were taken by somebody else and kept: those stay valid under the v1 projection
  and are never recomputed under the new one.

**It does not smuggle an ordering back.** `LV-D` ruled `SEV1` to `SEV4` opaque and
unordered, accepting by name that "every incident at or above SEV2" is unanswerable
here. The binding says which taxonomy was in force, never what a member outranks, and
`AE-3` is untouched.

**Found by the sweep.** `scripts/mutation_sweep.py` reported seven refusals in the new
code that no test observed, including every guard in the reconstruction helpers. Each is
now covered, and one branch was deleted instead: `ContractViolation` subclasses
`ValueError`, so the `except (TypeError, ValueError)` beside the re-raise could only
catch what the re-raise had already handled — while blunting the precise refusal message
on any path that reached it. The sweep is back to zero unclassified survivors.


## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

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
