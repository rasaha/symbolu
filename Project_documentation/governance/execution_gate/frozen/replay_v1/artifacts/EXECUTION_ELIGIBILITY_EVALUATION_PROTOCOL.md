# Execution Eligibility — Evaluation Protocol (pre-registered)

*Phase 10 deliverable. Registered before the evaluation report is written. The evaluation
is deterministic and offline (no live credentials), so "sample size" is the fixed scenario
suite; a live extension is specified as future work.*

## Hypotheses

- **H1 (primary):** an explicit execution-eligibility layer reduces **invalid model
  selections** — policy violations + failed first attempts — versus retry-only routing.
- **H2:** it reduces **selection regret** versus retry-only and static rules.
- **H3:** ExecutionGate + ModelPolicy ≥ ExecutionGate alone on regret (policy adds value
  *after* eligibility filtering).
- **H0 (null / falsification):** in stable, all-eligible environments the eligibility layer
  adds only overhead; retry-only and static allowlists match it.

## Endpoints

- **Primary:** invalid-selection rate = policy-violation rate + (1 − first-attempt-success
  rate), vs `retry_only`.
- **Secondary:** selection regret; execution success rate; failed-calls; fallback rate;
  abstention rate; latency; cost per success; eligibility precision/recall; **false-eligible
  on critical (compliance) constraints** (severe, reported separately); false-ineligible.

## Design

- **Datasets:** the deterministic scenario suite (`execution_gate/scenarios.py`), 11
  scenarios across 7 categories (replay, governance, execution, capability, operational,
  staleness, stable), each with per-candidate ground truth.
- **Baselines:** no-eligibility, retry-only, provider-health, static-allowlist,
  execution-gate, execution-gate+policy.
- **Simulation:** each baseline's attempt sequence is run against ground truth; a
  working-but-prohibited selection is a **policy violation** (retry logic cannot detect it);
  an unexecutable attempt is a failed call that triggers fallback.
- **Seeds / determinism:** no randomness; fixed base time `T0`; identical inputs ⇒ identical
  outputs (a determinism test enforces this).
- **Multiplicity:** the primary endpoint is single; secondary endpoints are descriptive.
  Any future live study applies BH-FDR to the secondary family.
- **Spend cap:** offline evaluation spends $0. A live extension inherits the frozen
  `PILOT_MAX_SPEND_USD` discipline and probes at minimum cost.

## Severity weighting (fixed)

**False-eligibility on a critical/compliance constraint is the most severe error** — it lets
ModelPolicy route to a prohibited or non-executable model. It is reported separately and must
be **zero** for the gate to be considered safe. False-ineligibility (discarding usable
capacity) is a real but lesser cost, reported alongside.

## Operational success criteria (pre-registered)

The eligibility layer is judged **valuable** if, on the suite:
1. policy-violation rate = 0 (vs > 0 for retry-only); **and**
2. false-eligible-critical = 0; **and**
3. invalid-selection rate materially below retry-only (≥ 30% relative reduction); **and**
4. selection regret materially below retry-only (≥ 30% relative reduction); **and**
5. the added latency/overhead does not exceed the latency saved from avoided failed calls on
   the non-stable scenarios.

It is judged **not valuable / over-engineered** if retry-only or static-allowlist match it on
the primary endpoint, or if false-ineligibility removes more useful capacity than the
violations/failed-calls it prevents.

## Stopping / failure rules

- If a test exposes a **specification defect** (a stated invariant is violated), STOP and fix
  the spec, not the numbers.
- If a test exposes only an adapter/binding defect, fix the implementation.
- Report null and negative findings directly; do not reframe a stable-environment null as
  success.

## Falsification targets (Phase 11) — explicitly tested

Retry equals gate; provider-health captures most value; eligibility latency too high; cache
staleness dominates; false-ineligibility too costly; live probes too expensive; reachability
dominates all signals; billing/quota too provider-specific; manual allowlists win; ModelPolicy
adds nothing post-filter; gate benefit vanishes in stable environments; complexity exceeds
benefit. Each maps to a measured comparison in the report.
