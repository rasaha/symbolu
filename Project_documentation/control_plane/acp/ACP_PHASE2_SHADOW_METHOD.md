# ACP Phase 2 — Shadow Method (§6)

How the physical-safety shadow evaluation runs and guarantees zero production
impact. Code: `robotics_reliability_bench/acp_shadow2/run_shadow2_bench.py`.

---

## 1. Per-scenario flow

```
corpus candidate (joint trajectory + obstacles/human + ground-truth label)
   │
   ├─► TrajectoryValidatorAdapter.evaluate  ──► PhysicalEvidence + HARD ConstraintResults
   │        (REAL TrajectoryValidator, real thresholds)
   │
   └─► LexicographicActionSelector (order: physical safety_score ↓, id)
             │
        record: acp decision + evidence + surviving/rejected
                + modeled current-runtime pick + ground-truth comparison
```

- The **current runtime has no physical gate** at these call sites; its pick is
  modeled as the abstract-max (where an abstract score exists) else the
  planner-preferred (first) candidate. We record whether that pick is physically
  inadmissible under the real evidence — i.e. *would the current runtime have
  selected a physically-unsafe action*.
- Every record carries `shadow_only=true`.

## 2. Recorded per scenario (milestone §6)

authoritative/current pick; ACP decision + selected; ACP surviving/rejected +
dispositive reasons; full `PhysicalEvidence` per candidate (validity, is_safe,
safety_score, ttc, violations); ground-truth unsafe set; physical-detected-unsafe
set; false-rejected-safe set; `current_runtime_physically_inadmissible`;
abstract-vs-physical agreement pairs; `NO_SAFE_ACTION`; provenance; family;
`shadow_only`.

## 3. What ACP must NOT alter (verified)

The harness makes **no production call that mutates state** — it constructs its
own validator + envelopes and never touches the planner, task allocator, conflict
resolver, actuator, or recovery. `current_runtime_behavior_change_count = 0`;
robotics baseline suite is byte-identical before/after
(`ACP_PHASE0_COMPATIBILITY_REPORT.md` methodology).

## 4. Authorization sub-check

For the authorization family: ACP authorizes its pick, then the harness mutates
the world version (or presents a different candidate identity) and calls the
commit revalidator — which must raise `StaleAuthorizationError` /
`AuthorizationBindingError`. A direct A-cannot-authorize-B binding check also
runs. No grant ever actuates.

## 5. Guarantees the harness proves

- **Deterministic rerun identity** = 100% (whole corpus run twice, records
  compared).
- **ACP inadmissible-selection count** = 0 (never selects a physically-inadmissible
  candidate).
- **Fail-closed** on missing / stale / evaluator-failure evidence.
- **No actuation** — every record `shadow_only`; no `ControlAuthorization`
  consumed by an actuator.

## 6. Reporting discipline

Metrics are reported **separately per provenance class and per family** — the
INTEGRATION_TEST and AUTHORED_DETERMINISTIC results are never merged into one
headline (milestone §8). Real-physical-evidence coverage, missing/stale rates,
detection recall, false-rejection, current-runtime-inadmissible rate, and
abstract-vs-physical agreement are each broken out.
