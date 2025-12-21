"""
Domain Pattern Definitions
==========================

Each domain is defined as a structural pattern with:
- Ideal profile values for each dimension
- Dimension weights (importance)
- Compatibility threshold
- Rationale explaining why these patterns matter

These are EXPLICIT RULES, not learned correlations.
"""

from typing import Dict, Optional, Tuple

from symbolu.name_resonance.types import DomainPattern, DIMENSION_NAMES


# =============================================================================
# Helper to create frozen domain patterns
# =============================================================================

def _make_pattern(
    name: str,
    category: str,
    ideal: Dict[str, float],
    weights: Dict[str, float],
    threshold: float,
    rationale: str,
) -> DomainPattern:
    """Create an immutable DomainPattern."""
    # Ensure all dimensions are present
    ideal_tuple = tuple((dim, ideal.get(dim, 0.5)) for dim in DIMENSION_NAMES)
    weights_tuple = tuple((dim, weights.get(dim, 0.05)) for dim in DIMENSION_NAMES)

    return DomainPattern(
        name=name,
        category=category,
        ideal_profile=ideal_tuple,
        dimension_weights=weights_tuple,
        compatibility_threshold=threshold,
        rationale=rationale,
    )


# =============================================================================
# Career Domain Patterns
# =============================================================================

CAREER_DOMAINS: Tuple[DomainPattern, ...] = (
    _make_pattern(
        name="Justice / Law Enforcement",
        category="career",
        ideal={
            "force": 0.70, "stability": 0.80, "duration": 0.55,
            "initiation": 0.60, "flow": 0.40, "termination": 0.70,
            "complexity": 0.50, "density": 0.60, "balance": 0.75,
            "openness": 0.35, "depth": 0.65, "connectivity": 0.40,
        },
        weights={
            "stability": 0.15, "balance": 0.14, "force": 0.13,
            "termination": 0.12, "depth": 0.10, "density": 0.09,
            "initiation": 0.08, "duration": 0.06, "complexity": 0.05,
            "flow": 0.03, "openness": 0.03, "connectivity": 0.02,
        },
        threshold=0.62,
        rationale="Justice requires stability (consistent application of rules), balance "
                  "(fairness/equilibrium), force (authority), and clear termination "
                  "(definitive judgments). Low openness reflects controlled expression.",
    ),

    _make_pattern(
        name="Strategic Leadership",
        category="career",
        ideal={
            "force": 0.75, "stability": 0.65, "duration": 0.70,
            "initiation": 0.70, "flow": 0.50, "termination": 0.60,
            "complexity": 0.70, "density": 0.60, "balance": 0.60,
            "openness": 0.50, "depth": 0.70, "connectivity": 0.60,
        },
        weights={
            "force": 0.14, "initiation": 0.13, "complexity": 0.12,
            "depth": 0.11, "duration": 0.10, "stability": 0.09,
            "connectivity": 0.08, "termination": 0.07, "balance": 0.06,
            "density": 0.04, "flow": 0.03, "openness": 0.03,
        },
        threshold=0.58,
        rationale="Strategic leadership requires force (command presence), decisive "
                  "initiation, ability to handle complexity, depth (gravitas), and "
                  "sustained duration (long-term thinking).",
    ),

    _make_pattern(
        name="Counseling / Emotional Care",
        category="career",
        ideal={
            "force": 0.30, "stability": 0.70, "duration": 0.75,
            "initiation": 0.30, "flow": 0.80, "termination": 0.30,
            "complexity": 0.50, "density": 0.30, "balance": 0.70,
            "openness": 0.85, "depth": 0.70, "connectivity": 0.90,
        },
        weights={
            "connectivity": 0.17, "openness": 0.15, "flow": 0.14,
            "depth": 0.11, "stability": 0.10, "duration": 0.09,
            "balance": 0.07, "complexity": 0.05, "termination": 0.04,
            "force": 0.03, "initiation": 0.03, "density": 0.02,
        },
        threshold=0.60,
        rationale="Counseling requires high connectivity (empathy/rapport), openness "
                  "(receptivity to others), smooth flow (gentle guidance), with LOW "
                  "force (non-directive approach) and soft termination.",
    ),

    _make_pattern(
        name="Symbolic Design / Architecture",
        category="career",
        ideal={
            "force": 0.50, "stability": 0.65, "duration": 0.60,
            "initiation": 0.50, "flow": 0.65, "termination": 0.50,
            "complexity": 0.80, "density": 0.50, "balance": 0.80,
            "openness": 0.60, "depth": 0.70, "connectivity": 0.55,
        },
        weights={
            "complexity": 0.16, "balance": 0.15, "depth": 0.12,
            "flow": 0.10, "stability": 0.09, "openness": 0.09,
            "duration": 0.07, "connectivity": 0.07, "force": 0.05,
            "density": 0.04, "initiation": 0.03, "termination": 0.03,
        },
        threshold=0.58,
        rationale="Symbolic design requires high complexity (pattern recognition), "
                  "balance (aesthetic harmony), depth (meaning layers), with moderate "
                  "flow (creative process unfolds).",
    ),

    _make_pattern(
        name="Performing Arts",
        category="career",
        ideal={
            "force": 0.60, "stability": 0.40, "duration": 0.70,
            "initiation": 0.60, "flow": 0.80, "termination": 0.50,
            "complexity": 0.65, "density": 0.40, "balance": 0.50,
            "openness": 0.90, "depth": 0.55, "connectivity": 0.75,
        },
        weights={
            "openness": 0.16, "flow": 0.14, "connectivity": 0.13,
            "complexity": 0.10, "duration": 0.10, "force": 0.09,
            "initiation": 0.07, "depth": 0.06, "termination": 0.05,
            "balance": 0.04, "stability": 0.03, "density": 0.03,
        },
        threshold=0.55,
        rationale="Performing arts require extreme openness (expression), high flow "
                  "(movement/delivery), connectivity (audience rapport), with variable "
                  "stability (range of expression).",
    ),

    _make_pattern(
        name="Engineering / Technical",
        category="career",
        ideal={
            "force": 0.55, "stability": 0.75, "duration": 0.60,
            "initiation": 0.50, "flow": 0.50, "termination": 0.60,
            "complexity": 0.75, "density": 0.70, "balance": 0.70,
            "openness": 0.40, "depth": 0.65, "connectivity": 0.50,
        },
        weights={
            "stability": 0.14, "complexity": 0.14, "density": 0.12,
            "balance": 0.11, "depth": 0.10, "duration": 0.09,
            "termination": 0.08, "force": 0.06, "flow": 0.05,
            "initiation": 0.04, "connectivity": 0.04, "openness": 0.03,
        },
        threshold=0.58,
        rationale="Engineering requires stability (consistent methods), complexity "
                  "(handling intricate systems), density (detailed work), and balance "
                  "(systematic approaches).",
    ),

    _make_pattern(
        name="Therapist / Healer",
        category="career",
        ideal={
            "force": 0.35, "stability": 0.75, "duration": 0.80,
            "initiation": 0.35, "flow": 0.75, "termination": 0.35,
            "complexity": 0.55, "density": 0.35, "balance": 0.75,
            "openness": 0.80, "depth": 0.80, "connectivity": 0.85,
        },
        weights={
            "connectivity": 0.15, "depth": 0.14, "openness": 0.13,
            "flow": 0.12, "stability": 0.11, "duration": 0.09,
            "balance": 0.08, "complexity": 0.06, "force": 0.04,
            "termination": 0.03, "initiation": 0.03, "density": 0.02,
        },
        threshold=0.60,
        rationale="Healing requires deep connectivity, sustained depth (going beneath "
                  "surface), high openness (receptivity), with stability (consistent "
                  "presence) and low force.",
    ),
)


# =============================================================================
# Sports Domain Patterns
# =============================================================================

SPORTS_DOMAINS: Tuple[DomainPattern, ...] = (
    _make_pattern(
        name="Golf",
        category="sport",
        ideal={
            "force": 0.50, "stability": 0.90, "duration": 0.55,
            "initiation": 0.50, "flow": 0.70, "termination": 0.60,
            "complexity": 0.55, "density": 0.45, "balance": 0.90,
            "openness": 0.40, "depth": 0.70, "connectivity": 0.30,
        },
        weights={
            "stability": 0.18, "balance": 0.17, "flow": 0.12,
            "depth": 0.11, "termination": 0.09, "complexity": 0.07,
            "force": 0.07, "duration": 0.06, "initiation": 0.05,
            "openness": 0.03, "density": 0.03, "connectivity": 0.02,
        },
        threshold=0.62,
        rationale="Golf requires exceptional stability (consistency), balance (smooth "
                  "swing mechanics), depth (mental focus), and controlled flow. "
                  "Low connectivity (solo concentration).",
    ),

    _make_pattern(
        name="Archery / Shooting",
        category="sport",
        ideal={
            "force": 0.40, "stability": 0.95, "duration": 0.50,
            "initiation": 0.40, "flow": 0.55, "termination": 0.80,
            "complexity": 0.40, "density": 0.50, "balance": 0.90,
            "openness": 0.30, "depth": 0.80, "connectivity": 0.20,
        },
        weights={
            "stability": 0.20, "balance": 0.16, "termination": 0.14,
            "depth": 0.13, "flow": 0.09, "force": 0.07,
            "density": 0.05, "complexity": 0.05, "duration": 0.04,
            "initiation": 0.03, "openness": 0.02, "connectivity": 0.02,
        },
        threshold=0.65,
        rationale="Archery requires extreme stability (stillness), precise termination "
                  "(release point), high balance, and depth (focus). Very low "
                  "connectivity (isolated concentration).",
    ),

    _make_pattern(
        name="Team Sports (Soccer/Basketball)",
        category="sport",
        ideal={
            "force": 0.60, "stability": 0.50, "duration": 0.70,
            "initiation": 0.70, "flow": 0.80, "termination": 0.50,
            "complexity": 0.60, "density": 0.50, "balance": 0.50,
            "openness": 0.65, "depth": 0.40, "connectivity": 0.90,
        },
        weights={
            "connectivity": 0.18, "flow": 0.15, "initiation": 0.12,
            "duration": 0.10, "force": 0.09, "openness": 0.09,
            "complexity": 0.07, "stability": 0.06, "balance": 0.05,
            "termination": 0.04, "depth": 0.03, "density": 0.02,
        },
        threshold=0.55,
        rationale="Team sports require high connectivity (teamwork/passing), flow "
                  "(continuous play), quick initiation (reactions), with moderate "
                  "stability (adaptability to changing situations).",
    ),

    _make_pattern(
        name="Track / Endurance",
        category="sport",
        ideal={
            "force": 0.50, "stability": 0.80, "duration": 0.90,
            "initiation": 0.50, "flow": 0.90, "termination": 0.40,
            "complexity": 0.30, "density": 0.50, "balance": 0.70,
            "openness": 0.50, "depth": 0.55, "connectivity": 0.30,
        },
        weights={
            "duration": 0.19, "flow": 0.17, "stability": 0.14,
            "balance": 0.10, "depth": 0.08, "force": 0.08,
            "density": 0.06, "openness": 0.05, "initiation": 0.05,
            "complexity": 0.03, "termination": 0.03, "connectivity": 0.02,
        },
        threshold=0.58,
        rationale="Endurance requires exceptional duration (sustained effort), high "
                  "flow (rhythm), stability (pacing), with low complexity "
                  "(repetitive motion focus).",
    ),

    _make_pattern(
        name="Tennis (Singles)",
        category="sport",
        ideal={
            "force": 0.65, "stability": 0.65, "duration": 0.60,
            "initiation": 0.75, "flow": 0.60, "termination": 0.70,
            "complexity": 0.65, "density": 0.55, "balance": 0.70,
            "openness": 0.50, "depth": 0.55, "connectivity": 0.35,
        },
        weights={
            "initiation": 0.15, "force": 0.13, "balance": 0.12,
            "termination": 0.11, "stability": 0.10, "complexity": 0.09,
            "flow": 0.08, "duration": 0.07, "depth": 0.05,
            "density": 0.04, "openness": 0.03, "connectivity": 0.03,
        },
        threshold=0.58,
        rationale="Tennis singles requires quick initiation (reactions), force "
                  "(power shots), balance (court coverage), and clear termination "
                  "(point-ending shots). Low connectivity (1v1 sport).",
    ),

    _make_pattern(
        name="Martial Arts",
        category="sport",
        ideal={
            "force": 0.70, "stability": 0.75, "duration": 0.55,
            "initiation": 0.80, "flow": 0.65, "termination": 0.75,
            "complexity": 0.65, "density": 0.65, "balance": 0.80,
            "openness": 0.40, "depth": 0.70, "connectivity": 0.35,
        },
        weights={
            "initiation": 0.14, "balance": 0.13, "force": 0.12,
            "stability": 0.11, "termination": 0.10, "depth": 0.10,
            "flow": 0.08, "complexity": 0.07, "density": 0.05,
            "duration": 0.04, "openness": 0.03, "connectivity": 0.03,
        },
        threshold=0.60,
        rationale="Martial arts require explosive initiation, force, high balance "
                  "(stance), stability (grounding), decisive termination (strikes), "
                  "and depth (mind-body integration).",
    ),
)


# =============================================================================
# Combined Patterns
# =============================================================================

ALL_DOMAINS: Tuple[DomainPattern, ...] = CAREER_DOMAINS + SPORTS_DOMAINS


def get_domain(name: str) -> Optional[DomainPattern]:
    """Get a domain pattern by name."""
    for domain in ALL_DOMAINS:
        if domain.name.lower() == name.lower():
            return domain
    return None
