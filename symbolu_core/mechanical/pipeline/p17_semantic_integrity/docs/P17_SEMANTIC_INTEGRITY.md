# P17 Semantic Integrity Monitor

## Overview

P17 is a **deterministic, observation-only governance phase** that detects integrity issues between upstream semantic and lexical decisions. It operates after P9 (lexical selection) and reports potential contradictions, drift, and policy violations without modifying any upstream state.

## What P17 Checks

### 1. Contradiction Detection (`CONTRADICTION`)
Detects when P9 lexical selections semantically contradict P8 slot values.

**Example:** P8 sets `STATE = "feeling anxious"` but P9 selects `STATE = "calm and peaceful"` → contradiction detected.

### 2. Uncertainty Collapse (`UNCERTAINTY_COLLAPSE`)
Detects when P8 has an `UNCERTAINTY` slot populated but P9 contains certainty markers.

**Example:** P8 sets `UNCERTAINTY = "unsure about this"` but P9 contains "definitely" or "certainly" → uncertainty collapsed.

### 3. Causal Inference Leakage (`CAUSE_LEAK`)
Detects causal connectors in P9 when the regime or discourse act restricts causal reasoning.

**Restricted regimes:** `DE_ESCALATE`, `STABILIZE`, `HOLD`
**Restricted discourse acts:** `REFLECTION`, `ACKNOWLEDGMENT`, `DEFERRAL`

**Example:** Regime is `DE_ESCALATE`, discourse is `REFLECTION`, but P9 contains "because" or "therefore" → cause leak detected.

### 4. Authority Drift (`AUTHORITY_DRIFT`)
Detects when RELATIONAL content (talking about others) is treated as REFLEXIVE assertions with diagnostic certainty.

**Example:** PO1 mode is `RELATIONAL` but P9 contains "she is definitely depressed" → authority drift (projecting certainty onto others).

### 5. Tone Escalation (`TONE_ESCALATION`)
Detects intensifiers and emphatic markers that may escalate tone contrary to upstream de-escalation intent.

**Example:** Multiple uses of "extremely", "absolutely", "completely" → tone escalation signal.

### 6. Insufficient Evidence (`INSUFFICIENT_EVIDENCE`)
Reports when critical upstream artifacts are missing for complete analysis.

## Why P17 Is Governance, Not Semantics

P17 is a **governance layer**, not a semantic processing layer:

1. **Read-Only**: P17 never modifies P8, P9, or any upstream artifact
2. **Non-Blocking**: P17 never blocks pipeline execution directly
3. **Advisory**: The `P17IntegrityReport` is advisory information for downstream phases
4. **Deterministic**: Same inputs always produce identical reports (no LLM, no randomness)
5. **Conservative**: False positives are acceptable; severity levels help triage

## Authority Model

```
PO1 → PO2 → PO3 → PO4 → PO5 → P6 → P7 → P8 → P9 → [P17 observes]
                                                      ↓
                                              P17IntegrityReport
                                                      ↓
                                           [Later phases may gate]
```

P17 **cannot override** any upstream decisions. It only produces a report that later phases (e.g., renderer, DHA) may use to gate insight depth or adjust posture.

## How Later Layers Should Use P17

### Gating Pattern

```python
from symbolu.mechanical.pipeline.p17_semantic_integrity import (
    maybe_run_p17,
    is_integrity_clean,
    get_integrity_score,
)

# Run P17 after P9
maybe_run_p17(ctx)

# Gate based on cleanliness
if is_integrity_clean(ctx):
    # Full insight allowed
    render_full_response(ctx)
else:
    score = get_integrity_score(ctx)
    if score >= 0.7:
        # Moderate gating
        render_with_hedging(ctx)
    else:
        # Strong gating
        render_minimal_acknowledgment(ctx)
```

### Recommended Gating Thresholds

| Score Range | Interpretation | Recommended Action |
|-------------|----------------|-------------------|
| 1.0 | Clean | Full insight allowed |
| 0.8 - 1.0 | Minor issues | Proceed with caution |
| 0.5 - 0.8 | Moderate issues | Add hedging, reduce depth |
| 0.0 - 0.5 | Significant issues | Minimal response, acknowledge only |

### Issue Severity Guide

| Severity | Meaning | Action |
|----------|---------|--------|
| `INFO` | Informational, edge case | Log for debugging |
| `WARN` | Possible drift | Review, consider hedging |
| `HIGH` | Clear violation | Gate insight depth |

## API Reference

### Main Entry Point

```python
def maybe_run_p17(ctx: Any) -> Optional[P17IntegrityReport]:
    """Run P17 and attach report to ctx.p17"""
```

### Report Structure

```python
@dataclass(frozen=True)
class P17IntegrityReport:
    issues: Tuple[IntegrityIssue, ...]  # Detected issues
    integrity_score: float               # 0.0-1.0 (1.0 = clean)
    is_clean: bool                       # True if no HIGH severity
    debug: Dict[str, Any]               # Trace information
    version: str                         # Schema version
    architectural_phase: str             # "P17"
```

### Issue Structure

```python
@dataclass(frozen=True)
class IntegrityIssue:
    issue_type: IntegrityIssueType       # CONTRADICTION, UNCERTAINTY_COLLAPSE, etc.
    severity: Severity                   # INFO, WARN, HIGH
    message: str                         # Human-readable description
    evidence_paths: Tuple[str, ...]      # Paths to source artifacts
    clause_index: Optional[int]          # Clause-specific if applicable
```

## Testing

Run P17 tests:

```bash
pytest symbolu/mechanical/pipeline/tests/p17_semantic_integrity/ -v
```

## Version History

- **1.0.0**: Initial implementation
  - Core integrity checks: contradiction, uncertainty collapse, cause leak, authority drift, tone escalation
  - Deterministic scoring with severity-based penalties
  - Read-only, observation-only design
