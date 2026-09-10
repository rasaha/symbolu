# Deferral record — StoryGraph enforcement promotion

**Ruled by the repository owner, 2026-09-09: deferred.** StoryGraph is retained as an
optional, advisory, `RESEARCH_ONLY` capability. No shadow pilot is funded and no
enforcement integration is undertaken while
[`ENFORCEMENT_PROMOTION_CHECKLIST.md`](ENFORCEMENT_PROMOTION_CHECKLIST.md) stands at
0 of 10 and [`SHADOW_PILOT_REPORT_TEMPLATE.md`](SHADOW_PILOT_REPORT_TEMPLATE.md) is
still a template.

## Deferred is not failed

This must not be represented, in this repository or outside it, as a capability that
failed, was abandoned, was withdrawn, or was found defective. Nothing about
StoryGraph's implementation prompted this ruling. Its package suite is green (316
tests), its authoritative path is deterministic and replayable from an event log, and
its evidence ledger records three frozen evaluation runs with their hashes, metrics
and verdicts intact — including the two it superseded rather than edited.

What is deferred is **promotion**: the decision to spend on a shadow pilot and an
enforcement integration. The capability stays available, stays advisory, and stays
maintained at its current maturity. A reader encountering StoryGraph should understand
it as "not yet taken up", never as "tried and rejected".

## What remains true while deferred

- **Advisory / evidentiary only.** `OBSERVE` / `ESCALATE` / `UNAVAILABLE` findings and
  evidence records classed `ADVISORY` with an `OBSERVE`/`ESCALATE` effect ceiling. It
  emits no `ALLOW`/`DENY`/`AUTHORIZE`/`BLOCK`/`EXECUTE`/`CLEAR` and holds no
  action-authorization, binding-decision, operational-clearance or execution
  authority.
- **Synthetic-only validation.** No enterprise data is bundled; the historical-replay
  path ships templates and a synthetic reference fixture.
- **No enforcement, global or scoped.** The prohibitions in the promotion checklist's
  *Prohibited in this phase* section continue to bind, unchanged, for as long as this
  deferral stands.

## Re-entry conditions

Promotion may be reconsidered when **all five** are satisfied. They are cumulative;
none substitutes for another, and meeting them opens the checklist rather than
bypassing it — the ten criteria in `ENFORCEMENT_PROMOTION_CHECKLIST.md` still have to
be demonstrated on a frozen workflow afterwards.

1. **A named sponsor and a named use case.** A specific accountable owner and a
   specific tenant, workflow and action type. "Sequence risk in general" is not a use
   case, and an unnamed sponsor is not a sponsor.
2. **A completed pilot protocol**, written and agreed *before* any data is observed:
   scope, duration, the evidence-discipline label each figure will carry, and what
   would count as a negative result.
3. **A populated shadow-pilot report** — the template filled from an actual bounded
   run, with each figure carrying its `Measured — …` / `Modeled — …` / `NOT RUN` /
   `REQUIRES ENTERPRISE DATA` label, not a report asserting readiness in prose.
4. **Pre-registered acceptance criteria**, in particular a false-escalation threshold
   and a sustainable human-review volume, both fixed before the run rather than read
   off its results.
5. **Confirmation that the output remains non-approval-bearing.** Re-entry must not
   quietly convert an advisory finding into an authorization. Any binding consequence
   stays owned by the authoritative policy, per the checklist's consequence mapping,
   and `BLOCK` continues to require a separately-approved, pinned high-consequence
   tuple.

## What would reopen this earlier

A defect found in the current advisory behaviour is not governed by this record — that
is ordinary maintenance and proceeds normally. This deferral governs promotion spend
only.
