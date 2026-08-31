# ADR: Ugence Agent Constitution — family supersession opt-in, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item family supersession opt-in
scoping ballot. **No implementation is authorized by this ADR**, and none is
performed: no field is added, no adapter changes, no projection moves, and
`ACC-SU-5` below sequences the implementation as a separate change set under a
separate ruling. No constitution is issued, superseded or revoked by virtue of
this record.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `9c981dd9`, at or after `9c616ac9` — the merge of PR
#1547, which shipped structured supersession in Policy Authority `0.2.0`.

## 1. What was ratified, exactly

The ballot put is
[`AGENT_CONSTITUTION_FAMILY_SUPERSESSION_OPT_IN_SCOPING_BALLOT.md`](AGENT_CONSTITUTION_FAMILY_SUPERSESSION_OPT_IN_SCOPING_BALLOT.md)
**as that file stands at commit `3b7106d5`**, the commit that authored it:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_FAMILY_SUPERSESSION_OPT_IN_SCOPING_BALLOT.md` |
| Authoring commit | `3b7106d5` ("Put the Agent Constitution family's supersession opt-in scoping ballot") |
| Document SHA-256 | `6c67770e0fdad3f462c77ca314f8061bca2cfdc03f11b966f69f89adf54db1f7` |
| Line count | 232 |
| Ballot-block SHA-256 (`## 4.` heading through the `## 5.` heading, inclusive; 69 lines) | `a44e069e5a53000662b73382f485d3bddb0bcc84369cb9c2aa33a73bd7ae36f1` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`AC_SU_SURFACE`, `AC-SU-1` … `AC-SU-5`. `[R]` The authoring commit is the
citation of record, on the precedent `ACC-FC`, `ACC-PR` and `ACC-LC` follow;
`[I]` it sits on the same branch as this ADR and becomes an ancestor of the
default branch when that branch merges under the repository's merge-commit
convention. The digest is the pin; the commit is the locator.

**Recorded exactly as ruled:**
`AC_SU_SURFACE=YES AC-SU-1=A AC-SU-2=A AC-SU-3=A AC-SU-4=A AC-SU-5=A`

`[R]` Every answer takes the ballot's recommended path; there is no departure to
record. `[V]` The ballot's §5 independent-review prompt **had not been run at
ruling time**; the owner ruled directly, in the same session that drafted the
ballot. That is recorded as fact, not as a defect: review was offered — the
ballot's §6 named `AC-SU-2` as the row where being wrong is expensive, and §5
asks a reviewer to argue *against* the recommendation — and it remains available
to anyone auditing this record against the repository.

**Numbering.** `[R]` This ADR assigns **no** new `OD`, `S2B-*`, `P`, `RCG-D`,
`ACC-S1`, `ACC-AM`, `ACC-FC`, `ACC-IA`, `ACC-PR` or `ACC-LC` number. The
composite fixed-surface ruling is recorded as **`ACC-SU-BASE`** and the five
register rulings as **`ACC-SU-1`** – **`ACC-SU-5`**, all scoped to this ADR, on
the standing precedent of ADR-scoped citability labels; the ballot's own
`AC_SU_SURFACE` and `AC-SU-1` – `AC-SU-5` labels remain the ballot's.

## 2. `ACC-SU-BASE` — the fixed surface

**Ruled: YES**, in the words of the ballot: a contract and design act over one
family's artifact shape — no new authority, and the shipped supersession
mechanism is not reopened on the recommended path; `OD-C4=A` holds untouched (no
agent or role lifecycle authority is taken, implied or prepared for); `OD-C3=B`
holds; no signing key, trust root or approval artifact enters the repository and
no issuance, revocation or supersession is performed; no existing artifact is
invalidated and no existing refusal is relaxed — the unstructured
`supersedes_ref` keeps being refused; no agent runs, is enrolled or is claimed
governed; suspension stays unimplemented and its round uncommissioned
(`ACC-LC-3`); `/clauses/v2` stays out of scope and `ACC-AM-4`'s re-arm stays
untriggered.

**Precedence, as the ballot stated it** `[R]`: where an `AC-SU` row and this
surface overlap, the row governs. No conflict exists in this all-`A` record.

## 3. `ACC-SU-1` – `ACC-SU-5` — the five-item register

Each ruling is recorded in the words of the option the owner selected.

### `ACC-SU-1` — Where the structured predecessor lives `[R]`

**Ruled: A.** A new field on `AgentConstitutionPolicyMetadata` carrying the
exact predecessor coordinate, which the adapter maps into the descriptor's
`supersedes_coordinate`. The artifact states what it replaces. `[I]` This keeps
the shipped mechanism untouched: the authority already takes its predecessor
from the descriptor (`ACC-LC-IA-1`), so the family opts in by *producing* what
the authority already consumes. **Does not settle:** the field's name, type or
position, which belong to the implementation-authority ruling.

### `ACC-SU-2` — Whether the ratified v1 identity moves `[R]`

**Ruled: A.** No — the new field is excluded from the canonical projection, on
the same ground `content_digest` is: what a version replaces is a claim about
the registry, not part of the bytes it is identified by. Every existing digest,
the ratified v1 content's included, is unmoved and `ACC-FC-2` is untouched.

`[V]` The exclusion is load-bearing, not cosmetic: the family's canonical
projection removes *exactly* `metadata.content_digest`
(`agent-constitution-policy/.../adapter.py:153`), so every other metadata field
is inside the body digest — measured at this baseline, the digested metadata
keys are `effective_from`, `effective_to`, `lifecycle_state`, `policy_id`,
`scope`, `supersedes_ref`, `tenant_id`, `version`, and adding one further key
changes the digested bytes. Without the exclusion this round would silently move
a ratified identity value.

`[G]` **The consequence, ratified as disclosed:** a constitution's claim about
what it supersedes is then **not** covered by that artifact's own signature. The
claim is instead carried by the signed `PolicySupersessionRecord` the authority
writes (`ACC-LC-IA-2`), which is where an auditor must look for it. The
implementation must not be read as making the artifact self-attest its
predecessor.

### `ACC-SU-3` — Proof scope `[R]`

**Ruled: A.** Three legs: a **digest-invariance** proof that the ratified v1
content's body digest is byte-identical before and after the change; a
v2-supersedes-v1 chain driven through the shipped authority on ephemeral
in-process keys; and the six `ACC-LC-IA-3` refusals re-driven over this family.
`[I]` The invariance leg is what makes `ACC-SU-2` checkable rather than merely
asserted.

### `ACC-SU-4` — Which distributions and versions move `[R]`

**Ruled: A.** `agent-constitution-policy` only — minor bump, `public_api.json`
regenerated if the surface grows, CHANGELOG note; the conformance and activation
distributions and the Policy Authority are **untouched**. `[R]` The
implementation-authority ballot **must first enumerate every consumer** of this
family's artifact shape and closed vocabularies, harnesses included
(`ACC-LC-IA-BASE-A1`). That is an obligation on the next ballot, not advice: the
last round's surface was unsatisfiable because it was bounded without that
enumeration.

### `ACC-SU-5` — What this round commits `[R]`

**Ruled: A.** Contract, design and ratification only — documentation, no source
change; the implementation is a separate change set under the ruling that
follows.

## 4. What remains open

* `[G]` **Everything mechanical.** No field exists, no adapter produces
  `supersedes_coordinate`, and no shipped family can declare a predecessor. This
  ADR closes no gap in the source; it settles what the change set must be.
* `[G]` **Supersession stays unexercisable even after the opt-in lands.**
  `ACC-LC-IA-3` refuses an absent predecessor, and no constitution has been
  issued, because the `ACC-FC-5` deployment gates — key custody, approving
  authority, operational composition, reference-map population — are still shut.
  This round closes a contract gap, not an operational one.
* `[G]` **Suspension** and its round remain uncommissioned (`ACC-LC-3`), with
  the cost recorded there.
* `[R]` **`/clauses/v2` remains uncommissioned** and `ACC-AM-4`'s re-derivation
  re-arm stays untriggered.

## 5. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record. No
lifecycle authority over agents or roles exists or is implied (`OD-C4=A`);
nothing here writes or transitions an agent lifecycle state, or mints, changes
or ends a role. Constitution binding grants no compute, tools, evidence access
or consequential execution; digest membership proves integrity after
construction, never provenance; no verifier emits a disposition or reserved
authority term (`OD-C3=B`); conformance replay proves conformance of presented
facts only. No constitution is issued, superseded, suspended or revoked by
virtue of this record, and no signing key, trust root or approval artifact
enters the repository.

## 6. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** Policy Authority remains at `0.2.0`; all
three constitution distributions remain at `0.1.0`, the family exposing 27
public names. The pinned ballot document is unmodified by this ADR: its commit,
digest, line count and ballot block are as recorded in §1.

**Next step after this ADR merges:** the implementation-authority ballot for
this round, as its own document — settling the field's name, type and position,
the projection exclusion's exact mechanism, and the change set's bounds, and
opening with the consumer enumeration `ACC-SU-4` requires. Until it is answered
and its ruling lands, no source file may change under this record.
