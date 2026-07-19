# ActionGate — Human-Curated Policy Governance

**Status:** Implemented (Phase HP-2 — per-decision authority mode).
Backward-compatible; off unless a policy book is configured, and identical to
the pre-feature service when no registry / per-rule mode is set.

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
- **`HumanPolicyEngine`** — deterministic, fail-closed evaluator; accepts an
  optional `mode` (default) and `criticality_registry`, and resolves the
  per-decision effective mode.
- **`ActionCriticalityRegistry` / `CriticalityClass` / `UncertainDisposition`**
  — human-authored, deterministic action-class → criticality classification and
  its conservative uncertain-handling policy.
- **`resolve_authority_mode` / `AuthorityModeResolution`** — the per-decision
  mode precedence (rule → registry → engine default).
- **`RequestContext` / `build_request_context`** — a dependency-light,
  duck-typed view of an `AuthorizationRequest` (no Pydantic import → no cycle).
- **`resolve_human_policy` / `stricter_decision`** — the adapter + composition
  helper used by `GovernanceService`.
- **`build_default_book()`** — a small illustrative book mirroring a few frozen
  reference invariants; meant to be replaced by a real book.

## 3. Authority modes — the switch (now resolved per decision)

The relationship between a matched human verdict and the LLM/model-derived
decision is `HumanPolicyMode`. It is **resolved per authorization request**, so a
single `GovernanceService` handles critical and non-critical actions
concurrently — each under its own mode. See §3a for the resolution precedence;
the engine-level `mode` is only the lowest-precedence default.

```python
HumanPolicyEngine(book, mode=HumanPolicyMode.BASELINE)          # default
HumanPolicyEngine(book, mode=HumanPolicyMode.SOURCE_OF_TRUTH)
HumanPolicyEngine(book, criticality_registry=registry)          # per-decision
```

### Mode A — `BASELINE` (default): "human sets the baseline, the LLM can only tighten"

When a curated rule matches, its verdict becomes the **baseline**. Because every
downstream layer is already stricter-only, the composed result is the **more
restrictive** of the human baseline and the LLM baseline:

```
final = stricter_of( human_baseline , llm_baseline_and_downstream_tightening )
```

A human `ALLOW` is a **ceiling of permissiveness**, not a guarantee — a
low-confidence or drifting model can still deny. A human `DENY` /
`REQUIRE_APPROVAL` can never be loosened by the model.

### Mode B — `SOURCE_OF_TRUTH`: "humans are the source of truth"

When a curated rule matches, its verdict is **dispositive**. The model layers
(confidence gate, JEPA, domain, shadow, sovereign biases) are still evaluated —
and fully recorded in the audit event — but they are **advisory**: they cannot
change the decision. A human `ALLOW` stays `ALLOW` even if the model would have
deferred or denied.

The one carve-out: a human `ALLOW` is still subject to the **independent,
fail-closed hard blocks that are themselves human-configured** (not LLM
judgements) — a forbidden capability, an agent `PolicyEngine` hard-deny, or a
closed generation gate. These still force `DENY`, because a permissive policy
book must not be able to open, say, `malware_execution`.

Mechanically this is a final reconciliation (Step 5f) that restores the human
verdict after the model layers run.

### Truth table (both modes)

| Human match | Human verdict | Strong LLM says | `BASELINE` | `SOURCE_OF_TRUTH` |
|---|---|---|---|---|
| yes | `DENY` | ALLOW | **DENY** | **DENY** |
| yes | `REQUIRE_APPROVAL` | ALLOW | **DEFER** (+human) | **DEFER** (+human) |
| yes | `ALLOW` | ALLOW | **ALLOW** | **ALLOW** |
| yes | `ALLOW` | DENY (low confidence) | **DENY** (LLM tightened) | **ALLOW** (human wins) |
| yes | `ALLOW` | ALLOW, but forbidden capability | **DENY** | **DENY** (hard block) |
| **no** | — | ALLOW | **ALLOW** | **ALLOW** |
| **no** | — | DENY | **DENY** | **DENY** |
| n/a (no engine) | — | any | LLM baseline | LLM baseline |

The effective mode is recorded on every decision (see §3a and §4).

## 3a. Per-decision authority-mode resolution

The mode is **not fixed at engine construction**. It is resolved for each request
by precedence, so one service runs both semantics at once — critical decisions
under `SOURCE_OF_TRUTH`, non-critical under `BASELINE`.

**Precedence** (highest first), implemented in `resolve_authority_mode()`:

1. **Explicit `authority_mode` on the matched rule** — a human's deliberate
   per-rule override (e.g. promoting an otherwise non-critical action to
   `SOURCE_OF_TRUTH`).
2. **Human-authored criticality registry** (`ActionCriticalityRegistry`):
   - `CRITICAL` action class → `SOURCE_OF_TRUTH`;
   - `NON_CRITICAL` → `BASELINE`;
   - `UNKNOWN` → conservative (see below).
3. **Engine/service default mode** — backward-compatible; used when neither a
   per-rule mode nor a registry classification applies.

**Criticality is deterministic and human-authored.** `ActionCriticalityRegistry`
classifies by human-configured class membership (risk level / action type / tool)
plus caller-declared deterministic impact facts (`last_replica`, `irreversible`,
`bulk`, `public_sensitive`, …). Those impact facts may only **promote** an action
to `CRITICAL`; the LLM producing the governance verdict has **no input** to
classification, so it can never downgrade an action to non-critical. It may of
course still *tighten* the decision under `BASELINE`, and it may escalate.

**Conservative handling of uncertain criticality** (`UncertainDisposition`):

- `REQUIRE_APPROVAL` (default): resolve to `SOURCE_OF_TRUTH` **and** apply a
  `DEFER` floor — an unclassified action with a broad human `ALLOW` becomes
  `DEFER` (+ human confirmation), never a silent pass.
- `TREAT_AS_CRITICAL`: resolve to `SOURCE_OF_TRUTH` and let the matched verdict
  stand.

**The LLM can never downgrade a `SOURCE_OF_TRUTH` decision to `BASELINE`** —
mode resolution consults only human-authored inputs (rule mode, registry,
engine default); the model is never a source. It can recommend escalation
(tighten) but not relax the authority mode.

**Fail-closed hard blocks remain the final layer** in both modes: a forbidden
capability, an agent `PolicyEngine` hard-deny, or a closed generation gate force
`DENY` even over a human `SOURCE_OF_TRUTH` `ALLOW` (these are independent
human-configured invariants, not LLM judgements).

```python
from agentic.agentic_framework.human_policy import (
    ActionCriticalityRegistry, UncertainDisposition, HumanPolicyEngine,
)
registry = ActionCriticalityRegistry(
    critical_risk_levels=("destructive", "privileged"),
    non_critical_risk_levels=("read_only",),
    critical_tools=("prod_db",),
    uncertain_disposition=UncertainDisposition.REQUIRE_APPROVAL,
)
engine = HumanPolicyEngine(book, criticality_registry=registry)  # per-decision
```

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
   JEPA override): capture `llm_baseline_decision`, `resolve_human_policy(...)`
   (which resolves the **per-decision** `effective_mode`), then set the baseline
   — `stricter_of(llm, human)` when the effective mode is `BASELINE`, or the human
   verdict directly when `SOURCE_OF_TRUTH`; apply the conservative floor; set
   `eligible=False` when non-ALLOW; capture `human_requires_human`.
3b. **Step 5f** (after the model layers / shadow): compute `hard_block` +
   provenance and the `model_advisory_decision`; when the effective mode is
   `SOURCE_OF_TRUTH` and a rule matched, restore the human verdict (undoing model
   tightening) unless a hard block forces `DENY`; then attribute
   `final_authority_used` ∈ {`HARD_BLOCK`, `HUMAN_SOURCE_OF_TRUTH`,
   `HUMAN_BASELINE_COMPOSED`, `MODEL`}.
4. **`effective_requires_human`** — OR in `human_requires_human` (incl. the
   uncertain `DEFER` floor); in a source-of-truth override it is set from the
   human verdict.
5. **Rationale codes** — `HUMAN_POLICY:*`, `HUMAN_POLICY_RULE:*`,
   `HUMAN_POLICY_MODE:*`, `HUMAN_POLICY_MODE_SOURCE:*`,
   `HUMAN_POLICY_CRITICALITY:*`, `HUMAN_POLICY_CONSERVATIVE_FLOOR:*`,
   `HUMAN_POLICY_AUTHORITATIVE`, `HUMAN_POLICY_FINAL_AUTHORITY:*`.
6. **Audit** — full `human_policy` block on the `AuditEvent` and provenance keys
   in `request_snapshot`; a `human_policy` field on `AuthorizationResponse`.
   (Both models gained an optional `human_policy` field with a default, so
   existing callers are unaffected.) The block distinguishes: configured
   **default mode**, matched **rule mode**, **criticality** + basis + implied
   mode, **effective mode** + **resolution source**, **human verdict**,
   **model advisory verdict**, **hard-block** decision + provenance, and the
   **final authority used**.

## 5. Guarantees

- **Fail-closed.** A configured book that errors (bad regex, malformed rule)
  resolves to `DENY` with a `HUMAN_POLICY_ERROR` code — never a silent fallback
  to the LLM. The whole `authorize()` remains wrapped in the existing
  fail-closed try/except.
- **Backward-compatible.** No engine → `human_policy` is `None`; no registry and
  no per-rule mode → the engine default governs exactly as before. Decisions are
  byte-identical to the pre-feature service in those cases.
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
    HumanPolicyMode,
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

# The switch: how the human verdict relates to the LLM.
#   BASELINE        → human sets the baseline, the LLM can only tighten (default)
#   SOURCE_OF_TRUTH → the human verdict is dispositive; the LLM is advisory
svc = GovernanceService(
    human_policy_engine=HumanPolicyEngine(book, mode=HumanPolicyMode.SOURCE_OF_TRUTH),
)
```

Callers declare facts via `AuthorizationRequest.metadata["facts"]`, e.g.
`{"facts": {"last_replica": True}}`.

## 8. Testing

`agentic/agentic_framework/tests/test_human_policy.py` (41 tests): engine/book
unit tests (matching, facts, priority overrides, fail-closed, content hash),
`GovernanceService` integration tests proving each row of the truth table,
mode-switch tests (`BASELINE` vs `SOURCE_OF_TRUTH`, incl. the hard-block
carve-out), criticality-registry + `resolve_authority_mode` precedence tests,
and **concurrent per-decision** tests proving one service instance handles
critical (`SOURCE_OF_TRUTH`), non-critical (`BASELINE`), uncertain
(conservative `DEFER`), explicit-rule-override, and hard-block requests
back-to-back.

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
