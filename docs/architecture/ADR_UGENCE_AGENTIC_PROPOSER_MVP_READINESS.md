# ADR: Ugence Agentic Proposer — MVP readiness

**Status:** Accepted (readiness record; no public contract frozen), with
Amendment 1 proposed and unratified
**Stage:** S0 skeleton, with Stage P (ugence-jcs extraction) complete
**Supersedes:** nothing
**Depends on:** an Agent Constitution document that does not exist and will not
exist before S1 (see *Open architectural dependency* and **D8**)

This artifact exists so that no public contract is frozen and no version is
declared before the ratified decisions, the missing dependency, and the authority
boundary are on the record. It is a readiness record, not a design.

D1–D5 were ratified before implementation. D6–D10 were ratified after Stage P and
Stage S0 landed, and close every question this artifact previously carried as open;
they are recorded under *Ratified resolutions* below.

**Amendment 1** (below) reopens the record with D11–D14, the S1 proposal-identity
contract. They are **proposed and not ratified**, so S1 is blocked on ratification
grounds until they are filled.

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

D6–D10 closed every question this artifact carried as open through Stage S0.
**Amendment 1** then opened four more: **D11–D14**, the S1 proposal-identity
contract. All four are unratified.

`[R]` markers that remain above are implementation obligations that S1 must
discharge — mechanical enforcement of D6's standing rule, D7's contract shape and
D8's export bound — not unratified decisions.

---

# Amendment 1 — S1 proposal-identity contract (D11–D14)

**Status:** Proposed. **Not ratified.** Each decision below carries an unfilled
ratification line; until those are filled, *Open owner decisions* above is superseded
by this amendment and S1 is **blocked on ratification grounds**.

**Occasion.** `ugence-jcs` 0.2.0 adds one public function,
`canonical_sha256_hex(value, set_paths=..., nfc_paths=...)`
(`packages/jcs/src/ugence_jcs/canon.py:129`), the intended substrate for S1's
Equation 3, `PID = SHA256(JCS(P_unsigned))`.

References below to `packages/jcs/src/ugence_jcs/canon.py` and
`packages/jcs/tests/test_canonical_sha256_hex.py` resolve against commit `582bf633`
(PR #1473), which is not yet merged. Every other `file:line` resolves against the
default branch at `0de0c93a`.

`[V]` The function is safe and is exactly what it claims: `canon.py:137-139` is
literally `hashlib.sha256(canonical_bytes(value, set_paths, nfc_paths)).hexdigest()`,
so it cannot diverge from that expression for any input. `canonical_string`,
`canonical_bytes` and every `ugence_jcs.errors` type are byte-for-byte unchanged,
and the frozen CER V0.2 identity digests still reproduce
(`cer_v0_3/tests/test_cleanroom.py` + `test_forbidden_imports.py`, 14 passed;
`packages/jcs/tests/`, 108 passed; `platform_freeze.verify` substantive digest
`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`).

`[G]` Equation 3 itself is **not** recorded in any committed ADR. `P_unsigned`,
`Equation 3` and `PID = SHA256(…)` return zero hits across `docs/` and
`packages/capabilities/agentic-proposer/`. **D2** ratifies the substrate
(`ugence-jcs` and nothing else) and is silent on the formula, the digest's surface
form, the canonicalization profile and domain separation. D11–D14 close that gap.

---

## D11 — The surface form of `PID`, and which layer applies `sha256:`

**Proposed:** `PID` is a **bare 64-character lowercase hex string**. No layer inside
the Agentic Proposer applies a `sha256:` prefix. If a consumer's wire contract
requires one, that consumer applies it at its own boundary and strips it before any
comparison against a `PID`.

**Precedent, and why it points this way.**

`[V]` Identity digests in this repository are bare hex.
`cer_v0_3/cleanroom/digest.py:35` (`action_digest`) returns `…hexdigest()` with no
prefix, and the frozen V0.2 constants it is pinned against
(`cer_v0_3/tests/test_cleanroom.py:21-22`) are bare 64-hex.

`[V]` `sha256:` in this repository marks a **referenced-content field value**, never
an identity. `cer_v0_3/cleanroom/profiles.py:93` fixes `_DIGEST_LEN = 71` — `"sha256:"`
plus 64 hex — for `image_digest`, `current_manifest_digest` and `statement_digest`;
`cer_v0_3/profiles/database.py:51` repeats it. These are pointers to content the
envelope does not carry, not the envelope's own identity.

`[V]` The prefix is affirmatively rejected as an identity elsewhere:
`packages/trusted-evidence-authority/tests/contract/test_identity_contracts.py:169`
lists `"sha256:" + CONTENT_DIGEST` among the malformed inputs, and
`verify_trusted_evidence_authority_distribution.py:266` repeats it.

`[I]` A `PID` carrying the prefix would therefore read, against this repository's own
conventions, as a pointer to external content rather than as the proposal's identity
— the opposite of what Equation 3 means.

`[R]` **Coupled to D14.** If the owner instead rules that the proposer applies the
prefix, the guard in `test_no_local_canonicalization.py:40` rejects the literal
`"sha256:"` as source text. Probe G below: a one-line
`return "sha256:" + canonical_sha256_hex(p)` fails
`test_no_canonicalization_or_hashing_source_text` even under the amended guard. That
is not an argument against the ruling; it is a second file the ruling would have to
change.

**Ratified:** ______________________  **Date:** ____________

---

## D12 — The frozen canonicalization profile for `P_unsigned`

**Proposed:** `P_unsigned` is canonicalized with **empty `set_paths` and empty
`nfc_paths`**. The profile is frozen at S1 and is part of the identity contract: any
later change to either set is a `PID`-breaking change requiring its own ratification.

**Consequences, recorded so they are not discovered later.**

`[V]` **This is not "pure RFC 8785".** Empty path sets disable only the set-ordering
and NFC-validation rules. The Action Profile still refuses bare JSON numbers
(`packages/jcs/src/ugence_jcs/canon.py:86-93`: any `int` or `float` raises
`BareNumberError`), and it implements none of RFC 8785's ES6 number serialization.
Every numeric in `P_unsigned` must already be a typed string when it reaches the
identity function. A contract that admits a bare number does not produce a wrong
`PID`; it produces no `PID` at all.

`[V]` **Array order is identity.** With empty `set_paths`, declaration order is
preserved exactly (`canon.py:104-112`). Any semantically order-insensitive collection
must be deterministically sorted **during contract construction, before
canonicalization**. The identity function will not sort it, and must not be asked to:
routing such a collection through `set_paths` would silently convert it to a set and
reject duplicates that the contract may legitimately allow.

`[V]` **No Unicode normalization beyond JCS.** With empty `nfc_paths`, strings pass
through unnormalized and un-validated; a composed and a decomposed spelling of the
same text are different proposals with different `PID`s
(`packages/jcs/tests/test_canonical_sha256_hex.py:93-95`). If S1 requires NFC on
any field, that is a `nfc_paths` entry under this decision, not a normalization step
bolted on elsewhere.

`[I]` The empty/empty default is the right one *because* it is the weakest: it adds
no semantics to the substrate, so every normalization obligation stays visible in the
contract layer where an owner can see it.

**Ratified:** ______________________  **Date:** ____________

---

## D13 — Domain separation for `PID`

**Proposed for ratification — no recommendation is offered; this is the one decision
here that trades off two defensible positions.**

`[R]` Equation 3 as written is **undomain-separated**: a bare SHA-256 over canonical
bytes, with no domain tag, no length prefix and no schema version. This repository's
own action identity is not.

`[V]` `cer_v0_3/cleanroom/digest.py:38-44` computes
`SHA-256( LP(domain_tag) || LP(canon_version) || LP(schema_version) || LP(canon) )`
with `domain_tag(ACTION) = "SYMBOLU/ACTIONGATE/ACTION/v1"`, implementing
`ACTION_CANONICALIZATION_AND_HASHING_SPEC.md` §9, §17. The clean-room deliberately
left `digest.py` behind during Stage P precisely because a canonicalization substrate
must not carry a domain tag (*Stage P*, above) — which means the framing is expected
to be applied by the identity layer, and S1 currently plans to apply none.

The two positions:

**(i) Keep Equation 3 bare.** A `PID` is an internal handle for an advisory artifact
that carries no authority (**D4**, *Authority-ownership boundary*). Domain framing
buys nothing if `PID`s never leave the proposer and are never compared against an
action digest.

**(ii) Frame the `PID`.** `PID` and `action_digest` are both "SHA-256 over JCS bytes"
to any reader and to any store keyed by hex string. Without a domain tag, the only
thing preventing a `P_unsigned` from being constructed whose canonical bytes equal
some other domain's canonical bytes is that no one has tried. Framing costs one
constant and closes the class.

`[G]` No evidence in this repository settles which position is correct, because no
`PID` exists yet and no store holds both kinds of digest. What the owner is deciding
is whether `PID`s will ever be persisted, logged, or compared alongside action
digests. If the answer is or may become yes, (ii) is the only safe ruling, and it
must be taken **before** the first `PID` is minted — retrofitting domain separation
invalidates every `PID` already issued.

`[I]` Whichever way this goes, `canonical_sha256_hex` remains the correct substrate.
Under (ii) the framing is applied by S1 **around** the canonical bytes, which means
S1 would need `canonical_bytes` rather than `canonical_sha256_hex` — a consequence
that bears on D14's admitted-name list.

**Ratified:** ______________________  **Date:** ____________

---

## D14 — Admitting the substrate call through the no-local-canonicalization guard

**Proposed:** `packages/capabilities/agentic-proposer/tests/test_no_local_canonicalization.py`
is amended to admit exactly one import form —
`from ugence_jcs import canonical_sha256_hex` — and nothing else, and the declared
dependency floor is raised to `ugence-jcs>=0.2.0`.

**The problem is real and is a hard blocker, not a nuisance.**

`[V]` The guard today rejects the very call D2 mandates. `SUSPECT_TEXT`
(`test_no_local_canonicalization.py:38-41`) contains `"sha256"` at `:40`, matched as a raw
substring against the whole file body, and `SUSPECT_DEF_SUBSTRINGS`
(`:32-35`) contains `"canon"`, `"digest"` and `"proposal_id"`. A minimal S1 module —
`from ugence_jcs import canonical_sha256_hex` plus
`def proposal_identity(...)` — placed in a scratch copy of the package produces
**2 failed**: `identity.py contains ['sha256']` and
`identity.py defines ['proposal_identity']`.

**The amendment, and why it does not widen the guard.**

The exemption is pinned to one module, one name, no alias, and one call site. The
text scan is not given a blanket carve-out: it runs on the source with the exact
identifier `canonical_sha256_hex` blanked, and **only** in a file that imports it in
the admitted form. Every other occurrence of every suspect string is still scanned.

`[V]` The design was executed against a scratch copy of the package during the audit
that produced this amendment. The patch is **not** applied to the repository — S1
applies it — but the behaviour is measured, not assumed:

| Probe | Expected | Result |
| --- | --- | --- |
| 0. Unmodified S0 package | pass | 26 passed |
| A. Admitted import + `pid_for` | pass | 30 passed |
| B. `hashlib` imported alongside it | fail | text scan + import scan |
| C. `json.dumps(sort_keys=True)` alongside it | fail | text scan + json scan |
| D. `import … as _h` (aliased) | fail | text scan + import-form test |
| E. `canonical_bytes` also imported | fail | text scan + import-form test |
| F. Two modules importing it | fail | one-call-site test |
| G. `"sha256:" + …` prefix applied locally | fail | text scan (see **D11**) |
| H. Function named `proposal_identity` | fail | def-name scan |

`[V]` **Consequence: the S1 identity function may not be named
`proposal_identity`.** `SUSPECT_DEF_SUBSTRINGS` is not relaxed, and
`"proposal_id"` is a substring of it (probe H). `pid_for` is clean against every
suspect substring and is the proposed name.

`[R]` **If D13 rules (ii)**, S1 needs the canonical *bytes* to frame, so the admitted
name becomes `canonical_bytes` rather than `canonical_sha256_hex`, and the framing
code will itself contain `hashlib` and `struct` — both in `FORBIDDEN_IMPORTS`
(`:44`). That is a materially larger guard amendment. **D13 must be ratified before
D14 is implemented.**

**Dependency floor.** `[V]` Three references to `ugence-jcs>=0.1.0` remain:
`packages/capabilities/agentic-proposer/pyproject.toml:56` (the declaration), and two
assertions pinning that exact string —
`tests/test_boundaries.py:148` and `tests/test_no_local_canonicalization.py:137`.
All three are satisfied by 0.2.0 today, so nothing is broken and nothing is urgent;
but the floor still admits a 0.1.0 that lacks `canonical_sha256_hex` entirely, so S1
must raise all three together.

`[I]` `packages/jcs` appears nowhere in `platform/PLATFORM_FREEZE_V1.json`. The
freeze verifier passing across the 0.2.0 change confirms no collateral damage to
frozen components; it is not evidence about this package, and no owner should read it
as such.

**Ratified:** ______________________  **Date:** ____________

---

## What this amendment does not do

`[V]` It implements no part of S1: no identity module, no guard patch, no version
bump, no contract. `ugence-jcs` 0.2.0 is additive and byte-preserving, so nothing
here is time-pressured.

`[R]` Ratification order is **D13 → D11 → D12 → D14**. D13 determines what S1
imports, which determines the shape of D14's guard amendment; D11 determines whether
D14 must also admit a `"sha256:"` literal.
