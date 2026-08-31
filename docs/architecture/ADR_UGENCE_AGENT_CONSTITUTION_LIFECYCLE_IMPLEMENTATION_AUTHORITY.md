# ADR: Ugence Agent Constitution — lifecycle round, implementation-authority ruling

**Status:** **Accepted (owner ruling) — documentation only.** This is the ruling
`ACC-LC-5` sequenced after the lifecycle round's ratification. It **authorizes**
a change set and settles how it is built; it **performs** none of it. No source,
test, `public_api.json`, `version.py`, CHANGELOG, package metadata or CI file is
modified by this document, and no issuance, revocation or supersession occurs by
virtue of it.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `69642cfc` — the merge of PR #1545, which landed the
lifecycle round's scoping ballot and its ratification.

**Governing record:**
[`ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_ROUND_RATIFICATION.md`](ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_ROUND_RATIFICATION.md)
(`ACC-LC-BASE`, `ACC-LC-1` – `ACC-LC-5`). `[R]` This ruling refines and may not
overrule those rulings; the ballot carried that precedence rule, and it is
recorded here unchanged.

## 1. What was ratified, exactly

The ballot put is
[`AGENT_CONSTITUTION_LIFECYCLE_IMPLEMENTATION_AUTHORITY_BALLOT.md`](AGENT_CONSTITUTION_LIFECYCLE_IMPLEMENTATION_AUTHORITY_BALLOT.md)
**as that file stands at commit `e43cf4f7`**, the commit that authored it:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_LIFECYCLE_IMPLEMENTATION_AUTHORITY_BALLOT.md` |
| Authoring commit | `e43cf4f7` ("Put the lifecycle round's implementation-authority ballot") |
| Document SHA-256 | `3b196f9a973533b7120d3005e92d82eace120b83280262dddfc06a682643d6e3` |
| Line count | 219 |
| Ballot-block SHA-256 (`## 3.` heading through the `## 4.` heading, inclusive; 76 lines) | `c0589dfdd07001eae20906d5cdd4211e5b9b427a71c6b6b3800ba8011200f4c3` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`LC_IA_SURFACE`, `LC-IA-1` … `LC-IA-5`. `[I]` `e43cf4f7` sits on the same branch
as this ADR and becomes an ancestor of the default branch when that branch
merges under the repository's merge-commit convention; the digest above is the
pin, the commit is the locator.

**Recorded exactly as ruled:**
`LC_IA_SURFACE=YES LC-IA-1=A LC-IA-2=A LC-IA-3=A LC-IA-4=A LC-IA-5=A`

**Numbering.** `[R]` Recorded as **`ACC-LC-IA-BASE`** and **`ACC-LC-IA-1`** –
**`ACC-LC-IA-5`**, ADR-scoped, on the standing precedent. No `OD`, `ACC-S1`,
`ACC-AM`, `ACC-FC`, `ACC-IA`, `ACC-PR` or `ACC-LC` number is assigned or moved.

## 2. The interpretive ruling this record turns on

`[R]` `LC-IA-1=A` settles a question the ballot raised and could not answer for
itself: **`ACC-LC-1`'s parenthetical "(`policy_id`, `version`, `scope`,
`tenant_id`)" is illustrative, not binding.** Its operative phrase is *"a
structured reference binding an exact policy coordinate"*, and the exact
coordinate this repository defines has six components. The owner has ruled that
reading; `ACC-LC-1` is fulfilled, not amended, and no amendment to the
ratification is required.

`[V]` The reading is what the repository forces: `PolicyCoordinate` is *"the
complete, exact, family-neutral identity of one policy version … every component
participates in identity, so an exact-match lookup is the only lookup the
registry can perform"* (`core/adapters.py:64-76`), and the registry offers
*"exact coordinate resolution only — there is no `latest()`, `current()` or
`find_by_id()`"* (`core/registry.py:10-20`). A four-field reference is
unresolvable by any lookup that exists, so the literal reading would have
required inventing a search capability — widening the authority `ACC-LC-4`
placed the work inside.

`[R]` The same logic governs `ACC-LC-2`'s "transitions the predecessor to
`SUPERSEDED`": `[V]` issued records are *"immutable and cannot be overwritten"*
in an append-only store (`core/registry.py:112-121`) and `lifecycle_state` is
signed artifact content, so the ruling's intent — one signed act, no unsigned
edit — is honoured by an **append**, exactly as revocation already is, and not
by an edit that the registry would refuse.

## 3. `ACC-LC-IA-BASE` — the fixed surface

**Ruled: YES**, in the words of the ballot: the authorized change set touches
the **shared Policy Authority only** — a structured successor reference, the
step-4 admissibility checks, the supersession act and its store, the resolution
consultation, the proof module, `public_api.json`, the version and the
CHANGELOG, and nothing else. No agent or role lifecycle authority is taken,
implied or prepared for (`OD-C4=A`); no disposition or reserved authority term
is emitted (`OD-C3=B`); no signing key, trust root or approval artifact enters
the repository and every proof runs on ephemeral in-process keys; no
already-valid artifact is invalidated and no existing refusal is relaxed — a
non-empty **unstructured** value keeps being refused exactly as today;
suspension is not implemented (`ACC-LC-3`); `/clauses/v2` stays out of scope and
`ACC-AM-4`'s re-arm stays untriggered; no constitution is issued, superseded,
suspended or revoked by any act of this repository, and no agent runs, is
enrolled or is claimed governed.

**Precedence** `[R]`: where an `LC-IA` row and this surface overlap, the row
governs; where either conflicts with an `ACC-LC` ruling, the `ACC-LC` ruling
governs. No conflict exists in this all-`A` record.

## 4. `ACC-LC-IA-1` – `ACC-LC-IA-5` — the five-item register

Each ruling is recorded in the words of the option the owner selected.

### `ACC-LC-IA-1` — The successor reference's field set `[R]`

**Ruled: A.** The full six-field `PolicyCoordinate` (`policy_family`,
`policy_id`, `version`, `content_digest`, `scope`, `tenant_id`), reused as-is —
the only shape the registry can resolve, since exact-match lookup is the only
lookup it performs. `[G]` **The bite, ratified as disclosed:** a successor's
author must know the predecessor's `content_digest` to name it. Accepted
deliberately — it is what makes the reference bind exact bytes rather than a
mutable notion of "version 1.0.0", and the digest is already carried on every
issuance receipt.

### `ACC-LC-IA-2` — How supersession is recorded `[R]`

**Ruled: A.** A third append-only store of signed supersession records, on
revocation's exact precedent; each names predecessor and successor coordinates,
and resolution consults it and denies the predecessor with its own typed
supersession reason. Issued records stay immutable and are never edited.

### `ACC-LC-IA-3` — Whether issuance verifies the predecessor `[R]`

**Ruled: A.** Yes — at step 4 the predecessor must exist and be resolvable at
the issuance instant; absent, revoked, already-superseded, wrong-tenant,
wrong-scope and self-referential predecessors are refused before signing.
`[I]` Step 4 gains a registry **read**. `[R]` The invariant that governs is
unchanged and must remain provable: **nothing from a rejected artifact is
stored**. The module comment's narrower "before any registry access" phrasing
describes the old step order and is to be updated to say what is actually
guaranteed, not deleted.

### `ACC-LC-IA-4` — The proof obligations `[R]`

**Ruled: A.** The full fail-closed matrix as its own test module — the six
refusals of `ACC-LC-IA-3`, the preserved refusal of the unstructured string, the
predecessor ceasing to resolve after supersession while remaining readable, and
one happy-path chain issuing a v2 over the ratified v1 on ephemeral keys.

### `ACC-LC-IA-5` — Packaging and versioning `[R]`

**Ruled: A.** Policy Authority **minor version bump** with `public_api.json`
regenerated for the new public names, plus a CHANGELOG entry; the constitution
family, the conformance distribution and the activation root are **untouched** —
no new seam, no new public name, no version move (`ACC-LC-4`).

## 5. What is authorized, and what is not

**Authorized** `[R]`: exactly the change set §3 bounds, built as §4 rules, in
the shared Policy Authority. It must satisfy that distribution's existing suite
and every repository-wide scan as they stand; a change set needing a new
exemption is not the authorized change set.

**Not authorized** `[R]`: any other file, package, distribution or workflow;
any relaxation of the unstructured-value refusal; any suspension mechanism
(`ACC-LC-3`); any production issuance, revocation or supersession; and any
touching of a role or an agent (`OD-C4=A`).

**Still open** `[G]`: suspension and its round; the `ACC-FC-5` deployment gates,
which supersession mechanics neither close nor advance; `/clauses/v2`.

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
platform-freeze artifact is modified. Policy Authority remains at `0.1.0` with
66 authorized public names until the authorized change set lands.

**Next step after this ADR merges:** implement the authorized change set of §5,
exactly as bounded, as its own change.
