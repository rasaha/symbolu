# Changelog — ugence-agentic-proposer

## 0.2.0 — OD-7, OD-8, OD-9 and OD-10 implemented; C7 and C9 removed with their replacements

The additive S2 public-surface release. `[V]` **Production and behavioural guards
exercise the OD-7 selection surface**, in
`tests/test_od7_domain_evaluation_boundary.py`, which discharges `I8.1` – `I8.15`. The
**documentation-consistency guards** in `tests/test_documentation_consistency.py` are
unchanged in kind and are still **not production enforcement**: they check what these
documents say, not what any selector does, which is why the behavioural module stands
beside them rather than replacing them.

**One atomic change set, as OD-7 part 8 requires.** C7's unconditional refusal of
`DomainCheckCompletion.COMPLETE` and C9's unconditional refusal of a non-null
`AdvisoryCandidateSet.selected_candidate_id` are **removed only alongside** every
replacement field, coupling validator, vocabulary member, protocol, identity mirror,
equation term, replay function, selector behaviour, exception and test obligation the
amendment specifies. Neither was removed as an isolated edit, and no intermediate state
carrying one removal without the replacement surface was committed.

### Implemented

* **OD-7 part 2 — the injected evaluator boundary.** `DomainEvaluationProvider` (a
  `typing.Protocol`), `DomainEvaluationRequest` and `DomainEvaluationResponse`. None is
  a contract: no C2 common field, no identity role, never stored, transported or
  included in `P_unsigned`. The response echoes back both the profile identity/version
  and the `candidate_id` it evaluated — a **request/response correlation check**, not a
  defence against a dishonest provider, and documented as such.
* **OD-7 part 3 — `DomainEvaluationOutcome`** (`SATISFIED`, `NOT_SATISFIED`,
  `INCONCLUSIVE`), on a new `CandidateAdvisory.domain_evaluation_outcome` field coupled
  to `domain_check_completion` in both directions. `INCONCLUSIVE` is reachable under the
  coupling, not excluded by it. `INDETERMINATE` is deliberately not reused, and the two
  spellings are asserted never to collide.
* **OD-7 part 5 — identity binding.** `AdvisoryCandidateSet` gains
  `domain_evaluation_profile_id`/`_version` and `selection_policy_id`/`_version`, all
  **C5b**; `ProposerAdvisory` mirrors the four, which is what puts them inside
  `P_unsigned`, and `identity.py`'s private `_UnsignedAdvisoryPayload` carries them too
  under G2's equivalence obligation. R-1b gains two correspondence clauses. Cardinality:
  `AdvisoryCandidateSet` 8 → 12, `CandidateAdvisory` 10 → 11, `ProposerAdvisory` 23 → 27,
  re-verified against `src/`.
* **OD-7 part 5 — two replay functions.** `verify_domain_evaluation` takes
  `expected_profile_id`/`_version` from **outside** the advisory under test, so it
  cannot be satisfied by a provider echoing back a tampered set's own label;
  `verify_deterministic_selection` recomputes the qualifying pool and checks the stored
  selector-policy identity against this package's own ratified constants.
  `verify_advisory_selection` gains a call to the second. Four disclosed ceilings —
  candidate suppression is invisible, a profile label is not a profile, there is no
  selector-policy registry, and replay proves reproducibility rather than authority —
  are asserted in the tests, not only stated in prose.
* **OD-7 part 6 — Equation 2 now has seven terms.** `DomainEvaluationSatisfied` joins
  the six. It is what replaced C7's structural closure of R-2/V13's `PROPOSAL` path, and
  it is exercised directly against `evaluate_readiness` as an exported function and
  mutation-tested against the six-term form, which must fail.
* **V13 reimplemented to recompute R-2 rather than refuse `PROPOSAL` outright.**
  `ProposerProcessRecord` enforces R-2's locally decidable half — `PROPOSAL` requires a
  selection — and `build_proposer_advisory` recomputes Equation 2 for the resolved
  candidate, which is where B3 assigns that recomputation.
* **OD-8 — selection-policy v1 is fail-closed uniqueness.** Implemented in-package as a
  deterministic, versioned function reading exactly `is_eligible` and
  `domain_evaluation_outcome`. Exactly one qualifying candidate is selected; zero or
  more than one selects nothing. **The `candidate_id` tie-break is deliberately
  unexercised**, and no code path resolves a multi-qualifier set to a selection.
* **OD-9 remains per candidate.** A candidate carrying `INCONCLUSIVE` or
  `NOT_SATISFIED` is filtered out of the qualifying pool **and nothing more**: a set
  holding one qualifying candidate beside any number of them selects that one. There is
  no run-wide interpretation of `INCONCLUSIVE` anywhere in the implementation.
* **OD-10 — the residual completed no-selection outcome** is reached, not merely
  declared: the fail-closed table's six rows are implemented as one ordered,
  non-overlapping classification, and its totality and disjointness are property-tested.
* **The public surface moves from 39 to 46 names**, adding exactly the seven this
  amendment authorized — `DomainEvaluationOutcome`, `DomainEvaluationProvider`,
  `DomainEvaluationRequest`, `DomainEvaluationResponse`, `DomainEvaluationProviderError`,
  `verify_domain_evaluation`, `verify_deterministic_selection` — and removing none.
  `version.py` moves `0.1.0` → `0.2.0`. `public_api.json` was regenerated only after the
  exported code and its tests existed.
* **H2 gains a fifth class**, `DomainEvaluationProviderError`, so a caller catches one
  named family for every OD-7 construction-time failure. Builders raise; verifiers
  report: a provider exception inside a verifier's own replay call returns `False`.
* **The exact H1 builder signatures are owner-ratified for this version (A13).** OD-7
  entailed that a builder constructing one of the new bearers in a single expression
  must be handed the provider and the profile; what it did not fix was the spelling.
  All four builders' keyword-only parameter names, their documented order, the injected
  `provider` parameter, the two scalar profile parameters (rather than a pair object),
  and the decision not to accept caller-supplied selector-policy identity parameters are
  now compatibility decisions rather than an open `[R]`. Documentation only: `src/` and
  H1 already matched exactly, which is the condition the declaration was given on.
* **`S-2 (via R-1b)` is now enforced locally** and moved from
  `tests/test_unenforced_local_rules.py`'s `UNENFORCED` registry to `ENFORCED`, leaving
  the former empty. Selection-policy v1 recomputes the qualifying pool from the
  advisory's **own** nested candidates, so an advisory selecting an ineligible candidate
  is refused by the advisory's own validator rather than only by the builder and the
  verifier.

### Deliberately still absent — not gaps

* **Substantive multi-candidate ranking.** No merit criterion is invented. A future
  ruling must name the business objective, the authoritative producer, a deterministic
  non-floating-point representation, the identity binding, and a replay path no
  untrusted caller can steer.
* **Concrete domain evaluators.** The boundary ships; no evaluator does. Nothing is
  imported, discovered, loaded or embedded, and the only providers in the tests are
  stubs that compute nothing about any business domain.
* **Multi-provider evaluation.** OD-7 ratifies exactly one injected provider returning
  one outcome per candidate.
* **Networking, storage, service discovery and plugin loading.** Barred outright by
  OD-7 part 2; the injected object is a plain in-process callable, and a guard asserts
  no module in `src/` imports a mechanism for reaching one.

### Verified

`pytest packages/capabilities/agentic-proposer -q` passes in full;
`python packages/capabilities/agentic-proposer/verify_agentic_proposer_distribution.py`
reports `AGENTIC_PROPOSER_S1_DISTRIBUTION_VERIFIED`, including a wheel build, an
isolated clean-room install and an end-to-end advisory built through an injected stub;
`scripts/check_doc_links.py` and `scripts/validate_terminology.py` pass; the
platform-freeze substantive digest is unchanged at
`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.

## Unreleased — OD-8, OD-9 and OD-10 ratified; OD-7 tie-break corrected

**Superseded by 0.2.0, which implements all three rulings.** The rulings below are
unchanged; only the status this entry recorded has moved on.

Ratified 2026-08-28. **Documentation only, as of this entry.** No `src/` module,
`public_api.json` or `version.py` was changed by it; C7 and C9 were still active and
unmodified; the package was still `0.1.0`; the substantive platform-freeze digest was
unchanged. The one test file touched was `tests/test_documentation_consistency.py`: at
that point no production or behavioural guard exercised the OD-7 selection surface, and
the **documentation-consistency guards** added there pin the OD-8/OD-9/OD-10 meanings
and the OD-7 statements those rulings amended — part 5's replay rule and part 7's
fail-closed table — against a silent revert to the pre-ruling prose, and nothing else
in OD-7. Those guards are **not production enforcement** and proved nothing about the
implementation that has since landed.

* **OD-8 — selection-policy v1 is fail-closed uniqueness.** The selector selects only
  when **exactly one** candidate is both `is_eligible is True` and
  `domain_evaluation_outcome is SATISFIED`. More than one qualifying candidate
  produces **no selection** and terminates `ABSTAIN`.
* **OD-8 — no field may be repurposed as a merit proxy.** Timestamps, identifiers,
  dispositions, review actions, and reference/assumption/uncertainty counts are all
  barred. The ground is provenance: only `is_eligible` is package-computed and only
  `domain_evaluation_outcome` will be provider-produced; every other candidate field
  is caller-supplied, so ranking on one would let the caller steer selection.
* **Substantive multi-candidate ranking is deferred**, not outstanding. A future
  ruling must name the business objective, the authoritative producer, a
  deterministic non-floating-point representation (the canonicalisation substrate
  rejects `int`, `float` and `Decimal`, so any numeric rank must be a canonical
  decimal string), the identity binding, and a replay path no untrusted caller can
  steer. The `DomainEvaluationProvider` gains no business-preference authority.
* **OD-7 tie-break correction.** OD-7's statement that ascending `candidate_id` is
  "always decisive" over whatever OD-8 leaves tied was too broad and conflicted with
  fail-closed uniqueness. Corrected: the tie-break applies only after a ratified
  substantive policy establishes the tied candidates are equally preferable, never as
  a substitute for a missing criterion, and is deliberately unexercised under v1. The
  underlying uniqueness and ordering facts are unchanged; what is withdrawn is the
  inference that totality alone licenses resolving a preference the owner never made.
* **`verify_deterministic_selection`'s replay rule is restated for selection-policy
  v1.** OD-7's part-5 description had the verifier recompute the selector "and the
  ratified tie-break", which survived the tie-break correction as a stale instruction
  an implementer would have built a `candidate_id` fallback from — contradicting row 4
  of the fail-closed table. Corrected: the verifier recomputes the qualifying pool
  solely from the eligible-and-`SATISFIED` members; when exactly one candidate
  qualifies the stored `selected_candidate_id` must equal that candidate's identifier;
  when zero or more than one qualify it must be `None`; selection-policy v1 applies no
  `candidate_id` tie-break, and a future version may activate one only after a
  separately ratified substantive criterion establishes the remaining candidates are
  equally preferable and lawfully selectable. The selector-policy identity check is
  unchanged.
* **OD-9 — `INCONCLUSIVE` maps unconditionally to `ABSTAIN`.** `ESCALATE` was not
  chosen: no authoritative, replayable severity condition is ratified, and a
  no-selection run carries no referral destination under R-1a.
* **OD-9 mixed-set scope — the ambiguity in merged OD-7 is resolved.** OD-7's part-4
  filtering language and its fail-closed table row could be read as disagreeing on a
  set holding both a qualifying and an `INCONCLUSIVE` candidate. Ratified reading:
  `INCONCLUSIVE` is **per candidate** and does not poison the set — such a set
  **selects the qualifying candidate**. The mapping applies only when the qualifying
  pool is empty and at least one evaluated candidate is `INCONCLUSIVE`.
* **OD-10 — residual completed no-selection outcome.** A completed run with an empty
  qualifying pool and no `INCONCLUSIVE` candidate terminates `ABSTAIN`. Missing
  evidence, evaluator unavailability and verification failure keep their OD-7
  behaviour.
* **The fail-closed table is now six ordered, non-overlapping rows**, stated on the
  qualifying pool rather than on the presence of any individual candidate, with
  exactly one row matching any completed run.
* **New prospective obligations `I8.12`–`I8.15`**: selection-policy v1 including a
  mutation test against a `candidate_id` fallback; the non-repurposing bar; the
  mixed-set case that distinguishes the ratified reading from the run-wide one; and
  table totality and disjointness. Documentation-consistency guards are added so
  these ratified meanings cannot drift back.

## Unreleased — OD-7 ratified (amended); implemented at 0.2.0

`docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` and
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md` are amended by OD-7,
ratified 2026-08-27, scoping the S2 domain-evaluation and candidate-selection
boundary that removes C7 and C9 — **a boundary, not a complete executable
algorithm.** **Superseded by 0.2.0, which implements the ruling below; the ruling
itself is unchanged.** **This was a documentation-only entry.** No `src/` module, test,
`public_api.json` or `version.py` was changed by it, and none could be until the
amendment was built, per OD-7's own transition controls. As of this entry C7 and C9 were
still active and unmodified and the package was still `0.1.0`.
This entry supersedes the earlier OD-7 entries it replaces in git history. It carries
two rounds of correction: seven points a first independent review found in the
original draft, and four more a second independent review found after that — the
Equation 2 term below (the material one), a status sentence in the specification that
still read as though nothing were outstanding, a Part J bullet that contradicted
OD-7's own contract-shape ruling, and a false claim that the affected cardinality
numbers were unpinned when three existing tests pin them. Three further clarifications
were adopted in the same pass: a ratified computability constraint on OD-8, an honest
restatement of what the provider echo does and does not defend against, and four
additional disclosed ceilings on replay.

* **(1)–(2) A narrow injected boundary, not an embedded evaluator.** Domain evaluation
  and candidate selection are separate responsibilities in one ordered boundary. The
  domain evaluator is external, injected through a `DomainEvaluationProvider` protocol
  this package owns but does not implement, echoing back both the profile identity and
  the `candidate_id` it evaluated; no concrete evaluator is imported or embedded, and
  no network, storage, service-discovery or plugin-loading mechanism is authorized.
* **(3) `DomainCheckCompletion`'s substantive reading is new, not carried over from
  C7.** C7 itself only closes the enum and makes Equation 2 total; OD-7 is the first
  place "evaluation having run" is defined — every check reaching a *per-check*
  determinate reading, independent of whether those readings converge. That
  distinction is what makes `INCONCLUSIVE` reachable at all: it is itself one of
  `DomainEvaluationOutcome`'s three closed members (`SATISFIED`, `NOT_SATISFIED`,
  `INCONCLUSIVE` — not `INDETERMINATE`, which D4 reserves elsewhere), a determinate
  *aggregate* value even though what it reports is non-convergence, carried on a new
  `CandidateAdvisory.domain_evaluation_outcome` field coupled to
  `domain_check_completion`.
* **(4) Selection is a deterministic, versioned, in-package function**, considering
  only eligible, `SATISFIED` candidates. The substantive ranking criterion is named
  **OD-8** and was outstanding at the time of this entry — not ratified by OD-7, and
  not invented by that amendment. **Superseded by the OD-8/OD-9/OD-10 entry above
  (ratified 2026-08-28):** OD-8 is now ratified as selection-policy v1, fail-closed
  uniqueness. The ascending-`candidate_id` tie-break is a total order over already
  -unique keys (`_check_candidate_sequence`); this entry originally inferred from that
  totality that the tie-break must settle any tie by itself, and **that inference is
  withdrawn by OD-8's tie-break correction** — under v1 the tie-break is deliberately
  unexercised, because more than one qualifying candidate produces no selection.
* **(5) `P_unsigned` gains identity-bound fields — this is not a zero-contract-shape
  transition.** One field on `CandidateAdvisory`; four **C5b** (`Token`-typed) fields
  each on `AdvisoryCandidateSet` and, mirrored, `ProposerAdvisory`, binding the
  domain-evaluation profile identity, each candidate's evaluation outcome, and the
  selector-policy identity. Recording any of these only on `ProposerProcessRecord` is
  rejected: that record sits outside `P_unsigned`. `verify_domain_evaluation` now
  takes an independently supplied `expected_profile_id`/`version` so its profile
  check cannot be satisfied by a provider merely echoing back a tampered stored
  value, and also checks the echoed `candidate_id`; `verify_deterministic_selection`
  additionally checks the stored selector-policy identity against this package's own
  ratified selector constants, not only the recomputed selection. Malformed input
  returns `False`; a provider exception during replay returns `False`; a provider
  exception during the original build raises `DomainEvaluationProviderError`; missing
  evidence warns and routes to `NEED_EVIDENCE` without ever calling the provider —
  four distinct behaviors, not one.
* **(6)–(7) Execution order, a frozen `CandidateAdvisory`, and fail-closed
  behavior.** Eligibility, then domain evaluation, then verification, then selection,
  then readiness. `CandidateAdvisory` stays frozen throughout: "candidate
  construction" in that order names an internal, pre-contract representation, and the
  actual frozen instance is built exactly once, after evaluation, on the same
  one-expression G2 discipline `ProposerAdvisory` already follows — never assembled
  incrementally. **Equation 2 gains a seventh term** — `DomainEvaluationSatisfied`
  (`candidate.domain_evaluation_outcome is DomainEvaluationOutcome.SATISFIED`) —
  amending Part F. An earlier draft of this entry claimed no term was needed, on the
  ground that Equation 2 runs only after selection and only against the
  already-`SATISFIED` selected candidate. That is withdrawn: `evaluate_readiness` is
  an exported public symbol with no caller in `src/`, so the call order cannot be
  imposed on a consumer, and a candidate carrying `COMPLETE` plus `NOT_SATISFIED`
  would satisfy R-2's condition for `terminal_outcome=PROPOSAL` — letting the
  strongest classification be reached for a candidate domain evaluation rejected.
  Precisely: today's V13 is a blanket refusal of `PROPOSAL` that never calls
  `evaluate_readiness`, which it can be only because C7 makes `COMPLETE`
  unconstructible, so the exposure opens not on C7's removal alone but when V13 is
  reimplemented to enforce R-2's recomputation — which part 8 requires to land in the
  same change set. The term is inert in S1 and lands with the rest of the OD-7
  surface. The
  fail-closed table covers missing evidence, an `INCONCLUSIVE` outcome, no eligible
  candidate, and an unverifiable provider or policy; "evaluators disagree" is
  withdrawn as presupposing unratified multi-provider evaluation. The
  `INCONCLUSIVE`-to-terminal-outcome mapping is named **OD-9** and was outstanding at
  the time of this entry; **superseded by the entry above** — OD-9 is ratified
  2026-08-28 as an unconditional, per-candidate mapping to `ABSTAIN`.
* **(8) C7 and C9 must be removed together, in the same change set** that also
  introduces every OD-7 field, vocabulary member, protocol and replay function; neither
  validator may be removed in isolation.

**OD-8 and OD-9 were outstanding when this entry was written, tracked by name rather
than left as implementation detail.** OD-7 ratified the boundary above; it did not
ratify the selector's ranking criterion or the `INCONCLUSIVE` mapping. **Both are
ratified as of 2026-08-28 — see the OD-8/OD-9/OD-10 entry at the top of this file,
which also adds OD-10 and corrects OD-7's tie-break statement.** Implementation of the
OD-7 surface remains gated on OD-7 part 8.

Full ruling, field-ownership table, C5 classification, new vocabulary, exception
class, replay-function signatures, rejected alternatives and prospective `I8.1`–
`I8.15` enforcement obligations are in the specification's `OD-7` entry.

## Unreleased — I7.13–I7.16 test coverage completed

`tests/test_s1_implementation_obligations.py` discharges the four I7 test
obligations left undischarged by the `0.1.0` implementation commit: no `src/` or
`public_api.json` change, no version bump — this is test coverage of behaviour
that was already correct.

* **I7.13 — construction shape under `strict=True` (G2).** The explicit
  pass-through constructs the right leaf types (`created_at` a `datetime`,
  `candidates` a `tuple` of `CandidateAdvisory`); feeding the payload's own
  `model_dump(mode="json", exclude_none=False)` back into the constructor raises
  `ValidationError` carrying both `datetime_type` and `tuple_type`, while
  `model_dump()` (mode="python") raises `datetime_type` alone — the explicit C4
  `field_serializer` carries no `when_used="json"`, so it runs in both modes and
  stringifies every datetime either way, but the tuple container itself survives
  mode="python" untouched; and a `list` passed to either `candidates` field is
  rejected with `tuple_type`.
* **I7.14 — R-7 replay (E2).** `verify_observation_resolution` returns `False`,
  warning the failing reference, for a dangling reference, two observations
  sharing an `observation_id`, and an observation substituted to another tenant,
  case, or `source_ref` outside `allowed_record_refs`; returns `True` while
  warning that an unreferenced extra observation is unreferenced; and a candidate
  with an empty `observation_refs` is confirmed unable to make a *different*
  candidate's dangling reference pass vacuously. `verify_advisory_selection` is
  confirmed to return `False` whenever `verify_observation_resolution` does.
* **I7.15 — revision inputs (G3).** `build_advisory_revision` refuses a call
  omitting `claim_summaries`, `observation_refs` or `uncertainties` (a `TypeError`
  from the keyword-only signature itself, not a silent inheritance); the three
  supplied values, not the parent's, appear in the revision and in its
  `P_unsigned`; the continuity fields (`tenant_id`, `case_ref`, `agent_id`,
  `role_contract_id`, `mandate_id`, `context_id`) are inherited unchanged; and
  `advisory_version` increments while `parent_advisory_digest` binds the parent.
* **I7.16 — construction-call completeness (G2).** An AST test over `identity.py`
  asserts the keyword set of the `ProposerAdvisory(...)` construction call equals
  `set(ProposerAdvisory.model_fields)` exactly — no field missing, no keyword
  that is not a field, no `**`-unpacking this check could not see through.

## Unreleased — OD-6 implemented

`docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` and
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md` were amended by
OD-6, ratified 2026-08-27, resolving an inconsistency an independent review of the
`0.1.0` implementation commit found between B3, H1 and R-1b(iv). All three parts are
now implemented against `src/` and covered by tests, in the same commit sequence as
this entry. Package stayed `0.1.0` at that point; `public_api.json` was regenerated for
the one added export. `[V]` **(i)'s C9 validator was subsequently removed by OD-7 part 8
at `0.2.0`**, in the change set that supplied its replacement; (ii) and (iii) are
unaffected.

* **(i) The no-selection ceiling moves from the builder to the input.** New **C9**
  (`AdvisoryCandidateSet._selection_is_unconstructible`, `contracts.py`) makes a
  non-null `selected_candidate_id` structurally unconstructible in S1, on the same
  pattern C7 uses for `DomainCheckCompletion.COMPLETE`. The pre-OD-6 builder-side
  refusal is removed from `identity.py`'s `_construct_advisory`; `build_proposer_
  advisory` and `build_advisory_revision` inherit the ceiling with no separate check,
  because neither can now receive a set that violates it. Covered by
  `tests/test_s1_implementation_obligations.py`'s `OD-6(i)` section: direct
  construction and `model_validate` both raise `pydantic.ValidationError`;
  `model_construct` and `model_copy(update=...)` are confirmed and disclosed as the
  pydantic-level bypasses they are (neither runs validation, on either field); a
  mutation control shows a twin model built from the identical field but without the
  validator accepts what the real class rejects; and the builder is confirmed to
  produce a correctly null-selected advisory even given a `model_construct`-forged
  input, since the four selection-dependent fields are derived, never copied.
* **(ii) H2 gains a fourth exception class, `CrossContractViolationError`**
  (`verification.py`), exported via `__init__.py` and `public_api.json`. The actual
  call-site inventory, derived from source rather than assumed: **three** raise
  statements, not eight — `identity.py`'s shared `_require_equal` helper (covering
  R-5's two call sites and R-6's two, plus R-10's one) and two further inline raises
  (R-9; R-7, via `_resolve_references`'s `False` return). R-1b's cross-contract
  clauses ((i)-(iv), (viii), (ix)) fall under this exception conceptually but have no
  raise site to convert: the advisory's nested `candidates` and its four
  selection-dependent fields are derived directly from `candidate_set` rather than
  separately supplied and compared, so those clauses hold by construction on every
  path the builders support; `verify_advisory_selection` remains the independent
  replay that reports a violation of them by returning `False`. `EligibilityMismatch
  Error` is unchanged and unreclassified. Covered by the `OD-6(ii)` section of the
  same test file: one test per rule (R-5 ×2, R-6 ×2, R-9, R-10, R-7), a classification
  control distinguishing the two exception classes, a control confirming
  `EligibilityMismatchError` is untouched, a control confirming `build_advisory_
  revision`'s own parent-continuity checks (a distinct G3 rule, not R-5/R-6/R-9/R-10)
  stay plain `ValueError`, and a structural check that no `CrossContractViolationError`
  raise site in `identity.py` names R-1b.
* **(iii) `ProposerProcessState`'s nine-member composition and R-4's comparison basis
  are ratified as specification text and now fully pinned.** The enum and its
  value-based R-4 comparison were already correct in `src/`; what changed is
  coverage. `tests/test_s1_implementation_obligations.py`'s `OD-6(iii)` section pins
  the exact nine-member set, the four terminal members' shared wire values with
  `TerminalOutcome`, R-4's value-based agreement and disagreement, `strict=True`'s
  continued refusal of a cross-enum substitution, and identical JSON serialisation on
  the four-value overlap; `tests/test_process_ordering_obligation.py`'s own text
  asserting the cardinality and comparison basis were still open is replaced.
* **Done alongside this entry:** the CI fix that installs `packages/jcs` in the
  package-suite job and removes the obsolete S0-era public-API-absence assertion;
  `test_documentation_consistency.py`'s `test_there_is_exactly_one_owner_decision_
  record` (previously pinned to the literal heading text `"## Owner decisions OD-1 –
  OD-5 — all resolved"`) and its `OWNER_DECISIONS` tuple, both now covering `OD-6`;
  and the OD-6 subsection the amended specification needed to satisfy
  `test_the_adr_and_the_specification_agree_on_every_owner_decision`.

## 0.1.0 — S1 contracts and equations implemented; the first public-API snapshot

Implements `docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` in full against `src/`
and moves the version to `0.1.0` in the same change that creates `public_api.json`
and its drift test (`tests/test_public_api.py`), per I6 and I8. The specification
itself is frozen and unedited; this release is the implementation of it.

### Frozen at this version

* **The eight canonical contracts** — `AgentIdentityRef`, `CognitiveRoleContract`,
  `WorkMandate`, `BoundedContextEnvelope`, `ToolObservation`, `AdvisoryCandidateSet`,
  `ProposerAdvisory`, `ProposerProcessRecord` — and the **two nested public shapes**
  — `CandidateAdvisory`, `ProposerProcessStateTransition` — in `src/ugence_
  agentic_proposer/contracts.py`, with every C1–C9 model rule: shared `frozen=True,
  extra="forbid", strict=True` configuration; the C2 common fields; C4's
  timezone-aware, UTC-normalising, microsecond-precision-`Z`-serialising datetime
  validator/serializer pair on every `datetime` field; the exact C5a/C5b/C5c/C5d
  classification of every `str`-valued field, declared per C8 as `Annotated[str,
  StringConstraints(...)]` and never `Field(pattern=...)`; C6's digest-shaped-field
  format grammar; C7's unconditional rejection of `DomainCheckCompletion.COMPLETE`;
  and, added by OD-6(i), C9's unconditional rejection of a non-null
  `AdvisoryCandidateSet.selected_candidate_id`.
* **Seven new enums** — `ReviewAction`, `DomainCheckCompletion`,
  `AgentLifecycleState`, `RoleActivationStatus`, `ToolOperationClass`,
  `ToolObservationAdmissionStatus`, `ProposerProcessState` — added to
  `vocabulary.py` alongside the three ratified D4 enums. `ProposerProcessState`'s
  nine members (the five R-3 process states plus the four terminal outcomes, at
  identical wire values to `TerminalOutcome`) discharge a gap the specification
  itself records as open — no explicit membership table, and no stated basis for
  R-4's cross-enum comparison — by direct entailment from R-3's own stated chain;
  it is not a reconciliation of any stated rule. `[I]`, disclosed for ratification.
* **The identity module** (`identity.py`, the single module I1 exempts from the D2
  text scan for the `sha256:` prefix and the C6 grammar): `compute_advisory_
  identity`, `verify_advisory_identity`, `build_proposer_advisory` and
  `build_advisory_revision`, each following G1–G3 exactly — the frozen `P_unsigned`
  projection, the private unexported `_UnsignedAdvisoryPayload`, and the one lawful
  construction shape (explicit field pass-through, the substrate call inline in the
  `advisory_digest=` keyword).
* **Equations 1 and 2** (`equations.py`) — `evaluate_eligibility` and
  `evaluate_readiness`, both `all((...))`-based total functions returning an actual
  `bool`.
* **The three verifiers and one exception** (`verification.py`) —
  `verify_candidate_eligibility`, `verify_advisory_selection` (the independent
  replay of R-1b and R-7), `verify_observation_resolution` (E2's algorithm), and
  `EligibilityMismatchError`.
* **The remaining three builders** (`builders.py`) — `build_candidate_advisory`,
  `build_advisory_candidate_set`, `build_proposer_process_record`.
* **R-1a through R-10 and L-1**, enforced exactly where Part E places each:
  locally, on the contract itself, wherever one instance suffices (R-1a, the local
  half of R-1b, R-3, R-4, R-8's locally-decidable clauses, S-1, S-2, L-1); in the
  builders and verifiers wherever a second contract, a builder or a verifier is
  required (R-2, R-5, R-6, R-7, R-9, R-10, the cross-contract half of R-1b).
* **`public_api.json`** and `tests/test_public_api.py` — the full H3 surface plus
  OD-6(ii)'s addition (39 exported names: 8 contracts, 2 nested public shapes, 10
  enums, 5 builders, 2 equation functions, 2 identity functions, 3 verifiers, 2
  exceptions — `EligibilityMismatchError` and `CrossContractViolationError` — 4
  constants, `__version__`), drift-tested against the installed package. No exported
  name begins with `Proposal` or `Recommendation` (D7).
* **I1** — the module-path-scoped mask for the `sha256:` prefix and the C6 pattern,
  scoped to `identity.py` alone, with the five required mutation tests in
  `tests/test_no_local_canonicalization.py`.
* **I7's twelve test obligations**, in `tests/test_s1_implementation_obligations.py`
  and (I7.9, I7.11) the now-armed pre-existing guards: the frozen-profile suite;
  list-order significance; no bare number; no wall clock; naive-datetime rejection
  and non-UTC normalisation; eligibility forgery; `COMPLETE` unconstructibility;
  V13; R-3 process ordering; the installed `ugence-jcs` distribution check; the
  rival-identity composition `test_advisory_contract_shape.py` now binds against
  the real `ProposerAdvisory`/`CandidateAdvisory`; and the C8 declaration-form
  mutation test.

### Retired

* **`tests/s1_specification_mirror.py`'s temporary representative shapes.**
  `representative_shapes()` now returns the declared `src/` contracts directly
  instead of building parallel duplicates. `ProposerProcessStateTransition.state`'s
  `TerminalOutcome` placeholder is replaced with the real `ProposerProcessState`,
  and the placeholder note is removed. The pinned registries — `FIELD_
  CLASSIFICATION`, `CONTRACT_CARDINALITY`, `SELECTION_COUPLING`, the C5d entries —
  are unchanged in content: they remain a hand-transcribed, independent mirror of
  the specification, checked against the now-real declared surface rather than
  against a stand-in for it.
* **`tests/test_unenforced_local_rules.py`'s `UNENFORCED` registry**, from
  forty-six entries to one (`S-2 (via R-1b)`, which remains a builder/verifier
  obligation — see D9/E1). Every discharged entry moved to `ENFORCED` with a
  construction the real contract now rejects, so the discharge history stays
  legible rather than being silently deleted.
* **`tests/test_process_ordering_obligation.py`'s skip-based obligation.** R-3 is
  armed and enforced; the two tests that asserted the placeholder was still in
  place are replaced with tests asserting the discharge.

### Deferred (Part J) — unchanged by this release

Candidate selection, a domain evaluator, a disposition-to-outcome mapping, the
semantic auditor, storage, transport, service and authorisation surfaces, the
three reason/check/audit-reference catalogues behind the five C5d fields, and the
reasoning-strategy permission concept and its vocabulary (OD-5(iii)). None of these
is implemented, specified beyond Part D/E's structural placeholders, or
authorized by this release.

## 0.0.1 — unreleased (S0 skeleton; S1 enforcement guards)

A version is declared only because the MVP readiness artifact
(`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`) exists and
records owner decisions D1–D5. No public contract is frozen at this version and no
public-API snapshot is created or asserted.

### Added

* Package skeleton following the `agent-workforce-composer` convention: setuptools
  build with a dynamic version from `version.py`, `py.typed`, `conftest.py` for bare
  source checkouts, and an isolated-wheel distribution verifier.
* The ratified D4 vocabulary and nothing else: `TerminalOutcome`,
  `CandidateDisposition`, `SemanticAuditorFindingStatus`, and the
  `RESERVED_AUTHORITY_VOCABULARY` prohibition set.
* `tests/test_boundaries.py` — static import scan of every source file plus an
  isolated-subprocess probe of what the public API actually loads, against the
  forbidden legacy frameworks, authority-owning capabilities, envelope/identity
  reference stacks, control planes, and network/model SDKs.
* `tests/test_vocabulary.py` — equality assertions on each ratified enum, the
  reserved-term prohibition, the INDETERMINATE positional split, the
  ABSTAIN-is-not-a-denial guarantee, and a scan rejecting any ALLOW/DENY/DEFER triad
  or confidence-to-outcome gate.
* `tests/test_no_local_canonicalization.py` — proves the package defines no local
  JSON-canonicalization or digest function anywhere, imports no hashing module, and
  declares `ugence-jcs` as the only identity substrate.

### Added — S1 enforcement obligations (D6, D7, D8)

The three `[R]` obligations the readiness ADR carries for S1, each enforced by a test
that holds before the surface it governs exists and arms itself when that surface
lands. See `docs/S1_ENFORCEMENT.md`.

* `tests/test_no_auditor_status_projection.py` — D6's standing rule. Rejects the six
  source shapes a status-into-outcome projection takes, each resolved through import
  aliases and module-qualified references, and is parametrized over every field the
  package defines in a reserved position — union arms included — so it binds with the
  first such field and judges the field's own annotation rather than the bare enum.
* `tests/test_advisory_contract_shape.py` — D7. Bars the `Proposal*` and
  `Recommendation*` name prefixes, bars any unratified `ugence.agentic_proposer.*`
  kind string, requires identity to be computed only by a call into `ugence_jcs`, and
  rejects the eight barred fields at any nesting depth, statically and (when the
  types exist) over the live models.
* `tests/test_role_projection_bounds.py` — D8. Discovers every shared contract
  distribution in the repository and asserts none carries, snapshots or depends on
  the role projection; asserts the projection exists in no other package; and rejects
  every role lifecycle verb across this package's defined and imported surface.
* `tests/test_no_local_canonicalization.py` — extended to pin the three modules above
  by name and to assert that every file in `src` and `tests` is either scanned or one
  of the two named exemptions.

### Fixed — S1 enforcement defects found by audit

Three defects in the guards above, none of which changed `src/` or the version.

* **D6 did not bind.** All six shapes matched bare `ast.Name` ids, so a projection
  written through an import alias (`TerminalOutcome as T`) or a module-qualified
  reference (`vocabulary.TerminalOutcome`) was not detected — the ordinary way the
  violation would be written. Every shape now resolves both. A sixth shape covers
  member access (`TerminalOutcome.ABSTAIN`, `T[name]`) inside a scope that reads an
  auditor status: an if/elif ladder or a guarded return never calls the enum, so the
  conversion-call shape alone let it through. The runtime half now collects fields
  whose annotation admits a reserved type as a union arm, and asserts against the
  field's declared annotation instead of re-testing the enum.
* **D7's blessed identity call could not be written.** `SUSPECT_TEXT` bars the
  substring `sha256`, which `ugence_jcs.canonical_sha256_hex` contains, so the call
  D7 mandates failed the D2 text guard: the two rules were jointly unsatisfiable.
  The permitted substrate call spellings are now masked before the scan, and both
  the permitted call and a local `hashlib.sha256` in the same position are
  self-tested samples.
* **The `ugence-jcs` floor was stale and pinned.** `>=0.1.0` does not guarantee
  `canonical_sha256_hex`, which landed in 0.2.0; the floor is now `>=0.2.0`, and the
  assertions that pinned the old string were updated with it.

Scanners that had no self-test now have one — the `Proposal*`/`Recommendation*`
prefix bars, the rival-kind-string prefix, the runtime field walk, and D8's three
export scans. Shared-contract discovery is asserted against an independent read of
the same files and a floor on the count, rather than non-emptiness. The snapshot
check now skips explicitly, naming the distribution, where a package publishes no
`public_api.json`, instead of passing with zero assertions executed.

### Fixed — second audit round

An audit of the previous revision confirmed the seven enumerated D6 spellings bind,
and found five further ordinary spellings that did not, two scanners with no
self-test, and two ways to hash locally while satisfying every by-name check. No
`src/` change, no version bump, no public-API snapshot.

* **Five more D6 spellings now bind**: an in-package re-export chain (alias
  resolution closed to a fixpoint across the package, so a two-hop relay resolves),
  a dict comprehension building the same lookup table as a literal, `getattr` —
  including a name assembled from concatenated literals — string forward references,
  and `TYPE_CHECKING` imports paired with them. Each is a self-tested sample.
* **The D6 runtime half is self-tested at last.** Nothing exercised it: the
  parametrization is empty in S0, so both the union-arm rule and the collection
  itself could be deleted with the suite green — the union-arm rule being the fix
  the previous revision was named for. It is now exercised against a synthetic
  namespace covering a pydantic model, a dataclass, a string-union dataclass and a
  plain annotated class.
* **String-annotated fields are collected.** A dataclass under
  `from __future__ import annotations` keeps its annotation as a string, so exact
  equality against the bare type names skipped exactly the fields most likely to
  carry a widened position.
* **The substrate is a distribution, not a name.** A module inside this package
  called `ugence_jcs` satisfied D7's substrate rule and the D2 text mask by spelling
  alone while hashing locally. A relative import can no longer bind the permitted
  substrate, and no file or directory here may be named for it.
* **`importlib` is barred in `src`.** `importlib.import_module("hash" + "lib")`
  reached a barred module without naming it, defeating every text scan. Barred in
  `src` only: the guards themselves import it to walk this package's modules.

`docs/S1_ENFORCEMENT.md` now states what the D6 scan covers as a list, and names
four boundaries it does not cross — dynamic construction, the runtime half detecting
widened annotations rather than projections, the packages in reach, and the
substrate floor being a text assertion rather than a resolved installed version.

### Fixed — third audit round

An audit of the previous revision confirmed the earlier findings closed, then found
that the fix had cost more than it bought in one place. No `src/` change, no version
bump, no public-API snapshot.

* **The alias map is now per module.** Merging every module's aliases into one dict
  made another module's import rename a global fact, and rejected ordinary code:
  a module importing an unrelated `Result` from a sibling, a parameter named
  `Result`, a local variable `Result = {...}`. All three are self-tested as lawful;
  the two-hop relay still binds.
* **`Literal["TerminalOutcome"]` is a value, not a forward reference.** A function
  declaring which vocabulary it names was flagged. String constants inside a
  `Literal[...]` subscript are skipped; quotes elsewhere still resolve.
* **The shadow-module detector is self-tested.** Both branches — a `ugence_jcs.py`
  and a `ugence_jcs/` package — could be deleted with the suite green. It is the
  detector this package's substrate rule leans on hardest.
* **Dynamic imports are constrained everywhere.** `__import__("hash" + "lib")`
  reached `hashlib` from `src` without importing `importlib`, which is the route
  barring `importlib` was meant to close; and a canonicalizer in `tests/` using
  `importlib.import_module("hash" + "lib")` passed, contradicting that module's own
  docstring. A dynamic import may now neither name a barred module nor be handed a
  name assembled at the call site; a plain variable is still permitted, since the
  guards walk this package's modules that way.
* **The per-file wiring is self-tested**, not only the scanners. A scanner that is
  self-tested but never applied does nothing, and dropping either scan — or the
  `src`-only bar — from the per-file check left the suite green.

`docs/S1_ENFORCEMENT.md` now separates **known uncovered spellings** (alias by
assignment, class-attribute alias, `functools.partial`, `globals()` with a literal
name — all statically visible, none closed) from the four **named boundaries**, and
no longer lets `globals()` shelter under "dynamic construction". It also records
that the substrate floor could assert the resolved `ugence_jcs.__version__` rather
than `pyproject.toml` text, and that which the floor should mean is an owner
decision.

### Fixed — fourth audit round

An audit of the previous revision found that the per-module alias fix had silently
reopened ground closed one commit earlier, and that the dynamic-import rule read as
coverage it did not have. No `src/` change, no version bump, no public-API snapshot.

* **Three import spellings the per-module map had lost now bind again**:
  `from .relay import *`, an aliased re-export reached by `from . import Name`
  through the package `__init__`, and an absolute in-package import
  `from ugence_agentic_proposer.relay import Name`. Each was caught before the
  per-module change and passed after it. The three name-reuse shapes stay lawful.
* **A dynamic import may not be handed a name this module composed**, wherever the
  composition happens. `_NAME = "hash" + "lib"` followed by `__import__(_NAME)`
  reached `hashlib` from `src` with the suite green, which composes into a working
  local identity function — the invariant D2 exists to hold. Augmented assignment,
  `bytes(...).decode()`, `%`-formatting and annotated assignment are covered with
  it. The line is composition, not indirection: a name the module merely received —
  a parameter, `info.name` — stays permitted.
* **The fixpoint self-test was vacuous.** Its chain was in favourable sorted order,
  so a single pass resolved it and the loop could be reduced to `range(1)` with the
  suite green. A reverse-ordered chain now fails under that mutation.

`docs/S1_ENFORCEMENT.md` no longer says a dynamic import may not be handed a name
"assembled at the call site", which was literally true and read as coverage; it
states what is tracked and what is not. Two entries join the known-uncovered list: a
projection split across two modules where neither alone names both vocabularies, and
a name composed through a route the scan does not model as composition.

### Fixed — fifth audit round

The audit of the previous revision recommended merge and named one defect worth
closing first: the assembled-name set was built by walking the whole module, so one
scope's binding was a fact about every other. No `src/` change, no version bump, no
public-API snapshot.

* **Assembled names are tracked per scope.** A module-level `name = "age" + "ntic"`
  marked the parameter of `def load(name)` as composed, and with it
  `import_module(name) for name in infos` — the shape the guards themselves use to
  walk this package. Parameters, loop and comprehension variables, `with`/`except`
  bindings and imports now shadow an outer binding; a name rebound from a
  non-assembled source stops being composed; and an augmented assignment marks a
  name only when what it appends is text, so `n = 0; n += 1` no longer does.
* This is the third appearance of one defect: a merged package-wide alias map, then
  a merged module-wide alias map, now a merged module-wide assembled-name set. The
  rule it yields is worth stating once — **a binding in one scope is never a fact
  about another** — and is recorded in `docs/S1_ENFORCEMENT.md`.

`docs/S1_ENFORCEMENT.md` records an `[R]` owner decision: whether D2 means the
invariant (no working local digest reachable from `src`) or the scan (no modelled
composition route). An audit demonstrated a byte-correct local SHA-256 in `src` with
every guard green by assembling names through a helper function. The route is
disclosed as uncovered; which reading of D2 applies decides whether closing it is
work or waste.

### Changed — owner decisions O-1 – O-4

Four decisions ratified after the S1 enforcement guards were audited. Two narrow a
guard that was over-broad, two add one that was missing. No `src/` change, no version
bump, no public-API snapshot; all four are recorded in
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md` under *Ratified
refinements*.

* **O-2 — the D8 lifecycle bound now prohibits authority, not vocabulary.** The scan
  matched verb stems, so it rejected `SUSPENDED`, `REVOKED`, `RoleActivationStatus`,
  `activation_status` and `expires_at`: the domain's correct words for lifecycle facts
  another authority determined. Names are now classified by grammatical form and
  syntactic position — a mutation form (`activate`, `suspending_role`) is barred in
  every position; an actor form (`RoleActivator`) is barred as a type or a callable and
  permitted as a reference to an external party; any lifecycle-stemmed field annotated
  as a callable is barred. The six verbs D8 names explicitly are still barred in every
  position, and the five retained names are pinned by equality.
* **O-2 — the narrowing is mutation-tested.** Each rule is weakened in turn and a real
  violation must escape the weakened guard, so no rule survives without a sample that
  would catch its removal; a mutant that gained a false positive against the retained
  vocabulary fails too.
* **O-3 — the ratified kind is narrowed to `ProposerAdvisory`.** The D7 guard required
  the kind of both advisory types. `CandidateAdvisory` is a subordinate per-candidate
  record, and a kind is what a consumer routes and stores on, so a candidate record
  declaring the advisory kind would be consumable as an advisory in its own right. It
  is now barred from the ratified kind and from any other kind in this namespace, and
  the kind reader is self-tested against all three spellings a type can declare one
  through.

### Added — O-1 and O-4 enforcement

* `tests/test_selection_dependent_fields.py` — O-1. `recommended_disposition`,
  `requested_review_action` and `requested_review_destination_role_ref` are nullable,
  and all three are `None` when `selected_candidate_id` is. Dormant until a class
  declares one of them, then requiring the selector on that class, a `None`-admitting
  annotation on each dependent, and a coupling enforced by code rather than by a
  docstring. The rule is stated executably on a reference model, so the required
  behaviour runs today. O-1's value-agreement clause binds the stage that introduces
  candidates and is recorded as a boundary, not covered.
* `tests/test_identifier_normalization.py` — O-4. Identifier and reference fields are
  validated against `^[A-Za-z0-9][A-Za-z0-9._:/-]*$`; claims, reasons, summaries and
  other human-readable text must not be. The premise is demonstrated against the
  substrate rather than asserted — with an empty `nfc_paths` profile, two normalization
  forms of one identifier canonicalize to different bytes — and the guard fails if a
  non-empty profile is ever passed. How the pattern is applied is pinned with it:
  `re.match` admits a trailing newline against `$`, `re.fullmatch` does not.
* Both modules are pinned by name in `tests/test_no_local_canonicalization.py`, so
  neither can leave the no-local-canonicalization scan silently.

### Added — reconciliation with the canonical S1 specification

`docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` is the authoritative S1 contract and
equation specification. The guards are reconciled to it and are exact mirrors of it: a
test originates, adds, renames or reinterprets no contract field.

* `tests/s1_specification_mirror.py` — the pinned registries, transcribed from the
  specification and citing the section each block comes from, with
  `test_the_registry_cites_its_source` failing if a cited section is renamed there. It
  also builds **temporary representative shapes** — live models declared in the ratified
  `Annotated[str, StringConstraints(...)]` spelling — so the guards are exercised
  behaviourally before a production contract surface exists. These shapes declare no
  contract, are exported from nothing, and authorize nothing.
* **Registry authority (G-1).** `FIELD_CLASSIFICATION` pins the exact class set, the
  exact field set for every contract against Part D's stated cardinality, and the exact
  C5 category for every classified field. Self-tests fail on a field added, omitted,
  renamed or reclassified. Reconciled to the merged specification: the fourth mechanical
  class **C5d** for the five reserved lists; `AgentIdentityRef.lifecycle_state` and
  `ProposerAdvisory.candidates` as non-`str` entries; the C5a-keys/C5c-values shape of
  `normalized_fields`; the 23-field `ProposerAdvisory`; the retained `candidate_set_id`
  beside the nested `candidates`; and the eight contracts plus two nested shapes.
* **Behavioural O-1 coupling (G-2).** The bearer is constructed from a complete valid
  fixture supplying all twenty-three required fields, and the four coupling cases are
  exercised as live validation outcomes. Static AST inspection is retained as
  supplemental and is no longer described as proof of behaviour;
  `test_the_suite_kills_a_no_op_validator_mutant` shows a validator naming all four
  fields and enforcing nothing passing the static layer and being killed behaviourally.
* **Registry weakening (G-3).** Every C5a and C5b entry is mutation-pinned, not a
  sample. The mutated registry is fed through the guard's own verdict helper, and the
  sweep is 47 patterned entries × 8 weakening categories = 376 cases, all killed when
  that helper is sabotaged. The weakening domain is derived from the guard's predicate
  rather than hand-listed; the sibling patterned class is excluded as a *narrowing* and
  covered by its own 47-case sweep, so every registered category falls into one or the
  other.
* **Free text (G-4).** C5c bars the *mechanism*: no pattern or regex constraint of any
  kind, including arbitrary ASCII-only grammars that are neither named literal. Lawful
  Unicode free text is proved accepted by live model probes.
* **Decorative patterns (G-5).** Syntactic discovery is restricted to constraints that
  actually bind the field value; a pattern in `json_schema_extra`, a `description` or an
  `examples` entry is read as validating nothing. Live probes prove C5a rejects invalid
  identifiers, C5b rejects invalid tokens including slash, spaces, newline and
  homoglyphs, sequence-valued fields validate every element, and C5c accepts Unicode.
* **Dependency baseline (G-6).** `DEPENDENCY_BASELINE_MODULES` is derived from the
  declared dependency registry in `pyproject.toml` rather than written beside it, and the
  generated baseline setup is pinned by equality — a baseline carrying an added
  `import socket` fails a self-test. Pydantic's transitive schema-construction behaviour
  stays permitted, direct networking imports stay prohibited, and the two-entry
  allowlist is unchanged.
* **Dynamic imports (G-7).** Detection extended to a literal bound to a local name and
  passed to `__import__` or `import_module`, `exec("import socket")`,
  `eval("__import__('socket')")`, an import inside `compile(...)`, and the prohibited
  relative-import spellings — each with a negative control. The remaining ceiling is
  stated and demonstrated: arbitrary runtime composition, externally supplied strings and
  reflection are not proven absent by static scanning.
* **Documentation gates (G-8).** The Agentic Proposer documents are added to
  `scripts/check_doc_links.py`'s curated list, so its link coverage of them is real;
  `tests/test_documentation_consistency.py` asserts that and enforces the same rule
  package-locally. No terminology-gate coverage is claimed, and a self-test fails if such
  a claim is introduced.
* **Composition and identity (G-9).** `tests/test_advisory_contract_shape.py` discharges
  I7.11 against the corrected nested candidate graph: it bars a nested `ToolObservation`,
  **requires** the nested `CandidateAdvisory` sequence so a reversion to reference-by-id
  fails loudly, and bars any second identity on the candidate — the last as real mutated
  models, built by subclassing the ratified `CandidateAdvisory` shape and run through the
  same reachability verdict the live guard calls, directly and through a nesting advisory
  root, with a negative control proving a blinded walker lets the mutant escape. The C8
  `Annotated[str, StringConstraints(...)]` spelling is required and tested, and the
  declared-dependency count is corrected to two.

### Added — R-3 process ordering recorded as an explicit obligation

`tests/test_process_ordering_obligation.py` states R-3 as a **named skip**, not as a
green test. Before it, R-3 appeared in the specification and in no test file at all, so a
reader counting green tests would have found no signal that a ratified invariant was
uncovered. The module documents why the representative shape cannot exercise the rule —
`ProposerProcessStateTransition.state` is typed `ProposerProcessState` by the
specification, `vocabulary.py` does not declare that enum, and the mirror may not
originate a vocabulary the specification assigns to the public surface — pins that the
placeholder is still documented as one, and **arms itself** when the enum is declared, at
which point it fails until forward-only ordering is enforced. `[G]` What is not stated in the
specification is the enum's **cardinality** and R-4's **comparison basis**; terminal
membership follows by entailment from D8's typing and R-4's "when one is present". R-3
carries no weight in that argument — it permits at most one terminal state, it does not
require one. The module refuses to settle either open item and names both as questions for
the specification.

### Changed — documentation status language

Temporary status wording — unmerged-branch claims and SHA-based truths — is removed from
the readiness ADR, the specification, the README and `docs/S1_ENFORCEMENT.md`. Durable
text states that a decision is ratified, that a named guard enforces it, and that
production implementation remains separately gated; those are three distinct statuses and
are not collapsed. OD-1 – OD-4 have one **decision record**, the table in the readiness
ADR, with guard evidence and enforcement limitations folded beneath it as subordinate
detail; the specification states each decision in full as the implementation-ready
document, and the two must agree.

### Fixed — sixth audit round: controls that did not run the guard

* `tests/test_identifier_normalization.py` — the G-1 completeness check's decision is
  factored into `_completeness_verdict`, in the style of `_pattern_verdict`, and
  `test_the_registry_matches_the_declared_field_set_exactly` is refactored onto it. The
  three mutation controls — an added field, an omitted entry, a rename — now feed their
  mutated surface or registry through that function and assert the verdict changes,
  instead of asserting set inequality directly. They were controls in name only: with the
  live assertion neutered the whole suite stayed green at 1223 passed, and all three now
  fail.
* `tests/test_documentation_consistency.py` — the OD-4 agreement check anchored on
  `RATIFIED` and so read exactly one statement per document. Both documents state OD-4's
  resolution three times, including in Part D where an implementer reads contract shape,
  and flipping one of the unread statements to `(b)` left the suite green.
  `test_every_resolution_statement_in_each_document_says_the_same_thing` now collects
  **every** `resolved (x)` statement through a tempered match, requires each to name OD-4
  and `(a)`, pins the count per document, and checks the attributed count against the bare
  population so an unattributable statement is reported rather than skipped. Falsified
  against all six occurrences and against a deleted statement.
* `tests/test_advisory_contract_shape.py` — `RATIFIED_DIGEST_FIELDS` is applied by name
  over the whole reachable graph, so a `CandidateAdvisory` bearing `advisory_digest` or
  `parent_advisory_digest` is invisible from the advisory root and is caught only by the
  candidate root's empty exemption. That assertion had no mutation control. The per-root
  exemption is factored into `_exemption_for` / `_root_failures`, the live guard and the
  controls both run it, and both names are added to `RIVAL_IDENTITY_MUTATIONS`. Widening
  the candidate root's exemption now kills three tests. The stale cross-reference naming
  `test_the_digest_exemption_…` is corrected to `test_the_identity_exemption_…`.
* `tests/test_identifier_normalization.py` — the assertion
  `weakenings | narrowings == others` was a set identity that cannot fail; it is replaced
  by the denominator itself, `47 x 8 = 376` weakening cases plus `47` narrowing cases
  exhausting the `47 x 9 = 423` candidate reclassifications, with self-reclassification
  standing outside that count as the tenth candidate rather than inside it.

### Changed — what the guards do not yet establish, stated more completely

`docs/S1_ENFORCEMENT.md` gains two rows, both derived rather than hand-written.

The first records that the mirror declares two model validators, C7 and R-1a, and that
**every** other rule decidable from one instance of one contract is unenforced —
nineteen constructions the representative shapes accept: L-1; the three `candidates`
rules on both `ProposerAdvisory` (D7) and `AdvisoryCandidateSet` (D6); R-8's
no-duplicates rule on all six lists it names; the three Part D rejects-an-empty-list
rules; and R-1b(v) and R-1b(vi), whose local halves became decidable when OD-4(a) nested
the candidates. `tests/test_unenforced_local_rules.py` constructs a violating instance
for each, so the row cannot claim a rule is unenforced once it is, nor omit one that
still is. `CandidateAdvisory.claim_refs` is deliberately excluded and the exclusion is
tested: R-8 does not name it and its Part D row states `each C5a` only, so a duplicate
there is lawful and listing it would be a test originating a rule.

The second records that R-2, R-5, R-6, R-7, R-9 and R-10 are **named but not covered**,
and that a mention in a scope paragraph establishes nothing behavioural. These are
omissions of enforcement, not departures from the declared shape: every field name, type
and nullability in the mirror matches Part D. The "one decision record" gloss is restated
as a claim about **authority** rather than as an enumeration of four facts the
specification also states.

### Fixed — seventh audit round: a real escape, and three false statements

* `tests/test_advisory_contract_shape.py` — **the rival-identity exemption is now scoped
  to the bearer.** It was applied by name over the whole reachable graph, so a shape
  hanging off `ProposerAdvisory` but not reachable from `CandidateAdvisory` and declaring
  `advisory_digest` was reported by **neither** root: the advisory exempted the name
  wherever it appeared, and the candidate could not reach the shape. That is a second
  identity inside `P_unsigned`, which is what D6 bars. The walk now carries ownership —
  `_runtime_owned_fields_reachable_from` yields `(owner, field)` pairs and
  `_runtime_fields_reachable_from` is its projection, so the guards that bar a name at any
  depth are unchanged — and `exempt` is honoured only for a field the root itself
  declares. The special-case branch that pinned the old blindness as expected behaviour is
  deleted, and
  `test_a_sanctioned_name_on_a_shape_off_the_advisory_alone_still_fails` is the
  regression. Falsified two ways: un-scoping the exemption and discarding ownership each
  kill four tests.
* `docs/S1_ENFORCEMENT.md` — the "named in no test file" row was wrong in both directions
  at once: it named R-4, which `tests/test_process_ordering_obligation.py` mentions five
  times in text the previous commit added, and omitted R-7, which nothing mentioned at
  all. The row is replaced by two derived checks —
  `test_every_ratified_rule_is_named_somewhere_under_tests` and
  `test_the_named_but_unexercised_row_is_derived_from_the_test_tree` — which recompute
  membership from the specification's rule table and a scan of `tests/`, discounting the
  scope paragraph that only records why a rule is out of scope. The derivation excludes
  its own module, so it cannot read its own prose as coverage.
* `docs/S1_ENFORCEMENT.md` and `tests/test_process_ordering_obligation.py` — the terminal
  membership argument rested on a false premise. R-3 (`spec:1032`, not `:1030`) says "at
  most one terminal state and only in final position": it **permits** a terminal state
  and does not require one. The entailment survives on D8's typing plus R-4's "when one is
  present", and now rests on those alone. A second open item is recorded alongside
  cardinality: R-4 equates a `TerminalOutcome` with a `ProposerProcessState`, and a
  cross-enum `==` is never true in Python, so R-4 must mean equality of name or of value
  and does not say which.
* `tests/test_documentation_consistency.py` — the docstring of
  `test_there_is_exactly_one_owner_decision_record` still asserted the sentence the
  previous commit corrected in `docs/S1_ENFORCEMENT.md`. The two artifacts agreed on
  authority and disagreed in text; they now agree in both.
* `tests/test_boundaries.py` — `test_a_widened_baseline_setup_fails` was the same defect
  class as the three registry controls: deleting the equality pin at
  `test_the_baseline_setup_is_pinned_by_equality` left the file at 51 passed. The pin is
  factored into `_baseline_pin_verdict` and both the live assertion and the control run
  it. Falsified: neutering the verdict kills the control.

### Fixed — eighth audit round: the placeholder's reach, and coverage by registry

* `tests/test_unenforced_local_rules.py` — the registry grows from nineteen constructed
  violations to **twenty-eight**. Added: **S-1** on `AdvisoryCandidateSet`, both halves —
  a selector naming no member and a selector resolving to two; **S-2** on
  `AdvisoryCandidateSet` and, labelled `S-2 (via R-1b)`, on `ProposerAdvisory`, where
  R-1b(iii)/(iv) carry it rather than the specification stating it twice; **R-1b(vii)**'s
  local half — `requested_review_action` contradicting the selected nested candidate;
  **R-3**'s `at`-monotonicity, no-repeat and entangled terminal-count/terminal-position
  clauses; and **R-4**. Every one was confirmed accepted by the representative shapes
  before being listed. The module's boundary paragraph now states, per rule, why anything
  omitted is out of scope rather than leaving it to be inferred from the list's silence,
  and records that S-1 and S-2 are vacuous in S1 under B3 but exercised anyway, because
  the shapes do not enforce B3 either.
* `tests/test_process_ordering_obligation.py` and `docs/S1_ENFORCEMENT.md` — the claim
  that R-3's ordering rule "has nothing to be exercised against" was **false**. The
  `TerminalOutcome` placeholder blocks exactly two clauses — no backward transition, and
  subsequence of the chain — because each needs a process state to state a violation. The
  other four are violable with terminal states alone. Both documents now say which
  clauses are blocked and which are not, the skip reason names the distinction, and
  **R-4's uncovered status is recorded explicitly**: the placeholder does not block it at
  all, since both sides of R-4's comparison are `TerminalOutcome`, so the comparison-basis
  ambiguity does not arise there.
* `tests/test_documentation_consistency.py` — **coverage is decided by a registry, never
  by a textual mention.** Deriving it from mentions made the opposite error to the
  hand-written list it replaced: it classified R-4 as covered by the very module that
  states it covers none of R-4. `_rules_exercised_by_some_test` now reads
  `UNENFORCED`, the new `ENFORCED` registry, and the obligation module's new
  `OBLIGATION_RULES`, and `test_exercise_is_decided_by_a_registry_and_never_by_a_mention`
  asserts the reason rather than the outcome, so deleting a case fails rather than passing
  on a mention.
* `tests/test_documentation_consistency.py` — `_specified_rule_ids()` is pinned by set
  equality against `RATIFIED_RULE_IDS`, in the same form as `RATIFIED_DIGEST_FIELDS`, so a
  rule added to or removed from the specification fails here rather than silently changing
  what every derivation is quantified over. `_RULE_ID` now matches the bold-bullet form as
  well as table rows, so **S-1 and S-2** — stated as prose under D6, and previously invisible
  to every derivation — fall inside the "every ratified rule is named somewhere" check.
  The headline count in the enforcement row is pinned against the registry's length.

### Changed — reasoning functions and strategies (OD-5)

Documentation and guards only. No `src/` change, no version change, no
public-API snapshot, no platform-freeze artifact touched.

* **No field is added to `CognitiveRoleContract`.** The strategy permission concept and
  its vocabulary are **deferred together to S2** (owner ruling, below). D2's cardinality
  stays 10 and the C5d roster stays at five fields. No strategy catalogue is drafted or
  ratified, and no individual strategy is named.
* **The four-way distinction is stated once, in D8:** `primary_function` (the role's
  organizational purpose), a role's **permitted reasoning strategies** (the methods the
  role may select among — an S2 concept, not an S1 field), `declared_strategy` (the
  method the process record asserts was used), and the terminal outcome. Three of the
  four are S1 fields; the second is named as a concept so the distinction can be stated
  whole. Evidence collection and verification stay **contract
  mechanisms**, and abstention and escalation stay **outcomes**; none is a reasoning
  strategy.
* **R-3's lifecycle is unchanged**, and a new D8 subsection states what the record does
  not represent: a forward-only record deliberately carries no internal strategy control
  flow, so the **absence of repeated or branching transitions is not evidence that no
  internal iteration or branching occurred**.
* **`declared_strategy` carries no authority.** It is metadata outside `P_unsigned`;
  declaration does not establish conformance; and S1 neither selects, validates nor
  cryptographically binds a reasoning strategy — selection and enforcement are S2's.
* **Guards.** The `P_unsigned` projection-absence assertion for `declared_strategy` in
  `tests/test_advisory_contract_shape.py`, which also asserts that **no** contract
  declares `permitted_reasoning_strategies`, so the deferral is a checked fact rather
  than an omission a reader must notice; the ten-field `CONTRACT_CARDINALITY` entry and
  five-entry `C5D_ENTRIES` pin, which now hold the deferred field **out** and fail if it
  is reintroduced without a ruling; and a **heuristic spot-check** in
  `tests/test_documentation_consistency.py` refusing claims of S1 authority over a
  reasoning strategy — selection, validation or binding. `[I]` That scan is a regex over
  English prose and is **not** coverage of a class: it is not proof that no such claim can
  be written, and it is stated here as what it is proven against rather than as a
  guarantee. It classifies each sentence by **actor**, which is what the subject matter
  turns on — the same sentence is a defect with S1 as its subject and correct with S2 as
  its subject. Proven against a named corpus of claims it must catch and correct
  statements it must leave alone, the latter including true statements about S2.

### Fixed — ninth audit round: OD-5's own overstatements

An independent audit of the OD-5 commit confirmed the four-way distinction, the C5d
classification and the unchanged R-3 lifecycle, and found five defects. Documentation and
guards only.

* **A rename left three dangling cross-references and a contradicted sentence.** Renaming
  the ADR's table to "Owner decisions OD-1 – OD-5" left two references to the old heading,
  a sentence crediting OD-4 with shape-bearing that OD-5 also has, and a
  three-statuses sentence still scoped to four. The suite was green over all four because every existing guard
  read the table rather than the prose around it. Two new scans close the class: italic
  cross-references to the owner-decision section must resolve against the live heading, and
  no document may claim one decision alone bears on contract shape.
* **The strategy-authority scan was narrower than its stated coverage.** The ADR and this
  file said it refused *any* affirmative claim; an audit found eight ordinary spellings
  passing — an active-voice cross-field check naming the two fields is the representative
  one, and the set is pinned in the test module rather than restated here. The
  cause was structural: `\b` does not break at an underscore, so a pattern anchored on
  `\breasoning` never reached `permitted_reasoning_strategies`, and the subject of such a
  sentence is as often "the builder" as "S1". The patterns now cover both voices, three
  subjects and the underscored field names; the eight escaping spellings are pinned as a
  named regression set; and the coverage claim is stated as the forms enumerated rather
  than as "any".
* **C5d's class definition was false for its sixth member.** It said reservation means
  "populating it later is not a schema change", which is untrue of a field whose ratified
  form retypes the element and removes the default. The definition now states what C5d
  guarantees in both cases — no value accrues before a vocabulary is ratified — instead of
  leaving the correction to a note beneath it.
* **The ADR labelled "Ratified rider" what the specification marks `[R]`.** Restated so
  the two agree: what OD-5 ratifies is the **bar on the route**, the field may not be
  brought into service by widening it in place. The allowlist form itself is not ratified.
* **Two consequences went unstated.** The forward-only-record and unverified-declaration
  limitations are now **K.7**, where a reader consulting Part K for what the specification
  does not evidence will find them. D2 also stated, while the field was still reserved,
  that the reserved half of the pair left every conformant S1 record declaring a method no
  role could permit. That disclosure is what the owner ruled on below, and it is removed
  with the field it described.

`[R]` One question raised by the audit was recorded rather than resolved: whether a
role's permitted **methods** fall within ratified D1's *minimum immutable attributes
required for deterministic role matching* and outside D2's bar on a
**constitution-derived attribute**. The owner's deferral below removes its subject from
S1 entirely, so the question travels with the field to S2; the readiness ADR's general
statement of it, under *Open architectural dependency: the Agent Constitution*, stands as
it did before OD-5.

### Fixed — tenth audit round: three contradictions and a rebuilt scan

Documentation and guards only. The field's presence in D2 and D2's preamble were left
untouched by this round; they were under a separate owner decision, ruled on below.

* **The specification contradicted its own OD-5 entry.** Its ratification statement
  credited OD-4 with closing the last shape-bearing question, while its OD-5 entry records
  *Bears on contract shape: yes*. Corrected, and `_SOLE_SHAPE_BEARER_CLAIM` now carries
  six wordings rather than two. `[I]` The two instances found so far are phrased so
  differently — one about a decision, one about a question, sharing almost no substring —
  that a fixed-sentence check would have caught one and certified the other. The wordings
  themselves are enumerated in the test module, not restated here, since this scan reads
  this file too.
* **The ADR named guards for four of the five decisions** while asserting each of five
  carries an implementing guard. OD-5's four are now named.
* **C5d called all five original members reason-code fields.** `deterministic_checks`
  names checks that were run and `semantic_audit_refs` holds references to audit records;
  neither is a reason code, and ratifying a reason-code catalogue would tell an
  implementer nothing about either. Corrected in the class definition, in the sixth-member
  note, and in Part J, which deferred all three under one heading and now defers three
  catalogues separately.
* **The strategy-authority scan is rebuilt to discriminate by actor.** An audit found nine
  of ten fresh claims escaping — verbs it did not carry, and "Stage S1" and "The advisory
  builder" as subjects it did not know — and, in the other direction, two patterns that
  named no actor and so flagged *true* statements about what S2 does. The scan now
  classifies whole sentences: an authority claim offends when an S1 actor is the subject
  of the verb and the subject matter its object; binding and conformance claims offend
  without an actor, since identity is S1's by definition and a declaration evidences
  nothing at any stage. `[V]` All ten fresh claims are caught, no true S2 statement is
  flagged, and the guard is stated in the ADR and here as a **heuristic spot-check proven
  against a named corpus**, not as coverage of a class.

`[I]` Two things the rebuild had to keep, recorded because each was tried and reverted.
**Adjacency**: a first draft let the actor, verb and subject matter fall anywhere in the
sentence and flagged four true sentences from these documents, so the actor must stand
within two words of its verb. **Block splitting**: collapsing a whole document merges list
items that do not end in a full stop, pairing one item's actor with another's verb, so
blocks are cut at blank lines, list markers, headings and table rows before sentences are
split. Both failure modes are pinned as tests.

### Changed — owner ruling: the strategy permission concept is deferred to S2

The owner ruled on the question the previous two rounds recorded rather than resolved.
**`permitted_reasoning_strategies` is not reserved in the S1 `CognitiveRoleContract`; it
is deferred to S2 together with its vocabulary, and OD-5 does not change S1 contract
shape.** Documentation and tests only.

* **The field is removed from D2.** `CognitiveRoleContract`'s stated cardinality returns
  to **10** and the C5d roster to **five**; `docs/S1_ENFORCEMENT.md` and this file are
  corrected in the same change, as are `CONTRACT_CARDINALITY`, `FIELD_CLASSIFICATION` and
  the representative shape in `tests/s1_specification_mirror.py` and the `C5D_ENTRIES`
  equality pin in `tests/test_identifier_normalization.py`. `[V]` Those pins now hold the
  field **out**: reintroducing it without a ruling fails them, and
  `tests/test_advisory_contract_shape.py` additionally asserts that no contract declares
  it, so the deferral is a checked fact rather than an absence a reader must notice.
* **The reasoning is recorded with the decision.** Reserving a C5d empty-only list would
  not have spared a schema change — the intended allowlist rejects an empty list, so the
  field would have had to be retyped, revalidated and stripped of its default — while it
  would have cost three consequences the specification had disclosed: every conformant S1
  pair internally unsatisfiable on this axis, every S1-era role contract carrying the one
  value the ratified form must refuse, and every stored contract needing reissue.
* **Nothing else in OD-5 changes.** R-3's recorded lifecycle is unchanged and reasoning
  methods remain method labels operating within it, not additional process states. The
  four-way distinction stands, with the second term now described as a future S2 concept
  rather than an S1 field. `declared_strategy` remains metadata outside `P_unsigned` that
  establishes no conformance and carries no authority, and S1 still neither selects,
  validates nor cryptographically binds a reasoning strategy. K.7 stands.
* **Two questions travel with the field.** `[R]` The vocabulary itself is unratified, and
  `[R]` whether a role's permitted methods are a constitution-derived attribute is now
  S2's to answer rather than S1's to carry — the ADR's general statement of that question
  stands unchanged, and its field-specific instance is removed with its subject.
* **The sole-shape-bearer prose scan is gated on the ADR table rather than hard-coded.**
  `[I]` It was added when two decisions bore on contract shape, making a sole-bearer
  sentence false. This ruling makes OD-4 the sole bearer again and the same sentence true,
  so a hard-coded bar would have forbidden the documents from stating a fact their own
  table asserts. The offence is now the **disagreement** — prose claiming one bearer while
  the table records several — which is what the original defect was.

### Changed — the S1 specification is frozen for implementation (A12)

Owner declaration, 2026-08-26. `docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` moves
from `CONTRACT SPECIFICATION RATIFIED; PRODUCTION IMPLEMENTATION SEPARATELY GATED` to
**`CONTRACT SPECIFICATION FROZEN FOR IMPLEMENTATION`**. Documentation only: no `src/`
change, no version bump, no `public_api.json`, no platform-freeze artifact; the
substantive digest is unchanged.

* **The contract surface is closed to change.** A field, type, cardinality, vocabulary,
  equation term or validation rule may be altered only by a **ratified amendment**
  recorded in the readiness ADR's owner-decision table — never by an implementation
  change reconciling the specification to code. Where the two disagree, the
  specification is right.
* **A11 is discharged, and every statement that said otherwise is corrected.** Its
  condition was independent review *and* merge; both are met, so the eight places across
  the specification and the ADR that recorded production implementation as unauthorized
  would have become false on merge. Each now points at **A12** and states what actually
  remains.
* **What remains is one thing, and it is not a ruling or a review.** The Part I
  obligations — I1, I6 and the unbuilt parts of I7 — are undischarged. `[G]` The freeze
  neither closes them nor authorizes skipping them; they are guards to be armed against a
  contract module that does not yet exist.
* `[R]` **The freeze is not a claim of correctness.** It is a decision to stop changing
  the specification and to find its remaining defects by implementing against it: errors
  are now discovered as amendments rather than as edits. Nothing the specification marks
  `[R]` becomes ratified by it — the S2 strategy vocabulary, OD-1's normalization-profile
  rider, and every guard claim verified only against a representative shape stand exactly
  as they were.

### Not implemented

The eight canonical contracts, Equations 1–4, proposal identity, invoice-domain
checks, reason codes, read-only adapters, model-assisted extraction, the semantic
auditor, and any HTTP endpoint.

The contracts and equations are **specified and unimplemented**: no contract module
exists in `src/`, and the guards that would catch a departure from the specification are
dormant on that surface and exercised against temporary representative shapes instead.
Production implementation is separately gated. No public-API snapshot is created: there
is no S1 contract surface to freeze, and the version stays `0.0.1`.
