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
they are recorded under *Ratified resolutions* below. No owner decision remains
open, so S1 is unblocked on ratification grounds.

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

## Open owner decisions

None. D6–D10 close every question this artifact previously carried as open.

`[R]` markers that remain above are implementation obligations that S1 must
discharge — mechanical enforcement of D6's standing rule, D7's contract shape and
D8's export bound — not unratified decisions.

---

## Ratification addendum — 2026-08-24: the D2 addendum and the S1 contract specification

This addendum is additive. **No D1–D10 text above is rewritten**; each remains the
verbatim record of what was ratified when it was ratified. What follows is a dated
extension recording two ratifications that landed after D10.

### Provenance

| Fact | Value |
| --- | --- |
| Pull request | **#1474** — Agentic Proposer Stage S1: pre-S1 enforcement infrastructure (D6/D7/D8) |
| Merge commit | **`e28538eb454fce6008e94e0772e0fd09c9c7ea7f`** |
| Base for this addendum | the repository default branch at that merge commit |

`[V]` `e28538eb454fce6008e94e0772e0fd09c9c7ea7f` is the tip of the default branch and
carries PR #1474. `[V]` At that commit the package version is `0.0.1`, no
`public_api.json` exists, `src/` is the unchanged S0 tree (last touched by the S0
commit `c6567cf92`), and the platform-freeze substantive digest is
`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.

### A1 — D2 addendum: D2 is a behavioral and architectural invariant

D2 above ratifies the identity **substrate**. This addendum ratifies what D2
**means**, which `S1_ENFORCEMENT.md` previously carried as an open `[R]` question:

> D2 is a behavioral and architectural invariant. An advisory identity is valid only
> when an independent verifier recomputes it from the frozen unsigned advisory
> projection using the ratified `ugence-jcs` canonicalization profile and obtains the
> exact stored digest.
>
> Static scanning remains a mandatory release guard for declared imports, ordinary
> aliases, known dynamic-import forms and accidental local canonicalization. It is
> defense-in-depth and does not constitute proof against every intentionally
> obfuscated Python construction.
>
> The helper-assembled `__import__` escape is a disclosed limitation of static
> enforcement. It does not authorize local hashing. S1 must additionally provide
> package-owned construction, independent canonical replay, frozen-profile tests and
> installed-distribution verification.

`[V]` Recorded in full at
`packages/capabilities/agentic-proposer/docs/S1_ENFORCEMENT.md`, replacing the `[R]`
section that asked whether D2 meant the invariant or the scan. The disclosed exploit
is preserved there and reclassified as an enforcement limitation.

### A2 — The S1 contract and equation specification

`[V]` `packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_RATIFICATION.md`
is added, status `RATIFIED FOR S1 IMPLEMENTATION`, scoped to S1 contracts and
deterministic equations only. It records literally: the eight top-level contracts
(`AgentIdentityRef`, `CognitiveRoleContract`, `WorkMandate`,
`BoundedContextEnvelope`, `ToolObservation`, `AdvisoryCandidateSet`,
`ProposerAdvisory`, `ProposerProcessRecord`) with `CandidateAdvisory` as a nested
public shape; every field with its type, requiredness, nullability, default,
cardinality, closed vocabulary, validation, ownership, lineage and
canonical-identity participation; the frozen `P_unsigned` projection under an
empty-`set_paths`, empty-`nfc_paths` profile; and the four equation signatures,
including the independent digest-verification function A1 requires.

It authorizes no invoice-domain check, no adapter, no LLM, no semantic auditor, no
HTTP service, no authorization, no clearance and no execution. D1–D10 and A1 remain
authoritative over it, and it resolves any conflict with the earlier external MVP
draft in favour of the committed document.

### A3 — Implementation remains unauthorized

`[V]` This addendum and the two documents it references are **documentation only**.
No `src/` module, test, `pyproject.toml`, `version.py`, public API, CI workflow or
platform-freeze artifact is changed by them. The version stays `0.0.1`, no
`public_api.json` is created, and the freeze digest is unchanged.

**Implementation of the S1 contracts and equations remains unauthorized until this
documentation pull request is independently reviewed and merged.** The specification
distinguishes owner-ratified content from content authored to satisfy it, and
confirming the authored field sets against the owner's reconciled contract set is a
review obligation of that pull request, not a settled fact.

### Open owner decisions

Still none. A1 closes the last `[R]` that `S1_ENFORCEMENT.md` carried as a decision;
the `[R]` markers remaining in this artifact are implementation obligations for S1.
