"""
Expert Router - Activation Planning Logic
==========================================

Routes queries to appropriate expert systems based on tier and intent.

Routing Rules:
- LOWER tier → LCM + MoE (if domain)
- UPPER tier → HRM only
- HYBRID tier → HRM + LCM + MoE + FusionEngine

Version: v3.1
Status: Production
"""

from typing import Dict, Optional, List
from .activation_plan import TierType, IntentType, ExpertTarget


class ExpertRouter:
    """
    Routes to expert systems based on tier and intent.
    
    Expert Systems:
    - HRM: High Reasoning Module (abstract/symbolic)
    - LCM: Linguistic Coherence Module (concrete/semantic)
    - LAM: Life Anchor Module (emotional/therapeutic)
    - MoE: Mixture of Experts (domain-specific)
    - FusionEngine: Multi-channel blending (HYBRID only)
    """
    
    def __init__(self):
        pass
    
    def route(
        self,
        tier: TierType,
        intent: IntentType,
        domain: Optional[str] = None,
        user_state: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Determine expert activation.
        
        Args:
            tier: Selected tier (LOWER/UPPER/HYBRID)
            intent: Query intent type
            domain: Optional domain hint
            user_state: Optional user emotional state
            
        Returns:
            {
                "use_hrm": bool,
                "use_lcm": bool,
                "use_lam": bool,
                "use_moe": bool,
                "use_fusion": bool
            }
        """
        # Initialize all experts as inactive
        activation = {
            "use_hrm": False,
            "use_lcm": False,
            "use_lam": False,
            "use_moe": False,
            "use_fusion": False
        }
        
        # LOWER tier routing
        if tier == TierType.LOWER:
            activation["use_lcm"] = True
            
            # Activate MoE if domain-specific
            if domain and domain != "general":
                activation["use_moe"] = True
        
        # UPPER tier routing
        elif tier == TierType.UPPER:
            activation["use_hrm"] = True
            
            # Special case: reflection/emotional queries may need LAM
            if intent in [IntentType.REFLECTION, IntentType.FEELING]:
                activation["use_lam"] = True
        
        # HYBRID tier routing
        elif tier == TierType.HYBRID:
            activation["use_hrm"] = True
            activation["use_lcm"] = True
            
            # Activate MoE if domain-specific
            if domain and domain != "general":
                activation["use_moe"] = True
            
            # Activate FusionEngine for multi-channel blending
            # (only if 2+ experts are active)
            active_count = sum([
                activation["use_hrm"],
                activation["use_lcm"],
                activation["use_moe"]
            ])
            if active_count >= 2:
                activation["use_fusion"] = True
            
            # Special case: reflection/emotional may need LAM
            if intent in [IntentType.REFLECTION, IntentType.FEELING]:
                activation["use_lam"] = True
                # LAM counts as an expert for fusion
                if active_count >= 1:
                    activation["use_fusion"] = True
        
        return activation
    
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
