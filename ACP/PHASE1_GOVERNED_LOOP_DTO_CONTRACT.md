# Phase-1 Governed-Loop DTO ↔ Module-Type Contract

*The exact, field-by-field mapping between the console API's Pydantic DTOs and the
platform modules' native types, for every Phase-1 endpoint. This is the turnkey
build spec: it documents what is implemented in `ugence_console_api/` today and is
the reference for any re-implementation or client.*

**Import discipline (invariant).** Every native type below is imported through a
**frozen public API surface** only:

- `from governance_providers.api import ActionGovernanceRequest, ActionGovernanceResult, ActionGovernanceOutcome, AssertionGovernanceRequest, AssertionGovernanceResult, AssertionCoverage`
- `from actiongate_provider.configuration import build_actiongate_provider`
- `from tap_provider.configuration import build_tap_provider`
- Context Minimization: `actiongate_context_ablation.compressor` / `.units`

No console code imports a module-internal path. This keeps the console inside the
versioning guarantees recorded in `platform/PLATFORM_FREEZE_V1.json` (importing
internals would be a MAJOR-class break).

DTOs live in `ugence_console_api/models.py`; the mappings live in
`ugence_console_api/capabilities/*.py`; the orchestrator is
`ugence_console_api/orchestrator.py`.

---

## Vocabularies (verbatim from the modules — all fail-closed)

| Enum | Values | Source |
|---|---|---|
| `ActionGovernanceOutcome` | `AUTHORIZED` · `AUTHORIZED_WITH_CONSTRAINTS` · `DENIED` · `INDETERMINATE` · `EXPIRED` | `governance_providers/contracts/action.py` |
| `AssertionCoverage` | `SUPPORTED` · `UNSUPPORTED` · `INDETERMINATE` · `CONSTRAINED` | `governance_providers/contracts/assertion.py` |
| Clearance disposition | `CLEAR` · `HOLD` | console (`operational_safety.py`) |
| `DeploymentMode` | `shadow` · `recommendation` · `enforcement` | console (`models.py`) |

**Non-compensatory gate sets** (a stage "passes" only if its verdict is in the set;
`orchestrator.py`):

```
_ASSERTION_OK = {"SUPPORTED", "CONSTRAINED"}
_ACTION_OK    = {"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"}
_CLEARANCE_OK = {"CLEAR"}
would_execute = assertion_ok AND action_ok AND clearance_ok
```

---

## 1 · `POST /v1/gateway/minimize` — Context Minimization (Agent Gateway)

**Question:** *What information may the reasoning process receive?*

### Request DTO → native

`MinimizeRequest`:

| DTO field | Type | → native (`actiongate_context_ablation.units.SemanticUnit` / `.compressor.Context`) |
|---|---|---|
| `context_id` | `str` | `Context.id` |
| `units[]` | `list[ContextUnit]` | `Context.units: tuple[SemanticUnit]` |
| `units[].id` | `str` | `SemanticUnit.id` |
| `units[].text` | `str` | `SemanticUnit.text` |
| `units[].redundancy_set` | `str \| None` | `SemanticUnit.redundancy_set` |
| `units[].protected` | `bool` | selects the `protected_ids` frozenset (units with `protected=True`) |
| `correlation_id` | `str` | threaded by the orchestrator; not consumed by the module |

Fixed at construction: `SemanticUnit.source_type = "state_fact"` (a member of the
module's frozen `SOURCE_TYPES`), `Context.base = {"tool": "console", "verb":
"admit", "target": []}`, `Context.data_origin = "authored-fixture"`.

### Module call

```python
kept_ids, removed_ids = structural_compress(ctx, protected_ids)   # lossless dedup
```

### Native → response DTO

`MinimizeResult`:

| DTO field | Type | ← from |
|---|---|---|
| `kept_ids` | `list[str]` | `kept_ids` |
| `removed_ids` | `list[str]` | `removed_ids` |
| `total_units` | `int` | `len(units)` |
| `removed_units` | `int` | `len(removed_ids)` |
| `protected_ids` | `list[str]` | sorted `protected_ids` |
| `lossless` | `bool` | every removed unit is a duplicate of a represented fact |

> The full authorization-preserving compressor (`compress(ctx, protect_fn, sp,
> target_reduction)`) needs a fitted protection detector and a signed policy; it is
> the productization upgrade. Phase 1 uses the deterministic, model-free
> `structural_compress`.

---

## 2 · `POST /v1/assertions/evaluate` — Truth Assurance Platform (Truth & Evidence)

**Question:** *Is the completed response sufficiently supported before delivery?*
**Maturity:** emerging.

### Request DTO → native

`AssertionRequest` → `governance_providers.api.AssertionGovernanceRequest`:

| DTO field | Type | → native field | native type |
|---|---|---|---|
| `assertion` | `str` | `assertion` | `str` |
| `assertion_type` | `str` | `assertion_type` | `str` |
| `evidence_refs` | `list[str]` | `evidence_refs` | `tuple[str, ...]` |
| `source_identity` | `str` | `source_identity` | `str` |
| `policy_refs` | `list[str]` | `policy_refs` | `tuple[str, ...]` |
| `correlation_id` | `str` | `correlation_id` | `str` |
| — | | `context` | `Mapping[str,str]` (default `{}`) |

### Module call

```python
provider = build_tap_provider()                       # TAPProvider (real engine)
result   = provider.evaluate(assertion_governance_request)   # -> AssertionGovernanceResult
```

### Native → response DTO

`AssertionGovernanceResult` → `AssertionVerdict`:

| native field | type | → DTO field | DTO type |
|---|---|---|---|
| `coverage` | `AssertionCoverage` | `coverage` | `str` (`.value`) |
| `evidence_coverage` | `float` (0..1) | `evidence_coverage` | `float` |
| `covered_evidence_refs` | `tuple[str,...]` | `covered_evidence_refs` | `list[str]` |
| `unsupported_elements` | `tuple[str,...]` | `unsupported_elements` | `list[str]` |
| `constraints` | `tuple[str,...]` | `constraints` | `list[str]` |
| `obligations` | `tuple[str,...]` | `obligations` | `list[str]` |
| `provider_trace_id` | `str` | `provider_trace_id` | `str` |
| `omitted_qualifiers`, `explanation_refs`, `fingerprint` | | *(not surfaced in v1)* | |

---

## 3 · `POST /v1/actions/authorize` — ActionGate (Action Control)

**Question:** *May THIS exact action be executed?* CER-bound.

### CER identity (computed before the call)

The action is reduced to a canonical, order-independent envelope and hashed —
this is the Canonical Execution Request identity and the loop's join key
(`action_control.py`):

```python
envelope = {
  "action_type", "requested_parameters" (sorted), "actor",
  "authority_context", "target_resource", "policy_refs" (sorted),
}
fingerprint = sha256(json(envelope, sort_keys=True)).hexdigest()
cer_id      = f"cer-{fingerprint[:16]}"
```

`cer_id` is passed to the engine as `idempotency_key` and returned to the client,
so the same action always yields the same CER identity across runs.

### Request DTO → native

`ActionRequest` → `governance_providers.api.ActionGovernanceRequest`:

| DTO field | Type | → native field | native type |
|---|---|---|---|
| `action_type` | `str` | `action_type` | `str` |
| `requested_parameters` | `dict[str,str]` | `requested_parameters` | `Mapping[str,str]` |
| `actor` | `str` | `actor` | `str` |
| `authority_context` | `str` | `authority_context` | `str` |
| `target_resource` | `str` | `target_resource` | `str` |
| `policy_refs` | `list[str]` | `policy_refs` | `tuple[str,...]` |
| `risk_context` | `dict[str,str]` | `risk_context` | `Mapping[str,str]` |
| `evidence_refs` | `list[str]` | `evidence_refs` | `tuple[str,...]` |
| `correlation_id` | `str` | `correlation_id` | `str` |
| `authorization_expired` | `bool` | `authorization_expired` | `bool` |
| *(computed)* `cer_id` | `str` | `idempotency_key` | `str` |

### Module call

```python
provider = build_actiongate_provider()                # ActionGateProvider (real engine)
result   = provider.authorize(action_governance_request)   # -> ActionGovernanceResult
```

### Native → response DTO

`ActionGovernanceResult` → `ActionVerdict`:

| native field | type | → DTO field | DTO type |
|---|---|---|---|
| `outcome` | `ActionGovernanceOutcome` | `outcome` | `str` (`.value`) |
| `constraints` | `tuple[str,...]` | `constraints` | `list[str]` |
| `obligations` | `tuple[str,...]` | `obligations` | `list[str]` |
| `reason_codes` | `tuple[str,...]` | `reason_codes` | `list[str]` |
| `authority_basis` | `str` | `authority_basis` | `str` |
| `provider_trace_id` | `str` | `provider_trace_id` | `str` |
| *(computed)* | | `cer_id` | `str` |
| *(computed)* | | `action_fingerprint` | `str` (full sha256) |
| `expiry`, `fingerprint` | | *(not surfaced in v1)* | |

> **Productization path:** kernel-bound CER authorization via
> `governance_providers.api.ActionGovernanceControlPlaneAdapter.authorize(action_request, cer)`
> with a real `decision_governance.actions.cer.ContextEnvelopeRecord`. Phase 1
> computes the CER identity directly so the loop is self-contained.

---

## 4 · `POST /v1/actions/clear` — Autonomous Control Plane (operational safety)

**Question:** *Is execution operationally safe right now?* The digital sibling of
the physical robotics ACP. Deterministic, fail-closed: any missing required signal
holds the action.

### Request DTO

`OperationalSignals`:

| DTO field | Type | Meaning | Rule |
|---|---|---|---|
| `error_budget_remaining` | `float \| None` (0..1) | fraction of SLO error budget left | `HOLD` if `< 0.10`; `MISSING_error_budget` if absent |
| `cluster_health` | `str \| None` | `green` / `yellow` / `red` | `HOLD` if `red` (`CLUSTER_UNHEALTHY`) or unknown; `MISSING_cluster_health` if absent |
| `change_freeze_active` | `bool \| None` | change-freeze window | `HOLD` if `True` (`CHANGE_FREEZE_ACTIVE`); `MISSING_change_freeze` if absent |

### Response DTO

`ClearanceVerdict`:

| DTO field | Type | Meaning |
|---|---|---|
| `disposition` | `str` | `CLEAR` (all checks pass) or `HOLD` |
| `reason_codes` | `list[str]` | `["OPERATIONALLY_SAFE"]` when clear; else the failing reason codes |
| `evaluated` | `dict[str,str]` | the signals actually evaluated (for audit) |

---

## 5 · `POST /v1/governed-loop/shadow` — orchestrator

Runs stages 1→4 in order, records the trail, and computes the mode-aware
disposition. `POST /v1/governed-loop/scenario/{id}` runs the same over a named
sample.

### Request DTO

`GovernedLoopRequest`:

| field | Type | Notes |
|---|---|---|
| `mode` | `DeploymentMode` | default `shadow` |
| `correlation_id` | `str \| None` | generated (`corr-<hex>`) if absent; propagated into `assertion` and `action` |
| `context_units` | `list[ContextUnit]` | Gateway stage; skipped if empty |
| `assertion` | `AssertionRequest` | Verify stage |
| `action` | `ActionRequest` | Authorize stage |
| `operational_signals` | `OperationalSignals` | Clear stage |

### Response DTO

`GovernedLoopResult`:

| field | Type | Notes |
|---|---|---|
| `correlation_id` | `str` | join key |
| `cer_id` | `str` | from the Authorize stage |
| `mode` | `DeploymentMode` | echoed |
| `stages` | `list[StageResult]` | Gateway · Verify · Authorize · Clear · Record |
| `final_disposition` | `str` | mode-aware, human-readable (see below) |
| `would_execute` | `bool` | what enforcement *would* do — computed even in shadow |
| `recorded` | `bool` | audit chain written |

`StageResult`: `stage`, `capability`, `module`, `module_maturity`, `question`,
`decision`, `summary`, `detail` (the full stage DTO as a dict).

**Final-disposition text by mode** (`orchestrator._final_disposition`):

| mode | `would_execute=True` | `would_execute=False` |
|---|---|---|
| `shadow` | `OBSERVED (shadow) — enforcement would ALLOW; nothing changed.` | `… would BLOCK; nothing changed.` |
| `recommendation` | `RECOMMENDATION — would ALLOW; no escalation required.` | `… would BLOCK; escalation surfaced to humans.` |
| `enforcement` | `ALLOWED` | `BLOCKED` |

---

## 6 · `GET /v1/audit/{correlation_id}` — Audit & Reconstruction

Returns `AuditChain`:

| field | Type | Notes |
|---|---|---|
| `correlation_id` | `str` | key |
| `cer_id` | `str` | the action's CER identity |
| `mode` | `str` | deployment mode of the run |
| `final_disposition` | `str` | as above |
| `entries` | `list[AuditEntry]` | ordered `stage · module · decision · summary · detail` for the four decision stages |

`GET /v1/audit` lists recorded correlation ids. The store is in-memory
(`ugence_console_api/audit.py`); the reconstruction shape is designed to survive
the swap to a durable, tamper-evident, hash-chained record (roadmap gap #3).

---

## Reference request (copy-paste)

```json
POST /v1/governed-loop/shadow
{
  "mode": "shadow",
  "context_units": [
    {"id": "u2", "text": "Prometheus shows 3 healthy replicas.", "redundancy_set": "replicas"},
    {"id": "u3", "text": "prometheus reports three healthy replicas", "redundancy_set": "replicas"}
  ],
  "assertion": {
    "assertion": "payments-api has 3 healthy replicas and no active incidents.",
    "assertion_type": "operational_state",
    "evidence_refs": ["evidence:prometheus-snapshot", "evidence:pagerduty-clear"],
    "source_identity": "agent:infra-bot",
    "policy_refs": ["policy:k8s-prod-writes"]
  },
  "action": {
    "action_type": "k8s.delete_deployment",
    "requested_parameters": {"namespace": "prod", "name": "payments-api"},
    "actor": "agent:infra-bot",
    "authority_context": "sre-oncall",
    "target_resource": "prod/payments-api",
    "policy_refs": ["policy:k8s-prod-writes"],
    "risk_context": {"blast_radius": "high", "environment": "production"}
  },
  "operational_signals": {
    "error_budget_remaining": 0.04,
    "cluster_health": "yellow",
    "change_freeze_active": true
  }
}
```

Yields: Verify `SUPPORTED`, Authorize `AUTHORIZED`, Clear `HOLD`
(`CHANGE_FREEZE_ACTIVE`, `ERROR_BUDGET_EXHAUSTED`) →
`would_execute=false` → `OBSERVED (shadow) — enforcement would BLOCK; nothing
changed.`
