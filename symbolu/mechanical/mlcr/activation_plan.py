"""
MLCR Activation Plan - Type-Safe Routing Output
================================================

Dataclass for downstream expert systems to consume MLCR routing decisions.

Version: v3.1
Status: Production
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class TierType(str, Enum):
    """Three-tier consciousness routing system."""
    LOWER = "LOWER"      # Concrete/factual
    UPPER = "UPPER"      # Abstract/symbolic
    HYBRID = "HYBRID"    # Mixed/complex


class IntentType(str, Enum):
    """Query intent categories."""
    WHAT = "WHAT"                  # Factual queries
    WHY = "WHY"                    # Causal reasoning
    HOW = "HOW"                    # Process/method
    PLAN = "PLAN"                  # Strategic planning
    SHOULD = "SHOULD"              # Decision support
    REFLECTION = "REFLECTION"      # Self-reflection
    FEELING = "FEELING"            # Emotional state
    WHO = "WHO"                    # Identity/persona
    COMMAND = "COMMAND"            # Direct actions
    META = "META"                  # Meta-cognitive
    UNKNOWN = "UNKNOWN"            # Cannot classify


class ExpertTarget(str, Enum):
    """Available expert systems."""
    HRM = "HRM"      # High Reasoning Module
    LCM = "LCM"      # Linguistic Coherence Module
    LAM = "LAM"      # Life Anchor Module
    MoE = "MoE"      # Mixture of Experts


@dataclass
class ActivationPlan:
    """
    Complete routing decision for downstream systems.
    
    This dataclass provides type-safe access to MLCR routing results,
    enabling downstream engines to make informed processing decisions.
    """
    
    # Core routing
    tier: TierType
    intent: IntentType
    
    # Ontology analysis
    lower_mass: float
    upper_mass: float
    
    # Entropy measurements (mechanical proxies)
    H_D: Optional[float] = None  # Dimensional entropy
    H_G: Optional[float] = None  # Guna entropy
    H_K: Optional[float] = None  # Kosha entropy (placeholder)
    
    # Expert activation flags
    use_hrm: bool = False
    use_lcm: bool = False
    use_lam: bool = False
    use_moe: bool = False
    use_fusion: bool = False
    
    # Activated experts list
    experts: List[ExpertTarget] = field(default_factory=list)
    
    # Renderer configuration
    renderer_mode: str = "standard"  # standard, regulated, symbolic, minimal
    
    # Context metadata
    domain: Optional[str] = None
    user_state: Optional[str] = None
    
    # Audit trail
    audit_log: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Build experts list from activation flags."""
        self.experts = []
        if self.use_hrm:
            self.experts.append(ExpertTarget.HRM)
        if self.use_lcm:
            self.experts.append(ExpertTarget.LCM)
        if self.use_lam:
            self.experts.append(ExpertTarget.LAM)
        if self.use_moe:
            self.experts.append(ExpertTarget.MoE)
    
    def requires_fusion(self) -> bool:
        """Check if FusionEngine is needed."""
        return self.use_fusion
    
    def expert_count(self) -> int:
        """Count activated experts."""
        return len(self.experts)
    
    def is_regulated(self) -> bool:
        """Check if compliance mode is active."""
        return self.renderer_mode == "regulated"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier": self.tier.value,
            "intent": self.intent.value,
            "lower_mass": self.lower_mass,
            "upper_mass": self.upper_mass,
            "entropy": {
                "H_D": self.H_D,
                "H_G": self.H_G,
                "H_K": self.H_K
            },
            "activation": {
                "hrm": self.use_hrm,
                "lcm": self.use_lcm,
                "lam": self.use_lam,
                "moe": self.use_moe,
                "fusion": self.use_fusion
            },
            "experts": [e.value for e in self.experts],
            "renderer_mode": self.renderer_mode,
            "domain": self.domain,
            "user_state": self.user_state,
            "audit_log": self.audit_log
        }
