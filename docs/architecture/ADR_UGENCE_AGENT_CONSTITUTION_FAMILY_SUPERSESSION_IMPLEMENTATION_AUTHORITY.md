# ADR: Ugence Agent Constitution — family supersession opt-in, implementation-authority ruling

**Status:** **Accepted (owner ruling) — documentation only.** This is the ruling
`ACC-SU-5` sequenced after the opt-in's ratification. It **authorizes** a change
set and settles how it is built; it **performs** none of it. No source, test,
`public_api.json`, `version.py`, CHANGELOG, package metadata or CI file is
modified by this document.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `7015dec2` — the merge of PR #1552, which ratified
`ACC-SU-BASE` and `ACC-SU-1` – `ACC-SU-5`.

**Governing record:**
[`ADR_UGENCE_AGENT_CONSTITUTION_FAMILY_SUPERSESSION_OPT_IN_RATIFICATION.md`](ADR_UGENCE_AGENT_CONSTITUTION_FAMILY_SUPERSESSION_OPT_IN_RATIFICATION.md).
`[R]` This ruling refines and may not overrule those rulings; the ballot carried
that precedence rule and it is recorded here unchanged.

## 1. What was ratified, exactly

The ballot put is
[`AGENT_CONSTITUTION_FAMILY_SUPERSESSION_IMPLEMENTATION_AUTHORITY_BALLOT.md`](AGENT_CONSTITUTION_FAMILY_SUPERSESSION_IMPLEMENTATION_AUTHORITY_BALLOT.md)
**as that file stands at commit `7c39c388`**, the commit that authored it:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_FAMILY_SUPERSESSION_IMPLEMENTATION_AUTHORITY_BALLOT.md` |
| Authoring commit | `7c39c388` ("Put the family supersession opt-in implementation-authority ballot") |
| Document SHA-256 | `5b975aad56f3190ffd9df33c58856884e1858c9a6bd453e0010269e7075bf636` |
| Line count | 210 |
| Ballot-block SHA-256 (`## 3.` heading through the `## 4.` heading, inclusive; 67 lines) | `00a7272bcfdc70a4e132b7a12ca6f648595118c3b40f709db8d735e48a310df3` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`SU_IA_SURFACE`, `SU-IA-1` … `SU-IA-5`. `[I]` `7c39c388` sits on the same branch
as this ADR and becomes an ancestor of the default branch when that branch
merges under the repository's merge-commit convention; the digest is the pin, the
commit is the locator.

**Recorded exactly as ruled:**
`SU_IA_SURFACE=YES SU-IA-1=A SU-IA-2=A SU-IA-3=A SU-IA-4=A SU-IA-5=A`

**Numbering.** `[R]` Recorded as **`ACC-SU-IA-BASE`** and **`ACC-SU-IA-1`** –
**`ACC-SU-IA-5`**, ADR-scoped, on the standing precedent. No `OD`, `ACC-S1`,
`ACC-AM`, `ACC-FC`, `ACC-IA`, `ACC-PR`, `ACC-LC` or `ACC-SU` number is assigned
or moved.

## 2. The interpretive ruling this record turns on

`[R]` `SU-IA-4=A` settles the question the ballot raised and could not answer
for itself: **`ACC-SU-4`'s "untouched" means no behavioural change, not no
edited byte.** The two dependent verify scripts may have their
`family.__version__` pin moved `0.1.0` → `0.2.0`; nothing else in those
distributions changes. `ACC-SU-4` is fulfilled, not amended, and no amendment to
the ratification is required.

`[V]` The reading is what the repository forces. `ACC-SU-4` also ruled a minor
bump with `public_api.json` regenerated "if the surface grows", and the surface
does grow — the snapshot records the metadata dataclass's field list and order.
`[V]` Both dependent distributions assert `family.__version__ == "0.1.0"`
(`agent-constitution-conformance/verify_…:105`,
`agent-constitution-activation/verify_…:105`) and both run in CI
(`agent-constitution-ci.yml:121,127`). A bump that left those pins unmoved would
fail CI; refusing the bump would defy `ACC-SU-4`'s own instruction. The literal
reading is unsatisfiable, so the behavioural one governs.

`[R]` **The pins move; they are never deleted or loosened.** A dependent
distribution that stopped pinning the family's version would destroy the
tripwire that produced this ruling — the same discipline `ACC-LC-IA-BASE-A1`
recorded, and for the same reason.

## 3. `ACC-SU-IA-BASE` — the fixed surface

**Ruled: YES**, in the words of the ballot: the authorized change set touches
`agent-constitution-policy` and, per `ACC-SU-IA-4`, two pin lines in the
dependent verify scripts — nothing else. No new authority, and the shipped
supersession mechanism is not reopened; `OD-C4=A` holds untouched; `OD-C3=B`
holds; no signing key, trust root or approval artifact enters the repository and
every proof runs on ephemeral in-process keys; no already-valid artifact is
invalidated, no existing refusal is relaxed and **no existing digest moves**;
suspension is not implemented (`ACC-LC-3`); `/clauses/v2` stays out of scope and
`ACC-AM-4`'s re-arm stays untriggered; no constitution is issued, superseded,
suspended or revoked; no agent runs, is enrolled or is claimed governed.

**Precedence** `[R]`: where a `SU-IA` row and this surface overlap, the row
governs; where either conflicts with an `ACC-SU` ruling, the `ACC-SU` ruling
governs. No conflict survives in this all-`A` record.

## 4. `ACC-SU-IA-1` – `ACC-SU-IA-5` — the five-item register

### `ACC-SU-IA-1` — The field's name and type `[R]`

**Ruled: A.** `supersedes_coordinate: Optional[PolicyCoordinate] = None` on
`AgentConstitutionPolicyMetadata` — the authority's own coordinate type, under
the same name the descriptor uses, so the adapter's mapping is an assignment and
nothing is translated. `[V]` The family already imports `PolicyCoordinate` from
`ugence_policy_authority.api` and builds one in `agent_constitution_coordinate`
(`adapter.py:41,60,75`), so this introduces no new dependency and no parallel
identity notion.

### `ACC-SU-IA-2` — The exclusion and its guard `[R]`

**Ruled: A.** Exclude by name in `_canonical_projection`, beside
`content_digest`, with a comment naming `ACC-SU-2` as the exclusion's authority.
The guard already exists: `[V]` `test_authority_registration.py:181-190` asserts
the projection's metadata key set is **exactly** the eight current names, and
`test_artifact.py:405` pins which fields move the digest.

`[R]` **Both must stay green unedited, and the new field must not be added to
`test_artifact.py:405`'s parametrization.** Editing either is the tell that the
exclusion has been abandoned; a change set that needs to edit them is not the
authorized change set.

### `ACC-SU-IA-3` — The digest-invariance fixture `[R]`

**Ruled: A.** Pin the ratified v1 content's body digest as a **literal** in the
test, computed at implementation time, so any later projection change fails
loudly rather than only this one. `[I]` The literal is a digest of ratified
content — not key material, and nothing the repository's custody bounds refuse.

### `ACC-SU-IA-4` — The version-pin conflict `[R]`

**Ruled: A.** `ACC-SU-4`'s "untouched" is read as *no behavioural change*: the
surface includes the two `family.__version__` pin lines
(`agent-constitution-conformance/verify_…:105`,
`agent-constitution-activation/verify_…:105`), moved `0.1.0` → `0.2.0` and
**moved, never deleted or loosened**. Nothing else in those distributions
changes. See §2.

### `ACC-SU-IA-5` — The change set's file bounds `[R]`

**Ruled: A.** Exactly: `policy.py` (the field), `adapter.py` (map and exclude),
`public_api.json` (regenerated), `version.py` (`0.1.0` → `0.2.0`),
`tests/test_public_api.py` (its own pin), **one** new proof module carrying the
three `ACC-SU-3` legs, `CHANGELOG.md`, and the two dependent pin lines per
`ACC-SU-IA-4`. Nothing else.

## 5. What is authorized, and what is not

**Authorized** `[R]`: exactly the change set §3 bounds and `ACC-SU-IA-5`
enumerates, built as §4 rules. It must satisfy every existing suite and scan as
they stand — including the two guards of `ACC-SU-IA-2`, unedited. A change set
needing a new exemption is not the authorized change set.

**Not authorized** `[R]`: any other file, package or workflow; any relaxation of
the unstructured `supersedes_ref` refusal; any movement of an existing digest;
any suspension mechanism (`ACC-LC-3`); any production issuance, revocation or
supersession; and any touching of a role or an agent (`OD-C4=A`).

**Still open** `[G]`: supersession remains **unexercisable** after this lands —
`ACC-LC-IA-3` refuses an absent predecessor and the `ACC-FC-5` gates are shut;
suspension and its round; `/clauses/v2`.

## 6. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record or
of the authorized change set. No lifecycle authority over agents or roles exists
or is implied (`OD-C4=A`). Constitution binding grants no compute, tools,
evidence access or consequential execution; digest membership proves integrity
after construction, never provenance; no verifier emits a disposition or
reserved authority term (`OD-C3=B`); conformance replay proves conformance of
presented facts only. No constitution is issued, superseded, suspended or
revoked by virtue of this record, and no signing key, trust root or approval
artifact enters the repository.

## 7. What this ADR changed

One new documentation file. No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified. Policy Authority remains at `0.2.0`; all
three constitution distributions remain at `0.1.0` until the authorized change
set lands.

**Next step after this ADR merges:** implement the authorized change set of §5,
exactly as bounded, as its own change.
