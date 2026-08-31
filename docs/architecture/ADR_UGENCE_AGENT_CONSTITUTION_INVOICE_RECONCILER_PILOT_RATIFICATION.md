# ADR: Ugence Agent Constitution — invoice-reconciler pilot, owner ratification

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the six-item invoice-reconciler pilot
scoping ballot. **No implementation is authorized by this ADR**: it commits no
role document, no test and no proof, and settles nothing about how the pilot is
built. The implementation-authority ruling is a separate document that follows
this one.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `3c00046f` — the merge of PR #1540, which committed
the ballot this ADR ratifies.

**Supersedes a withdrawn pin.** `[V]` An earlier attempt at this record, PR
#1537, was **closed as superseded and never merged**. It pinned a 79-line
transcription of the same ballot, committed at `f4b0c94c` with document SHA-256
`bbb8d6c3685549ad857fe99dff0d3214ccd7158ac9069cffd7ad3e331854c0f6`, at the same
repository path #1540's document now occupies — an add/add collision that could
not be resolved without falsifying one ratification record or deleting a merged
document. `[R]` **That pin is withdrawn and has no force.** This ADR pins
#1540's merged document instead, and is the ratification of record. `[V]` The
ballot rows are unaffected by the substitution: the `PILOT_SURFACE` and
`IR-1`–`IR-5` rows in #1540's document are byte-identical to those in the
withdrawn transcription, which carried the same ballot without the surrounding
proposal.

## 1. What was ratified, exactly

The ballot put is
[`AGENT_CONSTITUTION_INVOICE_RECONCILER_PILOT_SCOPING_BALLOT.md`](AGENT_CONSTITUTION_INVOICE_RECONCILER_PILOT_SCOPING_BALLOT.md)
**as that file stands at commit `3c00046f`**:

| Identity value | Ratified value |
|---|---|
| File path | `docs/architecture/AGENT_CONSTITUTION_INVOICE_RECONCILER_PILOT_SCOPING_BALLOT.md` |
| Commit | `3c00046f` (the merge of PR #1540) |
| Document SHA-256 | `d971acfb9d08262a665e59c2c7f2c2b1060632217a397256aa31cee065ae68f3` |
| Line count | 297 |
| Ballot-block SHA-256 (`## 6.` heading through the `## 7.` heading, inclusive; 67 lines) | `5c2aa81975c75c860c62a335e3b813f6088fd7c1fc124ac0e37c28cb6dd6f522` |

`[V]` **All five values were verified before this ADR was written**, by reading
the file out of the named commit rather than out of a working copy; the working
copy is byte-identical. `[V]` The six ballot rows are present in order
`PILOT_SURFACE`, `IR-1` … `IR-5` and match the wording the owner ruled over.
`[R]` The ratified text is the version at `3c00046f`; should the file gain
further commits, this declaration continues to govern the text at that commit.

**Recorded exactly as ruled:**
`PILOT_SURFACE=YES IR-1=A IR-2=A IR-3=A IR-4=A IR-5=A`

`[R]` Every answer takes the ballot's recommended path; there is no departure
to record.

**Numbering.** `[R]` This ADR assigns **no** new `OD`, `S2B-*`, `P`, `RCG-D`,
`ACC-S1`, `ACC-AM`, `ACC-FC` or `ACC-IA` number. The composite fixed-surface
ruling is recorded as **`ACC-PR-BASE`** and the five register rulings as
**`ACC-PR-1`** – **`ACC-PR-5`**, all scoped to this ADR, on the standing
precedent of ADR-scoped citability labels; the ballot's own `PILOT_SURFACE` and
`IR-1` – `IR-5` labels remain the ballot's.

## 2. `ACC-PR-BASE` — the fixed surface

**Ruled: YES**, in the words of the ballot: the pilot is a committed
declaration and its proof, driven through the shipped `ACC-IA` orchestration —
no new authority surface, no change to any existing package's `src`, version or
`public_api.json`; no signing key, trust root or approval artifact enters the
repository (proof runs on ephemeral in-process keys); the only constitution
values used are the ratified `ACC-FC` content values, and every role
declaration sits inside the ratified bounds; no agent runs, is enrolled or is
claimed governed in operation; `/clauses/v2` stays out of scope and
`ACC-AM-4`'s re-arm stays untriggered.

**Precedence, as the ballot stated it** `[R]`: where an `IR` row and this
surface overlap, the `IR` ruling governs. Recorded because it governs how the
register below is read; no conflict exists in this all-`A` record.

## 3. `ACC-PR-1` – `ACC-PR-5` — the five-item register

Each ruling is recorded in the words of the option the owner selected.

### `ACC-PR-1` — The role artifact's home and form `[R]`

**Ruled: A.** One committed JSON document,
`packages/integration/agent-constitution-activation/pilot/invoice-reconciler-role.v1.json`
— data outside `src/`, never shipped in the wheel, constructed into the live
contract type only inside tests. **Does not settle:** the document's byte-level
content or the mechanics of its construction into the contract type, which
belong to the implementation-authority ruling.

### `ACC-PR-2` — The role's declared content `[R]`

**Ruled: A.** The §2 table with its disclosures: the governed reference as
document identity; tenant `ugence`; `role_contract_id` `invoice-reconciler`;
full ratified disposition and review-action vocabularies; tool scopes exactly
(`invoice.read`, `ledger.read`); `constitution_ref` equal to the signed
reference; the named escalation and strategy references carried as opaque,
ungoverned C5a values. `[I]` These values sit inside the `ACC-FC-4` bounds by
construction — the vocabularies are the ratified vocabularies whole, and the
declared tool scopes equal the ceiling — and both reference equalities restate
`ACC-FC-2`'s and `ACC-FC-3`'s ratified references.

### `ACC-PR-3` — Proof scope `[R]`

**Ruled: A.** The three-leg proof: document → contract equality; conformance
`True` from the document's facts with a widened-scope `False` control and the
two pinning assertions; and the full issue → activate → resolve → bind →
conform chain re-driven over this role, with a mismatched-reference refusal
control.

### `ACC-PR-4` — Packaging and versioning `[R]`

**Ruled: A.** Document + one test module in the activation distribution; the
shipped wheel is byte-identical and no version moves; a CHANGELOG note records
the pilot as a repository act. `[V]` Byte-identity is structural at this
baseline: the activation distribution builds from `where = ["src"]` with no
`MANIFEST.in`, so a `pilot/` directory beside `tests/` cannot enter the wheel
(`packages/integration/agent-constitution-activation/pyproject.toml`).

### `ACC-PR-5` — Commitment and sequencing `[R]`

**Ruled: A.** The pilot commits a governed declaration and its proof only — no
agent, no compute, no evidence access, no production issuance, no lifecycle
act; the lifecycle round (roadmap step 3) is not commissioned by this ballot.

## 4. The `ACC-FC-3` gap — carried forward, and what this pilot closes

`ACC-FC-3` was ruled with an explicit `[G]`: *no role artifact bearing
`ugence.roles/ugence/invoice-reconciler/v1` exists in this repository; the
`(tenant_id, role_contract_ref)` reference-map population remains ungoverned;
and governance begins at issuance and resolution, not at ratification.*

**What the pilot, once implemented as ruled, closes** `[R]`: the first clause
only — a committed role artifact bearing the ratified reference will exist,
with its content pinned by `ACC-PR-2` and its constructibility and conformance
proven by the `ACC-PR-3` legs, on ephemeral in-process keys.

**What remains open, precisely** `[G]`:

* **Until the implementation-authority ruling and its change set land, all of
  `ACC-FC-3`'s gap remains open** — this ADR closes nothing by itself. `[V]` At
  `3c00046f` no role artifact exists under that reference.
* **Production reference-map population stays ungoverned.** The `ACC-PR-3`
  chain leg populates a reference map from a record issued on ephemeral keys
  inside a test; no production issuance occurs and no operational reference map
  exists.
* **Governance in operation does not begin.** No agent runs, is enrolled, or is
  claimed governed (`ACC-PR-BASE`); the `ACC-FC-5` deployment gates — key
  custody, approving authority, operational composition, reference-map
  population — remain open and remain operational work, not change sets.
* **The lifecycle round (roadmap step 3) is uncommissioned** (`ACC-PR-5`).

## 5. Gap raised by this round — the committed-JSON guard `[G]`

`[G]` The activation distribution's role-projection scan at
`packages/integration/agent-constitution-activation/tests/test_import_boundary.py:174`
(and the repository-wide scan it re-asserts from the Agentic Proposer's suite)
covers `.py` files only. `[V]` At `3c00046f` that parametrization still globs
`*.py`. A committed JSON role declaration under `pilot/` is therefore not
reached by either scan, so no automated guard yet measures such a document.
**Recorded strictly as a gap.** This ADR decides nothing between extending the
scan and granting a narrow waiver — that decision belongs to the
implementation-authority ruling that follows.

## 6. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record.
Constitution binding grants no compute, tools, evidence access or consequential
execution; digest membership proves integrity after construction, never
provenance; no verifier emits a disposition or reserved authority term
(`OD-C3=B`); no lifecycle authority exists or is implied (`OD-C4=A`); and
conformance replay proves conformance of presented facts only. No constitution
exists, is issued, or may be described as issued by virtue of this record, and
the pilot's proof, when it runs, runs on ephemeral in-process keys — no signing
key, trust root or approval artifact enters the repository.

## 7. What this ADR changed

One new documentation file. **No production source, test, specification,
CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified**, and no ballot transcription is
committed — the pinned ballot is #1540's merged document, unmodified by this
ADR. The activation distribution remains at `0.1.0`.

**Next step after this ADR merges:** the implementation-authority ruling, as
its own document — settling the committed-JSON guard (§5) and authorizing the
pilot change set that `ACC-PR-1` – `ACC-PR-4` scope.
