# S2-B Round 2 — Strategy Vocabulary and Naming (design proposal)

> **PROPOSAL ONLY. THIS DOCUMENT RATIFIES NOTHING, AND NO IMPLEMENTATION IS AUTHORIZED
> BY IT.**
>
> It is a design proposal prepared for owner ratification and independent review. Every
> item in it is **ungranted** until the repository owner rules on it. It is **not** an
> ADR, it is **not** an owner declaration, and it must never be cited as authority.
> Where this document and
> [`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md`](ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md)
> or
> [`ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md`](ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md)
> differ, **those ADRs govern**.
>
> The S2-B §8 implementation gate is **closed** and this document does not open it. Only
> a ratification can, and none has been given for anything below.

**Date:** 2026-08-29.
**Baseline inspected:** branch `claude/s2b-reasoning-strategy-permission-zbc9rw` at
`c870298feb3f076125c0a30b881ff9d98c4e171e`, atop default-branch head
`90696d16ed8e9b9942252fe297c44bc3d16393a1`.

**Governed by, and reopening none of:** `S2B-D1` – `S2B-D8` and rider `R1`
(the S2-B scoping ADR); the owner declaration `S2B-S1-Q1` – `S2B-S1-Q13` of 2026-08-29
(the first-slice ratification ADR); OD-1 … OD-10 and A11–A13; P-1 … P-11;
RCG-D1 … RCG-D10.

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` requires ratification; `[G]` an unresolved gap.

**Tense discipline.** Proposed behaviour is never described in the present tense.

**Scope.** This round supplies the two items Round 1 deliberately left open, and which
together are the last thing standing before §8's gate: the strategy vocabulary's
**members**, and every **concrete name**. `[V]` `S2B-S1-Q1=A` ratified the vocabulary's
admission criteria and shape rules but no member; `S2B-S1-Q2=A` and `S2B-S1-Q6=A`
ratified field counts and the 46 → 51 public-surface movement but no name.

Short references below: **S1** =
`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`;
**ADR** = `ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md`.

---

## Part A — The vocabulary

### A.0 The admission test, applied

`S2B-S1-Q1=A` admits a member only if it is **(i)** externally evidenceable, **(ii)** not
a contract mechanism or an outcome, **(iii)** provider-neutral — with at least two
members, no default member and no escape member. Applied honestly, criterion (i) is far
more exclusionary than it first reads, and it is what would reject almost every phrase in
ordinary use.

**The ceiling, stated once and applying to every member below.** `[R]` A member would
describe **what the artifacts must show**, never what happened inside the producer. `[V]`
The specification is explicit that a linear record is compatible with internal iteration:
"the absence of repeated or branching transitions in a conformant record is not evidence
that no internal iteration or branching occurred" (`S1:1245`). No member may therefore be
worded as a claim about private process, and each below is defined by its observable
trace.

### A.1 Proposed members — three

| Member (spelling proposed, not settled) | What it would denote | Evidencing basis |
|---|---|---|
| `SINGLE_PASS` | the advisory carries exactly one candidate and is not a revision | `[V]` `candidates` is `1..n` and inside `P_unsigned` (`S1:1043`); `parent_advisory_digest` participates in identity **including when null** (`S1:1036`) |
| `PARALLEL_CANDIDATE_COMPARISON` | two or more candidates are carried into one advisory and reduced by the ratified selector | `[V]` the same `candidates` field; the selector and its policy identity are digest-bound (OD-8; OD-7 part 5) |
| `SUCCESSIVE_REVISION` | at least one revision advisory is bound to its parent by digest | `[V]` `build_advisory_revision` sets `parent_advisory_digest = parent.advisory_digest` and increments `advisory_version` (`S1:1836-1837`; B7 at `S1:377-386`) |

Three members, no default member, no escape member — satisfying `S2B-S1-Q1`'s shape rules
with one member to spare.

**ENTAILED** — that members must be evidenceable, exclusive of mechanisms and outcomes,
and provider-neutral (`S2B-S1-Q1=A`); that a member denotes an externally observable
orchestration procedure rather than an unobservable model disposition or a capability tier
(`S2B-D2=A`, `ADR:113-116`).

**CHOSEN** — these three members, their spellings, and the decision to define each by the
artifact evidence rather than by producer behaviour.

`[R]` **What each would not claim.** `SINGLE_PASS` would **not** claim that only one
candidate was ever considered: a producer that generated five and carried one forward
yields an identical artifact, and `S1:1245` states that the record cannot tell. It would
claim that the advisory carries one. The same shape of limit applies to the other two.

### A.2 Rejected candidates — recorded, because an implementer would reach for them

| Rejected | Why |
|---|---|
| `STAGED_DECOMPOSITION` | fails (i) **today**: `[G]` no field records stages or sub-questions, and R-3's forward-only chain cannot represent them (`S1:1231-1259`). Admissible later only if a producer of observable stages exists — the same gap that blocks `S2B-D8`'s conformance stage (`ADR:346-347`) |
| `SELF_CRITIQUE` / `REFLECTION` | fails (i) as private model behaviour, which `S2B-D2=A` bars as an "unobservable model disposition" (`ADR:113-116`); and if made observable it becomes **verification**, an OD-5 exclusion (`S1:1173`) |
| `TOOL_AUGMENTED` / `EVIDENCE_GATHERING` | is **evidence collection**, an OD-5 exclusion by name (`S1:1173-1189`) |
| `EXTENDED_REASONING` / `HIGH_EFFORT` | fails (iii): a model capability tier (`ADR:115-116`) and a compute claim, which would create the binding to Reasoning Compute Governance that S2-B forbids (`ADR:256-257`; RCG-D5) |

`[I]` The last three are the load-bearing rejections. Each is what a reader who has not
internalised OD-5 would propose first, and each would quietly convert a ratified mechanism,
or a compute question, into a matter of permitted method.

---

## Part B — The names

`[V]` No name below begins with `Proposal` or `Recommendation` (D7, `S1:2260-2261`); none
collides with `RESERVED_AUTHORITY_VOCABULARY`; and every proposed member spelling satisfies
the C5b pattern `^[A-Za-z0-9][A-Za-z0-9._:-]*$`
(`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/contracts.py:92`),
underscore included.

### B.1 Four field names

| Bearer | Proposed name | Class | Convention followed |
|---|---|---|---|
| `CognitiveRoleContract` | `strategy_policy_ref` | C5a | `[V]` `escalation_role_ref`, `owner_role_ref`, `source_ref` |
| `ProposerAdvisory` | `strategy_policy_id` | C5b | `[V]` `selection_policy_id`, `domain_evaluation_profile_id` |
| `ProposerAdvisory` | `strategy_policy_version` | C5b | `[V]` `selection_policy_version` |
| `ProposerAdvisory` | `declared_strategy` | C5b | **the same name the process record already uses** — see below |

**On reusing `declared_strategy`.** Recommended. Rider R1's rule is exact equality between
the two fields, and matching names would make that legible at every call site. `[V]` OD-3
already requires the I5 registry to be keyed by **bearer contract and field name, never by
field name alone**, precisely because `requested_review_action` is a different field on two
contracts (`S1:2454-2456`), so the shared spelling introduces no ambiguity the registry
cannot express. The alternative — `asserted_strategy` on the advisory — would avoid any
reader confusion about which field is authoritative, at the cost of obscuring that the two
must be equal.

### B.2 Five public names — the ratified 46 → 51

| # | Proposed name | Kind |
|---|---|---|
| 1 | `ReasoningStrategy` | enum — `[V]` `(str, Enum)` with values equal to member names, as every existing enum in `vocabulary.py:63-246` |
| 2 | `StrategyPolicyResolver` | protocol |
| 3 | `StrategyPolicyRequest` | call-boundary shape (not a contract) |
| 4 | `StrategyPolicyResponse` | call-boundary shape (not a contract) |
| 5 | `verify_strategy_permission` | function — `[V]` the `verify_*` convention, five existing |

**On `Resolver` rather than `Provider`.** `[V]` The tight precedent is
`DomainEvaluationProvider` (`contracts.py:780`), and symmetry argues for
`StrategyPermissionProvider`. Recommended **against**: a "permission provider" reads as
something that *grants* permission, and `S2B-D7=A` is emphatic that the declared strategy
is "bound as an assertion, never as an authorization" (`ADR:197-198`), with five identities
held distinct (`ADR:206-208`). `Resolver` names what the collaborator does — resolve a
policy — and cannot be misread as authorizing. `[R]` A genuine trade-off: precedent
symmetry against authority connotation.

### B.3 One question Round 1 did not reach

`[V]` `S2B-S1-Q3=A` narrowed `ProposerProcessRecord.declared_strategy` from C5c to C5b. It
did not settle whether the field would become the **closed enum** or a C5b `Token`
constrained separately. A closed enum is *narrower* than C5b, so this sits just outside
what that ruling covers.

`[R]` **Disclosed cost, either way.** Any S1-era process record carrying free-text
`declared_strategy` would fail validation under both options — the enum would reject it,
and the C5b `Token` would reject any spelling containing a space. `[I]` This is the same
class of cost OD-5 weighed when it rejected reserving the field early (`S1:2678-2682`), and
it should be ruled on rather than discovered at migration.

---

## Part C — Cardinality and surface: confirmed, not changed

This round would add **no** field and **no** public name beyond what `S2B-S1-Q2=A` and
`S2B-S1-Q6=A` already ratified. `CognitiveRoleContract` 11, `ProposerAdvisory` 30, private
unsigned payload 29, `ProposerProcessRecord` 18, `AdvisoryCandidateSet` 12,
`CandidateAdvisory` 11; public surface 51. It supplies the spellings for movements already
counted and ratified.

---

## Part D — Readiness verdict

## `S2B_R2_REQUIRES_OWNER_RATIFICATION`

No repository contradiction was found. If ratified, this round would close the last §8 gate
item — the vocabulary's members — and, with the names settled, **the gate would open**.

`[G]` Implementation would nonetheless remain blocked in fact until a strategy-permission
policy family is registered with Policy Authority (`ADR:343-344`), which is not this
package's work.

`[I]` That is the material difference from Round 1, and the claim in this document most
deserving of adversarial review: **this ballot, unlike the last one, could open the gate.**

---

## Part E — What would remain ungranted after this round

Everything in the first-slice ratification ADR's §3 except the vocabulary members:
strategy composition, ordering and subordinates (`S2B-D3=A`); mandate-level narrowing and
per-invocation authorization (`S2B-D4=A`); **required** strategies; the
operational-disposition owner for a structural permission failure (`S2B-D5=A`);
observable-procedure conformance replay and any producer of observable reasoning stages
(`S2B-D8`); registration of the strategy-permission policy family and its Policy Authority
adapter; a strategy-policy registry; any binding to Reasoning Compute Governance; and the
Agent Constitution. Plus `STAGED_DECOMPOSITION`, admissible only if observable stages ever
exist.

---

## Part F — Owner ballot (paste as-is)

```
S2-B Round 2 ratification — vocabulary members and names.
Governed by S2B-D1..D8, rider R1, and S2B-S1-Q1..Q13 (2026-08-29). Do not
reopen any of it. Letters only, one line per item. Every recommendation is A.
Each item states the rule PUT TO THE VOTE; none of it is in force until
answered.

R2-Q1  Members. Ratify exactly three: SINGLE_PASS,
       PARALLEL_CANDIDATE_COMPARISON, SUCCESSIVE_REVISION — each defined by
       what the artifacts show, never by private producer behaviour.
       A = ratify all three as stated [recommended]
       B = ratify a subset (name it)
       C = reject; require different members (name them)

R2-Q2  Rejections. Record STAGED_DECOMPOSITION (no observable stages exist),
       SELF_CRITIQUE/REFLECTION (private, or else verification),
       TOOL_AUGMENTED (evidence collection), EXTENDED_REASONING (capability
       tier / compute claim) as rejected and inadmissible without a new ruling.
       A = record the four rejections as stated [recommended]
       B = record them as deferred rather than rejected

R2-Q3  Field names. strategy_policy_ref on CognitiveRoleContract;
       strategy_policy_id and strategy_policy_version on ProposerAdvisory;
       declared_strategy on ProposerAdvisory, the SAME name the process record
       already uses.
       A = ratify as stated [recommended]
       B = as stated, but name the advisory field asserted_strategy

R2-Q4  Public names. ReasoningStrategy, StrategyPolicyResolver,
       StrategyPolicyRequest, StrategyPolicyResponse,
       verify_strategy_permission.
       A = ratify as stated [recommended]
       B = use StrategyPermissionProvider/Request/Response, matching the
           DomainEvaluationProvider precedent, accepting that "provider of
           permission" may read as granting

R2-Q5  Record field type — not settled by S2B-S1-Q3. Either option invalidates
       any stored S1-era record carrying free-text declared_strategy.
       A = type BOTH declared_strategy fields as the ReasoningStrategy enum
           [recommended]
       B = enum on the advisory, C5b Token on the process record

R2-Q6  Gate. With R2-Q1..Q5 ratified, §8's sixth item (the vocabulary) is
       satisfied in full and the implementation gate OPENS — subject to the
       standing fact that no strategy-permission policy family is registered
       with Policy Authority, which blocks execution regardless.
       A = the gate opens on this ratification [recommended]
       B = the gate stays closed pending the policy family's registration
```

---

## Part G — Independent-review prompt for a different model (paste as-is)

```
Independent review, read-only. Repository rasaha/symbolu. Modify nothing: no
branch, no commit, no push, no PR.

ARTIFACT. docs/architecture/S2B_ROUND2_VOCABULARY_AND_NAMING_PROPOSAL.md on
branch claude/s2b-reasoning-strategy-permission-zbc9rw. Verify the commit
hash, SHA-256 and line count you are given against the file before reviewing,
and report the result; if they differ, report ARTIFACT_IDENTITY_MISMATCH with
the computed values and stop. Verify everything against the tree at
90696d16ed8e9b9942252fe297c44bc3d16393a1, never against the proposal's own
assertions.

1. ADMISSION TEST. For each of the three proposed members, does it actually
   satisfy S2B-S1-Q1's three criteria? Attack criterion (i) hardest: can an
   auditor distinguish the member's execution from its non-execution using
   fields that exist today? Is any member in truth a property of the ARTIFACT
   being passed off as a PROCEDURE — and if so, does S2B-D2=A permit that?
2. EXCLUSIONS. Does any proposed member collapse into evidence collection,
   verification, abstention or escalation (OD-5, S1:1173-1189)? Are the four
   recorded rejections correctly reasoned, and is any of them in fact
   admissible on the criteria as ratified?
3. PRIVATE-REASONING CLAIMS. Does any member's wording assert something about
   producer-internal process? Test SINGLE_PASS specifically against S1:1245.
4. NAMES. Check every proposed name against: D7's Proposal/Recommendation bar;
   RESERVED_AUTHORITY_VOCABULARY; the C5b pattern at contracts.py:92; the 46
   names in public_api.json; and the repository's own enum, field and verify_*
   conventions. Does StrategyPolicyResolver vs StrategyPermissionProvider
   matter as the proposal claims, or is that over-read?
5. SCOPE. Does this round add any field, name, or commitment beyond what
   S2B-S1-Q2=A and S2B-S1-Q6=A already ratified? The claimed counts are
   11 / 30 / 29 / 18 / 12 / 11 and a public surface of 51 — re-derive them.
6. R2-Q5. Is the record field's retyping genuinely outside what S2B-S1-Q3=A
   settled, or is the proposal manufacturing a question? Is the disclosed
   migration cost complete?
7. GATE. Is it TRUE that ratifying this opens §8's gate? Check each of the six
   items against ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md, and say plainly
   if the proposal overstates its own consequence.
8. FALSE REPOSITORY CLAIMS. Mechanically check every file:line citation.
   Report each that does not resolve or supports a weaker claim than made.

Return: the identity-gate result; a blocker list with file:line and the ruling
violated; a non-blocking list; and one verdict — SOUND,
SOUND_WITH_CORRECTIONS, or UNSOUND. Propose no replacement design.
```

---

## Part H — What this document changed

One new documentation file. **No production source, test, specification, ADR, CHANGELOG,
`public_api.json`, `version.py`, package metadata, CI workflow or platform-freeze artifact
is modified.** It ratifies nothing and authorizes no implementation.
