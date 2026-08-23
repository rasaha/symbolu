# ADR: Ugence Agentic Proposer — MVP readiness

**Status:** Accepted (readiness record; no public contract frozen)
**Stage:** S0 skeleton, with Stage P (ugence-jcs extraction) complete
**Supersedes:** nothing
**Depends on:** an Agent Constitution document that does not exist (see *Open
architectural dependency*)

This artifact exists so that no public contract is frozen and no version is
declared before the ratified decisions, the missing dependency, and the authority
boundary are on the record. It is a readiness record, not a design.

Evidence labels: `[V]` verified against this repository, `[I]` inferred,
`[R]` requires ratification, `[G]` gap.

---

## Ratified owner decisions

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

`[R]` When that document exists, the CognitiveRoleContract projection must be
re-derived from it rather than promoted as-is. Nothing in this repository should be
read as evidence that the projection anticipates the constitution correctly.

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
must not be named or shaped so as to imply it is that one. `[R]` The name and shape
of that artifact are an S1 decision; no such artifact exists at S0.

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
pins both halves. This is the reading the implementation encodes; `[R]` if the owner
intended `INDETERMINATE` to be reserved everywhere, the semantic-auditor status must
be renamed before the auditor is built.

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

## Owner decisions still open

1. `[R]` The Agent Constitution document, and whether the D1 CognitiveRoleContract
   projection survives contact with it.
2. `[R]` Whether `INDETERMINATE` is reserved everywhere or only in the two positions
   where it reads as an authority claim — the implementation encodes the latter.
3. `[R]` The name and shape of the proposer's recommendation artifact, which must not
   imply it is Agent Runtime's `TransitionProposal`.
4. `[R]` Whether the production CER identity path is ever migrated onto `ugence-jcs`,
   and under what compatibility evidence. Stage P deliberately did not do this.
5. `[R]` Whether `ugence-jcs` is published to an index. It is currently resolvable
   only from a locally built wheel, which every consumer's verifier must build.
