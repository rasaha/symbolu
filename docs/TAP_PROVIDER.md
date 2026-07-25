# TAP Assertion-Governance Provider (Phase 5H)

TAP is the **second real governance provider** for the Decision Governance
Middleware (DGM) and the first concrete `AssertionGovernanceProvider`. It
evaluates whether a *material assertion* is adequately supported by *supplied
evidence* and returns a structured, component-level result that feeds DGM's
**assessment / recommendation** workflow.

TAP is a genuine **peer** of the ActionGate action-governance provider: the two
products share the framework contracts but are mutually unaware. Neither imports
nor invokes the other. Delivering TAP required **no change** to the frozen DGM
kernel (1.0.0) or to ActionGate.

- Import package: `tap_provider` · Distribution: `dgm-tap-provider` · Version: `0.1.0`
- Depends on: `decision-governance==1.0.0`, `dgm-provider-framework==0.1.0`
- Does **not** depend on `dgm-actiongate-provider` / `actiongate_provider`.

---

## 1. Architectural placement

```
Evidence + Proposed Assertion
            │
            ▼
      Provider Registry            (governance_providers)
            │
            ▼
        TAP Provider               (tap_provider.provider.TAPProvider)
            │
            ▼
AssertionGovernanceProvider.evaluate()
            │
            ▼
AssertionAssessmentIntegration     (governance_providers.adapters)
            │
            ▼
Assessment / Recommendation Evidence
            │
            ▼
Decision Trace                     (decision_governance audit)
```

TAP integrates into **assessment and recommendation only**. It is never routed
through `ActionControlPlanePort` or `ExternalExecutionPort`. It does not
authorize, execute, reconcile, or compensate actions, does not replace DGM
assessments, and does not make final business decisions. The application or
domain owns the assertion and the supplied evidence; TAP evaluates them.

Dependency direction: `application → tap_provider → {governance_providers,
decision_governance}.api`. The TAP **core** (`tap_provider/core/`) imports neither
DGM nor the framework.

---

## 2. Assertion and evidence models

### TAP-native request (`tap_provider.core.TapEvaluationRequest`)

| field | meaning |
|---|---|
| `assertion` | the assertion text under evaluation |
| `evidence` | tuple of `TapEvidenceItem` |
| `context` | opaque evaluation context (`Mapping[str, object]`) |
| `assertion_type` | optional classification (`"claim"`, …) |
| `source_identity` | who asserted it |
| `policy_references` | governing policy refs |
| `correlation_id` / `trace_id` | correlation / trace carriers |

### Evidence projection (`TapEvidenceItem`)

`evidence_id`, `source_type`, `source_reference`, `content` (governed excerpt
only), `provenance`, `evidence_class`, `effective_period`, `authority`,
`fingerprint`. Evidence classes distinguish **direct / derived / policy /
historical / model-generated / human-provided** evidence.

**Provenance is kept separate from evidentiary support** — TAP never claims an
item is true merely because it exists. Only governed excerpts and hashes are
retained; unrestricted source documents are never placed into audit records.

### Evidence resolution

The neutral contract carries evidence **references** only (never raw content).
The request mapper resolves each reference into a `TapEvidenceItem` whose
`provenance` records the resolution mode. The default mode is
`caller_supplied`; `provider_client` and `external_resolver` are also accepted
(configuration). TAP performs **no implicit fetch** of unrestricted enterprise
data, and evidence acquisition is never hidden inside an untestable global.

---

## 3. Outcome semantics

`TapOutcome` → `AssertionCoverage`:

| TAP native | neutral | meaning |
|---|---|---|
| `SUPPORTED` | `SUPPORTED` | evidence adequately supports the material assertion |
| `UNSUPPORTED` | `UNSUPPORTED` | evidence contradicts, or fails to support a material component |
| `CONSTRAINED` | `CONSTRAINED` | supportable only if qualifiers / scope / confidence limits are retained |
| `INDETERMINATE` | `INDETERMINATE` | incomplete / ambiguous / inaccessible / inconsistent / insufficient |
| `UNKNOWN` (native non-determination) | `INDETERMINATE` | unresolved — **never** promoted to supported |

Uncertainty is never silently converted into approval. `INDETERMINATE` is never
treated as `SUPPORTED`.

---

## 4. Request mapping

`AssertionGovernanceRequest → TapEvaluationRequest` (deterministic, total).
Preserves assertion text, assertion type, evidence references (→ evidence items
with provenance), source identity, context, policy references, and correlation /
trace ids. See `tap_provider/mapping/request.py`.

## 5. Result mapping

`TapEvaluationResult → AssertionGovernanceResult` (`tap_provider/mapping/result.py`):

| native | neutral |
|---|---|
| `outcome` | `coverage` (unknown/unmapped → `INDETERMINATE`, never `SUPPORTED`) |
| `evidence_coverage` | `evidence_coverage` (clamped to [0,1]) |
| `covered_evidence_ids` | `covered_evidence_refs` |
| `unsupported_components` | `unsupported_elements` |
| `omitted_qualifiers` | `omitted_qualifiers` |
| `constraints` | `constraints` (encoded `type=value` strings) |
| `obligations` | `obligations` (encoded strings) |
| `supported_components` + `reason_codes` | `explanation_refs` (`supported:…` / `reason:…`) |
| `trace_id` | `provider_trace_id` |
| — | `fingerprint` (deterministic SHA-256 over the mapped result) |

A malformed or unknown native outcome becomes `INDETERMINATE` (or a normalized
provider error the integration treats fail-safely). It never becomes `SUPPORTED`.

---

## 6. Qualifier and scope handling; component-level findings

TAP supports **structured analysis** of assertions containing multiple claims
(e.g. *"Supplier X reduced costs by 20% and has no compliance incidents"* →
cost-reduction *supported*, 20 % magnitude *constrained/unsupported*, no
compliance incidents *indeterminate*). Component findings map to
`unsupported_elements` and, for the *supported* breakdown that the generic
contract has no field for, to provider-owned `explanation_refs`
(`supported:<component>`) — **without modifying the framework**.

TAP represents assertions that become unsafe when qualifiers are removed
(*"Revenue increased"* vs *"Revenue increased in the North America segment during
Q2"*). It carries structured outputs for **omitted qualifier, scope expansion,
certainty inflation, unsupported generalization, temporal / population / metric
mismatch, and source-authority mismatch** via `omitted_qualifiers`, reason codes,
constrained outcomes, and unsupported components. No domain-specific policy is
embedded in the generic provider layer.

---

## 7. Constraint and obligation vocabulary

A **constraint** limits what may be asserted; an **obligation** requires an
additional step or disclosure. They are kept in separate tuples — never flattened
into one free-text field (`tap_provider/mapping/controls.py`).

- **Constraints:** `required_qualifier`, `allowed_scope`, `maximum_confidence`,
  `required_attribution`, `temporal_limitation`, `population_limitation`,
  `metric_limitation`, `approved_wording`, `prohibited_wording`.
- **Obligations:** `include_citation`, `include_uncertainty_disclosure`,
  `request_human_review`, `obtain_additional_evidence`, `retain_source_attribution`,
  `log_evidence_provenance`.

Unknown extension types are preserved as `ext:type=value` — never silently
dropped.

---

## 8. Assessment integration

`AssertionAssessmentIntegration.assess(request)` runs `TAPProvider.evaluate()` and
produces an `AssertionAssessment` (finalized/blocked flags, evidence coverage,
covered refs, unsupported elements, explanation refs, trace id, fingerprint). A
DGM `CaseRecommendationService.submit_recommendation(...)` then **cites** the
assessment through `assessment_refs`, and the audit log forms the decision trace:

```
Assertion + Evidence → TAPProvider.evaluate() → AssertionAssessment
   → recommendation (assessment_refs) → decision trace (audit events)
```

Coverage drives the recommended outcome so an unsupported/indeterminate assertion
**cannot** be represented as supported: `SUPPORTED→ADVANCE`, `CONSTRAINED→HOLD`,
`UNSUPPORTED→REJECT`, `INDETERMINATE→REQUEST_ADDITIONAL_EVIDENCE`. TAP never
creates an action authorization.

## 9. Optional (lossy) LinkedRecord projection

The canonical TAP result is `AssertionGovernanceResult` + `AssertionAssessment`.
The framework's `AssertionAssessmentIntegration.to_linked_record_snapshot(...)`
is retained only as an **optional** compatibility projection onto the kernel
`LinkedRecordPort`. It **preserves** record identity, a finalized/blocked status,
subject ref, and (as opaque metadata) the coverage ratio + trace id. It **loses**
the structured breakdown — component-level findings, per-component evidence
coverage, qualifier analysis, constraints, obligations, and explanation details —
which remain on the assessment for the recommendation to cite. It is never the
canonical result.

---

## 10. Failure policy (fail-safe)

Native failures are normalized to the framework taxonomy (`tap_provider/errors`):

| native | framework error |
|---|---|
| invalid configuration | `ProviderConfigurationError` |
| protocol / version mismatch | `ProviderProtocolError` |
| engine unavailable | `ProviderUnavailableError` |
| evaluation deadline exceeded | `ProviderTimeoutError` |
| malformed native result | `ProviderResultValidationError` |
| unexpected native failure | `ProviderError` |

**No TAP-native exception crosses the provider boundary.** In the default
`fail_safe=True` mode, a native timeout / unavailable / malformed / protocol
failure is translated *and* converted to an `INDETERMINATE` result (with the
normalized reason retained in `explanation_refs`) so the assessment workflow —
which does not itself catch — fails safe. With `fail_safe=False` the classified
`ProviderError` is raised for callers that normalize themselves. **In no case does
infrastructure failure produce `SUPPORTED`.**

## 11. Lifecycle and health

TAP uses the framework provider lifecycle (`REGISTERED → INITIALIZING → AVAILABLE
→ DEGRADED ↔ AVAILABLE → UNAVAILABLE → STOPPING → STOPPED`), distinct from DGM
business-record lifecycles, with no background threads. `tap_provider.health`
reports availability, configuration validity, protocol compatibility, evaluator
readiness, evidence-resolver readiness, and policy-bundle availability. Health
checks never produce a business assertion result and never mutate evidence; when
the engine is unavailable the provider reports `DEGRADED`.

## 12. Registry configuration

```yaml
providers:
  assertion_governance:
    default: tap-primary
    registered:
      - id: tap-primary
        implementation: tap
        enabled: true
        contract_version: "1.0"
        settings:
          mode: in_process            # or: remote
          policy_bundle: default
          evidence_resolution: caller_supplied
        secret_refs: {}               # references only — never embedded secrets
```

`TapSettings.validate()` rejects unsupported modes, incompatible contract
versions, unsupported evidence-resolution modes, and embedded plaintext secrets.
The framework registry rejects duplicate ids and contradictory defaults. TAP
implements no secret-management system.

## 13. Observability

`TapInvocationLog` captures, separately from DGM milestone events: provider id /
version, mapping version, mode, compatibility, TAP trace id, normalized outcome,
evidence count, evidence coverage, fingerprint, and (on failure) error class +
failure class. **No unrestricted evidence content and no secrets are logged** —
only counts and coverage ratios.

---

## 14. Peer relationship with ActionGate & dependency direction

TAP (assertion governance) and ActionGate (action governance) are independent
peers of distinct `ProviderKind`s. They may correlate through DGM records but:

```
TAP  must not import or invoke ActionGate
ActionGate  must not import or invoke TAP
```

Enforced dependency rules (tested in `tap_provider/tests/test_dependency_boundaries.py`):

```
decision_governance   ⇏ governance_providers / actiongate_provider / tap_provider
governance_providers   ⇏ actiongate_provider / tap_provider
actiongate_provider    ⇏ tap_provider
tap_provider           ⇏ actiongate_provider ; consumes only *.api / *.conformance
tap_provider/core      ⇏ decision_governance / governance_providers
```

## 15. Packaging

`dgm-tap-provider` packages the canonical `tap_provider` tree via a symlink,
depends on the two independent distributions, and bundles **no** copy of DGM, the
framework, ActionGate, or any domain. `packaging/verify_tap_provider_distribution.py`
builds all four wheels, installs only `dgm-tap-provider` + `dgm-actiongate-provider`
into a fresh venv (no monorepo path), and proves import, registration, conformance,
the four assertion outcomes, ActionGate operability, mutual unawareness, and the
absence of consuming layers / duplicate kernel source.

## 16. Limitations

- The generic `AssertionGovernanceResult` has no dedicated field for the
  *supported* component breakdown or for reason codes; these are retained in
  provider-owned `explanation_refs`. This is deliberate — the framework was not
  expanded merely for TAP convenience.
- The neutral request carries no `tenant` field (a known candidate for a future
  backward-compatible contract extension, not changed here).
- The reference engine is deterministic and offline; a production model-backed
  evaluator lives behind the same client seam but is out of scope. No
  nondeterministic benchmark claims are made.
- No action authorization / execution, marketplace, data crawling, secret
  manager, dashboards, or domain-specific policy are implemented (out of scope).
