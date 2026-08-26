# Enterprise Validation Pilot (Phase 5I)

A bounded, deterministic, cross-provider validation of the Decision Governance
Middleware (DGM) ecosystem operating as deployed. The pilot composes the frozen
kernel, provider framework, TAP (assertion governance), and ActionGate (action
governance) through their **public APIs only** and runs realistic enterprise
decision workflows end to end.

- Import package: `enterprise_validation_pilot` · Distribution:
  `dgm-enterprise-validation-pilot` 0.1.0
- Depends on (never vendors): `decision-governance==1.0.0`,
  `dgm-provider-framework==0.1.0`, `dgm-actiongate-provider==0.2.0`,
  `dgm-tap-provider==0.1.0`
- Run: `python -m enterprise_validation_pilot.run --output build/pilot-results`

## 1. Purpose

This is **not** an architecture phase. It measures whether the existing system
works coherently under realistic decision workflows while preserving its
architectural boundaries and fail-safe governance invariants — and whether that
requires any change to the frozen kernel or provider contracts. It does not.

Central acceptance question: *Can TAP, ActionGate, DGM, and external execution
operate together across realistic enterprise workflows while preserving their
boundaries, enforcing fail-safe invariants, and requiring no modification to the
frozen kernel or provider contracts?* — Answered **yes** by this pilot.

## 2. Architecture

```
Enterprise Evidence → Proposed Assertion → TAP Provider → Assertion Assessment
   → Recommendation → Decision → Proposed Action → ActionGate Provider
   → Authorization / Constraints / Obligations → External Execution → Reconciliation
```

TAP feeds the assessment/recommendation workflow; ActionGate authorizes the
prepared action; external execution is separate; reconciliation verifies what
actually occurred. TAP never authorizes; ActionGate never evaluates assertion
truth; the execution provider never decides authorization; DGM remains the
lifecycle and record authority.

- `composition/` — provider config, ecosystem manifest, engine construction from
  scenario policy, and the composition root (registry wiring + DGM services +
  deterministic identity/clock).
- `runners/` — the end-to-end workflow, active constraint enforcement, obligation
  verification, and correlated-trace assembly.
- `evaluators/` — scenario evaluation, safety invariants, failure injection,
  provider independence.
- `metrics/`, `reports/`, `run.py` — per-layer metrics and report generation.

## 3. Domain selection

Three enterprise domains with materially different action/assertion patterns:
**procurement** (`PURCHASE_ORDER`), **finance_operations** (`PAYMENT_RELEASE`),
**refund_operations** (`ISSUE_REFUND`). Each contributes 30 scenarios spanning
assertion-evaluation, recommendation, authorization, constrained-action, denied,
indeterminate, and execution/reconciliation cases. Regulated medical/legal advice
workflows are intentionally excluded.

## 4. Scenario taxonomy

A stable taxonomy (`schemas/taxonomy.py`) with 12 assertion classes, 16 action
classes, and 9 cross-provider classes. Every scenario declares its labels
explicitly, and the dataset covers all classes.

## 5. Ground-truth methodology & self-fulfilling-test prevention

The 90-scenario dataset (`datasets/enterprise_pilot_v1.json`, versioned + SHA-256
hashed) is authored by a provider-free module (`scenarios/authoring.py`). Each
scenario carries two **disjoint** regions:

- *provider-facing inputs* (assertion, evidence, proposed action, deployed TAP /
  ActionGate policy, execution spec) — everything the engines see;
- *expected* — the independently-authored ground truth, consumed **only** by the
  evaluators.

Guarantees (all tested): scenario generation never calls a provider; expected
labels are stored before execution; the runner never reads `.expected`; and
mutating a scenario's expected region provably does not change actual outputs.
The pilot **consumes** provider conformance results and does not redefine them.

> **Honesty note.** TAP/ActionGate outcomes come from the providers' deterministic
> **reference engines configured per domain policy**. The pilot validates
> *workflow integration and invariant enforcement*, not the providers' model/NLP
> accuracy (covered by provider conformance). Downstream behavior — recommendation
> posture mapping, dispatch gating, constraint enforcement, obligation
> verification, reconciliation, and every safety invariant — is genuinely
> exercised and is not tautological with the configured outcome.

## 6. Provider composition

Provider selection flows through the framework `ProviderRegistry` and the pilot
configuration (`tap-primary`, `actiongate-primary`); scenario handlers never
instantiate a provider directly. Engine *behavior* is built from scenario policy.
Deterministic id/clock factories are injected into DGM services so entire runs
(traces included, bar one kernel-opaque `authorization_id`) are reproducible.

## 7. Human-review simulation

Human review is a deterministic fixture representing **human authority only** — a
provider never fabricates approval (invariant I14). Modeled paths: supplying
missing evidence (→ TAP re-evaluates through a registry-resolved provider),
approving/declining an action requiring approval, and accepting a constrained
assertion. Example: `*-005` (INDETERMINATE → human supplies evidence → re-evaluate
to SUPPORTED → action proceeds).

## 8. Constraint enforcement

DGM/the pilot — not the execution provider — actively enforces authorized
constraints **before** dispatch (`runners/constraint_enforcement.py`):
`maximum_amount`, `maximum_quantity`, `allowed_region`, `allowed_resource`,
`required_approval`, `single_use` (and records `execution_deadline` etc.). An
action outside its envelope (e.g. `*-017`, amount > limit) is blocked before it
reaches the execution adapter.

## 9. Obligation verification

Obligations carry explicit states (`PENDING`/`SATISFIED`/`FAILED`/
`WAIVED_BY_AUTHORITY`/`EXPIRED`) and are verified independently of execution
success. Reconciliation distinguishes *action executed* from *governance
obligations satisfied* — an action may execute successfully yet remain
governance-noncompliant (e.g. `*-025`), never collapsed into one outcome
(invariant I9).

## 10. Failure injection

A deterministic (non-random) harness injects TAP timeout/unavailable/malformed,
ActionGate timeout/unavailable/malformed, execution timeout/business-rejection/
transport-failure, reconciliation mismatch, missing obligation evidence, registry
resolution failure, and incompatible provider version — verifying fail-safe
behavior for each. Infrastructure failure never yields support or authorization.

## 11. Metrics

Reported **per layer**, never combined into one "governance score":

- **TAP:** outcome accuracy; SUPPORTED precision/recall; UNSUPPORTED/CONSTRAINED/
  INDETERMINATE recall; qualifier-detection recall; unsupported-component recall;
  evidence-coverage error; provider-failure fail-safe rate.
- **ActionGate:** authorization accuracy; unsafe-authorization rate; false-denial
  rate; constraint/obligation preservation; denial & indeterminate non-dispatch
  rates; provider-failure fail-safe rate.
- **Workflow:** trace completeness; provider-resolution determinism; constraint-
  enforcement rate; obligation-verification rate; execution/reconciliation
  consistency; cross-provider isolation violations; audit-correlation completeness.

## 12. Safety invariants

Fifteen invariants (`evaluators/invariants.py`, I1–I15) are verified over the full
scenario set plus static import analysis; any failure fails the pilot regardless
of aggregate metrics. They encode: no promotion of UNSUPPORTED/INDETERMINATE; no
dispatch on DENIED/INDETERMINATE; timeout/unknown never authorize or support;
constraints survive into enforcement; obligations survive into reconciliation;
execution success ≠ compliance; TAP↔ActionGate mutual non-invocation; the
execution provider never decides authorization; deterministic auditable selection;
no fabricated human approval; and no plaintext secrets in audit records.

## 13. Reproducibility

A single deterministic command produces machine- and human-readable reports. A
*substantive digest* over outcome fields (excluding volatile kernel ids/timestamps)
is stable across repeated runs and across a clean isolated install
(`a293154ff74b7665…`).

## 14. Packaging

`dgm-enterprise-validation-pilot` symlinks the canonical package, depends on the
four frozen distributions, ships the dataset as package data, and bundles no
kernel/framework/provider source. `packaging/verify_enterprise_pilot_distribution.py`
builds all five wheels, installs only the pilot into a fresh venv (no monorepo
path), and proves import, registration, manifest validation, dataset load,
deterministic execution, invariants, failure-injection fail-safety, independence,
and report generation.

## 15. Limitations

- Synthetic data only; **no production-readiness or regulatory-compliance claim**.
- Provider outcomes are reference-engine + domain-policy driven (see §5 honesty
  note); NLP/model accuracy is out of scope and covered by provider conformance.
- Single-process, in-memory repositories; no live connectors, UI, or performance
  claims.
- The neutral request contract's absent `tenant` field (noted in Phase 5G/5H) was
  **not** required by any scenario, so no contract extension is proposed.

## 16. Interpretation guidance

Read the reports as: *measured result* (what the composed system did),
*designed expectation* (independently authored ground truth), *inference* (the
architecture preserves its boundaries and fail-safe invariants under realistic
cross-provider workflows), and *limitation* (§15). All-passing metrics here mean
the workflow reproduces the designed governance behavior deterministically — not
that the providers' underlying models are validated, and not that the system is
production-certified.
