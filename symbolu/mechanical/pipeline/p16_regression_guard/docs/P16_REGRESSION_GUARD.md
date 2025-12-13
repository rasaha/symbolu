# P16 Regression Guard — Input Contract + Regression Guard

## Purpose

The P16 Regression Guard is a **deterministic, non-LLM, non-authoritative layer** that enforces immutability of upstream authority decisions from phases PO1–P15. It ensures that any work performed in P16 or later phases does not:

1. Mutate upstream authority objects
2. Drift from established authority decisions
3. Expand semantic slots or allowed actions
4. Amplify certainty where uncertainty existed
5. Escalate acoustic parameters
6. Write to forbidden paths

## Authority Model

### Read-Only Upstream Access

P16 operates in **READ-ONLY** mode for all upstream phases (PO1–P15). It captures a cryptographic hash snapshot of all authority-bearing objects before any P16 work begins, then validates that these hashes remain unchanged after P16 work completes.

### Authority Scopes

The following scopes are tracked:

| Scope | Phase | Context Attribute | Authority Level |
|-------|-------|-------------------|-----------------|
| PO1 | Phase -1 | `phase_minus_one` | Grounding (AUTHORITY) |
| PO2 | Phase 0 | `phase_zero` | Intent (AUTHORITY) |
| PO3 | Phase 1 | `allowed_actions` | Actions (AUTHORITY) |
| PO4 | Phase O4 | `po4_proposal` | Planner (READ) |
| PO5 | Phase O5 | `po5_execution_eligibility` | Execution (READ) |
| P6 | Phase 6 | `p6_regime` | Regime (AUTHORITY) |
| P7 | Phase 7 | `p7_discourse_envelope` | Discourse (AUTHORITY) |
| P8 | Phase 8 | `semantic_frame` | Semantics (AUTHORITY) |
| P9 | Phase 9 | `lexical_frame` | Lexical (READ) |
| P10 | Phase 10 | `p10_acoustic` | Acoustic (PROTECTED) |
| P11 | Phase 11 | `p11_prosodic_evidence` | Prosodic (READ) |
| P12 | Phase 12 | `p12_consistency` | Consistency (READ) |
| P13 | Phase 13 | `p13_safety_envelope` | Safety (PROTECTED) |
| P14 | Phase 14 | `p14_surface` | Surface (PROTECTED) |
| P15 | Phase 15 | `interaction_directive` | Interaction (AUTHORITY) |

### Write Permissions

P16 is **ONLY** permitted to write to:

| Path | Mode |
|------|------|
| `p16` | Full write |
| `p16_guard_result` | Full write |
| `_p16_snapshot` | Full write |
| `debug` | Append-only |
| `metrics` | Append-only |

Any attempt to write to other paths is a contract violation.

## What It Reads

The guard reads and hashes the following from each authority scope:

### From PO1 (Grounding)
- `overall_policy` (PERMITTED / CAUTIONARY / BLOCKED)
- `dominant_mode` (DETACHED / REFLEXIVE / ENGAGED)
- `clauses` (list of analyzed clauses)

### From PO2 (Intent)
- `intent_type` (INFORM / CLARIFY / SUPPORT / REFLECT)
- `response_posture` (ENGAGE_OPEN / ACKNOWLEDGE / HOLD)

### From PO3 (Allowed Actions)
- `allowed_actions` (frozenset of action classes)

### From P6 (Regime)
- `regime` (STABILIZE / REFLECT / INFORM / CLARIFY / DE_ESCALATE / HOLD)

### From P7 (Discourse)
- `act` (EXPLANATION / QUESTION / REFLECTION / etc.)
- `allowed` (boolean)

### From P8 (Semantics)
- `slots` (dict of slot name → value)
- `uncertainty` (boolean flag)

### From P10/P13/P14 (Acoustic Protected)
- All acoustic parameters
- Safety bounds
- Surface plan settings

### From P15 (Interaction)
- `mode` (INFORMATIVE / SUPPORTIVE / etc.)
- `blocked` (boolean)

## What It Forbids

### 1. Authority Drift
Any change to authority scope hashes is forbidden:

```python
# Before P16:
snapshot = guard.snapshot(ctx)  # Hash: "abc123"

# After P16 work:
# If ctx.p6_regime.regime changed, hash differs
violations = guard.assert_unchanged(ctx, snapshot)
# → AUTHORITY_DRIFT violation
```

### 2. Slot Expansion
Adding new semantic slots to P8 is forbidden:

```python
# Before: slots = {"subject": ..., "predicate": ...}
# After:  slots = {"subject": ..., "predicate": ..., "new_slot": ...}
# → SLOT_EXPANSION violation
```

### 3. Certainty Amplification
If P8 had uncertainty markers, P16 cannot introduce certainty signals:

```python
# If snapshot.uncertainty_present is True:
ctx.certainty = 0.95  # → CERTAINTY_AMPLIFICATION violation
ctx.p16 = {"certainty": 0.9}  # → CERTAINTY_AMPLIFICATION violation
```

### 4. Acoustic Escalation
P10, P13, P14 frames cannot be modified:

```python
ctx.p10_acoustic.energy_level = 0.9  # → ACOUSTIC_ESCALATION violation
ctx.p13_safety_envelope.max_energy = 2.0  # → ACOUSTIC_ESCALATION violation
```

### 5. Blocked State Unblocking
A blocked state cannot become unblocked:

```python
# If snapshot.blocked_state is True:
ctx.interaction_directive.blocked = False  # → BLOCKED_UNBLOCK violation
```

### 6. Forbidden Writes
Writing to non-allowed paths:

```python
guard.enforce_allowlist(ctx, written_paths={"p6_regime"})
# → FORBIDDEN_WRITE violation
```

### 7. Append-Only Replacement
Replacing (not appending) to debug/metrics:

```python
debug_before = [{"log": "entry1"}]
ctx.debug = [{"log": "new_entry"}]  # Replaced, not appended
# → APPEND_ONLY_REPLACEMENT violation
```

## How Hashes Are Computed

### Stable JSON Serialization

Objects are converted to stable JSON using:

```python
json.dumps(
    stabilized_obj,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

Key properties:
- **Dict keys sorted**: `{"z": 1, "a": 2}` → `{"a":2,"z":1}`
- **Enums use .value**: `MyEnum.VALUE` → `"VALUE"`
- **Frozensets sorted**: `frozenset({"b", "a"})` → `["a", "b"]`
- **Dataclasses via asdict()**: Fields sorted by name

### Hash Computation

```python
stable_hash(obj) = sha256(stable_json(obj)).hexdigest()
```

This produces a 64-character hex string that is:
- **Deterministic**: Same input → same hash
- **Stable**: Key ordering doesn't matter
- **Collision-resistant**: SHA-256 cryptographic hash

### Aggregate Hash

Individual scope hashes are combined:

```python
aggregate = stable_hash_combine(*sorted_scope_hashes)
```

## How to Interpret Violations

### ContractViolation Fields

```python
@dataclass(frozen=True)
class ContractViolation:
    scope: AuthorityScope      # Which phase was violated
    violation_type: ViolationType  # Type of violation
    field_path: str            # Specific field that changed
    expected: Any              # Original value/hash
    observed: Any              # Current value/hash
    reason: str                # Human-readable explanation
    severity: str              # ERROR or WARNING
```

### Example Violation Output

```
P16 Contract Violation: 2 violation(s) detected.
P16 operates READ-ONLY on upstream phases PO1-P15.
Violations:
  - [P6] AUTHORITY_DRIFT: field='p6_regime', expected=abc123..., observed=def456...
  - [P15] BLOCKED_UNBLOCK: field='blocked_state', expected=True, observed=False
```

### Violation Types

| Type | Description |
|------|-------------|
| `HASH_MISMATCH` | Generic hash comparison failure |
| `AUTHORITY_DRIFT` | Authority scope hash changed |
| `SLOT_EXPANSION` | New semantic slots added |
| `ACTION_EXPANSION` | New allowed actions added |
| `BLOCKED_UNBLOCK` | Blocked state became unblocked |
| `CERTAINTY_AMPLIFICATION` | Certainty added despite uncertainty |
| `FORBIDDEN_WRITE` | Write to non-allowed path |
| `APPEND_ONLY_REPLACEMENT` | Append-only content replaced |
| `ACOUSTIC_ESCALATION` | Acoustic parameters modified |
| `SAFETY_BOUND_EXCEEDED` | Safety envelope violated |
| `CONTRACT_BREACH` | Generic contract violation |
| `INVARIANT_VIOLATION` | Structural invariant broken |

## Usage

### Basic Usage

```python
from symbolu.mechanical.pipeline.p16_regression_guard import (
    maybe_run_p16_guard_pre,
    maybe_run_p16_guard_post,
)

# Before P16 work:
snapshot, contract = maybe_run_p16_guard_pre(ctx)

# ... P16 work happens ...

# After P16 work:
maybe_run_p16_guard_post(ctx, snapshot)  # Raises on violation
```

### Context Manager Usage

```python
from symbolu.mechanical.pipeline.p16_regression_guard import P16GuardContext

with P16GuardContext(ctx) as guard_ctx:
    # P16 work here
    ctx.p16 = {"result": "computed"}  # OK - allowed write
    # Any mutations to upstream → raises at exit
```

### Diagnostic Usage (No Raise)

```python
from symbolu.mechanical.pipeline.p16_regression_guard import (
    validate_p16_without_raise,
)

result = validate_p16_without_raise(ctx, snapshot)
if result and not result.passed:
    for v in result.violations:
        print(f"{v.scope}: {v.violation_type} - {v.reason}")
```

### Disabling the Guard

```python
# Per-context disable:
ctx._p16_disabled = True

# Or:
ctx._p16_enabled = False
```

## Design Principles

1. **No LLM Calls**: Purely mechanical, deterministic logic
2. **Deterministic Output**: Same input → same hashes → same violations
3. **Immutable Contracts**: All schema types are frozen dataclasses
4. **Fail-Fast**: Raises exception immediately on violation
5. **Complete Audit**: All violations collected, not just first
6. **No Auto-Correction**: Violations are reported, never silently fixed
7. **Minimal Diff**: Only touches P16 integration points

## Files

```
p16_regression_guard/
├── __init__.py              # Public exports
├── p16_contract_schema.py   # Contract, violation, snapshot types
├── p16_hashing.py           # Stable hashing utilities
├── p16_regression_guard.py  # Core guard logic
├── p16_integration.py       # Pipeline integration functions
└── docs/
    └── P16_REGRESSION_GUARD.md  # This document
```

## Testing

Run tests with:

```bash
pytest symbolu/mechanical/pipeline/tests/p16_regression_guard/ -v
```

Test groups:
- **Group A**: Hash determinism
- **Group B**: Mutation detection
- **Group C**: Allow-list enforcement
- **Group D**: Blocked safety invariants
- **Group E**: Adversarial case regression (clause explosion)
