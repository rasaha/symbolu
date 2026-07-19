# Future Work — Enterprise Governance Track

**Status:** Archival record. Cross-references the frozen architecture
([`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md))
and [`ARCHITECTURE_FREEZE.md`](./ARCHITECTURE_FREEZE.md). Nothing here reopens a
frozen decision.

---

## Immediate

**None.**

The track is frozen and research-complete pending real enterprise validation. No
further research, architecture, ontology, or synthetic-experiment work is to be
performed on this track now. Doing more synthetic work would add no evidence the
current work does not already provide.

## Requires real enterprise participation

Every open question below needs **real operational data** and cannot be answered
synthetically. These are the questions a real pilot exists to resolve (see
[`RESUME_GUIDE.md`](./RESUME_GUIDE.md) and
[`../enterprise_pilot/REAL_ENTERPRISE_PILOT_CHECKLIST.md`](../enterprise_pilot/REAL_ENTERPRISE_PILOT_CHECKLIST.md)):

1. **Precision on real workflows** — of the findings emitted, how many correspond
   to real governance problems (against enterprise ground truth)?
2. **Recall against known-bad cases** — of the enterprise's known historical
   failures, how many would the invariants have surfaced?
3. **Real false-positive rate** — do clean real workflows stay finding-free as the
   synthetic clean variants did?
4. **Net-new versus *real* controls** — against the enterprise's actual approval
   matrices / reconciliation jobs / rule engines / access reviews, what remains
   net-new (not what a modeled baseline says)?
5. **Capability-set sufficiency** — can real workflows be fully expressed by the 10
   frozen capability groups, or do they reveal an architecture-coverage gap (to be
   recorded, per the freeze, not silently patched)?
6. **Shared-invariant reuse at breadth** — do the 11 invariants govern *many* real,
   heterogeneous workflows unchanged, or only a favorable few?
7. **Reconciliation / audit improvement** — is there a measurable improvement in
   real reconciliation or audit outcomes?
8. **Preventive value** — can at least one net-new finding be shown to precede a
   real invalid execution (the strongest possible signal)?
9. **Which invariants graduate from audit to enforcement** — this is explicitly
   *not frozen* and is a data-driven decision; integration-closure and
   prohibited-capability-exposure are the named first candidates, but only after
   validated data.

## Future research (genuinely new questions only)

These are new lines that do **not** reopen frozen decisions. Pursue only if a real
pilot first establishes baseline value; otherwise they are premature.

1. **Adapter-generation ergonomics** — reducing the effort to write a read-only
   adapter for a new source (tooling/scaffolding), without changing the evidence
   model.
2. **Cross-workflow dependency graphs at scale** — how cross-system dependency and
   closure findings compose when many real workflows interact (a genuinely new
   question about aggregate behavior, not a model change).
3. **Human-review workflow design** — how enterprise reviewers best consume,
   triage, and act on advisory findings (an HCI/operations question, out of the
   frozen model's scope).
4. **Longitudinal drift** — whether verified authority/provenance stays accurate as
   real source systems change over time.

## Explicitly out of scope (do not do)

- Redesigning or extending the twelve-layer ontology. *(Frozen; rejected as runtime
  schema.)*
- Adding capability groups or invariants for symmetry or on opinion. *(Requires new
  evidence.)*
- More synthetic scenarios, fixtures, or metrics. *(Add no evidence.)*
- Wiring ActionGate to any enterprise write/execute path before validated data.
- Any efficacy, ROI, or production-readiness claim.

## Cross-references

- Freeze scope and change bar: [`ARCHITECTURE_FREEZE.md`](./ARCHITECTURE_FREEZE.md)
- How to resume: [`RESUME_GUIDE.md`](./RESUME_GUIDE.md)
- Metric definitions (all `TBD`): [`../enterprise_pilot/ENTERPRISE_METRICS.md`](../enterprise_pilot/ENTERPRISE_METRICS.md)
