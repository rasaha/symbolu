# Shadow-Mode Operation

**Status:** Phase-3 readiness documentation against the **frozen** architecture
([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
This describes how the pilot is **operated** in shadow mode on real historical
records. It changes no code and asserts no results.

---

## 1. What shadow mode is

`observe → evaluate → emit findings → compare to baseline → (human review)`.

The frozen `ShadowEvaluator` (`shadow.py`) runs the 11 invariants over assembled
`WorkflowEvidence`, compares each finding's code to the enterprise baseline set,
and returns metrics. **There is no automated denial and no write path.** ActionGate
is not connected to any enterprise system in the pilot; the loop terminates at
"findings for human review."

## 2. Non-negotiable operating constraints

1. **Read-only.** Adapters observe historical exports/replicas/scoped reads.
   Nothing writes to a source. (Adapter contract:
   [`SOURCE_ADAPTER_SPECIFICATION.md`](SOURCE_ADAPTER_SPECIFICATION.md) §1.)
2. **No automated enforcement.** Every finding is advisory input to an enterprise
   reviewer. Promotion levels on findings are *defaults for a future decision*, not
   live actions.
3. **Historical first.** The first pilot runs over past, labeled records — not live
   traffic — so results can be judged against known outcomes.
4. **Determinism.** Same export → same findings. No clocks or randomness in
   adapters or invariants.
5. **Missing stays missing.** Gaps surface as `EvidenceStatus.MISSING`; nothing is
   invented.

## 3. The promotion ladder (why nothing enforces yet)

Findings carry a `default_promotion` on the frozen ladder
`AUDIT → WARNING → APPROVAL_REQUIRED → HARD_ENFORCE` (`PromotionLevel`). In shadow
mode **every finding is treated as audit-only regardless of its default** — the
default records where a finding *could* eventually sit, not where it acts now.

Promotion of an individual invariant from audit toward enforcement is **out of
scope for this pilot** and, per the freeze, is a later data-driven decision
([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md) §5).
The frozen guidance names **integration closure** and **prohibited-capability
exposure** as the first enforcement *candidates*, with advisory/derivation findings
staying audit-oriented longer — but no promotion happens during the readiness
pilot.

## 4. Run procedure

1. **Freeze inputs.** Hash-record the labeled ground-truth set
   ([`GROUND_TRUTH_PROTOCOL.md`](GROUND_TRUTH_PROTOCOL.md)) and the
   `enterprise_baseline_codes` set
   ([`BASELINE_COMPARISON_FRAMEWORK.md`](BASELINE_COMPARISON_FRAMEWORK.md))
   **before** running, so nothing is back-fitted.
2. **Assemble evidence.** Run the read-only adapters over the historical export to
   build one `WorkflowEvidence` per instance.
3. **Evaluate.** `ShadowEvaluator(baseline).evaluate_workflow(wf)` per instance;
   `evaluate([...], clean=[...])` for the aggregate report.
4. **Do not reveal to adjudicators early.** Findings are computed but the
   code-mapping adjudication (ground truth) must already be locked.
5. **Compute metrics** ([`ENTERPRISE_METRICS.md`](ENTERPRISE_METRICS.md)) with
   denominators and dates.
6. **Human review.** Enterprise reviewers judge findings; the pilot records
   agreement/disagreement. No action is taken on the enterprise's systems.

## 5. What is logged per run

- Input hashes (ground truth set, baseline set, export snapshot id).
- Per-workflow: total findings, net-new, duplicates, missing-data rate,
  disposition/promotion profile, invariants fired (all emitted by `shadow.py`).
- Adjudication outcomes against ground truth.
- Any architecture-coverage gap (a real problem class expressible by no frozen
  failure code) — logged as a research observation, not silently dropped.

## 6. Boundary with ActionGate (restated)

```
 Enterprise evidence & coherence layer (this pilot, shadow, read-only)
        ↓  findings, constraints, dependencies, verified authority, closure state
 ActionGate  — NOT connected to enterprise systems during the readiness pilot
        ↓  allow / deny / constrain / escalate / require approval  (future, post-validation)
```

Advisory/reasoning-style findings inform; they never authorize. Wiring ActionGate
to an enterprise enforcement boundary is explicitly **after** validated data, not
part of readiness.

## 7. Failure/abort conditions for a run

Stop and report (do not tune to rescue a number) if:

- An adapter cannot map a source without inventing data → record as coverage gap.
- The baseline set was not locked before the run → invalid run, discard.
- Ground truth was revealed before code-mapping was locked → invalid run, discard.
- A source turns out to require a write path → out of scope; do not proceed.

## 8. Cross-references

- Evaluator: `agentic/enterprise_governance/shadow.py`.
- Promotion ladder / dispositions: `agentic/enterprise_governance/model.py`,
  `invariants.py`.
- Frozen shadow description: [`ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md`](../../actiongate/ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md) §5.
- Frozen position: [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md).
