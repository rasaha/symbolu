# ADR: Ugence S2-B strategy-permission policy family and concrete resolver — owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the three rulings put by the S2-B strategy-permission
policy-family and concrete-resolver design proposal. **No implementation is performed by this
ADR, and none exists.** It does authorize implementation — see §3 — but authorization is not
implementation, and nothing is built here.

**Date:** 2026-08-29.

**Decision owner:** the repository owner, who is the sole ratifying authority for S2-B
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:23`), ratifying personally.

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`, head
`070a91281f1f3a8ad9185ebae1f422430727d974` (merge of PR #1503, the S2-B first production
implementation at `0.3.0`).

## What was ratified, exactly

The three-part ballot put over
[`S2B_STRATEGY_PERMISSION_POLICY_FAMILY_AND_RESOLVER_DESIGN.md`](S2B_STRATEGY_PERMISSION_POLICY_FAMILY_AND_RESOLVER_DESIGN.md)
**as that file stood at commit `1091549641d8dcb50f94a39ce53b4b87b1db6734`**:

| Identity value | Ratified value |
|---|---|
| Commit | `1091549641d8dcb50f94a39ce53b4b87b1db6734` |
| Document SHA-256 | `579c42389c3118a2c3bc9e654ac5cac64fa7fdced295e15b81cb2ef35900fe3e` |
| Line count | 774 |
| Ballot-block SHA-256 (`## 12.` heading through the `## 13.` heading, inclusive) | `48eff4dd6393a65f9b04ac425ac3c6ec3a094711e3c033baea17f9161615f8a1` |

`[V]` **All four values were verified against that commit before this ADR was written**, by
reading the file out of the named commit rather than out of a working copy: the commit
resolves and is the head of `claude/strategy-permission-policy-authority-nptbu6`; the document
digest, the line count and the ballot-block digest each reproduce exactly; and the design
baseline head reproduces exactly. `[V]` The eight owner-decision register rows at that commit
are present, in order `OD-A` … `OD-H`, and match the wording the ballot quoted.

`[R]` **The ratified text is the version at that commit**, not any later working copy. Should
that file ever gain further commits, this declaration continues to govern the text at
`1091549641d8dcb50f94a39ce53b4b87b1db6734`.

**Recorded exactly as ruled:**
`FIXED_DESIGN_SURFACE=YES OD-A=A OD-B=A OD-C=A OD-D=A OD-E=A OD-F=A OD-G=B OD-H=A
AUTHORIZE_IMPLEMENTATION=YES`

`[R]` **`OD-G=B` is the sole departure from the design's recommended path.** Every other
answer takes the recommendation; `OD-G` does not, and §3 records what that authorizes.

**Numbering.** `[R]` This ADR assigns **no new OD number and no new `S2B-D` number.** The
composite ruling is recorded as **`S2B-PF-BASE`**, the register as **`S2B-PF-A`** – **`S2B-PF-H`**,
and the implementation-authority ruling as **`S2B-PF-IMPL`**, all scoped to this ADR. `[I]` The
ballot named the first two labels and did not name a label for the third; `S2B-PF-IMPL` is
supplied here for citability and is the one naming choice this ADR makes rather than records.
OD-1 … OD-10, A11–A13, P-1 … P-11, `S2B-D1` – `S2B-D8` with rider `R1`, `S2B-S1-Q1` – `S2B-S1-Q13`
and `S2B-R2-Q1` – `S2B-R2-Q8` are neither extended, renumbered nor reopened.

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` an owner ruling; `[G]` an unresolved gap.

> *This ADR changes **no** production source, test, specification, CHANGELOG,
> `public_api.json`, `version.py`, package metadata, CI workflow or platform-freeze artifact.
> The substantive freeze digest is unchanged before and after it:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 1. `S2B-PF-BASE` — the fixed design surface `[R]`

**Ruled: YES.** Ratify, as the foundational S2B-PF design surface, the non-alternative
implementation commitments stated in §§1–10 of the pinned artifact, including:

* the exact adapter ID, policy-family value and policy-type value in §1.2;
* scopes `GLOBAL` and `TENANT`;
* lifecycle labels `DRAFT`, `APPROVED_ACTIVE`, `SUPERSEDED`, `WITHDRAWN`;
* the exact metadata and policy-body field sets, types, requiredness and validation rules in §1.3;
* `ugence.agentic-proposer.reasoning-strategy/v1` as the exact required `vocabulary_version`
  value — see §1.1;
* the canonical projection removing only `metadata.content_digest`;
* `ReasoningStrategy`'s string values as the permitted-set representation;
* the imported `ReasoningStrategy` enum as the single source of truth;
* the recommended package ownership and dependency direction;
* `case_ref` as correlation/audit context only;
* caller-supplied `as_of` passed through unchanged;
* request-derived tenant verification;
* historical resolution `DENY_ALWAYS`;
* the exact response mapping, with no `verified` boolean;
* the resolver failure taxonomy, and the rule that `PolicyResolutionReason` tokens reach a
  caller only through the exception's `reason` attribute, never message text;
* the exact `0.1.0` versions and public surfaces in §8's delta table;
* the end-to-end proof obligations and atomic implementation order in §§9–10.

### 1.1 The `vocabulary_version` value is fixed **by this ruling** `[R]`

`[V]` §1.3 of the pinned artifact states
`ugence.agentic-proposer.reasoning-strategy/v1` **illustratively** — "e.g." — not as a settled
value. `[R]` **`S2B-PF-BASE=YES` hardens that example into a fixed, digest-bound value**, and
the owner ratified it deliberately in that knowledge, naming no alternative.

`[R]` It is recorded here as **a value fixed by ruling, not a value carried over from the
artifact.** `[I]` The consequence is ordinary and intended: the string participates in the
canonical projection and therefore in every issued policy's body digest, so changing it later
moves every digest and is a new policy version, not an edit.

### 1.2 Precedence — reproduced verbatim from the ballot `[R]`

> PRECEDENCE, so YES cannot pre-settle the register. Several items above are governed by an
> OD row — the §1.3 body includes strategy_policy_ref (OD-C) and vocabulary_version (OD-F);
> §4's ownership is OD-A; §5.3's mapping mechanism is OD-D; the approval verifier is OD-E; §8's
> two-distribution surface is OD-A; §1.3's non-empty rule is OD-B. Where the fixed surface and
> an OD ruling overlap, THE OD RULING GOVERNS, and the fixed surface ratifies only the residue
> that no OD row puts in question. A YES here is not a vote for option A on any of the eight.

`[I]` On this ballot the point is procedural rather than consequential, since every overlapping
row was independently answered `A`. It is recorded because it governs how `S2B-PF-BASE` is to be
read, including by anyone later reopening a single OD row: reopening `OD-D` reopens §5.3's
mechanism, and `S2B-PF-BASE` does not preserve it.

### 1.3 What YES does not do — reproduced verbatim from the ballot `[R]`

> WHAT YES DOES NOT DO. It does not convert any [V] factual claim into an owner ruling; it does
> not widen any non-claim in the S2-B ADR's §6; it does not authorize implementation by itself;
> and it does not settle the four stale Agentic Proposer prose sites recorded in §8.1.

`[R]` **What `S2B-PF-BASE` does not settle**, beyond that clause: nothing about whether the
design is correct, only that it is the ratified surface to build; no repository fact, all of
which remain verifiable or falsifiable on their own terms; and no question the register or
§3 answers.

---

## 2. `S2B-PF-A` – `S2B-PF-H` — the eight-item register

Each ruling is recorded in the words of the option the owner selected.

### `S2B-PF-A` — Packaging `[R]`

**Ruled: A.** Two new integration distributions:
`ugence-agentic-proposer-strategy-permission-policy` (artifact + `PolicyFamilyAdapter`) and
`ugence-agentic-proposer-strategy-permission-runtime` (concrete resolver).

`[R]` **Does not settle:** the internal module layout of either distribution; whether either
ever splits further; or any packaging question for a third party consuming them.

### `S2B-PF-B` — Empty permitted set at issuance `[R]`

**Ruled: A.** The family refuses to construct or issue a policy whose permitted set is empty.

`[R]` **Does not settle:** what an empty set would have meant. `[V]` It remains
**representable at the resolver-response boundary**, which is ratified and unchanged — the
response shape admits an empty set on purpose so `verify_strategy_permission`'s third check can
report that state, and this ruling does not touch it.

### `S2B-PF-C` — Signed reference binding `[R]`

**Ruled: A.** `StrategyPermissionPolicy` carries `strategy_policy_ref` in its digest-bound
body, and the resolver requires exact equality with the request's reference.

`[R]` **Does not settle:** who mints a reference, or by what convention. The policy asserts
which reference it answers to; it does not confer authority to choose one.

### `S2B-PF-D` — Reference resolution mechanism `[R]`

**Ruled: A.** An injected, immutable, defensively copied mapping keyed by
`(tenant_id, strategy_policy_ref)` to a complete `PolicyCoordinate`; unknown keys fail closed.

`[R]` **Does not settle:** how a deployment populates or distributes that mapping, or its
operational lifecycle. `[I]` With `S2B-PF-C=A` the mapping locates a policy; the signed
reference is what binds it.

### `S2B-PF-E` — Approval re-verification `[R]`

**Ruled: A.** Resolution always supplies an approval verifier, so an approval withdrawn after
issuance invalidates resolution.

`[R]` **Does not settle:** which verifier a composition root configures, or what external
governance process stands behind it. `[V]` Production ships only a deny-by-default verifier;
permissive verifiers exist only under `tests/`.

### `S2B-PF-F` — Vocabulary version `[R]`

**Ruled: A.** The artifact carries a required `vocabulary_version` naming the strategy
vocabulary. Its exact value is fixed by `S2B-PF-BASE` — §1.1.

`[R]` **Does not settle:** any process for versioning the vocabulary itself, or what a second
vocabulary version would mean. `[V]` A fourth vocabulary member remains unratified and, on
`S2B-R2-Q1=A`'s tiling property, cannot simply be added.

### `S2B-PF-G` — The disclosed `0.3.0` alien-response `AttributeError` `[R]`

**Ruled: B.** Authorize a **separate** Agentic Proposer `0.3.1` change set wrapping it as
`CrossContractViolationError` (public surface unchanged at 51 names).

`[R]` **This is the ballot's one departure from the design's recommendation**, which was to
leave the behaviour as garbage input. The owner ruled otherwise, and §3 records the separation
that ruling requires.

`[R]` **Does not settle:** H2's class count, which stays at **five** — `S2B-S1-Q8=A` ratified
no new exception type and this ruling introduces none; it routes an existing failure into an
existing class. Nor does it settle any other change to Agentic Proposer: the authorization is
for this hardening and nothing adjacent.

### `S2B-PF-H` — Family package `public_api.json` snapshot `[R]`

**Ruled: A.** Ship one.

`[R]` **Does not settle:** whether the runtime distribution ships one. `[I]` The ballot's
wording targets the family package, and under `S2B-PF-A=A` that is unambiguous.

### 2.1 The disclosed couplings, as resolved by these answers `[I]`

`[V]` The design disclosed three couplings. All resolve consistently here:

* `OD-C` is motivated by `OD-D=A` — and `S2B-PF-D=A` was ruled, so `S2B-PF-C=A` sits on its
  intended footing rather than the redundant one;
* `OD-E=B` would have made the `APPROVAL_PROOF_INVALID` failure row unreachable — `S2B-PF-E=A`
  was ruled, so that row **remains reachable** and its end-to-end obligation stands;
* `OD-H`'s wording presupposes `OD-A=A` — which was ruled, so no retargeting is required.

---

## 3. `S2B-PF-IMPL` — implementation authority `[R]`

**Ruled: YES.** Authorizes §10 steps 2–5 (family package, runtime package, end-to-end proof,
distribution verification), **and only after this ratification ADR merges.**

`[V]` The dependency the ballot recorded is satisfied: `S2B-PF-IMPL=YES` has effect because
`S2B-PF-BASE=YES` fixed the surface those steps implement.

### 3.1 The `S2B-PF-G=B` separation, recorded explicitly `[R]`

Because `S2B-PF-G=B` was ruled, this ADR records, as the ballot requires:

1. `AUTHORIZE_IMPLEMENTATION=YES` authorizes **§10 steps 2–5 only after this ratification ADR
   merges**;
2. `S2B-PF-G=B` **independently** authorizes the separate Agentic Proposer `0.3.1` boundary
   hardening at **§10 step 7**, on its own change set;
3. **the `0.3.1` change MUST NOT be bundled with the two new integration packages.**

`[R]` These are two authorizations, not one. Neither implies the other's scope, and neither may
be widened by the other's existence. `[I]` The bundling prohibition is the same discipline the
S2-B §8 gate enforced against "while we're in there" edits, applied here to a change the owner
has now explicitly authorized rather than to one nobody had.

### 3.2 What `S2B-PF-IMPL` does not settle `[R]`

It authorizes the steps as the pinned artifact specifies them. It does **not** authorize: any
step 2–5 work that departs from `S2B-PF-BASE` or from any register ruling; step 6's
documentation reconciliation beyond what §10 states; any change to Agentic Proposer other than
step 7's; any change to Policy Authority; or anything the pinned artifact records as deferred,
ungranted or unruled.

---

## 4. Non-claims carried forward, unchanged `[R]`

This declaration changes nothing in the S2-B ADR's §6. Reasoning Strategy Permission still does
not claim, and must never be described as claiming, that a model's private reasoning becomes
deterministic; that a declared strategy proves the model internally followed it; that Ugence can
inspect, reconstruct, preserve or replay private chain-of-thought; that a provider's description
establishes the strategy used; or that a caller-supplied identifier becomes authoritative
through structure or digest binding.

`[R]` **Permission grants no compute, tools, evidence access or consequential execution.**
Consequential execution remains with Risk Authority, ActionGate and Decision Authority.

`[R]` **S2-B still creates no binding to Reasoning Compute Governance**, and any future binding
requires separate ratification. This declaration duplicates no part of RCG.

`[R]` **Digest membership proves integrity after construction, never provenance.** Inclusion in
an identity projection establishes that a value was not altered afterwards; it does not
establish that the proper authority issued it.

`[R]` A successful Policy Authority resolution proves issuance authenticity and current
validity under configured trust roots at an explicit `as_of`. It proves **nothing** about
whether a policy is wise, correct, lawful or commercially sound, and it authorizes no runtime
action.

---

## 5. What remains ungranted `[R]`

Unchanged by this declaration:

* **strategy composition or ordering** (`S2B-D3=A`) — exactly one primary strategy per
  invocation stands;
* **mandate-level narrowing and per-invocation authorization** (`S2B-D4=A`) — permission
  remains role-level;
* **required strategies** — whether policy may compel a procedure is not ruled;
* **the operational-disposition owner for a structural permission failure** (`S2B-D5=A`) —
  deliberately unruled, and nothing here maps a permission failure to abstention, hold,
  escalation or referral;
* **observable-procedure conformance replay in general** (`S2B-D8=B`), and `[G]` its still-absent
  producer — no component records observable reasoning stages;
* **any fourth vocabulary member** — the three tile every lawful advisory.

---

## 6. Gaps this declaration does not close `[G]`

`[G]` **The four stale present-tense sites in Agentic Proposer**, recorded at §8.1 of the pinned
artifact: `version.py:12-13` and `contracts.py:839-842` in source, and
`tests/test_s2b_strategy_permission.py:26` and `tests/s1_specification_mirror.py:427` in the test
tree. All four assert that no strategy-permission policy family is registered. `[V]` **No test
pins any of the four strings** — the two test-tree occurrences are a docstring and a comment,
not assertions — so when they go stale, nothing fails and nothing announces the drift.

`[R]` **Whether to correct `contracts.py` was deliberately not on this ballot**, and this
declaration does not settle it. `[I]` It is not reachable from §10 step 6 either, since
correcting it means editing Agentic Proposer source. `[R]` It is **not** authorized by
`S2B-PF-G=B`: that ruling authorizes the `0.3.1` boundary hardening, not a documentation sweep
travelling with it.

---

## 7. What changes about execution

`[R]` **The standing gap — "no strategy-permission policy family is registered with Policy
Authority" — is closed as a RULING by this declaration.** `S2B-D1=A` was design-ready and
implementation-blocked; `S2B-PF-BASE`, the register and `S2B-PF-IMPL` together remove the
blockage, so the family that closes it is now specified, decided and authorized to be built.

`[G]` **It is not closed as a FACT.** No family is registered, no adapter exists, no resolver
exists, and Reasoning Strategy Permission still **cannot execute end to end**. That remains true
until §10 steps 2–3 land — the family package and the runtime package, each as its own atomic
change set. `[R]` Until then, no document, changelog, release note or status report may describe
the capability as executable, and the distinction between a ruling and a fact must not be
elided in either direction.

`[I]` This is the A11/A12 pattern in its final position: "unblocked on ratification grounds" was
never "authorized to implement", and "authorized to implement" is not "implemented".

---

## 8. What this ADR changed

One new documentation file. **No production source, test, specification, readiness ADR, RCG
document, CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** The pinned design artifact is unmodified: its commit,
document digest, line count and ballot block are unchanged, and this ADR neither edits nor
supersedes it.

The Agentic Proposer remains at `0.3.0` with fifty-one authorized public names, and Policy
Authority at `0.1.0` with sixty-six, until the change sets `S2B-PF-IMPL` and `S2B-PF-G=B`
authorize are themselves written.
