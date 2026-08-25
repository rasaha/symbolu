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
they are recorded under *Ratified resolutions* below. OD-1 – OD-4, raised later by
auditing the S1 enforcement guards and reconciling this artifact with the contract
specification, were ratified 2026-08-25 and are recorded under *Owner decisions
OD-1 – OD-4* below. **No owner decision remains open, so S1 is unblocked on ratification grounds** —
and on ratification grounds only. **Three** things still gate S1 code, none of them a
ruling: the O-1 – O-4 and OD-1 – OD-3 enforcement guards are implemented on a branch
that is **not merged**; the Part I implementation obligations in the contract
specification are undischarged; and A11 keeps implementation unauthorized until this
documentation is independently reviewed and merged. "Unblocked on ratification grounds"
is therefore not "authorized to implement", and this artifact does not claim it is.

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

> **Provenance of this section.** O-1 – O-4 were first written on branch
> `claude/governance-refinements-o1-o4-k96vbz`. They are recorded **here**, in this
> artifact, because a decision that exists only on an unmerged branch is not a record.
> Documents on this branch previously cross-referenced an *O-1 – O-4* section that no
> merged revision of this artifact carried, leaving the four decisions cited and
> undefined. The text below is that section, moved in verbatim in substance.
>
> `[R]` The `[V]` claims inside it are read from that branch's tests, which are not
> merged here. Each is to be re-verified when that branch merges.

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

`[R]` The guard classifies fields from an **exact pinned per-contract registry**, not
from name shape. This is read from the unmerged guard branch
`claude/governance-refinements-o1-o4-k96vbz` at head `96510a1c4` and is **not** a fact
about any merged branch: at `30945dac8` the same guard classified by name suffix. It is
to be re-verified on merge, and it matches the `[R]` labelling of **I5** of
`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`,
which gives why suffix inference alone was insufficient and names the six fields it
reached as neither identifiers nor text. The
patterns are pinned by equality, and their application is pinned too: `re.match` admits
a trailing newline against `$` and `re.fullmatch` does not, so stating a pattern without
stating the application would leave the rule one convenience call away from admitting a
value it names as invalid.

## Owner decisions OD-1 – OD-4 — all resolved

**All four are ratified 2026-08-25**, recorded here so this artifact does not report a
clean record its own subordinate documents contradict, nor a cleaner one than the
enforcement supports. D6–D10 close every question this artifact previously carried as
open, and O-1 – O-4 close the four the S1 enforcement audit raised; OD-1 – OD-4 were
raised afterwards, by auditing those guards against representative contract shapes and
by reconciling this artifact with
`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`,
where each is stated in full with its rider, its enforcement design and its three
statuses. OD-4 was the only one bearing on contract shape; it is resolved below and the
specification implements the resolution.

**No ruling is outstanding on any of the four.** What is outstanding on OD-1 – OD-3 is
a **merge**: `[R]` the guards are implemented on branch
`claude/governance-refinements-o1-o4-k96vbz` at head `96510a1c4` — including both
corrections the specification's I4 previously reported as outstanding, the O-1 guard's
bearer scoping (OD-3) and the `pydantic`/`socket` boundary probe (OD-2), **both applied
there** — but that branch is not merged, so none of it is a fact about this repository.
`[R]` No further repair is identified. S1 production implementation stays unauthorized
under A11 independently of all of it. The *Enforcement* column below records that second
axis; the decisions themselves are closed.

| Id | Decision | Bears on contract shape | Enforcement |
| --- | --- | --- | --- |
| **OD-1** — **RATIFIED 2026-08-25** | `primary_function` and `declared_strategy` are classified **C5c** human-readable free text rather than C5b canonical tokens, on the ground that neither is reachable from `P_unsigned`, so O-4's Unicode hazard does not reach them and the stricter class could only reject lawful values. Reclassifying either to C5b, while it stays outside `P_unsigned`, is a narrowing needing no new ratification. **Ratified rider:** the classification rests on unreachability, not on the values, so making either field **identity-participating** requires a **separately ratified normalization profile** — C6 freezes `nfc_paths` empty and the identity function normalises nothing — and must not be done by reclassifying to C5b in passing. | no | `[R]` carried by the O-4 registry on `96510a1c4`; lands with it |
| **OD-2** — **RATIFIED 2026-08-25** | `pydantic` loads `socket` while constructing a `BaseModel`, which `tests/test_boundaries.py` forbids as a whole-process assertion. Every S1 contract is a `BaseModel` and `pydantic>=2` is a ratified dependency, so the first contract module fails that guard for a reason unrelated to this package's authority. **Resolved:** exempt exactly the transitive route and keep the bar on any direct import; dropping `socket` from `FORBIDDEN` is rejected. **Ratified enforcement design:** direct-source checks on `src/` that consult no runtime module table; a baseline comparison against the module table produced by the approved dependencies alone, recomputed rather than hand-listed; and negative controls proving the guard still fails on a direct import, on a forbidden module outside the baseline, and on a locally written indirection. **Ceiling disclosed:** `[V]` a static scan cannot see a module name assembled at runtime, so no design here closes the dynamic-import route (K.5). `[R]` What the guard establishes — that nothing in `src/` imports `socket` statically and that this package adds no forbidden root beyond its approved-dependency baseline — is read from an unmerged branch and is not that no runtime path can reach a socket. | no | `[R]` **implemented at `96510a1c4`, not merged** — I4.2; the five-layer probe, `DEPENDENCY_BASELINE_MODULES` pinned by equality, and a baseline the test recomputes |
| **OD-3** — **RATIFIED 2026-08-25** | O-1's dependent-field set is matched by name alone, so `CandidateAdvisory.requested_review_action` — the candidate's own required, non-null routing — is caught as if it were selection-dependent. **Resolved:** `DEPENDENT_FIELDS` is scoped to the **bearer contract**, pinned by bearer **and** field name and never by field name alone. The **three** dependent fields are selection-dependent on `ProposerAdvisory` only, coupled to its `selected_candidate_id` selector, which is held separately and is not itself a dependent field. | no | `[R]` **implemented at `96510a1c4`, not merged** — I4.1; `SELECTION_COUPLING`, `NON_BEARERS_SHARING_A_FIELD_NAME`, and three equality self-tests |
| **OD-4** — **RATIFIED 2026-08-25, resolved (a)** | D7 above says `ProposerAdvisory` carries per-candidate `CandidateAdvisory` entries; an earlier revision of the specification instead had it reference an `AdvisoryCandidateSet` by `candidate_set_id`. `[V]` That departure was **not** forced by the rival-identity walk, which bars only nested `ToolObservation` and reaches no field of `CandidateAdvisory`. **Resolution (a): restore the nesting D7 requires.** `ProposerAdvisory` carries an immutable `candidates` sequence of `CandidateAdvisory`, ordered ascending by `candidate_id`, participating in `P_unsigned`; `candidate_set_id` is retained as the reference to `AdvisoryCandidateSet`, which stays a **top-level contract** and is not nested; the two candidate lists must correspond exactly in membership, order and content, checked by the builder and by the independent replay verifier. `ToolObservation` stays referenced by id, which A3/the rival-identity walk does force. **Rejected alternative:** reference by id, ratified as an amendment narrowing D7 — rejected because it deviates from ratified text, leaves candidate dispositions, `is_eligible` Booleans and evidence references outside the advisory digest, and leaves an amended candidate set undetectable by replay. | **yes — resolved** | `[R]` **outstanding** — no guard yet pins the ratified composition; the specification's I7.11 requires a test that bars a nested `ToolObservation` **and requires** a nested `CandidateAdvisory`, so a reversion to reference-by-id fails loudly. `[V]` The merged rival-identity walk in `tests/test_advisory_contract_shape.py` bars the observation half only |

`[R]` The guards enforcing OD-1 – OD-3 live on branch
`claude/governance-refinements-o1-o4-k96vbz`, which is not merged, so their
*enforcement* is pending here and every statement about them is to be re-verified on
merge. The *decisions* are ratified and are not reopened by that. None of the three
changes a contract, a field type, a cardinality, a vocabulary or an equation term.

`[R]` markers elsewhere above are implementation obligations that S1 must
discharge — mechanical enforcement of D6's standing rule, D7's contract shape and
D8's export bound — not unratified decisions.

---

## Ratification addendum — 2026-08-24: the D2 interpretation and the S1 contract specification

This addendum is additive. **No D1–D10 text above is rewritten**; each remains the
verbatim record of what was ratified when it was ratified. What follows is a dated
extension recording ratifications that landed after D10.

**Ordering dependency, resolved.** An earlier revision of this addendum assumed the
*Ratified refinements (O-1 – O-4)* section would arrive with the guard branch
`claude/governance-refinements-o1-o4-k96vbz` and cross-referenced it in the meantime.
That branch is not merged, so the cross-references pointed at nothing and O-1 – O-4 were
cited throughout this artifact and its subordinate documents while being defined in none
of them. The section is now carried **above, in this artifact**. A5–A8 below still do not
restate it; they record only how the four bear on the contract specification, so each
decision has one account and not two. `[R]` Because that branch also carries a copy of
*Ratified refinements (O-1 – O-4)*, the two copies will conflict when it merges: **the
guard branch's copy is the one to drop**, this artifact's being the canonical record.

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
`CONTRACT SPECIFICATION RATIFIED; IMPLEMENTATION AUTHORIZATION PENDING MERGED ENFORCEMENT`, scoped to S1 contracts and deterministic equations
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
`candidate_set_id`. **OD-4 is now resolved (a)** under *Owner decisions OD-1 – OD-4*: the
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

The specification proposed on the unmerged branch
`claude/d2-enforcement-ratification-si5lmm` (PR #1475, head
`4fab9d811ff15f59acf59c1f93db502be999a801`) is a **rejected draft** and must not be used
for implementation: its authored field sets diverged from the owner's reconciled
contract set on all eight contracts and on both equations, and its nested composition
fails the guard described in A9. Several of its individual judgments were correct — the
prohibition on numeric fields, the honest statement that an exported model's constructor
remains reachable, recompute-and-reject as the operative eligibility guarantee,
`strict=True`, and reading the substrate version from installed distribution metadata —
and are carried forward. PR #1475 is left unaltered as a record of that scrutiny.

### A11 — Implementation remains unauthorized

`[V]` This addendum and the documents it references are **documentation only**. No
`src/` module, test, `pyproject.toml`, `version.py`, public API, CI workflow or
platform-freeze artifact is changed by them. The version stays `0.0.1`, no
`public_api.json` is created, and the freeze digest is unchanged.

**Implementation of the S1 contracts and equations remains unauthorized until this
documentation pull request is independently reviewed and merged.**

### Owner decisions, and what actually gates S1

A1–A8 close every question the contract specification's *equations, vocabularies and
enforcement interpretation* depend on. They do not close everything, and what remains is
not a ruling.

**OD-1 – OD-4 are all resolved, ratified 2026-08-25**, and are recorded once, under
*Owner decisions OD-1 – OD-4* above. **OD-4, the only one bearing on contract shape, is resolved
(a)**: `ProposerAdvisory` carries its `CandidateAdvisory` entries as D7 says, and
reference-by-id is the rejected alternative. OD-1 carries a ratified rider — future
identity participation for `primary_function` or `declared_strategy` requires a
separately ratified normalization profile — and OD-2 carries a ratified enforcement
design: direct-source checks, an approved-dependency baseline comparison, and negative
controls, with the dynamic-import ceiling disclosed rather than papered over.

**Each of OD-1 – OD-3 carries three statuses, and they must not be collapsed.** The
owner decision is **resolved**; the enforcement implementation is **pending** on the
unmerged branch `claude/governance-refinements-o1-o4-k96vbz` (head `96510a1c4`), which
`[R]` carries both corrections the specification's I4 previously reported as
outstanding — the O-1 guard's bearer scoping (OD-3) and the `pydantic`/`socket` boundary
probe (OD-2), both applied there — with no further repair identified, so what is
outstanding is that branch's review and merge; and **S1 production implementation is
unauthorized under A11** regardless of either, until this documentation is independently
reviewed and merged.

The specification's status is therefore
`CONTRACT SPECIFICATION RATIFIED; IMPLEMENTATION AUTHORIZATION PENDING MERGED ENFORCEMENT`. No
ruling gates the first contract module — what gates it is merged enforcement and A11.

The `[R]` markers elsewhere in this artifact are implementation obligations for S1, not
unratified decisions.
