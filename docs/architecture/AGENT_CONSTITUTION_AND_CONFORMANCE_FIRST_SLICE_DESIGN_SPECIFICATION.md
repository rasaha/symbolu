# Agent Constitution & Conformance — first-slice design specification

**Status: design proposal — documentation only. Nothing here is ratified, and no
implementation is authorized by it.** The analysis was performed read-only: it modified no
production source, test, package metadata, `public_api.json`, `version.py`, CI workflow or
platform-freeze artifact, and this document is the only file its change set adds. The five
owner decisions in §10 are **open**; §11 is the ballot that would settle them.

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`, head
`f4ab600ffcd741902cb155fc9666061cff27fa02` — which **is** the merge commit of PR #1521, the
Agent Constitution & Conformance scoping ADR. Every `[V]` claim below is verifiable against
that head.

**Governing scope:** the `OD-C1` – `OD-C5` rulings of
[`ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md`](ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md).
This specification designs within them, extends no standing boundary, reopens no ruling, and
assigns **no** new `OD`, `S2B-D`, `S2B-S1`, `S2B-R2`, `S2B-PF`, `P` or `RCG-D` number. Ballot
rows are labeled `Q1` – `Q5`, proposal-local; the register labels for whatever is ratified
are the ratification ADR's to assign, on the `S2B-PF` precedent. Per `OD-5`'s arrive-together
rule (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:638`), every name and vocabulary member
here is a **ballot item**, not a settled value.

**Load-bearing question, answered first.** The first slice is **one new Policy Authority
policy family plus one disposition-free structural conformance verifier, shipped as new
integration distributions with no change to any existing package** — the `S2B-PF-A`
packaging entailment followed, not objected to. The Agentic Proposer contract-amendment
round `OD-C1=B` puts on the MVP's critical path is **designed here as a separately balloted,
separately ratified step** (§7): it is not part of this ballot, and first release is gated
on it. The two design-surface guard obligations the scoping ADR assigned to this register —
the family-collision guard and the one-active-constitution-per-role rule — are carried as
ballot rows `Q3` and `Q4`.

**Evidence labels.** `[V]` verified against this repository at the cited `file:line` or the
named basis; `[I]` architectural inference; `[R]` owner ruling required; `[G]` unresolved gap.

> *This specification changes **no** production source, test, package metadata, CHANGELOG,
> `public_api.json`, `version.py`, CI workflow or platform-freeze artifact. `[V]` The
> substantive freeze digest was recomputed in this session and is unchanged, all checks PASS:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 0. Baseline verification

| Check | Result |
|---|---|
| Default-branch head | `[V]` `f4ab600ffcd741902cb155fc9666061cff27fa02` — exact match; the working tree was verified clean |
| Merge of PR #1521 in history | `[V]` it is the head commit itself (`git merge-base --is-ancestor` returns true) |
| Scoping rulings | `[V]` `OD-C1=B OD-C2=A OD-C3=B OD-C4=A OD-C5=A` (`ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md:64`) |
| Agentic Proposer | `[V]` `0.3.1` (`src/ugence_agentic_proposer/version.py:84`); `public_api.json` = 51 symbols |
| Policy Authority | `[V]` `0.1.0`; `public_api.json` = 66 symbols |
| Strategy-permission family + runtime | `[V]` both exist under `packages/integration/agentic-proposer-strategy-permission-{policy,runtime}` |
| No constitution family under any name | `[V]` no `packages/integration` entry and no adapter names a constitution; `UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_INITIAL_DESIGN_SPEC_v0.1` remains absent |
| Substantive freeze digest | `[V]` recomputed via `python -m platform_freeze.verify`: PASS, `d9930935…fac036`, unchanged |

**No baseline mismatch. Proceeding.**

---

## 1. What the first slice is, and is not

`OD-C5=A` fixes the **product label** as "Agent Constitution" and leaves the canonical
technical artifact a narrower name settled at ratification. This document proposes that
narrower name (§3, `Q1`); until ratification the artifact is referred to generically below.

`[I]` The first slice is deliberately **structural**: an externally authored, externally
approved, authority-issued constitution artifact that declares, for the roles it governs,
the bounds a role projection must stay within — and a replay-style verifier that reports
whether presented role facts conform. That is the largest slice constructible inside the
rulings: `OD-C2=A` gives it an issuance home, `OD-C3=B` forbids it any operational
disposition, `OD-C4=A` forbids it any lifecycle authority, and the standing gaps (§9) leave
observable-procedure conformance without an input.

**This document is not `UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_INITIAL_DESIGN_SPEC_v0.1`
and does not claim its name.** `[V]` The readiness ADR obliges the proposer-local role
projection to be re-derived from the constitution "when the document does exist", rather
than promoted (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:123-127`). `[R]` Nothing here
promotes the projection, and the designed vehicle for the re-derivation question is the
contract-amendment round (§7). Whether any later document takes that recorded name is an
owner matter outside this ballot.

**Never, in this slice** (each prohibition stated once, all carried from standing rulings):
no component writes or transitions `AgentLifecycleState` (`OD-C4=A`; `[V]` the enum is an
externally issued input fact, `vocabulary.py:193-199`, `S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`
role-binding table); no suspension, revocation or offboarding authority; no operational
disposition, denial, `ABSTAIN` or reserved authority term from any verifier (`OD-C3=B`;
`[V]` `RESERVED_AUTHORITY_VOCABULARY`, `vocabulary.py:123-135`); no compute, tools, evidence
access or consequential execution granted; no role identity minted, and no required-attribute
authority claimed over roles beyond the declared bounds; no strategy-permission content —
that family owns it; no amendment content ratified outside the §7 round.

---

## 2. The constitution policy family contract

### 2.1 Placement and precedent

`[V]` `OD-C2=A` rules issuance into a new Policy Authority policy family, and the additive
path is proven: `P-9` adds a family by registering an adapter with no core change
(`ADR_UGENCE_POLICY_AUTHORITY.md:125-127`), exercised twice from outside the authority's
distribution — capacity-bounds and strategy-permission
(`packages/integration/agentic-proposer-strategy-permission-policy/src/ugence_agentic_proposer_strategy_permission_policy/adapter.py:83-101`).
This design mirrors the strategy-permission family's discipline exactly: stdlib-only frozen
dataclasses, validation at construction, a canonical projection removing exactly
`metadata.content_digest` by path.

### 2.2 Metadata envelope

`[I]` Identical in shape and rules to the ratified strategy-permission metadata
(`…strategy_permission_policy/identifiers.py:62-87`, `policy.py`): `policy_id` and `version`
(C5b `Token` grammar, strings), `content_digest` (declared, removed by path from the
projection), `scope` `GLOBAL`/`TENANT` with the tenant rule, `policy_family` fixed to this
family's constant and re-checked by the adapter, `lifecycle_state` in
`DRAFT`/`APPROVED_ACTIVE`/`SUPERSEDED`/`WITHDRAWN` (active iff `APPROVED_ACTIVE`),
`supersedes_ref` empty (`[V]` P-6 refuses non-empty at issuance,
`ADR_UGENCE_POLICY_AUTHORITY.md:112`), tz-aware half-open effective window.

### 2.3 Body

| Field | Type | Rule |
|---|---|---|
| `metadata` | envelope | §2.2 |
| `agent_constitution_ref` | `str` | the reference this constitution asserts it is named by — C5a `Identifier` grammar; the `S2B-PF-C` signed-reference precedent (`ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md:161-167`). §7's amendment round is its consumer: a role's `constitution_ref` must equal it exactly |
| `governed_role_refs` | `tuple[str, ...]` | non-empty; C5a grammar; no duplicates; ascending codepoint order, rejected if unsorted (capacity-bounds ordering precedent). The roles this constitution claims to govern |
| `permitted_candidate_dispositions_bound` | `tuple[str, ...]` | non-empty, unique, sorted; every element a `CandidateDisposition` value (`[V]` `vocabulary.py:86`) — the maximal set a governed role may declare |
| `permitted_review_actions_bound` | `tuple[str, ...]` | non-empty, unique, sorted; every element a `ReviewAction` value (`[V]` `vocabulary.py:138-142`) |
| `permitted_tool_scopes_bound` | `tuple[str, ...]` | unique, sorted, **may be empty** (`[V]` a role's `permitted_tool_scopes` defaults empty, `contracts.py:302`); C5b `Token` grammar — an open vocabulary, bounded not enumerated |
| `constitution_vocabulary_version` | `str` | required; names the clause vocabulary the bounds are drawn from; proposed value in §3 (`S2B-PF-F` precedent) |

`[I]` The three bounds reference the proposer's ratified enums as the single source of truth
— the imported-enum option the strategy-permission family ratified (`S2B-PF-BASE`,
`S2B_STRATEGY_PERMISSION_POLICY_FAMILY_AND_RESOLVER_DESIGN.md:245-250`) — so no fork of a
closed vocabulary is possible; the tool-scope bound is the one open-vocabulary bound, and it
bounds by membership, not by grammar alone.

`[I]` Conditional on the §2.1 projection, every body field except `metadata.content_digest`
is transitively signed through `policy_body_digest`; the coverage claim holds exactly as far
as the projection is implemented as written, which is why the end-to-end proof recomputes the
framed digest independently (§5.4).

**First-slice conformance predicate.** Presented role facts conform to a resolved
constitution iff: the role reference is a member of `governed_role_refs`; the declared
candidate-disposition set is a subset of its bound; the declared review-action set is a
subset of its bound; and the declared tool-scope set is a subset of its bound. Set semantics,
order-insensitive; empty declared tool scopes conform to any bound. `[R]` The predicate is a
`Q`-independent part of the fixed surface, put whole to ratification.

---

## 3. Identifiers — proposed values, settled only at ratification (`Q1`)

| Constant | Proposed value |
|---|---|
| Adapter ID | `ugence.agent-constitution/v1` |
| Policy family | `agent_governance.agent_constitution` |
| Policy type | `AgentConstitutionPolicy` |
| Canonical technical artifact name (`OD-C5=A`'s "narrower name") | `AgentConstitutionPolicy` — the artifact class and the policy type are the same word deliberately |
| `constitution_vocabulary_version` | `ugence.agent-constitution/clauses/v1` |
| Scopes / lifecycle labels | reused verbatim from §2.2 — no new member |

`[V]` Collision analysis: the proposed family value collides with no registered family —
the five UVI values are bare upper tokens (`GEOGRAPHY` … `READINESS`,
`packages/uvi-policy-contracts/src/ugence_uvi_policy_contracts/contracts/enums.py:29-36`),
and the two integration families are `cloud_scaling.capacity_bounds` and
`agentic_proposer.strategy_permission`
(`…strategy_permission_policy/identifiers.py:46`). The adapter ID collides with no
registered adapter ID. `[R]` Per `OD-5`, name and vocabulary arrive together: `Q1` ratifies
this table whole or returns it whole.

---

## 4. Packaging — the `S2B-PF-A` entailment, restated and followed (`Q2`)

`[R]` Restated from the scoping ADR's §4: packaging is entailed by the `S2B-PF-A` convention
— **a governance concern ships as its own integration distributions rather than inside the
capability package** (`ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md:143-150`) —
and the entailment was left open to objection by this specification.

**This specification follows the entailment and raises no objection.** `[I]` Every reason
that forced it for strategy permission binds harder here: the authority's dependency bars
exclude an in-authority adapter outright (`[V]` the stdlib-only import bar,
`packages/policy-authority/tests/packaging/test_dependency_boundary.py`), the proposer may
not import the authority (`[V]` `BARRED_IMPORTS`,
`tests/test_s2b_strategy_permission.py:911`), and a constitution inside any single
capability would mis-own an artifact whose `governed_role_refs` reach beyond it.

Proposed (names are `Q2` ballot items):

* `packages/integration/agent-constitution-policy/` — distribution
  `ugence-agent-constitution-policy`: artifact, adapter, identifiers, errors. No resolution,
  no signing, no clock, no network. Ships `public_api.json` (`S2B-PF-H` precedent).
* `packages/integration/agent-constitution-conformance/` — distribution
  `ugence-agent-constitution-conformance`: the concrete resolver, the conformance verifier,
  failure taxonomy, composition helper, end-to-end proof.

Dependency direction mirrors the strategy-permission pair: both new packages may import
`ugence_policy_authority.api` and `ugence_agentic_proposer` (vocabulary enums only); neither
existing package imports either of them; neither existing package changes.

---

## 5. Conformance verification design

### 5.1 A constraint that shapes the input: the role-projection scan

`[V]` `test_the_projection_is_local_to_this_package_wherever_it_is_defined` scans every
`.py` under `packages/` outside the proposer for the substrings `CognitiveRole`,
`COGNITIVE_ROLE`, `cognitive_role` — docstrings included
(`packages/capabilities/agentic-proposer/tests/test_role_projection_bounds.py:58,508-518`).
Neither new package may name the role contract anywhere in its source. `[I]` The verifier
therefore takes a **package-local frozen dataclass of plain role facts** — role reference,
declared disposition values, declared review-action values, declared tool-scope tokens,
tenant — assembled by the caller. Disclosed plainly: replay proves conformance of the
**presented** facts to the resolved constitution; that those facts equal a live role
projection is the caller's assertion, exactly as digest membership proves integrity after
construction, never provenance (`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:298-301`).

### 5.2 Resolution

On the ratified `S2B-PF-D`/`S2B-PF-E` pattern, restated once: an injected, immutable,
defensively copied mapping keyed by `(tenant_id, role_contract_ref)` to a complete
`PolicyCoordinate`; unknown keys fail closed with no fallback, prefix match or "latest";
caller-supplied tz-aware `as_of` passed through verbatim; request-derived
`expected_reference_tenant_id`; an approval verifier always supplied at resolution;
historical resolution `DENY_ALWAYS`. A response exists **only** on `RESOLVED`; every other
authority reason raises. Post-checks, each raising its own error class: exact runtime
artifact type; `request.role_contract_ref ∈ resolution.policy.governed_role_refs` (the
signed-side role binding); every bound element a member of its source enum; and — where the
caller presents a constitution reference (post-amendment, §7) — exact equality with the
signed `agent_constitution_ref`.

### 5.3 Failure taxonomy — disposition-free by construction (`OD-C3=B`)

One base error class with subclasses for the §5.2 rows, each carrying the authority's
`PolicyResolutionReason` verbatim in a `reason` attribute. `[V]` The reserved-vocabulary
collision is real and inherited: `EXPIRED`, `SUPPORTED` and `UNSUPPORTED` are reserved terms
scanned uppercased as substrings (`vocabulary.py:123-135`), so a resolution-reason token may
appear **only** in the `reason` attribute, never in message text — the rule `S2B-PF-BASE`
already ratified for the sibling family. The conformance verifier itself returns `True` or
`False`, mints no artifact on failure, and maps nothing to abstention, hold, escalation or
referral: `[V]` the structural-failure operational-disposition owner remains deliberately
unassigned (`OD-C3=B`, continuing `S2B-D5=A`).

### 5.4 End-to-end proof obligations

On `test_authority_registration.py`'s pattern, deterministic, clock- and network-free:
genuine issuance with real Ed25519 signing and independent recomputation of the framed body
digest; deny-by-default approval verifier refused at issuance, permissive verifiers under
`tests/` only; exact-only mapping (near-miss role ref raises); mutated artifact fails on
digest mismatch; revocation, effective-window and lifecycle refusals; role not in
`governed_role_refs` raises; conformance predicate proven in both directions (conforming
facts → `True`; each bound violated independently → `False`); a guard asserting no reserved
authority term, `TerminalOutcome` or `CandidateDisposition` value in any error name or
message template, scanned uppercased as substrings; no networking, storage,
service-discovery, plugin-loading or clock import; and the §6 guards below.

---

## 6. The register guard obligations (`Q3`, `Q4`)

Carried here as design-surface register items because the scoping ADR's §4 assigns them to
this specification's register rather than ruling them.

### 6.1 `Q3` — the Policy Authority family-collision guard

`[V]` The existing collision surface is exactly one check: the adapter registry refuses a
duplicate `adapter_id` at registration
(`packages/policy-authority/src/ugence_policy_authority/core/adapters.py:217-220`). Nothing
refuses two adapters, under distinct IDs, claiming the same `policy_family` value: recognition
is by artifact type (`adapters.py:229-239`), and the coordinate identity slot
(`adapters.py:94`) would let two families' artifacts collide in the registry's identity space
only coordinate-by-coordinate, as conflicts, after issuance.

`[R]` **Recommended (`Q3=A`):** the family package ships the stronger guard at its own
boundary, with no authority change — the composition helper that registers this family
asserts, over the assembled registry, that exactly one adapter answers for this family value
and that the family value differs from every family value any other registered adapter
emits; plus a packaged test pinning the §3 value against the repository's known family
values. `[I]` This closes the collision for this family without touching the frozen
authority core; a core-level uniqueness guard for all families is raised as a Policy
Authority milestone (§9), consistent with `OD-C2=A`'s treatment of lifecycle gaps.
**`Q3=B`** relies on the duplicate-ID refusal and per-coordinate conflict semantics alone.

### 6.2 `Q4` — one active constitution per role

`[R]` **Recommended (`Q4=A`):** ratify the rule — **at most one constitution governs a role
at any `as_of`** — and enforce it fail-closed at the conformance boundary, where it is
enforceable today: the §5.2 mapping is keyed by `(tenant_id, role_contract_ref)`, so a
deployment cannot *represent* two active constitutions for one role; the signed
`governed_role_refs` membership check then binds the one selected constitution to the role
on the signed side. Disclosed honestly `[G]`: two issued constitutions may both sign
`governed_role_refs` containing the same role, and no registry-level cross-artifact query
exists to refuse the overlap at issuance — that enforcement point is raised as a Policy
Authority milestone (§9), not claimed. **`Q4=B`** declines the rule and admits plural
resolvable constitutions per role; rejected by recommendation because every downstream
consumer would then need its own precedence semantics, which is an authority question no
ruling grants.

---

## 7. The contract-amendment ratification round (`OD-C1=B`), designed (`Q5`)

`[V]` `OD-C1=B` puts an Agentic Proposer contract-amendment ratification round on the MVP's
critical path, so the first released constitution is digest-bound to the proposals it
governs, and rules that the round itself must ratify the amendment's content, fields and
binding mechanism (`ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md:95-107`).

**The designed shape this specification proposes to that round** (proposed, not ratified —
`Q5` adopts the design as the round's input, never as its outcome):

1. **Role surface:** one C5a reference field, `constitution_ref`, on the role-contract
   surface, on the exact precedent of `strategy_policy_ref` (`[V]` `contracts.py:311-322`) —
   a reference to an externally issued constitution, resolved by injection, never role data.
2. **Proposal surface:** `constitution_policy_id` and `constitution_policy_version` stamped
   from resolution onto the advisory **inside `P_unsigned`**, on the `S2B-D6=B1` precedent
   that put `strategy_policy_id`/`strategy_policy_version` inside the signed projection so an
   unbound declaration cannot outlive its policy (`[V]` `identity.py:130-138`). That is what
   "digest-bound to the proposals it governs" cashes out to.
3. **Re-derivation:** the round is the vehicle for the readiness ADR's obligation to
   re-derive the role projection from the constitution rather than promote it
   (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:123-127`); the amendment ballot must state
   what the projection's re-derivation changes, even if the answer is "nothing yet".

**Sequencing** `[R]`: (1) this specification's ballot and ratification ADR; (2) family and
conformance implementation, if that ADR grants it; (3) the amendment round, separately
balloted and ratified; (4) the amendment's own change set. First release requires all four;
(2) and (3) do not order each other. The amendment moves the proposer's version and public
surface; by how much is the round's to ratify, and nothing here settles it.

---

## 8. Version and public-surface impact

| Package | Version / surface | Nature |
|---|---|---|
| `ugence-agentic-proposer` | `0.3.1`, 51 names, **unchanged by this slice** | the §7 round, when ratified, changes it in its own change set |
| `ugence-policy-authority` | `0.1.0`, 66 names, **unchanged** | `[V]` `P-9` additive-adapter path, twice proven |
| strategy-permission pair | **unchanged** | untouched |
| `ugence-agent-constitution-policy` | `0.1.0`, new | artifact, metadata, adapter, coordinate helper, identifiers, errors |
| `ugence-agent-constitution-conformance` | `0.1.0`, new | resolver, conformance verifier, role-facts input type, error family, composition helper |

---

## 9. Gaps carried and raised

`[G]` Carried unchanged: no agent-lifecycle writer; no reasoning-stage producer; no
invocation-level authorization; reference-map population ungoverned — and the §5.2 mapping
inherits that last gap in full (`ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md:233-256`).

`[G]` Raised by this design as Policy Authority milestones, on `OD-C2=A`'s pattern of
raising without closing: a core-level family-value uniqueness guard (§6.1), and a
registry-level cross-artifact check refusing overlapping `governed_role_refs` at issuance
(§6.2). Neither is designed, scheduled or closed here.

`[G]` The constitution's substantive content — which clauses a real constitution should
carry beyond the three structural bounds, and who authors the first one — is outside this
slice; the first slice proves the issuance, binding and conformance machinery on structural
clauses only.

---

## 10. Owner-decision register (five)

| # | Decision | A (recommended) | B |
|---|---|---|---|
| Q1 | Canonical name and vocabulary (arrive together) | the §3 table, whole | return whole; owner supplies values, same collision analysis required |
| Q2 | Packaging under the `S2B-PF-A` entailment | two distributions as named in §4 | one combined distribution |
| Q3 | Family-collision guard | family-side registration guard + pinned-value test (§6.1) | status quo surfaces only |
| Q4 | One-active-constitution-per-role | ratify the rule; enforce at the conformance boundary (§6.2) | no such rule |
| Q5 | The `OD-C1=B` amendment round | adopt §7's design and sequencing as the round's input | sequence the round with content left entirely to it |

Couplings, disclosed: `Q5=A` is what makes §2.3's `agent_constitution_ref` earn its place —
under `Q5=B` the field stays defensible as the `S2B-PF-C` precedent but its §5.2 equality
check has no caller until the round supplies one. `Q4=A` presupposes no particular `Q5`
answer: the mapping key is the role reference either way. No other pair interacts. All five
are independently answerable, and the fixed surface (§§2, 3-values-excepted, 4-names-excepted,
5) is put to ratification whole alongside them, on the `S2B-PF-BASE` precedent with its
precedence rule: where a `Q` row and the fixed surface overlap, **the `Q` ruling governs**.

---

## 11. Paste-ready owner-ratification ballot

```
Agent Constitution & Conformance — first-slice owner ballot
Baseline: rasaha/symbolu default head f4ab600ffcd741902cb155fc9666061cff27fa02
Governed by OD-C1..OD-C5 as ratified. Answer each with A or B. A = the recommended path.

FIXED_DESIGN_SURFACE  Ratify, as the foundational design surface, the non-alternative
      commitments of the specification's §§2, 4 and 5 — metadata envelope, body field set
      and validation rules, the conformance predicate, resolution and fail-closed semantics,
      the reason-attribute rule, and the proof obligations — with the S2B-PF precedence
      rule: where a Q row and this surface overlap, the Q ruling governs.  YES/NO.

Q1  Canonical name and vocabulary (OD-5: they arrive together).
    A = ratify the §3 table whole: adapter ID ugence.agent-constitution/v1, policy family
        agent_governance.agent_constitution, policy type and artifact name
        AgentConstitutionPolicy, clause-vocabulary version
        ugence.agent-constitution/clauses/v1, scopes and lifecycle labels reused.
    B = return the table; the owner supplies alternative values, which must pass the same
        collision analysis before ratification.

Q2  Packaging (the S2B-PF-A entailment, followed).
    A = two new integration distributions: ugence-agent-constitution-policy (artifact +
        adapter) and ugence-agent-constitution-conformance (resolver + verifier).
    B = one combined distribution.

Q3  Policy Authority family-collision guard (register obligation).
    A = the family package ships a registration-time guard asserting exactly one adapter
        answers for this family value across the assembled registry, plus a pinned-value
        collision test; a core-level uniqueness guard is raised as a Policy Authority
        milestone, not built.
    B = rely on the existing duplicate-adapter-id refusal and coordinate conflicts alone.

Q4  One active constitution per role (register obligation).
    A = ratify the rule: at most one constitution governs a role at any as_of, enforced
        fail-closed at the conformance boundary by the (tenant_id, role_contract_ref)
        mapping plus the signed governed_role_refs membership check; the registry-level
        overlap refusal is raised as a Policy Authority milestone, not claimed.
    B = no such rule; plural resolvable constitutions per role are admissible.

Q5  The OD-C1=B contract-amendment ratification round.
    A = adopt §7's designed shape (constitution_ref on the role surface;
        constitution_policy_id/version inside P_unsigned on the proposal surface;
        re-derivation addressed) and its sequencing as the round's INPUT; the round itself
        remains separately balloted and alone ratifies the amendment's content.
    B = sequence the round with its content left entirely to it.

Record as: FIXED_DESIGN_SURFACE=? Q1=? Q2=? Q3=? Q4=? Q5=?
No implementation is authorized by this ballot; implementation authority, register labels
and any authorization ruling belong to the ratification ADR that records these answers.
```

---

## 12. Paste-ready independent-review prompt

```
Read-only independent review. Do not modify files, create a branch, commit, push or open a PR.

Repository: rasaha/symbolu
Expected default-branch head: f4ab600ffcd741902cb155fc9666061cff27fa02
Artifact under review: the Agent Constitution & Conformance first-slice design
specification (docs/architecture/AGENT_CONSTITUTION_AND_CONFORMANCE_FIRST_SLICE_DESIGN_SPECIFICATION.md).

Verify the baseline first (head, clean tree, the scoping ADR merged as PR #1521, proposer
0.3.1/51, authority 0.1.0/66, both strategy-permission packages present); stop on mismatch.
Then judge against the repository, not the specification's prose:

1. Does the design stay inside OD-C1..OD-C5 — in particular, does anything grant lifecycle
   authority (OD-C4), emit a disposition or authority term (OD-C3), or ratify amendment
   content the OD-C1 round must ratify?
2. Are the two register obligations (family-collision guard, one-active-per-role) carried
   as genuine ballot rows with the existing enforcement surfaces cited correctly —
   adapters.py:217-220 and the absence of any family-value uniqueness check?
3. Is the S2B-PF-A packaging entailment restated accurately and followed coherently?
4. Do the proposed identifiers collide with any registered family or adapter value?
5. Can the conformance package be written at all under the role-projection substring scan
   (test_role_projection_bounds.py), and is the presented-facts caveat honest?
6. Is anything described as implemented, settled or ratified that is not?
Return SOUND, SOUND_WITH_CORRECTIONS, or BLOCKED, findings cited to file:line.
```

---

## 13. Readiness verdict

**READY_FOR_OWNER_RATIFICATION.** Baseline verified in full; the substantive freeze digest
is unchanged; five owner decisions plus the fixed-surface question are open, and none is
settled here. Next step after ratification: the ratification ADR recording the answers,
assigning register labels, and ruling on implementation authority — then, separately, the
§7 amendment round.
