# Stitching & Fusion: Implementation-Ready Specification

## Overview

This document resolves the architectural ambiguity between Stitching and Fusion by defining clear, non-overlapping responsibilities. The design is deterministic, Tier-1 safe, and implementation-ready.

**Design Principle:**

> "Stitching decides what is ALLOWED. Fusion decides what is BEST."

---

## 1. Clear Responsibility Definition

### 1.1 Stitching: The Gatekeeper

**Single Responsibility:** Determine which candidates are structurally valid and contextually appropriate.

| Aspect | Description |
|--------|-------------|
| Role | Boolean filter (allowed/disallowed) |
| Authority | Authoritative for candidate eligibility |
| Output | Set of allowed candidates + diagnostic audit |
| Does NOT | Rank candidates for selection |

**What Stitching Does:**
1. Validates candidates against hard constraints (confidence, entropy, domain caps)
2. Applies structural penalties (redundancy, domain-jump) as diagnostic signals
3. Filters candidates that violate constraints
4. Produces audit trail explaining every rejection

**What Stitching Must NOT Do:**
- Produce comparable ranking scores
- Select "the best" candidate
- Override downstream stages
- Make policy or ethical judgments
- Infer user psychology

### 1.2 Fusion: The Ranker

**Single Responsibility:** Select the optimal candidate from the allowed set using channel-weighted scoring.

| Aspect | Description |
|--------|-------------|
| Role | Score optimization and ranking |
| Authority | Authoritative for candidate selection |
| Output | Single selected candidate + ranked list |
| Does NOT | Re-validate candidates or apply eligibility filters |

**What Fusion Does:**
1. Receives pre-validated candidates from Stitching
2. Computes fusion scores using channel weights (HRM/LCM/MoE)
3. Ranks candidates by fusion score
4. Resolves ties deterministically
5. Makes routing decisions for downstream delivery

**What Fusion Must NOT Do:**
- Reject candidates that Stitching allowed
- Re-apply constraint validation
- Use Stitching diagnostic scores for ranking
- Override Stitching decisions
- Make policy or ethical judgments

### 1.3 Why This Division is Necessary and Sufficient

**Necessity:**
- Without separation, both stages compete for authority (who decides?)
- Overlapping scoring creates audit confusion (which score matters?)
- No clear contract between stages leads to implicit dependencies

**Sufficiency:**
- Stitching handles ALL eligibility concerns (structural, quality, constraint)
- Fusion handles ALL optimization concerns (channel blending, selection, routing)
- No gap: every candidate question is answered by exactly one stage
- No overlap: stages never duplicate responsibility

---

## 2. Authority Matrix

| Stage | Can Reject? | Can Rank? | Can Mutate Text? | Authority Level |
|-------|-------------|-----------|------------------|-----------------|
| **Stitching** | YES (via constraints) | NO (diagnostic only) | NO | Authoritative for eligibility |
| **Fusion** | NO (receives allowed set) | YES (primary function) | NO | Authoritative for selection |
| **DHA** | NO | NO | YES (tone modulation) | Authoritative for delivery tone |
| **Renderer** | NO | NO | YES (structure only) | Authoritative for output format |

### Authority Clarifications

1. **Stitching Authority**: Final say on what enters the allowed pool. If Stitching rejects a candidate, that decision is final and non-negotiable.

2. **Fusion Authority**: Final say on which allowed candidate is selected. Fusion MUST trust that all input candidates are valid.

3. **DHA Authority**: May adjust tone/delivery of selected content. Cannot change semantic meaning or reject content.

4. **Renderer Authority**: Structures output format (layers, formatting). Cannot alter semantic content.

---

## 3. Scoring Model Separation

### 3.1 Stitching Scores: Diagnostic / Feasibility Only

**Purpose:** Explain WHY candidates were filtered or allowed.

**Score Type:** `diagnostic_score` - NOT for ranking, only for audit/debug.

```
diagnostic_score = relevance - redundancy_penalty - domain_jump_penalty
```

**Key Properties:**
- Scores are per-candidate, not comparable across candidates
- Used to explain threshold violations
- Recorded in audit trail for transparency
- NEVER passed to Fusion for ranking purposes

**What Diagnostic Scores Mean:**
- `relevance`: How well candidate matches query aspects (structural match quality)
- `redundancy_penalty`: How much candidate overlaps with already-selected candidates
- `domain_jump_penalty`: Cost of cross-domain connection

### 3.2 Fusion Scores: Comparable / Ranking Only

**Purpose:** Determine WHICH candidate is optimal among allowed set.

**Score Type:** `fusion_score` - For ranking and selection.

```
fusion_score = α×HRM + β×LCM + γ×MoE + context_modifiers
```

**Key Properties:**
- Scores ARE comparable across candidates
- Higher score = better candidate for this context
- Used for final selection decision
- Independent of Stitching diagnostic scores

**What Fusion Scores Mean:**
- `HRM component`: Symbolic/abstract reasoning quality ("WHY")
- `LCM component`: Linguistic coherence quality ("WHAT")
- `MoE component`: Domain-specific factual quality ("HOW")
- `context_modifiers`: Adjustments for tier, intent, user preferences

### 3.3 Why Scores Must Never Be Merged

| Concern | If Merged | If Separated |
|---------|-----------|--------------|
| Audit clarity | Unclear which score affected decision | Clean trail per stage |
| Authority | Confusion over who decides | Single authority per concern |
| Debug | Cannot isolate issues | Each stage debuggable independently |
| Determinism | Implicit dependencies | Explicit contracts |
| Tuning | Coupling prevents independent tuning | Each stage tunable in isolation |

**Rule:** Stitching diagnostic scores MUST NOT flow into Fusion scoring formula.

---

## 4. Data Contracts (Implementation-Ready)

### 4.1 Stitching Output: `StitchingDecision`

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class RejectionReason(Enum):
    """Enumerated reasons for candidate rejection."""
    LOW_CONFIDENCE = "confidence_below_threshold"
    HIGH_ENTROPY = "entropy_above_threshold"
    DOMAIN_JUMP_CAP = "max_domain_jumps_exceeded"
    LOW_SCORE = "score_below_minimum"
    TOO_REDUNDANT = "redundancy_threshold_exceeded"
    CONSTRAINT_VIOLATION = "hard_constraint_violated"


@dataclass
class CandidateDecision:
    """Decision for a single candidate."""
    candidate_id: str
    allowed: bool

    # Diagnostic scores (NOT for ranking)
    diagnostic_scores: Dict[str, float] = field(default_factory=dict)
    # Expected keys: relevance, redundancy_penalty, domain_jump_penalty, total

    # Rejection info (if not allowed)
    rejection_reason: Optional[RejectionReason] = None
    rejection_detail: Optional[str] = None

    # Audit notes
    audit_notes: List[str] = field(default_factory=list)

    # Constraint status
    constraint_status: Dict[str, bool] = field(default_factory=dict)
    # Expected keys: confidence_ok, entropy_ok, domain_cap_ok, score_ok


@dataclass
class StitchingDecision:
    """
    Output from Stitching stage.

    Contains:
    - allowed_candidates: Candidates that passed all constraints
    - decisions: Per-candidate decision records (for audit)
    - diagnostics: Aggregate diagnostics for observability
    """

    # Primary output: IDs of allowed candidates (references, not copies)
    allowed_candidate_ids: List[str]

    # Per-candidate decisions (for audit trail)
    decisions: Dict[str, CandidateDecision] = field(default_factory=dict)

    # Aggregate diagnostics
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: total_evaluated, total_allowed, total_rejected,
    #                cross_domain_count, avg_relevance, rejection_summary

    # Audit metadata
    audit: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: timestamp, config_snapshot, constraint_thresholds

    def get_allowed_decisions(self) -> List[CandidateDecision]:
        """Get decisions for allowed candidates only."""
        return [d for d in self.decisions.values() if d.allowed]

    def get_rejection_summary(self) -> Dict[str, int]:
        """Count rejections by reason."""
        summary = {}
        for d in self.decisions.values():
            if not d.allowed and d.rejection_reason:
                key = d.rejection_reason.value
                summary[key] = summary.get(key, 0) + 1
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "allowed_candidate_ids": self.allowed_candidate_ids,
            "decisions": {
                cid: {
                    "allowed": d.allowed,
                    "diagnostic_scores": d.diagnostic_scores,
                    "rejection_reason": d.rejection_reason.value if d.rejection_reason else None,
                    "audit_notes": d.audit_notes,
                }
                for cid, d in self.decisions.items()
            },
            "diagnostics": self.diagnostics,
            "audit": self.audit,
        }
```

### 4.2 Fusion Output: `FusionRanking`

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ScoredCandidate:
    """Candidate with fusion score and components."""
    candidate_id: str

    # Fusion score (comparable, for ranking)
    fusion_score: float

    # Score components (for explainability)
    score_components: Dict[str, float] = field(default_factory=dict)
    # Expected keys: hrm_contribution, lcm_contribution, moe_contribution,
    #                context_adjustment, smi_penalty (if applicable)

    # Rank (1 = best)
    rank: int = 0

    # Tie-break info (if applicable)
    tie_break_applied: bool = False
    tie_break_reason: Optional[str] = None


@dataclass
class FusionRanking:
    """
    Output from Fusion stage.

    Contains:
    - selected: The winning candidate
    - rankings: Full ranked list with scores
    - routing: Decisions for downstream delivery
    - explain: Explainability data
    """

    # Primary output: selected candidate
    selected_candidate_id: str
    selected_fusion_score: float

    # Full ranking (for audit and fallback)
    rankings: List[ScoredCandidate] = field(default_factory=list)

    # Routing decisions for DHA/Renderer
    routing: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: render_mode, persona_hint, dha_tone_hint,
    #                use_rules_renderer, use_llm_renderer

    # Explainability
    explain: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: selection_reason, channel_weights_used,
    #                top_3_summary, tie_resolution (if applicable)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: total_candidates_evaluated, channel_weights,
    #                context_tier, context_intent

    def get_top_k(self, k: int = 3) -> List[ScoredCandidate]:
        """Get top k ranked candidates."""
        return self.rankings[:k]

    def get_score_spread(self) -> float:
        """Get difference between first and second scores."""
        if len(self.rankings) < 2:
            return 1.0  # Clear winner by default
        return self.rankings[0].fusion_score - self.rankings[1].fusion_score

    def was_tie_break(self) -> bool:
        """Check if tie-breaking was needed."""
        if not self.rankings:
            return False
        return self.rankings[0].tie_break_applied

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "selected_candidate_id": self.selected_candidate_id,
            "selected_fusion_score": round(self.selected_fusion_score, 4),
            "rankings": [
                {
                    "candidate_id": sc.candidate_id,
                    "fusion_score": round(sc.fusion_score, 4),
                    "score_components": {
                        k: round(v, 4) for k, v in sc.score_components.items()
                    },
                    "rank": sc.rank,
                }
                for sc in self.rankings
            ],
            "routing": self.routing,
            "explain": self.explain,
            "metadata": self.metadata,
        }
```

### 4.3 Handoff Contract: Stitching → Fusion

```python
@dataclass
class StitchingToFusionHandoff:
    """
    Contract for data passed from Stitching to Fusion.

    Explicitly defines what crosses the boundary and what does NOT.
    """

    # PASSED: Allowed candidates (by reference/ID)
    allowed_candidates: List[Any]  # List[Candidate]

    # PASSED: Context (unchanged from input)
    context: Any  # FusionContext

    # NOT PASSED: Stitching diagnostic scores
    # (Fusion must compute its own scores)

    # PASSED: Audit reference (for traceability only, not scoring)
    stitching_audit_id: Optional[str] = None

    # PASSED: Cross-domain metadata (informational only)
    cross_domain_info: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: cross_domain_count, domains_involved


def create_handoff(
    stitching_result: StitchingDecision,
    all_candidates: List[Any],
    context: Any,
) -> StitchingToFusionHandoff:
    """
    Create handoff from Stitching output.

    Explicitly filters to allowed candidates only.
    Does NOT pass diagnostic scores.
    """
    allowed = [
        c for c in all_candidates
        if getattr(c, 'id', None) in stitching_result.allowed_candidate_ids
    ]

    return StitchingToFusionHandoff(
        allowed_candidates=allowed,
        context=context,
        stitching_audit_id=stitching_result.audit.get("id"),
        cross_domain_info={
            "cross_domain_count": stitching_result.diagnostics.get("cross_domain_count", 0),
            "domains_involved": stitching_result.diagnostics.get("domains_involved", []),
        },
    )
```

---

## 5. Conflict Resolution Rules

### 5.1 Rule: Stitching Decisions Are Final

**Scenario:** Fusion "likes" a candidate that Stitching disallowed.

**Resolution:** Fusion NEVER sees disallowed candidates.

```
                     ┌─────────────────┐
All Candidates ───▶  │   Stitching     │ ───▶ Allowed Candidates Only
   (N=50)            │   (Gatekeeper)  │           (N=12)
                     └─────────────────┘
                              │
                              │ Rejected candidates are
                              │ REMOVED from flow
                              ▼
                     ┌─────────────────┐
                     │     Fusion      │ ───▶ Selected + Ranked
                     │    (Ranker)     │
                     └─────────────────┘
```

**Implementation:** Handoff contract explicitly contains only allowed candidates.
Fusion has no access to rejected candidate IDs or data.

### 5.2 Rule: Stitching Penalties Do NOT Affect Fusion Scores

**Scenario:** Should a candidate penalized heavily by Stitching rank lower in Fusion?

**Answer:** NO.

**Rationale:**
- Stitching penalties are diagnostic (why did we almost reject this?)
- Fusion scores are optimization (which is best among allowed?)
- A candidate with domain_jump_penalty=0.3 that passed constraints is equally valid as one with penalty=0.0
- Fusion evaluates channel quality, not structural feasibility

**Implementation:**
```python
# WRONG: Fusion uses Stitching penalty
fusion_score = hrm + lcm + moe - stitching_penalty  # NEVER DO THIS

# CORRECT: Fusion uses only channel scores
fusion_score = α * hrm + β * lcm + γ * moe + context_adjustment  # CORRECT
```

### 5.3 Rule: Fusion Cannot Override Stitching

**Scenario:** Can Fusion "rescue" a high-quality candidate that Stitching rejected?

**Answer:** NO.

**Rationale:**
- If Stitching rejected it, there's a constraint violation
- Constraint violations are non-negotiable (confidence, entropy, caps)
- Fusion has no authority to waive constraints
- This maintains determinism and audit clarity

**If Override Is Desired:**
- Adjust Stitching configuration (lower thresholds)
- Do NOT add bypass logic to Fusion
- Configuration changes are auditable; bypass logic is not

### 5.4 Rule: Score Domains Are Incompatible

**Scenario:** Should we combine Stitching diagnostic_score with Fusion fusion_score?

**Answer:** NO. They measure different things.

| Stitching diagnostic_score | Fusion fusion_score |
|---------------------------|---------------------|
| Structural feasibility | Channel quality |
| Constraint proximity | Optimization objective |
| Domain-agnostic aspects | HRM/LCM/MoE blend |
| Per-candidate, not comparable | Comparable for ranking |

**Combining them would:**
- Conflate eligibility with quality
- Break audit trail
- Create implicit coupling
- Prevent independent tuning

---

## 6. Pipeline Flow Diagram

```
                              PIPELINE FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           UPSTREAM STAGES                                │
│  TTOR → HRM/LCM/LAM → Candidate Generation                              │
│                                                                          │
│  Output: List[Candidate] with channel_scores, aspect_vectors, etc.      │
└─────────────────────────────────────────────────────────────────────────┘
    │
    │  Candidates (N=50, example)
    │  ─────────────────────────
    │  • candidate.id
    │  • candidate.text
    │  • candidate.domain
    │  • candidate.confidence
    │  • candidate.entropy
    │  • candidate.aspect_vector
    │  • candidate.channel_scores {hrm, lcm, moe}
    │
    ▼
╔═════════════════════════════════════════════════════════════════════════╗
║                         STITCHING STAGE                                  ║
║                     "What is ALLOWED?"                                   ║
╠═════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  INPUT:                                                                  ║
║    • All candidates from upstream                                        ║
║    • QueryContext (domain, aspect_vector, intent)                        ║
║    • StitchingConfig (thresholds, penalties)                            ║
║                                                                          ║
║  PROCESS:                                                                ║
║    1. For each candidate:                                                ║
║       a. Check confidence ≥ θ_conf          → PASS/REJECT               ║
║       b. Check entropy ≤ θ_entropy          → PASS/REJECT               ║
║       c. Check domain_jump_count ≤ max      → PASS/REJECT               ║
║       d. Compute diagnostic_score           → FOR AUDIT ONLY            ║
║       e. Check diagnostic_score ≥ min       → PASS/REJECT               ║
║       f. Check redundancy ≤ threshold       → PASS/REJECT               ║
║    2. Record decision + reason for each candidate                        ║
║    3. Build allowed_candidate_ids list                                   ║
║                                                                          ║
║  OUTPUT: StitchingDecision                                               ║
║    • allowed_candidate_ids: [id_1, id_3, id_7, ...]                     ║
║    • decisions: {id → CandidateDecision}                                ║
║    • diagnostics: {aggregate stats}                                      ║
║                                                                          ║
╚═════════════════════════════════════════════════════════════════════════╝
    │
    │  ┌──────────────────────────────────────────────────────────────┐
    │  │              HANDOFF BOUNDARY                                 │
    │  ├──────────────────────────────────────────────────────────────┤
    │  │  CROSSES:                                                     │
    │  │    • Allowed candidates (by ID/reference)                    │
    │  │    • Context (unchanged)                                      │
    │  │    • Cross-domain count (informational)                       │
    │  │    • Audit ID (traceability)                                  │
    │  │                                                               │
    │  │  DOES NOT CROSS:                                              │
    │  │    • Stitching diagnostic scores                             │
    │  │    • Rejection reasons                                        │
    │  │    • Penalty breakdowns                                       │
    │  │    • Rejected candidates                                      │
    │  └──────────────────────────────────────────────────────────────┘
    │
    │  Allowed Candidates (N=12, example)
    │
    ▼
╔═════════════════════════════════════════════════════════════════════════╗
║                          FUSION STAGE                                    ║
║                      "What is BEST?"                                     ║
╠═════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  INPUT:                                                                  ║
║    • Allowed candidates only (from handoff)                              ║
║    • FusionContext (tier, intent, domain, preferences)                  ║
║    • Channel weights (α=HRM, β=LCM, γ=MoE)                              ║
║                                                                          ║
║  PROCESS:                                                                ║
║    1. For each allowed candidate:                                        ║
║       a. Compute fusion_score = α×HRM + β×LCM + γ×MoE + modifiers       ║
║       b. Record score components                                         ║
║    2. Rank by fusion_score (descending)                                  ║
║    3. If tie (< 0.02 spread): apply deterministic tie-break              ║
║    4. Select top candidate                                               ║
║    5. Determine routing (render_mode, persona, tone)                     ║
║                                                                          ║
║  OUTPUT: FusionRanking                                                   ║
║    • selected_candidate_id: "id_7"                                       ║
║    • selected_fusion_score: 0.847                                        ║
║    • rankings: [{id, score, rank}, ...]                                  ║
║    • routing: {render_mode, persona_hint, dha_tone_hint}                ║
║    • explain: {selection reasoning}                                      ║
║                                                                          ║
╚═════════════════════════════════════════════════════════════════════════╝
    │
    │  Selected Candidate + Routing
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DOWNSTREAM STAGES                               │
│  DHA (tone modulation) → Renderer (format structuring)                  │
│                                                                          │
│  Input: Selected candidate + routing hints                               │
│  Output: Final response to user                                          │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Response to User
```

---

## 7. Determinism Guarantee

### 7.1 Repeatability

**Guarantee:** Given identical inputs, Stitching and Fusion produce identical outputs.

**How Achieved:**
- No randomness in scoring formulas
- No external state dependencies (no learning, no history effects)
- Deterministic tie-breaking rules
- Sorted iteration order (by ID when needed)

**Verification:**
```python
# This must always be true:
result_1 = stitching_engine.stitch(candidates, context)
result_2 = stitching_engine.stitch(candidates, context)
assert result_1.allowed_candidate_ids == result_2.allowed_candidate_ids

result_3 = fusion_engine.fuse(allowed, fusion_context)
result_4 = fusion_engine.fuse(allowed, fusion_context)
assert result_3.selected_candidate_id == result_4.selected_candidate_id
```

### 7.2 Explainability

**Guarantee:** Every decision can be explained by explicit formulas and thresholds.

**Stitching Explainability:**
- "Candidate X rejected: confidence 0.25 < threshold 0.30"
- "Candidate Y rejected: redundancy 0.82 with Candidate Z"
- "Candidate W allowed: all constraints passed, diagnostic_score=0.71"

**Fusion Explainability:**
- "Candidate A selected: fusion_score=0.847 (HRM=0.34, LCM=0.26, MoE=0.27)"
- "Tie-break applied: Candidate A preferred over B (higher HRM component)"

### 7.3 Zero Emergent Behavior

**Guarantee:** No behavior emerges that wasn't explicitly designed.

**How Achieved:**
- No feedback loops between stages
- No learning or adaptation
- No memory across requests
- No probabilistic sampling
- All formulas are closed-form

**Explicitly NOT Present:**
- Reinforcement signals
- Weight updates based on outcomes
- User preference learning
- Cross-request state accumulation
- Probabilistic selection

### 7.4 Suitability for Enterprise and Regulated Environments

**Guarantee:** The system is auditable, predictable, and compliant-ready.

| Requirement | How Met |
|-------------|---------|
| Audit trail | Full per-candidate decision records |
| Predictability | Deterministic, repeatable |
| Explainability | Formula-based, no black boxes |
| No learning | Zero-parameter Tier-1 design |
| Configuration control | All thresholds explicit |
| Separation of concerns | Clear stage boundaries |

**Compliance Implications:**
- SOC2: Audit logs demonstrate process consistency
- GDPR: No user data affects model behavior
- HIPAA: Decisions traceable to explicit rules
- Financial regulations: No hidden optimization objectives

---

## 8. Optional Refactor: Explicit Handoff Object

### Current State (Implicit Handoff)

```python
# Current: Stitching returns result, caller extracts allowed candidates
stitching_result = stitching_engine.stitch(candidates, context)
allowed = [c for c in candidates if c.id in stitching_result.scores]
fusion_result = fusion_engine.fuse(allowed, fusion_context)
```

**Issues:**
- Caller must know how to extract allowed candidates
- Easy to accidentally pass wrong candidates
- No type safety on handoff

### Proposed Refactor (Explicit Handoff)

```python
# Proposed: Stitching produces typed handoff, Fusion consumes it
stitching_decision = stitching_engine.evaluate(candidates, context)
handoff = StitchingToFusionHandoff.from_decision(stitching_decision, candidates, context)
fusion_ranking = fusion_engine.rank(handoff)
```

**Benefits:**
- Type-safe handoff contract
- Impossible to pass wrong candidates
- Explicit documentation of what crosses boundary
- Cleaner orchestration code

**Implementation Cost:** Low - wrapper dataclass + factory method.

**Recommendation:** Implement this refactor to enforce the boundary contract at the type level.

---

## 9. Summary

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Stitching = gatekeeper | Single responsibility: eligibility |
| Fusion = ranker | Single responsibility: optimization |
| Diagnostic vs fusion scores | Different concerns, different scales |
| No score merging | Preserves audit clarity |
| Explicit handoff | Type-safe boundary |
| No overrides | Determinism over flexibility |

### Implementation Checklist

- [ ] Update `StitchingResult` to `StitchingDecision` schema
- [ ] Update `FusionResult` to include `FusionRanking` fields
- [ ] Implement `StitchingToFusionHandoff` contract
- [ ] Remove any Stitching score usage from Fusion
- [ ] Update orchestrator to use explicit handoff
- [ ] Add determinism tests (same input → same output)
- [ ] Update documentation to reflect new contracts

### Design Principles Preserved

1. **No learning** - Both stages are stateless, formula-based
2. **No feedback loops** - Stitching → Fusion is one-way
3. **No policy enforcement** - Constraints are structural, not ethical
4. **No moral judgments** - Scores are mathematical, not evaluative
5. **No psychology inference** - No user modeling affects decisions
6. **Deterministic execution** - Repeatable, auditable
7. **Tier-compatible** - Works for Enterprise Search through Consumer/AGI

---

## Appendix A: Tier-Specific Configuration

| Tier | Stitching Enabled | Stitching Config | Fusion Config |
|------|-------------------|------------------|---------------|
| **Tier 1: Enterprise Search** | NO | N/A (bypassed) | Basic channel blend |
| **Tier 2: Enterprise Chat** | YES | Conservative: λ=0.4, max_jumps=1 | Standard blend |
| **Tier 3: Consumer/AGI** | YES | Permissive: λ=0.3, max_jumps=3 | Adaptive blend |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Stitching** | Stage that filters candidates via constraint enforcement |
| **Fusion** | Stage that selects optimal candidate via channel blending |
| **Diagnostic Score** | Stitching's internal score for audit (not for ranking) |
| **Fusion Score** | Fusion's comparable score for ranking |
| **Allowed Candidate** | Candidate that passed all Stitching constraints |
| **Channel** | Reasoning module (HRM, LCM, MoE) with associated score |
| **Handoff** | Explicit contract for data passed between stages |
| **Constraint** | Hard rule that candidates must satisfy (confidence, entropy, etc.) |
| **Penalty** | Soft cost applied to diagnostic score (redundancy, domain-jump) |

---

*Document Version: 1.0*
*Status: Implementation-Ready*
*Compatibility: STL Pipeline v3.x*
