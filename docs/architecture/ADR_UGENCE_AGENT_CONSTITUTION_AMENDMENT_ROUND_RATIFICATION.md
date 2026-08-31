# ADR: Ugence Agent Constitution — contract-amendment round, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item ballot put by the
contract-amendment round specification. **No implementation is performed by
this ADR, and none is authorized by it** — see §3: the implementation gate
stands, and an authorization ruling was deliberately not part of this ballot.

> **Superseded in part as to authorization (2026-08-31, `ACC-AM-IMPL=YES`).**
> "none is authorized by it" is retained verbatim above as the record of what
> was true of the six-item ballot this ADR records. `[R]` A **later, separate
> ruling the same day** — recorded at §6, put over this ADR as it stood at
> commit `1cc0a6e2ab4a7020e21a1909a169fe3f82311a66` — grants implementation
> authority under §3's stated terms. The rest of the sentence stands unchanged:
> this ADR still performs no implementation, and authorization is not
> implementation.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default branch
`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`, head
`21918b7441464cca68164a82c395f3791d3296a2` — the ballot document's own baseline,
`[V]` re-verified unchanged at ruling time.

## What was ratified, exactly

The ballot put over
[`AGENT_CONSTITUTION_CONTRACT_AMENDMENT_ROUND_SPECIFICATION.md`](AGENT_CONSTITUTION_CONTRACT_AMENDMENT_ROUND_SPECIFICATION.md)
**as that file stands at commit `4f668ba2aafabb92b0390d30e6a27a21ac0a0bf7`**:

| Identity value | Ratified value |
|---|---|
| Commit | `4f668ba2aafabb92b0390d30e6a27a21ac0a0bf7` |
| Document SHA-256 | `3a07234e4c8ce60dfd7495c767f08115456e5d06535afb9ccc878be9aba28722` |
| Line count | 275 |
| Ballot-block SHA-256 (`## 7.` heading through the `## 8.` heading, inclusive) | `8638898cd76b3786b78c0a53989638a9fbc8ce0ca8a66e7773fc62d8b9aa3fbf` |

`[V]` **All four values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`AMENDMENT_SURFACE`, `AR-1` … `AR-5` and match the wording the owner ruled over.

`[R]` **The ratified text is the version at that commit.** Should the file gain
further commits, this declaration continues to govern the text at `4f668ba2`.

**Recorded exactly as ruled:**
`AMENDMENT_SURFACE=YES AR-1=A AR-2=A AR-3=A AR-4=A AR-5=A`

`[R]` Every answer takes the specification's recommended path; there is no
departure to record. `[V]` The specification's §8 independent-review prompt had
not been run at ruling time; the owner ruled directly, in the same session that
drafted the specification. That is recorded as fact, not as a defect: review was
offered and remains available to anyone auditing this record against the
repository.

**Numbering.** `[R]` This ADR assigns **no** new `OD`, `S2B-*`, `P`, `RCG-D` or
`ACC-S1` number. The composite fixed-surface ruling is recorded as
**`ACC-AM-BASE`** and the five register rulings as **`ACC-AM-1`** –
**`ACC-AM-5`**, all scoped to this ADR, on the `S2B-PF` and `ACC-S1` precedent
of ADR-scoped citability labels; the ballot's own `AMENDMENT_SURFACE` and
`AR-1` – `AR-5` labels were proposal-local and are retired by this recording.
No standing series is extended, renumbered or reopened.

**Evidence labels.** `[V]` verified against this repository at the cited
`file:line`, a commit, or the named basis; `[I]` architectural inference; `[R]`
an owner ruling; `[G]` an unresolved gap.

> *This ADR changes **no** production source, test, specification, CHANGELOG,
> `public_api.json`, `version.py`, package metadata, CI workflow or
> platform-freeze artifact. `[V]` The substantive freeze digest was recomputed
> in this session and is unchanged, all checks PASS:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 1. `ACC-AM-BASE` — the fixed amendment surface `[R]`

**Ruled: YES.** Ratify, as the amendment's fixed surface, the specification's
§1 non-alternative commitments: the two-surface shape — `constitution_ref` on
the role-contract surface; `constitution_policy_id` and
`constitution_policy_version` inside `P_unsigned`, mirrored on the advisory
under the G2 equivalence obligation — with the ratified field names, C5a/C5b
grammars and placements; and §3's re-derivation statement.

**Precedence, as the ballot stated it** `[R]`: where a register ruling and the
fixed surface overlap, **the register ruling governs**. `[I]` On this ballot the
point is procedural, since every row was answered `A`; it is recorded because it
governs how `ACC-AM-BASE` is to be read by anyone later reopening a single row.

`[R]` **What YES does not do:** it authorizes no implementation (§3); it
ratifies no constitution clause content beyond the three structural bounds; it
changes nothing in Policy Authority or either constitution distribution; and it
does not close the reference-map population gap, which is carried, not settled.

---

## 2. `ACC-AM-1` – `ACC-AM-5` — the five-item register

Each ruling is recorded in the words of the option the owner selected.

### `ACC-AM-1` — Role-surface field requiredness `[R]`

**Ruled: A.** `constitution_ref` is **required**, on the `strategy_policy_ref`
precedent exactly (`[V]` a required C5a `Identifier` field,
`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/contracts.py:311-322`):
a reference to an externally issued, signed, versioned and revocable
constitution, resolved by injection, never role data. `[I]` The disclosed
consequence holds: every existing role construction gains an argument, and a
role that names no constitution is not constructible after the change set
lands. **Does not settle:** which constitution any deployment names — the
reference map's population remains ungoverned (`[G]`).

### `ACC-AM-2` — Proposal-surface binding `[R]`

**Ruled: A.** `constitution_policy_id` and `constitution_policy_version` are
**required** C5b `Token`s inside `P_unsigned`, mirrored on the advisory per the
G2 equivalence obligation, stamped from an injected constitution resolution —
`S2B-D6=B1` exactly (`[V]` the precedent trio,
`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/identity.py:130-138`).
`[I]` This is what "digest-bound to the proposals it governs" cashes out to: an
unbound declaration cannot outlive its constitution. **Does not settle:** the
change set's internal design — builder signatures, validator placement — which
implementation authority's ruling gates.

### `ACC-AM-3` — Advisory identity versioning `[R]`

**Ruled: A.** `advisory_version` stays `"1"` through the field addition, on the
`0.3.0` precedent (`[V]` held at `"1"` through `S2B-D6=B1`'s own
`P_unsigned`-moving addition, `identity.py:109`). `[R]` The disclosed
consequence is accepted as ruled: the digests of newly built advisories move
with the field set, and the version literal does not mark the shift. **Does not
settle:** any future policy for when `advisory_version` does move.

### `ACC-AM-4` — The readiness re-derivation obligation `[R]`

**Ruled: A.** Recorded: re-derivation changes **"nothing yet."** A first-slice
constitution declares three structural bounds and no clause content, and the
projection's field set is not derivable from bounds alone (`[V]` the obligation:
`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:123-127`). `[R]` The obligation is
**not discharged** — it re-arms the first time clause content beyond the three
structural bounds is ratified, at which point re-derivation gets its own round.
Nothing in this repository should be read as evidence that the projection
anticipates the constitution correctly.

### `ACC-AM-5` — Version and surface impact `[R]`

**Ruled: A.** `ugence-agentic-proposer` moves `0.3.1` → `0.4.0` in the
amendment's change set, on the `0.3.0` precedent for a `P_unsigned`-moving
amendment (`[V]` `packages/capabilities/agentic-proposer/CHANGELOG.md:53`); the
51 exported names are unchanged, and the `public_api.json` snapshot changes only
in field lists. **Does not settle:** the release itself — versioning is the
change set's act, and the change set is not authorized here.

---

## 3. Implementation gate — nothing is authorized by this ballot `[R]`

*(Recorded as ruled on the six-item ballot; the gate this section describes was
subsequently opened by the separate `ACC-AM-IMPL` ruling — see §6, which
governs.)*

**No amendment code may begin.** The ballot carried no authorization line by
design, the owner's answer contains none, and this ADR grants none. `[I]` This
is the standing discipline in the same position it held between `ACC-S1-BASE`
and `ACC-S1-IMPL`: the amendment is now specified and decided, and building it
awaits its own explicit owner ruling, given **only after this ADR merges into
the default branch** — the merge precondition is part of the pattern, exactly as
`ACC-S1-IMPL` carried it.

`[R]` What such a ruling would authorize, when given: one atomic change set to
the Agentic Proposer alone, implementing `ACC-AM-BASE` and the five register
rulings as recorded here, with the proposer's own suite, snapshot and CHANGELOG
updated and the substantive freeze digest unchanged. It would not authorize any
change to Policy Authority, either constitution distribution, or any other
package, and it would not touch the raised Policy Authority milestones.

---

## 4. Non-claims and gaps, carried forward unchanged

Constitution binding grants **no compute, tools, evidence access or
consequential execution**; digest membership proves integrity after
construction, never provenance; no verifier emits a disposition or reserved
authority term (`OD-C3=B`); no lifecycle authority exists or is implied
(`OD-C4=A`). `[G]` Carried: reference-map population ungoverned; the
constitution's substantive clause content and first authorship outside the
slice; the core-level family-value uniqueness guard and the registry-level
`governed_role_refs` overlap refusal raised as Policy Authority milestones,
open.

---

## 5. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** The pinned ballot document is
unmodified: its commit, digest, line count and ballot block are unchanged, and
this ADR neither edits nor supersedes it. The Agentic Proposer remains at
`0.3.1` with fifty-one authorized public names; Policy Authority at `0.1.0`;
both constitution distributions at `0.1.0`.

**Next steps after this ADR merges**, in the ratified sequencing: an explicit
owner ruling on implementation authority for the amendment's change set (§3),
then that change set itself. First release of the Agent Constitution first
slice requires both. *(The first of these has since been ruled — §6; the
change set remains gated on this ADR reaching the default branch.)*

---

## 6. `ACC-AM-IMPL` — implementation authority, recorded (2026-08-31) `[R]`

**Ruled: YES**, by the repository owner personally, in conversation on
2026-08-31, on a one-item ballot put **after** the six-item ballot §§1–2 record
and **over this ADR as it stood at commit
`1cc0a6e2ab4a7020e21a1909a169fe3f82311a66`**. `[V]` That commit was the branch
head at ruling time, with a clean tree, and the substantive freeze digest
reproduced unchanged
(`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`).

**Recorded exactly as ruled:** `ACC-AM-IMPL=YES`

The ballot's operative text, in full: authorize implementation of the ratified
contract amendment — one atomic change set to the Agentic Proposer alone,
implementing `ACC-AM-BASE` and `ACC-AM-1`..`ACC-AM-5` exactly as recorded:
required `constitution_ref` on the role-contract surface; required
`constitution_policy_id`/`constitution_policy_version` `Token`s inside
`P_unsigned` mirrored per G2, stamped from an injected constitution resolution;
`advisory_version` held at `"1"`; version `0.3.1` → `0.4.0` with 51 exported
names unchanged and the snapshot's field lists updated; suite, CHANGELOG and
replay obligations updated accordingly; substantive freeze digest unchanged. It
authorizes no departure from any `ACC-AM` ruling, no change to Policy Authority
or either constitution distribution, and **only after this ratification ADR has
merged** into the default branch.

`[R]` **What this changes, precisely.** The §3 gate is opened **as a ruling**:
the amendment is now specified, decided and authorized to be built — the
position `ACC-S1-IMPL` occupied for the two distributions. `[G]` **It is not
closed as a fact**: no field exists on any surface, and none may be described
as existing until the change set lands. The merge precondition is part of the
ruling: no implementation change set may begin ahead of this ADR reaching the
default branch.

`[R]` **Numbering.** `ACC-AM-IMPL` is scoped to this ADR like its §§1–2
siblings; no standing series number is assigned, and no prior ruling is
extended, narrowed or reopened. This section records one authorization and
nothing else; §§3–5 stand as the record of the ballot that preceded it, read
subject to this section.
