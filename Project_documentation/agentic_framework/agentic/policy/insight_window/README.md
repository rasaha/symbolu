# Phase 32 — Insight Window Gating

## Purpose

Phase 32 determines one thing only:

> **"Is the system allowed to surface deeper insight right now?"**

It does **not** decide:
- What insight to show
- How to phrase it
- Whether to act
- Whether to advise

It produces a single numeric gate signal (`insight_depth`) and a reasoned explanation (`gating_reason_codes`).

## Output: InsightWindowEnvelope

```python
@dataclass(frozen=True)
class InsightWindowEnvelope:
    is_open: bool                          # True if depth >= 0.55
    insight_depth: float                   # [0.0, 1.0]
    gating_reason_codes: Tuple[str, ...]   # Why gating tightened
    confidence_band: ConfidenceBand        # "low" | "medium" | "high"
```

This envelope is **read-only downstream**.

## Core Formula (LOCKED)

```
raw_depth =
    0.40 * coherence_v3_quality
  + 0.30 * ucf_score
  + 0.20 * schema_stability
  + 0.10 * (1 - drift_fusion_index)
```

### Monotonic Penalties

| Condition | Penalty |
|-----------|---------|
| `temporal_entropy_diff > 0.6` | multiply by 0.85 |
| `coherence_v3_quality < 0.45` | multiply by 0.80 |
| `acoustic_alignment_score < 0.4` | multiply by 0.95 (observer-only) |

⚠️ **Penalties can ONLY reduce depth, NEVER increase it.**

### Gate Rule

```python
is_open = insight_depth >= 0.55
```

## Inputs (Read-Only)

From `PipelineContext`:

| Input | Source |
|-------|--------|
| `coherence_v3_quality` | P10/P12 coherence state |
| `ucf_score` | P26 unified consciousness formula |
| `schema_stability` | P33 schema adaptive routing |
| `drift_fusion_index` | P19 drift fusion |
| `temporal_entropy_diff` | P18 temporal entropy |
| `acoustic_alignment_score` | P23 alignment report (optional) |

❌ **P22/P23/P24 must never be imported directly.**

## Hard Invariants

### Authority Constraints

❌ **MUST NOT:**
- Trigger regime changes (P6)
- Select discourse acts (P7)
- Modify semantics or lexical frames (P8-P9)
- Influence persona, DHA, renderer
- Trigger actions or agent handoff

✅ **MAY:**
- Close insight windows
- Leave windows unchanged

❌ **MUST NEVER:**
- Open insight windows due to acoustic input alone

### Monotonicity (MANDATORY)

Insight gating is **monotonic-restrictive**:
- New signals may close windows but **never open them**
- Acoustic input can only reduce depth, never increase it

## Required Invariants

| Code | Description |
|------|-------------|
| INV-P32-1 | Insight gating never opens due to observers |
| INV-P32-2 | Gate monotonicity enforced |
| INV-P32-3 | No upstream influence |
| INV-P32-4 | Deterministic behavior |
| INV-P32-5 | Envelope is advisory only |

## Reason Codes

Reason codes reflect **why gating tightened**, never why it opened:

- `LOW_COHERENCE_QUALITY` — coherence_v3_quality < 0.45
- `HIGH_TEMPORAL_ENTROPY` — temporal_entropy_diff > 0.6
- `ELEVATED_DRIFT` — drift_fusion_index > 0.6
- `ACOUSTIC_MISALIGNMENT` — acoustic_alignment_score < 0.4
- `SCHEMA_INSTABILITY` — schema_stability low
- `LOW_UCF_SCORE` — ucf_score < 0.4
- `GATE_CLOSED` / `GATE_OPEN` — final state
- `DEPTH_BELOW_THRESHOLD` — depth < 0.55

## Usage

```python
from symbolu.policy.insight_window import (
    get_insight_gating_engine,
    InsightWindowEnvelope,
)

# Via pipeline integration
from symbolu.mechanical.pipeline.p32_insight_window import maybe_run_p32

envelope = maybe_run_p32(ctx)

if envelope and envelope.is_open:
    print(f"Insight window open at depth {envelope.insight_depth}")
else:
    print(f"Window closed: {envelope.gating_reason_codes}")
```

## Design Principle

> Insight gating decides **WHEN** insight is allowed, **NOT** what insight is given.

> Sound must obey meaning. Meaning must never obey sound.

## File Structure

```
symbolu/policy/insight_window/
├── __init__.py                 # Public API
├── insight_envelope.py         # InsightWindowEnvelope dataclass
├── insight_gating_formula.py   # LOCKED formula and penalties
├── insight_gating_engine.py    # Main computation engine
└── README.md                   # This file

symbolu/mechanical/pipeline/p32_insight_window/
├── __init__.py
└── p32_integration.py          # Pipeline integration
```

## Version

**P32_VERSION = "1.0.0"**
