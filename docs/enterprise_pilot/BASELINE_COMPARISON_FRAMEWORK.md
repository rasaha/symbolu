# Baseline Comparison Framework

**Status:** Phase-3 readiness documentation against the **frozen** architecture
([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
This defines how a pilot finding is judged **net-new versus the enterprise's own
existing controls**, so we never claim credit for something they already catch. No
enterprise data or results appear here.

---

## 1. The claim we are (and are not) making

The only defensible value claim is: *the model produces findings a mature
enterprise's existing controls would miss.* Everything hinges on the baseline being
**honest and strong**. A weak baseline inflates net-new; a fabricated one is
dishonest. This framework exists to keep the baseline *at least as strong as what
the enterprise actually runs*.

We make **no** claim here that net-new findings are correct or valuable — that is
established (or not) later against ground truth
([`GROUND_TRUTH_PROTOCOL.md`](./GROUND_TRUTH_PROTOCOL.md)) and metrics
([`ENTERPRISE_METRICS.md`](./ENTERPRISE_METRICS.md)). Net-new only means *not
already covered*.

## 2. The frozen mechanism

Net-new is computed by the frozen `ShadowEvaluator` (`shadow.py`) against the
frozen `StrongControlsBaseline` (`baseline.py`):

```python
net_new = [f for f in findings if f.failure_code not in baseline_codes]
duplicate = [f for f in findings if f.failure_code in baseline_codes]
```

The reference baseline is deliberately **generous**. It models a mature stack —
approval matrix, ERP reconciliation job, business-rule engine, IAM access review —
assumed present and effective, and therefore already catching:

```python
BASELINE_DETECTABLE = {
    "MISSING_AUTHORITY_BASIS",        # approval matrix
    "STATE_RECONCILIATION_FAILURE",   # ERP reconciliation job
    "PROTECTED_INVARIANT_BREACH",     # business-rule engine
    "PROHIBITED_CAPABILITY_EXPOSURE", # IAM access review
}
```

A finding is net-new **only if even this strong baseline would miss it**.

## 3. Replacing the modeled baseline with the enterprise's real one

For a real pilot, the modeled `BASELINE_DETECTABLE` is **not** used blind. It is
reconciled with the enterprise's actual controls:

1. **Inventory real controls.** For the chosen workflow, the enterprise lists every
   control that already runs (matrix, jobs, rule engines, reviews, manual gates)
   and states, per control, which failure conditions it catches.
2. **Map each real control to failure codes.** Using the frozen failure-code
   vocabulary (`invariants.py`), record which codes each real control already
   detects. The union becomes the **enterprise baseline set** for that workflow.
3. **Reconcile with the modeled set.** Three cases:
   - Real control catches a code **in** `BASELINE_DETECTABLE` → keep it (expected).
   - Real control catches a code **not** in `BASELINE_DETECTABLE` → **add it** to
     the enterprise baseline set for this workflow. The default four are a floor,
     not a ceiling; a stronger real baseline shrinks our net-new honestly.
   - Modeled code that the enterprise does **not** actually catch → **do not**
     silently drop it. Record it as "modeled-but-unconfirmed" and, by default,
     keep treating it as baseline-covered (conservative: assume they catch it
     unless they say otherwise). Only move it out of the baseline with explicit
     enterprise confirmation, documented.
4. **Confirm strength before crediting net-new.** A control counts toward the
   baseline only if the enterprise attests it is actually deployed and effective
   for this workflow — not merely owned or intended.

The result is a per-workflow `enterprise_baseline_codes` set that is **≥** the
modeled floor. Net-new is computed against *that* set.

## 4. Grades of net-new

Not all net-new is equal. Each net-new finding is graded jointly with the
enterprise:

| Grade | Definition |
|---|---|
| **Confirmed net-new** | Ground truth says the instance was `problematic`, `caught_by_existing_controls != yes`, and the finding's code matches the adjudicated problem. |
| **Plausible net-new** | Net-new by code, on an instance the enterprise cannot confidently label (`unknown`). Reported separately; not counted as a win. |
| **Net-new false positive** | Net-new by code, but on a `clean`-labeled instance. Counts against precision. |
| **Redundant** | Finding whose code is in `enterprise_baseline_codes` (the existing stack already catches it). |

Only **confirmed net-new** supports any value statement, and even then only as a
measured pilot result, never as a general efficacy claim.

## 5. Honesty rules

- **The baseline may only grow, never shrink, without documented enterprise
  confirmation.** Shrinking the baseline is the easiest way to fake value; it
  requires explicit sign-off and a recorded reason.
- **Concede duplicates loudly.** The evaluator already reports
  `duplicate_of_existing_controls`; the pilot report leads with what the enterprise
  already catches before what is net-new.
- **No back-fitting the baseline after seeing findings.** The
  `enterprise_baseline_codes` set is frozen (hash-recorded) before shadow output is
  revealed, exactly like ground truth.
- **A strong baseline that eliminates most net-new is a valid outcome.** If the
  enterprise's controls already catch nearly everything, the pilot says so. That is
  a result, not a failure to hide.

## 6. Relationship to the synthetic pilot numbers

The synthetic shadow pilot reported net-new counts on **schema-shaped fixtures**
against the **modeled** baseline (discount 9 net-new, IAM 5 net-new). Those numbers
describe the fixtures, not any enterprise, and are **not** transferable. A real
pilot recomputes net-new from scratch against the enterprise's real baseline set.
See the non-claims in
[`ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md`](../../ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md) §10.

## 7. Cross-references

- Net-new computation: `agentic/enterprise_governance/shadow.py`,
  `agentic/enterprise_governance/baseline.py`.
- Failure-code vocabulary: `agentic/enterprise_governance/invariants.py`.
- Labels feeding the grades: [`GROUND_TRUTH_PROTOCOL.md`](./GROUND_TRUTH_PROTOCOL.md).
- Metric definitions: [`ENTERPRISE_METRICS.md`](./ENTERPRISE_METRICS.md).
- Frozen position: [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md).
