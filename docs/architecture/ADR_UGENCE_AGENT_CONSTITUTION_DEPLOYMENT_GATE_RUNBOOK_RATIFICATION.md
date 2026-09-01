# ADR: Ugence Agent Constitution — `ACC-FC-5` deployment-gate runbook, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item deployment-gate runbook
ballot. **No gate is closed by this ADR, no key is minted, no rehearsal is run
and no issuance is performed.** `ACC-FC-5`'s four gates are shut the day this
merges, exactly as they were the day before it.

**Date:** 2026-09-01.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-09-01. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `fa574353` — the merge of PR #1554, which landed the
family's supersession opt-in and closed the last contract gap in this arc.

**What it settles.** `ACC-FC-5` ruled the first issuance a deployment act gated
on four items and expressly **did not settle** *"when or by whom the deployment
gates are closed."* This ADR settles that question as **ordering and
ownership**, not as a calendar.

## 1. What was ratified, exactly

The ballot put is
[`AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_PROPOSAL.md`](AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_PROPOSAL.md)
**as that file stands at commit `91b177fb`**, the commit that authored it:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_PROPOSAL.md` |
| Authoring commit | `91b177fb` ("Propose the ACC-FC-5 deployment-gate runbook") |
| Document SHA-256 | `513b3c8c4cbf13bd9038279b43b72046af0ae53bc50eface65266b5a881cd899` |
| Line count | 228 |
| Ballot-block SHA-256 (`## 4.` heading through the `## 5.` heading, inclusive; 69 lines) | `704e5d828bf5340ee92f7d6332f7012792723b6484a0f9769870f009639193ae` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`FC5_SURFACE`, `FC5-1` … `FC5-5`. `[I]` `91b177fb` sits on the same branch as
this ADR and becomes an ancestor of the default branch when that branch merges
under the repository's merge-commit convention; the digest is the pin, the
commit is the locator.

**Recorded exactly as ruled:**
`FC5_SURFACE=YES FC5-1=A FC5-2=A FC5-3=A FC5-4=A FC5-5=A`

`[R]` Every answer takes the proposal's recommended path; there is no departure
to record. `[V]` The proposal's §5 independent-review prompt had **not** been
run at ruling time; the owner ruled directly. That is recorded as fact, not as
a defect — the prompt asked a reviewer to attack two specific claims (that gate
4 is strictly downstream of issuance, and that `FC5-4`'s permitted values leak
nothing), and it remains available to anyone auditing this record.

**Numbering.** `[R]` Recorded as **`ACC-FC5R-BASE`** and **`ACC-FC5R-1`** –
**`ACC-FC5R-5`**, ADR-scoped, on the standing precedent. **No `ACC-FC` number
is assigned, moved or amended** — `ACC-FC-5` itself is untouched; this ADR
answers the question it left open without reopening the ruling.

## 2. `ACC-FC5R-BASE` — the fixed surface

**Ruled: YES**, in the words of the ballot: a documentation and planning act.
**No signing key, trust root or approval artifact enters this repository under
any option on any row**, and no value from which one could be reconstructed; no
gate is closed, no rehearsal is run, and no issuance, revocation or supersession
is performed; `OD-C4=A` holds untouched and no agent runs, is enrolled or is
claimed governed; `OD-C3=B` holds; no existing artifact is invalidated, no
refusal relaxed and no digest moved; suspension stays unimplemented
(`ACC-LC-3`); `/clauses/v2` stays out of scope and `ACC-AM-4`'s re-arm stays
untriggered; **no date binds anyone**.

**Precedence** `[R]`: where an `FC5` row and this surface overlap, the row
governs. No conflict exists in this all-`A` record.

## 3. `ACC-FC5R-1` – `ACC-FC5R-5` — the five-item register

### `ACC-FC5R-1` — Who closes each gate, in what order `[R]`

**Ruled: A.** The order the code forces: gates **1 and 2 in parallel**
(signing-key custody; an approving authority), then **3** (composition, which
needs both already constructed), then the **rehearsal** of `ACC-FC5R-3`, then
the first issuance, then **4** (reference-map population). Each gate names a
responsible **role** — custodian, approving authority, deploying operator — not
a person.

`[V]` **The ordering is forced, not chosen.** `populate_reference_map` derives
entries *"from one issued record"*
(`agent-constitution-activation/.../reference_map.py:45-59`), so gate 4 cannot
precede the first issuance: there is nothing to derive from until gates 1–3 have
produced a record. `[V]` Gates 1 and 2 are the only ones no repository artifact
can advance — the activation source cannot mint or read key material by ruling
(`tests/test_import_boundary.py:6-10`), and the shipped approval verifier denies
by default (`policy-authority/core/approval.py:160-164`).

### `ACC-FC5R-2` — What evidence each gate produces, and where `[R]`

**Ruled: A.** Each closure produces a **non-secret attestation**: gate name,
date, responsible role, and the public identifiers the act already exposes
(`key_id`, issuing and approving authority ids, `approval_ref`, `record_id`, the
issued coordinate), recorded in the **operational log outside this repository**.
What may enter the repository is settled by `ACC-FC5R-4`.

### `ACC-FC5R-3` — The rehearsal `[R]`

**Ruled: A.** **Mandatory.** Before any custody key signs, the target deployment
must run the full chain — preflight → issue → activate → resolve → bind →
conform — on **ephemeral in-process keys**, and the four-way fail-closed matrix
must refuse as specified.

`[V]` The instrument exists and the ratified gate list does not name it:
`preflight_issuance` *"runs every pre-signing check and report; sign nothing,
store nothing"* (`agent-constitution-activation/.../preflight.py:111`). It is
the only way to exercise gates 2 and 3 in a real deployment **before** a custody
key signs anything, which is what makes this requirement practicable rather
than aspirational.

### `ACC-FC5R-4` — What the repository may hold about a closed gate `[R]`

**Ruled: A.** **Non-secret facts only**: gate name, closure date, responsible
role, and public identifiers and digests — **never** key material, a trust root,
approval-artifact bytes, or any value from which they could be reconstructed. A
closure is recorded as a one-line ADR fact naming **where** the evidence is
held, never the evidence itself.

`[R]` **This row is the one that cannot be undone.** A secret committed once is
committed in history; the permitted set is therefore exhaustive, not
illustrative, and anything not named in it is refused. `[G]` The adversarial
read of that permitted set — whether any listed identifier or digest could
reconstruct key material, a trust root or approval evidence — was put to an
independent reviewer in the proposal's §5 and **has not been run**. Recorded as
an open check, not as a settled one.

### `ACC-FC5R-5` — What this round commits `[R]`

**Ruled: A.** The runbook and its ratification only. No gate is closed, no
rehearsal run, no issuance performed, and **no date fixed**; the first issuance
remains a separate act under a separate record.

`[G]` **The bite, ratified as disclosed:** this removes the excuse of not
knowing how, and nothing else.

## 4. What remains open

* `[G]` **All four gates are shut**, exactly as before this ADR. Closing them is
  operational work by the roles `ACC-FC5R-1` names; no repository file can
  perform it, and this ADR schedules nothing.
* `[G]` **Supersession, activation and conformance stay unexercisable** until
  the gates close — `ACC-LC-IA-3` refuses an absent predecessor, and no
  constitution has been issued.
* `[G]` **The `FC5-4` leak review is unrun**, per §3.
* `[G]` **Suspension** and its round remain uncommissioned (`ACC-LC-3`).
* `[R]` **`/clauses/v2` remains uncommissioned** and `ACC-AM-4`'s re-arm stays
  untriggered.

## 5. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record. No
lifecycle authority over agents or roles exists or is implied (`OD-C4=A`).
Constitution binding grants no compute, tools, evidence access or consequential
execution; digest membership proves integrity after construction, never
provenance; no verifier emits a disposition or reserved authority term
(`OD-C3=B`); conformance replay proves conformance of presented facts only. No
constitution exists, is issued, superseded, suspended or revoked by virtue of
this record, and no signing key, trust root or approval artifact enters the
repository.

## 6. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** Policy Authority remains at `0.2.0`;
`agent-constitution-policy` at `0.2.0`; conformance and activation at `0.1.0`.
The pinned proposal is unmodified by this ADR: its commit, digest, line count
and ballot block are as recorded in §1.

**Next step after this ADR merges:** none in this repository's files. The gates
are closed by the roles `ACC-FC5R-1` names, in the order it fixes, and that is
operational work — the same answer `ACC-FC-5` gave, now with an owner, an order,
an evidence definition and a mandatory rehearsal attached to it.
