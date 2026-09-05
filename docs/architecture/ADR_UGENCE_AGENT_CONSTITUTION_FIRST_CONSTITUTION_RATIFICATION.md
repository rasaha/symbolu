# ADR: Ugence Agent Constitution — first constitution's content, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item ballot put by the
first-constitution content specification. **No constitution is issued by this
ADR, and no issuance is authorized by it**: `ACC-FC-5` below sequences the first
issuance as a deployment act, gated on trust configuration that no repository
file may lawfully contain, and this ADR performs none of it.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default branch
`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`, head
`f5edbec9765c6768fd14ff167b37173bcfdff5a8` — the ballot document's own baseline,
the merge of PR #1530, which completed the `ACC-S1-Q5` sequencing.

## What was ratified, exactly

The ballot put over
[`AGENT_CONSTITUTION_FIRST_CONSTITUTION_CONTENT_SPECIFICATION.md`](AGENT_CONSTITUTION_FIRST_CONSTITUTION_CONTENT_SPECIFICATION.md)
**as that file stands at commit `5b6adb8860d5c3f0771a3e80184a11dfa782ed78`**:

| Identity value | Ratified value |
|---|---|
| Commit | `5b6adb8860d5c3f0771a3e80184a11dfa782ed78` |
| Document SHA-256 | `f9c436bde68802473b6535d1fe08ec6cc39b402b62b2dab6e2f83a9b637dbb30` |
| Line count | 275 |
| Ballot-block SHA-256 (`## 6.` heading through the `## 7.` heading, inclusive) | `f4e8f738908f6258cd1f6fadbce9bda18fdc8199b3e1aecb9ef1966d9b2c8854` |

`[V]` **All four values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`CONTENT_SURFACE`, `FC-1` … `FC-5` and match the wording the owner ruled over.
`[V]` Every §2 value in the pinned table was proven constructible by the family
package before the ballot was put — grammars, ordering and vocabulary membership
included.

`[R]` **The ratified text is the version at that commit.** Should the file gain
further commits, this declaration continues to govern the text at `5b6adb88`.

**Recorded exactly as ruled:**
`CONTENT_SURFACE=Yes FC-1=A FC-2=A FC-3=A FC-4=A FC-5=A`

`[I]` The ballot's stated answer domain for the surface question is `YES/NO`;
`Yes` is read as `YES`, and the five rows are unambiguous. `[R]` Every answer
takes the specification's recommended path; there is no departure to record.
`[V]` The specification's §7 independent-review prompt had not been run at
ruling time; the owner ruled directly, in the same session that drafted the
specification. That is recorded as fact, not as a defect: review was offered and
remains available to anyone auditing this record against the repository.

**Numbering.** `[R]` This ADR assigns **no** new `OD`, `S2B-*`, `P`, `RCG-D`,
`ACC-S1` or `ACC-AM` number. The composite fixed-surface ruling is recorded as
**`ACC-FC-BASE`** and the five register rulings as **`ACC-FC-1`** –
**`ACC-FC-5`**, all scoped to this ADR, on the standing precedent of ADR-scoped
citability labels; the ballot's own `CONTENT_SURFACE` and `FC-1` – `FC-5` labels
were proposal-local and are retired by this recording. No standing series is
extended, renumbered or reopened.

**Evidence labels.** `[V]` verified against this repository at the cited
`file:line`, a commit, or the named basis; `[I]` architectural inference; `[R]`
an owner ruling; `[G]` an unresolved gap.

> *This ADR changes **no** production source, test, specification, CHANGELOG,
> `public_api.json`, `version.py`, package metadata, CI workflow or
> platform-freeze artifact. `[V]` The substantive freeze digest was recomputed
> in this session and is unchanged, all checks PASS:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 1. `ACC-FC-BASE` — the fixed surface `[R]`

**Ruled: YES.** Ratify the fixed surface: the first constitution's clause
content is confined to the ratified `/clauses/v1` vocabulary — the three
structural bounds, nothing richer representable; no constitution is issued by
this round; no signing key, trust root or approval evidence enters the
repository; and the `/clauses/v2` question is out of scope (per `ACC-FC-5=A`).

**Precedence, as the ballot stated it** `[R]`: where a register ruling and the
fixed surface overlap, **the register ruling governs**. `[I]` Procedural on this
ballot, every row having been answered `A`; recorded because it governs how
`ACC-FC-BASE` is to be read by anyone later reopening a single row.

---

## 2. `ACC-FC-1` – `ACC-FC-5` — the five-item register

Each ruling is recorded in the words of the option the owner selected.

### `ACC-FC-1` — Authorship `[R]`

**Ruled: A.** The repository owner authors the first constitution personally;
this ADR records the authorship as an owner act. `[R]` Concretely: the pinned
specification's §2 content table, as ratified whole by `ACC-FC-2`..`ACC-FC-4`,
**is** the first constitution's authored content, and the owner is its author of
record. **Does not settle:** the approving authority at issuance, which remains
a deployment matter (`ACC-FC-5`).

### `ACC-FC-2` — Identity and scope `[R]`

**Ruled: A.** `policy_id` `agent-constitution-ugence`; `version` `1.0.0`;
`agent_constitution_ref` `ugence.agent-constitution/ugence/baseline/v1`;
`GLOBAL` scope with the canonical empty tenant; the effective window opening at
issuance and unbounded until superseded or revoked. `[I]` The signed reference
is the value every governed role's `constitution_ref` must equal exactly
(`ACC-AM-1`'s field, the conformance resolver's fourth post-check, and the
advisory builders' stamping equality — three consumers, one value). **Does not
settle:** any later tenant-scoped constitution, which is a new issuance.

### `ACC-FC-3` — Governed roles `[R]`

**Ruled: A.** Exactly one governed role reference:
`ugence.roles/ugence/invoice-reconciler/v1`, with the §3 disclosures ratified
alongside it. `[G]` Carried as ruled: no role artifact bearing this reference
exists in this repository; the `(tenant_id, role_contract_ref)` reference-map
population remains ungoverned; and governance begins at issuance and resolution,
not at this ratification — naming the role is a statement of intent with a
signed future, not present governance of anything.

### `ACC-FC-4` — The three bounds `[R]`

**Ruled: A.** The `/clauses/v1` content:
`permitted_candidate_dispositions_bound` = the full ratified closed vocabulary
(`ESCALATE_EXCEPTION`, `RECOMMEND_MATCHED_FOR_APPROVAL`, `RECOMMEND_WITHHOLD`,
`REQUEST_EVIDENCE`); `permitted_review_actions_bound` = the full ratified closed
vocabulary (`CREATE_EXCEPTION_REVIEW_BUNDLE`, `ROUTE_APPROVAL_BUNDLE`);
`permitted_tool_scopes_bound` = `("invoice.read", "ledger.read")`. `[R]` The
§2 bite disclosure is accepted as ruled: the closed bounds exclude nothing today
and bind as the vocabularies grow, while role membership and the tool-scope
ceiling are the constraints with present force — a governed role declaring any
scope beyond the two read scopes does not conform, and widening the ceiling is a
new constitution version, never an edit.

### `ACC-FC-5` — Issuance sequencing and the v2 round `[R]`

**Ruled: A.** The content is ratified documentation-only. The first issuance is
a **deployment act**, gated on: signing-key custody, an approving authority
whose evidence the always-supplied approval verifier checks, a composition root
wiring the guarded registration path, and reference-map population — `[G]` each
raised as a gap, none performed, none performable by a repository file. The
`/clauses/v2` vocabulary round is **not** commissioned, and `ACC-AM-4`'s
re-derivation re-arm condition stays untriggered. **Does not settle:** when or
by whom the deployment gates are closed.

---

## 3. Non-claims, carried forward unchanged

No constitution exists, is issued, or may be described as issued by virtue of
this record; ratified content is authored text with a signed future, not a
resolvable artifact. Constitution binding grants no compute, tools, evidence
access or consequential execution; digest membership proves integrity after
construction, never provenance; no verifier emits a disposition or reserved
authority term (`OD-C3=B`); no lifecycle authority exists or is implied
(`OD-C4=A`); and conformance replay, when it first runs against a genuinely
issued constitution, proves conformance of presented facts only.

---

## 4. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** The pinned ballot document is
unmodified: its commit, digest, line count and ballot block are unchanged, and
this ADR neither edits nor supersedes it. The Agentic Proposer remains at
`0.4.0` with fifty-one authorized public names; Policy Authority at `0.1.0`;
both constitution distributions at `0.1.0`.

**Next steps after this ADR merges:** none in this repository's files — the
`ACC-FC-5` deployment gates (key custody, approving authority, composition
root, reference-map population) are the path to the first genuine issuance, and
they are operational work, not change sets. The open in-repo threads remain the
two raised Policy Authority milestones and, when the owner chooses to convene
it, the `/clauses/v2` vocabulary round — which re-arms the `ACC-AM-4`
re-derivation obligation the day it ratifies clause content beyond the three
structural bounds.
