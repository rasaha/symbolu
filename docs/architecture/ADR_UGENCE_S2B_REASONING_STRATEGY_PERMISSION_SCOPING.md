# ADR: Ugence S2-B — Reasoning Strategy Permission (architectural scoping)

**Status:** **Accepted (ratified architectural scoping) — documentation only.**
This ADR records owner rulings on the **scope, authority, binding semantics, failure
semantics and replay boundary** of Reasoning Strategy Permission. **No implementation is
authorized by this ADR, and none exists.**

**Date:** 2026-08-28.

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
default head `80dcdce48821c563bfe41ced45d915a16e0908c1` (merge of PR #1500, the S2-A
Agentic Proposer `0.2.0` release). `[V]` That head contains
`246ca5c3ee332296c22ccbda3a42abadf90c577f` with an empty tree diff between the two.

**Scope:** eight owner decisions `S2B-D1` – `S2B-D8`, one rider on `S2B-D6`, and the
riders and confirmations recorded under *Riders and confirmations* below.

**Non-scope:** this ADR introduces **no runtime code, no package, no contract, no field,
no vocabulary member, no enum member, no protocol, no validator, no normalization
profile, no exception type, no public API, no test, no CI change, no package version and
no platform-freeze change.** It changes **architecture documentation only**.

**Decision owner:** the repository owner, ruling 2026-08-28.

**Related, and unchanged by this ADR:**
- [`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`](ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md)
  — D1–D10, O-1 – O-4, OD-1 … OD-10, and declarations A11–A13. **No OD is added,
  renumbered or reopened by this ADR.**
- [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) — P-1 … P-11, the
  single platform-wide issuer/verifier of signed, versioned policy families.
- [`ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md`](ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md)
  — RCG-D1 … RCG-D10 and the ten standing principles.
- [`ROADMAP_UGENCE_REASONING_COMPUTE_GOVERNANCE.md`](ROADMAP_UGENCE_REASONING_COMPUTE_GOVERNANCE.md)
  — exploratory, ratifying nothing.
- [`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`](../../packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md)
  — the frozen Agentic Proposer contract specification.

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` an owner ruling; `[G]` an unresolved gap.

> *This ADR changes **no** production source, test, package metadata, CHANGELOG,
> `public_api.json`, `version.py`, CI workflow or platform-freeze artifact. The
> substantive freeze digest is unchanged before and after it:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 1. Authority, and relationship to what is already ratified

**To OD-5.** `[V]` OD-5, ratified 2026-08-26, distinguishes reasoning *functions* from
reasoning *strategies*, states the four-way distinction, and defers
`permitted_reasoning_strategies` **and its vocabulary together** to S2
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:638`;
`.../S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1122-1191`, `:2674-2690`). This ADR is
the S2 ruling OD-5 deferred to. It does **not** amend OD-5. Two OD-5 constraints carry
through unchanged:

* `[V]` the concept and the vocabulary that gives it content **arrive together**, so no
  field may be declared before its vocabulary is ratified alongside it;
* `[V]` **evidence collection, verification, abstention and escalation are not reasoning
  strategies** and do not enter the vocabulary
  (`.../S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1183-1189`).

**To S2-A.** `[V]` OD-7, OD-8, OD-9 and OD-10 are ratified **and implemented** at package
version `0.2.0` (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:640`). This ADR does not
change the meanings of `SATISFIED`, `NOT_SATISFIED` or `INCONCLUSIVE`, does not weaken
fail-closed selection uniqueness, introduces no candidate merit ranking, does not
activate the `candidate_id` tie-break, and gives the injected `DomainEvaluationProvider`
no reasoning-strategy authority.

**To A13.** `[V]` A13, declared 2026-08-28, ratifies the exact H1 builder signatures as
the `0.2.0` public callable surface (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:1085-1119`).
A13 stands unchanged. Its scope is settled under *Riders and confirmations* below.

**To RCG-0.** `[V]` RCG-0, ratified 2026-08-28, is documentation-only and unimplemented.
S2-B asks **which declared reasoning procedure is permitted**; RCG asks **how much
probabilistic computation is authorized and consumed**. `[R]` Permission to use a
strategy grants no compute; a compute envelope authorizes no strategy. **S2-B creates no
binding to Reasoning Compute Governance, and any future binding requires separate
ratification.**

**Numbering.** `[R]` This ADR assigns **no new OD number.** The rulings are recorded as
the dated owner declaration `S2B-D1` – `S2B-D8`, scoped to this ADR. OD-1 through OD-10
remain the Agentic Proposer decision record and are neither extended nor reopened.

---

## 2. The eight rulings

**Recorded exactly as ruled:** `D1=A D2=A D3=A D4=A D5=A D6=B1 rider R1 D7=A D8=B`.

### S2B-D1 — Issuing authority and permission bearer `[R]`

**Ruled: A.** Policy Authority issues a new registered **strategy-permission policy
family** — signed, versioned and revocable. `CognitiveRoleContract` bears **only a
reference** to an externally issued, resolvable policy; it does not carry the permitted
set as role data.

`[V]` Policy Authority is the only currently implemented mechanism in this repository
able to issue such a family: a family-neutral `PolicyCoordinate`
(`packages/policy-authority/src/ugence_policy_authority/core/adapters.py:63-95`), a
`PolicyFamilyAdapter` seam (`:166`), a fixed issuance order
(`.../core/issuance.py:1-25`), signed revocation and exact-match resolution. `[V]` P-9
makes a second family additive; `[V]` P-4 and P-5 keep authorship, approval, issuance,
resolution and runtime authorization as five distinct roles.

`[R]` **Excluded as issuers:** Agentic Proposer, Agent Runtime, Model Authority,
Decision Authority and Risk Authority. A capability's authority for one responsibility
does not transfer to another.

### S2B-D2 — Vocabulary abstraction and scope `[R]`

**Ruled: A.** A vocabulary member denotes an **externally observable orchestration
procedure** — defined by calls, stages and validations that an auditor could evidence —
not an unobservable model disposition and not a model capability tier.

`[R]` **No member, spelling, bound or default is ratified by this ruling.** Under OD-5
the concept and its vocabulary arrive together, so the vocabulary must be ratified
before any field carrying it is declared.

### S2B-D3 — Cardinality and ordering `[R]`

**Ruled: A.** **Exactly one primary strategy per invocation.** Permission is a set of
alternatives the role may select among. Composition — a primary plus subordinates, an
ordered stage sequence, or an unordered composable set — is **deferred to a separate
ruling** and is not authorized here.

`[I]` One strategy per invocation is what makes the declaration a scalar, and therefore
what makes `S2B-D6=B1` sufficient without a container-shape or ordering ruling.

### S2B-D4 — Permission level `[R]`

**Ruled: A.** Permission is **role-level only**; the invocation declares within it.
Mandate-level narrowing and per-invocation authorization are not ratified.

`[V]` This matches OD-5's own wording — a role's permitted reasoning strategies are "the
methods the role may select among".

### S2B-D5 — Structural permission result `[R]`

**Ruled: A.** When permission cannot be established, the result is **structural**:
**construction does not produce the identity-bearing artifact, and independent replay
returns `False`** — **without emitting an authority disposition.**

The triggering conditions are: no governing policy resolves; the policy's signature or
version cannot be verified; a required declaration is absent; the permitted set is empty;
the declared strategy is not a member of it; or replay cannot establish correspondence.

`[R]` **No authority disposition is emitted, and none is ratified.** The capability emits
no denial, and `ABSTAIN` is never a denial
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:240-247`); no reserved authority term may
be emitted (`:263-278`). **No exception name or error class is ratified.** Construction
is **not** described as silent — under this ruling it refuses, and the mechanism of
refusal is not ratified here.

`[R]` **Which component maps a structural permission failure to an operational outcome —
abstention, hold, escalation or referral — is deliberately outside this scope and is not
ruled.** Nothing in the ratified scope depends on that answer.

### S2B-D6 — Placement and binding shape `[R]`

**Ruled: B1 — proposal-bound, direct declaration value.** The **governing
strategy-policy identity and version**, and **one direct scalar declared-strategy
assertion**, are bound into the **proposal identity projection**.

`[R]` This delivers the **proposal-bound guarantee** and rejects the weak linked-record
guarantee, under which the proposal digest would not bind the declaration and a proposal
would remain digest-valid with its declaration absent, replaced or never produced.

`[R]` **No field name, container shape or builder parameter is ratified by this ruling.**

**Rejected alternatives, recorded.** A pre-advisory declaration-artifact digest (which
would add a contract, an identity rule, a construction ordering, a transport and an
unresolvable-artifact failure mode to carry one scalar assertion); binding the policy
identity while leaving the declaration unbound (which delivers only the weak guarantee);
and a fully separate authorization artifact (which differs in issuance, not in binding).

### S2B-D6 rider R1 — the existing process-record declaration `[R]`

**Ruled: R1.** `ProposerProcessRecord.declared_strategy` is **retained**, **derived from
the proposal-bound declaration at construction**, and subject to **exact equality during
replay**.

`[V]` The field exists today as a caller-supplied string
(`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/contracts.py:989`),
and the record's builder receives it, together with `advisory_digest` as a bare
caller-supplied reference, rather than receiving the advisory
(`.../builders.py:194-231`). `[I]` Derivation prevents divergence at construction; the
replay check re-establishes it across two independently transported artifacts, on the
repository's standing rule that construction is defence-in-depth and **independent replay
is the guarantee**.

### S2B-D7 — Provenance discipline `[R]`

**Ruled: A.** The **policy identity and version are package-stamped from an
independently resolved policy**; no builder accepts them as caller-supplied parameters.
The **declared strategy is supplied by the producer and bound as an assertion, never as
an authorization.**

`[V]` This follows OD-7 part 5's selector-policy precedent, under which the selector
policy is deliberately not a builder parameter because "accepting it from a caller would
let a caller label a selection with a policy that did not make it". `[R]` A
caller-supplied value is not authoritative merely because it is structured or
digest-bound.

`[R]` Five identities remain distinct: the issuing policy; the strategy vocabulary or
profile version; the declared strategy; observable-execution evidence; and the resulting
proposal.

### S2B-D8 — Replay boundary `[R]`

**Ruled: B — proposal-bound replay.** Its inputs are the `ProposerAdvisory`, the
resolved and signature-verified policy version, the `CognitiveRoleContract`, and the
`ProposerProcessRecord` for the rider R1 equality check.

`[R]` **Observable-procedure conformance replay is a named later stage and is not in this
scope.** `[G]` It is blocked today: no component records observable reasoning stages.

---

## 3. Riders and confirmations

`[R]` **D1 rider.** A reference to an externally issued Policy Authority
strategy-permission policy **is not a constitution-derived attribute**. The role contract
may therefore bear that reference within D8's existing containment bounds
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:392-420`).

`[R]` **No ruling in this ADR ratifies a vocabulary member, field name, container shape,
builder parameter, default, ordering encoding, exception name or terminal disposition.**

`[R]` **D6=B1 binds** the governing policy identity and version, and one direct scalar
declared-strategy assertion, into the proposal identity projection.

`[R]` **R1 retains** `ProposerProcessRecord.declared_strategy`, **derives** it from the
proposal-bound declaration at construction, and **requires exact equality during replay.**

`[R]` **B1 implies later-version changes** to `build_proposer_advisory` and
`build_advisory_revision`.

`[R]` **R1 independently implies a later-version change** to
`build_proposer_process_record`.

`[R]` **A13's "all four builders" does not cover `build_proposer_process_record`.**
`[V]` A13's text enumerates four (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:1091`)
while H1 defines five build functions
(`.../S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1922`, `:1943`, `:1956`, `:1979`,
`:2000`), and the four carrying provider and profile parameters exclude the
process-record builder. `[I]` R1's change therefore sits **outside** A13's enumeration
rather than superseding it; A13 stands intact for its four. The builder remains one of
the forty-six authorized public names, so a later-version public-surface ratification is
required for R1 regardless.

`[R]` **These later-version signature and public-surface changes are properly raised but
are not granted by this ruling.**

`[R]` **S2-B creates no binding to Reasoning Compute Governance**; any future binding
requires separate ratification.

`[R]` **The stale C7/C9 statements** in the RCG-0 ADR header and the RCG roadmap remain a
**separate documentation-maintenance task outside this change**, and are not corrected
here.

---

## 4. Eight concepts held apart

`[R]` These are routinely collapsed, and each is a different kind of statement made by a
different party. The ratified scope depends on keeping them distinct.

| Concept | What it is |
|---|---|
| **Permitted strategy** | what an authoritative policy allows a role to use |
| **Required strategy** | whether policy may compel a procedure for a class of work — not ruled here |
| **Declared strategy** | what the proposal-producing process asserts it used |
| **Executed observable procedure** | the external calls, stages, tools and validations that can be evidenced |
| **Private model reasoning** | internal model computation Ugence cannot inspect or prove |
| **Strategy request** | what an agent or model asks permission to use |
| **Strategy authorization** | the permission independently issued by governance |
| **Conformance evidence** | what deterministic replay or audit can establish from observable records |

`[R]` A model, agent, caller or proposer may **request or declare**; **none may
authorize.**

---

## 5. Proposal identity and replay guarantees

Under `S2B-D6=B1` with rider `R1`, `S2B-D7=A` and `S2B-D8=B`:

**Independent replay could establish** — once the separately ratified design exists —
that the proposal, at its digest, was constructed under a declaration that was a member
of the permitted set of the policy version **the proposal itself binds**; that neither
the declaration nor the policy reference changed after signing; and that the process
record's declaration corresponds exactly. This is subject to independently verifying the
policy's issuer and signature through Policy Authority resolution, which is a separate
call the digest does not supply.

`[R]` **Digest membership proves integrity after construction, never provenance.**
Inclusion in the identity projection establishes that a value was not altered afterwards;
it does not establish that the proper authority issued it. That is why `S2B-D7=A`
requires package-stamping from an independently resolved policy.

`[R]` **Equality between the two declaration fields proves correspondence between two
observable fields — that the record and the proposal name the same declared strategy. It
does not prove conformance with private reasoning, and it does not prove that the
declared procedure was executed.**

**Replay can never establish:** hidden model state; private chain-of-thought;
undocumented provider-side routing or fallback; whether a model internally used a
technique a provider names; external facts not carried across the replay boundary; or
whether omitted stages, evidence or candidates never existed.

---

## 6. Non-claims

Reasoning Strategy Permission, as scoped here, does **not** claim, and must never be
described as claiming, that:

- a model's private reasoning becomes deterministic;
- a declared strategy proves the model internally followed it;
- Ugence can inspect, reconstruct, preserve or replay private chain-of-thought;
- a provider's description establishes the strategy used;
- a caller-supplied identifier becomes authoritative through structure or digest binding;
- permission to use a strategy authorizes additional compute, tools, evidence access or
  consequential execution;
- a reasoning strategy is a model capability tier;
- a permitted strategy is appropriate for every invocation;
- a more elaborate strategy yields a better or more authoritative proposal.

It claims nothing about candidate completeness. It does **not** authorize consequential
execution, which remains with Risk Authority, ActionGate and Decision Authority. It
duplicates no part of RCG.

---

## 7. Residual gaps and required future ratifications

`[G]` **The Agent Constitution does not exist**
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:106-130`). The authority ratified here is
one that can operate today, not that document's successor.

`[G]` **No second Policy Authority family is registered.** `S2B-D1=A` is design-ready and
implementation-blocked until one is.

`[G]` **No component records observable reasoning stages**, so `S2B-D8`'s conformance
stage has no producer.

`[G]` **No component issues an invocation-level authorization of any kind.**

`[G]` **No strategy vocabulary exists**, and none may be inferred from illustrative
roadmap prose.

`[G]` **The operational-disposition owner for a structural permission failure is
unresolved**, and is outside this scope by construction.

**Required future ratifications, each separately reviewed:** the strategy vocabulary's
members, declared together with the concept per OD-5; the concrete contract shape and its
C5 classification and canonicalization treatment; the normalization profile a membership
test requires; the changed builder signatures and the public-surface delta from the
forty-six authorized names; the package version; any exception type; the injected
policy-resolver protocol `S2B-D7=A` implies; and the replay function or extension that
discharges `S2B-D8=B`.

---

## 8. Implementation gate

`[R]` **No S2-B code may begin.** No S2-B implementation may start until **all** of the
following are separately ratified: the strategy **vocabulary**; the **normalization**
profile; the concrete **contract shape**; the **builder signatures**; the **public
surface**; and the **later package version**.

`[I]` This mirrors the repository's own A11/A12 pattern, in which "unblocked on
ratification grounds" is explicitly not "authorized to implement". Ratification of scope
is not authorization to write production code, and this ADR does not claim it is.

---

## 9. Independent-review evidence

`[I]` The scoping analysis these rulings answer was produced as a working deliberative
artifact and was **independently reviewed read-only against this repository at baseline
`80dcdce48821c563bfe41ced45d915a16e0908c1`**, under an artifact-identity check binding
the review to exact content. The review reported **no blockers** and returned the verdict
**SOUND**.

`[I]` That artifact is **deliberative evidence, not a repository source**. It is
deliberately not committed, is not a normative document, and is not cited as authority
anywhere in this ADR. **This ADR is the canonical repository record of the S2-B rulings.**
Where the two ever differ, this ADR governs. Every `[V]` claim above is verifiable
directly against the repository at the cited `file:line`, independently of that artifact.

---

## 10. What this ADR changed

One new documentation file. **No production source, test, specification, readiness ADR,
RCG document, CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow
or platform-freeze artifact is modified.** The substantive freeze digest is unchanged.
