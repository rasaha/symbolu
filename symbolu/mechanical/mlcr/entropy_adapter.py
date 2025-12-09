"""
Entropy Adapter - Mechanical Proxy Approximations
==================================================

Provides mechanical approximations of Symbol-U entropy formulas.
These are NOT the real H_D, H_G, H_K formulas.

IMPORTANT: Real entropy computation belongs in Symbol-U Core.
This module provides mechanical proxies for MLCR routing only.

Version: v3.1
Status: Production
"""

import math
from typing import Dict, Optional, List


class EntropyAdapter:
    """
    Mechanical entropy approximations.
    
    These are PROXIES, not the real Symbol-U formulas.
    Used only for MLCR tier selection thresholds.
    """
    
    def __init__(self):
        pass
    
    def compute_dimensional_entropy(
        self, 
        layer_activations: Dict[int, float]
    ) -> float:
        """
        Compute H_D proxy via Shannon entropy.
        
        This is a MECHANICAL approximation.
        Real H_D formula is in Symbol-U Core.
        
        Args:
            layer_activations: {layer_id: probability}
            
        Returns:
            H_D proxy (0 to ~3.32)
        """
        # Shannon entropy over 10 layers
        # H = -sum(p * log2(p))
        
        probs = [v for v in layer_activations.values() if v > 0]
        
        if not probs or sum(probs) == 0:
            return 0.0
        
        # Normalize probabilities
        total = sum(probs)
        probs = [p / total for p in probs]
        
        # Shannon entropy
        H_D = -sum(p * math.log2(p) for p in probs if p > 0)
        
        return round(H_D, 3)
    
    def compute_guna_entropy(
        self,
        lower_mass: float,
        upper_mass: float,
        intent_strength: float = 1.0
    ) -> float:
        """
        Compute H_G proxy via tension metric.
        
        This is a MECHANICAL approximation.
        Real H_G formula is in Symbol-U Core.
        
        Args:
            lower_mass: Lower tier mass (0-1)
            upper_mass: Upper tier mass (0-1)
            intent_strength: Intent classification confidence (0-1)
            
        Returns:
            H_G proxy (0 to ~2.0)
        """
        # Proxy: Tension between lower/upper + intent uncertainty
        
        # Mass tension (high when balanced)
        mass_tension = 2 * lower_mass * upper_mass  # 0 to 0.5
        
        # Intent uncertainty
        intent_uncertainty = 1.0 - intent_strength  # 0 to 1
        
        # Combined proxy
        H_G = mass_tension + intent_uncertainty
        
        return round(H_G, 3)
    
    def compute_kosha_entropy(
        self,
        text: str = None,
        **kwargs
    ) -> Optional[float]:
        """
        Compute H_K proxy - PLACEHOLDER.
        
        Real H_K requires Symbol-U Kosha resonance formulas.
        Returns None to indicate this is not yet implemented.
        
        Args:
            text: Query text (unused in proxy)
            
        Returns:
            None (placeholder)
        """
        # Placeholder - real H_K requires Symbol-U Core
        return None
    
    def compute_all(
        self,
        layer_activations: Dict[int, float],
        lower_mass: float,
        upper_mass: float,
        intent_strength: float = 1.0,
        text: str = None
    ) -> Dict[str, Optional[float]]:
        """
        Compute all entropy proxies.
        
        Returns:
            {
                "H_D": float,
                "H_G": float,
                "H_K": None
            }
        """
        return {
            "H_D": self.compute_dimensional_entropy(layer_activations),
            "H_G": self.compute_guna_entropy(
                lower_mass, 
                upper_mass, 
                intent_strength
            ),
            "H_K": self.compute_kosha_entropy(text)
        }
    
    def interpret_entropy(
        self,
        H_D: Optional[float],
        H_G: Optional[float],
        H_K: Optional[float]
    ) -> Dict[str, str]:
        """
        Interpret entropy values for human understanding.
        
        Returns:
            {
                "H_D_meaning": str,
                "H_G_meaning": str,
                "H_K_meaning": str,
                "overall": str
            }
        """
        interpretations = {}
        
        # H_D interpretation
        if H_D is not None:
            if H_D < 0.5:
                interpretations["H_D_meaning"] = "Very focused (low diversity)"
            elif H_D < 1.0:
                interpretations["H_D_meaning"] = "Moderate focus"
            elif H_D < 1.5:
                interpretations["H_D_meaning"] = "Balanced distribution"
            elif H_D < 2.0:
                interpretations["H_D_meaning"] = "High diversity"
            else:
                interpretations["H_D_meaning"] = "Very high complexity"
        else:
            interpretations["H_D_meaning"] = "Not computed"
        
        # H_G interpretation
        if H_G is not None:
            if H_G < 0.3:
                interpretations["H_G_meaning"] = "Clear intent, low tension"
            elif H_G < 0.7:
                interpretations["H_G_meaning"] = "Moderate complexity"
            elif H_G < 1.1:
                interpretations["H_G_meaning"] = "High tension/uncertainty"
            else:
                interpretations["H_G_meaning"] = "Very high complexity"
        else:
            interpretations["H_G_meaning"] = "Not computed"
        
        # H_K interpretation
        if H_K is not None:
            interpretations["H_K_meaning"] = f"Kosha resonance: {H_K}"
        else:
            interpretations["H_K_meaning"] = "Placeholder (requires Symbol-U Core)"
        
        # Overall assessment
        if H_D and H_G:
            if H_D > 1.2 or H_G > 1.1:
                interpretations["overall"] = "High complexity → forces HYBRID tier"
            else:
                interpretations["overall"] = "Normal complexity"
        else:
            interpretations["overall"] = "Incomplete entropy data"
        
        return interpretations
    
    def explain_calculation(
        self,
        entropy_result: Dict[str, Optional[float]],
        layer_activations: Dict[int, float],
        lower_mass: float,
        upper_mass: float
    ) -> List[str]:
        """Generate human-readable explanation of entropy computation."""
        explanations = []
        
        H_D = entropy_result.get("H_D")
        H_G = entropy_result.get("H_G")
        H_K = entropy_result.get("H_K")
        
        explanations.append("Entropy Computation (Mechanical Proxies):")
        explanations.append("")
        
        # H_D explanation
        if H_D is not None:
            active_layers = sum(1 for v in layer_activations.values() if v > 0)
            explanations.append(
                f"H_D (Dimensional): {H_D} "
                f"(Shannon entropy over {active_layers} active layers)"
            )
            interpretations = self.interpret_entropy(H_D, H_G, H_K)
            explanations.append(f"  → {interpretations['H_D_meaning']}")
        
        # H_G explanation
        if H_G is not None:
            tension = 2 * lower_mass * upper_mass
            explanations.append(
                f"H_G (Guna): {H_G} "
                f"(mass tension: {round(tension, 3)})"
            )
            interpretations = self.interpret_entropy(H_D, H_G, H_K)
            explanations.append(f"  → {interpretations['H_G_meaning']}")
        
        # H_K explanation
        explanations.append("H_K (Kosha): None (placeholder - requires Symbol-U Core)")
        
        return explanations


# Singleton instance
_entropy_adapter = None

def get_entropy_adapter() -> EntropyAdapter:
    """Get singleton entropy adapter."""
    global _entropy_adapter
    if _entropy_adapter is None:
        _entropy_adapter = EntropyAdapter()
    return _entropy_adapter
