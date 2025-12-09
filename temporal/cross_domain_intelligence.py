"""
Cross-Domain Intelligence - Universal Pattern Detection and Transfer
=====================================================================

This module provides deterministic, rule-based pattern detection and
cross-domain interpretation for consciousness analysis results.

Key Features:
- 13 universal patterns across protective, growth, stress, conflict, and recovery categories
- 6 domain mappings (finance, medicine, psychology, education, legal, corporate)
- Weighted scoring based on bhava, SMI, kosha, ontology, and temporal signals
- Explainable, rule-based pattern matching
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional


@dataclass
class PatternConfig:
    """Configuration for a universal pattern."""

    name: str
    min_confidence: float
    category: str
    smi_range: Tuple[float, float]  # (min, max) SMI range
    bhava_range: Tuple[int, int]  # (min, max) bhava_id range
    directions: List[str]  # acceptable bhava directions
    temporal_trends: List[str]  # favorable temporal trends
    kosha_weights: Dict[int, float] = field(default_factory=dict)  # kosha_id -> weight
    ontology_weights: Dict[int, float] = field(default_factory=dict)  # ontology_id -> weight


# Domain interpretation mappings
DOMAIN_INTERPRETATIONS: Dict[str, Dict[str, str]] = {
    "risk_hiding": {
        "finance": "Potential understatement of investment risk or hidden financial exposure",
        "medicine": "Potential downplaying of symptom severity or treatment side effects",
        "psychology": "Defensive minimization of emotional distress or trauma impact",
        "education": "Concealment of learning difficulties or academic struggles",
        "legal": "Potential omission of material facts or liability exposure",
        "corporate": "Underreporting of operational risks or compliance issues",
    },
    "emotional_masking": {
        "finance": "Suppressed anxiety about financial decisions or market uncertainty",
        "medicine": "Hidden emotional response to diagnosis or treatment stress",
        "psychology": "Defense mechanism concealing authentic emotional state",
        "education": "Student concealing anxiety about performance or social pressure",
        "legal": "Witness masking emotional involvement in case circumstances",
        "corporate": "Employee concealing workplace stress or burnout indicators",
    },
    "defensive_rationalization": {
        "finance": "Post-hoc justification of poor investment decisions",
        "medicine": "Rationalized non-compliance with treatment protocols",
        "psychology": "Cognitive defense against threatening self-insight",
        "education": "Justification of academic underperformance or avoidance",
        "legal": "Constructed rationale to minimize perceived culpability",
        "corporate": "Management rationalization of questionable decisions",
    },
    "breakthrough_insight": {
        "finance": "Sudden clarity about investment strategy or market dynamics",
        "medicine": "Patient gaining new understanding of health condition",
        "psychology": "Therapeutic breakthrough or aha moment in self-understanding",
        "education": "Concept crystallization or learning breakthrough moment",
        "legal": "Key insight connecting case elements or legal strategy",
        "corporate": "Strategic insight or innovative problem-solving moment",
    },
    "authentic_expression": {
        "finance": "Genuine disclosure of financial concerns or goals",
        "medicine": "Open communication about symptoms or treatment preferences",
        "psychology": "Vulnerable self-disclosure without defensive filters",
        "education": "Student expressing genuine intellectual curiosity",
        "legal": "Candid testimony without calculated impression management",
        "corporate": "Authentic feedback or transparent communication",
    },
    "integrative_growth": {
        "finance": "Balanced integration of risk tolerance and growth objectives",
        "medicine": "Holistic approach integrating treatment and lifestyle factors",
        "psychology": "Integration of conflicting aspects of self-concept",
        "education": "Synthesis of knowledge across domains or perspectives",
        "legal": "Comprehensive understanding of legal implications and options",
        "corporate": "Organizational learning and adaptive capability growth",
    },
    "acute_anxiety": {
        "finance": "Immediate distress about financial loss or market volatility",
        "medicine": "Acute health anxiety or panic about medical situation",
        "psychology": "Heightened anxiety state requiring immediate attention",
        "education": "Test anxiety or acute performance pressure",
        "legal": "Acute stress about legal proceedings or outcomes",
        "corporate": "Crisis-level stress about job security or deadlines",
    },
    "chronic_stress": {
        "finance": "Prolonged financial worry affecting decision-making",
        "medicine": "Sustained health-related stress impacting wellbeing",
        "psychology": "Long-term stress accumulation requiring intervention",
        "education": "Persistent academic pressure or burnout trajectory",
        "legal": "Extended legal uncertainty causing chronic distress",
        "corporate": "Sustained workplace stress affecting performance",
    },
    "tension_corridor": {
        "finance": "Extended period of market uncertainty and stress",
        "medicine": "Prolonged diagnostic uncertainty or treatment phase",
        "psychology": "Sustained therapeutic tension requiring resolution",
        "education": "Extended challenging learning phase with high stakes",
        "legal": "Prolonged legal proceedings with ongoing uncertainty",
        "corporate": "Extended organizational transition or restructuring stress",
    },
    "cognitive_dissonance": {
        "finance": "Conflicting beliefs about investment strategy or risk",
        "medicine": "Inconsistency between health beliefs and behaviors",
        "psychology": "Internal conflict between values and actions",
        "education": "Conflict between learning goals and actual engagement",
        "legal": "Contradictory statements or inconsistent narrative",
        "corporate": "Misalignment between stated values and practices",
    },
    "avoidance_pattern": {
        "finance": "Avoidance of financial planning or decision-making",
        "medicine": "Treatment avoidance or delayed care seeking",
        "psychology": "Experiential avoidance of difficult emotions",
        "education": "Academic avoidance or task procrastination",
        "legal": "Avoidance of legal responsibility or disclosure",
        "corporate": "Avoidance of difficult conversations or decisions",
    },
    "recovery_trajectory": {
        "finance": "Recovery from financial setback with improving outlook",
        "medicine": "Positive trajectory in treatment response or healing",
        "psychology": "Therapeutic progress and symptom improvement",
        "education": "Academic recovery and improving engagement",
        "legal": "Resolution trajectory with decreasing legal exposure",
        "corporate": "Organizational recovery from crisis or setback",
    },
    "resilience_pattern": {
        "finance": "Demonstrated ability to weather financial uncertainty",
        "medicine": "Adaptive coping with health challenges",
        "psychology": "Psychological resilience and effective coping",
        "education": "Academic persistence despite challenges",
        "legal": "Composed response to legal pressure and uncertainty",
        "corporate": "Organizational resilience and adaptive capacity",
    },
}


class CrossDomainIntelligence:
    """
    Universal pattern detection and cross-domain transfer engine.

    This class implements a deterministic, rule-based pattern matching
    system that identifies universal psychological patterns and translates
    them into domain-specific interpretations.

    Pattern Detection Weights:
    - Bhava range: 30%
    - Bhava direction: 25%
    - SMI range: 25%
    - Kosha signature: 10%
    - Ontology signature: 10%
    - Temporal signature: 10% (bonus when available)
    """

    # Weight configuration
    WEIGHTS = {
        "bhava_range": 0.30,
        "bhava_direction": 0.25,
        "smi_range": 0.25,
        "kosha_signature": 0.10,
        "ontology_signature": 0.10,
        "temporal_signature": 0.10,  # Bonus weight when temporal data available
    }

    # Supported domains
    DOMAINS = ["finance", "medicine", "psychology", "education", "legal", "corporate"]

    def __init__(self):
        """Initialize the pattern library and domain mappings."""
        self._patterns = self._initialize_patterns()
        self._domain_interpretations = DOMAIN_INTERPRETATIONS

    def _initialize_patterns(self) -> Dict[str, PatternConfig]:
        """Initialize the 13 universal patterns with their configurations."""
        patterns = {
            # Protective/Defensive patterns
            "risk_hiding": PatternConfig(
                name="risk_hiding",
                min_confidence=0.65,
                category="protective",
                smi_range=(0.5, 0.75),
                bhava_range=(3, 7),
                directions=["downward", "neutral"],
                temporal_trends=["rising", "stable"],
                kosha_weights={2: 0.3, 3: 0.4, 4: 0.3},
                ontology_weights={4: 0.3, 5: 0.4, 6: 0.3},
            ),
            "emotional_masking": PatternConfig(
                name="emotional_masking",
                min_confidence=0.60,
                category="protective",
                smi_range=(0.4, 0.7),
                bhava_range=(2, 6),
                directions=["downward", "neutral"],
                temporal_trends=["stable"],
                kosha_weights={1: 0.2, 2: 0.4, 3: 0.4},
                ontology_weights={3: 0.4, 4: 0.3, 5: 0.3},
            ),
            "defensive_rationalization": PatternConfig(
                name="defensive_rationalization",
                min_confidence=0.70,
                category="protective",
                smi_range=(0.45, 0.65),
                bhava_range=(4, 8),
                directions=["neutral", "upward"],
                temporal_trends=["rising", "stable"],
                kosha_weights={3: 0.3, 4: 0.4, 5: 0.3},
                ontology_weights={5: 0.4, 6: 0.3, 7: 0.3},
            ),
            # Growth/Expansion patterns
            "breakthrough_insight": PatternConfig(
                name="breakthrough_insight",
                min_confidence=0.70,
                category="growth",
                smi_range=(0.15, 0.35),
                bhava_range=(6, 9),
                directions=["upward"],
                temporal_trends=["falling", "stable"],
                kosha_weights={4: 0.3, 5: 0.4, 6: 0.3},
                ontology_weights={6: 0.3, 7: 0.4, 8: 0.3},
            ),
            "authentic_expression": PatternConfig(
                name="authentic_expression",
                min_confidence=0.65,
                category="growth",
                smi_range=(0.1, 0.3),
                bhava_range=(5, 8),
                directions=["upward", "neutral"],
                temporal_trends=["falling", "stable"],
                kosha_weights={3: 0.2, 4: 0.4, 5: 0.4},
                ontology_weights={5: 0.3, 6: 0.4, 7: 0.3},
            ),
            "integrative_growth": PatternConfig(
                name="integrative_growth",
                min_confidence=0.70,
                category="growth",
                smi_range=(0.2, 0.4),
                bhava_range=(7, 10),
                directions=["upward"],
                temporal_trends=["falling", "stable"],
                kosha_weights={5: 0.3, 6: 0.4, 7: 0.3},
                ontology_weights={7: 0.3, 8: 0.4, 9: 0.3},
            ),
            # Stress/Tension patterns
            "acute_anxiety": PatternConfig(
                name="acute_anxiety",
                min_confidence=0.75,
                category="stress",
                smi_range=(0.7, 1.0),
                bhava_range=(1, 4),
                directions=["downward"],
                temporal_trends=["rising"],
                kosha_weights={1: 0.5, 2: 0.3, 3: 0.2},
                ontology_weights={1: 0.4, 2: 0.3, 3: 0.3},
            ),
            "chronic_stress": PatternConfig(
                name="chronic_stress",
                min_confidence=0.70,
                category="stress",
                smi_range=(0.55, 0.75),
                bhava_range=(2, 5),
                directions=["downward", "neutral"],
                temporal_trends=["stable", "rising"],
                kosha_weights={2: 0.4, 3: 0.3, 4: 0.3},
                ontology_weights={2: 0.3, 3: 0.4, 4: 0.3},
            ),
            "tension_corridor": PatternConfig(
                name="tension_corridor",
                min_confidence=0.65,
                category="stress",
                smi_range=(0.6, 0.85),
                bhava_range=(2, 6),
                directions=["downward", "neutral"],
                temporal_trends=["stable"],
                kosha_weights={2: 0.3, 3: 0.4, 4: 0.3},
                ontology_weights={3: 0.3, 4: 0.4, 5: 0.3},
            ),
            # Conflict/Avoidance patterns
            "cognitive_dissonance": PatternConfig(
                name="cognitive_dissonance",
                min_confidence=0.70,
                category="conflict",
                smi_range=(0.5, 0.7),
                bhava_range=(3, 6),
                directions=["neutral"],
                temporal_trends=["stable", "rising"],
                kosha_weights={3: 0.3, 4: 0.4, 5: 0.3},
                ontology_weights={4: 0.3, 5: 0.4, 6: 0.3},
            ),
            "avoidance_pattern": PatternConfig(
                name="avoidance_pattern",
                min_confidence=0.65,
                category="conflict",
                smi_range=(0.4, 0.65),
                bhava_range=(2, 5),
                directions=["downward", "neutral"],
                temporal_trends=["stable"],
                kosha_weights={2: 0.3, 3: 0.4, 4: 0.3},
                ontology_weights={3: 0.3, 4: 0.4, 5: 0.3},
            ),
            # Recovery/Healing patterns
            "recovery_trajectory": PatternConfig(
                name="recovery_trajectory",
                min_confidence=0.65,
                category="recovery",
                smi_range=(0.3, 0.55),
                bhava_range=(4, 7),
                directions=["upward"],
                temporal_trends=["falling"],
                kosha_weights={3: 0.3, 4: 0.4, 5: 0.3},
                ontology_weights={4: 0.3, 5: 0.4, 6: 0.3},
            ),
            "resilience_pattern": PatternConfig(
                name="resilience_pattern",
                min_confidence=0.70,
                category="recovery",
                smi_range=(0.25, 0.5),
                bhava_range=(5, 8),
                directions=["upward", "neutral"],
                temporal_trends=["falling", "stable"],
                kosha_weights={4: 0.3, 5: 0.4, 6: 0.3},
                ontology_weights={5: 0.3, 6: 0.4, 7: 0.3},
            ),
        }
        return patterns

    def detect_pattern(
        self,
        smi: float,
        bhava_id: int,
        bhava_direction: str,
        kosha_id: int,
        ontology_id: int,
        temporal_trend: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """
        Detect patterns matching the given analysis parameters.

        Args:
            smi: Semantic Mismatch Index value (0.0 to 1.0).
            bhava_id: Bhava state identifier.
            bhava_direction: Direction of bhava ("upward", "downward", "neutral").
            kosha_id: Kosha layer identifier.
            ontology_id: Ontology state identifier.
            temporal_trend: Optional temporal trend ("rising", "falling", "stable").

        Returns:
            List of (pattern_name, confidence) tuples sorted by confidence descending.
            Only patterns meeting their minimum confidence threshold are returned.
        """
        results = []

        for pattern_name, config in self._patterns.items():
            confidence = self._compute_pattern_confidence(
                config, smi, bhava_id, bhava_direction, kosha_id, ontology_id, temporal_trend
            )

            if confidence >= config.min_confidence:
                results.append((pattern_name, round(confidence, 4)))

        # Sort by confidence descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _compute_pattern_confidence(
        self,
        config: PatternConfig,
        smi: float,
        bhava_id: int,
        bhava_direction: str,
        kosha_id: int,
        ontology_id: int,
        temporal_trend: Optional[str],
    ) -> float:
        """
        Compute confidence score for a pattern match.

        Weighting:
        - Bhava range: 30%
        - Bhava direction: 25%
        - SMI range: 25%
        - Kosha signature: 10%
        - Ontology signature: 10%
        - Temporal signature: 10% (bonus when available)
        """
        scores = {}

        # SMI range score (25%)
        smi_min, smi_max = config.smi_range
        if smi_min <= smi <= smi_max:
            # Score based on how centered within the range
            range_center = (smi_min + smi_max) / 2
            range_half = (smi_max - smi_min) / 2
            distance_from_center = abs(smi - range_center)
            scores["smi_range"] = 1.0 - (distance_from_center / range_half) * 0.5
        elif smi < smi_min:
            # Partial score for close matches
            distance = smi_min - smi
            scores["smi_range"] = max(0, 1.0 - distance * 3)
        else:
            distance = smi - smi_max
            scores["smi_range"] = max(0, 1.0 - distance * 3)

        # Bhava range score (30%)
        bhava_min, bhava_max = config.bhava_range
        if bhava_min <= bhava_id <= bhava_max:
            # Score based on position within range
            range_center = (bhava_min + bhava_max) / 2
            range_half = (bhava_max - bhava_min) / 2
            if range_half > 0:
                distance_from_center = abs(bhava_id - range_center)
                scores["bhava_range"] = 1.0 - (distance_from_center / range_half) * 0.3
            else:
                scores["bhava_range"] = 1.0
        else:
            # Partial score for adjacent bhava states
            if bhava_id < bhava_min:
                distance = bhava_min - bhava_id
            else:
                distance = bhava_id - bhava_max
            scores["bhava_range"] = max(0, 1.0 - distance * 0.25)

        # Bhava direction score (25%)
        if bhava_direction in config.directions:
            scores["bhava_direction"] = 1.0
        elif bhava_direction == "neutral":
            # Neutral is always somewhat acceptable
            scores["bhava_direction"] = 0.5
        else:
            scores["bhava_direction"] = 0.2

        # Kosha signature score (10%)
        if kosha_id in config.kosha_weights:
            scores["kosha_signature"] = config.kosha_weights[kosha_id] * 2.5
        else:
            # Default score for non-specified kosha
            scores["kosha_signature"] = 0.3

        # Ontology signature score (10%)
        if ontology_id in config.ontology_weights:
            scores["ontology_signature"] = config.ontology_weights[ontology_id] * 2.5
        else:
            # Default score for non-specified ontology
            scores["ontology_signature"] = 0.3

        # Temporal signature score (10% bonus)
        if temporal_trend is not None:
            if temporal_trend in config.temporal_trends:
                scores["temporal_signature"] = 1.0
            elif temporal_trend == "stable":
                scores["temporal_signature"] = 0.5
            else:
                scores["temporal_signature"] = 0.2
        else:
            # No temporal data - don't penalize, just no bonus
            scores["temporal_signature"] = 0.0

        # Compute weighted confidence
        base_weights = {
            "smi_range": self.WEIGHTS["smi_range"],
            "bhava_range": self.WEIGHTS["bhava_range"],
            "bhava_direction": self.WEIGHTS["bhava_direction"],
            "kosha_signature": self.WEIGHTS["kosha_signature"],
            "ontology_signature": self.WEIGHTS["ontology_signature"],
        }

        # Base confidence (90%)
        confidence = sum(scores[key] * weight for key, weight in base_weights.items())

        # Add temporal bonus if available (up to 10%)
        if temporal_trend is not None:
            confidence += scores["temporal_signature"] * self.WEIGHTS["temporal_signature"]
        else:
            # Normalize to 90% range when no temporal data
            confidence = confidence / 0.9 * 1.0 if confidence > 0 else 0

        return min(confidence, 1.0)

    def transfer_pattern_to_domain(
        self,
        pattern_name: str,
        domain: str,
    ) -> Dict[str, Any]:
        """
        Map a universal pattern to a specific domain.

        Args:
            pattern_name: Name of the detected pattern.
            domain: Target domain (finance, medicine, psychology, education, legal, corporate).

        Returns:
            Dictionary with pattern, domain, and domain-specific interpretation.

        Raises:
            ValueError: If pattern or domain is not recognized.
        """
        if pattern_name not in self._patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}")

        if domain not in self.DOMAINS:
            raise ValueError(f"Unknown domain: {domain}. Valid domains: {self.DOMAINS}")

        interpretation = self._domain_interpretations.get(pattern_name, {}).get(
            domain, f"Pattern '{pattern_name}' detected in {domain} context"
        )

        pattern_config = self._patterns[pattern_name]

        return {
            "pattern": pattern_name,
            "domain": domain,
            "category": pattern_config.category,
            "interpretation": interpretation,
            "min_confidence": pattern_config.min_confidence,
        }

    def get_pattern_categories(self) -> Dict[str, List[str]]:
        """
        Get all patterns organized by category.

        Returns:
            Dictionary mapping category names to lists of pattern names.
        """
        categories: Dict[str, List[str]] = {}
        for pattern_name, config in self._patterns.items():
            if config.category not in categories:
                categories[config.category] = []
            categories[config.category].append(pattern_name)
        return categories

    def get_all_patterns(self) -> List[str]:
        """Return list of all pattern names."""
        return list(self._patterns.keys())

    def get_pattern_config(self, pattern_name: str) -> Optional[PatternConfig]:
        """Get configuration for a specific pattern."""
        return self._patterns.get(pattern_name)
