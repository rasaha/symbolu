# Agent Constitution — invoice-reconciler pilot scoping ballot

**The load-bearing question:** can the ratified v1 Constitution be shown to
govern a **real, named role** — not a fixture invented inside a test — without
this repository acquiring an agent, a secret, or any new authority? **Yes**,
because governance at this layer is a property of declarations and machinery,
not of a running process: the constitution's `ACC-FC-3` ruling already names
`ugence.roles/ugence/invoice-reconciler/v1` as governed, and every consumer of
that naming is shipped and proven — the proposer's role surface bears the
required `constitution_ref` (`ACC-AM-1`), the conformance predicate answers
over presented role facts, and the activation root drives issue → activate →
resolve → bind → conform on ephemeral keys (`ACC-IA-5`). What is missing, and
was carried as a gap since `ACC-FC-3`, is the **role itself**: no artifact in
this repository declares what the invoice-reconciler is or claims. This pilot
commits that declaration and proves it conforms — closing the "no role artifact
exists" half of the gap while leaving deployment, custody and any live agent
exactly where the fixed surface keeps them: outside.

**Status:** scoping/design ballot — documentation only. Nothing here is
implemented, and **no implementation is authorized by this ballot**; register
labels and any later authorization belong to the ratification ADR and to the
separate implementation-authority ruling that follows it. **Date:** 2026-08-31.

**Authorities this round sits under:** `OD-C1..OD-C5`, `ACC-S1-*`, `ACC-AM-*`,
`ACC-FC-*` and `ACC-IA-*` as ratified.

---

## 0. Baseline verification

`[V]` Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
head `ac70994d9d4478628a17e96d0a656418302fbbdf` — the merge of PR #1534, which
landed the independently reviewed (SOUND) `ACC-IA` change set. `[V]` Working
tree clean. `[V]` Substantive freeze digest recomputed this session, all checks
PASS: `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`. `[V]`
Agentic Proposer `0.4.0`; Policy Authority `0.1.0`; all three constitution
distributions `0.1.0`.

Facts this design leans on, verified at this head:

* `[V]` The proposer's role surface carries exactly twelve fields, the twelfth
  being the required `constitution_ref` (`ACC-AM-1`); every §2 value below was
  proven constructible against the installed surface before this ballot was
  put — grammars, enum membership and tz-awareness included.
* `[V]` The repository-wide role-projection scan reads **`.py` files only**
  (`test_role_projection_bounds.py:511`), so a committed JSON document cannot
  trip it; the established fragment-assembled name lookup keeps the tests that
  construct the contract lawful (`_permission_runtime_fixtures.py:89`,
  `agent-constitution-activation/tests/test_end_to_end.py`).
* `[V]` The ratified first-constitution content (`ACC-FC-2`..`ACC-FC-4`)
  bounds this role: signed reference
  `ugence.agent-constitution/ugence/baseline/v1`, governed reference
  `ugence.roles/ugence/invoice-reconciler/v1`, full closed disposition and
  review-action vocabularies, tool-scope ceiling
  `("invoice.read", "ledger.read")`.

Stop condition for the eventual implementation: any of these failing at
implementation time halts the change set.

---

## 1. What a pilot lawfully is — and is not

**Is:** a committed, versioned **declaration** of the governed role, plus the
proof that the declaration sits inside the ratified bounds and that the whole
shipped chain governs it end to end. The declaration is data; the proof is
tests; the machinery is the `ACC-IA` root, unchanged.

**Is not:** an enrolment, an activation of any agent, a grant of compute or
evidence access, a production issuance, or a lifecycle act. `[I]` Committing
the role document creates governance *of a declaration*; governance of a
running reconciler begins at deployment, when an operator issues the
constitution with real custody and a live system presents this role's facts.
Nothing in this pilot may be described as a running or governed *agent* — the
non-claims of `ACC-FC` §3 and `ACC-IA` carry forward unchanged.

---

## 2. The role document, field by field

One committed JSON document (per `IR-1=A`):
`packages/integration/agent-constitution-activation/pilot/invoice-reconciler-role.v1.json`
— **data, not code**: outside `src/`, never shipped in the wheel, no Python
name in it, constructed into the live contract type only inside tests. It
carries the governed reference as its identity plus the twelve contract fields:

| Field | Proposed value |
|---|---|
| *(document identity)* `role_contract_ref` | `ugence.roles/ugence/invoice-reconciler/v1` |
| `schema_version` | `1.0` |
| `tenant_id` | `ugence` |
| `created_at` | `2026-09-01T09:00:00Z` (the declaration instant; no clock is read anywhere) |
| `role_contract_id` | `invoice-reconciler` |
| `primary_function` | `reconcile supplier invoices against ledger entries` |
| `permitted_tool_scopes` | `("invoice.read", "ledger.read")` — the full ratified ceiling, nothing beyond it |
| `permitted_candidate_dispositions` | the full ratified closed vocabulary (4 members) |
| `permitted_review_actions` | the full ratified closed vocabulary (2 members) |
| `escalation_role_ref` | `ugence.roles/ugence/reconciliation-supervisor/v1` |
| `activation_status` | `ACTIVE` |
| `strategy_policy_ref` | `policy-authority/strategy-permission/reconciliation` |
| `constitution_ref` | `ugence.agent-constitution/ugence/baseline/v1` |

Disclosures, put to ratification with the table: `[I]` `role_contract_ref` is
the **resolution key** — the value the constitution's `governed_role_refs`
names and the reference map is keyed by — while `role_contract_id` is the
contract's own internal id; the document carries both, and the tests pin the
reference against the ratified constitution content. `[I]` `constitution_ref`
equals the signed reference exactly, which is what makes this role bindable at
all: the resolver's fourth post-check and the advisory builders' stamping
equality both compare against it. `[I]` Declaring the **full** bounds means the
conformance predicate's `True` is currently unconditional for this role; the
proof therefore includes a widened-declaration control (a write scope) that
answers `False`, so the pilot demonstrates bite, not vacuity. `[G]`
`escalation_role_ref` and `strategy_policy_ref` name things no artifact in this
repository declares; they are opaque C5a references on the role surface, and
this pilot neither creates nor governs their targets — carried as gaps, exactly
as the role's own reference was carried until now.

---

## 3. The three-leg proof

All inside the activation distribution's suite, on ephemeral in-process keys,
with the ratified `ACC-FC` content values and nothing else (per `IR-3=A`):

1. **Document → contract.** The committed JSON parses, constructs the live
   role contract (fragment-assembled lookup), and every declaration in the
   document equals the constructed contract's value — so the document cannot
   drift from what the tests actually prove.
2. **Conformance with bite.** `role_facts_conform` over the ratified
   constitution content and facts read **from the document** answers `True`;
   the widened-scope control (`ledger.write`) answers `False`; and the pinning
   assertions hold: the constitution's `governed_role_refs` contains the
   document's `role_contract_ref`, and the document's `constitution_ref`
   equals the signed `agent_constitution_ref`.
3. **The full chain, this role.** Issue → activate → resolve → bind → conform
   through the shipped `ACC-IA` root, with the bound advisory built over
   **this role document's contract** rather than an invented fixture — the
   `ACC-AM-2` stamping seam fed by the genuinely resolved constitution, the
   advisory identity replaying, and a mismatched-reference control refusing.

`[I]` No new machinery is needed for any leg: leg 3 re-drives code the
`ACC-IA-5` proof already exercises, substituting the committed declaration for
the fixture role. That is the entire point of the pilot — the machinery is
done, and the role is now real.

---

## 4. Packaging, scans and versioning

Per `IR-4=A`: the pilot adds the JSON document and one test module to the
existing activation distribution — `pilot/` and `tests/` are outside `src/`
and outside the wheel, so **the shipped artifact is byte-identical and no
version moves**; the CHANGELOG gains a dated note recording the pilot as a
repository act, not a release. The shared agent-constitution CI workflow
already runs the activation suite on these paths. Disciplines carried
unchanged: the projection scan (data file exempt by format, tests lawful by
the established lookup), the reserved-vocabulary scan (enum values appear in
the JSON as data the scan does not read, and in tests only as enum-derived
values, never fresh literals in source), authority via
`ugence_policy_authority.api` only, no clock reads, no secrets in any form.

---

## 5. Owner-decision register (five)

| # | Decision | A (recommended) | B |
|---|---|---|---|
| IR-1 | The role artifact's home and form | one committed JSON document, `packages/integration/agent-constitution-activation/pilot/invoice-reconciler-role.v1.json` — data outside `src/`, never shipped, constructed into the live contract only inside tests | tests-only fixture, no committed artifact; the `ACC-FC-3` "no role artifact exists" gap stays open |
| IR-2 | The role's declared content | the §2 table whole, with its four disclosures — full ratified bounds declared, the reference and signed-reference equalities pinned | owner supplies different values; every declaration must still sit inside the ratified bounds and the two reference equalities must hold |
| IR-3 | Proof scope | the three-leg proof of §3: document→contract equality, conformance with the widened-scope `False` control and the two pinning assertions, and the full chain re-driven over this role with a mismatched-reference refusal control | legs 1–2 only; the chain leg deferred |
| IR-4 | Packaging and versioning | document + one test module in the activation distribution; wheel byte-identical, **no version moves**; CHANGELOG note records the pilot | a separate pilot package, or a version bump; owner names which |
| IR-5 | What the pilot commits, and sequencing | the pilot commits a governed **declaration** and its proof — no agent, no compute, no evidence access, no production issuance, no lifecycle act, and no claim that a reconciler runs or is governed in operation; the lifecycle round (structured supersession and suspension, roadmap step 3) is **not** commissioned by this ballot | also commission the lifecycle round's scoping ballot now, as its own document |

Couplings, disclosed: `IR-2` and `IR-3` interact through the two reference
equalities — both sides of each come from ratified text plus the §2 table, so
ratifying the table whole keeps them consistent by construction. `IR-1=B`
empties leg 1 of `IR-3` and leaves the `ACC-FC-3` gap in place; that is a
lawful choice, and the row exists so it is a chosen one. No other pair
interacts. The fixed surface below is put to ratification whole alongside the
rows, with the standing precedence rule: where an `IR` row and the fixed
surface overlap, **the `IR` ruling governs**.

---

## 6. Paste-ready owner-ratification ballot

```
Agent Constitution — invoice-reconciler pilot scoping ballot
Baseline: rasaha/symbolu default head ac70994d9d4478628a17e96d0a656418302fbbdf
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-* and ACC-IA-* as ratified.
Answer each with A or B. A = the recommended path.

PILOT_SURFACE  Ratify the fixed surface: the pilot is a committed declaration and
      its proof, driven through the shipped ACC-IA orchestration — no new
      authority surface, no change to any existing package's src, version or
      public_api.json; no signing key, trust root or approval artifact enters the
      repository (proof runs on ephemeral in-process keys); the only constitution
      values used are the ratified ACC-FC content values, and every role
      declaration sits inside the ratified bounds; no agent runs, is enrolled or
      is claimed governed in operation; /clauses/v2 stays out of scope and
      ACC-AM-4's re-arm stays untriggered — with the precedence rule: where an IR
      row and this surface overlap, the IR ruling governs.  YES/NO.

IR-1  The role artifact's home and form.
      A = one committed JSON document,
          packages/integration/agent-constitution-activation/pilot/
          invoice-reconciler-role.v1.json — data outside src/, never shipped in
          the wheel, constructed into the live contract type only inside tests.
      B = tests-only fixture, no committed artifact; the ACC-FC-3 gap stays open.

IR-2  The role's declared content (§2, arrives whole).
      A = the §2 table with its disclosures: the governed reference as document
          identity; tenant ugence; role_contract_id invoice-reconciler; full
          ratified disposition and review-action vocabularies; tool scopes
          exactly (invoice.read, ledger.read); constitution_ref equal to the
          signed reference; the named escalation and strategy references carried
          as opaque, ungoverned C5a values.
      B = the owner supplies different values; declarations must still sit
          inside the ratified bounds and both reference equalities must hold.

IR-3  Proof scope.
      A = the three-leg proof: document -> contract equality; conformance True
          from the document's facts with a widened-scope False control and the
          two pinning assertions; and the full issue -> activate -> resolve ->
          bind -> conform chain re-driven over this role, with a
          mismatched-reference refusal control.
      B = legs 1-2 only; the chain leg deferred.

IR-4  Packaging and versioning.
      A = document + one test module in the activation distribution; the shipped
          wheel is byte-identical and no version moves; a CHANGELOG note records
          the pilot as a repository act.
      B = a separate pilot package, or a version bump; the owner names which.

IR-5  Commitment and sequencing.
      A = the pilot commits a governed declaration and its proof only — no
          agent, no compute, no evidence access, no production issuance, no
          lifecycle act; the lifecycle round (roadmap step 3) is not
          commissioned by this ballot.
      B = additionally commission the lifecycle round's scoping ballot now, as
          its own document.

Record as: PILOT_SURFACE=? IR-1=? IR-2=? IR-3=? IR-4=? IR-5=?
No implementation is authorized by this ballot; register labels and the
implementation-authority ruling belong to the ratification ADR that records
these answers and to the separate ruling that follows it.
```

---

## 7. Paste-ready independent-review prompt

```
Read-only independent review. Do not modify files, create a branch, commit, push or open a PR.

Repository: rasaha/symbolu
Expected default-branch head: ac70994d9d4478628a17e96d0a656418302fbbdf
Artifact under review: docs/architecture/AGENT_CONSTITUTION_INVOICE_RECONCILER_PILOT_SCOPING_BALLOT.md

Verify the baseline first (head, clean tree, the ACC-IA change set merged via PR #1534,
proposer 0.4.0, all three constitution distributions 0.1.0, freeze digest
d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036 unchanged); stop on
mismatch. Then judge against the repository, not this document's prose:

1. Is every §2 value constructible on the proposer's twelve-field role surface exactly
   as stated, does every declaration sit inside the ratified ACC-FC bounds, and do the
   two reference equalities (governed_role_refs membership; constitution_ref == the
   signed agent_constitution_ref) hold against the ratified content?
2. Is the claim that a committed JSON document cannot trip the repository-wide
   role-projection scan accurate against that scan's own source, and is the
   fragment-assembled lookup genuinely the established lawful pattern for the tests?
3. Is the "bite, not vacuity" disclosure honest — do the full declared bounds make the
   predicate's True unconditional for this role today, and does the proposed
   widened-scope control genuinely answer False under the ratified content?
4. Does anything here run, enrol or claim to govern an agent; issue anything in
   production; commit a secret; move any package's version or src; create a new
   authority; trigger ACC-AM-4; or touch /clauses/v2?
5. Are the five IR rows genuinely open decisions with defensible recommendations, and
   is anything described as implemented, committed, proven or governed that is not?
Return SOUND, SOUND_WITH_CORRECTIONS, or BLOCKED, findings cited to file:line.
```

---

## 8. Readiness verdict

**READY_FOR_OWNER_RATIFICATION.** Baseline verified in full; the substantive
freeze digest is unchanged; five owner decisions plus the fixed-surface
question are open, and none is settled here. After ratification: the
ratification ADR recording the answers and assigning register labels; a
separate implementation-authority ruling; then one small change set — the role
document, one test module, a CHANGELOG note — at whose merge the ratified v1
Constitution demonstrably governs a real, named, committed role declaration
end to end, which is what remains provable inside a repository. Governance of
the running reconciler is then a deployment fact away: the same machinery, real
custody, live facts.
