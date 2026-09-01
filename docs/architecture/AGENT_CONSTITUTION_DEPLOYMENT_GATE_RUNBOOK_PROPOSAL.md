# Agent Constitution — `ACC-FC-5` deployment-gate runbook proposal

**The load-bearing question:** every contract gap in this arc is now closed, and
**nothing has ever been issued.** The authority can supersede, the family can
declare a predecessor, the composition root is shipped and proven — and all of
it is unreachable, because `ACC-FC-5`'s four gates are shut and *"none
performable by a repository file"*. `ACC-FC-5` deliberately left **when or by
whom** the gates are closed unsettled. This round settles that, and **only**
that: it writes the runbook, closes no gate, and issues nothing.

**Why a runbook is repository work at all.** Closing a gate is operational, but
*knowing what closing it means* is not. Today the four gates are a list in a
ratification ADR with no owner, no order, no evidence definition and no
rehearsal requirement. An operator holding a key would still have to invent all
four. `[V]` Two of the gates already have shipped machinery and two do not, and
the order is **not** a free choice — the fourth gate is strictly downstream of
the first issuance. That is knowable from the repository, and worth ratifying
before anyone holds a key.

**Status:** scoping/design proposal — documentation only. **No gate is closed,
no key is minted, no issuance is performed, and no implementation is authorized
by this document.** **Date:** 2026-09-01.

**Authorities this round sits under:** `OD-C1..OD-C5`, `ACC-S1-*`, `ACC-AM-*`,
`ACC-FC-*`, `ACC-IA-*`, `ACC-PR-*`, `ACC-LC-*` and `ACC-SU-*` as ratified.

---

## 0. Baseline, and the gate-by-gate state

`[V]` Default branch head `fa574353`, clean working tree, at or after
`fa574353` — the merge of PR #1554, which landed the family's supersession
opt-in. `[V]` Policy Authority `0.2.0`; `agent-constitution-policy` `0.2.0`;
conformance and activation `0.1.0`.

`ACC-FC-5` as ruled: *"The first issuance is a deployment act, gated on:
signing-key custody, an approving authority whose evidence the always-supplied
approval verifier checks, a composition root wiring the guarded registration
path, and reference-map population — each raised as a gap, none performed, none
performable by a repository file."*

Which gates the shipped code covers, verified at this head:

| Gate | Shipped machinery | What remains, and its nature |
|---|---|---|
| **1. Signing-key custody** | none, **by ruling** — `[V]` the activation source *"cannot mint, read or persist key material … the AST proves the package could not build one if asked"* (`agent-constitution-activation/tests/test_import_boundary.py:6-10`); the signer arrives already constructed | **purely operational.** A key must exist and be held somewhere this repository cannot see |
| **2. Approving authority** | partial — `[V]` the shipped default is `DenyAllApprovalVerifier`, *"the production default: no approval authority is wired up, so deny"* (`policy-authority/core/approval.py:160-164`), so an unconfigured deployment cannot issue at all | **purely operational.** A real authority, and evidence its verifier accepts |
| **3. Composition root** | `[V]` **shipped** — `build_activation_root` requires registry, signer, signature verifier and approval verifier with **no defaults**, shape-checked so *"a mis-wired deployment fails at composition"* (`activation/composition.py:222-237`) | supplying the real four. The wiring act itself is code that already exists |
| **4. Reference-map population** | `[V]` **shipped** — `populate_reference_map` derives entries *"from one issued record"*, one per reference in the record's artifact (`activation/reference_map.py:45-59`) | **strictly downstream of issuance.** It cannot be closed first: there is no record to derive from until gates 1–3 have produced one |

`[V]` A fourth instrument exists that the gate list does not name:
`preflight_issuance` *"runs every pre-signing check and report; sign nothing,
store nothing"* (`activation/preflight.py:111`). It is the only way to exercise
gates 2 and 3 in a real deployment **before** a custody key signs anything.

`[I]` Two consequences follow from the table, and neither is a preference:
gate 4 cannot precede issuance, and gates 1 and 2 are the only ones no
repository artifact can advance.

Stop condition for the eventual runbook: any of these failing at the time it is
written halts the document.

---

## 1. What this round lawfully is — and is not

**It is a plan, ratified.** It names owners, order, evidence and a rehearsal
requirement, so that closing a gate is a defined act rather than an improvised
one.

**It closes no gate and schedules nothing.** No date binds anyone; `ACC-FC-5`'s
"when" is settled as *ordering*, not as a calendar.

**It brings no secret into the repository.** That prohibition is the round's
own boundary: a runbook that required the repository to hold key material, a
trust root or approval-artifact bytes would be out of scope by construction, not
merely discouraged.

**It grants nothing.** `OD-C4=A` and `OD-C3=B` hold; no agent is enrolled, runs
or is claimed governed; `/clauses/v2` stays out of scope and `ACC-AM-4`'s re-arm
stays untriggered.

---

## 2. Owner-decision register (five)

| Row | Question | Recommended (A) | Alternative (B) |
|---|---|---|---|
| `FC5-1` | Who closes each gate, **in what order** | the order the code forces: **1 and 2 in parallel** (custody, and an approving authority), then **3** (composition, which needs both constructed), then a **rehearsal** (`FC5-3`), then the first issuance, then **4** (reference-map population, which derives only from the issued record). Each gate names a **responsible role**, not a person: custodian, approving authority, deploying operator | the owner names a different order or different owners |
| `FC5-2` | What evidence each gate produces, and **where it is recorded** | each closure produces a **non-secret attestation**: gate name, date, responsible role, and the public identifiers the act already exposes (`key_id`, issuing and approving authority ids, `approval_ref`, `record_id`, the issued coordinate). It is recorded in the **operational log outside this repository**; what may enter the repository is settled by `FC5-4` | a single consolidated attestation at the end, rather than one per gate |
| `FC5-3` | Whether a **dry-run rehearsal** is required first | **yes, mandatory.** Before any custody key signs, the target deployment must run the full chain — preflight → issue → activate → resolve → bind → conform — on **ephemeral in-process keys**, and the four-way fail-closed matrix must refuse as specified. `[V]` `preflight_issuance` exists precisely to make the pre-signing half of this possible without signing | recommended but not required; the operator decides per deployment |
| `FC5-4` | What the repository may hold about a **closed** gate | **non-secret facts only**: gate name, closure date, responsible role, and public identifiers and digests — **never** key material, a trust root, approval-artifact bytes, or any value from which they could be reconstructed. A closure is recorded as a one-line ADR fact naming where the evidence is held, never the evidence itself | the repository holds nothing at all about gate closure |
| `FC5-5` | What this round **commits** | the runbook and its ratification only — documentation. No gate is closed, no rehearsal is run, no issuance is performed, and no date is fixed. The first issuance remains a separate act under a separate record | additionally authorize the operator to close gates 1–3 under this ruling |

Couplings, disclosed: `FC5-2` and `FC5-4` interact — `FC5-4=B` (the repository
holds nothing) empties the in-repository half of `FC5-2`, leaving the whole
record outside version control. `FC5-1` and `FC5-3` interact only in that the
rehearsal sits between gates 3 and 4 in the ruled order. No other pair
interacts.

`[G]` **The bite of `FC5-5=A`, disclosed:** ratifying a runbook does not make
supersession, activation or conformance exercisable. It removes the excuse of
not knowing how, and nothing else. The gates stay shut until someone closes
them.

---

## 3. The fixed surface put to ratification

Ratified whole alongside the rows, with the standing precedence rule: **where an
`FC5` row and this surface overlap, the `FC5` ruling governs.**

This round is a documentation and planning act. **No signing key, trust root or
approval artifact enters this repository under any option on any row**, and no
value from which one could be reconstructed; no gate is closed, no rehearsal is
run and no issuance, revocation or supersession is performed by any document of
this round; `OD-C4=A` holds untouched — no agent or role lifecycle authority is
taken, implied or prepared for, and no agent runs, is enrolled or is claimed
governed; `OD-C3=B` holds — no disposition or reserved authority term is
emitted; no existing artifact is invalidated, no existing refusal is relaxed and
no digest moves; suspension stays unimplemented and its round uncommissioned
(`ACC-LC-3`); `/clauses/v2` stays out of scope and `ACC-AM-4`'s re-arm stays
untriggered; and no date binds anyone. **YES/NO.**

---

## 4. Paste-ready owner-ratification ballot

```
Agent Constitution — ACC-FC-5 deployment-gate runbook proposal
Baseline: rasaha/symbolu default head fa574353
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-*, ACC-IA-*, ACC-PR-*,
ACC-LC-* and ACC-SU-* as ratified. Answer each with A or B.
A = the recommended path.

FC5_SURFACE  Ratify the fixed surface: a documentation and planning act. No
      signing key, trust root or approval artifact enters this repository under
      any option on any row, and no value from which one could be
      reconstructed; no gate is closed, no rehearsal is run, and no issuance,
      revocation or supersession is performed; OD-C4=A holds untouched and no
      agent runs, is enrolled or is claimed governed; OD-C3=B holds; no existing
      artifact is invalidated, no refusal relaxed and no digest moved;
      suspension stays unimplemented (ACC-LC-3); /clauses/v2 stays out of scope
      and ACC-AM-4's re-arm stays untriggered; no date binds anyone — with the
      precedence rule: where an FC5 row and this surface overlap, the FC5 ruling
      governs.  YES/NO.

FC5-1  Who closes each gate, and in what order.
      A = the order the code forces: gates 1 and 2 in parallel (signing-key
          custody; an approving authority), then gate 3 (composition, which
          needs both already constructed), then the rehearsal of FC5-3, then the
          first issuance, then gate 4 (reference-map population, which derives
          only from the issued record). Each gate names a responsible ROLE --
          custodian, approving authority, deploying operator -- not a person.
      B = the owner names a different order or different owners.

FC5-2  What evidence each gate produces, and where it is recorded.
      A = each closure produces a non-secret attestation: gate name, date,
          responsible role, and the public identifiers the act already exposes
          (key_id, issuing and approving authority ids, approval_ref, record_id,
          the issued coordinate), recorded in the operational log outside this
          repository. What may enter the repository is settled by FC5-4.
      B = a single consolidated attestation at the end, not one per gate.

FC5-3  Whether a dry-run rehearsal is required first.
      A = yes, mandatory. Before any custody key signs, the target deployment
          must run preflight -> issue -> activate -> resolve -> bind -> conform
          on ephemeral in-process keys, and the four-way fail-closed matrix must
          refuse as specified.
      B = recommended but not required; the operator decides per deployment.

FC5-4  What the repository may hold about a closed gate.
      A = non-secret facts only: gate name, closure date, responsible role, and
          public identifiers and digests -- never key material, a trust root,
          approval-artifact bytes, or any value from which they could be
          reconstructed. A closure is a one-line ADR fact naming where the
          evidence is held, never the evidence itself.
      B = the repository holds nothing at all about gate closure.

FC5-5  What this round commits.
      A = the runbook and its ratification only. No gate is closed, no rehearsal
          run, no issuance performed, and no date fixed; the first issuance
          remains a separate act under a separate record. Bite: this removes the
          excuse of not knowing how, and nothing else.
      B = additionally authorize the operator to close gates 1-3 under this
          ruling.

Record as: FC5_SURFACE=? FC5-1=? FC5-2=? FC5-3=? FC5-4=? FC5-5=?
No implementation is authorized by this ballot; register labels belong to the
ratification ADR that records these answers.
```

---

## 5. Paste-ready independent-review prompt

```
Review, do not implement. Repository rasaha/symbolu at default head fa574353.
Read docs/architecture/AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_PROPOSAL.md
and judge four things against the repository, not against the document:

1. Is §0's gate-by-gate table true — that gates 1 and 2 have no shipped
   machinery by ruling, that build_activation_root and populate_reference_map
   cover gates 3 and 4, and that preflight_issuance signs and stores nothing?
2. Is the claim that gate 4 is STRICTLY downstream of the first issuance
   correct, or could a reference map be populated some other lawful way? If the
   ordering in FC5-1 is not forced, say so — the row's recommendation rests on
   it.
3. Does FC5-4=A leak anything? Walk the listed identifiers and digests and say
   whether any could reconstruct key material, a trust root, or approval
   evidence. Take the adversarial reading.
4. Does any option, if ruled, bring a secret into the repository, close a gate,
   perform an issuance, or touch a role or agent (OD-C4=A)?

Report findings labelled [V]/[I]/[R]/[G] with file:line support. Name any row
whose A and B are not genuinely exclusive.
```

---

## 6. Readiness verdict

`[R]` **Ready to put.** Each recommendation rests on a fact verified at §0
rather than on preference, and the one structural claim the round leans on —
that gate 4 cannot precede issuance — is put to a reviewer in §5 rather than
asserted. `[G]` The round's honest limit is stated in `FC5-5` itself: a ratified
runbook does not close a gate, and the four gates that have blocked every round
of this arc will still be shut the day it merges.
