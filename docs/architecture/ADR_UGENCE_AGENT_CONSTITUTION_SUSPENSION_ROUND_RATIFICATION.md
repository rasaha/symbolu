# ADR: Ugence Agent Constitution — suspension round, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item suspension round scoping
ballot. **No implementation is authorized by this ADR**, and none is performed:
no store, no record type, no resolution reason and no entitlement is added, and
`ACC-SUSP-5` below sequences the implementation as a separate change set under a
separate ruling. No policy is suspended, reinstated, revoked or superseded by
virtue of this record.

**Date:** 2026-09-01.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-09-01. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `e84941a8` — the merge of PR #1560, which narrowed
`ACC-FC5R-4`'s permitted set.

## 1. What was ratified, exactly

The ballot put is
[`AGENT_CONSTITUTION_SUSPENSION_ROUND_SCOPING_BALLOT.md`](AGENT_CONSTITUTION_SUSPENSION_ROUND_SCOPING_BALLOT.md)
**as that file stands at commit `b8359bc7`**, the commit that authored it:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_SUSPENSION_ROUND_SCOPING_BALLOT.md` |
| Authoring commit | `b8359bc7` ("Commission the two deferred rounds: suspension and /clauses/v2 scoping ballots") |
| Document SHA-256 | `7ba91e619af237979d0b04cee5438083b8e084855afe04196eb980f7d6d3dd14` |
| Line count | 198 |
| Ballot-block SHA-256 (`## 3.` heading through the `## 4.` heading, inclusive; 65 lines) | `7a2fd5f52549d59e11d746615df5620199f14b3ba14d06a0ca64cedaaf6119ed` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical, and all six rows are present.

**Recorded exactly as ruled:**
`SUSP_SURFACE=YES SUSP-1=A SUSP-2=A SUSP-3=A SUSP-4=A SUSP-5=A`

`[R]` Every answer takes the ballot's recommended path. `[V]` The ballot's §4
independent-review prompt had **not** been run at ruling time; the owner ruled
directly. Recorded as fact, not defect — the prompt asked a reviewer to attack
the central claim and the `SUSP-2` ordering rule, and remains available.

**Numbering.** `[R]` Recorded as **`ACC-SUSP-BASE`** and **`ACC-SUSP-1`** –
**`ACC-SUSP-5`**, ADR-scoped, on the standing precedent. No `OD`, `ACC-S1`,
`ACC-AM`, `ACC-FC`, `ACC-IA`, `ACC-PR`, `ACC-LC`, `ACC-SU` or `ACC-FC5R` number
is assigned or moved.

## 2. The correction this round is built on

`[R]` `ACC-LC-3` deferred suspension and gave a reason: *"a reversible pause
needs a state absent from the ratified closed set `ADMITTED_LIFECYCLE_STATES`,
which makes it a vocabulary act rather than a mechanics act."* **That reason does
not hold, and this ADR records the correction rather than inheriting it.**

`[V]` The supersession mechanism the same round shipped never writes
`lifecycle_state`: `core/supersession.py` contains no lifecycle reference, and
resolution denies via a store consulted at `as_of` with a typed reason
(`core/resolution.py:293-296`). A superseded policy's signed artifact still reads
`APPROVED_ACTIVE`; only the store stops it resolving.

`[R]` **`ACC-LC-3`'s conclusion stands; only its premise is corrected.**
Suspension still gets its own round — this one — and `ACC-LC-3` is not amended,
reopened or renumbered. `[R]` The cost is real but different from the one
`ACC-LC-3` named: suspension extends `PolicyResolutionReason`, a closed
vocabulary a consumer mirrors **total and injective**
(`cloud-scaling-policy-authenticity/tests/test_typed_outcomes.py:26,32`) — the
coupling that made `ACC-LC-IA-BASE`'s surface unsatisfiable and forced the `A1`
amendment. `ACC-SUSP-4` makes that a precondition rather than a discovery.

## 3. `ACC-SUSP-BASE` — the fixed surface

**Ruled: YES**, in the words of the ballot: a contract and design act over
policy-version lifecycle only; no new authority; `OD-C4=A` holds untouched — a
signed policy artifact's lifecycle, never an agent's or a role's; `OD-C3=B`
holds; no signing key, trust root or approval artifact enters the repository and
no issuance, revocation, supersession or suspension is performed; no
already-valid artifact is invalidated and no existing refusal is relaxed — the
unstructured `supersedes_ref` keeps being refused and revocation stays terminal
and separate — and no existing digest moves; `/clauses/v2` stays out of scope and
`ACC-AM-4`'s re-arm stays untriggered; the `ACC-FC-5` gates are neither closed
nor advanced; no agent runs, is enrolled or is claimed governed.

**Precedence** `[R]`: where a `SUSP` row and this surface overlap, the row
governs. No conflict exists in this all-`A` record.

## 4. `ACC-SUSP-1` – `ACC-SUSP-5` — the five-item register

### `ACC-SUSP-1` — Suspension does not touch the lifecycle vocabulary `[R]`

**Ruled: A.** Follow supersession's shipped shape — an append-only store, signed
records, resolution consulting it — with `lifecycle_state` **never written**.
`ADMITTED_LIFECYCLE_STATES` stays closed exactly as ratified, and `ACC-LC-3`'s
stated premise is corrected rather than inherited (§2).

### `ACC-SUSP-2` — Reversal is append-only and ordered `[R]`

**Ruled: A.** Suspend and reinstate are **both signed records in one store**;
resolution reads the latest applicable record at `as_of` and denies only if it is
a suspension. Nothing is ever deleted or mutated, so the history of pauses stays
legible.

`[G]` **The row where being wrong is expensive, recorded as such.** This is the
first state in this authority whose current value is not simply *"a record
exists"*. The ordering rule must be total and unambiguous, and the ballot's §4
review — asking a reviewer to construct equal timestamps, out-of-order arrival,
and a reinstate with no prior suspend — **has not been run**. The
implementation-authority ballot must settle those three cases explicitly.

### `ACC-SUSP-3` — One entitlement covers both acts `[R]`

**Ruled: A.** An authority that may pause may unpause. `[R]` The ground is
recorded: splitting the entitlement would create a state only a second party can
exit, which is an availability hazard dressed as a control.

### `ACC-SUSP-4` — The consumer surface, known in advance `[R]`

**Ruled: A.** The round's surface **must name** the new `PolicyResolutionReason`
member(s) and, with them, the consumer outcome members required by
`cloud-scaling-policy-authenticity`'s total, injective mapping — **enumerated in
the implementation-authority ballot before the surface is bounded**
(`ACC-SU-4`'s standing obligation, itself born of `ACC-LC-IA-BASE-A1`). `[R]`
This is an obligation on the next ballot, not advice.

### `ACC-SUSP-5` — What this round commits `[R]`

**Ruled: A.** Contract, design and ratification only — documentation, no source
change; the implementation is a separate change set under the ruling that
follows.

## 5. What remains open

* `[G]` **Everything mechanical.** No suspension store, record type, resolution
  reason or act exists. `[V]` The substring `SUSPENDED` appears in no source file
  of the authority or the three constitution distributions. This ADR closes no
  gap in the source; it settles what the change set must be.
* `[G]` **The `ACC-SUSP-2` ordering rule is unproven**, per §4.
* `[G]` **Suspension will be unexercisable on the day it lands**, exactly as
  supersession is: nothing has been issued and the `ACC-FC-5` gates are shut.
* `[R]` `/clauses/v2` and `ACC-AM-4` are untouched by this record.

## 6. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record. No
lifecycle authority over agents or roles exists or is implied (`OD-C4=A`);
nothing here writes or transitions an agent lifecycle state, or mints, changes or
ends a role. Constitution binding grants no compute, tools, evidence access or
consequential execution; digest membership proves integrity after construction,
never provenance; no verifier emits a disposition or reserved authority term
(`OD-C3=B`); conformance replay proves conformance of presented facts only. No
constitution is issued, superseded, suspended or revoked by virtue of this
record, and no signing key, trust root or approval artifact enters the
repository.

## 7. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** Policy Authority remains at `0.2.0`;
`agent-constitution-policy` at `0.2.0`; conformance and activation at `0.1.0`.

**Next step after this ADR merges:** the implementation-authority ballot for this
round — opening with the `ACC-SUSP-4` consumer enumeration, and settling the
three `ACC-SUSP-2` ordering cases. Until it is answered and its ruling lands, no
source file may change under this record.
