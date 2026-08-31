# Agent Constitution — the `OD-C1=B` contract-amendment ratification round

**Status: proposal — documentation only. Nothing here is ratified, and no
implementation is authorized by it.** The analysis was performed read-only: it
modified no production source, test, package metadata, `public_api.json`,
`version.py`, CI workflow or platform-freeze artifact, and this document is the
only file its change set adds. The five owner decisions in §6 are **open**; §7
is the ballot that would settle them.

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
head `21918b7441464cca68164a82c395f3791d3296a2`. Every `[V]` claim below is
verifiable against that head.

**Governing scope.** `OD-C1=B` rules that the round this document convenes
**alone ratifies the amendment's content, fields and binding mechanism**
(`ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md:95-107`), and
`ACC-S1-Q5=A` adopted the first-slice specification's §7 designed shape and
sequencing **as this round's input, never as its outcome**
(`ADR_UGENCE_AGENT_CONSTITUTION_FIRST_SLICE_RATIFICATION.md:166-179`). This
document designs within those rulings, extends no standing boundary, reopens no
ruling, and assigns **no** new `OD`, `S2B-*`, `P`, `RCG-D` or `ACC-S1` number.
Ballot rows are labeled `AR-1` – `AR-5`, proposal-local; the register labels for
whatever is ratified are the ratification ADR's to assign, on the `S2B-PF` and
`ACC-S1` precedent.

**Load-bearing question, answered first.** This round settles exactly three
things: the amendment's **content and field set** on the role-contract and
advisory surfaces, its **binding mechanism** (how the constitution becomes
digest-bound to the proposals it governs), and the Agentic Proposer's **version
and public-surface impact**. It settles nothing else: implementation authority
remains a separate later ruling on the `ACC-S1-IMPL` precedent; the
constitution's substantive clause content and first authorship remain outside
the slice; and no Policy Authority or constitution-distribution change is put
in question.

**Evidence labels.** `[V]` verified against this repository at the cited
`file:line` or the named basis; `[I]` architectural inference; `[R]` owner
ruling required; `[G]` unresolved gap.

> *This specification changes **no** production source, test, package metadata,
> CHANGELOG, `public_api.json`, `version.py`, CI workflow or platform-freeze
> artifact. `[V]` The substantive freeze digest was recomputed in this session
> and is unchanged, all checks PASS:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 0. Baseline verification

| Check | Result |
|---|---|
| Default-branch head | `[V]` `21918b7441464cca68164a82c395f3791d3296a2` — exact match; the working tree was verified clean |
| Both `ACC-S1-Q2` change sets merged | `[V]` `96698ef1` (family, PR #1524) and `7170b0ca` (conformance, PR #1525) are ancestors of the head |
| Agentic Proposer | `[V]` `0.3.1` (`src/ugence_agentic_proposer/version.py:84`); `public_api.json` = 51 symbols |
| Policy Authority | `[V]` `0.1.0`; untouched by both change sets |
| Constitution distributions | `[V]` `ugence-agent-constitution-policy` and `ugence-agent-constitution-conformance`, both `0.1.0`, both under `packages/integration/` |
| The presented-reference consumer exists | `[V]` the conformance resolver's fourth post-check compares a presented constitution reference with the signed `agent_constitution_ref` and is documented as optional until this round lands (`…agent_constitution_conformance/resolution.py`, post-check 4) |
| Substantive freeze digest | `[V]` recomputed via `python -m platform_freeze.verify`: PASS, `d9930935…fac036`, unchanged |

**No baseline mismatch. Proceeding.**

---

## 1. What "digest-bound to the proposals it governs" must cash out to

`[V]` `OD-C1=B` rejected the weak linked-record guarantee under which a proposal
stays digest-valid with its governing declaration absent, replaced or never
produced; the ratified precedent is `S2B-D6=B1`, which put
`strategy_policy_id`/`strategy_policy_version` **inside the advisory's signed
projection** so an unbound declaration cannot outlive its policy
(`ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md:104-107`;
`src/ugence_agentic_proposer/identity.py:130-138`, where the private
`P_unsigned` payload carries those fields as **required**, mirrored on the
advisory under the G2 equivalence obligation).

`[I]` The amendment therefore has exactly two surfaces, and both are already
designed in the ratified input:

1. **Role-contract surface** — one C5a reference field, `constitution_ref`, on
   the exact precedent of `strategy_policy_ref` (`[V]` a required C5a
   `Identifier` field, `src/ugence_agentic_proposer/contracts.py:311-322`): a
   reference to an externally issued, signed, versioned and revocable
   constitution, **resolved by injection, never role data**. Its consumer
   already ships: the conformance resolver requires exact equality with the
   signed `agent_constitution_ref` when a reference is presented.
2. **Proposal surface** — `constitution_policy_id` and
   `constitution_policy_version`, C5b `Token`s, stamped from a constitution
   resolution onto the advisory **inside `P_unsigned`**, mirrored on the
   advisory model per G2, exactly as the `S2B-D6=B1` trio is today.

**Never, in this amendment** (each prohibition stated once): no role lifecycle
verb or authority enters any surface (`OD-C4=A`); no verifier disposition,
denial, abstention or reserved authority term (`OD-C3=B`); no compute, tools,
evidence access or consequential execution is granted; no constitution clause
content beyond the three structural bounds is ratified; no Policy Authority or
constitution-distribution source changes — the amendment's change set touches
the Agentic Proposer alone.

---

## 2. Consequences, disclosed before the ballot

* `[I]` **Construction is breaking.** A required role-surface field and a
  required advisory pair mean every existing construction call gains arguments.
  That is the shape `S2B-D6=B1` took: `[V]` its four fields landed as the
  `0.3.0` minor release (`packages/capabilities/agentic-proposer/CHANGELOG.md:53,84-87`).
* `[I]` **Advisory digests move.** New required fields inside `P_unsigned`
  change the identity of every newly built advisory. `[V]` The `S2B` precedent
  kept `advisory_version` at `"1"` through exactly such an addition
  (`identity.py:109`, still `"1"` after `0.3.0`); whether this round follows
  that precedent is `AR-3`.
* `[I]` **A resolver seam is implied but not new.** Stamping from resolution
  requires an injected constitution resolution at advisory-build time, on the
  pattern of the injected strategy resolver; the concrete resolver already
  exists in `ugence-agent-constitution-conformance` and is not changed by this
  round.
* `[G]` **Reference-map population remains ungoverned** — carried unchanged
  from the scoping ADR; this round does not close it and must not be read as
  closing it.

---

## 3. Re-derivation — the readiness obligation, addressed

`[V]` The readiness ADR obliges the proposer-local role projection to be
**re-derived from the constitution rather than promoted** when the governing
document exists, and bars reading the projection as anticipating the
constitution correctly (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:123-127`).
`ACC-S1-Q5=A` makes this round the vehicle for stating what re-derivation
changes, *even if the answer is "nothing yet"*.

`[I]` **The recommended answer is "nothing yet", recorded with its re-arm
condition.** A first-slice constitution declares three structural bounds and no
clause content; the projection's field set is not derivable from bounds alone,
and inventing a derivation would claim constitution content the slice does not
carry. The obligation is not discharged — it **re-arms** the first time a
clause vocabulary beyond the structural bounds is ratified, at which point
re-derivation gets its own round. `AR-4` puts this to the owner.

---

## 4. Version and public-surface impact

| Item | Proposed | Basis |
|---|---|---|
| `ugence-agentic-proposer` version | `0.3.1` → `0.4.0` | `[V]` the `0.3.0` precedent for a P_unsigned-moving amendment (`CHANGELOG.md:53`) |
| Exported names | 51, unchanged | `[I]` the amendment adds fields to existing models and exports no new symbol; the `public_api.json` snapshot changes only in field lists |
| `advisory_version` | `AR-3`'s to settle | see §2 |
| Constitution distributions | unchanged | consumers, not subjects, of this round |
| Policy Authority | unchanged | `[V]` untouched throughout the slice |

---

## 5. What this round does not settle

Implementation authority for the amendment's change set (a later, separate
ruling, on the `ACC-S1-IMPL` precedent); the constitution's substantive clause
content and who authors the first constitution; the raised Policy Authority
milestones (core-level family-value uniqueness; registry-level
`governed_role_refs` overlap refusal); reference-map population; and any
naming claim over the absent
`UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_INITIAL_DESIGN_SPEC_v0.1`, which
remains an owner matter outside this ballot.

---

## 6. Owner-decision register (five)

| # | Decision | A (recommended) | B |
|---|---|---|---|
| AR-1 | Role-surface field | `constitution_ref` **required**, C5a, on the `strategy_policy_ref` precedent exactly — fail-closed at construction | optional until the first constitution is issued; requiredness ratified later |
| AR-2 | Proposal-surface binding | `constitution_policy_id`/`constitution_policy_version` **required** C5b `Token`s inside `P_unsigned`, mirrored per G2, stamped from an injected constitution resolution — `S2B-D6=B1` exactly | an optional pair; a proposal may be digest-valid without its governing constitution's identity |
| AR-3 | Advisory identity versioning | keep `advisory_version` `"1"` through the field addition, on the `0.3.0` precedent | move `advisory_version` to `"2"`, making the digest shift explicit in the identity |
| AR-4 | Re-derivation | record **"nothing yet"** with the §3 re-arm condition | commission a re-derivation design inside this round |
| AR-5 | Version impact | `0.4.0`, 51 names unchanged, snapshot field lists updated | the owner supplies a different version, same disclosure obligations |

Couplings, disclosed: `AR-2=B` would reopen the exact weakness `OD-C1=B` was
ruled to exclude, and is listed because the round must be able to say no, not
because the recommendation is in doubt. `AR-1` and `AR-2` are independently
answerable — a required role reference does not entail required stamping, and
the reverse. No other pair interacts. The fixed amendment surface (§1's field
names, types, grammar and placement; §3's statement) is put to ratification
whole alongside the rows, with the standing precedence rule: where an `AR` row
and the fixed surface overlap, **the `AR` ruling governs**.

---

## 7. Paste-ready owner-ratification ballot

```
Agent Constitution — OD-C1=B contract-amendment round, owner ballot
Baseline: rasaha/symbolu default head 21918b7441464cca68164a82c395f3791d3296a2
Governed by OD-C1..OD-C5 and ACC-S1-BASE/Q1..Q5/IMPL as ratified. Answer each with
A or B. A = the recommended path.

AMENDMENT_SURFACE  Ratify, as the amendment's fixed surface, §1's non-alternative
      commitments: the two-surface shape (constitution_ref on the role-contract
      surface; constitution_policy_id/constitution_policy_version inside P_unsigned,
      mirrored per G2), the field names, C5a/C5b grammars and placements, and §3's
      re-derivation statement — with the precedence rule: where an AR row and this
      surface overlap, the AR ruling governs.  YES/NO.

AR-1  Role-surface field requiredness.
      A = constitution_ref required, on the strategy_policy_ref precedent exactly.
      B = optional until the first constitution is issued.

AR-2  Proposal-surface binding.
      A = required constitution_policy_id/constitution_policy_version Tokens inside
          P_unsigned, mirrored per G2, stamped from an injected constitution
          resolution (S2B-D6=B1 exactly).
      B = an optional pair.

AR-3  Advisory identity versioning.
      A = keep advisory_version "1" through the addition (the 0.3.0 precedent).
      B = move advisory_version to "2".

AR-4  The readiness re-derivation obligation.
      A = record "nothing yet", re-arming when clause content beyond the three
          structural bounds is ratified.
      B = commission a re-derivation design inside this round.

AR-5  Version and surface impact.
      A = ugence-agentic-proposer 0.4.0; 51 exported names unchanged; snapshot
          field lists updated.
      B = owner supplies a different version, same disclosure obligations.

Record as: AMENDMENT_SURFACE=? AR-1=? AR-2=? AR-3=? AR-4=? AR-5=?
No implementation is authorized by this ballot; implementation authority, register
labels and any authorization ruling belong to the ratification ADR that records
these answers.
```

---

## 8. Paste-ready independent-review prompt

```
Read-only independent review. Do not modify files, create a branch, commit, push or open a PR.

Repository: rasaha/symbolu
Expected default-branch head: 21918b7441464cca68164a82c395f3791d3296a2
Artifact under review: docs/architecture/AGENT_CONSTITUTION_CONTRACT_AMENDMENT_ROUND_SPECIFICATION.md

Verify the baseline first (head, clean tree, both ACC-S1-Q2 change sets merged as PRs
#1524/#1525, proposer 0.3.1/51, authority 0.1.0, freeze digest
d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036 unchanged); stop on
mismatch. Then judge against the repository, not this document's prose:

1. Does the designed surface stay inside OD-C1..OD-C5 and the ACC-S1 rulings — in
   particular, does anything here ratify what OD-C1=B reserves to the round's owner
   ballot, grant lifecycle authority (OD-C4), or emit a disposition (OD-C3)?
2. Are the two precedents cited accurately — strategy_policy_ref as a required C5a role
   field (contracts.py:311-322) and the required S2B-D6=B1 Token pair inside P_unsigned
   with G2 mirroring (identity.py:130-138)?
3. Are the disclosed consequences real — breaking constructions, moving advisory digests,
   the 0.3.0 version precedent, advisory_version held at "1"?
4. Is the re-derivation answer honest against the readiness ADR's obligation
   (ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:123-127), and is its re-arm condition
   stated rather than the obligation quietly discharged?
5. Are the five AR rows genuinely open decisions with accurate recommendations, and is
   anything described as implemented, settled or ratified that is not?
Return SOUND, SOUND_WITH_CORRECTIONS, or BLOCKED, findings cited to file:line.
```

---

## 9. Readiness verdict

**READY_FOR_OWNER_RATIFICATION.** Baseline verified in full; the substantive
freeze digest is unchanged; five owner decisions plus the fixed-surface question
are open, and none is settled here. Next steps after ratification, in the
`ACC-S1-Q5` sequencing: the ratification ADR recording the answers and assigning
register labels; a separate implementation-authority ruling; then the
amendment's own change set — the first release of the slice requires all of
them.
