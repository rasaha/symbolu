"""
Expert Router - Activation Planning Logic
==========================================

Routes queries to appropriate expert systems using TTOR canonical mapper rules v2.0.

Canonical Mapper Switching Rules:
- HRM: (tier != LOWER) and (normalized_entropy > 0.40)
- LCM: (tier == LOWER) and (normalized_entropy > 0.50)
- LAM: long_arc_tension > 0.50 OR temporal_patterns_detected
      OR (domain in ["therapy", "identity", "spiritual"] and normalized_entropy > 0.60)

Version: v3.2 (TTOR Integration)
Status: Production
"""

from typing import Dict, Optional, List
from .activation_plan import TierType, IntentType, ExpertTarget

# Constants for entropy computation (mirrored from TTOR)
H_D_MAX = 2.302585093  # ln(10)
H_G_MAX = 1.098612289  # ln(3)


class ExpertRouter:
    """
    Routes to expert systems using TTOR canonical mapper switching rules.

    Applies deterministic rules based on tier, entropy, domain, and long-arc tension
    to decide which mappers (HRM, LCM, LAM) should be activated.

    Expert Systems:
    - HRM: High Reasoning Module (abstract/symbolic)
    - LCM: Linguistic Coherence Module (concrete/semantic)
    - LAM: Life Anchor Module (emotional/therapeutic)
    - MoE: Mixture of Experts (domain-specific)
    - FusionEngine: Multi-channel blending (HYBRID only)
    """

    # Canonical thresholds (frozen in TTOR v2.0 specification)
    HRM_ENTROPY_THRESHOLD = 0.40
    LCM_ENTROPY_THRESHOLD = 0.50
    LAM_TENSION_THRESHOLD = 0.50
    LAM_DOMAIN_ENTROPY_THRESHOLD = 0.60
    LAM_DOMAINS = ["therapy", "identity", "spiritual"]

    def __init__(self):
        pass
    
    def route(
        self,
        tier: TierType,
        intent: IntentType,
        domain: Optional[str] = None,
        user_state: Optional[str] = None,
        H_D: Optional[float] = None,
        H_G: Optional[float] = None,
        long_arc_tension: Optional[float] = None,
    ) -> Dict[str, bool]:
        """
        Determine expert activation using TTOR canonical mapper rules v2.0.

        Args:
            tier: Selected tier (LOWER/UPPER/HYBRID)
            intent: Query intent type
            domain: Optional domain hint
            user_state: Optional user emotional state
            H_D: Optional dimensional entropy (for normalized_entropy computation)
            H_G: Optional guna entropy (for normalized_entropy computation)
            long_arc_tension: Optional long-arc tension value [0, 1]

        Returns:
            {
                "use_hrm": bool,
                "use_lcm": bool,
                "use_lam": bool,
                "use_moe": bool,
                "use_fusion": bool,
                "long_arc_tension": float  # for downstream use
            }
        """
        # Initialize all experts as inactive
        activation = {
            "use_hrm": False,
            "use_lcm": False,
            "use_lam": False,
            "use_moe": False,
            "use_fusion": False,
            "long_arc_tension": long_arc_tension if long_arc_tension is not None else 0.0,
        }

        # Compute normalized_entropy from H_D and H_G (if provided)
        normalized_entropy = self._compute_normalized_entropy(H_D, H_G)

        # Canonical TTOR mapper switching rules v2.0
        # ------------------------------------------

        # HRM: (tier != LOWER) and (normalized_entropy > 0.40)
        activation["use_hrm"] = (
            tier != TierType.LOWER and normalized_entropy > self.HRM_ENTROPY_THRESHOLD
        )

        # LCM: (tier == LOWER) and (normalized_entropy > 0.50)
        activation["use_lcm"] = (
            tier == TierType.LOWER and normalized_entropy > self.LCM_ENTROPY_THRESHOLD
        )

        # LAM: long_arc_tension > 0.50 OR temporal_patterns_detected
        #      OR (domain in ["therapy", "identity", "spiritual"] and normalized_entropy > 0.60)
        lat = activation["long_arc_tension"]
        temporal_patterns_detected = False  # TODO: Add temporal tracking
        activation["use_lam"] = (
            lat > self.LAM_TENSION_THRESHOLD
            or temporal_patterns_detected
            or (
                domain in self.LAM_DOMAINS
                and normalized_entropy > self.LAM_DOMAIN_ENTROPY_THRESHOLD
            )
        )

        # MoE: Activate if domain-specific (non-general domain)
        if domain and domain not in ("general", "generic", None):
            activation["use_moe"] = True

        # FusionEngine: Activate if 2+ experts are active
        active_count = sum([
            activation["use_hrm"],
            activation["use_lcm"],
            activation["use_lam"],
            activation["use_moe"],
        ])
        if active_count >= 2:
            activation["use_fusion"] = True

        return activation

    def _compute_normalized_entropy(
        self,
        H_D: Optional[float],
        H_G: Optional[float],
    ) -> float:
        """
        Compute normalized entropy from H_D and H_G using TTOR formula.

        normalized_entropy = 0.5 * (H_D / H_D_MAX) + 0.3 * (H_G / H_G_MAX)

        Args:
            H_D: Dimensional entropy [0, ln(10)]
            H_G: Guna entropy [0, ln(3)]

        Returns:
            Normalized entropy in [0, 1]
        """
        if H_D is None or H_G is None:
            # Default to medium entropy if not provided
            return 0.5

        # Normalize to [0, 1]
        H_D_norm = min(1.0, max(0.0, H_D / H_D_MAX)) if H_D_MAX > 0 else 0.0
        H_G_norm = min(1.0, max(0.0, H_G / H_G_MAX)) if H_G_MAX > 0 else 0.0

        # Weighted entropy mix (same formula as TTOR)
        # H_D has higher weight (0.5), H_G (0.3), H_K would be (0.2) but not used here
        normalized_entropy = 0.5 * H_D_norm + 0.3 * H_G_norm

        return normalized_entropy
    
    def get_activated_experts(
        self,
        activation: Dict[str, bool]
    ) -> List[ExpertTarget]:
        """Get list of activated experts."""
        experts = []
        if activation["use_hrm"]:
            experts.append(ExpertTarget.HRM)
        if activation["use_lcm"]:
            experts.append(ExpertTarget.LCM)
        if activation["use_lam"]:
            experts.append(ExpertTarget.LAM)
        if activation["use_moe"]:
            experts.append(ExpertTarget.MoE)
        return experts
    
    def explain_routing(
        self,
        tier: TierType,
        intent: IntentType,
        activation: Dict[str, bool],
        domain: Optional[str] = None
    ) -> List[str]:
        """Generate human-readable explanation of routing."""
        explanations = []
        
        explanations.append(f"Expert Routing for {tier.value} tier:")
        explanations.append("")
        
        # Show activation decisions
        experts_list = self.get_activated_experts(activation)
        explanations.append(f"Activated Experts: {len(experts_list)}")
        for expert in experts_list:
            explanations.append(f"  ✓ {expert.value}")
        
        # Explain rationale
        explanations.append("")
        explanations.append("Routing Rationale:")
        
        if tier == TierType.LOWER:
            explanations.append("  → LOWER tier: Concrete/factual processing")
            explanations.append("  → LCM: Semantic coherence and clarity")
            if activation["use_moe"]:
                explanations.append(f"  → MoE: Domain expertise ({domain})")
        
        elif tier == TierType.UPPER:
            explanations.append("  → UPPER tier: Abstract/symbolic processing")
            explanations.append("  → HRM: High-level reasoning and philosophy")
            if activation["use_lam"]:
                explanations.append("  → LAM: Emotional anchor (reflection query)")
        
        elif tier == TierType.HYBRID:
            explanations.append("  → HYBRID tier: Multi-channel processing")
            explanations.append("  → HRM: Abstract reasoning")
            explanations.append("  → LCM: Concrete semantics")
            if activation["use_moe"]:
                explanations.append(f"  → MoE: Domain expertise ({domain})")
            if activation["use_lam"]:
                explanations.append("  → LAM: Emotional anchor")
            if activation["use_fusion"]:
                explanations.append("  → FusionEngine: Blend multiple channels")
        
        # Show fusion decision
        if activation["use_fusion"]:
            explanations.append("")
            explanations.append("FusionEngine Activated:")
            explanations.append(f"  → Blending {len(experts_list)} expert channels")
            explanations.append("  → Will generate unified response")
        
        return explanations
    
    def get_expert_description(self, expert: ExpertTarget) -> str:
        """Get description of expert system."""
        descriptions = {
            ExpertTarget.HRM: (
                "High Reasoning Module: Handles abstract reasoning, "
                "philosophical queries, and symbolic analysis."
            ),
            ExpertTarget.LCM: (
                "Linguistic Coherence Module: Ensures semantic clarity, "
                "factual accuracy, and linguistic consistency."
            ),
            ExpertTarget.LAM: (
                "Life Anchor Module: Provides emotional grounding, "
                "therapeutic context, and self-reflection support."
            ),
            ExpertTarget.MoE: (
                "Mixture of Experts: Domain-specific knowledge pools "
                "for specialized queries (trading, medical, etc.)."
            )
        }
        return descriptions.get(expert, "Unknown expert")
    
    def requires_fusion(self, activation: Dict[str, bool]) -> bool:
        """Check if FusionEngine is needed."""
        return activation.get("use_fusion", False)
    
    def get_expert_count(self, activation: Dict[str, bool]) -> int:
        """Count activated experts (excluding fusion)."""
        count = 0
        if activation["use_hrm"]:
            count += 1
        if activation["use_lcm"]:
            count += 1
        if activation["use_lam"]:
            count += 1
        if activation["use_moe"]:
            count += 1
        return count


# Singleton instance
_expert_router = None

def get_expert_router() -> ExpertRouter:
    """Get singleton expert router."""
    global _expert_router
    if _expert_router is None:
        _expert_router = ExpertRouter()
    return _expert_router
