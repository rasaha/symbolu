# ugence-agent-assurance-evidence

**Contracts only. Not enforcement-ready, and not a probe runner.** The record of
what a security or robustness exercise found about one exact AI system: a bounded
declaration binding the neutral system identity to one existing evidence reference
under an uninterpreted finding label, all three owned by governance-contracts.
Scoped and ratified by `docs/architecture/ADR_UGENCE_AGENT_ASSURANCE_EVIDENCE_SCOPING.md`
(AE-1 to AE-5); sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md`
(wave 4, line 63: "evidence provider to TAP and Risk Authority; never a decision
authority").

> This package records what a declarer asserted an exercise found. It **never**
> runs, probes, scores, admits, evaluates, persists or decides. A declaration is a
> record, not a verdict, and not a permission.

## What "contracts only" means here

Record types, refusal reasons, pure selectors, and one read-only Protocol. **No
probe runner, no attack corpus, no scorer, no admission engine, no control
evaluation, no store, no clock.** The lines the rulings draw are held
*structurally* rather than by discipline: there is nothing in the distribution
that could produce a finding, judge one, or hand one to anybody, so "it does not
admit" is not a promise this package could break. A boundary test asserts it — no
module named `store`, `adapter`, `connector`, `client`, `runner`, `probe`,
`corpus`, `scorer` or `engine`, and no `probe`, `attack`, `corpus`, `payload`,
`score`, `severity`, `admit`, `evaluate`, `verify`, `connect`, `url` or `socket`
anywhere in the code.

The shape follows `packages/integration/vendor-dependency` (wave 4), which
follows `data-use-admission` and `ai-system-registry`.

## The five rulings, and what each forbids here

- **AE-1.** Named for what it records. Not "adversarial": that word is the house
  name for every package's own probe suite (`adversarial_probes.py`,
  `tests/adversarial/`), and this package is not one of those.
- **AE-2 `NEW_RECORD_TYPE`.** `AssuranceFindingDeclaration` binds exactly one
  canonical `AssessedSystemBinding` to exactly one existing `EvidenceReference`.
  **The evidence reference is the finding's sole evidence identity**: it is carried
  whole, no competing reference is minted, and no provenance field is copied out of
  it. A look-alike reference is refused at construction.
- **AE-3 `UNINTERPRETED_LABEL`.** The finding is an `AssuranceFindingLabel`: no
  taxonomy, severity, score, ordering or implied verification.
  `VerificationStatus` remains an independent statement about whether a claim was
  *checked* and never represents what the exercise *found*; a `VerificationStatus`
  member passed as a finding is refused.
- **AE-4 `BOTH`.** TAP may cite the declaration's `EvidenceReference` in
  `evidence_refs`; separately, a composition root may construct Risk Authority's
  `ControlEvidenceRecord` from the declaration and submit it through
  `EvidenceAdmissionPort` (`packages/risk_authority/src/risk_authority/integrations/tap.py:22-27`).
  Both routes read the same `evidence_id`; a TAP citation is not Risk Authority
  admission, and neither route upgrades the other. **Neither route is built in this
  slice**, and the package imports neither consumer.
- **AE-5.** `AssuranceFindingLabel` landed in governance-contracts first, so every
  engine carrying a finding carries the same type.

## The identity, the evidence and the vocabulary are borrowed, never minted

`AssessedSystemBinding`, `EvidenceReference` and `AssuranceFindingLabel` are
**re-exported from governance-contracts**, never redefined — the direction that
package fixes itself (`contracts/system_identity.py:17-18`). A test asserts each
exported symbol *is* the same class object, and that no class here is named
`…SystemBinding`, `…Reference` or `…Label`.

**And the ceilings come with them.** A binding proves internal consistency and
digest-bound identity only (`system_identity.py:36-45`); `authenticity_status` is
permanently `STRUCTURAL_UNVERIFIED`, and the declaration exposes it. An evidence
reference is a digest-bound pointer, not the evidence. A label is what the declarer
*called* the finding, never whether it is true or how bad it is.

## The declaration

`AssuranceFindingDeclaration(declaration_id, tenant_id, binding, evidence, finding,
exercise_ref, validity, supersedes, declared_by, correlation_id, notes)`.

- **Three agreements are enforced, none assumed.** `tenant_id` must equal the
  binding's tenant; the evidence reference's tenant must equal it too; and the
  evidence reference's `subject_id` must equal the binding's `subject_id`. A finding
  about one subject bound to another system's identity is **refused**, never
  reconciled either way.
- **`evidence`** is carried whole. `evidence_id`, `evidence_digest` and
  `evidence_kind` are read through, never duplicated into parallel fields, and a
  test pins the field set.
- **`finding`** is uninterpreted (AE-3). A blank label is refused upstream; an
  unrecognized one is not, because there is no recognized set.
- **`exercise_ref`** is an opaque, non-secret reference to the exercise in the
  caller's own spelling. Nothing here can run it.
- **`declaration_id`** is derived from the binding's digest, the evidence
  reference's own id and content digest, the label's digest, the exercise reference
  and the window — no UUID, no clock — and the record **verifies** it at
  construction, so an id is never chosen by a caller.

## The window

Every declaration is bounded by a
`ugence_governance_contracts.contracts.validity.Validity`, evaluated with
`status_at(as_of)` at a caller-supplied, timezone-aware instant. **A declaration
outside its window is absent from every answer** — not returned with a flag — so a
lapsed finding cannot be argued around downstream. **No clock is read anywhere**
(no `time.time()`, no `datetime.now`, no `uuid4`), asserted over the AST of every
source file.

## Supersession

A changed declaration is made **afresh**, carrying `supersedes`; the prior record is
never edited. `supersession_refusals()` is pure and refuses a supersession that
names no predecessor, crosses a tenant, concerns a **different system identity**
(that is a new declaration, not a replacement), or **changes nothing**. A re-run
exercise that produced new evidence is a change; an identical re-declaration is
not.

`supersession_chain()` walks that history newest-first and is deliberately **not**
filtered by instant. It walks **only admissible links**; a cycle terminates rather
than looping.

## The read seam

`AssuranceFindingPort` is a read-only Protocol with five methods —
`get_declaration`, `declarations_for_tenant`, `declarations_for_system`,
`declarations_for_evidence`, `declarations_by_finding`. **No implementation ships
in 0.1.0**: a Protocol is a seam, not an adapter. There is no write method, by
construction, and a test pins the whole surface.

The pure selectors — `declared_at`, `select_for_tenant`, `select_for_system`,
`select_for_evidence`, `select_by_finding`, `select_by_exercise` — answer over a
collection the caller holds. They filter to in-force declarations first, always,
and never return another tenant's declaration. `select_for_evidence` is the lookup
both AE-4 routes share: a consumer holding an evidence id finds the declaration
that binds it.

## What it is not

- **Not a probe runner, a corpus or a scorer.** It produces no finding and ranks
  none.
- **Not an admission engine or a control evaluator.** `EvidenceAdmissionPort` and
  `ControlAssurancePort` stay Risk Authority's; nothing here calls either.
- **Not TAP.** It cites nothing; a composition root may.
- **Not a second system identity, evidence reference or label type.** See above.
- **Not an `…Authority`.** It decides nothing.

## Dependencies

`ugence-governance-contracts>=0.8.0` and the Python standard library. Nothing else —
no Risk Authority, no evidence runtime, no TAP provider, no provider framework, no
Decision Authority, no agent-runtime, no `sqlite3`, no network client, no cloud
SDK, no pydantic. Composition roots, products and applications may import it; no
capability package may — enforced repository-wide by
`scripts/check_package_import_boundaries.py` and
`tests/boundaries/test_package_import_boundaries.py`.

## Maturity ceiling

**`REFERENCE_GRADE_CONTRACT_ONLY`.** Nothing here runs a probe, holds a corpus,
scores a finding, admits evidence, evaluates a control, or proves that the
referenced evidence exists, that the exercise was sound, or that the named system
was the one exercised. Neither consumer route is built: no composition root
constructs a `ControlEvidenceRecord` and no TAP request is issued.
`ENFORCEMENT_ENABLED` is `False` and stays so until a further ruling authorizes a
route.

## Gaps that survive this release

- No store, so nothing persists; a composition root holds whatever it declares.
- The finding vocabulary is unratified, so the label stays uninterpreted until an
  owner fixes a taxonomy.
- An `evidence` reference that points at nothing is indistinguishable here from one
  that dereferences; only the store that holds the evidence can tell, and it is
  never asked.
- A dynamic `importlib.import_module(name)` cannot be caught by any static checker;
  that seam remains a reviewer's judgement.
