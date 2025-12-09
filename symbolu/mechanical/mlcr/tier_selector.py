"""
Tier Selector - Three-Tier Consciousness Routing
=================================================

Selects processing tier based on ontology mass and entropy.

Tier Logic:
- LOWER: Concrete/factual (lower_mass > 0.65)
- UPPER: Abstract/symbolic (upper_mass > 0.65)
- HYBRID: Mixed/complex (both < 0.65 OR high entropy)

Version: v3.1
Status: Production
"""

from typing import Dict, Optional, List
from .activation_plan import TierType


# Tier selection thresholds
TIER_THRESHOLDS = {
    "lower_mass": 0.65,
    "upper_mass": 0.65,
    "entropy_H_D": 1.2,
    "entropy_H_G": 1.1
}


class TierSelector:
    """
    Three-tier consciousness routing selector.
    
    Routes queries to:
    - LOWER: Concrete/manifest (LCM + MoE)
    - UPPER: Abstract/symbolic (HRM)
    - HYBRID: Mixed/complex (HRM + LCM + MoE + Fusion)
    """
    
    def __init__(self):
        self.thresholds = TIER_THRESHOLDS
    
    def select_tier(
        self,
        lower_mass: float,
        upper_mass: float,
        H_D: Optional[float] = None,
        H_G: Optional[float] = None,
        H_K: Optional[float] = None
    ) -> tuple[TierType, Dict]:
        """
        Select processing tier.
        
        Args:
            lower_mass: Lower tier mass (0-1)
            upper_mass: Upper tier mass (0-1)
            H_D: Dimensional entropy (optional)
            H_G: Guna entropy (optional)
            H_K: Kosha entropy (optional)
            
        Returns:
            (tier, metadata)
        """
        reasons = []
        
        # Check for entropy override (forces HYBRID)
        high_entropy = False
        if H_D is not None and H_D > self.thresholds["entropy_H_D"]:
            high_entropy = True
            reasons.append(f"High H_D ({H_D} > {self.thresholds['entropy_H_D']})")
        
        if H_G is not None and H_G > self.thresholds["entropy_H_G"]:
            high_entropy = True
            reasons.append(f"High H_G ({H_G} > {self.thresholds['entropy_H_G']})")
        
        if high_entropy:
            return TierType.HYBRID, {
                "reason": "High entropy forces HYBRID",
                "details": reasons,
                "override": "entropy"
            }
        
        # Standard mass-based selection
        if lower_mass > self.thresholds["lower_mass"]:
            reasons.append(
                f"Lower mass dominant ({lower_mass} > {self.thresholds['lower_mass']})"
            )
            return TierType.LOWER, {
                "reason": "Lower mass dominant (concrete/factual)",
                "details": reasons,
                "override": None
            }
        
        if upper_mass > self.thresholds["upper_mass"]:
            reasons.append(
                f"Upper mass dominant ({upper_mass} > {self.thresholds['upper_mass']})"
            )
            return TierType.UPPER, {
                "reason": "Upper mass dominant (abstract/symbolic)",
                "details": reasons,
                "override": None
            }
        
        # Both below threshold → HYBRID
        reasons.append(
            f"Mixed distribution (lower={lower_mass}, upper={upper_mass})"
        )
        return TierType.HYBRID, {
            "reason": "Mixed ontology distribution",
            "details": reasons,
            "override": None
        }
    
    def explain_tier_selection(
        self,
        tier: TierType,
        metadata: Dict,
        lower_mass: float,
        upper_mass: float,
        H_D: Optional[float] = None,
        H_G: Optional[float] = None
    ) -> List[str]:
        """Generate human-readable explanation of tier selection."""
        explanations = []
        
        explanations.append(f"Selected Tier: {tier.value}")
        explanations.append(f"Reason: {metadata['reason']}")
        explanations.append("")
        
        explanations.append("Mass Distribution:")
        explanations.append(f"  Lower: {lower_mass} (threshold: {self.thresholds['lower_mass']})")
        explanations.append(f"  Upper: {upper_mass} (threshold: {self.thresholds['upper_mass']})")
        
        if H_D is not None or H_G is not None:
            explanations.append("")
            explanations.append("Entropy Checks:")
            if H_D is not None:
                status = "HIGH ⚠️" if H_D > self.thresholds['entropy_H_D'] else "Normal"
                explanations.append(
                    f"  H_D: {H_D} (threshold: {self.thresholds['entropy_H_D']}) → {status}"
                )
            if H_G is not None:
                status = "HIGH ⚠️" if H_G > self.thresholds['entropy_H_G'] else "Normal"
                explanations.append(
                    f"  H_G: {H_G} (threshold: {self.thresholds['entropy_H_G']}) → {status}"
                )
        
        if metadata.get("override"):
            explanations.append("")
            explanations.append(f"Override: {metadata['override'].upper()}")
        
        explanations.append("")
        explanations.append("Tier Characteristics:")
        if tier == TierType.LOWER:
            explanations.append("  → Concrete/factual queries")
            explanations.append("  → Fast, deterministic processing")
            explanations.append("  → Activates: LCM + MoE")
        elif tier == TierType.UPPER:
            explanations.append("  → Abstract/symbolic queries")
            explanations.append("  → Deep reasoning required")
            explanations.append("  → Activates: HRM only")
        else:  # HYBRID
            explanations.append("  → Mixed/complex queries")
            explanations.append("  → Multi-channel processing")
            explanations.append("  → Activates: HRM + LCM + MoE + Fusion")
        
        return explanations
    
    def get_tier_description(self, tier: TierType) -> str:
        """Get description of tier."""
        descriptions = {
            TierType.LOWER: (
                "LOWER tier: Concrete/manifest queries requiring factual answers. "
                "Uses LCM (Linguistic Coherence) + MoE (domain experts) for fast, "
                "deterministic processing."
            ),
            TierType.UPPER: (
                "UPPER tier: Abstract/symbolic queries requiring deep reasoning. "
                "Uses HRM (High Reasoning Module) for philosophical/conceptual analysis."
            ),
            TierType.HYBRID: (
                "HYBRID tier: Mixed/complex queries requiring multiple reasoning channels. "
                "Uses HRM + LCM + MoE + FusionEngine to blend symbolic and concrete reasoning."
            )
        }
        return descriptions.get(tier, "Unknown tier")
    
    def update_threshold(self, threshold_name: str, value: float):
        """Update tier selection threshold."""
        if threshold_name in self.thresholds:
            self.thresholds[threshold_name] = value
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get current thresholds."""
        return self.thresholds.copy()


# Singleton instance
_tier_selector = None

def get_tier_selector() -> TierSelector:
    """Get singleton tier selector."""
    global _tier_selector
    if _tier_selector is None:
        _tier_selector = TierSelector()
    return _tier_selector
