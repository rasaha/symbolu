# ADR: Ugence Agent Constitution — `ACC-FC5R-4` leak-review amendment

**Status:** **Accepted (owner ruling) — amendment, documentation only.** This
ADR narrows the permitted set of
[`ADR_UGENCE_AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_RATIFICATION.md`](ADR_UGENCE_AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_RATIFICATION.md)'s
`ACC-FC5R-4`. It changes **nothing else**: `ACC-FC5R-BASE`, `ACC-FC5R-1`,
`ACC-FC5R-2`, `ACC-FC5R-3` and `ACC-FC5R-5` stand exactly as ruled, and **all
four `ACC-FC-5` gates remain shut**. No gate is closed, no key minted, no
rehearsal run and no issuance performed.

**Date:** 2026-09-01.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-09-01. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `f100c12c`.

**Numbering.** `[R]` Recorded as **`ACC-FC5R-4-A1`** and **`ACC-FC5R-4-A2`**,
ADR-scoped, on the standing precedent of `ACC-LC-IA-BASE-A1`. Two labels rather
than one because the rows settle different things: what the permitted set *is*,
and whether the exclusion admits any exception. No other register item is
created and no existing number moves.

## 1. What was ratified, exactly

The ballot put is §4 of
[`AGENT_CONSTITUTION_FC5_4_LEAK_REVIEW.md`](AGENT_CONSTITUTION_FC5_4_LEAK_REVIEW.md)
**as that file stands at commit `a238a805`**, the commit that authored it:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_FC5_4_LEAK_REVIEW.md` |
| Authoring commit | `a238a805` ("Run the ACC-FC5R-4 leak review: one material finding") |
| Document SHA-256 | `becff9cb9f9220782bcc0fcae9a3fc561e0b63f5bb1d71c2daebce2fcde36eb7` |
| Line count | 155 |
| Ballot-block SHA-256 (`## 4.` heading through the `## 5.` heading, inclusive; 36 lines) | `2108dbabef9f2b14333ce933d3cc8a83854f4885f6ae135d7dad1fbd7338ad67` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical, and both rows `LR-1` and `LR-2` are present.

**Recorded exactly as ruled:** `LR-1=A LR-2=A`

## 2. `ACC-FC5R-4-A1` — the amended permitted set `[R]`

**Ruled: A.** `ACC-FC5R-4`'s *"public identifiers and digests"* is replaced by
an explicit list. What the repository may hold about a **closed gate** is
exactly:

1. the **gate name**;
2. the **closure date**;
3. the **responsible role** (a role, never a person);
4. `key_id`;
5. the **issuing** authority id;
6. the **approving** authority id;
7. `approval_ref`;
8. `record_id`;
9. the **issued coordinate**, *including* its `content_digest`.

**`approval_digest` is excluded by name, and so is any digest of an
approval artifact by whatever name it is carried.**

`[R]` **The list is exhaustive, not illustrative: anything not named above is
refused.** `[R]` This amendment is **stricter, never looser** — it removes a
value the ratified text admitted and adds none. Every prohibition
`ACC-FC5R-4` already carried stands unchanged: no key material, no trust root,
no approval-artifact bytes, and no value from which any of them could be
reconstructed; a closure is still recorded as a one-line fact naming **where**
the evidence is held, never the evidence itself.

### The ground

`[R]` **A digest is one-way only when its preimage is unguessable.** That is
the whole of the reasoning, and it sorts the two digests in the ratified text in
opposite directions:

* `[V]` The issued coordinate's **`content_digest`** stays admitted. Its
  preimage is the canonical projection of **ratified, public** constitution
  content, so an adversary who confirms it learns nothing that ratification has
  not already published.
* `[V]` The **`approval_digest`** is excluded. Its preimage is an *externally
  produced approval artifact's bytes* — a structured governance record drawn
  from a small space. Committing it publishes a **confirmation oracle**: anyone
  able to enumerate plausible artifacts learns with certainty which is real.
  That is reconstruction of approval evidence, and version control makes it
  permanent and retroactive.

`[I]` The two values are both sha-256. Treating them alike would have been a
rule about *hashing*; the rule is about **preimages**.

## 3. `ACC-FC5R-4-A2` — the exclusion is absolute `[R]`

**Ruled: A.** No approval-artifact digest enters the repository, **whatever
entropy the artifact is claimed to carry**. Two reasons, both recorded:

* `[R]` **An entropy claim cannot be checked from inside this repository.** The
  artifact is external by construction — `ACC-IA-2`'s custody bound means the
  source cannot read it — so an "attested high-entropy nonce" would be an
  assertion the repository must take on trust, in exactly the place where taking
  something on trust is the failure being prevented.
* `[V]` **The value serves no purpose `ACC-FC5R-2` names.** That ruling's
  attestation list — gate name, date, responsible role, `key_id`, the two
  authority ids, `approval_ref`, `record_id`, the issued coordinate — does not
  include `approval_digest`. Excluding it costs the runbook nothing it was
  relying on.

## 4. The open check `ACC-FC5R-4` recorded

`ACC-FC5R-4` recorded a `[G]`: *"The adversarial read of that permitted set …
was put to an independent reviewer in the proposal's §5 and **has not been
run**. Recorded as an open check, not a settled one."*

`[R]` **That check has now been run, and this amendment is its outcome.** The
review is `AGENT_CONSTITUTION_FC5_4_LEAK_REVIEW.md`, pinned in §1; it walked all
seven permitted values, found one material finding, and stated what it did *not*
find — that nothing in the set exposes key material or a trust root. The `[G]`
is **closed**.

`[G]` **What remains open, honestly.** The review's own §5 prompt — an
*independent* read of the review, asking a reviewer to argue that a sha-256 is
safe regardless of preimage, and to hunt for values or multi-value combinations
the review missed — **has not been run**. The finding is first-party. A second
opinion would strengthen it and could still widen it; nothing here should be
read as a claim that the permitted set has been adversarially cleared by an
independent party.

## 5. Nothing recorded under the wider rule

`[V]` **No historical record needs revisiting.** No `ACC-FC-5` gate has been
closed, no closure has been recorded, and **no approval-digest *value* has been
recorded anywhere** in `docs/` — a search for a 64-hex value carried as an
approval digest returns nothing. `[I]` The token `approval_digest` does appear in
three unrelated design documents, but only as a **field name** in a list of an
artifact's fields, never as a value; those are descriptions of a shape, not
records of a closure, and nothing in them is touched by this amendment. The
defect existed only in a rule that had never been
exercised, so this amendment leaves no prior record to correct or redact — which
is the whole reason `ACC-FC5R-4` flagged itself as the row that cannot be undone,
and the reason fixing it now cost nothing.

## 6. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record. No
lifecycle authority over agents or roles exists or is implied (`OD-C4=A`);
`OD-C3=B` holds — no verifier emits a disposition or reserved authority term.
Constitution binding grants no compute, tools, evidence access or consequential
execution; digest membership proves integrity after construction, never
provenance; conformance replay proves conformance of presented facts only. No
constitution exists, is issued, superseded, suspended or revoked by virtue of
this record, and **no signing key, trust root or approval artifact enters the
repository**. Suspension stays unimplemented and its round uncommissioned
(`ACC-LC-3`); `/clauses/v2` stays out of scope and `ACC-AM-4`'s re-arm stays
untriggered.

## 7. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** `ACC-FC5R-4` is amended in the single
respect §2 and §3 state; `ACC-FC5R-BASE`, `ACC-FC5R-1`, `ACC-FC5R-2`,
`ACC-FC5R-3` and `ACC-FC5R-5` are untouched, and **all four `ACC-FC-5` gates
remain shut**. The pinned leak review is unmodified: its commit, digest, line
count and ballot block are as recorded in §1.

**Next step after this ADR merges:** none forced by it. The gates are closed by
the roles `ACC-FC5R-1` names, in the order it fixes, and any closure recorded
thereafter is governed by the narrowed set above.
