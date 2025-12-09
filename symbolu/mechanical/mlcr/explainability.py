"""
Explainability Module - Audit Log Generator
============================================

Generates comprehensive audit logs for MLCR routing decisions.
Essential for transparency, debugging, and compliance.

Version: v3.1
Status: Production
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from .activation_plan import TierType, IntentType, ExpertTarget


class ExplainabilityLogger:
    """
    Generates detailed audit logs for MLCR decisions.
    
    Provides:
    - Decision trail
    - Reasoning explanations
    - Component breakdowns
    - Debugging information
    """
    
    def __init__(self):
        pass
    
    def generate_log(
        self,
        text: str,
        ontology_result: Dict,
        intent: IntentType,
        intent_metadata: Dict,
        entropy_result: Dict,
        tier: TierType,
        tier_metadata: Dict,
        activation: Dict[str, bool],
        renderer_context: Dict,
        domain: Optional[str] = None,
        user_state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate complete audit log.
        
        Args:
            text: Original query text
            ontology_result: Ontology mass computation result
            intent: Classified intent
            intent_metadata: Intent classification metadata
            entropy_result: Entropy computation result
            tier: Selected tier
            tier_metadata: Tier selection metadata
            activation: Expert activation flags
            renderer_context: Renderer context
            domain: Optional domain
            user_state: Optional user state
            
        Returns:
            Comprehensive audit log dictionary
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Build structured log
        log = {
            "timestamp": timestamp,
            "query": {
                "text": text,
                "length": len(text),
                "word_count": len(text.split()),
                "domain": domain,
                "user_state": user_state
            },
            "ontology_analysis": {
                "lower_mass": ontology_result["lower_mass"],
                "upper_mass": ontology_result["upper_mass"],
                "dominant_layer": ontology_result["dominant_layer"],
                "dominant_label": ontology_result["dominant_label"],
                "matched_keywords": len(ontology_result["matched_keywords"]),
                "layer_activations": ontology_result["layer_activations"]
            },
            "intent_classification": {
                "intent": intent.value,
                "confidence": intent_metadata.get("confidence", 0.0),
                "matched_pattern": intent_metadata.get("matched_pattern", ""),
                "source": intent_metadata.get("source", "")
            },
            "entropy_computation": {
                "H_D": entropy_result.get("H_D"),
                "H_G": entropy_result.get("H_G"),
                "H_K": entropy_result.get("H_K")
            },
            "tier_selection": {
                "tier": tier.value,
                "reason": tier_metadata.get("reason", ""),
                "override": tier_metadata.get("override")
            },
            "expert_activation": activation,
            "renderer_context": renderer_context,
            "decision_trail": self._build_decision_trail(
                ontology_result,
                intent,
                entropy_result,
                tier,
                tier_metadata,
                activation
            ),
            "metadata": {
                "version": "MLCR v3.1",
                "layer": "mechanical"
            }
        }
        
        return log
    
    def _build_decision_trail(
        self,
        ontology_result: Dict,
        intent: IntentType,
        entropy_result: Dict,
        tier: TierType,
        tier_metadata: Dict,
        activation: Dict[str, bool]
    ) -> List[Dict[str, str]]:
        """Build step-by-step decision trail."""
        trail = []
        
        # Step 1: Ontology analysis
        trail.append({
            "step": 1,
            "action": "Compute ontology mass",
            "result": f"Lower={ontology_result['lower_mass']}, Upper={ontology_result['upper_mass']}",
            "reasoning": f"Dominant: {ontology_result['dominant_label']}"
        })
        
        # Step 2: Intent classification
        trail.append({
            "step": 2,
            "action": "Classify intent",
            "result": intent.value,
            "reasoning": f"Pattern-based classification"
        })
        
        # Step 3: Entropy computation
        H_D = entropy_result.get("H_D")
        H_G = entropy_result.get("H_G")
        trail.append({
            "step": 3,
            "action": "Compute entropy",
            "result": f"H_D={H_D}, H_G={H_G}",
            "reasoning": "Mechanical proxy approximations"
        })
        
        # Step 4: Tier selection
        trail.append({
            "step": 4,
            "action": "Select tier",
            "result": tier.value,
            "reasoning": tier_metadata.get("reason", "")
        })
        
        # Step 5: Expert routing
        active_experts = [k for k, v in activation.items() if v and k != "use_fusion"]
        trail.append({
            "step": 5,
            "action": "Route to experts",
            "result": ", ".join(active_experts),
            "reasoning": f"Based on {tier.value} tier logic"
        })
        
        # Step 6: Fusion decision
        if activation.get("use_fusion", False):
            trail.append({
                "step": 6,
                "action": "Activate FusionEngine",
                "result": "Yes",
                "reasoning": "Multiple experts require blending"
            })
        
        return trail
    
    def format_log_human_readable(self, log: Dict) -> str:
        """Format log as human-readable text."""
        lines = []
        
        lines.append("=" * 80)
        lines.append("MLCR ROUTING AUDIT LOG")
        lines.append("=" * 80)
        lines.append(f"Timestamp: {log['timestamp']}")
        lines.append("")
        
        # Query
        lines.append("QUERY:")
        lines.append(f"  Text: {log['query']['text']}")
        lines.append(f"  Domain: {log['query']['domain']}")
        lines.append("")
        
        # Ontology
        lines.append("ONTOLOGY ANALYSIS:")
        onto = log['ontology_analysis']
        lines.append(f"  Lower Mass: {onto['lower_mass']}")
        lines.append(f"  Upper Mass: {onto['upper_mass']}")
        lines.append(f"  Dominant: Layer {onto['dominant_layer']} ({onto['dominant_label']})")
        lines.append("")
        
        # Intent
        lines.append("INTENT CLASSIFICATION:")
        intent = log['intent_classification']
        lines.append(f"  Intent: {intent['intent']}")
        lines.append(f"  Confidence: {intent['confidence']}")
        lines.append("")
        
        # Entropy
        lines.append("ENTROPY COMPUTATION:")
        entropy = log['entropy_computation']
        lines.append(f"  H_D: {entropy['H_D']}")
        lines.append(f"  H_G: {entropy['H_G']}")
        lines.append(f"  H_K: {entropy['H_K']} (placeholder)")
        lines.append("")
        
        # Tier
        lines.append("TIER SELECTION:")
        tier = log['tier_selection']
        lines.append(f"  Tier: {tier['tier']}")
        lines.append(f"  Reason: {tier['reason']}")
        lines.append("")
        
        # Experts
        lines.append("EXPERT ACTIVATION:")
        activation = log['expert_activation']
        for expert, active in activation.items():
            status = "✓" if active else "✗"
            lines.append(f"  {status} {expert}")
        lines.append("")
        
        # Renderer
        lines.append("RENDERER CONTEXT:")
        renderer = log['renderer_context']
        lines.append(f"  Mode: {renderer['mode']}")
        lines.append(f"  Tone: {renderer['tone']}")
        lines.append("")
        
        # Decision Trail
        lines.append("DECISION TRAIL:")
        for step in log['decision_trail']:
            lines.append(f"  Step {step['step']}: {step['action']}")
            lines.append(f"    → {step['result']}")
            lines.append(f"    Reasoning: {step['reasoning']}")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def extract_key_metrics(self, log: Dict) -> Dict[str, Any]:
        """Extract key metrics for monitoring/analytics."""
        return {
            "timestamp": log["timestamp"],
            "tier": log["tier_selection"]["tier"],
            "intent": log["intent_classification"]["intent"],
            "lower_mass": log["ontology_analysis"]["lower_mass"],
            "upper_mass": log["ontology_analysis"]["upper_mass"],
            "H_D": log["entropy_computation"]["H_D"],
            "H_G": log["entropy_computation"]["H_G"],
            "experts_activated": sum(log["expert_activation"].values()),
            "fusion_used": log["expert_activation"].get("use_fusion", False),
            "renderer_mode": log["renderer_context"]["mode"],
            "domain": log["query"]["domain"]
        }
    
    def compare_decisions(self, log1: Dict, log2: Dict) -> Dict[str, Any]:
        """Compare two routing decisions."""
        comparison = {
            "tier_match": log1["tier_selection"]["tier"] == log2["tier_selection"]["tier"],
            "intent_match": log1["intent_classification"]["intent"] == log2["intent_classification"]["intent"],
            "mass_delta": {
                "lower": abs(log1["ontology_analysis"]["lower_mass"] - log2["ontology_analysis"]["lower_mass"]),
                "upper": abs(log1["ontology_analysis"]["upper_mass"] - log2["ontology_analysis"]["upper_mass"])
            },
            "expert_diff": self._compare_activations(
                log1["expert_activation"],
                log2["expert_activation"]
            )
        }
        return comparison
    
    def _compare_activations(self, act1: Dict, act2: Dict) -> List[str]:
        """Compare expert activations."""
        differences = []
        for expert in act1.keys():
            if act1.get(expert) != act2.get(expert):
                status1 = "active" if act1.get(expert) else "inactive"
                status2 = "active" if act2.get(expert) else "inactive"
                differences.append(f"{expert}: {status1} → {status2}")
        return differences


# Singleton instance
_explainability_logger = None

def get_explainability_logger() -> ExplainabilityLogger:
    """Get singleton explainability logger."""
    global _explainability_logger
    if _explainability_logger is None:
        _explainability_logger = ExplainabilityLogger()
    return _explainability_logger
