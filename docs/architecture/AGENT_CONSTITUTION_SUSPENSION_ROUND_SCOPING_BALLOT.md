# Agent Constitution — suspension round scoping ballot

**The load-bearing question:** `ACC-LC-3` deferred suspension and gave a reason.
**That reason no longer holds.** It ruled that *"a reversible pause needs a state
absent from the ratified closed set `ADMITTED_LIFECYCLE_STATES`, which makes it a
vocabulary act rather than a mechanics act."* `[V]` The supersession mechanism
the **same round** then shipped never touches `lifecycle_state` at all: it
appends to its own store and denies at resolution with a typed reason, leaving
the signed artifact's lifecycle label untouched
(`policy-authority/core/supersession.py` contains no lifecycle reference;
`core/resolution.py:293-296`). Suspension can follow that exact shape.

**The cost is real, but it is a different cost.** Suspension still extends a
closed vocabulary — just `PolicyResolutionReason`, not
`ADMITTED_LIFECYCLE_STATES` — and `[V]` that vocabulary is mirrored,
**total and injective**, by a consumer distribution
(`cloud-scaling-policy-authenticity/tests/test_typed_outcomes.py:26,32`). That is
precisely the coupling that made `ACC-LC-IA-BASE`'s surface unsatisfiable and
forced the `A1` amendment. This round starts knowing it.

**Status:** scoping/design ballot — documentation only. **No implementation is
authorized by this ballot.** **Date:** 2026-09-01.

**Authorities:** `OD-C1..OD-C5`, `ACC-S1-*`, `ACC-AM-*`, `ACC-FC-*`, `ACC-IA-*`,
`ACC-PR-*`, `ACC-LC-*`, `ACC-SU-*` and `ACC-FC5R-*` as ratified.

---

## 0. Baseline, and what changed since the deferral

`[V]` Default head `65c90d31`, clean tree. Policy Authority `0.2.0`;
`agent-constitution-policy` `0.2.0`; conformance and activation `0.1.0`.

* `[V]` **No suspension concept exists** in any source file of the authority or
  the three constitution distributions — the substring `SUSPENDED` appears
  nowhere. Unchanged since `ACC-LC-3`.
* `[V]` **Supersession set a reusable pattern**: a third append-only store, a
  signed record, and resolution consulting it — with `lifecycle_state` never
  written. Suspension needs the same three parts plus one thing supersession
  never needed: **reversal**.
* `[V]` **Revocation is terminal and remains the only pause available**, with
  five reason codes (`core/statuses.py:149-153`). `ACC-LC-3`'s ratified bite —
  an operator whose approval is questioned but not withdrawn has only the
  terminal instrument — is still live.
* `[V]` **Extending `PolicyResolutionReason` is not free**: a consumer maps it
  one-for-one, total and injective, so each new reason needs a distinct new
  outcome member there.

`[I]` **What makes suspension genuinely novel.** Revocation and supersession are
one-way: a record appears and the answer changes once, forever. Suspension must
answer differently at two instants with **no new record between them** in the
naive design — or, if reinstatement is itself a record, resolution must evaluate
an ordered *sequence* rather than the presence of a record. That is the first
time this authority would hold state whose current value is not simply "a record
exists".

---

## 1. Owner-decision register (five)

| Row | Question | Recommended (A) | Alternative (B) |
|---|---|---|---|
| `SUSP-1` | Whether suspension touches the **lifecycle vocabulary** | **no** — follow supersession's shipped shape: an append-only store, signed records, resolution consulting it, and `lifecycle_state` never written. `ADMITTED_LIFECYCLE_STATES` stays closed as ratified, and `ACC-LC-3`'s stated premise is corrected rather than inherited | add a `SUSPENDED` lifecycle state, as `ACC-LC-3` assumed, accepting a change to a ratified closed set and to every artifact contract that mirrors it |
| `SUSP-2` | How **reversal** is represented | **append-only, ordered**: suspend and reinstate are both signed records in one store; resolution reads the latest applicable record at `as_of` and denies only if it is a suspension. Nothing is ever deleted or mutated, so the history of pauses is legible | a single mutable per-coordinate flag, cleared on reinstatement — simpler to read, but it destroys the record of what happened |
| `SUSP-3` | Who may **reinstate** | a key entitled for the act, and the ballot's recommended reading is that **suspension and reinstatement are one entitlement**, not two: an authority that may pause may unpause, and splitting them creates a state only a second party can exit | separate entitlements for suspend and reinstate |
| `SUSP-4` | The **consumer surface**, known in advance | the round's surface **must name** the new `PolicyResolutionReason` member(s) and, with them, the consumer outcome members required by `cloud-scaling-policy-authenticity`'s total, injective mapping — enumerated in the implementation-authority ballot **before** the surface is bounded (`ACC-SU-4`'s standing obligation) | bound the surface to the authority alone and handle consumers as they surface |
| `SUSP-5` | What the round **commits** | contract, design and ratification only — documentation, no source change; implementation is a separate change set under the ruling that follows | additionally authorize the implementation change set now |

Couplings, disclosed: `SUSP-1` and `SUSP-2` interact — `SUSP-1=B` (a lifecycle
state) makes `SUSP-2`'s ordered-record design largely moot, since the state
itself would carry the answer, and imports the whole cost of amending a ratified
closed vocabulary. `SUSP-4` applies whichever way `SUSP-1` is ruled. No other
pair interacts.

`[G]` **The standing bite, unchanged:** suspension, like supersession before it,
will be **unexercisable** on the day it lands — `ACC-LC-IA-3` refuses an absent
predecessor, nothing has been issued, and the `ACC-FC-5` gates are shut
(`ACC-FC5R-*` names the order for closing them but closes none). This round
buys an instrument for a deployment that does not yet exist.

---

## 2. The fixed surface put to ratification

Ratified whole, with the precedence rule: **where a `SUSP` row and this surface
overlap, the row governs.**

A contract and design act over policy-version lifecycle only: no new authority;
`OD-C4=A` holds untouched — this is the lifecycle of a signed policy artifact,
never an agent's or a role's; `OD-C3=B` holds; no signing key, trust root or
approval artifact enters the repository and no issuance, revocation,
supersession or suspension is performed; **no already-valid artifact is
invalidated and no existing refusal is relaxed** — the unstructured
`supersedes_ref` keeps being refused and revocation stays terminal and separate;
no existing digest moves; `/clauses/v2` stays out of scope and `ACC-AM-4`'s
re-arm stays untriggered; the `ACC-FC-5` gates are neither closed nor advanced;
no agent runs, is enrolled or is claimed governed. **YES/NO.**

---

## 3. Paste-ready owner-ratification ballot

```
Agent Constitution — suspension round scoping ballot
Baseline: rasaha/symbolu default head 65c90d31
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-*, ACC-IA-*, ACC-PR-*,
ACC-LC-*, ACC-SU-* and ACC-FC5R-* as ratified. Answer each with A or B.
A = the recommended path.

SUSP_SURFACE  Ratify the fixed surface: a contract and design act over
      policy-version lifecycle only; no new authority; OD-C4=A holds untouched
      (a signed policy artifact's lifecycle, never an agent's or a role's);
      OD-C3=B holds; no signing key, trust root or approval artifact enters the
      repository and no issuance, revocation, supersession or suspension is
      performed; no already-valid artifact is invalidated, no existing refusal
      relaxed -- the unstructured supersedes_ref keeps being refused and
      revocation stays terminal and separate -- and no existing digest moves;
      /clauses/v2 stays out of scope and ACC-AM-4's re-arm stays untriggered;
      the ACC-FC-5 gates are neither closed nor advanced; no agent runs, is
      enrolled or is claimed governed -- with the precedence rule: where a SUSP
      row and this surface overlap, the SUSP ruling governs.  YES/NO.

SUSP-1  Whether suspension touches the lifecycle vocabulary.
      A = no. Follow supersession's shipped shape -- an append-only store,
          signed records, resolution consulting it -- with lifecycle_state never
          written. ADMITTED_LIFECYCLE_STATES stays closed as ratified, and
          ACC-LC-3's stated premise is corrected rather than inherited.
      B = add a SUSPENDED lifecycle state as ACC-LC-3 assumed, accepting a
          change to a ratified closed set and to every contract mirroring it.

SUSP-2  How reversal is represented.
      A = append-only and ordered: suspend and reinstate are both signed records
          in one store; resolution reads the latest applicable record at as_of
          and denies only if it is a suspension. Nothing is deleted or mutated,
          so the history of pauses stays legible.
      B = a single mutable per-coordinate flag, cleared on reinstatement.

SUSP-3  Who may reinstate.
      A = one entitlement covers both acts: an authority that may pause may
          unpause. Splitting them creates a state only a second party can exit.
      B = separate entitlements for suspend and reinstate.

SUSP-4  The consumer surface, known in advance.
      A = the round's surface must name the new PolicyResolutionReason
          member(s) and the consumer outcome members required by
          cloud-scaling-policy-authenticity's total, injective mapping,
          enumerated in the implementation-authority ballot BEFORE the surface
          is bounded (ACC-SU-4's standing obligation).
      B = bound the surface to the authority alone; handle consumers as they
          surface.

SUSP-5  What the round commits.
      A = contract, design and ratification only; implementation is a separate
          change set under the ruling that follows.
      B = additionally authorize the implementation change set now.

Record as: SUSP_SURFACE=? SUSP-1=? SUSP-2=? SUSP-3=? SUSP-4=? SUSP-5=?
No implementation is authorized by this ballot; register labels and the
implementation-authority ruling belong to the ratification ADR that records
these answers and to the separate ruling that follows it.
```

---

## 4. Paste-ready independent-review prompt

```
Review, do not implement. Repository rasaha/symbolu at default head 65c90d31.
Read docs/architecture/AGENT_CONSTITUTION_SUSPENSION_ROUND_SCOPING_BALLOT.md and
judge:

1. Is the central claim true -- that supersession never writes lifecycle_state,
   so ACC-LC-3's stated reason for deferring suspension does not hold? If the
   claim is wrong, the ballot's framing collapses; say so plainly.
2. Is SUSP-2=A's ordered-record design sound at RESOLUTION time? Construct a
   sequence of suspend/reinstate records and an as_of for which "the latest
   applicable record" is ambiguous or gives the wrong answer -- equal
   timestamps, out-of-order arrival, a reinstate with no prior suspend.
3. Does SUSP-3=A create a hazard: one entitlement means whoever can pause can
   unpause. Is that right, or does a paused policy need a second party to
   release it?
4. Does any option touch a role or an agent (OD-C4=A), relax a refusal, or move
   an existing digest?

Report findings labelled [V]/[I]/[R]/[G] with file:line support.
```

---

## 5. Readiness verdict

`[R]` **Ready to put, with its premise corrected in the open.** The round is
still worth convening — `ACC-LC-3`'s *conclusion* (its own round) stands — but
its stated *reason* is falsified by what the same round shipped, and inheriting
a false reason would have set this round's surface wrongly. `[G]` `SUSP-2` is
the row where being wrong is expensive: reversal is the first state in this
authority whose current value is not simply "a record exists", and §4 asks a
reviewer to attack the ordering rule directly.
