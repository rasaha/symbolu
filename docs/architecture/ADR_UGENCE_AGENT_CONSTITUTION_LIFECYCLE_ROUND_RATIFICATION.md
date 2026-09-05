# ADR: Ugence Agent Constitution — lifecycle round, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item lifecycle round scoping
ballot. **No implementation is authorized by this ADR**, and none is performed:
no contract changes shape, no lifecycle state is added, no act is written, and
`ACC-LC-5` below sequences the implementation as a separate change set under a
separate ruling. No issuance, revocation or supersession occurs by virtue of
this record.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `534cd5ac` — the merge of PR #1543, which landed the
`ACC-PR` ratification, the `ACC-PR-IA` implementation-authority ruling and the
invoice-reconciler pilot change set.

## 1. What was ratified, exactly

The ballot put is
[`AGENT_CONSTITUTION_LIFECYCLE_ROUND_SCOPING_BALLOT.md`](AGENT_CONSTITUTION_LIFECYCLE_ROUND_SCOPING_BALLOT.md)
**as that file stands at commit `42880238`**, the commit that authored it:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_LIFECYCLE_ROUND_SCOPING_BALLOT.md` |
| Authoring commit | `42880238` ("Convene the lifecycle round: scoping ballot over policy-version supersession") |
| Document SHA-256 | `2bffe512fe3a0df2febebc61272a243d9c1ebe96bebbc0cfe334f12fec19cafb` |
| Line count | 283 |
| Ballot-block SHA-256 (`## 6.` heading through the `## 7.` heading, inclusive; 67 lines) | `a63734920a766d47974f2aa4b963e8843212bf395ad1d4e7abb2ea15ccb7891f` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`LIFECYCLE_SURFACE`, `LC-1` … `LC-5` and match the wording the owner ruled
over.

`[R]` **The authoring commit is the citation of record**, on the precedent this
repository follows — `ACC-FC` pinned its ballot at `5b6adb88`, and the `ACC-PR`
ratification records `f2ec22e5` for the same reason. `[I]` `42880238` is not
yet an ancestor of the default branch: it sits on the same branch as this ADR,
and becomes one when that branch merges under the repository's merge-commit
convention. `[R]` Should the branch instead be squashed, this declaration
continues to govern the text whose digest is recorded above, which is the
identity that matters; the commit is the locator, the digest is the pin.

**Recorded exactly as ruled:**
`LIFECYCLE_SURFACE=YES LC-1=A LC-2=A LC-3=A LC-4=A LC-5=A`

`[R]` Every answer takes the ballot's recommended path; there is no departure
to record.

**Numbering.** `[R]` This ADR assigns **no** new `OD`, `S2B-*`, `P`, `RCG-D`,
`ACC-S1`, `ACC-AM`, `ACC-FC`, `ACC-IA` or `ACC-PR` number. The composite
fixed-surface ruling is recorded as **`ACC-LC-BASE`** and the five register
rulings as **`ACC-LC-1`** – **`ACC-LC-5`**, all scoped to this ADR, on the
standing precedent of ADR-scoped citability labels; the ballot's own
`LIFECYCLE_SURFACE` and `LC-1` – `LC-5` labels remain the ballot's.

## 2. `ACC-LC-BASE` — the fixed surface

**Ruled: YES**, in the words of the ballot: this is a contract and design act
over policy-version lifecycle only — no new authority, no movement of any
existing authority's bounds; `OD-C4=A` holds untouched (no agent or role
lifecycle authority is taken, implied or prepared for); `OD-C3=B` holds; no
signing key, trust root or approval artifact enters the repository and no
issuance, revocation or supersession is performed; no already-valid artifact is
invalidated and no existing refusal is relaxed; `/clauses/v2` stays out of
scope and `ACC-AM-4`'s re-arm stays untriggered; no agent runs, is enrolled or
is claimed governed.

**Precedence, as the ballot stated it** `[R]`: where an `LC` row and this
surface overlap, the `LC` ruling governs. Recorded because it governs how the
register below is read; no conflict exists in this all-`A` record.

`[R]` **The `OD-C4` boundary is the round's own scope condition**, not a
disclaimer appended to it: "lifecycle" here means the lifecycle of a signed,
versioned, revocable *policy artifact*. A design that needed to touch a role or
an agent to express supersession would be outside this round by construction,
and no ruling below may be read as reaching one.

## 3. `ACC-LC-1` – `ACC-LC-5` — the five-item register

Each ruling is recorded in the words of the option the owner selected.

### `ACC-LC-1` — The successor reference's shape `[R]`

**Ruled: A.** Replace the unstructured `supersedes_ref: str` with a structured
reference binding an exact policy coordinate (`policy_id`, `version`, `scope`,
`tenant_id`), reusing the coordinate type resolution already binds; empty stays
the default and no already-valid artifact is invalidated. `[V]` The ruling
supplies what the authority today refuses for a stated reason: a non-empty
unstructured value "cannot bind a complete exact policy coordinate, and
guessing one would be an unsigned authority decision"
(`packages/policy-authority/src/ugence_policy_authority/core/issuance.py:134-141`).
**Does not settle:** the concrete type's name, module or field order, which
belong to the implementation-authority ruling.

### `ACC-LC-2` — Which act performs supersession `[R]`

**Ruled: A.** The successor declares its predecessor at its own issuance, and
that one signed act both admits the successor and transitions the predecessor
to `SUPERSEDED`; no unsigned edit ever moves a record. `[I]` `SUPERSEDED` is
already an admitted lifecycle state outside `ACTIVE_LIFECYCLE_STATE`
(`agent-constitution-policy/.../identifiers.py:81-97`), so the predecessor
stops resolving through the authority's existing lifecycle refusal and remains
readable as history; no new refusal vocabulary is required.

### `ACC-LC-3` — Whether suspension belongs to this round `[R]`

**Ruled: A.** No — this round settles supersession only; suspension is deferred
to its own round, because a reversible pause needs a state absent from the
ratified closed set `ADMITTED_LIFECYCLE_STATES`, which makes it a vocabulary act
rather than a mechanics act.

`[G]` **The bite, ratified as disclosed:** until that round is convened and
lands, an operator whose approval is questioned but not withdrawn has only the
terminal instrument — revoke and re-issue. This is an accepted cost, not an
oversight. `[V]` No suspension concept exists in any source file of the
authority or the three constitution distributions at this baseline.

### `ACC-LC-4` — Where the mechanics live `[R]`

**Ruled: A.** The shared Policy Authority, family-neutral, beside the issuance,
revocation and resolution it extends; the constitution family and the
activation root gain no new seam and no new public name. `[I]` This keeps the
activation layer's ruled posture intact — it holds no revocation seam
(`agent-constitution-activation/.../composition.py:25`) and gains no
supersession seam.

### `ACC-LC-5` — What this round commits `[R]`

**Ruled: A.** Contract, design and ratification only — documentation, no source
change; the implementation is a separate change set authorized by the ruling
that follows, on the `ACC-FC-5` / `ACC-PR` precedent.

## 4. What remains open

* `[G]` **Everything mechanical.** No structured reference type exists, no act
  transitions a record to `SUPERSEDED`, and `supersedes_ref` remains the
  unstructured string the authority refuses. This ADR closes no gap in the
  source; it settles what the change set must be.
* `[G]` **Suspension**, per `ACC-LC-3`, with the bite recorded above. Its round
  is not convened by this record.
* `[G]` **The `ACC-FC-5` deployment gates** — key custody, approving authority,
  operational composition, reference-map population — stand where `ACC-FC-5`
  left them; supersession mechanics neither close nor advance them.
* `[R]` **`/clauses/v2` remains uncommissioned** and `ACC-AM-4`'s re-derivation
  re-arm stays untriggered.

## 5. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record. No
lifecycle authority over agents or roles exists or is implied (`OD-C4=A`);
nothing here writes or transitions an agent lifecycle state, suspends, revokes
or offboards an agent, or mints, changes or ends a role. Constitution binding
grants no compute, tools, evidence access or consequential execution; digest
membership proves integrity after construction, never provenance; no verifier
emits a disposition or reserved authority term (`OD-C3=B`); conformance replay
proves conformance of presented facts only. No constitution is issued,
superseded, suspended or revoked by virtue of this record, and no signing key,
trust root or approval artifact enters the repository.

## 6. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** The Agentic Proposer remains at `0.4.0`;
Policy Authority at `0.1.0`; all three constitution distributions at `0.1.0`.
The pinned ballot document is unmodified by this ADR: its commit, digest, line
count and ballot block are as recorded in §1.

**Next step after this ADR merges:** the implementation-authority ballot for
this round, as its own document — settling how the structured reference and the
single signed act are built, and authorizing the change set that `ACC-LC-1` –
`ACC-LC-4` scope. Until it is answered and its ruling lands, no source file may
change under this record.
