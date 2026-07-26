# Provider Heterogeneity, Resolution, and Failover Validation (Phase 6B)

Validates that the existing provider framework supports **more than one provider
per governance family**: deterministic selection by compatibility, capability,
health, and explicit policy; bounded, safe failover under infrastructure failure;
and strict prohibition of governance shopping — all with **no change** to any
frozen component.

- Packages: `baseline_assertion_provider` (`dgm-baseline-assertion-provider`),
  `baseline_action_provider` (`dgm-baseline-action-provider`),
  `provider_heterogeneity_validation` (`dgm-provider-heterogeneity-validation`) — all 0.1.0.
- Run: `python -m provider_heterogeneity_validation.run --output build/phase6b-results`

## 1. Alternative-provider purpose

The two baseline providers are **deterministic validation implementations, not
production competitors**. Each is a legitimate but intentionally capability-limited
alternative to TAP / ActionGate, used to prove the framework hosts heterogeneous
providers per family.

- **BaselineAssertionProvider** — exact evidence matching → SUPPORTED; explicit
  contradiction → UNSUPPORTED; missing evidence → INDETERMINATE. It performs no
  qualifier/scope/component/provenance analysis, so any assertion requiring those
  is returned INDETERMINATE (never a less-safe SUPPORTED). Passes the shared
  assertion conformance unchanged (12/12) plus a specific suite (10/10).
- **BaselineActionProvider** — deterministic allow/deny; a restricted constraint
  vocabulary (`maximum_amount`) and obligation vocabulary (`logging`,
  `notification`); any unsupported policy construct → INDETERMINATE (never a
  less-safe AUTHORIZED); never executes. Passes shared action conformance (11/11)
  plus a specific suite (11/11).

Both use the existing lifecycle and error taxonomy, expose honest descriptors, are
independent of TAP/ActionGate and of the other family, and package independently.

## 2. Capability model & compatibility

A canonical capability vocabulary (`profiles/capabilities.py`) and an honest
per-provider capability declaration. Baseline providers declare their (limited)
capabilities in their descriptors; the frozen TAP/ActionGate providers are mapped
to canonical capabilities from documented real behaviour without modification.
Capability is asserted only where genuinely supported. Compatibility, enabled
state, health, capability, and provider-kind are all expressed with the **existing**
framework structures (`ProviderCompatibility`, `ProviderCapabilities`,
`ProviderHealth`, `is_contract_compatible`) — no new compatibility system was
required.

## 3. Resolution policies (Task 7)

Four explicit policies, built on the framework's discovery primitives:

- **FIXED** — always the configured id if eligible; never falls back.
- **ORDERED** — first compatible/enabled/healthy/capable provider in a preference list.
- **CAPABILITY_REQUIRED** — only providers satisfying all mandatory capabilities;
  an incapable provider is never selected even when healthy (H4, H19).
- **BOUNDED_FALLBACK** — the preferred provider unless it is infrastructure-ineligible
  (incompatible / unavailable / degraded-not-allowed / disabled) *and* policy permits,
  in which case the next eligible capable provider is chosen; otherwise → no provider.

If no valid provider exists: assertion governance → INDETERMINATE; action governance
→ INDETERMINATE with no dispatch. Governance is never bypassed as authorized/supported.

## 4. Fallback semantics & the prohibition on governance shopping (Task 10)

Selection, fallback, retry, and provider-result indeterminacy are distinct.
**Selection happens strictly before invocation**, so a substantive provider result
can never influence which provider is chosen — governance shopping is structurally
impossible. Fallback is triggered only by infrastructure/compatibility/health/
capability rejection recorded at selection time, never because a provider returned
a legitimate UNSUPPORTED/DENIED/INDETERMINATE. Invariants H5–H8 and the
`governance_shopping_violations` metric (measured 0) enforce this; the
`test_governance_shopping_prevented_*` tests demonstrate that an UNSUPPORTED
assertion or a DENIED action under bounded fallback never seeks a more favourable
provider.

## 5. Selection records (Task 8)

Every resolution produces a benchmark-owned `SelectionRecord` with request id,
kind, policy, candidate ids/versions/health/compatibility, required capabilities,
per-candidate rejection reasons, the selected provider + version, fallback used +
reason, and a resolution fingerprint. Selection is reproducible from registry
state, configuration, health, compatibility, required capabilities, and policy —
ordered by preference then provider id, never by dictionary traversal or
registration accident. No secrets or unrestricted evidence are logged.

## 6. Failure injection (Task 12)

21 deterministic profiles inject per-provider timeout / unavailable / malformed /
incompatible / degraded, plus registry-duplicate-id, no-compatible-provider, and
no-capability-match. Each targets one provider (or a structural condition) and is
applied only to configurations containing the relevant component. The runner thus
exercises both **provider-result indeterminacy** (engine fails but the provider is
reachable/selected → fail-safe INDETERMINATE result) and **selection-time rejection**
(health/compat/capability → fallback or no-provider).

## 7. Metrics (Task 13)

Resolution metrics (determinism, preferred-selection, fallback, safe-fallback,
no-valid-provider, capability-match, compatibility/health rejection counts, trace
completeness) are reported separately from governance metrics (unsupported
promotion, unsafe authorization/dispatch, constraint preservation, fail-safe rate,
governance-shopping violations). Provider-specific metrics (eligible/selected/
invocations/infrastructure-failures/substantive-indeterminate/fallbacks) are
reported **per provider and never combined into a single ranking** — a
capability-limited provider is not penalised for requests it honestly declares
unsupported.

## 8. Scenario-class cost/benefit frontier (Task 14)

For each scenario class the frontier reports the sufficient provider pairs
(reproducing the full pair's safe operational outcome), the lowest-workload
sufficient pair, the required capabilities, whether bounded fallback is acceptable,
and whether the full pair is required. Analytical output only — not a dynamic
production router.

## 9. Configurations (Task 15) & headline result

Six configurations run across all 90 frozen scenarios. **No configuration produced
any unsafe outcome.** C1 (TAP + ActionGate) reproduces Phase 6A full governance
exactly. C2–C4 (with a capability-limited provider) produce fail-safe INDETERMINATE
*false blocks* where a capability is missing, never an unsafe promotion. C5
(bounded fallback, preferred healthy) matches C1. C6 (capability-driven) routes each
request to the lightest sufficient provider and escalates only when a capability is
genuinely required; it also, by policy, routes some ActionGate-infrastructure-failure
scenarios to the healthy baseline action provider (a resilience property, selected
pre-invocation — not shopping). All 20 invariants H1–H20 pass.

## 10. Reproducibility, packaging, dependency direction

One deterministic CLI runs all six configurations, the required failure profiles
over a fixed representative subset, all invariants, and all reports; the substantive
digest excludes volatile ids/durations and is stable across runs and a clean
isolated install. Enforced dependency rules: frozen packages import no benchmark/
validation package; the two same-family providers never import one another;
assertion providers never import action providers and vice versa; the validation
package imports concrete providers only in its two composition modules
(`runners/composition.py`, `runners/workflow.py`); selection is provider-neutral;
the baseline providers consume only public framework/DGM APIs and their cores are
pure. `packaging/verify_provider_heterogeneity_distribution.py` builds all eight
wheels and proves import, registration, conformance, deterministic selection,
capability rejection, safe fallback, rejected-unsafe fallback, no-provider fail-safe,
and C1/Phase-6A reproduction in a fresh venv with no monorepo path.

## 11. Limitations

- The alternative providers are **deterministic validation implementations, not
  production competitors**; no production/regulatory claim is made.
- Capability profiles for the frozen providers are a documented benchmark-owned
  mapping (the frozen providers' own feature vocabulary predates this canonical
  set); baseline providers declare capabilities directly.
- The failure matrix runs over a fixed representative scenario subset for speed;
  normal-mode runs cover all 90 scenarios.
- No frozen-component change was required or made.
