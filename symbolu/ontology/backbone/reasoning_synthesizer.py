"""
Reasoning Synthesizer
=====================

Combines multiple ExperientialObjects into a unified reasoning response
tailored to the user's problem and inclination.

The synthesizer:
1. Takes a problem and relevant experientials
2. Identifies common patterns across domains
3. Synthesizes insights considering user preferences
4. Generates structured output (not LLM-generated, but structured templates)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from .experiential import ExperientialObject, PatternType, CausalChain
from .user_inclination import (
    UserInclinationProfile,
    ReasoningStyle,
    CommunicationPreference,
)
from .encoder import DimensionalVector, Dimension, encode_10d


@dataclass
class SynthesizedInsight:
    """A single insight synthesized from experientials."""
    insight_text: str
    source_domains: List[str]
    source_experientials: List[str]  # experiential_ids
    confidence: float
    pattern_type: Optional[PatternType] = None


@dataclass
class CrossDomainConnection:
    """A connection identified across domains."""
    domains: List[str]
    shared_pattern: str
    shared_dimensions: List[str]
    explanation: str


@dataclass
class ActionableStep:
    """A concrete step derived from reasoning."""
    step_number: int
    action: str
    rationale: str
    source_domain: Optional[str] = None


@dataclass
class SynthesisResult:
    """
    Complete synthesis result combining multiple experientials.

    This is the final output provided to the user.
    """
    # Problem context
    problem_summary: str
    problem_vector: DimensionalVector

    # Core insights
    primary_insight: str
    supporting_insights: List[SynthesizedInsight]

    # Cross-domain connections
    cross_domain_connections: List[CrossDomainConnection]

    # Actionable output
    recommended_actions: List[ActionableStep]
    warnings: List[str]

    # Metadata
    domains_consulted: List[str]
    experientials_used: List[str]
    confidence_score: float

    # For feedback
    synthesis_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            "problem_summary": self.problem_summary,
            "primary_insight": self.primary_insight,
            "supporting_insights": [
                {
                    "text": i.insight_text,
                    "domains": i.source_domains,
                    "confidence": i.confidence,
                }
                for i in self.supporting_insights
            ],
            "cross_domain_connections": [
                {
                    "domains": c.domains,
                    "pattern": c.shared_pattern,
                    "explanation": c.explanation,
                }
                for c in self.cross_domain_connections
            ],
            "recommended_actions": [
                {
                    "step": a.step_number,
                    "action": a.action,
                    "rationale": a.rationale,
                }
                for a in self.recommended_actions
            ],
            "warnings": self.warnings,
            "domains_consulted": self.domains_consulted,
            "confidence_score": self.confidence_score,
        }

    def format_for_user(
        self,
        style: ReasoningStyle = ReasoningStyle.BALANCED,
        comm_pref: CommunicationPreference = CommunicationPreference.STRUCTURED,
    ) -> str:
        """Format synthesis for user based on preferences."""
        lines = []

        if comm_pref == CommunicationPreference.CONCISE:
            # Brief format
            lines.append(f"**Insight**: {self.primary_insight}")
            if self.recommended_actions:
                lines.append("\n**Actions**:")
                for a in self.recommended_actions[:3]:
                    lines.append(f"  {a.step_number}. {a.action}")

        elif comm_pref == CommunicationPreference.DETAILED:
            # Comprehensive format
            lines.append(f"## Analysis of: {self.problem_summary}\n")
            lines.append(f"### Primary Insight\n{self.primary_insight}\n")

            if self.supporting_insights:
                lines.append("### Supporting Evidence")
                for ins in self.supporting_insights:
                    lines.append(f"- {ins.insight_text} (from {', '.join(ins.source_domains)})")
                lines.append("")

            if self.cross_domain_connections:
                lines.append("### Cross-Domain Patterns")
                for conn in self.cross_domain_connections:
                    lines.append(f"- **{' ↔ '.join(conn.domains)}**: {conn.explanation}")
                lines.append("")

            if self.recommended_actions:
                lines.append("### Recommended Actions")
                for a in self.recommended_actions:
                    lines.append(f"{a.step_number}. **{a.action}**")
                    lines.append(f"   _{a.rationale}_")
                lines.append("")

            if self.warnings:
                lines.append("### Warnings")
                for w in self.warnings:
                    lines.append(f"⚠️ {w}")

        else:  # STRUCTURED (default)
            lines.append(f"**Problem**: {self.problem_summary}\n")
            lines.append(f"**Key Insight**: {self.primary_insight}\n")

            if self.cross_domain_connections:
                lines.append("**Patterns Across Domains**:")
                for conn in self.cross_domain_connections:
                    lines.append(f"  • {' ↔ '.join(conn.domains)}: {conn.shared_pattern}")
                lines.append("")

            if self.recommended_actions:
                lines.append("**Recommended Steps**:")
                for a in self.recommended_actions:
                    lines.append(f"  {a.step_number}. {a.action}")
                lines.append("")

            if self.warnings:
                lines.append("**Consider**:")
                for w in self.warnings:
                    lines.append(f"  • {w}")

        return "\n".join(lines)


# =============================================================================
# Synthesis Engine
# =============================================================================

class ReasoningSynthesizer:
    """
    Synthesizes multiple experientials into unified reasoning.

    This is the core engine that combines cross-domain knowledge
    into actionable insights for the user.
    """

    def __init__(self):
        self._pattern_templates = self._load_pattern_templates()

    def _load_pattern_templates(self) -> Dict[PatternType, Dict[str, str]]:
        """Load templates for different pattern types."""
        return {
            PatternType.CAUSAL: {
                "insight": "When {cause} occurs, {effect} typically follows",
                "action": "Address {cause} to influence {effect}",
                "warning": "Be aware that {cause} can trigger {effect}",
            },
            PatternType.BIFURCATION: {
                "insight": "Systems under pressure tend to split rather than compromise",
                "action": "Either find middle ground or plan for clean separation",
                "warning": "Unclear division can be more destructive than clean split",
            },
            PatternType.ESCALATION: {
                "insight": "Dynamics tend to intensify unless actively managed",
                "action": "Intervene early before escalation becomes irreversible",
                "warning": "Small issues can compound into major problems",
            },
            PatternType.CYCLICAL: {
                "insight": "Pattern has recurred before and likely will again",
                "action": "Prepare for the next phase of the cycle",
                "warning": "Don't assume 'this time is different'",
            },
            PatternType.TRANSFORMATION: {
                "insight": "Change from one state to another is possible",
                "action": "Identify transformation triggers and facilitate transition",
                "warning": "Transformation may be irreversible",
            },
            PatternType.CONVERGENCE: {
                "insight": "Separate elements can unite under right conditions",
                "action": "Identify shared goals and remove barriers to integration",
                "warning": "Forced convergence without alignment can fail",
            },
            PatternType.THRESHOLD: {
                "insight": "Gradual change can lead to sudden shift at threshold",
                "action": "Monitor for approaching threshold indicators",
                "warning": "System may appear stable until sudden change",
            },
            PatternType.EQUILIBRIUM: {
                "insight": "Opposing forces can reach stable balance",
                "action": "Identify the equilibrium point and manage tensions",
                "warning": "Equilibrium can be disrupted by external shocks",
            },
        }

    def synthesize(
        self,
        problem: str,
        experientials: List[Tuple[ExperientialObject, float]],  # (exp, score)
        user_profile: Optional[UserInclinationProfile] = None,
    ) -> SynthesisResult:
        """
        Synthesize experientials into unified reasoning.

        Args:
            problem: User's problem statement
            experientials: List of (experiential, relevance_score) tuples
            user_profile: Optional user profile for personalization

        Returns:
            SynthesisResult with synthesized insights and actions
        """
        import hashlib

        problem_vector = encode_10d(problem)

        # Generate synthesis ID
        exp_ids = "_".join([e[0].experiential_id[:6] for e in experientials[:3]])
        synthesis_id = "syn_" + hashlib.sha256(
            f"{problem[:50]}_{exp_ids}".encode()
        ).hexdigest()[:12]

        # Extract common patterns
        patterns = self._identify_common_patterns(experientials)

        # Build primary insight
        primary_insight = self._generate_primary_insight(problem, experientials, patterns)

        # Build supporting insights
        supporting = self._generate_supporting_insights(experientials)

        # Find cross-domain connections
        connections = self._find_cross_domain_connections(experientials)

        # Generate actions
        actions = self._generate_actions(problem, experientials, patterns, user_profile)

        # Generate warnings
        warnings = self._generate_warnings(experientials, patterns)

        # Compute confidence
        confidence = self._compute_confidence(experientials, patterns)

        return SynthesisResult(
            problem_summary=problem[:200],
            problem_vector=problem_vector,
            primary_insight=primary_insight,
            supporting_insights=supporting,
            cross_domain_connections=connections,
            recommended_actions=actions,
            warnings=warnings,
            domains_consulted=list(set(e[0].source_domain for e in experientials)),
            experientials_used=[e[0].experiential_id for e in experientials],
            confidence_score=confidence,
            synthesis_id=synthesis_id,
        )

    def _identify_common_patterns(
        self,
        experientials: List[Tuple[ExperientialObject, float]]
    ) -> Dict[PatternType, int]:
        """Count pattern types across experientials."""
        pattern_counts = {}
        for exp, _ in experientials:
            pt = exp.pattern_type
            pattern_counts[pt] = pattern_counts.get(pt, 0) + 1
        return pattern_counts

    def _generate_primary_insight(
        self,
        problem: str,
        experientials: List[Tuple[ExperientialObject, float]],
        patterns: Dict[PatternType, int],
    ) -> str:
        """Generate the primary insight."""
        if not experientials:
            return "Insufficient data for insight generation"

        # Use most common pattern
        if patterns:
            top_pattern = max(patterns.items(), key=lambda x: x[1])[0]
            template = self._pattern_templates.get(top_pattern, {})
            if "insight" in template:
                return template["insight"]

        # Fallback: use highest-scored experiential's insight
        top_exp = experientials[0][0]
        if top_exp.insight:
            return f"Based on {top_exp.source_domain}: {top_exp.insight}"

        return "Multiple patterns identified; analysis suggests careful consideration needed"

    def _generate_supporting_insights(
        self,
        experientials: List[Tuple[ExperientialObject, float]]
    ) -> List[SynthesizedInsight]:
        """Generate supporting insights from experientials."""
        insights = []

        for exp, score in experientials[:5]:  # Top 5
            if exp.insight:
                insights.append(SynthesizedInsight(
                    insight_text=exp.insight,
                    source_domains=[exp.source_domain],
                    source_experientials=[exp.experiential_id],
                    confidence=score,
                    pattern_type=exp.pattern_type,
                ))

        return insights

    def _find_cross_domain_connections(
        self,
        experientials: List[Tuple[ExperientialObject, float]]
    ) -> List[CrossDomainConnection]:
        """Find connections across different domains."""
        connections = []

        # Group by domain
        by_domain: Dict[str, List[ExperientialObject]] = {}
        for exp, _ in experientials:
            if exp.source_domain not in by_domain:
                by_domain[exp.source_domain] = []
            by_domain[exp.source_domain].append(exp)

        domains = list(by_domain.keys())

        # Find connections between pairs of domains
        for i, d1 in enumerate(domains):
            for d2 in domains[i + 1:]:
                # Check for shared patterns
                patterns_d1 = set(e.pattern_type for e in by_domain[d1])
                patterns_d2 = set(e.pattern_type for e in by_domain[d2])
                shared = patterns_d1 & patterns_d2

                if shared:
                    pattern = list(shared)[0]
                    connections.append(CrossDomainConnection(
                        domains=[d1, d2],
                        shared_pattern=pattern.value,
                        shared_dimensions=[],
                        explanation=f"Both domains show {pattern.value} pattern",
                    ))

        return connections[:3]  # Top 3 connections

    def _generate_actions(
        self,
        problem: str,
        experientials: List[Tuple[ExperientialObject, float]],
        patterns: Dict[PatternType, int],
        user_profile: Optional[UserInclinationProfile],
    ) -> List[ActionableStep]:
        """Generate recommended actions."""
        actions = []
        step_num = 1

        # Add pattern-based actions
        for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
            template = self._pattern_templates.get(pattern, {})
            if "action" in template:
                actions.append(ActionableStep(
                    step_number=step_num,
                    action=template["action"],
                    rationale=f"Based on {pattern.value} pattern seen in {count} sources",
                ))
                step_num += 1
                if step_num > 3:
                    break

        # Add experiential-specific actions from causal chains
        for exp, score in experientials[:3]:
            if exp.causal_chain and len(exp.causal_chain.steps) >= 2:
                action = f"Consider the {exp.causal_chain.steps[0]} → {exp.causal_chain.steps[-1]} dynamic"
                actions.append(ActionableStep(
                    step_number=step_num,
                    action=action,
                    rationale=f"Pattern from {exp.source_domain}",
                    source_domain=exp.source_domain,
                ))
                step_num += 1
                if step_num > 5:
                    break

        return actions

    def _generate_warnings(
        self,
        experientials: List[Tuple[ExperientialObject, float]],
        patterns: Dict[PatternType, int],
    ) -> List[str]:
        """Generate warnings based on patterns."""
        warnings = []

        for pattern in patterns.keys():
            template = self._pattern_templates.get(pattern, {})
            if "warning" in template:
                warnings.append(template["warning"])

        return warnings[:3]

    def _compute_confidence(
        self,
        experientials: List[Tuple[ExperientialObject, float]],
        patterns: Dict[PatternType, int],
    ) -> float:
        """Compute overall confidence score."""
        if not experientials:
            return 0.0

        # Base: average similarity score
        avg_score = sum(s for _, s in experientials) / len(experientials)

        # Boost for pattern agreement
        if patterns:
            max_pattern_count = max(patterns.values())
            pattern_agreement = max_pattern_count / len(experientials)
            avg_score = avg_score * 0.7 + pattern_agreement * 0.3

        # Boost for cross-domain agreement
        domains = set(e[0].source_domain for e in experientials)
        if len(domains) >= 2:
            avg_score *= 1.1

        return min(1.0, avg_score)


# =============================================================================
# Convenience Functions
# =============================================================================

def synthesize_for_problem(
    problem: str,
    experiential_store: "ExperientialStore",
    user_id: Optional[str] = None,
    top_k: int = 5,
) -> SynthesisResult:
    """
    Convenience function: retrieve and synthesize in one call.

    Args:
        problem: User's problem statement
        experiential_store: Store containing experientials
        user_id: Optional user ID for personalization
        top_k: Number of experientials to retrieve

    Returns:
        SynthesisResult
    """
    from .experiential import ExperientialStore
    from .user_inclination import get_user_store

    # Encode problem
    problem_vector = encode_10d(problem)

    # Get user profile if available
    user_profile = None
    if user_id:
        user_store = get_user_store()
        user_profile = user_store.get(user_id)

    # Search experientials
    results = experiential_store.search(
        problem_vector=problem_vector,
        user_id=user_id,
        top_k=top_k,
    )

    # Synthesize
    synthesizer = ReasoningSynthesizer()
    return synthesizer.synthesize(problem, results, user_profile)
