# Routing Contract v2.0

**Status:** Production
**Version:** 2.0
**Last Updated:** 2025-12-09

---

## 1. Purpose

This document defines the **Routing Contract** between the TTOR (Two-Tier Ontology Router), MLCR (Multi-Layer Coherence Router), mapper engines (HRM/LCM/LAM), and the Symbol-U pipeline.

The contract serves as:

- **Behavioral specification** for deterministic routing decisions
- **Integration interface** between TTOR, MLCR, and mapper engines
- **Drift prevention mechanism** enforced by CI tests
- **Patent alignment guarantee** for zero-LLM routing logic

All routing decisions are:
- **Deterministic**: Same inputs always produce same outputs
- **Zero-LLM**: No language models involved in routing logic
- **Auditable**: Full debug trail via RoutingPlan.debug dictionary
- **Testable**: CI-enforced drift detection on canonical rules

---

## 2. Inputs to TTOR

The TTOR router accepts a `RouterContext` containing the following signals:

### 2.1 Aspect Probabilities (`aspect_probs: Dict[str, float]`)

Probability distribution over 10 cognitive aspects, classified into two tiers:

**Lower Tier Aspects** (operational, concrete):
- `Execution` — Action-oriented, task completion
- `Identity` — Self-concept, personal context
- `Form` — Structure, patterns, definitions
- `Cognition` — Logical reasoning, problem-solving

**Upper Tier Aspects** (abstract, transcendent):
- `Agency` — Intentionality, choice, autonomy
- `Reasoning` — Meta-cognition, philosophical inquiry
- `Purpose` — Meaning-making, "why" questions
- `Observation` — Awareness, witnessing, meta-perspective
- `Core` — Fundamental self, unchanging essence
- `Universal` — Collective consciousness, transpersonal

### 2.2 Entropy Measures

**Dimensional Entropy (`H_D`)**: Entropy over 10 dimensional classifications
- Range: `[0, ln(10)] ≈ [0, 2.303]`
- Measures uncertainty in dimensional categorization

**Guna Entropy (`H_G`)**: Entropy over 3 guna qualities (sattva, rajas, tamas)
- Range: `[0, ln(3)] ≈ [0, 1.099]`
- Measures energetic uncertainty

**Kosha Entropy (`H_K`)**: Entropy over 5 kosha layers
- Range: `[0, ln(5)] ≈ [0, 1.609]`
- Measures depth-layer uncertainty

**Normalized Entropy (`normalized_entropy`)**: Weighted combination
- Formula: `normalized_entropy = 0.5 * (H_D / ln(10)) + 0.3 * (H_G / ln(3))`
- Range: `[0, 1]`
- Primary signal for mapper activation thresholds

### 2.3 Experiential Anchor Scores (`anchor_scores: Dict[str, float]`)

Scores over 9 experiential anchors, classified into two tiers:

**Lower Tier Anchors**:
- `Needs` — Survival, security
- `Exchange` — Transactions, reciprocity
- `Challenge` — Problem-solving, overcoming obstacles

**Upper Tier Anchors**:
- `Belonging` — Connection, community
- `Relation` — Interpersonal dynamics
- `Change` — Transformation, growth
- `Meaning` — Purpose, significance
- `Role` — Social identity, contribution
- `Collective` — Shared consciousness

### 2.4 Domain Classification (`domain: str`)

Categorical domain of the query:

**Task-Oriented Domains** (favor LOWER tier):
- `task`, `code`, `math`, `lookup`

**Reflective Domains** (favor UPPER tier):
- `therapy`, `philosophy`, `spiritual`, `identity`

**Regulated Domains** (require safety overrides):
- `health`, `finance`, `legal`

**Default Domain**:
- `generic`

### 2.5 Long-Arc Tension (`long_arc_tension: float`)

Measures temporal continuity and unresolved narrative threads:
- Range: `[0, 1]`
- Primary trigger for LAM (Long-Arc Mapper) activation
- Future integration: TemporalBhavaTracker

### 2.6 Risk Level (`risk_level: str`)

Classification of query risk:
- Values: `low`, `medium`, `high`, `critical`
- Affects `regulated_mode` and `allow_metaphor` flags

---

## 3. Canonical Mapper Rules v2.0

The following formulas are **frozen** and enforced by CI drift tests.

### 3.1 HRM (High-Resolution Mapper)

**Activation Rule:**
```python
use_hrm = (tier != LOWER) and (normalized_entropy > 0.40)
```

**Purpose:**
Activates high-resolution symbolic processing for abstract, upper-tier queries with sufficient uncertainty.

**When Active:**
- Tier is UPPER or HYBRID
- Normalized entropy exceeds 0.40

**Capabilities:**
- Abstract reasoning
- Philosophical inquiry
- Symbolic pattern recognition
- Meta-cognitive analysis

---

### 3.2 LCM (Low-Context Mapper)

**Activation Rule:**
```python
use_lcm = (tier == LOWER) and (normalized_entropy > 0.50)
```

**Purpose:**
Activates procedural, low-context processing for concrete, lower-tier queries with moderate uncertainty.

**When Active:**
- Tier is LOWER
- Normalized entropy exceeds 0.50

**Capabilities:**
- Semantic coherence
- Factual accuracy
- Linguistic consistency
- Task-oriented execution

---

### 3.3 LAM (Long-Arc Mapper)

**Activation Rule:**
```python
use_lam = (
    long_arc_tension > 0.50
    or temporal_patterns_detected
    or (domain in ["therapy", "identity", "spiritual"] and normalized_entropy > 0.60)
)
```

**Purpose:**
Activates temporal continuity and deep emotional anchoring for queries requiring narrative context or therapeutic grounding.

**When Active:**
- Long-arc tension exceeds 0.50, OR
- Temporal patterns are detected (future enhancement), OR
- Domain is therapy/identity/spiritual AND normalized entropy exceeds 0.60

**Capabilities:**
- Emotional grounding
- Therapeutic context
- Temporal continuity
- Self-reflection support
- Identity integration

---

### 3.4 Threshold Summary

| Mapper | Tier Constraint | Entropy Threshold | Tension Threshold | Domain Constraint |
|--------|----------------|-------------------|-------------------|-------------------|
| HRM    | != LOWER       | > 0.40            | —                 | —                 |
| LCM    | == LOWER       | > 0.50            | —                 | —                 |
| LAM    | —              | > 0.60 (domain)   | > 0.50            | therapy/identity/spiritual |

---

## 4. CI Enforcement

The routing contract is enforced by two test suites in `symbolu/core/drift_tests/`:

### 4.1 `test_mapper_activation_regions.py`

**Grid-Based Validation:**
Tests all combinations of:
- Tier: LOWER / HYBRID / UPPER
- Domain: generic / task / therapy / identity / spiritual
- Normalized Entropy: [0.0, 0.39, 0.41, 0.49, 0.51, 0.59, 0.61, 1.0]
- Long-Arc Tension: [0.0, 0.49, 0.51, 1.0]

**Purpose:**
Ensures that TTOR produces mapper flags (`use_hrm`, `use_lcm`, `use_lam`) that exactly match the canonical formulas across the entire parameter space.

**Drift Detection:**
If any test case fails, it indicates that TTOR logic has drifted from the canonical rules. This must be treated as a **contract violation** and requires immediate investigation.

**Edge Cases Covered:**
1. LOWER tier, entropy 0.49 → no HRM, no LCM
2. LOWER tier, entropy 0.51 → use_lcm = True
3. UPPER tier, entropy 0.41 → use_hrm = True
4. UPPER tier, entropy 0.39 → use_hrm = False
5. Therapy domain, entropy 0.61, tension=0.0 → use_lam = True
6. Generic domain, entropy 0.61, tension=0.0 → use_lam = False
7. Any domain, tension 0.51 → use_lam = True

---

### 4.2 `test_pipeline_routing_profiles.py`

**End-to-End Profile Validation:**
Tests representative user profiles:
- **LOWER + task**: Simple procedural queries (code, math, lookup)
- **UPPER + therapy**: Deep reflective queries with high entropy + tension
- **UPPER + identity**: Self-exploration queries in identity domain
- **Generic + low entropy**: Balanced queries with no strong signals

**Purpose:**
Ensures that the full TTOR + MLCR pipeline produces expected behavior for realistic input scenarios.

**Integration Validation:**
Verifies that TTOR and MLCR expert router produce identical mapper activation flags for the same inputs, ensuring consistency across the pipeline.

---

### 4.3 CI Workflow Integration

The drift tests are integrated into `.github/workflows/ttor-ci.yml`:

```yaml
- name: Run Routing Drift Tests
  run: |
    pytest symbolu/symbolu/core/drift_tests -q
```

**Failure Policy:**
Any drift test failure causes CI to fail, blocking merges until the contract is restored.

---

## 5. Extensibility

The routing contract is designed to support future enhancements while preserving determinism:

### 5.1 Temporal Patterns Detection

**Current State:**
`temporal_patterns_detected` is hardcoded to `False` in both TTOR and MLCR.

**Future Integration:**
Will be wired to `TemporalBhavaTracker` to detect:
- Unresolved narrative threads
- Recurring emotional themes
- Long-term identity shifts
- Session-to-session continuity

**Contract Impact:**
When enabled, will expand LAM activation zones but will NOT change existing thresholds.

---

### 5.2 New Domains

**Adding Domains:**
New domains can be added to domain classifications (task/reflective/regulated) without breaking the contract, as long as:
1. Existing domains remain in their categories
2. Canonical thresholds (0.40, 0.50, 0.60) are preserved
3. Drift tests are updated to cover new domains

**Example:**
Adding `"creative"` to reflective domains would require:
- Updating `REFLECTIVE_DOMAINS` in `symbolu/mechanical/pipeline/ttor/constants.py`
- Adding `"creative"` to `LAM_DOMAINS` in canonical rules if it should trigger LAM
- Adding drift test cases for the new domain

---

### 5.3 New Mappers

**Adding Mappers:**
Future mappers (e.g., DMM - Deep Memory Mapper) can be added by:
1. Defining a new canonical activation rule
2. Adding the rule to TTOR `_compute_module_flags()`
3. Adding the flag to `RoutingPlan` dataclass
4. Creating drift tests for the new mapper

**Backward Compatibility:**
Existing HRM/LCM/LAM rules must remain unchanged. New mappers must use independent activation logic.

---

## 6. Contract Violations

Any change that causes drift tests to fail is a **contract violation** and requires one of:

### 6.1 Bug Fix (Restore Contract)

If TTOR or MLCR logic was unintentionally changed:
- Revert the change
- Verify drift tests pass
- Document the incident

### 6.2 Intentional Rule Update (Requires Approval)

If canonical rules need to be updated (rare):
1. Document the rationale (e.g., empirical evidence, user feedback)
2. Update canonical formulas in:
   - `symbolu/mechanical/pipeline/ttor/router.py` (`_compute_module_flags`)
   - `symbolu/mechanical/mlcr/expert_router.py` (`route`)
   - `symbolu/core/drift_tests/test_mapper_activation_regions.py` (`expected_mappers`)
   - This document (`docs/routing_contract.md`)
3. Update drift tests to reflect new rules
4. Increment contract version (e.g., v2.0 → v2.1)
5. Obtain approval from project maintainers
6. Verify all tests pass

---

## 7. Audit Trail

Every routing decision produces a complete audit trail via `RoutingPlan.debug`:

```python
{
    "lower_base": float,
    "upper_base": float,
    "lower_anchor_boost": float,
    "upper_anchor_boost": float,
    "normalized_entropy": float,
    "entropy_ratio": float,
    "H_D": float,
    "H_G": float,
    "H_K": float,
    "lower_entropy_boost": float,
    "upper_entropy_boost": float,
    "domain": str,
    "lower_domain_mod": float,
    "upper_domain_mod": float,
    "final_lower": float,
    "final_upper": float,
    "tier_threshold": float,
    "tier_difference": float,
    "is_high_entropy": bool,
    "is_high_tension": bool,
    "entropy_threshold": float,
    "tension_threshold": float,
    "long_arc_tension": float,
    "conflict_score": float,
    "use_hrm": bool,
    "use_lcm": bool,
    "use_lam": bool,
    "risk_level": str,
    "regulated_mode": bool,
    "allow_metaphor": bool,
}
```

This debug dictionary enables:
- Reproducible routing decisions
- Post-hoc analysis of unexpected behavior
- Compliance verification for regulated domains
- Performance tuning and optimization

---

## 8. Summary

The Routing Contract v2.0 ensures:

✅ **Determinism**: Same inputs → same outputs
✅ **Zero-LLM**: No language models in routing
✅ **Testability**: CI-enforced drift detection
✅ **Auditability**: Complete debug trail
✅ **Patent Alignment**: Canonical rules match IP claims
✅ **Extensibility**: Future enhancements without breaking changes

**Contract Guardians:**
- `symbolu/core/drift_tests/test_mapper_activation_regions.py`
- `symbolu/core/drift_tests/test_pipeline_routing_profiles.py`

**Contract Violations:**
Any change causing drift test failures requires approval and documentation.

---

**End of Routing Contract v2.0**
