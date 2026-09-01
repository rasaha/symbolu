# ADR: Ugence Agent Constitution — `/clauses/v2` round, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item `/clauses/v2` scoping
ballot. **The round is ruled *not yet* (`ACC-CV2-1`), no clause content is
ratified, and `ACC-AM-4` is NOT re-armed by this record** — the re-arm is
triggered only by a later ruling that actually ratifies clause content beyond the
three structural bounds.

**Date:** 2026-09-01.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-09-01. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `e84941a8`.

## 1. What was ratified, exactly

The ballot put is
[`AGENT_CONSTITUTION_CLAUSES_V2_ROUND_SCOPING_BALLOT.md`](AGENT_CONSTITUTION_CLAUSES_V2_ROUND_SCOPING_BALLOT.md)
**as that file stands at commit `b8359bc7`**, the commit that authored it:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_CLAUSES_V2_ROUND_SCOPING_BALLOT.md` |
| Authoring commit | `b8359bc7` ("Commission the two deferred rounds: suspension and /clauses/v2 scoping ballots") |
| Document SHA-256 | `78fa4514d9e717aaff5fc1bbdd837b366818d855933bdbd8b0af838ef88b4b65` |
| Line count | 191 |
| Ballot-block SHA-256 (`## 3.` heading through the `## 4.` heading, inclusive; 62 lines) | `acf5352d827c4ce583b67a464edf336cbbccedee98d4adec3489210236b6618d` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical, and all six rows are present.

**Recorded exactly as ruled:**
`CV2_SURFACE=YES CV2-1=A CV2-2=A CV2-3=A CV2-4=A CV2-5=A`

`[R]` Every answer takes the ballot's recommended path. `[V]` The ballot's §4
independent-review prompt — which asks a reviewer to argue the strongest case
**against** the deferral — had **not** been run at ruling time; the owner ruled
directly. Recorded as fact, not defect.

**Numbering.** `[R]` Recorded as **`ACC-CV2-BASE`** and **`ACC-CV2-1`** –
**`ACC-CV2-5`**, ADR-scoped, on the standing precedent. No other register number
is assigned or moved.

## 2. `ACC-CV2-BASE` — the fixed surface

**Ruled: YES**, in the words of the ballot: a scoping act. **No clause content is
ratified and `ACC-AM-4` is not re-armed by this document or by any answer to
it.** No constitution is authored, issued, superseded, suspended or revoked;
`OD-C4=A` and `OD-C3=B` hold; no signing key, trust root or approval artifact
enters the repository; no already-valid artifact is invalidated, no existing
refusal relaxed and no existing digest moved — **in particular v1's ratified
content and digest are untouched**; suspension stays unimplemented (`ACC-LC-3`,
now designed under `ACC-SUSP-*` but not built); the `ACC-FC-5` gates are neither
closed nor advanced; no agent runs, is enrolled or is claimed governed.

**Precedence** `[R]`: where a `CV2` row and this surface overlap, the row
governs. No conflict exists in this all-`A` record.

## 3. `ACC-CV2-1` – `ACC-CV2-5` — the five-item register

### `ACC-CV2-1` — Not yet `[R]`

**Ruled: A.** The round is **not commissioned now**. It is deferred until at
least one `ACC-FC-5` gate is closed.

`[R]` The ground, recorded: every capability this arc built is unexercisable, and
clause content is the one addition that would **also re-arm `ACC-AM-4`** and so
commit a second round on top of it. `[V]` `ACC-AM-4` is *"not discharged"* and
*"re-arms the first time clause content beyond the three structural bounds is
ratified, at which point re-derivation gets its own round."*

`[G]` **The bite, ratified as disclosed:** this leaves the constitution at three
structural bounds indefinitely. If clause content is what makes a constitution
*useful* rather than merely well-formed, deferring postpones the substance and
not merely the work. That is an accepted cost, not an oversight.

`[R]` **What `ACC-CV2-2`..`ACC-CV2-5` therefore are.** They are **pre-settled for
whenever the round is convened**, not immediately operative. The round arrives
with its shape already decided; nothing in them authorises or schedules anything.

### `ACC-CV2-2` — A v2 is authored as a successor to v1 `[R]`

**Ruled: A.** When convened, a v2 declares `supersedes_coordinate` naming v1's
exact coordinate — the first genuine use of the `ACC-LC` / `ACC-SU` machinery.

`[G]` **Disclosed and accepted:** this pins v1's `content_digest` permanently. A
later change to v1's ratified content would orphan the successor's reference.

### `ACC-CV2-3` — Re-derivation is sequenced first `[R]`

**Ruled: A.** The `ACC-AM-4` re-derivation round is scoped and ruled **before**
clause content is ratified, so the proposer's projection field set is settled
against content that is *proposed*, never retrofitted to content already
ratified.

### `ACC-CV2-4` — What counts as clause content `[R]`

**Ruled: A.** Ruled explicitly rather than left to argument: **any constitution
field that is not one of the three structural bounds, the identity fields, or the
governed-role references.** `[R]` The `ACC-AM-4` re-arm is mechanical once this
definition is written down, which is the point of writing it down now.

### `ACC-CV2-5` — What this round commits `[R]`

**Ruled: A.** Scoping only. Answering commissions nothing; a later decision to
convene would still require a further content ballot before any clause text is
ratified.

## 4. What remains open

* `[R]` **The round itself**, deferred by `ACC-CV2-1` with a condition rather
  than a date: at least one `ACC-FC-5` gate closed.
* `[G]` **`ACC-AM-4` stays armed-but-untriggered.** Its re-derivation obligation
  is undischarged and this record does not fire it.
* `[G]` **The constitution stays at three structural bounds**, per the bite in
  `ACC-CV2-1`.
* `[R]` Suspension is designed but unbuilt (`ACC-SUSP-*`); the `ACC-FC-5` gates
  are shut.

## 5. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record. No
lifecycle authority over agents or roles exists or is implied (`OD-C4=A`);
`OD-C3=B` holds. Constitution binding grants no compute, tools, evidence access
or consequential execution; digest membership proves integrity after
construction, never provenance; conformance replay proves conformance of
presented facts only. No constitution is authored, issued, superseded, suspended
or revoked by virtue of this record; **no clause content is ratified**; and no
signing key, trust root or approval artifact enters the repository.

## 6. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified**, and **v1's ratified content and digest
are untouched**. Policy Authority remains at `0.2.0`; `agent-constitution-policy`
at `0.2.0`; conformance and activation at `0.1.0`.

**Next step after this ADR merges:** none forced by it. The round is convened
only when `ACC-CV2-1`'s condition is met, and it then proceeds in the shape
`ACC-CV2-2`..`ACC-CV2-5` have already settled.
