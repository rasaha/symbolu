# S2-B First-Slice Design Specification — Reasoning Strategy Permission

> **PROPOSAL ONLY. THIS DOCUMENT RATIFIES NOTHING, AND NO IMPLEMENTATION IS AUTHORIZED
> BY IT.**
>
> It is a design proposal prepared for owner ratification and independent review. Every
> item in it is **ungranted** until the repository owner rules on it. It is **not** an
> ADR, it is **not** an owner declaration, and it must never be cited as authority.
> Where this document and
> [`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md`](ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md)
> differ, **the ADR governs**.
>
> The S2-B ADR's §8 implementation gate stands unchanged: **no S2-B code may begin**
> until the strategy vocabulary, the normalization profile, the concrete contract shape,
> the builder signatures, the public surface and the later package version are **all**
> separately ratified. Nothing below satisfies any part of that gate.
>
> **Produced as a read-only design task.** It changes no production source, test,
> specification, ADR, `public_api.json`, `version.py`, package metadata, CI workflow or
> platform-freeze artifact. It adds one documentation file and nothing else.

**Date:** 2026-08-29.
**Baseline inspected:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
head `90696d16ed8e9b9942252fe297c44bc3d16393a1` (merge of PR #1501).

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` requires ratification; `[G]` an unresolved gap.

**Tense discipline.** Proposed behaviour is never described in the present tense.
Implemented behaviour, ratified design and proposal are distinguished throughout.

---

## 1. Precondition result

**Inspected SHA: `90696d16ed8e9b9942252fe297c44bc3d16393a1`** — matches the expected head
exactly. This is the merge of PR #1501;
`origin/claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` resolves to it.

| Check | Result |
|---|---|
| Head contains `80dcdce48821c563bfe41ced45d915a16e0908c1` | `[V]` ancestor confirmed (`git merge-base --is-ancestor`) |
| Head contains `246ca5c3ee332296c22ccbda3a42abadf90c577f` | `[V]` ancestor confirmed |
| S2-B ADR present, 400 lines | `[V]` `docs/architecture/ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md`, exactly 400 lines |
| Agentic Proposer `0.2.0` | `[V]` `packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/version.py:20` |
| Exactly 46 authorized public names | `[V]` `packages/capabilities/agentic-proposer/public_api.json` holds 46 symbols |
| `__all__` equals `public_api.json` | `[V]` AST-extracted `__all__` (46 names) equals the snapshot key set exactly |
| No later default-branch change reopens or contradicts the S2-B rulings | `[V]` the inspected head **is** the S2-B merge; no commit sits after it |

`[G]` **One incidental staleness found, reported and not repaired.**
`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1719,1726,1846,2379,2603,2615`
still narrate the `ProposerAdvisory` pass-through as "twenty-two"/"twenty-three", while
the contract carries 27 fields and the construction call at `identity.py:392-421` carries
27 keywords. The **rule** is unaffected — I7.16 states the obligation over
`set(ProposerAdvisory.model_fields)` rather than over a written count (`:2615`) — so no
guard is wrong. It belongs with the stale C7/C9 statements the S2-B ADR already parks as
separate documentation maintenance (ADR:259-261). It is **not** a contradiction blocking
this work, but any slice adding advisory fields makes it staler.

---

## 2. The eight proposals

Throughout: **ENTAILED** = follows from an already-ratified decision; **CHOSEN** = a
decision the owner must make and could make differently. Nothing below is ratified;
nothing below is implemented.

### Proposal 1 — The strategy vocabulary, and the OD-5(iii) joint arrival

**Proposal.** A **closed** vocabulary of C5b canonical symbolic tokens, declared in this
package, arriving in **one change set** together with every field that carries it. `[R]`
No member is proposed by name here, and no member should be ratified from prose. Instead,
three **admission criteria** would be ratified, and members admitted only by them:

1. **Evidenceable** — the member denotes an externally observable orchestration procedure
   whose execution an auditor could distinguish from its non-execution using calls, stages
   and validations (S2B-D2=A, ADR:113-115).
2. **Not already a mechanism or an outcome** — excludes evidence collection, verification,
   abstention and escalation (OD-5,
   `packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1183-1189`).
3. **Provider-neutral** — not a model capability tier (ADR:115-116), and never a provider
   or commercial model name (RCG-D5,
   `ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md:228-230`).

Plus three shape rules: **at least two members** (a one-member vocabulary would make a
declaration carry no information); **no escape member** (`OTHER`, `UNSPECIFIED`, `NONE`);
**no default member**.

**ENTAILED** — closedness (a C5b value is "matched by equality against an allowlist",
`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:506-508`); the three exclusions (OD-5); provider
neutrality (RCG-D5); joint arrival with the field (OD-5(iii),
`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:638`; ADR:58-59).

**CHOSEN** — the criteria triple as a ratifiable admission test; the two-member floor; the
bar on an escape member; enum-versus-`frozenset[Token]` representation.

**Alternatives considered and rejected.**
*(a) Ratify an illustrative member list now* — ADR:351 records `[G]` that no vocabulary
exists and "none may be inferred from illustrative roadmap prose"; a list drawn from this
design would be exactly that.
*(b) An open vocabulary constrained by a pattern only* — would defeat the membership test
S2B-D5=A's trigger conditions require (ADR:147) and would let a producer mint a
"permitted" strategy.
*(c) Reserve the field now as a C5d empty-only list and populate it later* — already
considered and **rejected by the owner** under OD-5
(`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2661-2668`).

**What it does not authorize.** Any member. Any spelling. Any *required* strategy (S2B-D3
and ADR §4 leave "required" unruled). Any composition of strategies (S2B-D3=A,
ADR:123-127). Any binding to Reasoning Compute Governance.

**Guard or test obligation.** An equality-pinned vocabulary test on the OD-6(iii)
precedent, plus the I5 registry (`packages/capabilities/agentic-proposer/tests/s1_specification_mirror.py`)
gaining the new fields so that an unregistered field fails loudly
(`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2459-2464`).
**Enforcement stops** at spelling and closure: no test could establish that a member
denotes a procedure anyone actually performed — `[G]` no component records observable
reasoning stages (ADR:346-347).

---

### Proposal 2 — Contract fields and their C5 treatment

**Proposal.** Four field movements, no more.

| Bearer | Field (name unsettled) | Class | Nullable | Identity | Source |
|---|---|---|---|---|---|
| `CognitiveRoleContract` | strategy-permission **policy reference** | C5a | no | no | external role owner |
| `ProposerAdvisory` | governing strategy-policy **identity** | C5b | **no** | **yes** | package-stamped |
| `ProposerAdvisory` | governing strategy-policy **version** | C5b | **no** | **yes** | package-stamped |
| `ProposerAdvisory` | **declared-strategy assertion** (one direct scalar) | C5b | **no** | **yes** | producer-supplied, bound as an assertion |
| `_UnsignedAdvisoryPayload` (private) | the same three | identical types, defaults, validators, serializers | — | — | G2 step 1 (`:1676-1680`) |
| `ProposerProcessRecord` | `declared_strategy` **retained**, field count unchanged | see below | no | no | **derived** (rider R1) |

The role-contract field would be a **reference only** — S2B-D1=A forbids carrying the
permitted set as role data (ADR:94-97), and the D1 rider records that such a reference is
not a constitution-derived attribute, so it sits inside D8's containment bounds
(ADR:223-226; `ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:392-420`).

**Non-nullability is ENTAILED, and is the sharpest structural consequence of S2B-D5=A.**
Unlike the four selection-coupled advisory fields
(`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1046-1051`), these three would have no null
branch: when permission cannot be established, no advisory is produced at all
(ADR:141-143). There is therefore no presence-coupling rule to write — the coupling would
be degenerate — and correspondingly no incidental omission-catching of the kind R-1a
supplies at `:1739-1742`. **Consequence for I7.16:** all three would be required without a
default, so an omission from the G2 pass-through would raise rather than construct
silently; they would land outside the "silent five".

**On the record's `declared_strategy` class.** `[V]` It is C5c today
(`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/contracts.py:989`;
`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1102`), under OD-1. `[V]` **OD-1's own text
pre-authorizes narrowing it to C5b while it stays outside `P_unsigned`** — "a narrowing
needing no new ratification" (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:638`, OD-1
row). **Recommended: take that narrowing**, so both operands of rider R1's equality carry
the same class. `[R]` OD-1's rider bars making *that* field identity-participating by
reclassifying it in passing — the advisory field proposed here would be a **new** field,
not that one moved, so the rider is not engaged; the owner should say so explicitly rather
than leaving it inferred.

**ENTAILED** — placement in the identity projection and the scalar shape (S2B-D6=B1,
ADR:162-165; S2B-D3=A is what makes the declaration a scalar, ADR:128-130);
package-stamping of the pair (S2B-D7=A, ADR:195-198); C5b for the pair, on the exact
precedent that `selection_policy_id`/`selection_policy_version` and the domain-evaluation
profile pair are C5b because they are matched by equality
(`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:517-527`); C3 compliance, every value being a
string including the version (`:449-456`); C6 unchanged, three ASCII scalars adding no set
path, no NFC path and no order significance (`:597-622`).

**CHOSEN** — C5b for the declared-strategy assertion (it would be the operand of a
membership test, which is C5b's defining criterion, `:509-516`); C5a rather than C5b for
the role-contract reference (it would be carried and compared whole, not split); taking
OD-1's pre-authorized narrowing.

**Alternatives considered and rejected.**
*(a) Carry the permitted set on the role contract* — refused by S2B-D1=A.
*(b) Bind the policy identity while leaving the declaration unbound* — the weak
linked-record guarantee S2B-D6=B1 explicitly rejects (ADR:166-168).
*(c) A nested "strategy declaration" sub-model* — adds a shape and a nesting path to carry
three scalars, and would place a new model inside `P_unsigned`'s reachable set, which the
I7.11 rival-identity walk pins deliberately (`:2545-2570`).
*(d) A pre-advisory declaration artifact with its own digest* — recorded as rejected in
the ADR itself (ADR:172-176).

**What it does not authorize.** Any field name. Any mirroring onto `AdvisoryCandidateSet`
(S2B-D6=B1 names the proposal identity projection alone). Any change to `nfc_paths` or
`set_paths`. Any numeric value at any depth.

**Guard or test obligation.** The frozen-profile corpus extended (I7.1); I5 registry
entries and the `CONTRACT_CARDINALITY` pins updated in the same change set (`:2455-2495`,
`:3781-3787`); an identity test asserting the three fields appear in `P_unsigned` and that
mutating any one changes the digest.
**Enforcement stops** at integrity: digest membership proves the values were not altered
after construction, never that the proper authority issued them (ADR:298-301).

---

### Proposal 3 — The normalization profile a C5b membership test requires

**Proposal.** **No normalization function, and no profile change.** The membership test
would be exact codepoint equality (`==` on `str`) between two values each already
constrained by the C5b pattern; `set_paths` and `nfc_paths` would both stay
`frozenset()`. Ratified explicitly as prohibitions: no casefolding, no
`unicodedata.normalize` call, no whitespace trimming, no separator splitting, no prefix or
namespace stripping.

**ENTAILED** — C5b is ASCII and therefore NFC-invariant, which is exactly why the
specification records that both classes satisfy B9
(`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:522-527`); C6 freezes the profile and states
that the identity function normalises nothing (`:610-613`); C5b excludes `/` precisely to
remove the invitation to split a value before comparing it (`:511-516`).

**CHOSEN** — writing the null profile down as a ratified rule rather than leaving it
implicit; the explicit bar on case-insensitive comparison.

**Alternatives considered and rejected.**
*(a) Add the declaration path to `nfc_paths`* — OD-1's rider requires a separately
ratified normalization profile for identity-participating text, and adding a path would
reopen C6's freeze for values that cannot be non-NFC in the first place.
*(b) Normalize at the boundary "defensively"* — a normalizer would be a second place at
which membership is decided, and B2's standing rule refuses a rule only one side checks
(ADR:189-191).

**What it does not authorize.** Any normalization of a policy body — that is Policy
Authority's canonicalization (`ADR_UGENCE_POLICY_AUTHORITY.md:363`). Any pattern on a C5c
field (`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:528-545`).

**Guard or test obligation.** A mutation test on the I5 pattern: a member differing only
by case, by surrounding whitespace, or by a `/`-bearing spelling must fail membership.
**Enforcement stops** at the two compared strings; it would say nothing about how the
resolver's permitted set was spelled upstream.

---

### Proposal 4 — Changed builder signatures and the public-surface delta

**Proposal.**

- **`build_proposer_advisory`** and **`build_advisory_revision`** would each gain exactly
  two keyword-only parameters: the **injected strategy-permission resolver** (Proposal 6)
  and the **producer's declared-strategy assertion**. Neither would gain a policy-identity
  or policy-version parameter — S2B-D7=A forbids it (ADR:195-198), on OD-7 part 5's
  selector-policy precedent, which the code already realises
  (`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/builders.py:157-162`).
  18 → 20 and 16 → 18 parameters.
- **`build_proposer_process_record`**: `declared_strategy: str` and `advisory_digest: str`
  would **both** be replaced by one `advisory: ProposerAdvisory` parameter, from which the
  builder would derive the record's `declared_strategy` (rider R1) and its
  `advisory_digest`. 13 → 12 parameters. `[V]` Today it receives both as bare
  caller-supplied strings (`builders.py:200,206`), which is exactly the shape R1 refuses
  (ADR:184-188). The plain-mapping `model_validate` construction would stay as it is, for
  the identity-source-guard reason documented at `builders.py:220-228`.

**Public surface: 46 → 51**, zero removals, zero renames.

**ENTAILED** — that all three builders change (ADR:237-241); that the record builder's
change sits **outside** A13's enumeration and needs its own public-surface ratification
(ADR:243-251; `[V]` A13 enumerates four builders at
`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:1091` while H1 defines five at
`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1922,:1943,:1956,:1979,:2000`); that no builder
takes the policy pair (S2B-D7=A).

**CHOSEN** — replacing `advisory_digest` with the whole advisory rather than adding a
third parameter beside it; the count and identity of the five added names; the
precedent-faithful request/response pair rather than a bare tuple return.

**Alternative considered (real, and a genuine owner choice).** A **minimal** surface of
46 → 48 — vocabulary, protocol, replay function — with the resolver returning the
permitted set and the policy pair as a plain tuple. Rejected as the recommendation because
OD-7's boundary exports request *and* response shapes precisely so the echo can be
correlated (`contracts.py:780-796`); a tuple has nowhere to carry the echoed reference,
and echo correlation is what would stop a resolver answering about a different policy.

**What it does not authorize.** Multi-resolver resolution. Any networking, storage,
service discovery or plugin loading (OD-7 part 2's bar, carried across). Any exported name
beginning with `Proposal` or `Recommendation` (D7,
`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2262-2265`).

**Guard or test obligation.** The `public_api.json` drift test by equality; the AST test
that the construction call's keyword set equals `set(ProposerAdvisory.model_fields)`
exactly (I7.16, `:2596-2618`), which the three new required fields would immediately
exercise.
**Enforcement stops** at shape: no test would establish that the injected resolver is the
right one.

---

### Proposal 5 — Package version, and whether an exception type is needed

**Version: `0.3.0`.** `[R]` It would be a **breaking** callable-surface move, not an
additive one: two builders gain required parameters and one loses two. Under `0.x` a minor
bump is the correct signal; `0.2.1` could not carry a contract change, and `1.0.0` would
assert a stability this slice does not have (three `[G]`s remain open). The move would
happen in the **same change set** as the fields, vocabulary, protocol, replay function and
tests, never ahead of them (I8's ratified ordering,
`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2620-2634`; OD-7 part 8's precedent).

**Exception type: none. Recommended.** S2B-D5=A's construction refusal would be discharged
by the **existing** H2 surface (`:2179-2213`):

| Failure | Existing type |
|---|---|
| Declared value fails its own field constraint, or is not a vocabulary member | `pydantic.ValidationError` — a closed in-package vocabulary is decidable by the model's own validator |
| Declared value not in the **resolved policy's** permitted set; permitted set empty; policy identity mismatch | `CrossContractViolationError` — H2 row 2 is exactly "a rule that compares fields across two or more independently constructed contract instances" |
| Resolver returns nothing, returns an uncorrelated echo, or raises | `CrossContractViolationError` (see the alternative below) |

**ENTAILED** — that independent replay returns `False` and never raises (S2B-D5=A,
ADR:143; `[V]` the existing verifiers do exactly this,
`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/verification.py:101-113,193-202,422-441`);
that no exception name is ratified and that construction "refuses" without a ratified
mechanism (ADR:151-154).

**CHOSEN** — reusing `CrossContractViolationError` rather than adding a sixth H2 class;
the version number.

**Alternative the owner may prefer.** A **fourth package-defined exception** for resolver
failure, on the `DomainEvaluationProviderError` precedent, which exists for the analogous
case of a provider raising during the original build (`:2189`). The argument for it is
symmetry and a caller catching one named family. The arguments against are that H2 is
written closed — "exactly five classes of failure, and no others" (`:2181`) — and that a
name of the `StrategyPermissionError` shape risks reading as a **denial**, which the
capability must never emit (ADR:151-153;
`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:240-247,263-278`). `[R]` A genuine owner
choice.

**What it does not authorize.** Any error text naming a reserved authority term. Any
mapping from a refusal to an operational outcome — S2B-D5=A leaves that owner deliberately
unruled (ADR:156-158).

**Guard or test obligation.** An exception-classification control on the OD-6(ii)
precedent; a source scan asserting that no new raise site names a reserved term.
**Enforcement stops** at this package: what a caller does with the refusal is out of scope
by ruling.

---

### Proposal 6 — The injected policy-resolver protocol S2B-D7=A implies

**Proposal.** A `runtime_checkable` **Protocol owned by this package and implemented
nowhere in it**, on the `DomainEvaluationProvider` precedent
(`contracts.py:780-796`). One keyword-only method:

```
resolve(*, request: <ResolverRequest>) -> <ResolverResponse>
```

- **Request** would carry: the policy reference read from `role`; `tenant_id`; `case_ref`;
  and a **caller-supplied** `as_of: datetime` — C4 bars any `src` module from reading a
  wall clock (`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:458-462`), and Policy Authority's
  own `resolve_policy` likewise takes an injected instant
  (`packages/policy-authority/src/ugence_policy_authority/core/resolution.py:107-118`).
- **Response** would carry: the policy identity; the policy version, as a **string** (C3);
  the permitted set as a sequence of vocabulary members; and an **echo of the reference
  resolved**, correlation-checked before use (OD-7 part 2's echo discipline;
  `builders.py:115-118`).
- The package would stamp identity and version **from the response**, never from a
  parameter (S2B-D7=A).
- **Fail-closed contract:** the resolver returns a response only for a policy it resolved
  *and* signature-verified through Policy Authority (`resolution.py:107-126`, whose key
  and signature statuses are already the failure taxonomy); anything else would be a
  structural failure under S2B-D5=A. `[R]` The response would carry **no** `verified`
  boolean — a boolean would be exactly the caller-supplied authorization S2B-D7=A refuses
  (ADR:203-204).

**ENTAILED** — that resolution is injected and the identity package-stamped (S2B-D7=A);
that Policy Authority is the issuer and resolver (S2B-D1=A; P-1, P-4, P-9,
`ADR_UGENCE_POLICY_AUTHORITY.md:88-131`); that a second family is additive by adapter
registration with no core change (P-9, `:273-300`); that this package imports no authority
internal (`:300-320`).

**CHOSEN** — one method rather than two; `as_of` carried in the request; the echo field;
the no-boolean rule.

**Alternatives considered and rejected.**
*(a) Import `ugence_policy_authority` directly* — breaks the dependency direction P-9
ratifies and would make the proposer a resolver.
*(b) Pass the resolved policy in as a plain value* — collapses S2B-D7=A: the package could
no longer distinguish a resolved policy from a caller-labelled one.
*(c) Let the proposer cache resolutions* — no caching is ratified anywhere, and a cache
would be a second resolution point.

**What it does not authorize.** Any concrete resolver. Any registration of the
strategy-permission policy family — `[G]` **none is registered, and S2B-D1=A is
design-ready and implementation-blocked until one is** (ADR:343-344). Any Policy Authority
core change.

**Guard or test obligation.** A protocol-conformance test with a stub resolver; negative
controls for a missing response, an uncorrelated echo, and an empty permitted set; a
boundary test that `src/` imports no `ugence_policy_authority` symbol.
**Enforcement stops** hard: `[G]` this package could not itself verify the policy's
signature, and no strategy-policy registry exists — the same disclosed ceiling
`verify_deterministic_selection` already carries for the selector policy
(`verification.py:437-441`).

---

### Proposal 7 — Rider R1: derive at construction, exact equality at replay

**Proposal.**

- **Derivation.** `build_proposer_process_record` would accept no `declared_strategy`. It
  would assign `record.declared_strategy` from the supplied advisory's declared-strategy
  field, and `record.advisory_digest` from the same object. This is the "derived, never
  accepted" move H1 already makes for the nested `candidates` sequence and the three
  selection-dependent fields (`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2140-2160`), one
  step beyond `build_advisory_candidate_set`'s "checked, never trusted"
  (`builders.py:151-156`).
- **Equality at replay.** Inside the S2B-D8=B function (Proposal 8):
  `record.declared_strategy == advisory.<declared-strategy field>`, exact codepoint
  equality under Proposal 3, plus `record.advisory_digest == advisory.advisory_digest` so
  a record cannot be replayed against a different advisory. Failure would return `False`.

**What it would prove, stated as the ADR requires.** `[R]` Equality proves
**correspondence between two observable fields** — that the record and the proposal name
the same declared strategy. It does **not** prove conformance with private reasoning, and
it does **not** prove that the declared procedure was executed (ADR:303-306). Derivation
prevents divergence at construction; **independent replay is the guarantee**
(ADR:188-191).

**ENTAILED** — retention, derivation and exact equality (rider R1, ADR:180-183); that
construction alone would be refused by B2's standing rule, which makes the replay leg
mandatory rather than optional.

**CHOSEN** — deriving `advisory_digest` from the same object at the same time; adding the
digest-equality check to the replay; the parameter replacement in Proposal 4.

**Alternatives considered and rejected.**
*(a) Keep `declared_strategy` a parameter and validate it against the advisory* — the
value would remain caller-supplied at the API boundary, and R1 says derived.
*(b) Drop the record's field as redundant* — R1 ratifies retention.
*(c) Make the record reachable from `P_unsigned`* — would make it a second identity
surface and is barred by D9 (`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:1260-1299`).

**What it does not authorize.** Any claim of conformance. Any inference from
`state_transitions` about internal control flow — the forward-only record cannot represent
it (`:1231-1259`).

**Guard or test obligation.** A construction test that a forged record (`model_construct`
with a divergent value) is rejected by the replay, on the I7.6 eligibility-forgery
precedent (`:2519-2521`); a signature test that no `declared_strategy` parameter exists.
**Enforcement stops** at the two fields: a producer that declares one method and performs
another would still yield a well-formed record — `[V]` the specification says so in terms
(`:1131-1136`).

---

### Proposal 8 — The replay function discharging S2B-D8=B

**Proposal.** One **new** exported function — not an extension of an existing verifier —
returning `bool`, never raising, taking exactly S2B-D8=B's four inputs (ADR:212-214):

```
verify_<...>_strategy_permission(
    *,
    advisory: ProposerAdvisory,
    policy: <ResolverResponse>,        # already resolved and signature-verified
    role: CognitiveRoleContract,
    process_record: ProposerProcessRecord,
) -> bool
```

It would check, in order, returning `False` and warning on the first failure (the
`_resolve_references` reporting precedent, `verification.py:193-202`):

1. the advisory's bound policy identity **and** version equal the supplied resolved
   policy's;
2. `role`'s policy reference resolves to that same policy;
3. the resolved permitted set is **non-empty**;
4. the advisory's declared strategy is a **member** of it, under Proposal 3's exact
   equality;
5. `process_record.declared_strategy` equals the advisory's, and
   `process_record.advisory_digest` equals `advisory.advisory_digest` (rider R1,
   Proposal 7).

It would emit **no disposition and no reserved authority term**, and a caller acting on an
advisory would have to call `verify_advisory_identity` as well — identity and
correspondence answer different questions
(`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2166-2172`).

**ENTAILED** — the four inputs and the `False` return (S2B-D8=B, S2B-D5=A); that signature
verification is an *input* rather than a step (ADR:212-213, :294-296).

**CHOSEN** — a new function over an extension; the five checks and their order; the
digest-equality addition.

**Alternative considered and rejected.** *Extend `verify_advisory_selection`* — its
`False` would then be ambiguous between a selection failure and a permission failure,
which is precisely the reason `verify_observation_resolution` was split out as a
separately named function (`:2174-2177`).

**What it does not authorize.** Observable-procedure conformance replay — `[R]` a named
later stage, outside this scope, and `[G]` blocked today because no component records
observable reasoning stages (ADR:216-218, :346-347).

**Guard or test obligation.** One negative test per check, plus a control that a `False`
from this function never coincides with an emitted disposition.
**Enforcement stops** at: the signature (verified upstream, and an input); provenance of
the named policy (`[G]` no strategy-policy registry); and everything listed at
ADR:307-311 — hidden model state, private chain-of-thought, provider-side routing or
fallback, and omitted stages, evidence or candidates.

---

## 3. Cardinality and public-surface delta

| Contract / model | Now | Proposed | Movement |
|---|---|---|---|
| `CognitiveRoleContract` | 10 `[V]` | 11 | +1 policy reference (C5a, non-identity) |
| `ProposerAdvisory` | 27 `[V]` | 30 | +3 (policy identity, policy version, declared-strategy assertion — all C5b, all identity-participating, all required and non-nullable) |
| `_UnsignedAdvisoryPayload` (private) | 26 `[I]` | 29 | mirrors the advisory minus `advisory_digest` (G2 step 1) |
| `ProposerProcessRecord` | 18 `[V]` | **18** | unchanged — `declared_strategy` retained; class narrowed C5c → C5b under OD-1's pre-authorization |
| `AdvisoryCandidateSet` | 12 `[V]` | 12 | unchanged — S2B-D6=B1 binds the **proposal** identity projection only |
| `CandidateAdvisory` | 11 `[V]` | 11 | unchanged |
| `AgentIdentityRef` / `WorkMandate` / `BoundedContextEnvelope` / `ToolObservation` / `ProposerProcessStateTransition` | 8 / 9 / 9 / 12 / 2 `[V]` | same | unchanged |

**Public surface: 46 → 51.** Zero removals; zero renames.

| Movement | Name (unsettled) | Kind |
|---|---|---|
| +1 | strategy vocabulary | enum or constant |
| +1 | strategy-permission resolver | protocol |
| +1 | resolver request | call-boundary shape (not a contract) |
| +1 | resolver response | call-boundary shape (not a contract) |
| +1 | S2B-D8=B replay function | function |
| ±0 | `build_proposer_advisory`, `build_advisory_revision`, `build_proposer_process_record` | names retained, **signatures changed** |

`[R]` The three builder signature changes would require public-surface ratification
independently of A13 — A13 covers four builders and stands intact for them
(ADR:243-251). `[R]` No exception name is added under the recommendation in Proposal 5.

---

## 4. The construction and replay order the first slice implies

**Construction — `build_proposer_advisory` / `build_advisory_revision`:**

1. validate inputs (existing behaviour);
2. read the strategy-permission policy reference from `role`;
3. call the injected resolver **once**, and correlate its echo;
4. **stamp** policy identity and version from the response (S2B-D7=A);
5. test the producer's declared strategy for membership in the resolved permitted set —
   no resolution, an unverified policy, an empty set or a non-member would **end
   construction here, producing no artifact** (S2B-D5=A);
6. then the existing OD-7 part 6 order: eligibility → domain evaluation → verification →
   selection → readiness;
7. construct the private payload (29 fields under Proposal 2) → `p_unsigned` → the single
   `ProposerAdvisory` expression with the substrate call inline in the `advisory_digest=`
   keyword (G2, `identity.py:392-421`);
8. `build_proposer_process_record` **derives** `declared_strategy` and `advisory_digest`
   from that advisory (rider R1).

`[I]` **Steps 2–5 would precede step 6 by choice, not entailment.** The reason: a
permission failure yields no artifact, so placing the permission test first would stop an
unpermitted run from ever reaching the injected domain evaluator. Placing it immediately
before construction is equally consistent with every ruling. `[R]` The owner should settle
it, because it is externally observable — it decides whether an unpermitted invocation
calls a third-party provider.

**Replay — independent, and the guarantee:**

1. resolve and signature-verify the policy version through Policy Authority — **outside
   this package**, and an input to what follows;
2. `verify_advisory_identity(advisory)`;
3. the S2B-D8=B function's five checks, in Proposal 8's order;
4. `verify_advisory_selection` and `verify_observation_resolution`, unchanged.

`[I]` Step 2 would precede step 3 by choice: testing membership on bytes not yet shown to
be the signed ones proves nothing about the signed artifact.

---

## 5. Implementation-readiness verdict

## `S2B_SLICE_REQUIRES_OWNER_RATIFICATION`

**Not blocked.** No repository contradiction was found. Every S2-B `[V]` claim
spot-checked against the tree held: `contracts.py:989`, `builders.py:194-231`, the
A13-versus-H1 four-against-five arithmetic, the 46-name surface, and the `__all__`
equality. The one staleness found (§1) is documentation narrative rather than a rule, and
is already the kind of item the ADR parks separately.

**Not ready.** §8's gate lists six items — vocabulary, normalization, contract shape,
builder signatures, public surface, package version — and this document **proposes** all
six and ratifies none (ADR:369-372). Two `[G]`s additionally block implementation even
after ratification: no second Policy Authority family is registered (ADR:343-344), and no
strategy vocabulary exists (ADR:351).

---

## 6. What remains ungranted after this design round

Everything in §8's gate, until the owner rules on §2. Beyond that, and **not proposed
here**:

- any vocabulary **member**, field **name**, spelling, default or encoding;
- strategy **composition**, ordering or subordinates (S2B-D3=A defers it);
- **mandate-level** narrowing and per-invocation authorization (S2B-D4=A);
- **required** strategies — whether policy may compel a procedure (ADR §4, unruled);
- the **operational-disposition owner** for a structural permission failure (S2B-D5=A,
  outside scope by construction);
- **observable-procedure conformance replay** (S2B-D8's later stage), and any producer of
  observable reasoning stages;
- registration of the strategy-permission **policy family** and its Policy Authority
  adapter;
- a **strategy-policy registry** that would close Proposal 8's provenance ceiling;
- any **binding to Reasoning Compute Governance** (ADR:256-257);
- recording provider or commercial model names as anything but operational evidence
  (RCG-D5);
- the Agent Constitution, and the re-derivation of the `CognitiveRoleContract` projection
  (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:106-130`);
- the three deferred catalogues and substantive multi-candidate ranking, unchanged by this
  slice.

---

## 7. Owner-ratification prompt (paste as-is)

```
S2-B first-slice ratification. Baseline: default branch head
90696d16ed8e9b9942252fe297c44bc3d16393a1. Governed by
docs/architecture/ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md
(S2B-D1..D8, rider R1, §8 gate) — do not reopen any of it.

Answer with letters only; one line per item. Recommendation in [brackets].

Q1  Vocabulary admission. Ratify a CLOSED vocabulary admitting members only by
    three criteria — externally evidenceable; not a contract mechanism or an
    outcome (OD-5's four exclusions); provider-neutral — with >=2 members, no
    default member and no escape member (OTHER/UNSPECIFIED/NONE); members
    themselves NOT ratified here.
    A = ratify the criteria as stated [recommended]
    B = ratify the criteria but permit an escape member
    C = defer the criteria; require members and criteria together in one ruling

Q2  Contract shape. CognitiveRoleContract 10->11 (a C5a policy REFERENCE only);
    ProposerAdvisory 27->30 (+ policy identity, policy version, one scalar
    declared-strategy assertion — all C5b, all identity-participating, all
    REQUIRED and NON-NULLABLE); private payload 26->29; ProposerProcessRecord
    stays 18; AdvisoryCandidateSet stays 12.
    A = ratify as stated [recommended]
    B = same, but make the three advisory fields nullable
    C = reject; require a nested declaration sub-model instead

Q3  Record field class. OD-1 states that narrowing declared_strategy to C5b,
    while it stays outside P_unsigned, needs no new ratification.
    A = take the narrowing, so both sides of R1's equality share a class
        [recommended]
    B = leave it C5c; R1's equality compares a C5b value against a C5c field

Q4  Normalization. Membership is exact codepoint equality between two
    C5b-constrained ASCII values. No normalizer, no casefolding, no trimming,
    no splitting; set_paths and nfc_paths stay frozenset().
    A = ratify as stated [recommended]
    B = require a normalization step (name the profile)

Q5  Builder signatures. build_proposer_advisory and build_advisory_revision each
    gain exactly two keyword-only parameters (injected resolver; producer's
    declared-strategy assertion) and NO policy-identity or version parameter.
    build_proposer_process_record replaces declared_strategy and advisory_digest
    with one `advisory` parameter and derives both (R1).
    A = ratify all three as stated [recommended]
    B = ratify the two advisory builders; defer the record builder
    C = keep declared_strategy a parameter on the record builder and validate it

Q6  Public surface. 46 -> 51: vocabulary, resolver protocol, resolver request,
    resolver response, replay function. No removals.
    A = 51 as stated [recommended]
    B = 48 — vocabulary, protocol, replay function only; resolver returns a
        plain tuple (loses echo correlation)

Q7  Package version.
    A = 0.3.0, moved in the same change set as fields, vocabulary, protocol,
        replay function and tests, never ahead of them [recommended]
    B = 1.0.0    C = other (state it)

Q8  Exception type for D5=A construction refusal.
    A = none; reuse pydantic.ValidationError and CrossContractViolationError,
        leaving H2 at five classes [recommended]
    B = add a fourth package-defined exception on the
        DomainEvaluationProviderError precedent (name to be ratified)

Q9  Resolver protocol. Package-owned runtime_checkable Protocol, implemented
    elsewhere, one keyword-only resolve(*, request) -> response; request carries
    the reference, tenant, case and a caller-supplied as_of; response carries
    identity, version (string), the permitted set and an echo of the reference;
    NO verified boolean; identity and version stamped from the response only.
    A = ratify as stated [recommended]
    B = ratify but allow a verified boolean on the response

Q10 R1 semantics. Record's declared_strategy derived from the proposal-bound
    declaration at construction; exact equality re-established at replay, which
    proves correspondence between two observable fields ONLY — never conformance
    with private reasoning and never that the declared procedure was executed.
    A = ratify as stated [recommended]

Q11 Replay function. One NEW exported function, returns bool, never raises,
    taking exactly D8=B's four inputs, checking in order: policy identity+version
    match; role's reference resolves to the same policy; permitted set non-empty;
    declared strategy is a member; record's declaration and advisory_digest match
    the advisory. Emits no disposition and no reserved authority term.
    A = ratify as stated [recommended]
    B = extend verify_advisory_selection instead

Q12 Construction order — externally observable, so it needs a ruling.
    A = resolve and test permission BEFORE the OD-7 evaluation sequence, so an
        unpermitted run never reaches the injected domain evaluator [recommended]
    B = test permission last, immediately before construction

Q13 Implementation gate. §8 requires vocabulary, normalization, contract shape,
    builder signatures, public surface and package version all ratified first.
    A = ratifying Q1-Q12 satisfies the gate EXCEPT the vocabulary members, which
        must still arrive with the field per OD-5(iii); code may not begin until
        they do [recommended]
    B = the gate is fully satisfied by Q1-Q12
```

---

## 8. Independent-review prompt for a different model (paste as-is)

```
Independent read-only review. Repository rasaha/symbolu, default branch head
90696d16ed8e9b9942252fe297c44bc3d16393a1. Do not modify anything: no branch, no
commit, no push, no PR.

Review docs/architecture/S2B_FIRST_SLICE_DESIGN_SPECIFICATION.md — a proposal
document that ratifies nothing. Verify it against the tree, not against itself.

Governing sources, to be read from the repository:
  docs/architecture/ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md
  docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md
  docs/architecture/ADR_UGENCE_POLICY_AUTHORITY.md
  docs/architecture/ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md
  packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md

Answer these seven questions, each with file:line evidence:

1. ACCIDENTAL RATIFICATION. Does the document anywhere treat as settled something
   the S2-B ADR leaves unratified — a vocabulary member, field name, container
   shape, builder parameter spelling, default, ordering encoding, exception name
   or terminal disposition (ADR:228-229)? Quote each instance.

2. FALSE REPOSITORY CLAIMS. Mechanically check every file:line citation. Report
   each that does not resolve, resolves to different content, or supports a
   weaker claim than made. Check the cardinality numbers (10, 27, 18, 12, 11, 26)
   and the 46-name surface independently.

3. HIDDEN CONTRACT COMMITMENTS. Does any proposal commit the contract family to
   something not disclosed in the delta table — a numeric value at any depth
   (C3), a change to C6's set_paths/nfc_paths, a new model reachable from
   P_unsigned, a second identity field, a rival identity name, or a field that
   would fail the I7.11 reachability walk or the I5 registry?

4. PRIVATE-CHAIN-OF-THOUGHT CONFUSION. Does anything describe the design as
   establishing conformance with private reasoning, or as proving a declared
   procedure was executed? ADR:303-311 and §6 are the standard. Flag any present
   tense applied to proposed behaviour.

5. CONFLICT WITH S2-A, A13, OR THE MERGED S2-B ADR. Does anything change the
   meanings of SATISFIED/NOT_SATISFIED/INCONCLUSIVE, weaken fail-closed selection
   uniqueness, introduce merit ranking, activate the candidate_id tie-break, or
   alter Equation 1 or 2? Does the treatment of build_proposer_process_record
   respect ADR:243-251 — that A13's "all four builders" does not cover it?

6. RCG DUPLICATION. Does anything create a binding to Reasoning Compute
   Governance, or introduce a compute budget, ceiling, capability tier, cost
   value, or a provider or commercial model name as a normative contract value
   (ADR:256-257; RCG-D5)?

7. STRUCTURAL FAILURE SEMANTICS. Does anything emit a denial, a reserved
   authority term, or map a structural permission failure to abstention, hold or
   escalation — all of which D5=A places outside scope (ADR:141-158)?

Return: a blocker list (each with file:line and the ruling violated), a
non-blocking list, and one verdict — SOUND, SOUND WITH CORRECTIONS, or UNSOUND.
Do not propose replacement design; report only what is wrong and why.
```

---

## 9. What this document changed

One new documentation file. **No production source, test, specification, ADR, RCG
document, CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** It ratifies nothing and authorizes no
implementation.
