# Presentation Layer Design Specification v1.0

## Document Purpose

This document specifies the **Presentation Layer** — a Layer 4 component that consumes all system signals and produces UX directives. It translates complex metacognitive state into simple, actionable presentation instructions.

---

## Part 1: Architectural Position

```
╔═════════════════════════════════════════════════════════════════════════════╗
║                         SYMBOL-U LAYER MODEL                                 ║
╠═════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  ┌─────────────────────────────────────────────────────────────────────┐   ║
║  │ LAYER 4: EXTERNAL INTERFACES                                        │   ║
║  │                                                                     │   ║
║  │   symbolu/llm/           ─── LLM Interface Contract                │   ║
║  │   symbolu/hybrid/        ─── Transformer Optimization              │   ║
║  │   symbolu/api/           ─── Unified API Layer                     │   ║
║  │   symbolu/presentation/  ─── UX Directive Layer (NEW)              │   ║
║  └─────────────────────────────────────────────────────────────────────┘   ║
║                                      ▲                                      ║
║                                      │ consumes                             ║
║  ┌─────────────────────────────────────────────────────────────────────┐   ║
║  │ LAYER 3: PIPELINE PHASES + CHITTA-VṚTTI                            │   ║
║  │                                                                     │   ║
║  │   PO1-P55 Pipeline    ─── Processing phases                        │   ║
║  │   chitta_vritti/      ─── Metacognitive signals (v2.8)             │   ║
║  └─────────────────────────────────────────────────────────────────────┘   ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝
```

### Design Principle

> **Signals are data. Presentation rules are policy.**

The Presentation Layer:
- **DOES:** Consume signals, apply rules, emit directives
- **DOES NOT:** Modify signals, override pipeline, make content decisions

---

## Part 2: Signal Inventory

### 2.1 Chitta-Vṛtti Signals (v2.8)

| Signal | Type | Range | Source | Meaning |
|--------|------|-------|--------|---------|
| `coherence` | float | [0,1] | `ChittaVrittiResult` | Cross-layer agreement |
| `score` | float | [0,1] | `ChittaVrittiResult` | Overall readiness |
| `dominant_vritti` | enum | 5 values | `ChittaVrittiResult` | Primary cognitive mode |
| `vritti.pramana` | float | [0,1] | `ChittaVrittiResult` | Valid cognition strength |
| `vritti.viparyaya` | float | [0,1] | `ChittaVrittiResult` | Misperception strength |
| `vritti.vikalpa` | float | [0,1] | `ChittaVrittiResult` | Branching strength |
| `vritti.smrti` | float | [0,1] | `ChittaVrittiResult` | Memory/staleness |
| `vritti.nidra` | float | [0,1] | `ChittaVrittiResult` | Dormancy/absence |
| `fractures` | dict | [0,1] per pair | `ChittaVrittiResult` | Pairwise disagreement |
| `primary_fracture` | tuple | layer pair | `ChittaVrittiResult` | Highest disagreement |
| `fast_path_used` | bool | T/F | `ChittaVrittiResult` | Optimization applied |

### 2.2 Raw Observable Signals (v2.6/v2.7)

| Signal | Type | Range | Source | Meaning |
|--------|------|-------|--------|---------|
| `entropy` | float | [0,1] | `ChittaVrittiInputs` | Normalized uncertainty |
| `motion` | float | [0,1] | `ChittaVrittiInputs` | Semantic delta |
| `confidence` | float | [0,1] | `ChittaVrittiInputs` | Fusion audit confidence |
| `temporal_continuity` | float | [0,1] | `ChittaVrittiInputs` | State consistency |

### 2.3 Layer Presence Signals

| Signal | Type | Source | Meaning |
|--------|------|--------|---------|
| `phonemic_present` | bool | Input check | Acoustic data available |
| `semantic_present` | bool | Input check | Embedding available |
| `structural_present` | bool | Input check | Ontology encoding available |
| `temporal_present` | bool | Input check | Temporal state available |
| `layers_present_count` | int [0-4] | Derived | Total layers available |

### 2.4 Session Context Signals

| Signal | Type | Source | Meaning |
|--------|------|--------|---------|
| `turn_count` | int | Session state | Turns in conversation |
| `consecutive_low_scores` | int | Session history | Streak of score < 0.5 |
| `consecutive_high_scores` | int | Session history | Streak of score > 0.8 |
| `previous_dominant_vritti` | enum | Session history | Last turn's dominant mode |
| `accumulated_smrti` | float | Session state | Staleness accumulation |

### 2.5 V2.7 Experimental Signals (Optional)

These signals are only available when v2.7 is enabled via `V27Config.v2_7_enabled`.
V2.7 has two modes:
- **EMA mode:** Standard exponential moving average updates
- **Bayesian mode (Alpha 2.7):** Full uncertainty quantification with confidence intervals

| Signal | Type | Range | Mode | Source | Meaning |
|--------|------|-------|------|--------|---------|
| `v27_enabled` | bool | T/F | Both | `V27Config` | Master switch |
| `bayesian_mode` | bool | T/F | Both | `V27Config` | Bayesian mode active |
| `bayesian_confidence` | float | [0,1] | Bayesian only | `BayesianStateRegister` | Reliability of estimates |
| `credible_interval_width` | float | [0,∞) | Bayesian only | `BayesianPosterior` | Uncertainty width |
| `cognitive_state` | enum | 6 values | Both | Cognitive Ability Model | thriving/striving/stable/regressing/unstable/neutral |
| `mirror_balance` | float | [0,1] | Both | Cognitive Ability Model | Self-referential coherence |
| `cognitive_ambition` | float | [-1,1] | Both | Cognitive Ability Model | Improvement vs regression |
| `concept_readiness` | float | [0,1] | Both | CRI Module | Concept Readiness Index |
| `concept_readiness_level` | enum | 5 values | Both | CRI Module | ready/nearly_ready/forming/emerging/not_ready |
| `primary_cause` | str | layer name | Both | Causal Layer | Which layer caused issues |
| `causal_attribution` | dict | layer→% | Both | Causal Layer | Attribution percentages |
| `low_utility_streak` | int | [0,∞) | Both | Self-Improvement | Consecutive low utility observations |

#### V2.7 Signal Availability by Mode

| Signal | v2.7 Disabled | EMA v2.7 | Bayesian v2.7 |
|--------|---------------|----------|---------------|
| `bayesian_confidence` | ❌ | ❌ | ✓ |
| `credible_interval_width` | ❌ | ❌ | ✓ |
| `cognitive_state` | ❌ | ✓ | ✓ |
| `mirror_balance` | ❌ | ✓ | ✓ |
| `concept_readiness` | ❌ | ✓ | ✓ |
| `primary_cause` | ❌ | ✓ | ✓ |
| `low_utility_streak` | ❌ | ✓ | ✓ |

---

## Part 3: Presentation Directives

### 3.1 Delivery Mode

Primary instruction for how to present content.

```python
class DeliveryMode(Enum):
    CONFIDENT = "confident"       # Direct, assertive delivery
    HEDGED = "hedged"             # Qualified, tentative language
    CLARIFYING = "clarifying"     # Request user clarification
    ACKNOWLEDGING = "acknowledging"  # Acknowledge uncertainty
    SILENT = "silent"             # Suppress output entirely
```

### 3.2 Confidence Indicator

Visual/textual confidence signal for UX.

```python
class ConfidenceIndicator(Enum):
    HIGH = "high"         # Green / Full indicator
    MEDIUM = "medium"     # Yellow / Partial indicator
    LOW = "low"           # Red / Minimal indicator
    UNKNOWN = "unknown"   # Gray / No indicator
```

### 3.3 Suggested Behaviors

Additional UX behaviors to trigger.

```python
@dataclass
class SuggestedBehaviors:
    show_alternatives: bool = False      # Display multiple options
    request_repeat: bool = False         # Ask user to repeat
    offer_clarification: bool = False    # Offer to explain
    show_reasoning: bool = False         # Display confidence factors
    delay_response: bool = False         # Add processing pause
    escalate_to_human: bool = False      # Flag for human review
```

### 3.4 Diagnostic Info (Optional)

For debugging/advanced UX.

```python
@dataclass
class DiagnosticInfo:
    dominant_vritti: str
    primary_fracture: Optional[tuple[str, str]]
    active_penalties: list[str]
    signal_summary: str
```

### 3.5 Complete Directive Output

```python
@dataclass(frozen=True)
class PresentationDirective:
    """Complete UX directive from Presentation Layer."""

    # Primary instructions
    delivery_mode: DeliveryMode
    confidence: ConfidenceIndicator

    # Behavioral suggestions
    behaviors: SuggestedBehaviors

    # Optional diagnostic (for debug/advanced UX)
    diagnostic: Optional[DiagnosticInfo] = None

    # Explanatory text (for user-facing explanation)
    explanation: str = ""

    # Rule that produced this directive (for audit)
    triggered_rule: str = ""
```

---

## Part 4: Rule Definitions

### 4.1 Rule Structure

Each rule has:
- **Condition:** Signal predicate that must be true
- **Priority:** Higher priority rules win conflicts
- **Directive:** Output produced when rule fires

```python
@dataclass
class PresentationRule:
    name: str
    priority: int  # Higher = checked first
    condition: Callable[[SignalBundle], bool]
    directive: Callable[[SignalBundle], PresentationDirective]
```

### 4.2 Core Rules (Priority Order)

#### Rule 1: Critical Viparyaya (Priority 100)

**Condition:** `viparyaya > 0.5` OR (`viparyaya > 0.3` AND `confidence > 0.8`)

**Rationale:** High viparyaya with high confidence = "confidently wrong" — most dangerous state.

```python
RULE_CRITICAL_VIPARYAYA = PresentationRule(
    name="critical_viparyaya",
    priority=100,
    condition=lambda s: (
        s.vritti.viparyaya > 0.5 or
        (s.vritti.viparyaya > 0.3 and s.confidence > 0.8)
    ),
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.ACKNOWLEDGING,
        confidence=ConfidenceIndicator.LOW,
        behaviors=SuggestedBehaviors(
            show_alternatives=True,
            offer_clarification=True,
            escalate_to_human=True,
        ),
        explanation="System detected potential misinterpretation",
        triggered_rule="critical_viparyaya",
    ),
)
```

#### Rule 2: Severe Nidrā (Priority 95)

**Condition:** `nidra > 0.75` OR `layers_present_count < 2`

**Rationale:** Insufficient information to produce meaningful output.

```python
RULE_SEVERE_NIDRA = PresentationRule(
    name="severe_nidra",
    priority=95,
    condition=lambda s: s.vritti.nidra > 0.75 or s.layers_present_count < 2,
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.CLARIFYING,
        confidence=ConfidenceIndicator.UNKNOWN,
        behaviors=SuggestedBehaviors(
            request_repeat=True,
        ),
        explanation="Insufficient information received",
        triggered_rule="severe_nidra",
    ),
)
```

#### Rule 3: High Vikalpa (Priority 80)

**Condition:** `vikalpa > 0.4` AND `entropy > 0.5`

**Rationale:** Multiple valid interpretations exist; offer alternatives.

```python
RULE_HIGH_VIKALPA = PresentationRule(
    name="high_vikalpa",
    priority=80,
    condition=lambda s: s.vritti.vikalpa > 0.4 and s.entropy > 0.5,
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.CLARIFYING,
        confidence=ConfidenceIndicator.MEDIUM,
        behaviors=SuggestedBehaviors(
            show_alternatives=True,
        ),
        explanation="Multiple interpretations possible",
        triggered_rule="high_vikalpa",
    ),
)
```

#### Rule 4: Elevated Smṛti (Priority 70)

**Condition:** `smrti > 0.5` AND `consecutive_low_motion > 3`

**Rationale:** System may be stuck in a loop; offer to reset.

```python
RULE_ELEVATED_SMRTI = PresentationRule(
    name="elevated_smrti",
    priority=70,
    condition=lambda s: s.vritti.smrti > 0.5 and s.session.consecutive_low_motion > 3,
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.ACKNOWLEDGING,
        confidence=ConfidenceIndicator.MEDIUM,
        behaviors=SuggestedBehaviors(
            offer_clarification=True,
        ),
        explanation="Response seems similar to previous",
        triggered_rule="elevated_smrti",
    ),
)
```

#### Rule 5: Moderate Uncertainty (Priority 60)

**Condition:** `score < 0.6` AND `score >= 0.4`

**Rationale:** Moderate confidence; hedge language but proceed.

```python
RULE_MODERATE_UNCERTAINTY = PresentationRule(
    name="moderate_uncertainty",
    priority=60,
    condition=lambda s: 0.4 <= s.score < 0.6,
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.HEDGED,
        confidence=ConfidenceIndicator.MEDIUM,
        behaviors=SuggestedBehaviors(),
        explanation="Moderate confidence in interpretation",
        triggered_rule="moderate_uncertainty",
    ),
)
```

#### Rule 6: Low Confidence (Priority 55)

**Condition:** `score < 0.4`

**Rationale:** Low overall readiness; acknowledge uncertainty.

```python
RULE_LOW_CONFIDENCE = PresentationRule(
    name="low_confidence",
    priority=55,
    condition=lambda s: s.score < 0.4,
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.ACKNOWLEDGING,
        confidence=ConfidenceIndicator.LOW,
        behaviors=SuggestedBehaviors(
            offer_clarification=True,
        ),
        explanation="Low confidence in interpretation",
        triggered_rule="low_confidence",
    ),
)
```

#### Rule 7: High Pramāṇa (Priority 50)

**Condition:** `pramana > 0.7` AND `score > 0.8`

**Rationale:** Strong valid cognition; deliver confidently.

```python
RULE_HIGH_PRAMANA = PresentationRule(
    name="high_pramana",
    priority=50,
    condition=lambda s: s.vritti.pramana > 0.7 and s.score > 0.8,
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.CONFIDENT,
        confidence=ConfidenceIndicator.HIGH,
        behaviors=SuggestedBehaviors(),
        explanation="High confidence interpretation",
        triggered_rule="high_pramana",
    ),
)
```

#### Rule 8: Default Fallback (Priority 0)

**Condition:** Always true (fallback)

**Rationale:** When no other rule matches, use moderate hedging.

```python
RULE_DEFAULT = PresentationRule(
    name="default",
    priority=0,
    condition=lambda s: True,
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.HEDGED,
        confidence=ConfidenceIndicator.MEDIUM,
        behaviors=SuggestedBehaviors(),
        explanation="Standard interpretation",
        triggered_rule="default",
    ),
)
```

### 4.3 V2.7 Experimental Rules (Optional)

These rules only fire when v2.7 signals are present in the SignalBundle.
They check `bundle.has_v27_signals` or `bundle.has_bayesian_signals` before firing.

#### Rule V1: Unreliable Estimate (Priority 98) — Bayesian Only

**Condition:** `has_bayesian_signals AND bayesian_confidence < 0.5`

**Rationale:** Low Bayesian confidence means state estimates are unreliable.

```python
RULE_UNRELIABLE_ESTIMATE_V27 = PresentationRule(
    name="unreliable_estimate_v27",
    priority=98,
    condition=lambda s: (
        s.has_bayesian_signals and s.v27.bayesian_confidence < 0.5
    ),
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.ACKNOWLEDGING,
        confidence=ConfidenceIndicator.LOW,
        behaviors=SuggestedBehaviors(
            show_reasoning=True,
            offer_clarification=True,
        ),
        explanation=f"Low estimation confidence ({s.v27.bayesian_confidence:.0%})",
        triggered_rule="unreliable_estimate_v27",
    ),
)
```

#### Rule V2: Regressing State (Priority 88) — EMA or Bayesian

**Condition:** `has_v27_signals AND cognitive_state in {regressing, unstable}`

**Rationale:** Cognitive regression indicates system quality is declining.

```python
RULE_REGRESSING_STATE_V27 = PresentationRule(
    name="regressing_state_v27",
    priority=88,
    condition=lambda s: (
        s.has_v27_signals and s.v27.is_regressing
    ),
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.CLARIFYING,
        confidence=ConfidenceIndicator.LOW,
        behaviors=SuggestedBehaviors(
            offer_clarification=True,
            escalate_to_human=True,
        ),
        explanation=f"Cognitive state: {s.v27.cognitive_state}",
        triggered_rule="regressing_state_v27",
    ),
)
```

#### Rule V3: Concept Unstable (Priority 78) — EMA or Bayesian

**Condition:** `has_v27_signals AND concept_readiness < 0.4`

**Rationale:** Concepts not yet stable enough to present confidently.

```python
RULE_CONCEPT_UNSTABLE_V27 = PresentationRule(
    name="concept_unstable_v27",
    priority=78,
    condition=lambda s: (
        s.has_v27_signals and s.v27.concept_readiness < 0.4
    ),
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.HEDGED,
        confidence=ConfidenceIndicator.LOW,
        behaviors=SuggestedBehaviors(
            offer_clarification=True,
        ),
        explanation=f"Concept not yet stable ({s.v27.concept_readiness_level})",
        triggered_rule="concept_unstable_v27",
    ),
)
```

#### Rule V4: Low Utility Streak (Priority 68) — EMA or Bayesian

**Condition:** `has_v27_signals AND low_utility_streak >= 5`

**Rationale:** Prolonged streak of low utility indicates system needs attention.

```python
RULE_LOW_UTILITY_STREAK_V27 = PresentationRule(
    name="low_utility_streak_v27",
    priority=68,
    condition=lambda s: (
        s.has_v27_signals and s.v27.low_utility_streak >= 5
    ),
    directive=lambda s: PresentationDirective(
        delivery_mode=DeliveryMode.ACKNOWLEDGING,
        confidence=ConfidenceIndicator.MEDIUM,
        behaviors=SuggestedBehaviors(
            offer_clarification=True,
            show_reasoning=True,
        ),
        explanation=f"System quality below optimal ({s.v27.low_utility_streak} observations)",
        triggered_rule="low_utility_streak_v27",
    ),
)
```

### 4.4 Rule Priority Summary

#### Core Rules (Always Active)

| Priority | Rule Name | Trigger Condition |
|----------|-----------|-------------------|
| 100 | `critical_viparyaya` | High misperception + confidence |
| 95 | `severe_nidra` | Missing information |
| 80 | `high_vikalpa` | Multiple interpretations |
| 70 | `elevated_smrti` | Stuck/repeating |
| 60 | `moderate_uncertainty` | Score 0.4-0.6 |
| 55 | `low_confidence` | Score < 0.4 |
| 50 | `high_pramana` | Strong valid cognition |
| 0 | `default` | Fallback |

#### V2.7 Experimental Rules (Only when v2.7 enabled)

| Priority | Rule Name | Mode | Trigger Condition |
|----------|-----------|------|-------------------|
| 98 | `unreliable_estimate_v27` | Bayesian only | bayesian_confidence < 0.5 |
| 88 | `regressing_state_v27` | EMA or Bayesian | cognitive_state in {regressing, unstable} |
| 78 | `concept_unstable_v27` | EMA or Bayesian | concept_readiness < 0.4 |
| 68 | `low_utility_streak_v27` | EMA or Bayesian | low_utility_streak >= 5 |

#### Combined Priority Order (when v2.7 enabled)

```
100: critical_viparyaya
 98: unreliable_estimate_v27 (Bayesian only)
 95: severe_nidra
 88: regressing_state_v27
 80: high_vikalpa
 78: concept_unstable_v27
 70: elevated_smrti
 68: low_utility_streak_v27
 60: moderate_uncertainty
 55: low_confidence
 50: high_pramana
  0: default
```

---

## Part 5: Tier-Specific Behavior

The system has 4 tiers aligned with `EngineTier`:

| Tier | Engine | Use Case | Presentation Philosophy |
|------|--------|----------|------------------------|
| `ENTERPRISE_SEARCH` | Pure STL | Classification/tagging | Strictest, minimal UX |
| `ENTERPRISE_CHAT` | STL + 7B | Specialized chat | Strict, balanced UX |
| `CONSUMER` | Full cascade | General use | Tolerant, flow-optimized |
| `DEVELOPMENT` | Full access | Testing/debug | All features, verbose |

### 5.1 Enterprise Search Tier

**Philosophy:** Classification-focused. Minimal UX overhead. Maximum strictness for tagging accuracy.

```python
ENTERPRISE_SEARCH_CONFIG = PresentationConfig(
    tier="enterprise_search",

    # Thresholds (strictest - classification must be accurate)
    viparyaya_critical_threshold=0.2,      # Very sensitive to misperception
    nidra_severe_threshold=0.4,            # Need complete information
    vikalpa_high_threshold=0.25,           # Ambiguity is costly
    smrti_elevated_threshold=0.3,
    score_confident_threshold=0.9,         # High bar for "confident"
    score_moderate_threshold=0.6,

    # Behaviors (minimal)
    allow_silent_mode=True,                # Suppress uncertain classifications
    escalate_to_human=True,                # Flag for human review
    show_reasoning_by_default=False,       # Keep output clean
    include_diagnostics=True,              # Audit trail required

    # Language (terse)
    hedging_phrases=["[Uncertain]", "[Low confidence]"],
    clarifying_phrases=["[Ambiguous input]", "[Requires clarification]"],
)
```

### 5.2 Enterprise Chat Tier

**Philosophy:** Balanced strictness for chat. Flag uncertainty but maintain conversation flow.

```python
ENTERPRISE_CHAT_CONFIG = PresentationConfig(
    tier="enterprise_chat",

    # Thresholds (strict but conversational)
    viparyaya_critical_threshold=0.3,
    nidra_severe_threshold=0.5,
    vikalpa_high_threshold=0.35,
    smrti_elevated_threshold=0.4,
    score_confident_threshold=0.85,
    score_moderate_threshold=0.5,

    # Behaviors
    allow_silent_mode=False,               # Chat must respond
    escalate_to_human=True,                # Enable escalation
    show_reasoning_by_default=True,        # Transparency
    include_diagnostics=True,              # Audit trail

    # Language (professional)
    hedging_phrases=[
        "Based on available information",
        "With moderate confidence",
        "Subject to verification"
    ],
    clarifying_phrases=[
        "Please confirm the intended meaning",
        "Clarification required"
    ],
)
```

### 5.3 Consumer Tier

**Philosophy:** Maximize flow, minimize interruption. Tolerate uncertainty for smooth UX.

```python
CONSUMER_CONFIG = PresentationConfig(
    tier="consumer",

    # Thresholds (most tolerant)
    viparyaya_critical_threshold=0.6,      # Higher = less sensitive
    nidra_severe_threshold=0.8,
    vikalpa_high_threshold=0.5,
    smrti_elevated_threshold=0.6,
    score_confident_threshold=0.7,
    score_moderate_threshold=0.4,

    # Behaviors (user-friendly)
    allow_silent_mode=False,               # Never suppress output
    escalate_to_human=False,               # Handle internally
    show_reasoning_by_default=False,       # Keep it simple
    include_diagnostics=False,             # No debug info

    # Language (conversational)
    hedging_phrases=["I think", "It seems like", "Possibly"],
    clarifying_phrases=["Did you mean", "Just to confirm"],
)
```

### 5.4 Development Tier

**Philosophy:** Full access, maximum verbosity, all features for testing/debugging.

```python
DEVELOPMENT_CONFIG = PresentationConfig(
    tier="development",

    # Thresholds (same as Enterprise Search for accuracy testing)
    viparyaya_critical_threshold=0.2,
    nidra_severe_threshold=0.4,
    vikalpa_high_threshold=0.25,
    smrti_elevated_threshold=0.3,
    score_confident_threshold=0.9,
    score_moderate_threshold=0.6,

    # Behaviors (all enabled)
    allow_silent_mode=True,
    escalate_to_human=True,
    show_reasoning_by_default=True,
    include_diagnostics=True,              # Always for debugging

    # Language (explicit tags for testing)
    hedging_phrases=["[DEV:HEDGED]", "[DEV:UNCERTAIN]"],
    clarifying_phrases=["[DEV:CLARIFY]", "[DEV:AMBIGUOUS]"],
)
```

### 5.5 Threshold Comparison (All Tiers)

| Parameter | Ent.Search | Ent.Chat | Consumer | Dev |
|-----------|------------|----------|----------|-----|
| `viparyaya_critical` | 0.2 | 0.3 | 0.6 | 0.2 |
| `nidra_severe` | 0.4 | 0.5 | 0.8 | 0.4 |
| `vikalpa_high` | 0.25 | 0.35 | 0.5 | 0.25 |
| `smrti_elevated` | 0.3 | 0.4 | 0.6 | 0.3 |
| `score_confident` | 0.9 | 0.85 | 0.7 | 0.9 |
| `allow_silent` | Yes | No | No | Yes |
| `escalate` | Yes | Yes | No | Yes |
| `diagnostics` | Yes | Yes | No | Yes |

---

## Part 6: Signal Bundle Structure

### 6.1 Complete Input Bundle

```python
@dataclass(frozen=True)
class SignalBundle:
    """All signals consumed by Presentation Layer."""

    # === Chitta-Vṛtti Outputs ===
    coherence: float
    score: float
    dominant_vritti: str
    vritti: VrittiDistribution  # pramana, viparyaya, vikalpa, smrti, nidra
    fractures: dict[tuple[str, str], float]
    primary_fracture: Optional[tuple[str, str]]
    fast_path_used: bool

    # === Raw Observables ===
    entropy: float
    motion: float
    confidence: float
    temporal_continuity: float

    # === Layer Presence ===
    layers_present_count: int
    missing_layers: list[str]

    # === Session Context ===
    session: SessionContext

    # === V2.7 Experimental Signals (Optional) ===
    v27: Optional[V27ExperimentalSignals] = None

    @property
    def has_v27_signals(self) -> bool:
        """Check if v2.7 experimental signals are available."""
        return self.v27 is not None and self.v27.is_available

    @property
    def has_bayesian_signals(self) -> bool:
        """Check if Bayesian v2.7 signals are available."""
        return self.v27 is not None and self.v27.has_bayesian_signals

    @classmethod
    def from_cv_result(
        cls,
        result: ChittaVrittiResult,
        inputs: ChittaVrittiInputs,
        session: SessionContext,
        v27: Optional[V27ExperimentalSignals] = None,
    ) -> "SignalBundle":
        """Construct bundle from CV result and context."""
        return cls(
            coherence=result.coherence,
            score=result.score,
            dominant_vritti=result.dominant_vritti,
            vritti=VrittiDistribution(**result.vritti),
            fractures=result.fractures,
            primary_fracture=result.primary_fracture,
            fast_path_used=result.fast_path_used,
            entropy=inputs.entropy,
            motion=inputs.motion,
            confidence=inputs.confidence,
            temporal_continuity=inputs.temporal_continuity,
            layers_present_count=inputs.count_present_layers(),
            missing_layers=inputs.get_missing_layer_names(),
            session=session,
            v27=v27,
        )


@dataclass
class V27ExperimentalSignals:
    """Optional signals from v2.7 experimental features."""

    # Mode flags
    v27_enabled: bool = False
    bayesian_mode: bool = False

    # Bayesian only
    bayesian_confidence: Optional[float] = None
    credible_interval_width: Optional[float] = None

    # EMA or Bayesian
    cognitive_state: str = "neutral"
    mirror_balance: float = 1.0
    concept_readiness: float = 1.0
    concept_readiness_level: str = "ready"
    primary_cause: Optional[str] = None
    low_utility_streak: int = 0

    @property
    def is_available(self) -> bool:
        return self.v27_enabled

    @property
    def has_bayesian_signals(self) -> bool:
        return self.v27_enabled and self.bayesian_mode

    @property
    def is_regressing(self) -> bool:
        return self.cognitive_state in {"regressing", "unstable"}

    @classmethod
    def disabled(cls) -> "V27ExperimentalSignals":
        return cls(v27_enabled=False)

    @classmethod
    def ema_mode(cls, **kwargs) -> "V27ExperimentalSignals":
        return cls(v27_enabled=True, bayesian_mode=False, **kwargs)

    @classmethod
    def bayesian_mode_signals(cls, bayesian_confidence: float, **kwargs) -> "V27ExperimentalSignals":
        return cls(v27_enabled=True, bayesian_mode=True, bayesian_confidence=bayesian_confidence, **kwargs)


@dataclass
class VrittiDistribution:
    pramana: float
    viparyaya: float
    vikalpa: float
    smrti: float
    nidra: float


@dataclass
class SessionContext:
    turn_count: int = 0
    consecutive_low_scores: int = 0
    consecutive_high_scores: int = 0
    consecutive_low_motion: int = 0
    previous_dominant_vritti: Optional[str] = None
    accumulated_smrti: float = 0.0
```

---

## Part 7: Composition Engine

### 7.1 Rule Executor

```python
class PresentationEngine:
    """Composes presentation directives from signals."""

    def __init__(self, config: PresentationConfig):
        self._config = config
        self._rules = self._build_rules()

    def _build_rules(self) -> list[PresentationRule]:
        """Build rules list sorted by priority (descending)."""
        rules = [
            self._make_critical_viparyaya_rule(),
            self._make_severe_nidra_rule(),
            self._make_high_vikalpa_rule(),
            self._make_elevated_smrti_rule(),
            self._make_moderate_uncertainty_rule(),
            self._make_low_confidence_rule(),
            self._make_high_pramana_rule(),
            self._make_default_rule(),
        ]
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def compute(self, signals: SignalBundle) -> PresentationDirective:
        """Compute directive by evaluating rules in priority order."""
        for rule in self._rules:
            if rule.condition(signals):
                directive = rule.directive(signals)
                return self._apply_config_overrides(directive)

        # Should never reach here due to default rule
        return self._make_default_rule().directive(signals)

    def _apply_config_overrides(
        self,
        directive: PresentationDirective,
    ) -> PresentationDirective:
        """Apply tier-specific config overrides."""
        behaviors = directive.behaviors

        # Disable escalation if not allowed
        if not self._config.escalate_to_human:
            behaviors = dataclasses.replace(
                behaviors,
                escalate_to_human=False,
            )

        # Disable silent mode if not allowed
        if not self._config.allow_silent_mode:
            if directive.delivery_mode == DeliveryMode.SILENT:
                return dataclasses.replace(
                    directive,
                    delivery_mode=DeliveryMode.ACKNOWLEDGING,
                    behaviors=behaviors,
                )

        return dataclasses.replace(directive, behaviors=behaviors)
```

### 7.2 Session State Manager

```python
class SessionStateManager:
    """Tracks session context for presentation rules."""

    def __init__(self):
        self._turn_count = 0
        self._score_history: list[float] = []
        self._motion_history: list[float] = []
        self._vritti_history: list[str] = []
        self._accumulated_smrti = 0.0

    def update(self, signals: SignalBundle) -> SessionContext:
        """Update session state and return context."""
        self._turn_count += 1
        self._score_history.append(signals.score)
        self._motion_history.append(signals.motion)
        self._vritti_history.append(signals.dominant_vritti)
        self._accumulated_smrti = signals.vritti.smrti  # From CV engine

        return SessionContext(
            turn_count=self._turn_count,
            consecutive_low_scores=self._count_consecutive_low(
                self._score_history, threshold=0.5
            ),
            consecutive_high_scores=self._count_consecutive_high(
                self._score_history, threshold=0.8
            ),
            consecutive_low_motion=self._count_consecutive_low(
                self._motion_history, threshold=0.1
            ),
            previous_dominant_vritti=(
                self._vritti_history[-2] if len(self._vritti_history) > 1 else None
            ),
            accumulated_smrti=self._accumulated_smrti,
        )

    def reset(self) -> None:
        """Reset session state."""
        self.__init__()

    def _count_consecutive_low(
        self,
        history: list[float],
        threshold: float,
    ) -> int:
        """Count consecutive values below threshold from end."""
        count = 0
        for value in reversed(history):
            if value < threshold:
                count += 1
            else:
                break
        return count

    def _count_consecutive_high(
        self,
        history: list[float],
        threshold: float,
    ) -> int:
        """Count consecutive values above threshold from end."""
        count = 0
        for value in reversed(history):
            if value > threshold:
                count += 1
            else:
                break
        return count
```

---

## Part 8: Output Examples

### Example 1: High Confidence

**Signals:**
```
score=0.92, coherence=0.95, pramana=0.85, viparyaya=0.02
```

**Directive:**
```python
PresentationDirective(
    delivery_mode=DeliveryMode.CONFIDENT,
    confidence=ConfidenceIndicator.HIGH,
    behaviors=SuggestedBehaviors(),
    explanation="High confidence interpretation",
    triggered_rule="high_pramana",
)
```

**UX Effect:** Direct delivery, green indicator, no hedging.

---

### Example 2: Detected Misperception

**Signals:**
```
score=0.45, viparyaya=0.55, confidence=0.9, primary_fracture=("semantic", "structural")
```

**Directive:**
```python
PresentationDirective(
    delivery_mode=DeliveryMode.ACKNOWLEDGING,
    confidence=ConfidenceIndicator.LOW,
    behaviors=SuggestedBehaviors(
        show_alternatives=True,
        offer_clarification=True,
        escalate_to_human=True,  # Enterprise only
    ),
    explanation="System detected potential misinterpretation",
    triggered_rule="critical_viparyaya",
)
```

**UX Effect:** "I may have misunderstood. Did you mean X or Y?"

---

### Example 3: Multiple Interpretations

**Signals:**
```
score=0.65, vikalpa=0.52, entropy=0.68
```

**Directive:**
```python
PresentationDirective(
    delivery_mode=DeliveryMode.CLARIFYING,
    confidence=ConfidenceIndicator.MEDIUM,
    behaviors=SuggestedBehaviors(
        show_alternatives=True,
    ),
    explanation="Multiple interpretations possible",
    triggered_rule="high_vikalpa",
)
```

**UX Effect:** "I heard a few possibilities: [A], [B], or [C]. Which did you mean?"

---

### Example 4: Missing Information

**Signals:**
```
nidra=0.82, layers_present_count=1, missing_layers=["semantic", "structural", "temporal"]
```

**Directive:**
```python
PresentationDirective(
    delivery_mode=DeliveryMode.CLARIFYING,
    confidence=ConfidenceIndicator.UNKNOWN,
    behaviors=SuggestedBehaviors(
        request_repeat=True,
    ),
    explanation="Insufficient information received",
    triggered_rule="severe_nidra",
)
```

**UX Effect:** "I didn't catch that clearly. Could you repeat?"

---

## Part 9: File Structure

```
symbolu/
└── presentation/
    ├── __init__.py           # Module exports
    ├── types.py              # DeliveryMode, ConfidenceIndicator, Directive, etc.
    ├── signals.py            # SignalBundle, VrittiDistribution, SessionContext
    ├── rules.py              # PresentationRule definitions
    ├── config.py             # Consumer/Enterprise configs
    ├── engine.py             # PresentationEngine (rule executor)
    ├── session.py            # SessionStateManager
    └── phrases.py            # Language templates for hedging/clarifying

tests/
└── unit/
    └── presentation/
        ├── __init__.py
        ├── test_types.py           # Directive type tests
        ├── test_signals.py         # Signal bundle tests
        ├── test_rules.py           # Individual rule tests
        ├── test_engine.py          # Engine integration tests
        ├── test_session.py         # Session state tests
        ├── test_tier_configs.py    # Consumer vs Enterprise tests
        └── test_v27_rules.py       # V2.7 experimental rules tests
```

---

## Part 10: Invariants

| ID | Invariant | Test |
|----|-----------|------|
| INV-PL-1 | Determinism | Same signals → same directive |
| INV-PL-2 | Completeness | Every signal bundle produces a directive |
| INV-PL-3 | Priority ordering | Higher priority rules checked first |
| INV-PL-4 | Config isolation | Tier config doesn't leak between instances |
| INV-PL-5 | No side effects | Engine is stateless (session manager is separate) |
| INV-PL-6 | Rule transparency | Every directive includes triggered_rule name |
| INV-PL-7 | Bounded output | All fields have valid enum/range values |

---

## Part 11: Integration Points

### 11.1 With Chitta-Vṛtti Engine

```python
from symbolu.chitta_vritti import ChittaVrittiEngine, ChittaVrittiInputs
from symbolu.presentation import PresentationEngine, SignalBundle, SessionStateManager

# Setup
cv_engine = ChittaVrittiEngine(config=CV_CONFIG)
pres_engine = PresentationEngine(config=CONSUMER_PRESENTATION_CONFIG)
session_mgr = SessionStateManager()

# Per-turn flow
def process_turn(inputs: ChittaVrittiInputs) -> PresentationDirective:
    # 1. Compute CV result
    cv_result = cv_engine.compute(inputs)

    # 2. Update session and build signal bundle
    session_ctx = session_mgr.update_from_cv(cv_result)
    signals = SignalBundle.from_cv_result(cv_result, inputs, session_ctx)

    # 3. Compute presentation directive
    directive = pres_engine.compute(signals)

    return directive
```

### 11.2 With UX Layer (Conceptual)

```python
# UX layer receives directive and applies it
def apply_directive(content: str, directive: PresentationDirective) -> str:
    """Apply presentation directive to content."""

    if directive.delivery_mode == DeliveryMode.CONFIDENT:
        return content  # No modification

    elif directive.delivery_mode == DeliveryMode.HEDGED:
        return f"I think {content}"

    elif directive.delivery_mode == DeliveryMode.CLARIFYING:
        return f"Just to confirm: {content}. Is that right?"

    elif directive.delivery_mode == DeliveryMode.ACKNOWLEDGING:
        return f"I'm not entirely certain, but {content}"

    elif directive.delivery_mode == DeliveryMode.SILENT:
        return ""  # Suppress output

    return content
```

---

## Part 12: Open Questions

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | Rule override mechanism | Config-based vs code-based | Config-based for tier flexibility |
| 2 | Phrase localization | Hardcoded vs external | External file for i18n support |
| 3 | Diagnostic verbosity | Always vs on-demand | On-demand (config flag) |
| 4 | Historical window size | Fixed vs adaptive | Fixed (10 turns) for v1 |
| 5 | Custom rules API | Allow vs restrict | Restrict for v1, open in v2 |

---

## Part 13: Summary

### What This Enables

1. **Signal → UX translation** — Complex metacognitive state becomes simple directive
2. **Tier differentiation** — Consumer flows smoothly; Enterprise flags uncertainty
3. **Auditability** — Every directive traces to a named rule
4. **Extensibility** — Add rules without changing engine
5. **Separation of concerns** — Signal computation vs presentation policy

### What It Does NOT Enable

- Content modification (only presentation style)
- Signal override (read-only consumption)
- Autonomous decisions (UX layer has final say)
- Learning (rules are static)

### The UX Contribution

The system gains the ability to:
- Adapt presentation style to confidence state
- Offer alternatives when ambiguous
- Request clarification when uncertain
- Flag potential misinterpretations
- Maintain consistent personality per tier

---

---

## Part 14: V2.7 Integration

### 14.1 Constructing V27 Signals from V27Config

```python
from symbolu.guna_modulation.v27_config import V27Config, UpdateMode
from symbolu.presentation import V27ExperimentalSignals

def build_v27_signals(
    v27_config: V27Config,
    cognitive_state: str = "neutral",
    concept_readiness: float = 1.0,
    bayesian_state: Optional[BayesianStateRegister] = None,
) -> Optional[V27ExperimentalSignals]:
    """Build V27 signals from config and state."""

    # If v2.7 is disabled, return None
    if not v27_config.v2_7_enabled:
        return None

    # Bayesian mode: include confidence from state register
    if v27_config.is_bayesian and bayesian_state is not None:
        return V27ExperimentalSignals.bayesian_mode_signals(
            bayesian_confidence=bayesian_state.overall_confidence,
            credible_interval_width=bayesian_state.tau_768_posterior.std,
            cognitive_state=cognitive_state,
            concept_readiness=concept_readiness,
        )

    # EMA mode: no Bayesian signals
    return V27ExperimentalSignals.ema_mode(
        cognitive_state=cognitive_state,
        concept_readiness=concept_readiness,
    )
```

### 14.2 Complete Integration Flow

```python
from symbolu.chitta_vritti import ChittaVrittiEngine, ChittaVrittiInputs
from symbolu.guna_modulation.v27_config import V27Config
from symbolu.presentation import (
    PresentationEngine,
    SignalBundle,
    SessionStateManager,
    V27ExperimentalSignals,
)

# Setup
v27_config = V27Config.bayesian()  # or V27Config.enterprise_t2()
cv_engine = ChittaVrittiEngine(config=CV_CONFIG)
pres_engine = PresentationEngine(config=CONSUMER_PRESENTATION_CONFIG)
session_mgr = SessionStateManager()

# Per-turn flow with v2.7
def process_turn_with_v27(
    inputs: ChittaVrittiInputs,
    v27_config: V27Config,
    bayesian_state: Optional[BayesianStateRegister] = None,
) -> PresentationDirective:

    # 1. Compute CV result
    cv_result = cv_engine.compute(inputs)

    # 2. Build V27 signals if enabled
    v27_signals = None
    if v27_config.v2_7_enabled:
        v27_signals = V27ExperimentalSignals.bayesian_mode_signals(
            bayesian_confidence=0.85,  # From state register
        ) if v27_config.is_bayesian else V27ExperimentalSignals.ema_mode()

    # 3. Update session and build signal bundle
    session_ctx = session_mgr.update_from_cv(cv_result)
    signals = SignalBundle.from_cv_result(cv_result, inputs, session_ctx, v27=v27_signals)

    # 4. Compute presentation directive
    directive = pres_engine.compute(signals)

    return directive
```

### 14.3 Mode Comparison

| Aspect | v2.7 Disabled | EMA v2.7 | Bayesian v2.7 |
|--------|---------------|----------|---------------|
| **Config** | `V27Config.disabled()` | `V27Config.enterprise_t2()` | `V27Config.bayesian()` |
| **Rule count** | 8 | 12 | 12 |
| **v27 in bundle** | None | V27ExperimentalSignals | V27ExperimentalSignals |
| **bayesian_confidence** | N/A | N/A | [0, 1] |
| **cognitive_state** | N/A | Available | Available |
| **concept_readiness** | N/A | Available | Available |

---

*Document version: 1.1*
*Updated: Added v2.7 experimental signal integration (EMA and Bayesian modes)*
*Prepared for: Presentation Layer design*
*Status: Implemented with 267 tests passing*
