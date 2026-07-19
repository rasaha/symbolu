# ActionGate — Human-Curated Policy Governance

**Status:** Implemented (Phase HP-1). Backward-compatible; off unless a policy
book is configured.

**Scope:** Adds a deterministic, human-authored policy layer to the ActionGate
decision core (`agentic/agentic_framework/governance_service.py`) so that
governance verdicts can originate from **explicit human-curated rules** instead
of only from LLM-produced signals.

---

## 1. Problem: today the decision comes from the LLM

The ActionGate decision core is `GovernanceService.authorize()`. Today the
top-level verdict (`ALLOW` / `DENY` / `DEFER`) is derived from **model-authored
signals**:

| Signal | Source | Where it enters |
|--------|--------|-----------------|
| `quality_score`, `coherence_score`, `internal_consistency`, `goal_alignment`, `trajectory_confidence` | LLM / agent self-assessment | `_build_confidence_signals` → `ConfidenceGate.evaluate` |
| Confidence gate execution/escalation mode | derived from the above | `_compute_governance_decision` |
| SafetyContract preconditions | derived from the above | `_build_safety_contract_summary` |
| JEPA composite latent-state assessment | ontology/vritti model | `apply_jepa_override` |

Every rule-based overlay that already exists is **stricter-only** and cannot
issue an authoritative human *allow*:

- `safety.governance_patterns.policy_engine.PolicyEngine` — per-agent
  allow/deny/blackout/rate-limit, but **hard-deny only** and no action-attribute
  rules;
- `domain_policy`, `shadow_ai` — can only tighten.

A fully human-curated deterministic gate *does* exist elsewhere in the repo —
`cyber_security/action_gate_reference/action_gate_ref/policy.py` (signed
`DEFAULT_RULES` like "`DB_DELETE` + `last_replica` → DENY", "require dual
approver") — but it was **never wired into** the agentic ActionGate.

**Gap:** there is no way for a security owner to author a rule that
*authoritatively* decides an action inside the agentic ActionGate. The ALLOW
path belongs to the LLM.

## 2. What was added

A new stdlib-only module **`agentic/agentic_framework/human_policy.py`** plus a
minimal wiring change in `governance_service.py`.

```
AuthorizationRequest
   │
   ├─ ToolRiskClassifier.classify()                 (risk level)
   ├─ ConfidenceGate + SafetyContract               (LLM-derived baseline)   ── Step 5
   ├─ HumanPolicyEngine.evaluate()   ◄── NEW         (human baseline)         ── Step 5a
   │        reconcile: stricter_of(llm_baseline, human_baseline)
   ├─ JEPA / domain / shadow / generation-gate / agent-policy   (tighten only)
   └─ AuthorizationResponse  (+ human_policy audit block)
```

### Module pieces

- **`HumanPolicyVerdict`** — `ALLOW`, `ALLOW_WITH_CONSTRAINTS`,
  `REQUIRE_APPROVAL`, `DENY` (ordered by restrictiveness).
- **`HumanPolicyRule`** — a frozen, conjunctive match rule over request
  attributes: `action_types`, `tool_names`, `risk_levels`, `actor_ids`,
  `agency_levels`, `capabilities_any`, `target_patterns` (regex), and declared
  boolean `when_facts` / `unless_facts`. Outputs a verdict, optional
  `constraints`, `approver_policy`, and a `priority`.
- **`HumanPolicyBook`** — a versioned, content-hashed collection of rules with a
  stable `policy_version()` (mirrors `action_gate_ref.policy.policy_version`).
- **`HumanPolicyEngine`** — deterministic, fail-closed evaluator.
- **`RequestContext` / `build_request_context`** — a dependency-light,
  duck-typed view of an `AuthorizationRequest` (no Pydantic import → no cycle).
- **`resolve_human_policy` / `stricter_decision`** — the adapter + composition
  helper used by `GovernanceService`.
- **`build_default_book()`** — a small illustrative book mirroring a few frozen
  reference invariants; meant to be replaced by a real book.

## 3. Authority model — "human sets the baseline, the LLM can only tighten"

When a curated rule matches, its verdict becomes the **baseline** governance
decision. Because every downstream layer is already stricter-only, the composed
result is the **more restrictive** of the human baseline and the LLM baseline:

```
final = stricter_of( human_baseline , llm_baseline_and_downstream_tightening )
```

### Truth table

| Human rule match | Human verdict | Strong LLM says | Final decision | Why |
|---|---|---|---|---|
| yes | `DENY` | ALLOW | **DENY** | human DENY is dispositive |
| yes | `REQUIRE_APPROVAL` | ALLOW | **DEFER** (+requires_human) | human forces confirmation |
| yes | `ALLOW` | ALLOW | **ALLOW** | both agree |
| yes | `ALLOW` | DENY (low confidence) | **DENY** | LLM tightened the ceiling |
| yes | `ALLOW_WITH_CONSTRAINTS` | ALLOW | **ALLOW** (+constraints recorded) | constraints attached |
| **no** | — | ALLOW | **ALLOW** | silent → LLM baseline unchanged |
| **no** | — | DENY | **DENY** | silent → LLM baseline unchanged |
| n/a (no engine) | — | any | LLM baseline | fully backward-compatible |

Key property: a human `ALLOW` is a **ceiling of permissiveness**, not a
guarantee — a low-confidence or drifting model can still deny. A human `DENY` /
`REQUIRE_APPROVAL` can never be loosened by the model.

### Rule selection within a book

Among all matching rules the winner has the greatest
`(priority, verdict_severity)`, tie-broken by `rule_id` for determinism.
Consequences:
- at equal priority the **most restrictive** rule wins (DENY > REQUIRE_APPROVAL
  > ALLOW_WITH_CONSTRAINTS > ALLOW);
- a **higher-priority** ALLOW is how you write a narrow allow-exception to a
  broad DENY (e.g. a trusted service account).

## 4. Wiring points in `governance_service.py`

All changes are additive and guarded by `self._human_policy_engine is not None`:

1. **Imports** — `human_policy` symbols.
2. **`__init__`** — new optional `human_policy_engine` parameter, stored as
   `self._human_policy_engine`.
3. **Step 5a** (between the LLM baseline `_compute_governance_decision` and the
   JEPA override): `resolve_human_policy(...)`, then
   `governance_decision = stricter_of(llm, human)`; set `eligible=False` when it
   becomes non-ALLOW; capture `human_requires_human`.
4. **`effective_requires_human`** — OR in `human_requires_human`.
5. **Rationale codes / string** — `HUMAN_POLICY:*`, `HUMAN_POLICY_RULE:*`, and a
   human-readable clause.
6. **Audit** — full `human_policy` block on the `AuditEvent` and provenance keys
   in `request_snapshot`; a `human_policy` field on `AuthorizationResponse`.
   (Both models gained an optional `human_policy` field with a default, so
   existing callers are unaffected.)

## 5. Guarantees

- **Fail-closed.** A configured book that errors (bad regex, malformed rule)
  resolves to `DENY` with a `HUMAN_POLICY_ERROR` code — never a silent fallback
  to the LLM. The whole `authorize()` remains wrapped in the existing
  fail-closed try/except.
- **Backward-compatible.** No engine → `human_policy` is `None`, decisions are
  byte-identical to before. Verified: the full pre-existing governance suite
  (380 tests) passes unchanged.
- **Deterministic + auditable.** Evaluation is a pure function of (request,
  risk, facts, book). The book has a stable `policy_version()` recorded in the
  audit event.
- **No new heavy dependencies.** `human_policy.py` is standard-library only.

## 6. Relationship to the frozen reference gate

`action_gate_ref` remains the canonical, signed, deterministic gate for the
`cyber_security` enforcement path. This layer brings the *same idea* — human
rules decide, not the model — into the agentic ActionGate, expressed against the
`AuthorizationRequest` schema. The `HumanPolicyBook` content hash mirrors the
reference `policy_hash` pattern so the two can share a signing / provenance story
later (see Future work).

## 7. How to use

```python
from agentic.agentic_framework.governance_service import GovernanceService
from agentic.agentic_framework.human_policy import (
    HumanPolicyEngine, HumanPolicyBook, HumanPolicyRule, HumanPolicyVerdict,
)

book = HumanPolicyBook(
    name="acme-prod", version="2026.07",
    rules=(
        HumanPolicyRule(rule_id="no-last-replica", verdict=HumanPolicyVerdict.DENY,
                        risk_levels=("destructive",), when_facts=("last_replica",)),
        HumanPolicyRule(rule_id="destructive-dual-control",
                        verdict=HumanPolicyVerdict.REQUIRE_APPROVAL,
                        risk_levels=("destructive",), approver_policy="dual_control"),
        HumanPolicyRule(rule_id="sa-writes-ok", verdict=HumanPolicyVerdict.ALLOW,
                        risk_levels=("write",), actor_ids=("service-account",),
                        priority=100),
    ),
)
svc = GovernanceService(human_policy_engine=HumanPolicyEngine(book))
```

Callers declare facts via `AuthorizationRequest.metadata["facts"]`, e.g.
`{"facts": {"last_replica": True}}`.

## 8. Testing

`agentic/agentic_framework/tests/test_human_policy.py` (24 tests):
engine/book unit tests (matching, facts, priority overrides, fail-closed,
content hash) and `GovernanceService` integration tests proving each row of the
truth table above.

## 9. Future work

- **Signed policy books.** Reuse `action_gate_ref.signing` so a book carries a
  root-of-trust signature, verified at load like the reference bundle.
- **Externalized book loading.** Load a book from the Policy Externalization
  Layer / a tenant-scoped store (`tenant_id` / `org_id` fields already exist on
  the request) instead of constructing it in code.
- **`ALLOW_WITH_CONSTRAINTS` enforcement.** Constraints are currently recorded
  and surfaced; a downstream enforcement hook could bind them to the execution
  token (as the reference gateway does).
- **Structured facts bridge.** Auto-derive `facts` from the mechanical pipeline
  / parameters instead of relying on the caller to declare them.
