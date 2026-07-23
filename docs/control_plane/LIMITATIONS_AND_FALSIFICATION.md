# Limitations and Falsification

*Phase 16. Each falsification question from the task, answered directly against the code and
the mock evaluation. Negative findings are reported as findings, not hidden.*

## Falsification questions

**1. Is a simple sequential script sufficient?**
*Partly — and where it is, we say so.* On the single-provider, no-action scenario
(`single_provider_overhead`, flagged `can_lose`) all three configs — glue, orch, unified —
produce the identical outcome. With one provider and no action to govern, the control plane's
machinery is pure overhead. A script suffices. The architecture only earns its cost when there
is something to route around: multiple providers, real exclusions, real actions.

**2. Do formal contracts add measurable value?**
*Not on their own, on this suite — a genuine negative finding.* The `glue` and `orch` configs
are **identical on every safety metric** (`MOCK_EVALUATION_REPORT.md`). Contract *validation*
catches malformed/incompatible hand-offs but did not, by itself, prevent the upstream-exclusion
bypass or fix fallback. The safety difference came entirely from the **invariant-enforcement**
layer (unified). Contracts are necessary plumbing and version hygiene; they are not the source
of the guarantees.

**3. Does the orchestrator become a new monolith?**
*Avoided by construction, but it is the standing risk.* The reference orchestrator holds no
decision authority — it routes, validates, guards invariants, and records. Every eligibility,
selection, assertion, and action decision is made by the wrapped component. The risk is real:
if future changes push decision logic into the orchestrator, it becomes the monolith the
architecture was meant to prevent. The authority matrix is the guard against this.

**4. Do reason-code namespaces become too complex?**
*No, at current scope.* Seven namespaces, 28 codes, one owner each. The namespace *prevents*
merging existing component vocabularies (the alternative — one flat merged code space — would
be worse). Complexity would only bite if namespaces multiplied per provider; they do not.

**5. Does audit chaining add excessive overhead?**
*No, measurably.* 161 vs 160 records across 32 scenarios; hashing is one sha256 per record.
The chain is substrate-level and present in all configs. No measurable overhead problem here;
production throughput remains to be measured.

**6. Does downstream governance duplicate upstream policy?**
*No — but the boundary needs vigilance.* ExecutionGate (can-execute) and ActionGate
(may-act) answer different questions with different evidence. The one place duplication could
creep in is residency/provider approval, which ExecutionGate owns; ActionGate must not
re-decide it. The authority matrix assigns each exactly once.

**7. Are TAP and ActionGate boundaries clear?**
*Yes, and the decision-order test confirmed the ordering.* TAP governs *what may be asserted*
(runs after provider output); ActionGate governs *what may be done* (runs on the **governed**
assertion output, not raw model output). Assertion approval never implies action approval
(invariants 5, 17). The scenarios exercise assertion-approved-but-action-denied explicitly.

**8. Does fallback logic create loops?**
*No.* Fallback re-enters eligibility with the failed candidate **excluded** from the remaining
set (invariant 19); the eligible set strictly shrinks, so re-entry terminates. Verified by the
`fallback_reentry` scenario (switches candidate, does not retry in place).

**9. Does telemetry feedback create circular decisions?**
*No, by construction.* Registry updates target a **strictly future** registry version
(`RegistryUpdater` rejects same/past → `RUNTIME.CIRCULAR_DEPENDENCY_DETECTED`). Telemetry never
rewrites a prior decision and never affects the in-flight trace (invariants 11, 12).

**10. Does versioning cause operational fragility?**
*This is the top operational risk.* Per-trace immutable pins keep each request correct, but a
mixed-version fleet (embedded/sidecar) needs coordinated registry/policy rollout. Version
mismatch fails closed (`POLICY.*_VERSION_MISMATCH`) — safe, but a misconfigured rollout can
block traffic. Documented in the deployment model.

**11. Does component independence create excessive integration cost?**
*Moderate and one-time.* Each component needs an adapter (7 adapters here). The cost is the
adapter surface, paid once per component; the benefit is that each component stays
independently testable (execution_gate's 21 tests still pass unchanged, run alongside the
plane's 65).

**12. Do stable environments justify the complexity?**
*Often not — stated plainly.* See question 1. In a stable single-provider environment the
control plane adds overhead without a safety dividend. It is justified by *instability*:
multiple providers, changing eligibility, real actions, audit/regulatory requirements.

**13. Is human approval the real bottleneck?**
*Yes, for approval-gated actions.* No software budget changes human latency
(`LATENCY_AND_COMPLEXITY_BUDGET.md`). The plane's job there is to make the escalation
attributable and auditable, not fast.

**14. Can the architecture degrade safely when a governance component is unavailable?**
*Yes — verified.* TAP-unavailable and ActionGate-unavailable scenarios both terminate
fail-closed (`RUNTIME.GOVERNANCE_COMPONENT_UNAVAILABLE`), never silent-allow. Safe degradation
means refusing to act, not proceeding ungoverned.

## Standing limitations

- **No live validation.** Everything here is MOCK/deterministic. ENFORCEMENT, real providers,
  and real actions are disabled; no production latency or reliability is measured.
- **Mock downstream components.** Provider/TAP/ActionGate/ActionAdapter/Telemetry are
  deterministic stand-ins. Only ExecutionGate and ModelPolicy are the real packages. Real TAP
  and real ActionGate behavior may differ.
- **Contracts unproven under version churn.** Compatibility/deprecation rules are declared but
  not exercised across an actual multi-version migration.
- **Single-tenant reasoning.** Tenant isolation is described, not tested under concurrency.
- **The evaluation suite is small (32 scenarios).** It is designed to be falsifying, not
  exhaustive; absence of a failure here is not proof of absence in general.
