# Known Limitations — Enterprise Governance Track

**Status:** Archival record. Every limitation is stated explicitly and without
hedging. Cross-references the frozen architecture
([`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md))
and the honesty boundary
([`../enterprise_pilot/RESEARCH_BOUNDARY.md`](../enterprise_pilot/RESEARCH_BOUNDARY.md)).

If any external statement about this track omits these, that statement is
overclaiming.

---

## Data and validation

1. **Synthetic data only.** All fixtures are schema-shaped but synthetic. No real
   enterprise records have ever been processed.
2. **No production deployment.** Nothing has run in or against a live production
   system. The enforcement harnesses use a synthetic EMR and a simulated broker.
3. **No real enterprise controls.** The comparison baseline is a *model* of existing
   controls, deliberately generous; it is not any organization's real control stack.
4. **No enterprise ground truth.** Findings have never been judged against
   enterprise-authored labels of known-good/known-bad cases.

## Measurement gaps

5. **No precision estimate.** True-positive rate on real workflows is unmeasured.
6. **No recall estimate.** Detection of real known-bad cases is unmeasured.
7. **No real false-positive rate.** The zero-false-positive result holds only on
   synthetic clean workflows.
8. **No scalability measurement.** Shared-invariant reuse is shown across **two**
   synthetic workflows; behavior across many real, heterogeneous workflows is
   unknown.
9. **No operational ROI.** No cost/benefit, time-saved, or risk-reduction figure
   exists or is claimed.
10. **Net-new numbers are fixture-specific.** The synthetic net-new counts describe
    the fixtures, not any enterprise, and do not transfer.

## Enforcement and architecture

11. **No enforcement validation against real systems.** Adversarial guarantees
    (zero unauthorized execution, zero leakage) are proven only against the
    synthetic EMR / simulated broker, not real EMRs, brokers, IAM, or ERP.
12. **Capability-set sufficiency is unproven for real workflows.** The 10 capability
    groups expressed the synthetic workflows; a real workflow may reveal an
    architecture-coverage gap (to be recorded, not silently patched).
13. **Invariant promotion is untested.** No invariant has been promoted from
    audit-only toward enforcement on validated data; which should graduate is
    explicitly *not frozen* and undecided.
14. **HMAC, not asymmetric signatures.** Authorization artifacts use HMAC
    (shared-secret authentication/integrity), not public-key digital signatures;
    key-distribution/rotation for a real deployment is out of scope here.

## Method and scope

15. **The ontology is retained only as scaffold.** Its files remain in the tree as
    research history; they are **not** a runtime schema and their labels are not
    load-bearing.
16. **Determinism assumes stable snapshots.** Results are deterministic given a fixed
    input snapshot; real exports must be snapshot-stable for reproducibility.
17. **Anonymization vs join integrity is a design constraint, not a solved problem.**
    Real pilots must preserve cross-system join integrity under pseudonymization.
18. **Single-track scope.** These conclusions apply only to this track and say
    nothing about other research lines in the repo.

## What these limitations imply

Taken together: the track has a **validated-on-synthetic-data architecture and
method** and a set of **negative results about the ontology**, but **no established
real-world value, accuracy, or effectiveness**. Every remaining question of worth is
a real-data question. See [`FUTURE_WORK.md`](FUTURE_WORK.md) and
[`RESUME_GUIDE.md`](RESUME_GUIDE.md).
