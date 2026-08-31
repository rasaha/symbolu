# ADR: Ugence Agent Constitution — issuance & activation design, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item ballot put by the issuance
& activation design specification. **No implementation is authorized by this
ADR, no code exists for the ratified design, and no constitution is issued**:
implementation authority is a separate ruling that follows this ADR's merge to
the default branch, on the `ACC-S1` precedent, and issuance remains the
deployment act `ACC-FC-5` sequenced.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default branch
`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`, head
`8a67e4f9517a1a0793d5f8384a66eac6bd7f1f2a` — the ballot document's own baseline,
the merge of PR #1531, which recorded the `ACC-FC-*` first-constitution content
ratification.

## What was ratified, exactly

The ballot put over
[`AGENT_CONSTITUTION_ISSUANCE_AND_ACTIVATION_DESIGN_SPECIFICATION.md`](AGENT_CONSTITUTION_ISSUANCE_AND_ACTIVATION_DESIGN_SPECIFICATION.md)
**as that file stands at commit `aa72c8058e50303b75a6daa8d1ab0460286dc776`**:

| Identity value | Ratified value |
|---|---|
| Commit | `aa72c8058e50303b75a6daa8d1ab0460286dc776` |
| Document SHA-256 | `35aa5be53d2aab7cc34e6cb7479e15c9ce778b420e9641f6e736de6912b85793` |
| Line count | 293 |
| Ballot-block SHA-256 (`## 6.` heading through the `## 7.` heading, inclusive) | `8fb2211f77700ea9cef8229391bb97f5526a0be1f336e02fc416e3014d92e9b8` |

`[V]` **All four values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`ISSUANCE_SURFACE`, `IA-1` … `IA-5` and match the wording the owner ruled over.
`[V]` The ballot's §0 seam citations — `issue_policy`'s signature and posture,
the approval boundary's deny-all default, the `PolicySigner` protocol,
`build_constitution_resolver`'s guard-on-every-path, and the resolver-return /
proposer-stamping duck-type match — were verified against source at the baseline
head before the ballot was put.

`[R]` **The ratified text is the version at that commit.** Should the file gain
further commits, this declaration continues to govern the text at `aa72c805`.

**Recorded exactly as ruled** (six lines, verbatim):

```
ISSUANCE_SURFACE=YES
IA-1=A
IA-2=A
IA-3=A
IA-4=A
IA-5=A
```

`[I]` The ballot's requested single-line `Record as:` form and the six-line form
the owner used are the same six assignments; every row is unambiguous and every
answer takes the specification's recommended path — there is no departure to
record. `[V]` The specification's §7 independent-review prompt had not been run
at ruling time; the owner ruled directly. Recorded as fact, not as a defect:
review was offered and remains available to anyone auditing this record.

**Numbering.** `[R]` This ADR assigns **no** new `OD`, `S2B-*`, `P`, `RCG-D`,
`ACC-S1`, `ACC-AM` or `ACC-FC` number. The composite fixed-surface ruling is
recorded as **`ACC-IA-BASE`** and the five register rulings as **`ACC-IA-1`** –
**`ACC-IA-5`**, all scoped to this ADR, on the standing precedent of ADR-scoped
citability labels; the ballot's own `ISSUANCE_SURFACE` and `IA-1` – `IA-5`
labels were proposal-local and are retired by this recording. No standing series
is extended, renumbered or reopened.

**Evidence labels.** `[V]` verified against this repository at the cited
`file:line`, a commit, or the named basis; `[I]` architectural inference; `[R]`
an owner ruling; `[G]` an unresolved gap.

> *This ADR changes **no** production source, test, specification, CHANGELOG,
> `public_api.json`, `version.py`, package metadata, CI workflow or
> platform-freeze artifact. `[V]` The substantive freeze digest was recomputed
> in this session and is unchanged, all checks PASS:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 1. `ACC-IA-BASE` — the fixed surface `[R]`

**Ruled: YES.** Ratify the fixed surface: the feature is orchestration over the
existing Policy Authority and constitution distributions — it defines no
signing, approval, canonicalization, registry or resolution semantics, mints no
decision, emits no disposition or reserved authority term, and holds no
lifecycle authority of its own; no signing key, trust root or approval artifact
enters the repository in any form (tests use ephemeral in-process keys); the
only first-constitution values used are the ratified `ACC-FC` content values;
proposer `0.4.0`, Policy Authority `0.1.0` and both constitution distributions
`0.1.0` are unchanged by this round's ratification; `/clauses/v2` stays out of
scope and `ACC-AM-4`'s re-arm stays untriggered.

**Precedence, as the ballot stated it** `[R]`: where a register ruling and the
fixed surface overlap, **the register ruling governs**. `[I]` Procedural on this
ballot, every row having been answered `A`; recorded because it governs how
`ACC-IA-BASE` is to be read by anyone later reopening a single row.

---

## 2. `ACC-IA-1` – `ACC-IA-5` — the five-item register

Each ruling is recorded in the words of the option the owner selected.

### `ACC-IA-1` — Packaging `[R]`

**Ruled: A.** One new integration distribution
`ugence-agent-constitution-activation` (namespace
`ugence_agent_constitution_activation`), `0.1.0`, joining the shared
agent-constitution CI workflow; no existing version moves. **Does not settle:**
the distribution's exact public-name list, which the implementation change set
pins in its `public_api.json` under this round's ruled bounds.

### `ACC-IA-2` — Custody and trust seams `[R]`

**Ruled: A.** Signer, signature verifier and approval verifier arrive already
constructed via the existing `ugence_policy_authority.api` protocols; the
package `src` provably cannot mint, read or persist key material (AST and
import scan); ephemeral in-process keys in tests and the verify script only.
**Does not settle:** any custody backend — env, KMS or otherwise — which stays
deliberately outside this repository's scope, per the fixed surface.

### `ACC-IA-3` — Governed reference-map population `[R]`

**Ruled: A.** Entries derive only from the issued record — one per reference in
the policy's `governed_role_refs`, mapped to the issued coordinate under the
policy's scope tenant; free-form entries refused; conflicts fail closed; the
activation receipt lists every entry. `[I]` This narrows the standing
`ACC-FC-3` gap from "ungoverned" to "governed by derivation". `[G]` What
remains of that gap, carried: no role artifact bearing the governed reference
exists in this repository, and production map population remains a deployment
act performed by running the shipped machinery.

### `ACC-IA-4` — Preflight and receipts `[R]`

**Ruled: A.** `preflight_issuance` replays every pre-signing check via public
API calls and mutates nothing; frozen `IssuanceReceipt`/`ActivationReceipt` pin
coordinate, digests, record id, signer identity fields
(`authority_id`/`key_id`/`signature_alg` — never key material), approval
reference and digest, caller-supplied tz-aware times, and the activated
entries. **Does not settle:** receipt persistence or transport, which belong to
the operator running the root, not to this package.

### `ACC-IA-5` — Proof scope `[R]`

**Ruled: A.** The full issue → resolve → bind → conform chain plus the four-way
fail-closed matrix (missing approval, missing trust, missing mapping, revoked
policy), in tests and a pinned offline verify script, on ephemeral keys. `[I]`
The binding leg gives the `ACC-AM-2` stamping seam its first genuinely resolved
input, and entails a test-side dependency on the proposer package with the
role constructed under a fragment-assembled name so the repository-wide
projection scan holds — both disclosed in the ballot's couplings.

---

## 3. Non-claims, carried forward unchanged

Nothing is implemented by this ADR, and no capability it describes may be
called implemented, issued or production-ready until the change set it
authorizes-nothing-toward merges under a separate implementation-authority
ruling. No constitution exists or is issued; the first production issuance
remains a deployment act under `ACC-FC-5`, and this round makes its gates
closable, not closed. Constitution binding grants no compute, tools, evidence
access or consequential execution; no verifier or orchestrator emits a
disposition or reserved authority term (`OD-C3=B`); no lifecycle authority is
created or implied (`OD-C4=A`) — issuance and revocation acts composed by the
ratified design are the Policy Authority's, under owner-supplied trust.

---

## 4. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** The pinned ballot document is
unmodified: its commit, digest, line count and ballot block are unchanged, and
this ADR neither edits nor supersedes it. The Agentic Proposer remains at
`0.4.0` with fifty-one authorized public names; Policy Authority at `0.1.0`;
both constitution distributions at `0.1.0`.

**Next steps after this ADR merges:** the separate implementation-authority
ruling over a pinned baseline; then one atomic change set building
`ugence-agent-constitution-activation`, the CI wiring and the `ACC-IA-5` proof.
The open in-repo threads otherwise remain the two raised Policy Authority
milestones and, when the owner convenes it, the `/clauses/v2` round.
