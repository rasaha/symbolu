"""
LCM v1.0 Models Module

Defines data models for the Low-Context Mapper:
- LCMInput: Input context for LCM processing
- LowContextMap: Output low-context structural map

All models are dataclasses for deterministic processing.
The LCM handles short, procedural, task-like, or low-context queries
where deep symbolic fusion is unnecessary.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class LCMInput:
    """
    Input context for LCM (Low-Context Mapper) processing.

    Contains all signals needed for building a low-context structural map:
    - Query text
    - Domain classification
    - Aspect probabilities from symbolic engine
    - Experiential anchor scores
    - Entropy measures (dimensional, guna, kosha)
    - Tier and flow mode context

    LCM is triggered when TTOR sets use_lcm=True, typically for:
    - domain in {"task", "code", "math", "lookup"}
    - tier = "lower"
    - entropy low/medium
    - anchors emphasize Needs / Exchange

    Attributes:
        text: The raw query text to analyze.
        domain: Domain classification (task, code, math, lookup, etc.)
        aspect_probs: Dictionary mapping aspect names to probabilities [0, 1].
        anchor_scores: Dictionary mapping anchor names to scores [0, 1].
        H_D: Dimensional entropy [0, ln(10) ~ 2.303]
        H_G: Guna entropy [0, ln(3) ~ 1.099]
        H_K: Kosha entropy [0, ln(5) ~ 1.609]
        tier: Routing tier from TTOR ("lower", "upper", "hybrid")
        flow_mode: Cognitive flow mode ("outer_only", "outer_plus_inner", "inner_priority")
    """

    text: str
    domain: str
    aspect_probs: Dict[str, float]
    anchor_scores: Dict[str, float]
    H_D: float
    H_G: float
    H_K: float
    tier: str
    flow_mode: str


@dataclass
class LowContextMap:
    """
    Output low-context structural map from LCM.

    Contains a minimal structured context summary optimized for:
    - Determinism
    - Speed
    - Clarity
    - Minimal symbolic behavior

    This map is used by Fusion or Renderer directly for simple task-like queries.

    Attributes:
        task_type: Classification of the task ("lookup", "math", "code", "action", "generic").
        key_terms: List of significant alphanumeric tokens extracted from the text.
        numeric_features: Dictionary with numeric properties extracted from text:
                         - count: number of numeric values found
                         - sum: sum of numeric values (if any)
                         - max: maximum numeric value (if any)
                         - min: minimum numeric value (if any)
        complexity_score: Heuristic complexity score [0, 1] based on token count.
                         Lower = simpler query.
        entropy_regime: Entropy classification ("low", "medium", "high").
        recommended_engine: Suggested downstream engine:
                           - "persona": conversational but low complexity
                           - "fusion": structured but slightly complex
                           - "renderer_only": purely deterministic output preferred
    """

    task_type: str = "generic"
    key_terms: List[str] = field(default_factory=list)
    numeric_features: Dict[str, float] = field(default_factory=dict)
    complexity_score: float = 0.0
    entropy_regime: str = "low"
    recommended_engine: str = "fusion"

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "task_type": self.task_type,
            "key_terms": self.key_terms,
            "numeric_features": self.numeric_features,
            "complexity_score": self.complexity_score,
            "entropy_regime": self.entropy_regime,
            "recommended_engine": self.recommended_engine,
        }

    def __repr__(self) -> str:
        """Concise representation for logging."""
        terms_preview = ", ".join(self.key_terms[:3]) if self.key_terms else "none"
        return (
            f"LowContextMap(task_type={self.task_type}, "
            f"complexity={self.complexity_score:.2f}, "
            f"regime={self.entropy_regime}, "
            f"engine={self.recommended_engine}, "
            f"terms=[{terms_preview}])"
        )
