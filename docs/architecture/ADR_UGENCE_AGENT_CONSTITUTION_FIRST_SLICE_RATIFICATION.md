# ADR: Ugence Agent Constitution & Conformance first slice — owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item ballot put by the Agent Constitution &
Conformance first-slice design specification. **No implementation is performed by this ADR,
and none is authorized by it** — see §3: the implementation gate stands, and an
authorization ruling was deliberately not part of this ballot.

> **Superseded in part as to authorization (2026-08-31, `ACC-S1-IMPL=YES`).** "none is
> authorized by it" is retained verbatim above as the record of what was true of the
> six-item ballot this ADR records. `[R]` A **later, separate ruling the same day** —
> recorded at §7, put over this ADR as it stood at commit
> `b867ee8ace03226fcc9da884f5aa4042dd1317f1` — grants implementation authority under §3's
> stated terms. The rest of the sentence stands unchanged: this ADR still performs no
> implementation, and authorization is not implementation.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on 2026-08-31.
On the standing precedent: **where the conversation and this ADR differ, this ADR governs.**

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`, head
`f4ab600ffcd741902cb155fc9666061cff27fa02` (merge of PR #1521, the scoping ADR) — unchanged
since the specification's own baseline verification.

## What was ratified, exactly

The ballot put over
[`AGENT_CONSTITUTION_AND_CONFORMANCE_FIRST_SLICE_DESIGN_SPECIFICATION.md`](AGENT_CONSTITUTION_AND_CONFORMANCE_FIRST_SLICE_DESIGN_SPECIFICATION.md)
**as that file stands at commit `09a33d76237aa8cc66a410042cdc40b281e2c2dd`**:

| Identity value | Ratified value |
|---|---|
| Commit | `09a33d76237aa8cc66a410042cdc40b281e2c2dd` |
| Document SHA-256 | `62d213ce550c2563125acc854b341c159dc2817f0461c6a469e5affed4ffaeb5` |
| Line count | 472 |
| Ballot-block SHA-256 (`## 11.` heading through the `## 12.` heading, inclusive) | `4ba45ac2b26538294ca68f2bac8713eccb7d146c1baff142b3f46eb5c62d0eff` |

`[V]` **All four values were verified before this ADR was written**, by reading the file out
of the named commit rather than out of a working copy; the working copy is byte-identical.
`[V]` The ballot text the owner ruled over was diffed against the pinned `§11` fenced block
and matches it exactly, whitespace included. `[V]` The five register rows are present in
order `Q1` … `Q5` and match the wording the ballot quoted.

`[R]` **The ratified text is the version at that commit.** Should the file gain further
commits, this declaration continues to govern the text at `09a33d76`.

**Recorded exactly as ruled:**
`FIXED_DESIGN_SURFACE=YES Q1=A Q2=A Q3=A Q4=A Q5=A`

`[R]` Every answer takes the specification's recommended path; there is no departure to
record. `[V]` The specification's `§12` independent-review prompt had not been run at ruling
time; the owner ruled directly, in the same session that drafted the specification. That is
recorded as fact, not as a defect: review was offered and remains available to anyone
auditing this record against the repository.

**Numbering.** `[R]` This ADR assigns **no** new `OD`, `S2B-D`, `S2B-S1`, `S2B-R2`,
`S2B-PF`, `P` or `RCG-D` number. The composite fixed-surface ruling is recorded as
**`ACC-S1-BASE`** and the five register rulings as **`ACC-S1-Q1`** – **`ACC-S1-Q5`**, all
scoped to this ADR, on the `S2B-PF` precedent of ADR-scoped citability labels; the ballot's
own `Q1` – `Q5` labels were proposal-local and are retired by this recording. `OD-C1` –
`OD-C5` and every standing series are neither extended, renumbered nor reopened.

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`, a
commit, or the named basis; `[I]` architectural inference; `[R]` an owner ruling; `[G]` an
unresolved gap.

> *This ADR changes **no** production source, test, specification, CHANGELOG,
> `public_api.json`, `version.py`, package metadata, CI workflow or platform-freeze
> artifact. `[V]` The substantive freeze digest was recomputed in this session and is
> unchanged, all checks PASS:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 1. `ACC-S1-BASE` — the fixed design surface `[R]`

**Ruled: YES.** Ratify, as the foundational first-slice design surface, the non-alternative
commitments of the pinned specification's §§2, 4 and 5, including: the metadata envelope on
the ratified strategy-permission pattern; the exact body field set, types, requiredness and
validation rules of §2.3, `agent_constitution_ref` and the three bounds included; the
imported proposer enums as the single source of truth for the closed-vocabulary bounds; the
first-slice structural conformance predicate, whole; the canonical projection removing only
`metadata.content_digest`; the `(tenant_id, role_contract_ref)` injected-immutable-mapping
resolution with fail-closed semantics, request-derived tenant verification, an approval
verifier always supplied, and historical resolution `DENY_ALWAYS`; the signed
`governed_role_refs` membership post-check; the package-local role-facts input shape forced
by the role-projection scan, with its presented-facts caveat; the disposition-free failure
taxonomy and the rule that `PolicyResolutionReason` tokens reach a caller only through the
exception's `reason` attribute, never message text; and the §5.4 end-to-end proof
obligations.

**Precedence, as the ballot stated it** `[R]`: where a register ruling and the fixed surface
overlap, **the register ruling governs**, and the fixed surface ratifies only the residue no
register row puts in question. `[I]` On this ballot the point is procedural, since every
register row was answered `A`; it is recorded because it governs how `ACC-S1-BASE` is to be
read by anyone later reopening a single row.

`[R]` **What YES does not do:** it converts no `[V]` factual claim into an owner ruling; it
ratifies no name or vocabulary value (`ACC-S1-Q1` owns those); it authorizes no
implementation (§3); it does not settle the amendment round's content (`ACC-S1-Q5` and
`OD-C1` reserve that to the round itself); and it does not make the specification the absent
`UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_INITIAL_DESIGN_SPEC_v0.1` document, whose naming
remains an owner matter outside this ballot.

---

## 2. `ACC-S1-Q1` – `ACC-S1-Q5` — the five-item register

Each ruling is recorded in the words of the option the owner selected.

### `ACC-S1-Q1` — Canonical name and vocabulary `[R]`

**Ruled: A.** Ratify the specification's §3 table whole: adapter ID
`ugence.agent-constitution/v1`; policy family `agent_governance.agent_constitution`; policy
type and canonical technical artifact name `AgentConstitutionPolicy`; clause-vocabulary
version `ugence.agent-constitution/clauses/v1`; scopes and lifecycle labels reused verbatim
from the strategy-permission family, no new member.

`[R]` This is the `OD-C5=A` "narrower name settled at ratification", settled: the product
label remains **Agent Constitution**, and `AgentConstitutionPolicy` is the canonical
technical artifact. Per `OD-5`, the name and the vocabulary arrive together in this one
ruling. `[I]` The ordinary consequence holds: every ratified string that participates in the
canonical projection is digest-bound, so changing one later moves every issued digest and is
a new version, not an edit. **Does not settle:** any process for versioning the clause
vocabulary, or what a `/clauses/v2` would mean.

### `ACC-S1-Q2` — Packaging `[R]`

**Ruled: A.** Two new integration distributions: `ugence-agent-constitution-policy`
(artifact + adapter) and `ugence-agent-constitution-conformance` (resolver + verifier).

`[R]` The `S2B-PF-A` entailment — a governance concern ships as its own integration
distributions — was restated open to objection, no objection was raised, and this ruling
closes it **followed** for this family. **Does not settle:** internal module layout, any
later split, or packaging for third-party consumers.

### `ACC-S1-Q3` — Policy Authority family-collision guard `[R]`

**Ruled: A.** The family package ships a registration-time guard asserting exactly one
adapter answers for this family value across the assembled registry, plus a pinned-value
collision test; a core-level uniqueness guard is raised as a Policy Authority milestone, not
built.

`[V]` The register obligation this discharges was assigned by the scoping ADR's §4
(`ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md:221-229`), and the existing
surface is the duplicate-`adapter_id` refusal alone
(`packages/policy-authority/src/ugence_policy_authority/core/adapters.py:217-220`).
**Does not settle:** the milestone's design, schedule or owner — raised, on `OD-C2=A`'s
pattern, without being closed.

### `ACC-S1-Q4` — One active constitution per role `[R]`

**Ruled: A.** At most one constitution governs a role at any `as_of`, enforced fail-closed
at the conformance boundary by the `(tenant_id, role_contract_ref)` mapping plus the signed
`governed_role_refs` membership check; the registry-level overlap refusal is raised as a
Policy Authority milestone, not claimed.

`[G]` Disclosed by the specification and carried into this record: two issued constitutions
may both sign `governed_role_refs` containing the same role, and no registry-level
cross-artifact query exists to refuse the overlap at issuance. The rule is ratified; its
issuance-time enforcement point is a raised milestone. **Does not settle:** precedence
semantics for any future plural-constitution design, which this ruling makes unnecessary
rather than resolves.

### `ACC-S1-Q5` — The `OD-C1=B` contract-amendment ratification round `[R]`

**Ruled: A.** Adopt the specification's §7 designed shape — `constitution_ref` on the role
surface; `constitution_policy_id`/`constitution_policy_version` inside `P_unsigned` on the
proposal surface; re-derivation addressed — and its sequencing, **as the round's input**.
The round itself remains separately balloted, and alone ratifies the amendment's content.

`[R]` Read with `OD-C1` exactly: no amendment field, contract shape or binding mechanism is
ratified **here** — this ruling fixes what is put to that round and the order it happens in,
nothing more. The ratified sequencing: (1) this ADR; (2) family and conformance
implementation, once authorized (§3); (3) the amendment round; (4) the amendment's own
change set. First release requires all four; (2) and (3) do not order each other.
**Does not settle:** the proposer's post-amendment version or surface, which the round
ratifies.

---

## 3. Implementation gate — nothing is authorized by the six-item ballot `[R]`

*(Recorded as ruled on the six-item ballot; the gate this section describes was
subsequently opened by the separate `ACC-S1-IMPL` ruling — see §7, which governs.)*

**No Agent Constitution code may begin.** The ballot carried no authorization line by
design, the owner's answer contains none, and this ADR grants none. `[V]` The scoping ADR's
§6 gate (`ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md:259-268`) therefore
stands in full: ratification of a design surface is not authorization to implement. `[I]`
This is the standing A11/A12 discipline in the same position it held between `S2B-PF-BASE`
and `S2B-PF-IMPL` — the surface is now fixed and decided, and building it awaits its own
explicit owner ruling.

`[R]` What such a ruling would authorize, when given, is the pinned specification's design
as ratified here — the two `ACC-S1-Q2` distributions with their §5.4 proof obligations —
and nothing that departs from `ACC-S1-BASE` or any register ruling. It would not authorize
the amendment round's change set, which `ACC-S1-Q5` keeps separately balloted, nor any
change to Policy Authority or the Agentic Proposer.

---

## 4. Non-claims and standing principles, carried forward unchanged `[R]`

Strategy permission and constitution conformance alike grant **no compute, tools, evidence
access or consequential execution**. **Digest membership proves integrity after
construction, never provenance** — `OD-C1=B` binds the constitution and its proposals to
one another and makes neither self-authenticating. A successful resolution proves issuance
authenticity and current validity under configured trust roots at an explicit `as_of`, and
proves nothing about whether a constitution is wise, correct or lawful. Conformance replay
proves conformance of the **presented** role facts only. No verifier emits a disposition,
denial, `ABSTAIN` or reserved authority term (`OD-C3=B`), and the structural-failure
operational-disposition owner remains deliberately unassigned. No lifecycle authority
exists or is implied (`OD-C4=A`).

---

## 5. Gaps this declaration does not close `[G]`

Carried unchanged from the specification's §9: no agent-lifecycle writer; no
reasoning-stage producer; no invocation-level authorization; reference-map population
ungoverned, the `ACC-S1-Q4` mapping included. Raised as Policy Authority milestones and
left open: the core-level family-value uniqueness guard (`ACC-S1-Q3`) and the
registry-level `governed_role_refs` overlap refusal (`ACC-S1-Q4`). Outside the slice: the
constitution's substantive clause content beyond the three structural bounds, and who
authors the first constitution.

---

## 6. What this ADR changed

One new documentation file. **No production source, test, specification, readiness ADR, RCG
document, CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** The pinned specification is unmodified: its commit,
document digest, line count and ballot block are unchanged, and this ADR neither edits nor
supersedes it. The Agentic Proposer remains at `0.3.1` with fifty-one authorized public
names, and Policy Authority at `0.1.0` with sixty-six.

**Next steps after this ADR merges**, in the `ACC-S1-Q5` sequencing: an explicit owner
ruling on implementation authority for the two ratified distributions (§3), and — before
any first release — the `OD-C1=B` contract-amendment ratification round, on its own ballot.
*(The first of these has since been ruled — §7; the amendment round remains open.)*

---

## 7. `ACC-S1-IMPL` — implementation authority, recorded (2026-08-31) `[R]`

**Ruled: YES**, by the repository owner personally, in conversation on 2026-08-31, on a
one-item ballot put **after** the six-item ballot §§1–2 record and **over this ADR as it
stood at commit `b867ee8ace03226fcc9da884f5aa4042dd1317f1`**. `[V]` That commit was the
branch head at ruling time, with a clean tree, and the substantive freeze digest reproduced
unchanged (`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`).

**Recorded exactly as ruled:** `ACC-S1-IMPL=YES`

The ballot's operative text, in full: authorize implementation of the two ratified
distributions — `ugence-agent-constitution-policy` (artifact + adapter) and
`ugence-agent-constitution-conformance` (resolver + verifier) — exactly as the pinned
specification's ratified surface specifies them, each as its own atomic change set with its
§5.4 end-to-end proof obligations, and **only after this ratification ADR merges**. It
authorizes no departure from `ACC-S1-BASE` or any register ruling, no change to Policy
Authority or the Agentic Proposer, and not the `OD-C1=B` amendment round's change set,
which remains separately balloted.

`[R]` **What this changes, precisely.** The §3 gate is opened **as a ruling**: the first
slice is now specified, decided and authorized to be built — the position `S2B-PF-IMPL`
occupied for its family. `[G]` **It is not closed as a fact**: no constitution family, no
adapter, no resolver and no conformance verifier exists, and none may be described as
existing until the two change sets land. The merge precondition is part of the ruling: no
implementation change set may begin ahead of this ADR reaching the default branch.

`[R]` **Numbering.** `ACC-S1-IMPL` is scoped to this ADR like its §§1–2 siblings; no
standing series number is assigned, and no prior ruling — `ACC-S1-BASE`, the register,
`OD-C1` – `OD-C5`, or anything they carry forward — is extended, narrowed or reopened.
This section records one authorization and nothing else; §§3–6 stand as the record of the
ballot that preceded it, read subject to this section.
