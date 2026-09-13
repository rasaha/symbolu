# Change Effect Classifier — Stage 1 scoping: contracts and inert substrate

**Status:** **authorized as tracked work** by the owner on 2026-09-13 (ADR §8), strictly
contracts-only and inert. Items 3.1, 3.3 and the admission data of 3.6 are delivered in
`packages/integration/change-effect-records`; items 3.2, 3.4 and 3.5 are not yet started.
The package split and the Stage 2 timing of the conformance profile are confirmed by the
owner, closing Stage 1 decisions 2 and 3 (ADR §9). Originally
produced as scoping only. Produced 2026-09-12 under the
reviewer's staging recommendation, adopted by the owner the same day (ADR §5).
Revised 2026-09-13 to the record graph of GERL classification rule version 4.2.10, per
item 8 of the reviewer's 4.2.10 gate, and again the same day for the recorded erratum to
4.2.10. **Version 4.2.10 is conditionally ratified** (ADR §7); tracked implementation of
anything below still requires the external conditions that ratification named — archive
custody, verified linearizable audit-root operations, verified atomic target-version
compare-and-apply, the [R] parameters and owner decision 6 — the CEC and staging rulings adopted; the contract schema
frozen. Labels: `[V]` verified at commit `b60b8417`, `[I]` inferred, `[R]` requires
ratification, `[G]` gap.

## 1 — The question

What can exist before the rule is ratified without anticipating what the rule will say?
**Only shapes: a provider kind, a policy family, thirteen record types, a linkage contract, a
read-port contract and an admission-state contract, each of which records or declares and
none of which classifies, authorizes, admits, writes or reads governed state.** The
repository already builds packages of exactly this shape `[V]`: `agent-assurance-evidence`,
`vendor-dependency` and `ai-system-registry` are contracts-only or contracts-plus-one-file,
import only `ugence_governance_contracts`, and each README states in bold what it never
does (`packages/integration/agent-assurance-evidence/README.md:3,12`;
`vendor-dependency/README.md:3,12`; `ai-system-registry/README.md:3,12`).

## 2 — The precedent, and the rule for every item below

A Stage 1 package: imports `ugence_governance_contracts` and nothing else unless named
here; ships frozen dataclasses, enums, selectors, canonical digests and refusal codes;
ships no store, clock, verifier, RNG, replay, resolver or network; states its "never" list
in its README's first lines; and is inert by construction, meaning no runtime path in the
repository calls it until Stage 2 or 3 composes it. `[V]` The three precedents follow this
pattern exactly; `vendor-dependency` and `ai-system-registry` add one ruled local file,
which Stage 1 does not need.

## 3 — The seven items

### 3.1 Provider kind `CHANGE_EFFECT_CLASSIFICATION`

- **Lives in:** `governance-contracts`, `metadata.py`, appended after the three existing
  members `[V]` (`packages/governance-contracts/src/ugence_governance_contracts/metadata.py:18-32`).
- **Must not:** carry a contract of its own in Stage 1. The kind is a name; the request and
  result types arrive with the record contracts in 3.3.
- **Compatibility gate, CEC-1** `[V]`: registry dispatch checks membership and equality of
  descriptor kind and capabilities kind (`governance-provider-framework/.../registry/__init__.py:60-64`),
  so a new member is admitted without code change; TAP and ActionGate check only their own
  kind by identity (`providers/tap/.../provider.py:58,64`; `providers/actiongate/.../provider.py:52,58`),
  so neither breaks. `[V]` The conformance suite under
  `governance-provider-framework/.../conformance/` has exactly one profile per existing
  kind, `action.py`, `assertion.py`, `execution.py`, over `common.py`; a fourth kind needs
  its own profile before any provider registers under it `[G]`.
  `[G]` Serialized values: any consumer that persists `ProviderKind.value` and reads it back
  with exhaustive matching must be listed and checked; none found under `packages/*/src`
  outside tests, but the search covered identity checks only.
- **Inert because:** no provider registers under it in Stage 1.
- **Delivered** `[V]`: the member and both configuration labels exist; four baseline tests
  that pinned the enum to three members are updated (ADR §8.1); a dedicated test asserts
  peer-ness, nameability, non-registration and the profile's continued absence.

### 3.2 Policy family: protected-registry list and delegation table

- **Lives in:** a new integration package on the strategy-permission pattern `[V]`
  (`integration/agentic-proposer-strategy-permission-policy/.../policy.py:128-151,220`):
  its own frozen metadata type with `policy_id`, `version`, `content_digest`, `scope`,
  `lifecycle_state`, tenant, supersession and effectivity; `policy_family` fixed as a
  property; an adapter through `ugence_policy_authority.api`.
- **Imports:** `ugence_governance_contracts`, `ugence_policy_authority.api` (the adapter
  only). Nothing from the proposer or the classifier.
- **Content:** one artifact holding both the protected-registry list (seven registries with
  admission rules) and the delegation table, versioned atomically per CEC-2, pinning the
  intent-specification and constitution references it applies under.
- **Must not:** ship any operative delegation entry. The initial table is empty or every
  entry carries `active = false`; D1, D3, D4 and D5 are not encoded until their parameters
  and mechanisms are ratified. Must not resolve itself: resolution is `resolve_policy`
  under configured trust `[V]` (`policy-authority/.../core/resolution.py:121`).
- **Inert because:** nothing reads the family in Stage 1, and an empty table matches no delta.

### 3.3 Record contracts

Thirteen frozen, digest-bound record types in one new contracts package. Their canonical
bytes are **not a new scheme**: rule version 4.2.10 section 6a defines a **profile over the
envelope** these packages already share `[V]` — the envelope unchanged, with recursive NFC,
omitted-not-null, int64-only numbers, refusal of JSON booleans in favour of enumerated
strings, and explicit collection rules, none of which the repository convention itself
imposes — namespace, U+001F separator, schema version, `json.dumps`
with `sort_keys=True` and compact separators, SHA-256 full hex
(`packages/integration/execution-reservation/src/ugence_execution_reservation/_canon.py:17-18,45-57`,
and the same shape in twelve sibling packages). The thirteenth type,
`RevocationImpactRecord`, was added by rule version 4.2.9; version 4.2.10 adds no type and
changes no count. They form a
**directed acyclic graph**, per rule version 4.2.10 and its Figure 4, whose arrows mean
*pins the digest of* and therefore point back against writing order, not a linear order: the
amendment pins the classification; an investigation opening pins its obligation identifier
and **exactly one** of those two records, whichever introduced it, never both; an extension and a closure pin their own
opening; the final resolution pins the classification, the amendment and every `COMPLETED`
closure; the authorization pins the final resolution alone; the admission records pin their
predecessors. The contract rule is therefore not "earlier types only" but **every pinned
digest must already exist when the pinning record is sealed**, which the types express by
carrying digests and never back-references:

- **ClassificationRecord.** Effect classification as a list of RegistryEffectResult
  (`evaluation_status`, `effect_class` or null, `blocking_obligation_ref`); routing
  disposition as `jurisdictional_route` plus `blocking_obligations`; bound digests for the
  three snapshots, evaluator version, policy versions, replay environment, model and code,
  family seed and sample digest; drift and disparity figures; the `chain_id`, the
  domain-separated digest over tenant identity, candidate digest, anomaly-family identifier,
  family-seed digest and the classifier-issued `chain_instance_id`, all established in step
  0's four ordered sub-steps before the record is sealed, so that an identical candidate
  returning after a terminating outcome still receives a distinct chain; and, for each
  blocking obligation, its stable `obligation_id`,
  the domain-separated digest over the `chain_id`, the introducing record's *role* as a
  constant, the obligation kind, the registry or cell coordinate and a canonically assigned
  ordinal. **The identifier never digests the record that carries it** — that construction is
  circular, since the record cannot be digested until its identifiers are known — so the
  package derives identifiers from the `chain_id` alone and ships `OBLIGATION_ID_MISMATCH`
  for a record whose listed identifiers do not recompute, and `CHAIN_ID_IN_USE` for a second
  classification claiming one chain. Identifiers are unique and stable within one `chain_id`
  and are not comparable across chains. **Carries no confirmation
  field:** the confirmation seed, sample digest and result are produced after the freeze and
  live in the ConfirmationAmendment. References nothing that comes after it.
- **ConfirmationAmendment.** The post-freeze amendment carrying the confirmation seed,
  sample digest and result, the closed-obligation reference for CONFIRMATION_PENDING and any
  new obligations, referencing the frozen record's digest.
- **InvestigationRecord.** The immutable opening record only: candidate digest, anomaly
  family, named evaluation, owner identity, deadline, and the `obligation_id` it answers
  together with the digest of the record that introduced that obligation — the
  ClassificationRecord or the ConfirmationAmendment — carried as a role constant and a digest,
  not as a source of the identifier. The exact payload field names for both identifiers, and
  the test vectors an implementation must reproduce, are in rule section 6a. It acquires no state and no closing
  disposition; both arrive as successors below. At most one opening per `obligation_id`,
  enforced by the conditional append in 3.4 and not by these types;
  the package ships `OBLIGATION_UNKNOWN` for an opening naming an identifier its introducing
  record does not carry.
- **InvestigationExtensionRecord.** At most one per investigation, pinning the opening
  record's digest and carrying the extended deadline.
- **InvestigationClosureRecord.** Exactly one per investigation, pinning the opening
  record's digest and any extension, with outcome `COMPLETED`, `EXPIRED` or
  `CLOSED_INSUFFICIENT_EVIDENCE`, and, for `COMPLETED`, a **ClosureEffectBundle**: the
  `obligation_id`, the signed evaluation-result reference, an ordered list of one or more
  primitive effects, and an explicit declared write set naming every primitive target the
  bundle touches, plus the `mapping_version` under which it was derived. **The bundle is
  derived, not composed:** the evaluator signs a raw `EvaluationResult` and the
  policy-governance-owned `ClosureBundleMapping` produces the canonical bundle, which the
  Stage 3 verifier independently recomputes and compares for completeness as well as
  correctness. The primitive effects are exactly six — `SET_SAMPLE`,
  `SET_CELL_MEASUREMENT`, `SET_REGISTRY_OBSERVATION`, `SET_BASELINE`,
  `SET_EVIDENCE_CUSTODY`, and `SET_CONFIRMATION_RESULT` reserved to the amendment — and none
  writes a derived value: registry status, effect class, direction, magnitude, D1 bound and
  every routing input are recomputed by the Stage 3 projection, never supplied. There is no
  `CONFIRM_NO_CHANGE` and no registry-result replacement. A `COMPLETED` closure resolves
  inside the existing chain; it never starts a new one. Only `COMPLETED` can feed a final resolution: the other
  two are terminating outcomes that end the candidate with no resolution and no
  authorization, and the chain seals on the closure. `CLOSURE_NOT_EXPRESSIBLE` is the reason
  code for an evaluation that cannot be carried as an effect over the frozen record's inputs
  and must therefore terminate; the package also ships `CLOSURE_EFFECT_CONFLICT` for
  intersecting, mismatched or out-of-scope write sets and `COMPLETED_STATE_UNRESOLVED` for a
  condition that survives recomputation, `BUNDLE_MAPPING_MISMATCH` for a bundle that departs
  from the canonical derivation, `EVALUATION_RESULT_INCOMPLETE` for raw evidence missing a
  field the mapping requires — which **blocks and never terminates** — and
  `SEED_AUTHORITY_INVALID` and `SAMPLE_EXHAUSTED` for the sampling rules. Which bundles are
  admissible and which obligation kinds each effect may serve are data in the package;
  deciding either is not.
- **FinalResolutionRecord.** Binds the ClassificationRecord digest, the
  ConfirmationAmendment digest, every `COMPLETED` InvestigationClosureRecord digest, the final
  routing disposition re-applied to the completed results, and the assertion that the
  effective obligation set is empty. It is the only record an authorization pins, and it is
  terminal and unique for its chain: at most one per ClassificationRecord, and nothing
  attaches to the chain behind it.
- **ResolutionRevocationRecord.** Pins a FinalResolutionRecord and states the basis for
  withdrawing it and every authorization that pins it. **It carries no exposure window:** at
  the instant it is sealed the window may not exist yet, and an immutable record must not
  assert a fact that is not yet knowable. It never reopens the sealed chain, and anything
  further about the same change is a new candidate with a new ClassificationRecord.
- **RevocationImpactRecord.** The single successor of a revocation, carrying what becomes
  knowable only afterwards: whether application occurred; the ordering, `REVOKE_THEN_APPLY`
  or `APPLY_THEN_REVOKE`, as the control register fixed it; the pinned completion digest, or a
  completion-absence determination admissible only where no APPLY claim was ever made; the
  target versions the compare-and-apply advanced; the served-read receipt range; the resulting
  eligibility; and whether remediation is required under owner decision 6. **Every field is
  derived, not asserted:** the Stage 3 verifier recomputes the impact projection from the
  ledger and refuses a divergent record with `IMPACT_MISMATCH`. The type carries the fields; it
  computes none of them.
- **AuthorizationBinding.** The shape by which an M6 authorization pins a
  **FinalResolutionRecord** digest, and through it the classification, the amendment and
  every closure. Not the classification digest alone: an authorization pinned to the
  classification would not identify the final route or the evidence that emptied the
  effective obligation set. This is a binding contract only; issuance stays in M6.
- **AdmissionReservationRecord, AdmissionClaimRecord, AdmissionCompletionRecord,
  AdmissionResolutionRecord.**
  Immutable successors, per rule version 4.2.8: the reservation binds the
  FinalResolutionRecord and authorization digests, restates the ClassificationRecord and
  ConfirmationAmendment digests copied from the resolution, and carries the pre-state digest,
  the delta digest, the idempotency key and the `head_version` the boundary read the chain
  head at, the **authorization digest its transition is keyed by**, the single-tenant
  `(tenant, target)` set the delta touches and the **expected target version** for each, which together with the head version are the conditions its append and the later
  write are made under, state RESERVED; an
  **AdmissionClaimRecord** pins the reservation and carries `claim_kind` APPLY or CANCEL. An
  APPLY is a **compare-and-advance on the resolution's control register**, carrying the
  expected control version and requiring state ACTIVE; a revocation is the same operation on
  the same register, which is what makes a write after a committed revocation unreachable. A
  CANCEL claim is documentary: it records a revocation-first outcome where one is appended,
  and correctness never depends on it. A completion pins the APPLY claim and its prior state
  and carries APPLIED, FAILED or OUTCOME_UNKNOWN with a reason, and it — not the claim —
  states whether the physical mutation occurred and which target versions it advanced;
  `STALE_TARGET` is the reason a second resolution built on one pre-state records, and a
  completion that applied nothing returns the control register to ACTIVE so the resolution can be
  re-reserved under a new authorization, but only by winning that versioned transition before a
  revocation: a completion arriving after one is recorded and leaves the register REVOKED, and
  APPLIED is terminal for the admission; the package also ships `CROSS_TENANT_DELTA`,
  `TARGET_SET_MISMATCH`, `ADMISSION_IN_FLIGHT` and `INVESTIGATION_SEALED`; a
  resolution pins an OUTCOME_UNKNOWN completion and a human authority's resolved state. Every
  successor names its expected predecessor. The legal successions are data. No record is ever
  mutated.
- **Must not:** compute any field, and must not compute anything *across* records. Every
  digest is supplied by a caller; the package validates shape, non-emptiness, time-zone
  awareness and canonical form, as the precedents do. No classification logic, no route
  rules, no replay. In particular the final-resolution projection — introduced
  obligations, closure coverage, bundle admission and conflict detection, primitive
  application, the single recomputation of every derived value, the effective set and the
  deterministic re-application of R1 to R6 — together with terminal-head verification and conditional
  append, belongs to the producer and verifier boundaries of Stages 2 and 3, not to these
  types. The same holds for the authority decisions rule version 4.2.10 assigns: the evaluator
  produces **only a signed `EvaluationResult`** and never a bundle, the projection verifier
  derives the canonical bundle from the policy-governance-owned mapping and verifies it for
  completeness as well as correctness, the reviewer returns one of the four review outcomes,
  and the investigation owner records deadlines and dispositions only. The types carry who signed what; they decide nothing, and the projection
  they make *expressible* they never evaluate.
- **Inert because:** no producer exists.

### 3.4 Linkage-entry contract into the audit root

- **Lives in:** the same contracts package as 3.3.
- **Shape:** a `LedgerEntry` kind string and payload schema for each record type above,
  on the `governed-review-service` linkage pattern `[V]`
  (`integration/governed-review-service/.../linkage.py:7-8,56`), appended through
  `AuditLedger.append` `[V]` (`integration/control-plane-root/.../ledger.py:157`) with a
  `LedgerEntry` `[V]` (`entry.py:52`).
- **Imports:** `ugence_control_plane_root` for the entry and ledger types only.
- **Required audit-root capability, declared not implemented:** the rule requires an atomic
  conditional append with a uniqueness constraint over `(chain_id, predecessor_digest,
  transition_kind)` for every unique successor in the graph, which is all of them: the
  ConfirmationAmendment, the opening InvestigationRecord — whose `obligation_id` forms part of
  the `transition_kind`, so one-opening-per-obligation is the same constraint and not a second
  mechanism — the extension, the closure, the final resolution, the revocation, and each
  admission successor, including the `ADMISSION_CLAIM` slot, and the `RevocationImpactRecord`.
  Beyond slot uniqueness the rule requires **two linearizable registries**: a control register
  per resolution, read and conditionally advanced by both the APPLY claim and the revocation;
  and a **target-version registry** per `(tenant, target)` of governed memory, against which
  the mutation is an all-or-nothing compare-and-apply. `[G]` Nothing in the repository is
  verified to offer either.
  `head_version` is an **opaque concurrency token returned by an authoritative, linearizable
  chain-head read** and consumed by the conditional append; a ledger scan, an advisory index
  or an eventually consistent replica cannot supply it, whatever they return. The admission
  reservation conditions on that token, so terminal-head verification and reservation are one
  operation rather than a check followed by an append; `HEAD_MOVED` is its refusal. `[G]` No
  repository component has been verified to offer a linearizable head read; without one the
  Stage 3 boundary fails closed and no admission proceeds. Stage 1 declares that requirement as part
  of the payload schema and ships the `APPEND_UNIQUENESS_UNAVAILABLE` refusal code; whether
  `AuditLedger.append` can satisfy it is unverified `[G]` and is a Stage 2 question. A
  refusal code does not create uniqueness.
- **Must not:** append. Stage 1 defines kinds and payloads; the first append happens in
  Stage 2 under the CEC-3 record contract: immutable storage, signer identity,
  idempotency, append-failure behaviour, and the rule that a classification without its
  audit record is not admissible.
- **Inert because:** no writer.

### 3.5 Read-port contract

- **Lives in:** `governance-contracts`, as a `Protocol` beside `Provider` `[V]`
  (`contracts/base.py:17`), on the pattern of `LinkageIndex(Protocol)` `[V]`
  (`governed-review-service/.../linkage.py:91`).
- **Shape:** one method taking tenant, consumer identity, purpose, target and target
  version, and the consumer's authorization state, returning a typed eligibility
  determination that is never a bare boolean and carries the authorization digest it was
  computed under.
- **Must not:** be implemented in Stage 1. No store, no cache, no consumer adapter for M3
  or M11.
- **Inert because:** a Protocol with no implementation.

### 3.6 Admission-state contract

- **Lives in:** the contracts package of 3.3, as the admission state enum, the legal
  succession table over the **four** admission record types — reservation, claim, completion
  and resolution — and the recovery-rule outcomes as data
  (tag present and post-state matches → APPLIED; tag absent and pre-state matches → re-run;
  otherwise OUTCOME_UNKNOWN).
- **Single successor, as data:** the succession table is a function, not a relation —
  RESERVED to exactly one AdmissionClaimRecord; a CANCEL claim to nothing, being terminal; an
  APPLY claim to exactly one of APPLIED, FAILED, OUTCOME_UNKNOWN; and OUTCOME_UNKNOWN to
  exactly one resolution — and the package ships the `CHAIN_FORK_REFUSED` refusal code for a second
  successor to the same transition. The current state of an admission is the unique tip of
  its chain; "latest record" is not a defined notion. `CHAIN_FORK_REFUSED` is what the losing
  writer observes, never what makes the guarantee: that is the conditional append in 3.4, and
  where it is unavailable the Stage 3 boundary fails closed. The same holds for `HEAD_MOVED`
  and `CHAIN_SEALED`: the package ships the codes, the audit root supplies the guarantee.
- **Must not:** transition anything, and must not enforce the succession table. The admission boundary that drives the machine is
  Stage 3 and is the first enforcing consumer of a ClassificationRecord, per the staging
  ruling. The executor never reads the classification; it receives an admitted delta.
- **Inert because:** no boundary exists.

### 3.7 What is deliberately not in Stage 1

The classifier, the replay harness, the probe specification, the anchor store, the
justification graph, the confirmation-sample drawer, the admission boundary, the
executor, governed memory, any M3 or M11 adapter, archive custody, and any delegation
entry. Each depends on the rule's text or on a ruling that is open.

## 4 — Order of work within Stage 1 `[I]`

3.1 first, since the conformance profile gap must be closed before anything registers;
3.3 and 3.6 together, since the admission state enum is shared; 3.4 after 3.3; 3.2
and 3.5 independently. Freeze the schema only after a version passes review, because the
record surface has changed at every review so far and may change again.

## 5 — Owner decisions

1. Adopted 2026-09-12 (ADR §5).
2. **Confirmed 2026-09-13** (ADR §9): one contracts package for records, linkage and
   admission state; one policy-family package; kind and read port in the substrate.
3. **Confirmed 2026-09-13** (ADR §9): the conformance profile for the fourth kind belongs
   to Stage 2. Stage 1 continues to register no provider, and a test asserts the profile's
   continued absence so the ruling fails loudly if someone adds one.
