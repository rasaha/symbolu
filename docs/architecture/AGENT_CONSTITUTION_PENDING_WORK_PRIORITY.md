# Agent Constitution — pending work, prioritised

> # ⚠ RETIRED — 2026-09-09. Do not plan from this document.
>
> **Retired as an authoritative plan by `ACC-PWP-1`**
> ([`ADR_UGENCE_AGENT_CONSTITUTION_RECONCILIATION_SUSPENSION_AND_OVERLAP_RULINGS.md`](ADR_UGENCE_AGENT_CONSTITUTION_RECONCILIATION_SUSPENSION_AND_OVERLAP_RULINGS.md),
> which lands in the same commit as this header). It is preserved **verbatim
> below as historical evidence** of what was outstanding on 2026-09-01, and for
> no other purpose. `[R]` It rules nothing, and it is superseded as a statement
> of current fact.
>
> **Three specific things in it are no longer current** `[V]`:
>
> 1. **Its baseline does not exist.** `ab0205df` is **not an object in this
>    repository's history**, so nothing below can be re-verified against it.
> 2. **Its versions are behind the tree.** It pins proposer `0.4.0`, activation
>    `0.1.0` and authority `0.2.0`; the tree carries `0.6.0`, `0.2.0` and
>    `0.3.1`. Its public-name counts moved with them (the proposer's curated
>    surface is fifty-two, not fifty-one).
> 3. **Its P0 is closed.** The `LR-1`/`LR-2` `approval_digest` exclusion was
>    ruled `LR-1=A LR-2=A` in
>    `ADR_UGENCE_AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_AMENDMENT.md`
>    (commit `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00`). Its P1 items were
>    ruled the same day — `CV2_SURFACE=YES CV2-1=A`… and
>    `SUSP_SURFACE=YES SUSP-1=A`…
>
> **Every still-valid open item was migrated before retirement** (`ACC-PWP-1`
> §4). In particular, item 5 — cross-artifact governed-role overlap — is now the
> ratified `ACC-OVL` invariant, with a sequencing constraint: **no second
> constitution may be issued until it is implemented and verified.**
>
> **Where to look instead**, by immutable commit SHA:
>
> | For | Read | Commit |
> |---|---|---|
> | The scoping rulings `OD-C1`–`OD-C5` | `ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
> | The first slice | `ADR_UGENCE_AGENT_CONSTITUTION_FIRST_SLICE_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
> | `OD-C1=B` and `ACC-AM-IMPL=YES` | `ADR_UGENCE_AGENT_CONSTITUTION_AMENDMENT_ROUND_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
> | Issuance & activation | `ADR_UGENCE_AGENT_CONSTITUTION_ISSUANCE_ACTIVATION_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
> | The first-constitution content and the `ACC-FC-5` gates | `ADR_UGENCE_AGENT_CONSTITUTION_FIRST_CONSTITUTION_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
> | The gate runbook and `ACC-FC5R-4`'s narrowed permitted set | `ADR_UGENCE_AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_RATIFICATION.md`, then `…_AMENDMENT.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
> | Lifecycle, supersession and suspension | `ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_ROUND_RATIFICATION.md`, `…_SUSPENSION_ROUND_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
> | `ACC-COUPLING`, `ACC-FACTS`, `ACC-ATTESTER` | `ADR_UGENCE_AGENT_CONSTITUTION_LIVE_ATTESTATION_SCOPING.md` | `c0e48ca3e89631ca6eab978a3a1037d114cd082a` |
>
> `[V]` **The one fact below that is unchanged** is the one that mattered most:
> no constitution has ever been issued, no `ACC-FC-5` gate is closed, and **no
> pull request can advance gates 1 or 2**.

**Working document, not a ratification.** It records what is outstanding and in
what order I would take it. It rules nothing, authorises nothing, and every
ballot it references stays unanswered until the owner answers it.

**Baseline:** default head `ab0205df`, clean tree, all checks green. **Date:**
2026-09-01.

**The single organising fact:** the structural work is finished and the binding
constraint is operational. `[V]` No constitution has ever been issued, so
supersession, activation, conformance and the family opt-in are all real,
proven, and **unexercisable**. More contract capability does not change that;
only closing the `ACC-FC-5` gates does.

---

## P0 — before any gate closure is recorded

### 1. Rule `LR-1` / `LR-2` — the `approval_digest` exclusion

`[V]` `ACC-FC5R-4` permits *"public identifiers and digests"*, and the
unqualified word admits `approval_digest`, whose preimage is an external
approval artifact of unknown entropy. `[V]` Nothing has leaked: no gate closed,
no closure recorded, no approval digest in `docs/architecture/`.

**Why P0:** the permissive text is the **operative rule** until it is narrowed,
and the exposure becomes live the moment someone records a closure in good
faith. A secret committed once is committed in history.

**Cost:** two letters. The amendment is one-directional — it can only forbid
more. Ballot in `AGENT_CONSTITUTION_FC5_4_LEAK_REVIEW.md` §4.

---

## P1 — cheap rulings that close open questions

### 2. Rule the `/clauses/v2` ballot — as **`CV2-1=A`**, defer

Counter-intuitively early, and precisely *because* the recommended answer is
"not yet". Ruling it costs nothing, removes a standing open question, and
**pre-settles the round's shape** (`CV2-2`..`CV2-5`) for whenever it is
convened. Leaving it unanswered keeps a decision live that has already been
reasoned through.

`[V]` Ratifying clause content re-arms `ACC-AM-4`, whose re-derivation *"gets
its own round"* — so commissioning commits two rounds on top of capability
nothing can exercise.

### 3. Rule the suspension ballot — but rule the two questions separately

The ballot's rows and the decision to **implement** are different questions.
Ruling `SUSP_SURFACE`/`SUSP-1..5` records the design cheaply; authorising the
change set commits a full round (ratification ADR → implementation-authority
ballot → implementation, including every consumer of `PolicyResolutionReason`).

`[R]` If suspension is ruled, `SUSP-4` obliges the implementation-authority
ballot to enumerate those consumers **before** bounding its surface. That
obligation exists because skipping it cost two CI cycles in the `ACC-LC` round.

### 4. Reconcile the proposer README's status section

`[V]` **Much smaller than reported — see §Corrections.** The one real item:
`packages/capabilities/agentic-proposer/README.md` describes the surface only
through `0.3.0` and never explains the `0.4.0` constitution binding. A living
document that stops one version short of what it ships.

---

## P2 — hardening, with a named trigger rather than a date

### 5. Cross-artifact governed-role overlap

`[V]` Issuance has **no** refusal for two separately issued constitutions
claiming the same governed role: `governed_role_refs` is not consulted in
`core/issuance.py`. `[V]` The backstop is real but downstream —
`populate_reference_map` raises `ReferenceMapConflictError` at activation.

**Trigger, not a date:** harmless while exactly one constitution exists; it
becomes reachable the moment a **second** does. Supersession now makes second
constitutions expected, so close this **before the second constitution**, not
"eventually". Ranked above the item below because it has a foreseeable trigger.

### 6. Global `policy_family` uniqueness in the authority core

`[V]` The core registry has no global uniqueness guard; the constitution family
supplies a strong registration-time collision guard (`ACC-S1-Q3`) that protects
every supported composition path. A defence-in-depth gap, not a live hole.

### 7. The two malformed-resolver edge cases

`[V]` Disclosed in the proposer's own `version.py:27,37,45`: a type-alien value
can escape as `TypeError`, and an attribute failing after the presence guard as
`AttributeError`. Accurately documented; closing them needs an owner decision
about the boundary's contract, not a bug fix.

---

## P3 — operational, and not repository work

### 8. Close the four `ACC-FC-5` gates

`ACC-FC5R-1` fixes the order, and `[V]` the order is **forced, not chosen**:
gates 1 and 2 in parallel (custody; approving authority) → gate 3 (composition)
→ the mandatory ephemeral-key rehearsal → first issuance → gate 4 (reference-map
population, which derives only from an issued record).

**No PR can advance gates 1 or 2.** This is the item everything else waits on,
and the only one that cannot be done here. **Resolve P0 first** — gate closures
produce records, and the rule governing what may be recorded is the one under
amendment.

---

## Corrections to the analysis this document was built from

`[R]` Two claims in the source analysis do not survive checking, and the
ordering above reflects the corrected picture.

* **"Documentation drift — several documents still state the constitution
  *does not exist*."** `[V]` **Substantially wrong.** The flagged sentences say
  *"No constitution exists or is issued"* — which is **still true**; none has
  been issued. They also sit in **ADRs**, which are historical records pinned to
  a baseline; editing them to reflect later state would be worse practice, not
  better. `[V]` The MVP-readiness passage is **conditional and still accurate**
  (*"When the document does exist, the projection must be re-derived"*) — a
  standing `ACC-AM-4` obligation whose trigger has not fired. `[V]` No living
  spec or README asserts a false current-state claim. The item collapses from a
  multi-document reconciliation to **one README section** (item 4).
* **"Cross-artifact overlap — not currently a blocker."** `[V]` True today, but
  the framing hides a foreseeable trigger. Ranked at P2 **with that trigger
  named** rather than left undated (item 5).

`[V]` Everything else checked out: versions and public-name counts (proposer
`0.4.0`/51, family `0.2.0`/27, conformance `0.1.0`/13, activation `0.1.0`/13,
authority `0.2.0`/72); no `TODO`, `FIXME` or `NotImplementedError` in any
production source of these packages; and both hardening gaps are real.

---

## The sequence, in one line

Rule `LR` → rule `CV2` as defer → rule suspension (design now, implementation
separately) → **close gates 1 and 2** → rehearsal → first issuance → reference
map → then, and only then, the substantive `/clauses/v2` and `ACC-AM-4`
re-derivation rounds.

`[G]` Everything above P3 is cheap. P3 is the whole difference between a
governance system that is proven and one that is *in force*, and it is not
repository work.
