# ADR: Ugence Agent Constitution & Conformance — architectural scoping

**Status:** **Accepted (ratified architectural scoping) — documentation only.**
This ADR records the owner ruling on the five-item Agent Constitution & Conformance
scoping ballot (revision 2). **No implementation is authorized by this ADR, and none
exists.** No field name, package name, vocabulary member or version is ratified by it.

**Date:** 2026-08-30.

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
head `d5ffa8ebfca459fc3d98af55afe4ec889404171c` (merge of PR #1517). `[V]` That history
contains `48d4cfc978d55a50a812e4f4881a3f583d3064d6` (merge of PR #1515); PR #1515 and
PR #1517 together completed the S2-B stale-sites cleanup, so this baseline is **not
provisional**. The working tree was verified clean before this file was added.

**Scope:** five owner decisions `OD-C1` – `OD-C5`, ruled together as one ballot.

**Non-scope:** this ADR introduces **no runtime code, no contract, no field, no
vocabulary member, no public API, no package, no version, no test, no CI change and no
platform-freeze change.** It changes architecture documentation only.

**Decision owner:** the repository owner, ruling 2026-08-30.

**Related, and unchanged by this ADR:**
- [`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`](ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md)
  — OD-1 … OD-10 and declarations A11–A13.
- [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) — P-1 … P-11.
- [`ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md`](ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md)
  — RCG-D1 … RCG-D10.
- [`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md`](ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md)
  — S2B-D1 … S2B-D8 with rider R1.
- [`ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md`](ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md)
  — S2B-S1-Q1 … S2B-S1-Q13.
- [`ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md`](ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md)
  — S2B-R2-Q1 … S2B-R2-Q8.
- [`ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md`](ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md)
  — S2B-PF-BASE, S2B-PF-A … S2B-PF-H, S2B-PF-IMPL, and the §9 maintenance rulings.

**Evidence labels.** `[V]` verified against the cited evidence — this repository at
`file:line`, a commit, or a PR record, with the basis named where it is not `file:line`;
`[I]` architectural inference; `[R]` an owner ruling; `[G]` an unresolved gap.

> *This ADR changes **no** production source, test, package metadata, CHANGELOG,
> `public_api.json`, `version.py`, CI workflow or platform-freeze artifact. `[V]` The
> substantive freeze digest was recomputed in this session and is unchanged, all checks
> PASS:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 1. The ruling, transcribed verbatim

The repository owner ruled the five-item scoping ballot in conversation on 2026-08-30.
This ADR is the canonical repository record of that ruling, on the S2-B scoping ADR
precedent: **where the conversation and this ADR differ, this ADR governs.**

> Owner ruling — Agent Constitution & Conformance scoping ballot (revision 2),
> ruled personally by the repository owner.
>
> Baseline acknowledged as provisional: head 48d4cfc9; the S2-B stale-sites
> follow-up (two README sites, two S1 specification sites, the distribution-
> verifier comment, the family ratification ADR §6 record) has not merged.
>
> Recorded exactly as ruled: OD-C1=B OD-C2=A OD-C3=B OD-C4=A OD-C5=A
>
> OD-C1=B is ruled acknowledging its disclosed cost: the MVP includes an Agentic
> Proposer contract-amendment ratification round before first release, so the
> first released constitution is digest-bound to the proposals it governs.
> OD-C3=B leaves the structural-failure operational-disposition owner unassigned;
> a later ruling may assign it to an explicit component. OD-C4=A grants no
> suspension, revocation or offboarding authority; any such authority requires
> its own design and ratification. No field name, package name, vocabulary
> member or version is ratified by this declaration, and no implementation is
> authorized by it.

**Historical note on the provisional-baseline clause.** `[V]` The clause is historical:
the S2-B stale-sites follow-up it names has since merged as PR #1517
(`ADDITIONAL_STALE_SITES=EXACT_FIVE`, `RECORD_MAINTENANCE_RULINGS=YES`). `[V]` PR #1517
also superseded the duplicate PR #1520 — evidenced by the GitHub PR record, not by git
history: #1520 covers the same five stale sites and was closed unmerged on 2026-08-30,
with #1517 carrying the work. The maintenance rulings are recorded at
`ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md:356`, and the follow-up's
merge commit `d5ffa8eb` is this ADR's baseline head. The rulings themselves carry
forward unchanged; nothing in the follow-up touched the ballot's subject matter.

---

## 2. The five decisions

Each ruling below states the text of the option the owner selected, so the answer is
legible without the ballot. The texts of the options not selected are not reproduced
here; the ballot itself was a conversational artifact and this ADR does not
reconstruct it.

### OD-C1 — Proposal digest binding `[R]`

**Ruled: B — digest binding is MVP-mandatory.** The MVP includes an Agentic Proposer
contract-amendment ratification round before first release, so the first released
constitution is digest-bound to the proposals it governs.

`[R]` The disclosed cost is accepted as ruled: a contract-amendment ratification round
is on the MVP's critical path. `[R]` No amendment content, field, contract shape or
binding mechanism is ratified here — the round itself must ratify them. `[I]` The
precedent for proposal-bound binding over a weak linked-record guarantee is
`S2B-D6=B1`, under which an unbound declaration would leave a proposal digest-valid
with the declaration absent, replaced or never produced
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:160-176`).

### OD-C2 — Issuance ownership `[R]`

**Ruled: A — a new Policy Authority policy family.** Policy Authority lifecycle gaps
(structured supersession, suspension) are raised as Policy Authority milestones.

`[V]` Policy Authority is the only implemented mechanism in this repository able to
issue such a family: P-9 makes an additional family additive over a shared core with
per-family adapters (`ADR_UGENCE_POLICY_AUTHORITY.md:125-127`), and the pattern is
exercised — the strategy-permission family's adapter exists and registers through the
same seam
(`packages/integration/agentic-proposer-strategy-permission-policy/src/ugence_agentic_proposer_strategy_permission_policy/adapter.py:87-122`).
`[V]` The lifecycle gaps are real: P-7 defers structured successor references
(`ADR_UGENCE_POLICY_AUTHORITY.md:117`), P-6 rejects unstructured supersession at
issuance (`:112`), and a source search of
`packages/policy-authority/src/ugence_policy_authority/` finds no suspension mechanism
of any kind. `[R]` Those gaps are raised as Policy Authority milestones by this ruling;
they are **not** closed, scheduled or designed by it.

### OD-C3 — Structural-failure operational disposition `[R]`

**Ruled: B — the owner remains unassigned.** Conformance verifiers stay
disposition-free and emit no authority term. A later ruling may assign the
structural-failure operational-disposition owner to an explicit component.

`[V]` This continues `S2B-D5=A`, under which a structural permission failure produces
no identity-bearing artifact and replay returns `False` without any authority
disposition, and the component that maps such a failure to abstention, hold,
escalation or referral is deliberately unruled
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:139-158`). `[V]` The
reserved-vocabulary rule the verifiers must continue to satisfy is held in code and
asserted by equality (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:263-278`), and
`ABSTAIN` is never a denial (`:240-247`).

### OD-C4 — Agent lifecycle `[R]`

**Ruled: A — a later lifecycle layer of this product is the intended home for the
first writer of `AgentLifecycleState`; no authority is granted.** As ruled: no
suspension, revocation or offboarding authority is granted, and any such authority
requires its own design and ratification.

`[V]` `AgentLifecycleState` exists today as a closed four-member enum
(`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/vocabulary.py:193`)
whose value the S1 contract receives from an external identity issuer as an input
fact
(`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:856`);
under D1's bounds the proposer never computes activation state and never mints,
activates, suspends or ratifies a role
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:129-132`). `[G]` **No component in this
repository writes that state.** `[R]` "Intended home" is a statement of architectural
direction only: it authorizes no layer, no writer and no transition semantics.

### OD-C5 — Naming `[R]`

**Ruled: A — the product label is "Agent Constitution".** The canonical technical
artifact takes a narrower name settled at ratification, concept and vocabulary
arriving together per OD-5.

`[V]` OD-5 is the arrive-together rule: a concept and the vocabulary that gives it
content are declared once, together, in ratified form
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:638`). `[V]` The document the label
names does not exist:
`UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_INITIAL_DESIGN_SPEC_v0.1` is recorded as
absent, and D1's `CognitiveRoleContract` is a proposer-local projection that confers
no conformance with any constitution
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:106-130`). `[R]` No artifact name is
ratified here.

---

## 3. Standing boundaries, none extended or reopened

`[R]` This ballot rules on scope only. Every standing decision record below is left
exactly as ratified — none is extended, narrowed, renumbered or reopened, and no new
`OD`, `S2B-D`, `S2B-S1`, `S2B-R2`, `S2B-PF`, `P` or `RCG-D` number is assigned:

- `S2B-D1` – `S2B-D8` with rider R1
  (`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:90`);
- `S2B-S1-Q1` – `S2B-S1-Q13` (`ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md:28-35`);
- `S2B-R2-Q1` – `S2B-R2-Q8` (`ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md:27-32`);
- `S2B-PF-BASE`, `S2B-PF-A` – `S2B-PF-H`, `S2B-PF-IMPL`
  (`ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md:50-60`);
- `OD-1` – `OD-10` and `A11` – `A13`
  (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:30`, `:1085`);
- `P-1` – `P-11` (`ADR_UGENCE_POLICY_AUTHORITY.md:86-133`);
- `RCG-D1` – `RCG-D10`
  (`ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md:15`, `:136`).

Two standing principles carry through unchanged and constrain everything scoped here:

- `[V]` **strategy permission grants no compute, tools, evidence access or
  consequential execution**
  (`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:325-326`);
- `[V]` **digest membership proves integrity after construction, never provenance**
  (`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:298-301`). OD-C1=B binds
  the constitution and its proposals to one another; it does not make either
  self-authenticating.

---

## 4. Deliberately off the ballot

`[R]` Two matters were kept off this ballot on purpose, and their recorded treatment
is as follows:

- **Packaging.** Packaging is entailed by the `S2B-PF-A` convention — a governance
  concern ships as its own integration distributions rather than inside the
  capability package
  (`ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md:143-150`). `[I]` The
  constitution family is expected to follow that convention. `[R]` The entailment is
  **restated open to objection**: the design specification may object with reasons,
  and no distribution name is settled here.

- **The Policy Authority family-collision guard, and any one-active-constitution-
  per-role rule.** Both are **design-surface guard obligations for the design
  specification's own register** — the specification must carry them as register
  items, on the `S2B-PF-A` – `S2B-PF-H` pattern, rather than this ADR ruling them.
  `[V]` The existing collision surface is the adapter registry's duplicate-id
  refusal
  (`packages/policy-authority/src/ugence_policy_authority/core/adapters.py:217-220`);
  whether the constitution family needs a stronger guard, and whether at most one
  constitution may be active per role, are for that register.

---

## 5. Remaining gaps

`[G]` **No agent-lifecycle writer exists.** `AgentLifecycleState` is consumed as an
input fact; nothing in this repository produces or transitions it (§2, OD-C4).

`[G]` **No reasoning-stage producer exists.** No component records observable
reasoning stages, so observable-procedure conformance replay still has no input
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:346-348`).

`[G]` **No invocation-level authorization exists.** No component issues one, of any
kind (`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:349`).

`[G]` **Policy Authority has no structured supersession and no suspension.** P-7
defers the first (`ADR_UGENCE_POLICY_AUTHORITY.md:117`); the second has no mechanism
in source. OD-C2=A raises both as Policy Authority milestones without closing either.

`[G]` **Reference-map population is ungoverned.** `S2B-PF-D=A` resolves policy
references through an injected, immutable, defensively copied mapping
(`ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md:169-171`), and whether a
deployment's trust anchors, approval verifier and reference mapping are the right
ones is recorded as unprovable by the design that ships it
(`S2B_STRATEGY_PERMISSION_POLICY_FAMILY_AND_RESOLVER_DESIGN.md:594`). No authority
governs who populates that mapping, for this family or the constitution's.

---

## 6. Implementation gate, and what follows

`[R]` **No Agent Constitution code may begin.** Nothing here authorizes a contract, a
family adapter, a writer, a verifier or an amendment. `[I]` This is the repository's
standing A11/A12 discipline: ratification of scope is not authorization to implement,
and "unblocked on ratification grounds" is not "authorized to implement".

**Next step after this ADR merges:** the first-slice design specification, with its
own ballot — including the §4 register items — and its own ratification ADR. It is
deliberately not drafted alongside this record.

---

## 7. What this ADR changed

One new documentation file. **No production source, test, specification, readiness
ADR, RCG document, CHANGELOG, `public_api.json`, `version.py`, package metadata, CI
workflow or platform-freeze artifact is modified.** The substantive freeze digest is
unchanged (header, `[V]` recomputed this session).
