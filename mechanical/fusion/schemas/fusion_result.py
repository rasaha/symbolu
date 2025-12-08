"""
FusionResult Schema - Output from FusionEngine
Represents the final fused decision for downstream rendering
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from .candidate import Candidate


@dataclass
class FusionResult:
    """
    Result of fusion process
    
    Contains:
    - Selected candidate
    - Routing decisions for renderer
    - Explainability data
    - All ranked candidates
    """
    
    # Primary output
    selected_candidate: Candidate
    fusion_score: float
    
    # Ranking
    ranked_candidates: List[Candidate] = field(default_factory=list)
    
    # Routing decisions for downstream renderer
    routing: Dict[str, Any] = field(default_factory=dict)
    
    # Explainability
    explain: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default routing if not provided"""
        if not self.routing:
            self.routing = {
                "render_mode": "auto",
                "use_rules_renderer": False,
                "use_llm_renderer": True,
                "persona_hint": None,
                "dha_tone_hint": None,
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "selected_candidate": self.selected_candidate.to_dict(),
            "fusion_score": round(self.fusion_score, 4),
            "ranked_candidates": [c.to_dict() for c in self.ranked_candidates],
            "routing": self.routing,
            "explain": self.explain,
            "metadata": self.metadata,
        }
    
    def get_top_k_candidates(self, k: int = 3) -> List[Candidate]:
        """Get top k candidates"""
        return self.ranked_candidates[:k]
    
    def should_use_rules_renderer(self) -> bool:
        """Check if rules renderer should be used"""
        return self.routing.get("use_rules_renderer", False)
    
    def should_use_llm_renderer(self) -> bool:
        """Check if LLM renderer should be used"""
        return self.routing.get("use_llm_renderer", True)
    
    def get_persona_hint(self) -> Optional[str]:
        """Get persona hint for rendering"""
        return self.routing.get("persona_hint")
    
    def get_dha_tone_hint(self) -> Optional[str]:
        """Get DHA tone hint for rendering"""
        return self.routing.get("dha_tone_hint")


@dataclass  
class FusionContext:
    """
    Context for fusion decisions
    
    Includes MLCR decision, user state, and operational constraints
    """
    
    # MLCR decision
    tier: str  # LOWER, UPPER, HYBRID
    intent: str  # WHY, HOW, WHAT, ACTION
    domain: str
    entropy: Dict[str, float]
    ontology_mass: Dict[str, float]
    
    # User state
    user_id: Optional[str] = None
    conversation_history: List[str] = field(default_factory=list)
    
    # Operational constraints
    regulated_mode: bool = False
    latency_budget_ms: Optional[float] = None
    safety_thresholds: Dict[str, float] = field(default_factory=dict)
    
    # Personalization
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    def is_high_entropy(self) -> bool:
        """Check if entropy is high"""
        total_entropy = self.entropy.get("total_entropy", 0.0)
        return total_entropy > 0.6
    
    def is_regulated(self) -> bool:
        """Check if in regulated mode"""
        return self.regulated_mode
    
    def has_tight_latency(self) -> bool:
        """Check if latency budget is tight"""
        if self.latency_budget_ms is None:
            return False
        return self.latency_budget_ms < 500
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tier": self.tier,
            "intent": self.intent,
            "domain": self.domain,
            "entropy": self.entropy,
            "ontology_mass": self.ontology_mass,
            "user_id": self.user_id,
            "regulated_mode": self.regulated_mode,
            "latency_budget_ms": self.latency_budget_ms,
            "safety_thresholds": self.safety_thresholds,
            "user_preferences": self.user_preferences,
        }
