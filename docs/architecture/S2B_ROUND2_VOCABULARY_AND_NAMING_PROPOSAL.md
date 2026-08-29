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
that no internal iteration or branching occurred" (`S1:1244-1246`). No member may therefore be
worded as a claim about private process, and each below is defined by its observable
trace.

### A.1 Proposed members — three

| Member (spelling proposed, not settled) | What it would denote | Evidencing basis |
|---|---|---|
| `SINGLE_CANDIDATE_UNREVISED` | the advisory carries exactly one candidate and binds no parent | `[V]` `candidates` is `1..n` and inside `P_unsigned` (`S1:1043`); `parent_advisory_digest` participates in identity **including when null** (`S1:1036`) |
| `MULTI_CANDIDATE_UNREVISED` | the advisory carries two or more candidates and binds no parent | `[V]` the same `candidates` field. `[I]` The definition is **two-axis only**: it says nothing about the selector, because under OD-8 selection-policy v1 "more than one qualifying candidate produces no selection and `ABSTAIN`" (`S1:2653-2654`), so a lawful multi-candidate advisory may carry a **null** selector. An earlier draft added "and its selector is the ratified one" as a third condition, which left exactly that advisory matching no member |
| `REVISED_ADVISORY` | the advisory binds a parent by digest, at any candidate count | `[V]` `build_advisory_revision` sets `parent_advisory_digest = parent.advisory_digest` and increments `advisory_version` (`S1:1836-1837`; B7 at `S1:377-386`) |

Three members, no default member, no escape member — satisfying `S2B-S1-Q1`'s shape rules
with one member to spare.

`[I]` **`REVISED_ADVISORY` against criterion (ii), stated because it is the member most
easily mistaken for a mechanism.** Producing a revision is neither of OD-5's contract
mechanisms and neither of its outcomes: it is not evidence collection (`ToolObservation`,
`observation_refs`, R-7), not verification (Equation 4 and the `verify_*` surface,
`S1:1178-1179`), and not abstention or escalation, which are `TerminalOutcome` members
constrained by R-2 and R-4 (`S1:1173-1189`). `[V]` It is a **producer-chosen construction
path** — `build_advisory_revision` is called or it is not, and G3 makes the resulting parent
binding and version increment observable (`S1:1836-1837`) — which is what `S2B-D2=A` means
by an orchestration procedure. The same argument holds for the other two, which differ only
in candidate count on the same path.

**ENTAILED** — that members must be evidenceable, exclusive of mechanisms and outcomes,
and provider-neutral (`S2B-S1-Q1=A`); that a member denotes an externally observable
orchestration procedure rather than an unobservable model disposition or a capability tier
(`S2B-D2=A`, `ADR:113-116`).

**CHOSEN** — these three members, their spellings, and the decision to define each by the
artifact evidence rather than by producer behaviour.

`[R]` **The spellings name artifact shape, not processing.** An earlier draft of this
proposal used `SINGLE_PASS`, `PARALLEL_CANDIDATE_COMPARISON` and `SUCCESSIVE_REVISION`.
Those were withdrawn: "pass" and "parallel" assert *processing* — a step count and a
concurrency — that no artifact evidences, which is precisely the wording A.0 forbids and
which `S1:1244-1246` says a conformant record cannot support. The definitions were always
safe; the tokens were not, and a wire value is the thing an auditor reads.

`[R]` **The three are disjoint and exhaustive over the two observable axes.** Candidate
count (one / two-or-more) and parent binding (absent / present) give four cells;
`REVISED_ADVISORY` takes both parent-present cells, and the other two split parent-absent.
**Every member is defined by those two axes and by nothing else** — the table above, this
paragraph and ballot `R2-Q1` state the same conditions in the same terms. A member carrying
any third condition would reopen the hole the withdrawn selector clause created: an advisory
lawful under a ratified policy, matching no member, with no declaration available to it.
`[I]` Disjointness is not cosmetic: `S2B-D3=A` ratifies **exactly one primary strategy per
invocation** (`ADR:123-125`), so an advisory satisfying two members at once would have no
lawful declaration and no ratified rule to break the tie. The earlier spellings had exactly
that defect — a revision carrying two candidates satisfied two of them.

`[R]` **The consequence, stated plainly, because it decides whether this vocabulary is
wanted at all.** Because every member is defined by observable artifact shape, a
declaration under this vocabulary is **derivable from the advisory itself**, and the
members partition the outputs of the **two** ratified advisory-construction paths this
package already has (`[V]` `build_proposer_advisory` at `identity.py:187` and
`build_advisory_revision` at `:425`): `build_advisory_revision` yields `REVISED_ADVISORY`,
and `build_proposer_advisory` yields the other two according to candidate count. The
mapping is two-to-three, not one-to-one. Two things follow.
A role permitted only `SINGLE_CANDIDATE_UNREVISED` is, in effect, barred from
`build_advisory_revision` and from multi-candidate advisories — permission becomes a
statement about which ratified construction paths a role may use. And the declaration adds
no information a verifier could not recompute, so its value is *governance* (a role may
only produce shapes its policy permits) rather than *disclosure*.

`[I]` This is not a defect of these three members; it is what criterion (i) permits **while
no component records observable reasoning stages** (`ADR:346-347`). A vocabulary of
genuinely non-derivable procedures needs that recorder first. The owner should decide
whether a derivable vocabulary is worth ratifying now or whether the concept waits — which
is why `R2-Q7` exists.

`[R]` **What each would not claim.** `SINGLE_CANDIDATE_UNREVISED` would **not** claim that
only one candidate was ever considered: a producer that generated five and carried one forward
yields an identical artifact, and `S1:1244-1246` states that the record cannot tell. It would
claim that the advisory carries one. The same shape of limit applies to the other two.

### A.2 Rejected candidates — recorded, because an implementer would reach for them

| Rejected | Why |
|---|---|
| `STAGED_DECOMPOSITION` | fails (i) **today**: `[G]` no field records stages or sub-questions, and R-3's forward-only chain cannot represent them (`S1:1231-1259`). Admissible later only if a producer of observable stages exists — the same gap that blocks `S2B-D8`'s conformance stage (`ADR:346-347`) |
| `SELF_CRITIQUE` / `REFLECTION` | fails (i) as private model behaviour, which `S2B-D2=A` bars as an "unobservable model disposition" (`ADR:113-116`). `[I]` This ground alone is sufficient. An earlier draft added that an observable self-critique "becomes verification"; that is withdrawn as loose — OD-5's *verification* is the contract mechanism, Equation 4 and the `verify_*` surface (`S1:1178-1179`), which a self-critique pass is not |
| `TOOL_AUGMENTED` / `EVIDENCE_GATHERING` | is **evidence collection**, an OD-5 exclusion by name (`S1:1173-1189`) |
| `EXTENDED_REASONING` / `HIGH_EFFORT` | `[R]` The load-bearing grounds are **`S2B-D2=A`'s capability-tier bar** (`ADR:115-116`) and **(i)**: no artifact evidences reasoning effort. An earlier draft filed this under (iii); that is corrected — as ratified, criterion (iii) is **provider-neutrality**, and a capability tier need name no provider. `[I]` It would also carry a compute claim, creating the binding to Reasoning Compute Governance that S2-B forbids (`ADR:256-257`; RCG-D5) |

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
| 5 | `verify_strategy_permission` | function — `[V]` the `verify_*` convention, **six** existing names in `public_api.json` |

**On `Resolver` rather than `Provider`.** `[V]` **The decisive evidence is that the owner
has already ratified the word.** `S2B-S1-Q6=A` names "the **resolver** protocol, the
**resolver** request shape, the **resolver** response shape"
(`ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md:105-107`), and `S2B-S1-Q9=A` ratifies
`resolve(*, request) -> response` (`:127-132`). A `Provider` spelling would fight ratified
language, so this is a narrower choice than an earlier draft of this proposal presented it
as. `[V]` The tight precedent is `DomainEvaluationProvider` (`contracts.py:780`), and
symmetry would argue for `StrategyPermissionProvider`. Recommended **against** on a second,
independent ground: a "permission provider" reads as
something that *grants* permission, and `S2B-D7=A` is emphatic that the declared strategy
is "bound as an assertion, never as an authorization" (`ADR:197-198`), with five identities
held distinct (`ADR:206-208`). `Resolver` names what the collaborator does — resolve a
policy — and cannot be misread as authorizing. `[R]` A genuine trade-off: precedent
symmetry against authority connotation.

### B.3 One question Round 1 did not reach

`[V]` `S2B-S1-Q3=A` narrowed `ProposerProcessRecord.declared_strategy` from C5c to C5b. It
did not settle whether the field would become the **closed enum** or a C5b `Token`
constrained separately. `[V]` C5b is *defined* as "a vocabulary term matched by equality
against an allowlist" (`S1:507-509`), so the enum is C5b's natural closed realization rather
than a narrower class — the open question is **representation**, not classification, which
is why `S2B-S1-Q3=A` did not reach it.

`[R]` **The two options do not cost the same, and an earlier draft of this proposal was
wrong to say they did.** `[V]` The field is `Annotated[str, StringConstraints(min_length=1)]`
today (`contracts.py:989`), and the C5b pattern admits any space-free token
(`contracts.py:92`): a stored value of `exploratory` or `draft-then-revise` **passes**
option B and **fails** option A, which admits only ratified members. So option A invalidates
strictly more stored records than option B.

`[I]` The real trade-off is therefore not migration cost but **where a non-member is
caught**. Under A the record refuses it at construction. Under B the record accepts it while
the advisory's field refuses it, so a mismatched pair is caught by rider R1's equality at
**replay** instead — later, and by a verifier returning `False` rather than by a validator
raising. `[I]` Option A is the fail-closed reading and is recommended on that ground, not on
a migration-cost ground.

`[R]` **A also retypes the advisory's field**, not only the record's: the advisory field is
new, so it takes whatever representation is ratified here. B.3's question is which
representation **both** fields take.

---

## Part C — Cardinality and surface: confirmed, not changed

This round would add **no** field and **no** public name beyond what `S2B-S1-Q2=A` and
`S2B-S1-Q6=A` already ratified. `CognitiveRoleContract` 11, `ProposerAdvisory` 30, private
unsigned payload 29, `ProposerProcessRecord` 18, `AdvisoryCandidateSet` 12,
`CandidateAdvisory` 11; public surface 51. It supplies the spellings for movements already
counted and ratified.

`[V]` `AdvisoryCandidateSet` 12 is stated by `S2B-S1-Q2=A`; `CandidateAdvisory` 11 is **not**
named in that ruling and is quoted here from the tree (`contracts.py:565`), where it is
unchanged and untouched by this round.

---

## Part D — Readiness verdict

## `S2B_R2_REQUIRES_OWNER_RATIFICATION`

No repository contradiction was found. If ratified, this round would close the last §8 gate
item — the vocabulary's members — and, with the names settled, **the gate would open**.

`[G]` **Execution would nonetheless remain blocked** until a strategy-permission policy
family is registered with Policy Authority (`ADR:343-344`), which is not this package's
work. Ballot `R2-Q6` uses the same words for the same fact.

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

R2-Q1  Members. Ratify exactly three, defined over two observable axes and
       nothing else — candidate count, and parent binding:
         SINGLE_CANDIDATE_UNREVISED = exactly one candidate, binds no parent
         MULTI_CANDIDATE_UNREVISED  = two or more candidates, binds no parent
         REVISED_ADVISORY           = binds a parent, at any candidate count
       No member carries a condition on the selector: under OD-8 v1 a lawful
       multi-candidate advisory may carry a null selector, and a third
       condition would leave it matching no member. Each is named for artifact
       shape, never for processing; together they are disjoint and exhaustive,
       so D3=A's one-strategy-per-invocation rule always has exactly one
       lawful answer.
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

R2-Q5  Representation of BOTH declared_strategy fields — not settled by
       S2B-S1-Q3, which fixed the class and not the realization. The options do
       NOT cost the same: a stored space-free value like `exploratory` passes B
       and fails A, so A invalidates strictly more stored records. The real
       difference is where a non-member is caught — A at construction, B only
       at replay via R1's equality.
       A = the ReasoningStrategy enum on both fields; fail-closed at
           construction [recommended]
       B = enum on the advisory, C5b Token on the process record; non-members
           stay constructible on the record and are caught at replay

R2-Q6  Gate. With R2-Q1..Q5 ratified, §8's sixth item (the vocabulary) is
       satisfied in full and the implementation gate OPENS — subject to the
       standing fact that no strategy-permission policy family is registered
       with Policy Authority, which blocks execution regardless.
       A = the gate opens on this ratification [recommended]
       B = the gate stays closed pending the policy family's registration.
       Note: Q6 presumes Q7 = A. If Q7 = B, no vocabulary is ratified, the
       sixth gate item stays open, and Q6 does not arise.

R2-Q7  Character of this vocabulary. Every proposed member is defined by
       observable artifact shape, so a declaration is DERIVABLE from the
       advisory and the members partition the outputs of two existing construction
       paths: a role's permitted set becomes a statement about which ratified
       paths it may use, and the declaration adds no information a verifier
       could not recompute. This is what criterion (i) permits while no
       component records observable reasoning stages (ADR:346-347).
       A = accept a derivable vocabulary now; its value is governance, not
           disclosure [recommended]
       B = defer the whole vocabulary until a producer of observable reasoning
           stages exists, leaving the S2-B gate closed indefinitely
```

---

## Part G — Independent-review prompt for a different model (paste as-is)

```
Independent review, read-only. Repository rasaha/symbolu. Modify nothing: no
branch, no commit, no push, no PR.

ARTIFACT. docs/architecture/S2B_ROUND2_VOCABULARY_AND_NAMING_PROPOSAL.md, in
repository rasaha/symbolu, on branch
claude/s2b-reasoning-strategy-permission-zbc9rw, at commit <COMMIT> —
SHA-256 <SHA256>, <LINES> lines.

Those three values are supplied WITH this prompt and are deliberately not
written into the file: no file can contain the hash of itself or of the commit
that carries it. Whoever hands you this prompt must fill them in; if any of the
three still reads as a placeholder, say so and stop rather than reviewing an
unpinned artifact.

Fetch that exact commit, compute all three yourself, and report the result
before reviewing anything. If any differs, report ARTIFACT_IDENTITY_MISMATCH
with the computed values and stop — do not review a different revision, and do
not review a working copy. Verify every claim against the repository tree at
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
   producer-internal process? The three tokens name artifact shape
   (SINGLE_CANDIDATE_UNREVISED, MULTI_CANDIDATE_UNREVISED, REVISED_ADVISORY);
   test each against S1:1244-1246, and check the disjointness claim against
   D3=A.
4. NAMES. Check every proposed name against: D7's Proposal/Recommendation bar;
   RESERVED_AUTHORITY_VOCABULARY; the C5b pattern at contracts.py:92; the 46
   names in public_api.json; and the repository's own enum, field and verify_*
   conventions. Does StrategyPolicyResolver vs StrategyPermissionProvider
   matter as the proposal claims, or is that over-read?
5. SCOPE. Does this round add any field, name, or commitment beyond what
   S2B-S1-Q2=A and S2B-S1-Q6=A already ratified? The claimed counts are
   11 / 30 / 29 / 18 / 12 / 11 and a public surface of 51 — re-derive them.
6. R2-Q5. A prior review found the earlier cost claim FALSE — it said both
   options invalidate any stored free-text declared_strategy, when a space-free
   value passes the C5b pattern and so survives option B. Verify the CORRECTED
   claim: that A invalidates strictly more than B, and that the real difference
   is where a non-member is caught (construction under A, replay via rider R1's
   equality under B). Is that now accurate and complete? Is the representation
   question genuinely outside what S2B-S1-Q3=A settled, or manufactured?
7. GATE. Is it TRUE that ratifying this opens §8's gate? Check each of the six
   items against ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md, and say plainly
   if the proposal overstates its own consequence.
8. R2-Q7 AND DERIVABILITY. The proposal concedes that every member is defined
   by artifact shape, so a declaration is derivable from the advisory and the
   members partition the outputs of two existing construction paths. Test that concession
   hard: is it true, is it complete, and does a derivable vocabulary still
   satisfy S2B-D2=A and do useful work under S2B-D1=A — or does it reduce
   "reasoning strategy permission" to permission over construction paths? Is
   R2-Q7=B (defer until observable stages exist) the better answer, and does the
   ballot present that choice fairly?
9. FALSE REPOSITORY CLAIMS. Mechanically check every file:line citation.
   Report each that does not resolve or supports a weaker claim than made.
   Note that this revision fixed two blockers and seven findings from a prior
   review; check the fixes did not introduce new inaccuracies, which is the
   failure mode that has recurred in this document's history.

Return: the identity-gate result; a blocker list with file:line and the ruling
violated; a non-blocking list; and one verdict — SOUND,
SOUND_WITH_CORRECTIONS, or UNSOUND. Propose no replacement design.
```

---

## Part H — What this document changed

One new documentation file. **No production source, test, specification, ADR, CHANGELOG,
`public_api.json`, `version.py`, package metadata, CI workflow or platform-freeze artifact
is modified.** It ratifies nothing and authorizes no implementation.
