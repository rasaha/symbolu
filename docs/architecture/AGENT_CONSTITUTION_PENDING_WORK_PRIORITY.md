# Agent Constitution — pending work, prioritised

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
