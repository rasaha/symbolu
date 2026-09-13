# ADR — Change Effect Classifier: scoping

**Status:** the rule is conditionally ratified at version 4.2.10 (§7) and **Stage 1
contracts-only implementation is authorized as tracked work** (§8). Scoping; placements, CEC-1 to CEC-5, the reviewer's GERL dispositions and
the staging rulings adopted by the owner on 2026-09-12 by express reference to a reviewer-drafted statement (§5); no classifier package exists yet; as of this commit the record does amend
`governance-contracts` and `governance-provider-framework` for CEC-1 alone (§8). It carries the material the
capability-pipeline entry and the module-flowchart section cannot hold by their
conventions. The rule it scopes is the GERL target classification, version 4.1, an
owner-held document that received a whole-document review from outside the drafting
model family on 2026-09-12 with outcome NOT_RATIFIED (§4). Labels: `[V]` verified against this repository at
commit `b60b8417`, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Which component decides, for a frozen change to a governed system's persistent state,
what the change affects and which governance process may authorize it, without
trusting the proposer's description of the change? **Nothing does.** The pipeline's
nine questions govern actions `[V]` (`docs/UGENCE_ENTERPRISE_AI_GOVERNANCE_CAPABILITY_PIPELINE.md:16-32`),
and no entry among the seventy, and no section of the module flowcharts, mentions
recalibration, a learning loop, a memory write or a lesson `[V]` (search of both
documents, zero matches). A change labelled "learning" can alter permissions,
constraints or the treatment of a class of subjects indirectly, and the platform has
no place that measures whether it did. The answer is a detective provider that
classifies behavioural effect by replay and names a route. A classification authorizes
nothing.

## 2 — What the repository already fixes `[V]`

| Finding | Where |
|---|---|
| A provider is a `BaseProvider` registered through the framework's registry, with lifecycle, conformance and an invocation log. | `packages/governance-contracts/src/ugence_governance_contracts/contracts/base.py:26`; `packages/governance-provider-framework/src/ugence_governance_provider_framework/registry/__init__.py:23` |
| `ProviderKind` admits exactly three peers, ASSERTION_GOVERNANCE, ACTION_GOVERNANCE, EXTERNAL_EXECUTION, "never conflated". A classifier is none of them. | `packages/governance-contracts/src/ugence_governance_contracts/metadata.py:18-32` |
| A policy is resolved to one exact version under configured trust or fails closed, with approval re-verified at `as_of` when a verifier is supplied. | `packages/policy-authority/src/ugence_policy_authority/core/resolution.py:121` |
| A policy family is issued through the family-neutral authority with its own metadata type; `policy_family` is a property fixed per family, not a field. | `packages/integration/agentic-proposer-strategy-permission-policy/src/ugence_agentic_proposer_strategy_permission_policy/policy.py:3-6`, `:132-137`, `:220` |
| A signed receipt is re-verified scope-bound: payload digest recomputed, anchor resolved at the exact coordinate, window checked, every expectation coordinate equal. | `packages/trusted-evidence-authority/src/ugence_trusted_evidence_authority/authority/reverification.py:508`, `:584` |
| A review round trip is appended to the audit root once, as a `LedgerEntry` linkage, by a service that never approves, authenticates, mints, clears or executes. | `packages/integration/governed-review-service/src/ugence_governed_review_service/linkage.py:7-8`; `packages/integration/control-plane-root/src/ugence_control_plane_root/entry.py:52`, `ledger.py:157` |
| A provider's unknown state is mapped fail-safe to indeterminate, never promoted to support. | pipeline entry 25, `docs/UGENCE_ENTERPRISE_AI_GOVERNANCE_CAPABILITY_PIPELINE.md:453` |
| Which reasoning strategies a role may use is already a signed, revocable policy family; reasoning-method contracts are research-only vocabulary. | pipeline entries 11 and 16 |
| Two unreconciled clearance paths and seven independent ledgers are recorded as findings awaiting owner rulings. | `docs/UGENCE_MODULE_FLOWCHARTS.md:1128-1142` |

## 3 — The design `[I]`

**Home.** A new provider package, `packages/providers/change-effect-classifier`, on
TAP's grounds: it evaluates and never authorizes, it speaks the neutral contracts, and
it reaches the rest of the platform through ports. Sequence alignment Verify, with its
output consumed in Decide.

**Two outputs, not one.** For each protected registry the provider measures the
candidate's own effect, current state to proposed state, on replay. Output 1 is the
effect class: descriptive state, policy enforcement, authority, identity. Output 2 is
the route: GERL at the target's base tier, GERL under a named delegation entry, policy
governance, or further investigation with a named evaluation. Routes for
policy-enforcement effects are read from a constitution-owned delegation table; a
policy-enforcement effect with no matching entry routes to policy governance;
authority and identity effects always route to policy governance; anything the
provider cannot evaluate routes to further investigation and never to GERL.

**What it reads and never reads.** It reads the frozen candidate, the anomaly record
that keys its replay seed, the justification graph including instrumented read paths
and retrieval reach, the context anchor with class membership frozen at it, a replay
set it draws itself plus a constitution-owned probe set, the protected-registry list,
the delegation table, intent specifications, and producer-signed assurance records.
It never reads the candidate's narrative, the proposer's suggested class, route, tier
or scope, the proposer's confidence, any episode the proposer selects, or current
class membership.

**Contract vocabulary.** Request: `tenant_id`, `candidate_digest`, the typed delta
(target, field, old value, new value, declared premises), `anomaly_reference`,
evidence references each carrying a trusted-evidence receipt, policy references for
the registry list, delegation table and intent specifications, `as_of`. Result: effect
class per registry; `route`; delegation entry reference; tier and independence level;
seed and sample digest; three comparison digests; candidate effect, cumulative drift
cost, existing drift; absolute disparity; investigation record reference;
`AuditReference` of the appended record. Fail-safe: a provider error, an unresolvable
policy or an unverifiable evidence reference maps to further investigation, on the
precedent of entry 25's `UNKNOWN` mapping.

**Dependencies.**

| Package | Supplies | Reference `[V]` |
|---|---|---|
| `governance-contracts`, `governance-provider-framework` | Provider base, registry, lifecycle, conformance, invocation log | `contracts/base.py:26`; `registry/__init__.py:23` |
| `policy-authority` | Resolution of the registry list, delegation table and intent specifications as signed, versioned policy, failing closed | `core/resolution.py:121` |
| `trusted-evidence-authority` | Scope-bound verification of each evidence reference's producer receipt: digest, anchor, window, expectation coordinates `[V]`. Receipt verification does not establish that the store is proposer-unwritable; custody assurance is open (§5) `[G]` | `authority/reverification.py:584` |
| `governed-review-service` | Coordinates the review by record reference, not by import. Recomputing the replay from the bound seed yields REPLAY_MISMATCH on a digest mismatch; INSUFFICIENT_EVALUATION and MISCLASSIFIED are separate outcomes. The independent replay and evaluation capability is a proposed integration, not an existing verified service capability | `linkage.py:7-8` for the linkage pattern only |
| `control-plane-root` | Append of every ClassificationRecord and InvestigationRecord as a linkage entry, once | `entry.py:52`; `ledger.py:157` |

**Must not duplicate.** `agentic-proposer-strategy-permission-policy` governs which
reasoning strategies a role may use `[V]` (`policy.py:3-6`); `reasoning-method-governance`
supplies research-only comparison vocabulary `[V]` (pipeline entry 16). The classifier
governs what the proposer may keep, not how it thinks. It imports neither and issues
no fit assessment.

**Provider kind.** A fourth `ProviderKind`, `CHANGE_EFFECT_CLASSIFICATION`, appended
after the three existing members. The alternative, registering under
ASSERTION_GOVERNANCE with a feature tag, would describe the contract as evaluating an
assertion against evidence, which it does not do. This is CEC-1 below.

**Policy family.** The protected-registry list and the delegation table are issued as
one Policy Authority family on the strategy-permission pattern: its own metadata type,
`policy_family` fixed as a property, resolved through `resolve_policy` at `as_of`.
They change together, so they version together. This is CEC-2 below.

**Ownership, as ruled (§5).** M15 owns classification and nothing else. It does not
authorize and it does not mutate. Three further components, each separately scoped and
each without a package, complete the lane: a **governed memory** that enforces read
eligibility; an **admission boundary** that, before any write, verifies the exact
classification record and the separate M6 authorization, the expected pre-state and the
authorized delta, current validity and revocation conditions, and atomic, replay-protected
application; and a **recalibration executor** that is the sole mutation path. A signed M6
record is not, by itself, permission to apply any memory write.

**Reads.** Every consumer of governed recalibration state reads it through a neutral
**read port declared in M0**, never by direct store access. The port's answer is an
eligibility determination for this tenant, consumer, purpose, target version and
authorization state, not a cached boolean; a revoked entry cannot stay active through
caching. M3 and M11 are proposed consumers with target adapters still to be built and
verified. RA-7 observing trajectory change does not establish that M11 accepts learned
thresholds or anchors; that integration is proposed, not established. Protected probes,
baseline constraints and evaluation anchors sit behind an independently governed boundary
so that a learned threshold cannot weaken the checks that decide its own admissibility.

**Review outcomes.** M7 coordinates the review. Matching replay digests establish that the
recorded computation was reproduced, not that coverage or the rule was adequate, so review
returns three distinct outcomes: REPLAY_MISMATCH, INSUFFICIENT_EVALUATION, MISCLASSIFIED.
The independent replay and evaluation capability behind M7 is a proposed integration.

**Experiments.** An environment-touching experiment raised by the learning loop enters as
a proposal through M9's governance hook and clears by the ratified canonical clearance
path. This selects neither M6 nor M8 as canonical. Environment execution stays blocked
until flowchart ruling 1 and experiment-tier decision D2 are resolved.

**Record placement.** The provider keeps no ledger of its own. It appends its records
to `control-plane-root` as linkage entries exactly as `governed-review-service` does,
which is sufficient under either outcome of flowchart ruling 2. This is CEC-3 below.

**Relation to supersession.** A candidate of proposal type REPLACE can receive a GERL
route while the system it displaces keeps influence through routing, retrieval,
cached conclusions and dependent rules. Classification says nothing about that; a
separate supersession candidate under the governed-supersession specification is
required, and the two are never bundled.

## 4 — What does not exist `[G]`

- **The package.** Nothing under `packages/*/src` imports or defines it.
- **The provider kind.** `ProviderKind` has three members and the registry resolves
  by kind, so the provider cannot register until the fourth exists.
- **The policy family.** No family issues a protected-registry list or a delegation
  table; no policy references for them can resolve.
- **The stores the rule assumes.** No justification graph with instrumented read
  paths, no context-anchor store, no constitution-owned probe set, no replay harness
  exists in the repository. The rule's measurements have nothing to run on.
- **The consumer.** No recalibration executor exists to refuse an update whose
  ClassificationRecord digest it cannot verify. Until one does, a route is recorded
  and enforced by nothing.
- **The admission boundary and the read port.** Neither has a contract. The boundary's
  five verifications and the port's eligibility determination are stated in §3 and
  implemented nowhere.
- **Lesson-specific adapters.** M6 and M7 are reused as kernels. The lesson-specific
  authorization adapter, the replay-review adapter and independent replay capability, and
  the M3 and M11 consumer adapters do not exist.
- **Independent review of the rule: obtained, outcome NOT_RATIFIED.** Version 4.1 was
  reviewed in whole on 2026-09-12 by a reviewer recorded as OpenAI GPT-5, a model family
  separate from the Anthropic Claude drafting family. Ruling: NOT_RATIFIED; version 4.2
  may proceed against an eight-item gate: (1) effect-class and route separation at the
  direct-touch and parentless-context exits; (2) a compound routing disposition carrying
  the jurisdictional route and blocking obligations; (3) anomaly-family linkage,
  restricted sample disclosure and a fresh confirmation sample before authorization;
  (4) deterministic replay and complete record bindings; (5) evidence custody separated
  from receipt verification; (6) quantitative magnitude definitions; (7) the D1 to D6
  dispositions, none ratified as written; (8) admission verification at the mutation
  boundary. Model-family separation is established; organizational independence is
  limited to the process the owner defines. The rule is not the normative rule M15
  implements until a later version passes.

## 5 — Ruling record — 2026-09-12

Provenance, amended 2026-09-12. The reviewer, recorded as OpenAI GPT-5 and separate
from the Anthropic Claude drafting family, recommended the rulings below from the module
map PDF (rev 3.1). Both sentences previously quoted here as the owner's, "Accept both
placement corrections, but amend Placement 2's ownership and qualify CEC-5" and "My
ruling: accept the ownership and placement amendments as incorporated; require the
consistency corrections above before calling the ADR and figure finalized", were the
reviewer's. The sentence the reviewer later proposed as the owner's adoption words, "The
forwarded rulings accept both placements with amendments and add corrections I agree
with", was written by the drafting assistant in this session, not by the owner. Until
2026-09-12 the owner's adoption consisted of the act of forwarding the recommendations and
directing their application. On 2026-09-12 the owner adopted, by express reference, a
reviewer-drafted adoption statement and directed that it be recorded verbatim; it is
recorded in full under "Owner adoption" below. The reviewer did
not verify repository-specific claims; those in this ADR carry their own labels.

| Item | Ruling | Condition |
|---|---|---|
| Placement 1, experiments | ACCEPT, qualified | Enter as proposals through M9's governance hook and the ratified canonical clearance path. Selects neither M6 nor M8. Environment execution blocked until ruling 1 and decision D2. |
| Placement 2, memory readers | ACCEPT, amended | Every consumer reads through a neutral read port declared in M0. M3 and M11 shown as proposed consumers; adapters to be built and verified. No direct store access. |
| Placement 2, ownership | AMEND | M15 owns classification, not authorization or mutation. Governed memory enforces read eligibility; a separately scoped recalibration executor is the sole mutation path; M6 supplies authorization. M15 is not to be expanded into a preventive execution module. |
| CEC-1, fourth provider kind | CONFIRM, compatibility gate | Add CHANGE_EFFECT_CLASSIFICATION subject to checking registry dispatch, serialized values, exhaustive enum handling and provider conformance. |
| CEC-2, one policy family | CONFIRM | Version the registry list and delegation table atomically. Pin applicable intent specifications and constitution references explicitly. |
| CEC-3, linkage entries | CONFIRM, record contract | No classifier ledger. Specify immutable storage, signer identity, idempotency and append-failure behaviour. A classification lacking its audit record is not admissible for mutation. |
| CEC-4, general scope | CONFIRM, amended | General contract; first implementation limited to enumerated learning-update types and one enforcing consumer. "Learning" is an input scope, never evidence of low impact. Unsupported targets stay unevaluated. |
| CEC-5, classifier first | CONFIRM, offline only | Contracts, replay infrastructure and an auditable prototype before the consumer. Not preventive, not production-ready, until the consumer demonstrably rejects stale, mismatched, revoked, unauthorized and duplicate updates. |

**Further rulings recommended by the same reviewer on 2026-09-12, adopted by the owner
the same day (see "Owner adoption").** The reviewer recommended that the D1 to D6 dispositions from the version 4.1
review be the normative starting point for version 4.2; that the reviewer identity be
recorded as above; and that version 4.2 design work proceed now, since gate items 1 to 7
and the design of item 8 do not depend on flowchart ruling 1 or the ratification memo's
experiment-tier decision, with no environment experiment executing until both are
resolved, and with authority covering drafting only, not M15 implementation and not
pipeline publication. Adopted.

**Owner adoption, adopted by explicit reference on 2026-09-12.** The owner expressly
adopted the reviewer-drafted statement below and directed that it be recorded verbatim.
The text was drafted by the reviewer (OpenAI GPT-5); the adoption is the owner's act of
express reference to it. Recorded verbatim:

"I adopt the recorded CEC-1 to CEC-5 and placement rulings, together with the
outside-family reviewer's dispositions for GERL versions 4.1 and 4.2.1. I confirm OpenAI
GPT-5 as the outside-drafting-family reviewer and authorize drafting GERL 4.2.2 against
the outstanding review gate. GERL 4.1 and 4.2.1 remain NOT_RATIFIED. I authorize no-code
contracts-stage scoping only; this does not authorize tracked implementation, M15
operation, governed-memory mutation, pipeline publication, or environment experiments. The
admission boundary is the first enforcing consumer, and the recalibration executor is
solely the admitted mutation path."

This statement adopts: the placement rulings; CEC-1 to CEC-5 with their conditions; the
reviewer's dispositions on versions 4.1 and 4.2.1, including the D1 to D6 dispositions;
the reviewer identity; the staging rulings below, including the admission boundary as the
first enforcing consumer and the executor as the sole admitted mutation path. It authorizes
drafting version 4.2.2, which had been drafted earlier the same day under the owner's
standing instruction and is now covered by this authorization, and no-code contracts-stage
scoping. It authorizes nothing else. As at the date of adoption, versions 4.1 and 4.2.1 were
NOT_RATIFIED and version 4.2.2 was undrafted for review; the review history since that date
is recorded in section 7 and supersedes this sentence as a statement of status.

**Staging rulings recommended by the same reviewer on 2026-09-12, adopted by the owner
the same day (see "Owner adoption").** (1) A no-code, contracts-only scoping stage is authorized now; tracked
contract implementation only after version 4.2.2 or later passes outside-family review,
the applicable rulings are adopted, and the contract schema is frozen. (2) The first
enforcing consumer of a ClassificationRecord is the **admission boundary**, which enforces
the record and the M6 authorization together; not the recalibration executor, which is the
sole writer and applies only an admitted exact delta; not M3 or M11, which are read
consumers. The drafting family's earlier recommendation of the executor as first enforcer
was wrong and would have collapsed admission into execution. (3) Three stages: Stage 1,
contracts and inert substrate; Stage 2, offline classification with no authorization or
enforcement; Stage 3, enforced recalibration through review, M6, admission boundary,
executor, governed memory and eligible reads. (4) Policy content stays inert: the
policy-family contract may exist, but its initial delegation table is empty or explicitly
inactive, and D1, D3, D4 and D5 are not encoded as operative entries before their
parameters and mechanisms are ratified.

**Left open, current at 2026-09-13.** Archive
custody; the owner parameters the rule marks [R]; flowchart ruling 1 and the
experiment-tier decision; the package split and conformance-profile timing from the Stage 1
scoping. The classification rule itself is **conditionally ratified at version 4.2.10** (§7);
every earlier version reviewed — 4.1, 4.2.1, 4.2.3, 4.2.4, 4.2.5, 4.2.6, 4.2.7, 4.2.8 and
4.2.9 — was NOT_RATIFIED and none of them is the normative design. Tracked implementation, M15
operation, governed-memory mutation, pipeline publication and environment experiments are
not authorized.

**Module map corrections adopted with the rulings.** The loops share the anomaly record
and the platform's policy, evidence, review, authority and audit infrastructure, not the
record alone. The sandbox performs no external actions; approved recalibration changes
governed internal state; external experiments use the action path. Reuse of M6 and M7 is
of their kernels, not of adapters that do not exist. Policy governance is labelled outside
this proposed scope, since M1 is already Policy Authority. The cover count reads "one
hosted boundary where the product can enforce", spanning M8 and M9 as unit 1 of the
preventive/detective map, rather than "one module".

## 6 — Relation to the module-flowchart rulings `[V]`

Section 20 of `docs/UGENCE_MODULE_FLOWCHARTS.md` (`:1138-1142`) names two owner
rulings. **Ruling 1**, which clearance path is canonical: the offline classifier does not depend
on it, since it never clears and emits no CLEAR, HOLD, BLOCK or ESCALATE; environment
experiments raised by the learning loop do depend on it, and stay blocked until it is
taken. **Ruling 2**,
whether `control-plane-root` becomes the sink for the other ledgers: depended on for
record placement only, and CEC-3 is sufficient under either outcome. Section 18's
ledger row, "one chain per tenant does not exist" (`:1125`), is the reason CEC-3 uses
the linkage pattern rather than assuming a chain.

## 7 — Next step

The owner has adopted the rulings. The design phase is complete at version 4.2.10, conditionally
ratified. What remains is not design: it is the external conditions listed below and the owner's
separate authorization. The chain waits on those and on the owner parameters and rulings listed
under "Left open, current at 2026-09-13". Tracked contract implementation begins only when a version passes review, the
schema is frozen, and the owner authorizes it in a further statement.

A same-family consistency check of version 4.2.2 on 2026-09-12 found five gaps: no
explicit rule for a route while registries are UNEVALUATED; the authorization did not pin
the ConfirmationAmendment; FAILED did not consume the authorization; an infeasible disjoint
confirmation sample had no defined outcome; decision types had no registry. All five are
closed in version 4.2.3 the same day, which changes nothing else and is covered by the
owner's drafting authorization.

**Review of version 4.2.3, recorded.** Version reviewed: 4.2.3. Reviewer: OpenAI GPT-5,
separate from the Anthropic Claude drafting family. Outcome: NOT_RATIFIED. Gates closed:
trusted-base change controls at design level; document metadata. Gates partially closed:
evaluation states; one-way digest chain; admission state machine; confirmation protocol;
measurement definitions. Of the five 4.2.3 fixes: FAILED-consumes-authorization and
INSUFFICIENT_ARCHIVE closed, decision-type vocabulary closed narrowly, the provisional route
not fully closed, the amendment pinning partially closed. Five structural blockers: R4 and
R6 vacuous when nothing is measured; a frozen obligation list that admission required to be
empty; admission state transitions that would mutate an append-only record; D1 testing
disparity level instead of the candidate's change; exposure and numerator not distinct.
Required revision: 4.2.4, six items. The reviewer's forward statement: after those
corrections pass outside-family confirmation, the rule may serve as M15's normative design
once its [R] parameters are ratified and archive custody exists; production capability
would still require demonstrated evidence and separate implementation authorization.

Version 4.2.4 was drafted the same day against the six items and nothing else, under the
owner's standing instruction and drafting authorization, and returned to the same reviewer.

**Review of version 4.2.4, recorded.** Version reviewed: 4.2.4. Reviewer: OpenAI GPT-5,
separate from the Anthropic Claude drafting family. Outcome: NOT_RATIFIED. Of the six 4.2.4
gate items: R4/R6 and the undetermined route closed; D1 and exposure counting closed at
design level, with the statistical method, margin and power rules remaining owner
parameters; effective obligations and immutable admission records partially closed; the
version and adoption corrections closed in the PDF but incomplete across the record set.
Five structural blockers: the confirmation sequence contradicted itself across Figure 2, the
prose and Figure 3; authorization was not bound to the final classification state; investigation
closure had no immutable record of its own; the admission chain had no fork prevention; and the
associated documents — this ADR and the Stage 1 scope — were inconsistent with the chain.
Required revision: 4.2.5, six items. The reviewer's forward statement is unchanged from
4.2.3: after those corrections pass outside-family confirmation, the rule could serve as
M15's normative design once its [R] parameters are ratified and archive custody exists; that
would still not authorize implementation or establish production readiness.

Version 4.2.5 was drafted on 2026-09-13 against the six items and nothing else, under the
owner's standing instruction and drafting authorization, and returned to the same reviewer
together with this ADR and the Stage 1 scope. Its document reconciliation moved the
confirmation fields out of the ClassificationRecord, made InvestigationRecord an opening
record with extension and closure successors, added the FinalResolutionRecord and removed
DispositionAmendment, repointed AuthorizationBinding at the final resolution, and added
single-successor semantics with `CHAIN_FORK_REFUSED`.

**Review of version 4.2.5, recorded.** Version reviewed: 4.2.5, with this ADR and the Stage 1
scope. Reviewer: OpenAI GPT-5, separate from the Anthropic Claude drafting family. Outcome:
NOT_RATIFIED. Of the five 4.2.4 blockers, one closed — authorization is now bound to the final
classification state — and four closed partially: two stale confirmation statements survived,
the investigation records had no defined position in the record graph, fork prevention was
specified as an outcome rather than a mechanism, and the Stage 1 scope's claimed linear order
omitted the investigation opening and extension. Five findings on the corrections themselves:
a final resolution cannot always be emitted and should not be, since terminating investigation
outcomes end a candidate without one; nothing prevented a later record attaching behind a
resolution; the empty effective set was asserted rather than recomputable, for want of a
binding between an obligation, its opening, its closure and the result that replaces the
unevaluated one; single-successor enforcement requires an atomic conditional append, which a
refusal code does not supply; and the Stage 1 record types can remain computation-free, which
the scope should say explicitly. Required revision: 4.2.6, six items. The reviewer's forward
statement is unchanged: after those corrections pass outside-family confirmation, the rule
could serve as M15's normative design once archive custody and the [R] parameters are
ratified; implementation and production operation would still require separate authorization
and demonstrated enforcement evidence.

One factual correction the reviewer supplied and this record adopts: the version 4.2.5 PDF is
18 pages, not the eight reported to the owner when it was sent `[V]` (page count read from the
file). The drafting family's report was wrong; the reviewer's count is correct.

Version 4.2.6 was drafted on 2026-09-13 against the six items and nothing else, under the
owner's standing instruction and drafting authorization. Item 6 of that gate is discharged by
this section and by the revision of `STAGE1_CONTRACTS_SCOPING.md` the same day: the record
inventory is stated as a directed acyclic graph rather than a linear order, with the contract
rule that every pinned digest must already exist when the pinning record is sealed; each
blocking obligation carries a stable `obligation_id` that the opening InvestigationRecord pins
alongside the record that introduced it, with `OBLIGATION_UNKNOWN` for an orphan; the
terminating closure outcomes are named as ending a candidate without a resolution; the
FinalResolutionRecord is terminal and unique and a ResolutionRevocationRecord is added, so the
inventory is eleven record types, not ten; the atomic conditional append over
`(chain_id, predecessor_digest, transition_kind)` is declared as a required audit-root
capability, unverified against `AuditLedger.append` `[G]`, with `APPEND_UNIQUENESS_UNAVAILABLE`
as the fail-closed refusal; and the scope states explicitly that the five-step final-resolution
projection, terminal-head verification and conditional append belong to the Stage 2 and Stage 3
boundaries, not to the contract types. A sixth owner decision now stands open in the rule: which
authority may sign a ResolutionRevocationRecord, and whether revoking an applied delta always
requires a remediation candidate.

**Review of version 4.2.6, recorded.** Version reviewed: 4.2.6, with this ADR and the Stage 1
scope. Reviewer: OpenAI GPT-5, separate from the Anthropic Claude drafting family. Outcome:
NOT_RATIFIED, with the reviewer stating that the remaining defects are still structural rather
than only archive custody and parameter ratification. One gate item was found not closed and
five partially closed. The load-bearing finding: the `obligation_id` was defined as a digest
over the introducing record's digest while that record carries the identifier, so the
identifier could not be constructed at all. The others: "re-enters at step 0" contradicted the
frozen-chain model, since re-entry creates a new record and new identifiers while the design
requires substitution inside the existing chain; substitution covered only an UNEVALUATED
registry result, leaving the other obligation kinds — cells, denominators, baselines, custody,
NO_ANCHOR, D1 bounds, confirmation disagreement — with no defined projection; terminal-head
verification had a time-of-check to time-of-use race against a revocation or late append
committing before the reservation; Figure 4's arrows ran chronologically while its caption
declared them pins, so the normative edge meaning was stated twice in opposite directions; the
uniqueness constraint did not cover the ConfirmationAmendment or the one-opening-per-obligation
rule; and the revocation text mandated a remediation candidate in every case while owner
decision 6 recorded that choice as open. Required revision: 4.2.7, eight items. The reviewer's
forward statement: until that gate passes, 4.2.6 cannot serve as M15's normative design;
afterwards the remaining blockers could reduce to archive custody, audit-root capability
verification, the [R] parameter decisions and separate implementation authorization.

Version 4.2.7 was drafted on 2026-09-13 against the eight items and nothing else, under the
owner's standing instruction and drafting authorization. Item 8 of that gate is discharged by
this section and by the revision of `STAGE1_CONTRACTS_SCOPING.md` the same day: the stale "per
rule version 4.2.5" reference is corrected; the identifier is derived from a `chain_id` fixed
at step 0 and never from the digest of the record that carries it, with `OBLIGATION_ID_MISMATCH`
for a record whose identifiers do not recompute and with stability scoped to one chain; the
InvestigationClosureRecord carries a typed closure effect from a named set rather than a
registry-result substitution, with `CLOSURE_NOT_EXPRESSIBLE` as the terminating reason for an
evaluation that cannot resolve in the chain; the ResolutionRevocationRecord carries the exposure
window and the served reads; the reservation carries the `head_version` it was appended under;
and the conditional-append constraint is extended to the amendment, the opening, the extension,
the closure, the resolution and the revocation, with `HEAD_MOVED` and `CHAIN_SEALED` as the
refusals the audit root produces and the contracts merely name. The record inventory is
unchanged at eleven types. Owner decision 6 is narrowed rather than closed: withdrawal,
read-ineligibility and the recorded exposure window now follow from revocation in every case,
and only the remediation-candidate scope remains open. Return version 4.2.7, this ADR and the
Stage 1 scope to the same reviewer.

**Review of version 4.2.7, recorded.** Version reviewed: 4.2.7, with this ADR and the Stage 1
scope. Reviewer: OpenAI GPT-5, separate from the Anthropic Claude drafting family. Outcome:
NOT_RATIFIED. Eight structural findings, none of which parameter ratification or archive
custody would have removed. (1) `chain_id` was not unique per attempt and its timing
contradicted the procedure: the rule said the family seed was fixed at step 0 while step 3
generated it, and an identical candidate returning after a terminating closure would have
produced the same chain. (2) A different sample was declared non-expressible while
INSUFFICIENT_EVALUATION was resolved with a larger sample under a new seed. (3) The
one-effect-per-obligation model could not represent obligations needing compound updates:
MISSING_BASELINE demanded a baseline and dependent registry replacements, CUSTODY_UNVERIFIED
combined custody with a no-change operation, NO_ANCHOR closed through CONFIRM_NO_CHANGE while
the anchor remained missing, and INSUFFICIENT_ARCHIVE's status was unsettled. (4) Conflict
detection and recomputation were undefined, so canonical order silently chose between
conflicting evidence and a condition arising after recomputation had no outcome. (5) Figure 4
did not show that an opening's two parents are mutually exclusive. (6) `head_version` had no
defined interface, and a successful reservation still raced physical application, so a
revocation could commit between them. (7) Expressibility was left where an administrative
investigation owner could decide it. (8) The associated documents needed reconciling. Required
revision: 4.2.8, eight items, with a mandatory adversarial whole-document self-check over
fourteen named cases.

Version 4.2.8 was drafted on 2026-09-13 against the eight items and nothing else, under the
owner's standing instruction and drafting authorization. Item 8 is discharged by this section
and by the revision of `STAGE1_CONTRACTS_SCOPING.md` the same day. The substantive closures:
`chain_id` now digests tenant identity, candidate digest, anomaly family, family seed and a
classifier-issued `chain_instance_id`, and step 0 is four ordered sub-steps — family, seed,
instance identifier, chain identifier — all preceding the record's seal, whose append is
conditional on the chain being unused (`CHAIN_ID_IN_USE`); a named **frozen input set** makes a
supplemental sample expressible in chain and an anchor, environment, evaluator, delta, snapshot
or policy change not, with no third path; a **ClosureEffectBundle** of one or more of six
primitive effects replaces the single typed effect, and no effect writes a derived value, which
removes all four of the reviewer's contradictions and makes NO_ANCHOR unable to close in chain
at all; every bundle declares its write set, intersecting or out-of-scope writes are
`CLOSURE_EFFECT_CONFLICT`, primitives are applied before a single recomputation of every derived
value, and a surviving condition is `COMPLETED_STATE_UNRESOLVED`, both terminating; Figure 4
carries an XOR arc over the opening's two parents; `head_version` is defined as an opaque token
from an authoritative linearizable chain-head read, with a new **AdmissionClaimRecord** on which
an executor's APPLY and a revoking authority's CANCEL race for one slot, so a revocation either
prevents the write or provably follows it; and four authorities — evaluator, projection
verifier, reviewer, investigation owner — are separated, with `CLOSURE_NOT_EXPRESSIBLE` computed
by the verifier and expressly outside the owner's power. The record inventory rises to twelve,
the one count change the gate permits. The rule adds a `[G]` the repository cannot yet close: no
component here is verified to supply a linearizable chain head, and without one the admission
boundary fails closed, so on today's substrate no admission could proceed.

**Review of version 4.2.8, recorded.** Version reviewed: 4.2.8, with this ADR, the Stage 1
scope and the accompanying conformance model. Reviewer: OpenAI GPT-5, separate from the
Anthropic Claude drafting family. Outcome: **NOT_RATIFIED**. Eight required corrections. (1)
Revocation and APPLY sat in two concurrency domains, so a durable revocation could be followed
by an APPLY winning a separate claim slot; one linearizable domain was required, with the exact
keys, expected version, transition and failure codes stated and a proof that no ordering admits
a write after a committed revocation. (2) The case of revocation after APPLY but before the
physical write was undefined, and an immutable revocation record was required to carry an
exposure window not yet knowable. (3) The evaluator retained discretion over the bundle; a
deterministic, versioned mapping from obligation kind, signed result, frozen inputs and policy
version was required, with the verifier recomputing it and testing completeness, so that
selective omission could not provoke a termination. (4) Supplemental-sample seeds were not
required to be independent, and the sample was not bound well enough for a reviewer to
reproduce it. (5) INSUFFICIENT_ARCHIVE could appear resolved on a sample reference with no
observations. (6) The identifier encoding was informal. (7) The Stage 1 scope still said "three
admission record types" when 4.2.8 had four. (8) The 30-scenario simulation omitted most of the
graph and substituted flags for it, so its passes did not validate the normative design.

Version 4.2.9 was drafted on 2026-09-13 against the eight items and nothing else, under the
owner's standing instruction and drafting authorization. Item 7 is discharged by this section
and by the revision of `STAGE1_CONTRACTS_SCOPING.md` the same day, which corrects the admission
count to four types and carries every other change through. The substantive closures: APPLY and
revocation are each a **compare-and-advance on one linearizable control register per
resolution**, and section 8a proves the exhaustive case split by which no APPLY can commit
after a revocation, leaving the CANCEL record documentary; the revocation record carries the
decision alone and a new **RevocationImpactRecord** carries application, ordering, exposure
window, read receipts, eligibility and the owner-decision-6 remediation question, taking the
inventory to thirteen; the evaluator signs only a raw **EvaluationResult** while a
policy-governance-owned, versioned **ClosureBundleMapping** derives the canonical bundle that
the verifier independently recomputes, so a withheld field is `EVALUATION_RESULT_INCOMPLETE`,
which blocks the closure and never terminates the candidate; supplemental seeds come from
classifier-controlled randomness alone, with `SEED_AUTHORITY_INVALID` for any other source, and
each sample binds seed, authority, archive snapshot, algorithm and version, population, the
whole prior sample history and a recomputable disjointness proof, with `SAMPLE_EXHAUSTED`
blocking rather than resolving; INSUFFICIENT_ARCHIVE requires sample, observations and every
measurement the evaluation contract names; and section 6a fixes the byte projection by adopting
the repository's existing canonical-serialization convention `[V]` rather than inventing one,
with eight test vectors including the concatenation-ambiguity pair.

**On the conformance model.** The 30-scenario simulation the reviewer rejected is replaced by a
model that executes the record graph itself — identifiers under the canonical encoding,
classification, amendment, investigation opening, extension and closure, bundle derivation and
verification, the projection and R1 to R6, sealing and successor uniqueness for every record
type, the shared control register, FAILED and OUTCOME_UNKNOWN with human resolution, revocation
and impact, read eligibility and served receipts, sample history and disjointness, and actor
authority checks. It runs **91 scenarios, 0 failing**, including an exhaustive interleaving
search for a revoked-then-accepted APPLY. It is a conformance model of the normative text and
establishes nothing about repository behaviour; no component it models exists in
`rasaha/symbolu`.

**Review of version 4.2.9, recorded.** Version reviewed: 4.2.9, with this ADR, the Stage 1
scope and the conformance model. Reviewer: OpenAI GPT-5, separate from the Anthropic Claude
drafting family. Outcome: **NOT_RATIFIED**, with the reviewer stating that the remaining
defects had not reduced to parameters and infrastructure. The findings: (1) the control
register coordinates APPLY against revocation **within one resolution** and does not relate two
resolutions writing the same governed-memory target, so two candidates could bind one
pre-state and apply in sequence; (2) retry semantics contradicted the documentary CANCEL —
after a bare revocation a RESERVED admission with no claim still reported "claimable"; (3) the
RevocationImpactRecord's fields were accepted from the caller rather than reconstructed and
verified; (4) the model did not derive the normative graph from immutable records, so its
passes proved the consistency of a simplified Python interpretation rather than conformance;
(5) the mapping's self-modification path was substantially answered but should be stated
explicitly; (6) the codec was specified but not enforced, and "adopts unchanged" was inaccurate
since GERL adds normalisation and validation rules; (7) the Stage 1 scope still said the
evaluator produces the bundle and attributed the authority split to 4.2.8; (8) the PDF repeated
one confirmation-agreement sentence. A packaging failure was also recorded: the suite as sent
imported `model`, which resolved to an older file, and reproduced only after an undocumented
rename.

Version 4.2.10 was drafted on 2026-09-13 against the eight items and nothing else, under the
owner's standing instruction and drafting authorization. The substantive closures: the
reservation and the APPLY claim now bind `(tenant, target, expected target version)` and the
mutation is an **all-or-nothing compare-and-apply** over the target set, so of two resolutions
built on one pre-state at most one applies and the other records `STALE_TARGET`; retry is
answered from the **control register**, so a RESERVED admission whose register reads REVOKED is
terminally CANCELLED whether or not a CANCEL record exists; the impact record is **derived and
verified** with `IMPACT_MISMATCH`, a completion-absence determination is admissible only where
no APPLY claim was ever made, and a stalled executor is resolved by the recovery rule rather
than treated as absence; the mapping is stated to be unreachable by any delegation entry,
constitution-tagged under R1 and non-retroactive; and section 6a is restated as a **profile**
over the repository envelope, with recursive NFC, int64-only numbers, refusal of JSON booleans
in favour of enumerated strings, and explicit collection rules. The record inventory is
unchanged at thirteen; the admission record types are four.

**On the conformance model, rebuilt.** Normative state now lives only in the append-only
ledger: obligations, closures, sealing, the final resolution's pinned digests, admission state
and revocation impact are all reconstructed from immutable records, and governed memory is a
single store shared across admissions rather than a private dictionary per admission. The
codec enforces the profile it specifies. The suite runs **101 scenarios, 0 failing**, under
`run_conformance.py`, a manifest runner that prints each file's SHA-256 and **refuses to run
while an older `model.py` is present**, which is the packaging failure the reviewer hit. Two
defects were found during drafting: the codec's boolean refusal rejected the rule's own
`effective_set_empty: true` field, which is why flags are now enumerated strings; and one
forged-impact test was vacuous because its fixture served no reads. Both were fixed before the
build. The model is a conformance model of the normative text and establishes nothing about
repository behaviour.

**Adversarial probe of 4.2.10, recorded.** After drafting, eight constructions were run as
executable probes against the drafted design, each attempting to build a violation rather than
to confirm a sentence (`adversarial_probe.py`). Five findings resulted, four of them defects in
the drafted version and one a modelling weakness; all were fixed before the delivered build.
(a) **A legitimate retry was structurally impossible.** The rule says a FAILED completion
consumes the authorization and the change may be applied again under a new one, but the
reservation transition was keyed `(chain, resolution, ADMISSION_RESERVE)` and the control
register stayed APPLY_COMMITTED, so no second reservation could ever be made. The transition now
includes the authorization digest, and a completion that applied nothing — FAILED, including
FAILED for STALE_TARGET, and a human resolution to FAILED — returns the register to ACTIVE in
the same conditional append. APPLIED stays terminal for the register; REVOKED stays terminal
absolutely. A reservation attempted while an APPLY is in flight is now ADMISSION_IN_FLIGHT and
is no longer misreported as RESOLUTION_REVOKED. (b) **A cross-tenant delta was undefined.** The
rule described the target set as "(tenant, target) pairs", which admits more than one tenant; an
atomic write across two tenants' governed memory would make one tenant's admission depend on
another's state. The target set is now within one tenant and CROSS_TENANT_DELTA refuses the
rest. (c) **An extension could be appended behind its own closure**, which INVESTIGATION_SEALED
now refuses. (d) **Governed memory trusted its caller's tenant argument**; it now reads the
tenant, the target set and the expected versions from the reservation record, so the executor
supplies a delta and nothing else, with TARGET_SET_MISMATCH for a delta that differs from what
was reserved. (e) Two coverage gaps: R6's DESCRIPTIVE_STATE branch was unreachable in the model
and no scenario joined a drawn sample to the bundle that consumes it. Both are now exercised.
The suite is **116 scenarios, 0 failing**, and the probe re-runs with **0 findings**.

**Review of version 4.2.10, recorded. Outcome: `RATIFIED WITH ONE CONFORMANCE CORRECTION`.**
Version reviewed: 4.2.10, with this ADR, the Stage 1 scope, the conformance model and the
adversarial probe. Reviewer: OpenAI GPT-5, separate from the Anthropic Claude drafting family.
The reviewer found the target-level compare-and-apply, retry semantics, impact projection,
sampling bindings, bundle mapping, codec profile and document reconciliation adequate, ruled
that version 4.2.10 **may serve as M15's normative design once the external conditions below are
satisfied**, and required neither a version 4.2.11 nor a further broad review. This is the first
version of the rule to be ratified in any form; every earlier reviewed version was NOT_RATIFIED.

**The one correction, and how it was closed.** The reviewer found an untested interleaving the
drafting family's suite had missed: the model returned the control register to ACTIVE on a
FAILED completion *unconditionally*, so a completion arriving after a revocation resurrected a
revoked resolution and a new reservation was accepted; and an APPLIED completion left the
register at APPLY_COMMITTED rather than moving to a terminal state. The defect was in the
drafting family's own correction of an earlier finding, and it was reproduced exactly as the
reviewer described before being fixed. The binding correction is implemented: a completion or a
human resolution moves the register **only** through a versioned conditional transition out of
APPLY_COMMITTED, so FAILED returns it to ACTIVE only by winning before a revocation; where the
revocation won, the completion is still recorded and the register stays REVOKED; APPLIED moves
APPLY_COMMITTED to a terminal APPLIED, from which a later revocation may still move it to
REVOKED; a human resolution obeys the same rule and can never move REVOKED back to ACTIVE. A
reservation now distinguishes RESOLUTION_REVOKED, RESOLUTION_ALREADY_APPLIED and
ADMISSION_IN_FLIGHT. The rule carries the complete transition table as a recorded **erratum to
4.2.10**, which the reviewer accepted in place of a new version; the normative text already said
REVOKED is terminal absolutely, so no architecture changed. The suite is **132 scenarios, 0
failing**, with every completion-versus-revocation interleaving covered, and the adversarial
probe re-runs with 0 findings.

**What remains before operation, none of it design.** Archive custody. Verification that the
audit root supplies the required linearizable head and control operations. Verification that
governed memory supplies atomic target-version compare-and-apply. Ratification of the [R]
parameters. Owner decision 6. And separate owner authorization before any tracked
implementation. Until all six are satisfied, the conditional ratification authorizes nothing:
version 4.2.10 is a ratified design, not an operating capability, and no component it describes
exists in this repository.

Version 4.2.10, as corrected by the recorded erratum, is the rule's current state. It is not ratified, it is not M15's normative
design, and archive custody, verification that the audit root can supply **both** required
linearizable registries, the [R] parameters, owner decision 6 and separate implementation
authorization all remain open. Return version 4.2.10, this ADR, the Stage 1 scope and the model
to the same reviewer. Nothing further from the drafting family counts as review.


## 8 — Owner authorization — 2026-09-13

Recorded verbatim, in the owner's own words:

> I record the outside-family reviewer's ruling of RATIFIED WITH ONE CONFORMANCE
> CORRECTION on GERL target classification version 4.2.10, together with the recorded
> erratum, as the classification rule's current state.
>
> I confirm that this ratifies the design and does not authorize M15 operation,
> governed-memory mutation, pipeline publication, or environment experiments.
>
> I authorize Stage 1 contracts-only implementation as tracked work, strictly within the
> ratified Stage 1 scope. Stage 1 must remain inert: no classifier, routing execution,
> admission enforcement, memory reader or writer, runtime registration, or operative
> policy content.
>
> Progress beyond Stage 1 remains unauthorized until archive custody exists, the audit
> root is verified to supply the required linearizable operations, governed memory is
> verified to supply atomic target-version compare-and-apply, the [R] parameters are
> ratified, and I issue a separate authorization.
>
> I defer owner decision 6 pending a separate presentation of its exact alternatives,
> recommended default, and operational consequences.

This is the first authorization in this chain to permit a tracked-file change. It permits
exactly one thing: the Stage 1 items of
`docs/architecture/STAGE1_CHANGE_EFFECT_CLASSIFIER_CONTRACTS_SCOPING.md`, each inert by
construction. It permits no classifier, no routing execution, no admission enforcement, no
memory reader or writer, no runtime registration and no operative policy content.

**Two Stage 1 owner decisions steer the work and neither was taken.** Implementation
proceeds under stated assumptions, each reversible before the schema is frozen. Stage 1
decision 2, the package split: taken as the scope's own recommendation — one contracts
package for records, linkage and admission state; one policy-family package; the provider
kind and the read port in the substrate. Stage 1 decision 3, conformance-profile timing:
taken as **Stage 2**, since Stage 1 registers no provider and a profile is required only
before one does; a test asserts the profile's continued absence so the assumption fails
loudly rather than silently.

### 8.1 — CEC-1 delivered, and what it cost

`ProviderKind.CHANGE_EFFECT_CLASSIFICATION` is appended as a fourth peer
(`packages/governance-contracts/src/ugence_governance_contracts/metadata.py`), with both
configuration labels so the kind is nameable rather than unaddressable
(`governance-provider-framework/.../configuration.py`). Nothing registers under it.

The Stage 1 scope recorded a `[G]` that its search "covered identity checks only" and found
no consumer that would break. That gap was real and the search was too narrow: it excluded
tests, and **four tests pinned the enum to exactly three members** — the contract-shape
assertion, the serialization baseline, the curated public-API manifest, and a framework test
named `test_three_distinct_kinds`. All four are baselines whose purpose is to surface exactly
this change; each is updated here and cites this ADR. The framework test is renamed
`test_four_distinct_kinds`. Adding a fourth member to a shared enum is therefore not free,
and the scope should not have implied it was.

Verified `[V]`: `governance-contracts` and `governance-provider-framework` 325 passed, 3
skipped, unchanged from the pre-change baseline; `providers/tap` 82 passed;
`providers/actiongate` 62 passed; `policy-authority` and `integration/control-plane-root`
pass. A new test file asserts the kind's Stage 1 properties directly: peer and not conflated,
nameable in configuration, no provider registered under it, and no conformance profile yet.
`[G]` Package test collection across the whole repository fails in this environment for want
of installed distributions; that failure is present on a clean tree and is not caused by this
change.

## 9 — Owner decision 6, taken — 2026-09-13

Recorded verbatim, in the owner's own words:

> 6a. The authority that issued the authorization for the classification's governance
> route may sign the ResolutionRevocationRecord and may take the documentary CANCEL claim.
> The signer must never be the candidate's proposer or reviewer. A separate incident
> authority is not authorized by this ruling; one may be added later only through a
> separately ratified authority assignment.
>
> 6b. When an applied delta is revoked, a state-repair or compensating candidate is
> required in every case, regardless of whether the governed read port served the changed
> state.
>
> Downstream-exposure remediation is a separate obligation. It is required when at least
> one read was served under the revoked state. Until archive custody exists and the
> served-read log is custody-assured, the conservative presumption is that exposure
> occurred. Once custody assurance exists, a verified zero-read record may waive
> downstream-exposure remediation, but it may not waive the state-repair candidate.

The owner also confirmed the Stage 1 package split recorded in §8 and confirmed that the
`CHANGE_EFFECT_CLASSIFICATION` conformance profile belongs to Stage 2, with Stage 1
continuing to register no provider. Both assumptions §8 recorded are therefore closed.

**6b improves on what was presented.** The drafting family's memo offered a single
remediation question and recommended "always, narrowing to read-triggered once custody
exists". The ruling separates two obligations the memo had conflated: **state repair**,
which follows from the fact that governed memory now holds a delta whose authorization was
withdrawn and which nothing waives; and **downstream-exposure remediation**, which follows
from reads actually served and which a custody-assured zero-read record may one day waive.
Under the memo's wording a future zero-read finding would have waived both. It should not,
because a withdrawn authorization leaves the state wrong whether or not anyone read it.

The distinction is carried into the contracts: `RemediationRequirement` has three members
— `NONE`, `STATE_REPAIR_REQUIRED`, and
`STATE_REPAIR_AND_EXPOSURE_REMEDIATION_REQUIRED` — and `RevocationImpactRecord` refuses a
record that reports an applied delta with no remediation at all, and equally one that
reports remediation where nothing was applied. `exposure_presumed` carries the conservative
presumption explicitly, so a record written before custody exists cannot be mistaken later
for a verified zero-read finding.

6a is carried as `signer` and `signer_authority` on `ResolutionRevocationRecord`. Which
authority issued which route is a Stage 3 verification against the authorization; the
contract holds the fields and checks neither, because checking would require reading
another record.

## 10 — Stage 1 items 3.4 and 3.5, and the second dependency — 2026-09-13

The owner's ruling, recorded verbatim:

> The second dependency is admissible only for the item 3.4 linkage module. No record,
> identifier, canonicalization, vocabulary or admission-data module may import
> ugence_control_plane_root. Add a boundary test enforcing that restriction. Import only
> the immutable ledger/entry contract types actually needed; do not call or wrap
> AuditLedger.append, instantiate a ledger, or imply that the existing ledger satisfies
> conditional append, linearizable control-register, chain-head or target-version
> requirements. Those capabilities remain declared gaps. For item 3.5, keep the read-port
> contract neutral: define its request and typed eligibility result in
> governance-contracts, with no dependency back to change-effect-records, no
> implementation, cache, store or eligibility computation.

Both items are delivered on those terms.

**3.4, and why the confinement is structural rather than documentary.** `linkage.py` is the
only module in `change-effect-records` that imports `ugence_control_plane_root`, and it
imports `LedgerEntry` alone. `AuditLedger` is deliberately absent: a package that must not
append should not hold the means to, and importing the thing that appends would have made
the prohibition a matter of discipline. Two boundary tests hold the line — one over every
source file, naming any offender, and one that pins the imported names to exactly
`{LedgerEntry}`. A third asserts nothing instantiates a ledger type or appends to a
ledger-shaped receiver; it distinguishes that from Python's list `.append`, because a bare
ban on the word would have caught every list in the package and proved nothing.

**The declaration claims nothing about the existing ledger.** `REQUIRED_AUDIT_ROOT_CAPABILITIES`
names four capabilities the rule requires — atomic conditional append, linearizable chain
head, linearizable control register, linearizable target-version registry — each with what it
must guarantee and why it cannot be assumed, and **each carrying status `DECLARED_GAP`.** A
test asserts all four remain gaps, so a future commit that quietly marks one satisfied has to
change a test that says why it cannot be. `APPEND_UNIQUENESS_UNAVAILABLE` is named as the
fail-closed refusal of a Stage 3 boundary that does not exist.

**3.5, kept neutral.** The read port lives in `governance-contracts` beside `Provider` and
names no record type; it would be a coherent contract if `change-effect-records` did not
exist. Two properties are held by the shapes rather than by discipline. The determination
**refuses truthiness** — `bool(eligibility)` raises — because `if eligibility:` is the
mistake the port exists to prevent: it would read `INDETERMINATE` as permission and would
keep working after a revocation. And it carries the `authorization_digest` it was computed
under, with `answers()` tying it to one tenant, consumer, purpose, target and version, so a
determination cannot be detached from the question it answered. There is no implementation
here or anywhere; tests assert the Protocol method's body is `...`, that the module holds no
state and memoizes nothing, and that it imports no store, clock or network.

`[V]` change-effect-records 103 passed; governance-contracts 252 passed, 3 skipped.
Unchanged, each run alone: governance-provider-framework 88, tap 82, actiongate 62,
control-plane-root, agent-assurance-evidence and policy-authority pass. `[G]`
governed-review-service fails collection in this environment for want of installed
distributions, on a clean tree as well as this one.

Stage 1 item 3.2, the policy family, is not started. Progress beyond Stage 1 remains
unauthorized.
