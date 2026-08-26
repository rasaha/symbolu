# ADR: Ugence Agentic Proposer — MVP readiness

**Status:** Accepted (readiness record; no public contract frozen)
**Stage:** S0 skeleton, with Stage P (ugence-jcs extraction) complete
**Supersedes:** nothing
**Depends on:** an Agent Constitution document that does not exist and will not
exist before S1 (see *Open architectural dependency* and **D8**)

This artifact exists so that no public contract is frozen and no version is
declared before the ratified decisions, the missing dependency, and the authority
boundary are on the record. It is a readiness record, not a design.

D1–D5 were ratified before implementation. D6–D10 were ratified after Stage P and
Stage S0 landed, and close every question this artifact previously carried as open;
they are recorded under *Ratified resolutions* below. O-1 – O-4 were ratified after
the S1 enforcement guards landed and were audited, and are recorded under *Ratified
refinements* below; each narrows or completes a rule D6–D8 already carry. OD-1 – OD-4,
raised later by auditing those refinements against representative contract shapes and
reconciling this artifact with the contract specification, were ratified 2026-08-25 and
are recorded under *Owner decisions OD-1 – OD-5* below. **OD-5**, on reasoning functions
and strategies, was ratified 2026-08-26 and is recorded in the same table. **No owner
decision remains open, so S1 is unblocked on ratification grounds** — and on
ratification grounds only.
**One** thing still gates S1 code, and it is not a ruling: the Part I implementation
obligations in the contract specification are undischarged. A11's review-and-merge
condition is discharged by the freeze recorded in **A12**.
"Unblocked on ratification grounds" is therefore not "authorized to implement", and this
artifact does not claim it is. The O-1 – O-4 and OD-1 – OD-3 enforcement guards are
implemented in `packages/capabilities/agentic-proposer/tests/`; a guard being
implemented authorizes no production contract.

Evidence labels: `[V]` verified against this repository, `[I]` inferred,
`[R]` requires ratification, `[G]` gap.

---

## Ratified owner decisions (D1–D5)

Recorded verbatim. These are authoritative and are not reinterpreted here.

## D1 — Cognitive role contract

> Implement a proposer-local, strictly bounded CognitiveRoleContract data
> projection for MVP validation. It represents role information supplied by an
> external owner. The Agentic Proposer does not author, mint, activate, suspend or
> ratify an organizational role. The contract carries an opaque external role
> identifier plus the minimum immutable attributes required for deterministic role
> matching. Activation state is an input fact, never computed. Record the absence of
> UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_INITIAL_DESIGN_SPEC_v0.1 — which does not
> exist anywhere in this repository — as an explicit architectural dependency in the
> readiness artifact.

## D2 — Canonical proposal identity

> Do not create a proposer-local RFC 8785 / JCS implementation. Do not copy
> cer_v0_3/cleanroom/canon.py into the proposer. Extract the existing clean-room
> RFC 8785 / JCS implementation into one independently installable, authority-neutral
> leaf distribution, provisionally named ugence-jcs, preserving existing CER
> canonicalization semantics and test vectors byte-for-byte. This is a prerequisite
> dependency. If safe extraction requires unresolved package-placement, compatibility
> or migration decisions, stop and report those decisions rather than letting the
> proposer implement another canonicalizer. This decision covers the RFC 8785 / JCS
> exact-identity substrate only; it does not reverse the prior rejection of forced
> convergence among the compiler, Agent Workforce Composer, Risk Authority, Policy
> Authority and Cloud Scaling Controller canonicalizers, whose semantics and domains
> differ.

## D3 — Agent identity

> The Agentic Proposer mints no AgentIdentityRef. Agent identity is always supplied
> as an opaque externally issued identifier. The proposer may validate presence,
> declared binding and internal consistency; it may not create, activate, suspend,
> replace or enlarge an identity.

## D4 — Vocabulary

> The Agentic Proposer must not emit CLEAR, HOLD, BLOCK, AUTHORIZED,
> AUTHORIZED_WITH_CONSTRAINTS, DENIED, INDETERMINATE, SUPPORTED, UNSUPPORTED,
> CONSTRAINED, EXPIRED, or any equivalent authority claim. Ratified terminal
> outcomes: PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE. Ratified candidate
> dispositions: RECOMMEND_MATCHED_FOR_APPROVAL, RECOMMEND_WITHHOLD, REQUEST_EVIDENCE,
> ESCALATE_EXCEPTION. Ratified semantic-auditor finding statuses (for later stages,
> defined now): CONSISTENT, INCONSISTENT, INDETERMINATE, CONFLICTING. All are advisory
> proposer classifications. None constitutes evidence admission, a business decision,
> authorization, clearance or execution permission.

## D5 — Legacy reuse

> Implement the Agentic Proposer as a fresh leaf capability. Import and reuse no
> production code from agentic/agentic_framework, symbolu/agentic_framework or
> agent_runtime_migration. Those may be cited as design precedent only. Do not carry
> forward their competing policy-decision points, confidence gates, denial-triggered
> replanning, or LLM-coupled governance behavior.

---

## Open architectural dependency: the Agent Constitution

`[G]` `UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_INITIAL_DESIGN_SPEC_v0.1` does not
exist anywhere in this repository. D1's CognitiveRoleContract is therefore a
**proposer-local data projection for MVP validation only**. It is not an
implementation of, and confers no conformance with, any constitution.

What is unresolved while the document is absent:

* what an organizational role's authoritative attribute set is, and which of those
  attributes a matcher may depend on;
* who mints, activates, suspends and ratifies a role, and by what lifecycle;
* what conformance to the constitution requires of a capability that consumes role
  information;
* how activation state is asserted, and by whom, such that the proposer can treat it
  as an input fact.

`[V]` **D8 ratifies that the document will not exist before S1.** The projection
proceeds MVP-local with its re-derivation deferred, under the containment bounds in
D8. When the document does exist, the projection must be re-derived from it rather
than promoted as-is. Nothing in this repository should be read as evidence that the
projection anticipates the constitution correctly.

Until then D1's bounds hold: opaque external role identifier, minimum immutable
attributes for deterministic matching, activation state as an input fact never
computed, and no authoring, minting, activation, suspension or ratification of a
role by this capability.

---

## Stage P — ugence-jcs prerequisite and its outcome

**Outcome: complete, not blocked.** No package-placement, compatibility or
migration decision required an owner ruling.

`[V]` `cer_v0_3/cleanroom/canon.py` was extracted (via `git mv`, so history follows)
to `packages/jcs/src/ugence_jcs/canon.py` as the distribution `ugence-jcs`,
namespace `ugence_jcs`: independently installable, standard-library-only,
authority-neutral. Only the module docstring changed; every line of executable code
is byte-identical to the pre-extraction file. The five canonicalization error types
it raises moved with it, keeping their names, their `category` keys and the `path`
keyword; the base class moved renamed as `JcsError`, and `cer_v0_3.cleanroom.errors`
binds `CleanRoomError = JcsError`, so `except CleanRoomError` still catches every
clean-room fault and no `category` string changed.

`[V]` `digest.py`, `cer.py` and `profiles.py` stayed in the clean-room. They encode
an ActionGate domain tag, a CER envelope schema version and a profile registry — a
canonicalization substrate must not carry those — so the extraction stopped at the
byte stream.

### Placement, and the reasoning

`packages/jcs`, alongside the existing top-level leaves `packages/governance-contracts`,
`packages/governed-value`, `packages/policy-authority`, `packages/risk_authority`,
`packages/trusted-evidence-authority` and `packages/uvi-policy-contracts`.

`[I]` The `packages/` tiers — `capabilities/`, `providers/`, `runtime/`, `tooling/`,
`integration/`, `products/` — each name a role in the platform, and a JCS
canonicalizer fills none of them: it is not a capability (it decides nothing), not a
provider (it fronts no authority), not a runtime and not a product. The established
convention for a dependency-free substrate that several tiers may consume is a
top-level leaf. Those leaves are directory-named by stripping the `ugence-` prefix
from the distribution name (`ugence-governance-contracts` →
`packages/governance-contracts`), so `ugence-jcs` → `packages/jcs`.

### Independence preserved, not weakened

`[V]` The clean-room exists to prove CER identity semantics are reproducible by an
implementation sharing no code with the reference path. Extraction could have
weakened that in two ways, and both are closed in
`cer_v0_3/tests/test_forbidden_imports.py`: the clean-room may now import exactly
one non-stdlib module (`ugence_jcs`) and `test_only_stdlib_absolute_imports` still
rejects every other; and two new tests apply the same forbidden set
(`action_gate_ref`, `cer_v0_1`, `cer_v0_2`, `symbolu_robotics`, `cer_v0_3`) and the
same stdlib-only rule to the extracted tree, so reference code cannot re-enter
through the leaf.

`[V]` The production CER identity path (`cer_v0_3/envelope.py` →
`action_gate_ref.projection` + frozen `cer_v0_2`) is untouched and was not switched
to the extracted module in this stage.

### Evidence

| Claim | Evidence | Result |
| --- | --- | --- |
| Frozen CER V0.2 identity digests unchanged through the extracted module | `cer_v0_3/tests/test_cleanroom.py::test_cleanroom_matches_frozen_scale_digest`, `::test_cleanroom_matches_frozen_rollout_digest` | passed |
| Clean-room suite and independence proofs | `cer_v0_3/tests/test_cleanroom.py` + `test_forbidden_imports.py` | 14 passed |
| Byte stream preserved | `packages/jcs/tests/` (vectors captured before the move, Action-Profile behaviour, leaf boundaries) | 45 passed |
| Installs and behaves outside the monorepo | `packages/jcs/verify_jcs_distribution.py` (`--no-index` clean venv) | `UGENCE_JCS_DISTRIBUTION_VERIFIED` |
| Platform-freeze substantive digest unchanged | `python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json` | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`, identical before and after |

`[V]` CI: `.github/workflows/jcs-ci.yml` runs the package suite, the clean-room
consumer suite, the isolated-wheel install verifier, and the freeze verifier.

### Scope limit

`[V]` This covers the RFC 8785 / JCS exact-identity substrate only. It does not
reverse the prior rejection of forced convergence among the compiler, Agent
Workforce Composer, Risk Authority, Policy Authority and Cloud Scaling Controller
canonicalizers, whose semantics and domains differ. No such canonicalizer was
touched.

`[V]` **D9 ratifies that the production CER identity path is never migrated onto
`ugence-jcs`.** Stage P's decision not to switch it is therefore permanent, not
deferred.

---

## Authority-ownership boundary

The Agentic Proposer is advisory. It proposes; it decides nothing. Each authority
below is owned elsewhere, and the proposer must not duplicate, approximate or
pre-empt any of them.

| Authority | Owner | Basis |
| --- | --- | --- |
| Binding business decision | Decision Authority | `[V]` `docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md` (Accepted) |
| Exact-action authorization | ActionGate | `[V]` same ADR |
| Operational clearance | Action Clearance | `[V]` same ADR |
| Agent eligibility, ranking, team composition, proposed permission bounds | Agent Workforce Composer | `[V]` same ADR |
| Execution, and the provider-bound `TransitionProposal` | Agent Runtime | `[V]` `packages/runtime/agent-runtime/src/ugence_agent_runtime/models/proposal.py` |
| Evidence admission | Trusted Evidence Authority / TAP | `[V]` `packages/trusted-evidence-authority`, `tap_provider/` |

`[V]` `TransitionProposal` in Agent Runtime is immutable, deep-frozen,
deterministically fingerprinted and bound to an exact provider invocation. The
proposer's recommendation artifact is a different object at a different stage and
must not be named or shaped so as to imply it is that one. `[V]` **D7 ratifies its
name and shape**: `ProposerAdvisory`, with per-candidate `CandidateAdvisory`, kind
`ugence.agentic_proposer.advisory.v0`, and a field exclusion list that keeps it
structurally distinguishable from `TransitionProposal`. No such artifact exists at
S0; D7 binds S1.

### Audit findings that bind this implementation

`[V]` `agent_runtime_migration/reasoning/reflection.py:31` maps a denied
authorization to `REPLAN` ("replan a different approach"). That is denial bypass in
code. The proposer makes the inverse guarantee testable by emitting **no denial at
all**: `ABSTAIN` is a decision not to recommend, not a refusal, and there is
therefore nothing here for a downstream replanner to bypass.
`packages/capabilities/agentic-proposer/tests/test_vocabulary.py::test_abstain_is_not_a_denial`
pins it, and a source scan rejects the token `REPLAN`.

`[V]` `agentic/agentic_framework/governance_service.py:460-478` returns
`ALLOW`/`DENY`/`DEFER`; `confidence_gate.py:465-505` converts a confidence float into
`HALT`/`CONFIRM`/`BLOCKED`. Both are competing policy-decision points. Neither shape
is reproduced, and
`test_vocabulary.py::test_source_declares_no_competing_policy_decision_point`
rejects either by scanning the sources.

`[V]` `agentic/agentic_framework` (63 modules, 46,559 LOC, 70 test files) is run by
no CI workflow, and a divergent fork exists at `symbolu/agentic_framework` (24
modules). Per D5 neither is imported; both are design precedent only.
`test_boundaries.py` rejects `agentic`, `symbolu.agentic_framework` and
`agent_runtime_migration` statically and in an isolated subprocess.

---

## Reserved-vocabulary rule

`[V]` The capability must never emit `CLEAR`, `HOLD`, `BLOCK`, `AUTHORIZED`,
`AUTHORIZED_WITH_CONSTRAINTS`, `DENIED`, `INDETERMINATE`, `SUPPORTED`,
`UNSUPPORTED`, `CONSTRAINED`, `EXPIRED`, or any equivalent authority claim. The set
is held in code as `RESERVED_AUTHORITY_VOCABULARY` and asserted by equality, so a
term cannot be quietly dropped from the prohibition.

`[V]` One term appears on both sides of D4, and the split is by **position**:
`INDETERMINATE` is reserved as a terminal outcome and as a candidate disposition —
where it would read as an authority claim — and ratified only as a semantic-auditor
finding status, where it describes the auditor's reading of documents and claims
nothing about authorization. `test_vocabulary.py::test_indeterminate_is_scoped_to_the_semantic_auditor_only`
pins both halves. `[V]` **D6 ratifies this reading**: reservation is by position,
the semantic-auditor status is not renamed, and no auditor status may be projected
into an outcome or disposition field.

All ratified terms are advisory proposer classifications. None constitutes evidence
admission, a business decision, authorization, clearance or execution permission.

---

## Stage S0 — what was built, and what was not

`[V]` `packages/capabilities/agentic-proposer`, distribution
`ugence-agentic-proposer`, namespace `ugence_agentic_proposer`, following the
`packages/capabilities/agent-workforce-composer` convention. Core dependencies:
Python standard library, `pydantic`, `ugence-jcs`. Nothing else.

`[V]` The source defines the ratified D4 enums and nothing else. No canonicalization
code exists anywhere in the package — not in `src`, not in `tests`, not behind a
feature flag, not as a fallback, not as a temporary helper — enforced by
`test_no_local_canonicalization.py`, which scans the whole package for
canonicalization or digest definitions, hashing imports, `json.dumps` with ordering
or separator control, and canonicalization source text. The only permitted
implementation of proposal identity is a call into `ugence_jcs`; S0 implements no
identity and so imports nothing from it.

`[V]` Not implemented, and not authorized at this stage: the eight canonical
contracts, the eligibility and readiness equations (S1), proposal identity,
invoice-domain checks, reason codes, read-only adapters, model-assisted extraction,
the semantic auditor, and any HTTP endpoint.

`[V]` No public-API snapshot exists and none is asserted in CI; the declared version
is `0.0.1` and no public contract is frozen at it.

### Evidence

| Claim | Evidence | Result |
| --- | --- | --- |
| Leaf boundary holds statically and at runtime | `tests/test_boundaries.py` | passed |
| D4 vocabulary is exactly as ratified; no reserved term emitted | `tests/test_vocabulary.py` | passed |
| No local canonicalization anywhere in the package | `tests/test_no_local_canonicalization.py` | passed |
| Whole S0 suite | `python -m pytest packages/capabilities/agentic-proposer/tests -q` | 46 passed |
| Installs and behaves outside the monorepo, resolving ugence-jcs from a real wheel | `verify_agentic_proposer_distribution.py` | `AGENTIC_PROPOSER_S0_DISTRIBUTION_VERIFIED` |

`[V]` CI: `.github/workflows/agentic-proposer-ci.yml` runs the package suite, a job
asserting this artifact exists and records D1–D5 and that no public-API snapshot
exists, the isolated-wheel verifier, and the freeze verifier.

---

## Ratified resolutions

D6–D10 were ratified after Stage P and Stage S0 landed. Each closes a question this
artifact previously carried as open. They are recorded verbatim in substance and are
not reinterpreted here. Nothing below is implemented in this session; D6 is already
satisfied by the S0 code, and D7–D10 bind S1 and later stages.

## D6 — INDETERMINATE stays reserved by position

`INDETERMINATE` remains reserved **by position only** — as a terminal outcome and as
a candidate disposition — and remains ratified as a semantic-auditor finding status.
There is no rename.

**Standing rule.** No semantic-auditor finding status may be projected into an
outcome or disposition field. The reservation is positional, so it is defeated not
by the term appearing in the auditor's vocabulary but by an auditor status being
copied, mapped, coerced or defaulted into a `TerminalOutcome` or
`CandidateDisposition` field. `CONSISTENT` becoming a terminal outcome would breach
this rule exactly as `INDETERMINATE` would.

`[V]` D6 requires no change to S0: `vocabulary.py` already encodes the positional
split, and `tests/test_vocabulary.py::test_indeterminate_is_scoped_to_the_semantic_auditor_only`
pins both halves.

`[R]` The standing rule is not yet mechanically enforced, because S0 has no field
into which a status could be projected. S1 must add a test that rejects any
assignment or conversion from `SemanticAuditorFindingStatus` into an outcome or
disposition field at the same time as it introduces the first such field.

## D7 — The recommendation artifact is ProposerAdvisory

The proposer's recommendation artifact is named **`ProposerAdvisory`**, carrying
per-candidate **`CandidateAdvisory`** entries.

| Property | Ratified value |
| --- | --- |
| Kind | `ugence.agentic_proposer.advisory.v0` |
| Identity field | `advisory_digest` |
| Identity computation | only through `ugence_jcs` |

**Barred fields.** `ProposerAdvisory` and `CandidateAdvisory` must not carry
`fingerprint`, `provider_id`, `operation`, `arguments`, `idempotency_key`,
`workflow_id`, `instance_id` or `task_id`.

`[I]` The exclusion list is what makes the boundary structural rather than nominal.
Each barred field is the mark of an authority the proposer does not hold:
`fingerprint`, `provider_id`, `operation` and `arguments` bind an object to an exact
provider invocation, which is Agent Runtime's `TransitionProposal`;
`idempotency_key` implies an execution the artifact may be replayed against; and
`workflow_id`, `instance_id` and `task_id` bind it to a runtime execution context.
An advisory that carried them would be consumable as an execution instruction no
matter what it was named.

**Barred name prefixes.** `Proposal*` and `Recommendation*` are barred. `[V]`
`Proposal*` is already owned by Agent Runtime
(`packages/runtime/agent-runtime/src/ugence_agent_runtime/models/proposal.py`);
`Recommendation*` is owned by Decision Authority.

`[R]` S1 must enforce D7 mechanically when it defines the contract: a test asserting
the two type names, the kind string, that `advisory_digest` is the only identity
field, that identity is computed only by a call into `ugence_jcs`, that none of the
eight barred fields is present at any nesting depth, and that no exported name
begins with `Proposal` or `Recommendation`.

**Narrowed by O-3.** The kind belongs to `ProposerAdvisory` alone; `CandidateAdvisory`
must not declare it. See *O-3* under *Ratified refinements*.

## D8 — The Agent Constitution will not exist before S1

The Agent Constitution will not exist before S1. The D1 CognitiveRoleContract
projection proceeds **MVP-local with re-derivation deferred**, bounded to:

* a proposer-local **v0** projection;
* never exported to shared contracts;
* carrying no constitution-derived attribute;
* exposing no role lifecycle verb.

`[I]` The four bounds are containment for a projection built without its governing
document. Not exporting it keeps the blast radius inside this capability, so
re-derivation later is a local change rather than a cross-package migration.
Carrying no constitution-derived attribute prevents the projection from encoding a
guess about the absent document and having that guess read back as settled. Exposing
no lifecycle verb — no mint, activate, suspend, ratify, revoke or replace — keeps D1
and D3 intact: activation state stays an input fact, never computed.

`[G]` The gap recorded under *Open architectural dependency* is unchanged. D8
ratifies proceeding despite it; it does not close it. Nothing built under D8 may be
cited as conformance with a constitution that does not exist.

`[R]` S1 must enforce the export bound: the v0 projection is not re-exported from
any shared contract package, and no lifecycle verb appears on its surface.

**Narrowed by O-2.** The lifecycle bound is on mutation operations and callable
authority, not on a contract's vocabulary for lifecycle facts determined elsewhere.
`SUSPENDED`, `REVOKED`, `RoleActivationStatus`, `activation_status` and `expires_at`
are retained. See *O-2* under *Ratified refinements*.

## D9 — The production CER identity path is never migrated onto ugence-jcs

The production CER identity path (`cer_v0_3/envelope.py` →
`action_gate_ref.projection` + frozen `cer_v0_2`) is **never** migrated onto
`ugence-jcs`.

`[V]` The reasoning is the evidence structure itself. The clean-room exists to prove
that CER identity semantics are reproducible by an implementation sharing no code
with the reference path — enforced by `cer_v0_3/tests/test_forbidden_imports.py` and
consumed by `cer_v0_3/conformance/differential.py` and `conformance/cross_domain.py`.
Migrating production onto `ugence-jcs` would make the reference and clean-room paths
one implementation. The differential runner would then compare an implementation
with itself, and every agreement it reports would be vacuous. The independence
evidence would not be weakened; it would be destroyed, and no test currently in the
repository would fail to signal that.

**Reopening conditions.** This decision may be revisited only with (a) a third
independent implementation, so that differential conformance still compares two
genuinely separate implementations after the migration, **and** (b) full CER V0.2
conformance-corpus and frozen-digest equality demonstrated across them.

`[V]` Stage P was already built to this decision: the production path was left
untouched and only the clean-room consumes the extracted module.

## D10 — ugence-jcs stays locally built and unpublished

`ugence-jcs` is not published to an index. It stays locally built, consistent with
every other package in this repository.

`[V]` No package in `packages/` is index-published today; each consumer's verifier
builds the wheels it needs. `packages/capabilities/agentic-proposer/verify_agentic_proposer_distribution.py`
already builds the `ugence-jcs` wheel from the sibling package into a local
wheelhouse and installs against it, which is what proves the declared dependency is
satisfiable rather than aspirational.

**Revisit condition.** Only an out-of-repository consumer. Until one exists,
publishing would add a release surface with no reader.

---

## Ratified refinements (O-1 – O-4)

> **Provenance of this section.** O-1 – O-4 were first written alongside the S1
> enforcement guards and are recorded **here**, in this artifact, because that is where
> the decision record lives. Documents once cross-referenced an *O-1 – O-4* section that
> no revision of this artifact carried, leaving the four decisions cited and undefined;
> the text below is that section, moved in verbatim in substance.

O-1 – O-4 were ratified after the S1 enforcement guards landed and were audited.
Each narrows or completes a rule D6–D8 already carry; none reopens a ratified
decision. They are recorded verbatim in substance and are not reinterpreted here.

## O-1 — Selection-dependent fields are nullable and coupled

Three fields depend on a selected candidate and are nullable with it:

* `recommended_disposition: CandidateDisposition | None`
* `requested_review_action: ReviewAction | None`
* `requested_review_destination_role_ref: str | None`

When `selected_candidate_id` is `None`, all three are `None`. When a selected
candidate exists in a future stage, they must match that candidate and its permitted
routing.

`[I]` The coupling is what keeps the advisory readable. A disposition or a routing
request standing next to no selected candidate is a recommendation about nothing,
and a consumer cannot tell whether the selection was lost in transit or the routing
was invented — the two failure modes call for opposite responses.

`[V]` The nullability clause is enforced by
`tests/test_selection_dependent_fields.py`: the guard arms with the first class that
declares any of the three, and then requires the selector on the same class, an
annotation admitting `None` on each dependent field, and a coupling enforced by code
in that class rather than by its docstring. The rule itself is stated executably on
a reference model, so the required behaviour is exercised today.

`[R]` The value-agreement clause — a dependent field agreeing with the selected
candidate and its permitted routing — binds the stage that introduces candidates.
Nothing in this package has candidates, so nothing here can check it; the guard
records the boundary rather than covering it.

## O-2 — The lifecycle bound is on authority, not on vocabulary

The governance vocabulary is retained: `SUSPENDED`, `REVOKED`, `RoleActivationStatus`,
`activation_status`, `expires_at`. D8's lifecycle-verb bound is narrowed to prohibit
agent-owned lifecycle **mutation operations or callable authority** — `activate`,
`suspend`, `revoke`, `expire` or equivalent state-changing methods — without
prohibiting contracts from describing externally determined lifecycle states and
validity periods.

`[I]` D8's substance is unchanged: activation state stays an input fact, never
computed. What changes is the reading of the guard. A scan matching stems alone
cannot tell an act from a description, so it rejects the domain's correct words for
facts some other authority determined — and a rename bought under that pressure
costs the contract its meaning while removing no authority. The proposer is a
*reader* of roles; a reader needs the vocabulary of what it read.

`[V]` `tests/test_role_projection_bounds.py` now classifies each name by grammatical
form and syntactic position: a mutation form (`activate`, `suspending_role`) is
barred in every position, an actor form (`RoleActivator`) is barred as a type or a
callable and permitted as a reference to an external party, and any lifecycle-stemmed
field annotated as a callable is barred. The five retained names are pinned by
equality, and the six verbs D8 names explicitly are still barred in every position.

`[V]` The narrowing is mutation-tested. Each rule is weakened in turn and a real
violation must escape the weakened guard, so no rule survives without a sample that
would catch its removal; a mutant that gained a false positive against the retained
vocabulary fails too.

## O-3 — Only ProposerAdvisory bears the ratified kind

The ratified-kind guard is narrowed to `ProposerAdvisory`. `CandidateAdvisory` is a
subordinate candidate record and must not claim the authority-facing advisory kind.

`[I]` A kind is what a consumer routes and stores on. A per-candidate record
declaring the advisory kind would be consumable as an advisory in its own right —
the boundary D7 draws by naming, defeated by a field default. D7's pairing is
unaffected: both types are still ratified together, but only one is addressed to an
authority.

`[V]` `tests/test_advisory_contract_shape.py` requires the kind on `ProposerAdvisory`
and bars `CandidateAdvisory` from declaring it or any other kind in this capability's
namespace. The reader is self-tested against all three spellings a type can declare a
kind through, so a narrowed reader fails rather than reporting a clean record.

## O-4 — ASCII identifiers, and only identifiers

Identifier and reference fields are validated against `^[A-Za-z0-9][A-Za-z0-9._:/-]*$`.
The restriction applies to identifiers and references only — never to human-readable
text, claims, reasons or summaries.

`[V]` The restriction is required because this capability computes identity through
`ugence_jcs` with an empty `nfc_paths` profile: no string is Unicode-normalized before
canonicalization, so two normalization forms of one identifier produce two identities
while reading identically. `tests/test_identifier_normalization.py` demonstrates this
against the substrate rather than asserting it, and fails if a non-empty profile is
ever passed.

`[I]` The scope limit is not a softening. Identifiers are matched, routed and joined
on, so an ambiguity there corrupts identity; free text is carried, not matched, and an
ASCII bar on a reason or a summary would reject the languages those are written in —
a defect rather than a safeguard.

`[V]` The guard classifies fields from an **exact pinned per-contract registry**, not
from name shape: `tests/s1_specification_mirror.py` declares `FIELD_CLASSIFICATION`,
an exact mirror of the C5 tables of
`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`,
in which an unregistered field is a failure rather than a skip. An earlier revision of
that guard classified by name suffix; **I5** of the specification gives why suffix
inference alone was insufficient and names the six fields it reached as neither
identifiers nor text. The
patterns are pinned by equality, and their application is pinned too: `re.match` admits
a trailing newline against `$` and `re.fullmatch` does not, so stating a pattern without
stating the application would leave the rule one convenience call away from admitting a
value it names as invalid.

## Owner decisions OD-1 – OD-5 — all resolved

**OD-1 – OD-4 are ratified 2026-08-25 and OD-5 is ratified 2026-08-26**, recorded here
so this artifact does not report a
clean record its own subordinate documents contradict, nor a cleaner one than the
enforcement supports. D6–D10 close every question this artifact previously carried as
open, and O-1 – O-4 close the four the S1 enforcement audit raised; OD-1 – OD-4 were
raised afterwards, by auditing those guards against representative contract shapes and
by reconciling this artifact with
`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`,
where each is stated in full with its rider, its enforcement design and its three
statuses. OD-5 was raised separately, on the relationship between reasoning functions
and reasoning strategies, and was ruled **not** to bear on contract shape: it defers the
strategy permission concept and its vocabulary together to S2. OD-4 is the one decision of
the five that bears on contract shape; it is resolved below and the specification
implements the resolution.

**No ruling is outstanding on any of the five.** Three statuses are distinguished
throughout and must not be collapsed: a **decision is ratified**; a **named guard
implements** it in `packages/capabilities/agentic-proposer/tests/`; and **S1 production
implementation is authorized on merge** under A12, independently of both. A guard that
enforces a ratified decision authorizes no production contract — the independent review
and the merge do, and neither is a consequence of the guard. The *Enforcement* column
below records the second axis only; the decisions themselves are closed.

| Id | Decision | Bears on contract shape | Enforcement |
| --- | --- | --- | --- |
| **OD-1** — **RATIFIED 2026-08-25** | `primary_function` and `declared_strategy` are classified **C5c** human-readable free text rather than C5b canonical tokens, on the ground that neither is reachable from `P_unsigned`, so O-4's Unicode hazard does not reach them and the stricter class could only reject lawful values. Reclassifying either to C5b, while it stays outside `P_unsigned`, is a narrowing needing no new ratification. **Ratified rider:** the classification rests on unreachability, not on the values, so making either field **identity-participating** requires a **separately ratified normalization profile** — C6 freezes `nfc_paths` empty and the identity function normalises nothing — and must not be done by reclassifying to C5b in passing. | no | `[V]` carried by `FIELD_CLASSIFICATION`, declared in `tests/s1_specification_mirror.py` and enforced by `tests/test_identifier_normalization.py`, which pins `primary_function` and `declared_strategy` as C5c and asserts they carry no pattern constraint of any kind |
| **OD-2** — **RATIFIED 2026-08-25** | `pydantic` loads `socket` while constructing a `BaseModel`, which `tests/test_boundaries.py` forbids as a whole-process assertion. Every S1 contract is a `BaseModel` and `pydantic>=2` is a ratified dependency, so the first contract module fails that guard for a reason unrelated to this package's authority. **Resolved:** exempt exactly the transitive route and keep the bar on any direct import; dropping `socket` from `FORBIDDEN` is rejected. **Ratified enforcement design:** direct-source checks on `src/` that consult no runtime module table; a baseline comparison against the module table produced by the approved dependencies alone, recomputed rather than hand-listed; and negative controls proving the guard still fails on a direct import, on a forbidden module outside the baseline, and on a locally written indirection. **Ceiling disclosed:** `[V]` a static scan cannot see a module name assembled at runtime, supplied externally or reached by reflection, so no design here closes the dynamic-import route (K.5). `[V]` What the guard establishes is that nothing in `src/` imports `socket` statically or through any of the enumerated dynamic spellings, and that this package adds no forbidden root beyond its approved-dependency baseline — not that no runtime path can reach a socket. | no | `[V]` **implemented** — `tests/test_boundaries.py`: the five-layer probe, `DEPENDENCY_BASELINE_MODULES` derived from the declared dependency registry, `_BASELINE_SETUP` pinned by equality, and negative controls including a widened-baseline self-test |
| **OD-3** — **RATIFIED 2026-08-25** | O-1's dependent-field set is matched by name alone, so `CandidateAdvisory.requested_review_action` — the candidate's own required, non-null routing — is caught as if it were selection-dependent. **Resolved:** `DEPENDENT_FIELDS` is scoped to the **bearer contract**, pinned by bearer **and** field name and never by field name alone. The **three** dependent fields are selection-dependent on `ProposerAdvisory` only, coupled to its `selected_candidate_id` selector, which is held separately and is not itself a dependent field. | no | `[V]` **implemented** — `tests/test_selection_dependent_fields.py`: `SELECTION_COUPLING`, `NON_BEARERS_SHARING_A_FIELD_NAME`, two self-tests pinning both by equality and asserting them disjoint, and behavioural probes over a complete required-field fixture |
| **OD-4** — **RATIFIED 2026-08-25, resolved (a)** | D7 above says `ProposerAdvisory` carries per-candidate `CandidateAdvisory` entries; an earlier revision of the specification instead had it reference an `AdvisoryCandidateSet` by `candidate_set_id`. `[V]` That departure was **not** forced by the rival-identity walk, which bars only nested `ToolObservation` and reaches no field of `CandidateAdvisory`. **Resolution (a): restore the nesting D7 requires.** `ProposerAdvisory` carries an immutable `candidates` sequence of `CandidateAdvisory`, ordered ascending by `candidate_id`, participating in `P_unsigned`; `candidate_set_id` is retained as the reference to `AdvisoryCandidateSet`, which stays a **top-level contract** and is not nested; the two candidate lists must correspond exactly in membership, order and content, checked by the builder and by the independent replay verifier. `ToolObservation` stays referenced by id, which A3/the rival-identity walk does force. **Rejected alternative:** reference by id, ratified as an amendment narrowing D7 — rejected because it deviates from ratified text, leaves candidate dispositions, `is_eligible` Booleans and evidence references outside the advisory digest, and leaves an amended candidate set undetectable by replay. | **yes — resolved** | `[V]` **implemented** — `tests/test_advisory_contract_shape.py` discharges I7.11 on representative shapes: it bars a nested `ToolObservation`, **requires** a nested `CandidateAdvisory` sequence so a reversion to reference-by-id fails loudly, and bars any second identity on the candidate |

| **OD-5** — **RATIFIED 2026-08-26** | **Reasoning functions and reasoning strategies are different things, and only the first is a role's purpose.** Four parts. **(i) R-3's lifecycle is unchanged.** A reasoning strategy is a **method label**, not a process state: `ProposerProcessState` gains and loses nothing, and R-3's forward-only subsequence rule, R-4's agreement rule and the bar on representing execution state all stand as ratified. Strategies **operate within** that lifecycle. **(ii) The four-way distinction is preserved and stated:** `primary_function` is the role's organizational purpose; a role's **permitted reasoning strategies** — an S2 concept, not an S1 field — is the set of methods the role may select among; `declared_strategy` is the method the process record asserts was used; and `terminal_outcome` is where the work ended. Three of the four are S1 fields; the second is named as a concept so the distinction can be stated whole. **Evidence collection and verification remain contract mechanisms, and abstention and escalation remain outcomes** — none of the three is a reasoning strategy. **(iii) `permitted_reasoning_strategies` and its vocabulary are deferred together to S2.** **No field is added to `CognitiveRoleContract`, and OD-5 does not change S1 contract shape:** D2's cardinality stays 10 and the C5d roster stays at five fields. The concept and the vocabulary that gives it content arrive together, so the field is declared once, in its ratified form, against a vocabulary that already exists. **Rejected alternative — reserve it now as a C5d empty-only list.** Rejected because a reserved list would have had to be **retyped, revalidated and stripped of its default** to reach the intended allowlist, which rejects an empty list; reserving would therefore not have spared a schema change, which is the one thing reservation normally buys, while it would have cost three disclosed consequences — every conformant S1 pair internally unsatisfiable on this axis, every S1-era role contract carrying the one value the ratified form must refuse, and every stored contract needing reissue at the transition. `[R]` No member, spelling, bound or default of the eventual vocabulary is ratified, and none is ratified by deferring it. **(iv) S1 neither selects, validates nor cryptographically binds a reasoning strategy.** `declared_strategy` is metadata outside `P_unsigned`, declaration does not establish conformance, and strategy selection and enforcement are S2's in whole. **No strategy catalogue is drafted or ratified by this decision, and no individual strategy is named anywhere in it.** | **no** — no field added, no cardinality changed, no classification roster changed, and no field type, vocabulary or equation term changed; every part of the ruling states what S1 does not do, or records a distinction so it is not collapsed later | `[V]` **implemented** — `tests/test_advisory_contract_shape.py` (`declared_strategy` absent from the `P_unsigned` projection); `tests/s1_specification_mirror.py` and `tests/test_identifier_normalization.py`, whose ten-field `CONTRACT_CARDINALITY` entry and five-entry `C5D_ENTRIES` pin now hold the deferred field **out**, failing if it is reintroduced without a ruling; and `tests/test_documentation_consistency.py` (a **heuristic spot-check**, not coverage of a class: it classifies each sentence by actor, refusing a claim of selection, validation or binding whose subject is S1 or something inside it, and passing the same claim attributed to S2. `[I]` It is a regex over English prose and is **not** proof that no such claim can be written; what it is proven against is a named corpus of claims it must catch — including spellings two audits found escaping earlier versions — and correct statements it must leave alone, among them true statements about S2, which an earlier actor-blind version wrongly flagged) |

None of OD-1 – OD-3 changes a contract, a field type, a cardinality, a vocabulary or
an equation term; each is about a guard or a dependency, and OD-5 changes none of them
either. OD-4 bears on contract shape, and Part D of the specification is written for it. The *decisions* are
ratified, and the guards named above enforce them. Neither fact authorizes production
code.

`[R]` markers elsewhere above are implementation obligations that S1 must
discharge — mechanical enforcement of D6's standing rule, D7's contract shape and
D8's export bound — not unratified decisions.

### Guard evidence and enforcement limitations *(subordinate to the table above)*

The table is the decision record. What follows is implementation detail beneath it: how
each ratified decision is enforced, and where that enforcement stops. Nothing here is a
second ratification, and none of it is an authorization to write production contracts.

**OD-1 — the three-way classification the registry carries.** O-4's classification is
assigned per field rather than inferred, in the categories C5 of the specification
defines, plus the mechanical C5d class for the reserved lists that admit no value:

| Category | Rule | Pattern |
| --- | --- | --- |
| C5a — identifier or reference | an opaque handle other parties match, route or join on | `^[A-Za-z0-9][A-Za-z0-9._:/-]*$` |
| C5b — canonical symbolic token | a vocabulary term matched by equality against an allowlist | `^[A-Za-z0-9][A-Za-z0-9._:-]*$` |
| C5c — human-readable free text | carried for a person to read, never matched on | **none — no pattern of any kind** |
| C5d — structurally empty reserved list | rejects every non-empty value | none; emptiness is the whole rule |

`[I]` C5b is C5a **minus the path separator**, and the difference is semantic rather
than cosmetic. A C5a value is carried and compared whole; a C5b value is the operand of
a membership test — `tool_name in permitted_tool_scopes` — and a path-shaped spelling
invites a consumer to split or normalize it before comparing, which would make the
comparison depend on the consumer.

`[V]` Suffix inference could not carry this. Six fields — `agent_version`, `tool_name`,
`allowed_source_scopes`, `excluded_data_classes`, `permitted_tool_scopes` and
`tool_invocations` — end in no identifier suffix and carry no free-text marker, so
inference classified them as neither and they were checked by nothing at all.
`tool_name` is the sharpest case: it is matched by equality against
`permitted_tool_scopes`, so an unnormalized spelling changes an eligibility outcome.
`FIELD_CLASSIFICATION` mirrors the specification's C5 tables exactly — class set, field
set per class and C5 category per field, each pinned by equality — and every C5a and
C5b entry is mutation-pinned, so reclassifying any one of them to another category, or
to an unregistered one, fails.

`[V]` **Enforcement limitation.** The registry is a mirror, not an authority: it
originates no field and reinterprets none. Its completeness check binds only once a
production contract surface exists in `src/`; until then the registry is verified
against the specification and against temporary representative shapes, not against a
declared contract module.

**OD-2 — networking authority, not module residency.** The invariant prohibits the
Agentic Proposer from **possessing or exercising networking authority**. It does not
prohibit an approved runtime dependency from internally loading a standard-library
module while constructing schemas. `[V]` The premise is demonstrated rather than
assumed: bare `import pydantic` does **not** load `socket`; *defining any* `BaseModel`
does, through pydantic-core's schema build. Every S1 contract is a `BaseModel`, so a
whole-process `sys.modules` assertion would fail on the first contract module for a
reason unrelated to this package's authority. Enforcement in `tests/test_boundaries.py`
is layered:

1. a static scan rejecting direct imports of `socket` and the other forbidden roots
   from production source;
2. the same scan extended to `from … import …`, aliases, module-qualified use, and the
   dynamic-import spellings — a literal passed to `importlib.import_module` or
   `__import__`, a literal bound to a local name and then passed to either, a forbidden
   module named inside `exec(...)` or `eval(...)`, and the prohibited relative-import
   spellings;
3. a fresh-interpreter probe that establishes the approved dependency baseline first —
   import pydantic, define a minimal model — then imports this package and asserts it
   introduces **no additional** forbidden module roots beyond that baseline;
4. the declared-dependency allowlist, from which the baseline is derived rather than
   hand-listed, so the exemption cannot authorize a new networking library, and a
   baseline widened with an extra `import socket` fails a self-test;
5. negative controls for every spelling above, proving a direct `socket` import or use
   in this package still fails even though pydantic's transitive load is permitted.

`[I]` **The enforcement ceiling, stated exactly.** Layers 1–2 read source and an AST.
They catch every declared import, alias, `from` import, module-qualified use, literal
dynamic import, name-bound dynamic import, and `exec`/`eval` of an import written as a
literal. They do **not** catch arbitrary runtime composition: a module name assembled by
a helper and returned as an ordinary string, supplied externally, read from a file, an
environment variable or a data structure, or reached by reflection. Those are
undecidable by static scanning and are **not** proven absent by a green suite; they
remain subject to review, packaging and runtime isolation. Layer 3 compares module sets,
so it catches an indirect load whatever spelled it, but only along the import path the
probe executes, and once `socket` is in the baseline it structurally cannot see a direct
import — which is why layers 1–2 are not optional. **The invariant remains architectural
and review-enforced; these guards are defence-in-depth, not a proof.**

**OD-3 — the coupling is scoped to its bearer, and enforced behaviourally.** O-1's
dependent-field coupling applies to **`ProposerAdvisory` and to nothing else**: bearer
`ProposerAdvisory`, selector `selected_candidate_id`, dependents
`recommended_disposition`, `requested_review_action` and
`requested_review_destination_role_ref`. Fields are **not** classified by name globally
across unrelated contracts; `CandidateAdvisory.requested_review_action` is the
candidate's own required, non-null proposed routing and is not nullable merely because
`ProposerAdvisory` has a selection-dependent field of the same name.

`[V]` Enforcement is **behavioural first**. A representative `ProposerAdvisory` is
constructed from a complete valid fixture supplying every required field, and the four
coupling cases are exercised as live validation outcomes: a null selector with a
non-null dependent is rejected; a non-null selector with any null dependent is rejected;
a null selector with all three dependents null is accepted; a non-null selector with all
three non-null is accepted locally. A `CandidateAdvisory` bearing the same field name
keeps it required and non-null and is not reached by the bearer-scoped rule. Static AST
inspection is retained as a **supplemental** layer and is not evidence of behaviour: a
mutant validator that names all four fields and enforces nothing passes the AST layer
and is killed by the behavioural probes.

`[I]` The coupling is enforced in **both directions** and remains a **local** invariant:
a model validator holds `candidate_set_id`, not the set, so it establishes nothing about
the referenced `AdvisoryCandidateSet`. Correspondence between a dependent value and the
selected candidate is R-1b — the builder's obligation and an independent replay
verifier's — and O-1's second clause continues to bind the stage that has candidates.

**OD-4 — the composition is pinned in both directions.** `[V]` The rival-identity walk
is run against the corrected nested candidate graph: `ProposerAdvisory` reaches every
`CandidateAdvisory` field, `reachable & RIVAL_IDENTITY_FIELDS` is empty for both
advisory roots, `ToolObservation` is unreachable from either at any depth, and a mutant
that nests an observation, that adds a per-candidate digest field, or that removes the
nested `candidates` sequence each fail.

**What no guard in this package establishes.** None of them constitutes a proof against
arbitrary runtime behaviour, and none of them arms fully until a production contract
surface exists: the contract-shape, classification and coupling guards are dormant on
`src/` as it stands and are exercised against temporary representative shapes derived
from the specification. That dormancy is the design — a guard written before its surface
— and it is stated here so a green suite is not read as a verified contract.

---

## Ratification addendum — 2026-08-24: the D2 interpretation and the S1 contract specification

This addendum is additive. **No D1–D10 text above is rewritten**; each remains the
verbatim record of what was ratified when it was ratified. What follows is a dated
extension recording ratifications that landed after D10.

**Ordering dependency, resolved.** An earlier revision of this addendum cross-referenced
a *Ratified refinements (O-1 – O-4)* section this artifact did not yet carry, so
O-1 – O-4 were cited throughout it and its subordinate documents while being defined in
none of them. The section is now carried **above, in this artifact**, which is its single
canonical location; the duplicate that once stood in the guard documents is gone. A5–A8
below still do not restate it; they record only how the four bear on the contract
specification, so each decision has one account and not two.

### Provenance

| Fact | Value |
| --- | --- |
| Base | the repository default branch at merge commit `e28538eb454fce6008e94e0772e0fd09c9c7ea7f` (PR #1474) |
| Package version | `0.0.1`, unchanged |
| Public-API snapshot | none, unchanged |
| Platform-freeze substantive digest | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`, unchanged |

### A1 — D2 is a behavioural and architectural invariant

D2 above ratifies the identity **substrate**. This addendum ratifies what D2 **means**,
which `S1_ENFORCEMENT.md` previously carried as an open `[R]` question:

> D2 is a behavioural and architectural invariant. An advisory identity is valid only
> when an independent verifier recomputes it from the frozen unsigned advisory
> projection using the ratified `ugence-jcs` canonicalization profile and obtains the
> exact stored digest.
>
> Static scanning remains a mandatory release guard for declared imports, ordinary
> aliases, known dynamic-import forms and accidental local canonicalization. It is
> defence-in-depth and does not constitute proof against every intentionally obfuscated
> Python construction.
>
> The helper-assembled `__import__` escape is a disclosed limitation of static
> enforcement. It does not authorize local hashing. S1 must additionally provide
> package-owned construction, independent canonical replay, frozen-profile tests and
> installed-distribution verification.

Recorded in full at `packages/capabilities/agentic-proposer/docs/S1_ENFORCEMENT.md`.

### A2 — V13: a proposal requires readiness

> `TerminalOutcome.PROPOSAL` requires `evaluate_readiness(...) is True` for the selected
> candidate, independently recomputed by `build_proposer_advisory`.

Because S1 cannot construct `DomainCheckCompletion.COMPLETE`, readiness is `False` for
every candidate S1 can construct. Therefore S1 cannot emit `PROPOSAL`; every S1
authority-facing advisory has `selected_candidate_id = None`; and the only terminal
outcomes S1 may emit are `NEED_EVIDENCE`, `ABSTAIN` and `ESCALATE`.

This is fail-closed and intended. A stage that authorizes no domain check must not be
able to reach the proposer's strongest classification.

### A3 — `advisory_version`

> `advisory_version` is a required, non-null, identity-participating `str` matching
> `^[1-9][0-9]*$`. Its initial value is `"1"`. `build_advisory_revision` increments it
> as canonical positive decimal without leading zeroes.

It is not `int`, because `ugence-jcs` rejects bare JSON numbers; it is not
`Literal["1"]`, because that would make a revision unconstructible.
`kind = "ugence.agentic_proposer.advisory.v0"` remains a separate axis: `kind`
identifies the schema family, `advisory_version` identifies the advisory instance
revision. They are not redundant and not inconsistent.

### A4 — `ReviewAction`

> `ReviewAction` contains exactly `ROUTE_APPROVAL_BUNDLE` and
> `CREATE_EXCEPTION_REVIEW_BUNDLE`.

### A5–A8 — O-1 to O-4: recorded once, under *Ratified refinements*

O-1 (selection-dependent fields), O-2 (lifecycle authority, not vocabulary), O-3 (one
kind, one bearer) and O-4 (ASCII identifiers, and only identifiers) are recorded in this
artifact **once**, in the *Ratified refinements (O-1 – O-4)* section above, together
with the *Narrowed by O-2* and *Narrowed by O-3* notes on D8 and D7. That section is the
canonical record and this addendum does not restate it.

What this addendum adds, and that section does not carry, is how the four decisions bear
on the contract specification:

* **O-1** is implemented in the specification at **two distinct levels**. A local
  `ProposerAdvisory` model validator couples the presence of `selected_candidate_id` to
  the joint presence of `recommended_disposition`, `requested_review_action` and
  `requested_review_destination_role_ref`, and their joint absence to its absence. A
  separate cross-contract obligation on `build_proposer_advisory` and on an independent
  replay verifier resolves the referenced `AdvisoryCandidateSet` and checks
  correspondence. **The local validator does not, and cannot, establish the second**: it
  holds `candidate_set_id`, not the set. `ProposerAdvisory` therefore carries a mirrored
  `selected_candidate_id` — required as a field, nullable as a value, ASCII-constrained
  when non-null, identity-participating in `P_unsigned` — without which the local
  coupling would not be decidable on the advisory at all. Under A2 (V13) all four are
  `None` in S1; the future-stage branch is preserved and unreachable.
* **O-4** is implemented as an explicit **classification assigned per field** rather
  than inferred from name shape: three semantic categories — identifier or reference
  (C5a), canonical symbolic token (C5b), human-readable free text (C5c) — plus a fourth,
  **mechanical** category, C5d, for the reserved lists that reject every non-empty value
  (`selection_reason_codes`, `reason_codes`, `deterministic_checks`,
  `semantic_audit_refs`). C5d exists because a `list[str]` admitting no value has no
  content class, and assigning it one of the three would state something false about a
  value that cannot exist. Six fields (`agent_version`, `tool_name`,
  `allowed_source_scopes`, `excluded_data_classes`, `permitted_tool_scopes`,
  `tool_invocations`) are symbolic tokens that a suffix rule reaches as neither
  identifiers nor text; they carry their own canonical token pattern and are not
  silently treated as free text. C5c is restated as admitting **no pattern or regex
  constraint of any kind**, not merely neither of the two named patterns. The guards must
  classify from an exact pinned per-contract field registry that also carries non-`str`
  fields — `AgentIdentityRef.lifecycle_state` in particular — with mutation tests per
  category.
* **O-2 and O-3** are enforced as ratified. The specification records the guard branch's
  grammatical/syntactic O-2 rule as the preferred implementation, and its
  required-on-`ProposerAdvisory`, barred-on-`CandidateAdvisory` O-3 rule as stronger
  than the narrowing first proposed.

### A9 — The S1 contract and equation specification

`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`
is the canonical, implementation-ready S1 specification, status
`CONTRACT SPECIFICATION FROZEN FOR IMPLEMENTATION` (frozen 2026-08-26), scoped to S1 contracts and deterministic equations
only. It records the eight top-level contracts (`AgentIdentityRef`,
`CognitiveRoleContract`, `WorkMandate`, `BoundedContextEnvelope`, `ToolObservation`,
`AdvisoryCandidateSet`, `ProposerAdvisory`, `ProposerProcessRecord`) with
`CandidateAdvisory` and `ProposerProcessStateTransition` as nested public shapes; every
field with its type, requiredness, nullability, default, cardinality, closed vocabulary,
validation, ownership and canonical-identity participation; the frozen `P_unsigned`
projection under an empty-`set_paths`, empty-`nfc_paths` profile; and every equation
signature, including the independent verification function A1 requires.

In that document `ProposerAdvisory` **carries its `CandidateAdvisory` entries** and
references every other input by identifier.

`[V]` One half of that composition is forced: the merged rival-identity walk in
`tests/test_advisory_contract_shape.py` reaches `content_hash` through a nested
`ToolObservation` and fails, and `content_hash` is on that list precisely to prevent a
second identity. So `ToolObservation` is referenced, not carried, and the specification
records that as a standing prohibition with a test obligation.

`[V]` The other half is **not** forced, and an earlier revision of this section said it
was. That walk matches `RIVAL_IDENTITY_FIELDS` by exact name, and no field of
`CandidateAdvisory` is a member, so nesting `CandidateAdvisory` fails nothing. D7 above
says `ProposerAdvisory` carries per-candidate `CandidateAdvisory` entries, and an earlier
revision of the specification departed from that by referencing them through
`candidate_set_id`. **OD-4 is now resolved (a)** under *Owner decisions OD-1 – OD-5*: the
nesting D7 requires is restored, the candidates participate in `P_unsigned`,
`candidate_set_id` is retained as a reference to `AdvisoryCandidateSet` — which remains a
top-level contract — and the two candidate lists must correspond in membership, order and
content. `[R]` The rival-identity reachability analysis was re-run against the corrected
object graph and no prohibited identity field becomes reachable; that run is `[R]` until
a contract module exists. The residual limitation recorded in that document is now only
that an advisory digest binds the *identifiers* of the inputs it still references — the
observations and the governance artifacts — and not their bodies.

It authorizes no invoice-domain check, no reason-code catalogue, no adapter, no LLM, no
semantic auditor, no HTTP service, no authorization, no clearance and no execution.
D1–D10 and A1–A8 remain authoritative over it.

### A10 — The superseded draft

The specification proposed on branch `claude/d2-enforcement-ratification-si5lmm`
(PR #1475) is a **rejected draft** and must not be used
for implementation: its authored field sets diverged from the owner's reconciled
contract set on all eight contracts and on both equations, and its nested composition
fails the guard described in A9. Several of its individual judgments were correct — the
prohibition on numeric fields, the honest statement that an exported model's constructor
remains reachable, recompute-and-reject as the operative eligibility guarantee,
`strict=True`, and reading the substrate version from installed distribution metadata —
and are carried forward. PR #1475 is left unaltered as a record of that scrutiny.

### A11 — Implementation was unauthorized until review and merge

`[V]` This addendum and the documents it references are **documentation only**. No
`src/` module, test, `pyproject.toml`, `version.py`, public API, CI workflow or
platform-freeze artifact is changed by them. The version stays `0.0.1`, no
`public_api.json` is created, and the freeze digest is unchanged.

**Implementation of the S1 contracts and equations remains unauthorized until this
documentation pull request is independently reviewed and merged.** `[V]` **Both
conditions are met as of A12 below**, which records the freeze; A11 stands as the rule
that was applied, not as a gate still standing.

### A12 — The specification is frozen for implementation

**Declared by the owner on 2026-08-26.** The S1 contract and equation specification's
status becomes `CONTRACT SPECIFICATION FROZEN FOR IMPLEMENTATION`.

**What the freeze establishes.** The contract surface is **closed to change**. A field,
type, cardinality, vocabulary, equation term or validation rule may be altered only by a
**ratified amendment recorded in the owner-decision table above** — never by an
implementation change reconciling the specification to code that was written against a
different reading. Where code and the specification disagree, the specification is right
and the code is wrong.

**What the freeze rests on.** `[V]` A11's two conditions. Independent review: the
specification and its guards were audited across successive rounds, each conducted
against the repository rather than against the author's account of it, and each finding
was either fixed or recorded — among them a lifecycle guard that matched vocabulary
instead of authority, a registry that classified by name suffix, an enforcement scan
narrower than the coverage claimed for it, and four stale cross-references left by a
section rename. `[V]` Merge: this pull request. **The freeze takes effect on merge**, and
before merge this section states an intent rather than a fact.

**What the freeze does *not* establish.** Three things, stated so the declaration is not
read as more than it is:

* `[R]` **It is not a claim that the specification is correct.** It is a decision to stop
  changing it and to find the remaining defects by implementing against it. A frozen
  specification is one whose errors are now discovered as amendments rather than as
  edits.
* `[G]` **It does not discharge the Part I obligations.** I1, I6 and the unbuilt parts of
  I7 remain outstanding. Those are implementation work — guards to be armed against a
  contract module that does not yet exist — not specification questions, and the freeze
  neither closes them nor authorizes skipping them.
* `[R]` **It does not ratify anything the specification marks `[R]`.** The reasoning
  strategy vocabulary deferred to S2 (OD-5(iii)), the normalization profile OD-1's rider
  requires, and every guard claim verified only against a representative shape stay
  exactly as they are. Each is to be re-verified when the first contract module lands.

`[V]` No `src/` module, test, `pyproject.toml`, `version.py`, public API, CI workflow or
platform-freeze artifact is changed by this declaration. The version stays `0.0.1` and
the substantive freeze digest is unchanged.

### Owner decisions, and what actually gates S1

A1–A8 close every question the contract specification's *equations, vocabularies and
enforcement interpretation* depend on. They do not close everything, and what remains is
not a ruling.

**OD-1 – OD-4 are all resolved, ratified 2026-08-25, and OD-5 is resolved, ratified
2026-08-26**; all five are recorded once, under *Owner decisions OD-1 – OD-5* above.
**Of the five, OD-4 bears on contract shape; OD-5 was ruled not to.** **OD-4 is resolved (a)**: `ProposerAdvisory` carries its `CandidateAdvisory` entries as D7 says, and
reference-by-id is the rejected alternative. OD-1 carries a ratified rider — future
identity participation for `primary_function` or `declared_strategy` requires a
separately ratified normalization profile — and OD-2 carries a ratified enforcement
design: direct-source checks, an approved-dependency baseline comparison, and negative
controls, with the dynamic-import ceiling disclosed rather than papered over.

**Each of OD-1 – OD-5 carries three statuses, and they must not be collapsed.** The
owner decision is **ratified**; a **named guard implements** it — `FIELD_CLASSIFICATION`,
declared in `tests/s1_specification_mirror.py` and enforced by
`tests/test_identifier_normalization.py`, for OD-1; the layered probe in
`tests/test_boundaries.py` for OD-2, the bearer-scoped coupling in
`tests/test_selection_dependent_fields.py` for OD-3, the composition assertions in
`tests/test_advisory_contract_shape.py` for OD-4, and — for OD-5 — the `P_unsigned`
projection-absence assertion for `declared_strategy` in the same module, the
strategy-authority document scan in `tests/test_documentation_consistency.py`, and the
ten-field cardinality and five-entry `C5D_ENTRIES` pin that now hold the deferred field
out; and **S1 production implementation
is authorized on merge under A12**, independently of both: A11's
condition is discharged by the freeze, and what remains is the undischarged Part I
obligations. A ratified decision is not an implemented guard, and an implemented guard
was never an authorization — the review and the merge are.

The specification's status is therefore `CONTRACT SPECIFICATION FROZEN FOR IMPLEMENTATION`
(frozen 2026-08-26; see *A12*). No ruling gates the first contract module, and A11's
review condition is discharged; what remains are the undischarged Part I obligations,
which are implementation work rather than owner questions.

The `[R]` markers elsewhere in this artifact are implementation obligations for S1, not
unratified decisions.

