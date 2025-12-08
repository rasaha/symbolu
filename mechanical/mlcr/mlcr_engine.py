"""
MLCR Engine - Multi-Layer Consciousness RAG
============================================

Main orchestration engine for consciousness-aware query routing.

Routes queries through:
1. Ontology mass computation
2. Intent classification
3. Entropy computation
4. Tier selection
5. Expert routing
6. Renderer context building
7. Audit logging

Version: v3.1
Status: Production
"""

from typing import Dict, Optional, Any
from .activation_plan import ActivationPlan, TierType, IntentType
from .ontology_mass import get_ontology_computer
from .intent_classifier import get_intent_classifier
from .entropy_adapter import get_entropy_adapter
from .tier_selector import get_tier_selector
from .expert_router import get_expert_router
from .renderer_context import get_renderer_context_builder
from .explainability import get_explainability_logger


class MLCR:
    """
    Multi-Layer Consciousness RAG Engine.
    
    Main entry point for consciousness-aware query routing.
    Orchestrates all MLCR components to produce routing decisions.
    """
    
    def __init__(self):
        # Initialize all components
        self.ontology_computer = get_ontology_computer()
        self.intent_classifier = get_intent_classifier()
        self.entropy_adapter = get_entropy_adapter()
        self.tier_selector = get_tier_selector()
        self.expert_router = get_expert_router()
        self.renderer_context_builder = get_renderer_context_builder()
        self.explainability_logger = get_explainability_logger()
        
        self.version = "v3.1"
    
    def route(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Route query to appropriate experts.
        
        Args:
            text: Query text
            context: Optional context {
                "domain": str,
                "user_state": str,
                "session_id": str,
                ...
            }
            
        Returns:
            Complete routing decision with all metadata
        """
        # Extract context parameters
        domain = context.get("domain") if context else None
        user_state = context.get("user_state") if context else None
        
        # Step 1: Compute ontology mass
        ontology_result = self.ontology_computer.compute_mass(text)
        lower_mass = ontology_result["lower_mass"]
        upper_mass = ontology_result["upper_mass"]
        
        # Step 2: Classify intent
        intent, intent_metadata = self.intent_classifier.classify(text, domain)
        intent_confidence = intent_metadata.get("confidence", 0.8)
        
        # Step 3: Compute entropy
        entropy_result = self.entropy_adapter.compute_all(
            layer_activations=ontology_result["layer_activations"],
            lower_mass=lower_mass,
            upper_mass=upper_mass,
            intent_strength=intent_confidence,
            text=text
        )
        H_D = entropy_result["H_D"]
        H_G = entropy_result["H_G"]
        H_K = entropy_result["H_K"]
        
        # Step 4: Select tier
        tier, tier_metadata = self.tier_selector.select_tier(
            lower_mass=lower_mass,
            upper_mass=upper_mass,
            H_D=H_D,
            H_G=H_G,
            H_K=H_K
        )
        
        # Step 5: Route to experts
        activation = self.expert_router.route(
            tier=tier,
            intent=intent,
            domain=domain,
            user_state=user_state
        )
        
        # Step 6: Build renderer context
        renderer_context = self.renderer_context_builder.build_context(
            tier=tier,
            intent=intent,
            domain=domain,
            user_state=user_state,
            activation=activation
        )
        
        # Step 7: Generate audit log
        audit_log = self.explainability_logger.generate_log(
            text=text,
            ontology_result=ontology_result,
            intent=intent,
            intent_metadata=intent_metadata,
            entropy_result=entropy_result,
            tier=tier,
            tier_metadata=tier_metadata,
            activation=activation,
            renderer_context=renderer_context,
            domain=domain,
            user_state=user_state
        )
        
        # Build complete routing decision
        return {
            "tier": tier.value,
            "intent": intent.value,
            "ontology_mass": {
                "lower": lower_mass,
                "upper": upper_mass
            },
            "entropy": {
                "H_D": H_D,
                "H_G": H_G,
                "H_K": H_K
            },
            "activation_plan": activation,
            "renderer_context": renderer_context,
            "explain_log": audit_log,
            "metadata": {
                "version": self.version,
                "context": context
            }
        }
    
    def route_to_activation_plan(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> ActivationPlan:
        """
        Route query and return type-safe ActivationPlan.
        
        Convenient for downstream systems that prefer dataclass access.
        """
        decision = self.route(text, context)
        
        # Extract context parameters
        domain = context.get("domain") if context else None
        user_state = context.get("user_state") if context else None
        
        # Convert to ActivationPlan dataclass
        plan = ActivationPlan(
            tier=TierType(decision["tier"]),
            intent=IntentType(decision["intent"]),
            lower_mass=decision["ontology_mass"]["lower"],
            upper_mass=decision["ontology_mass"]["upper"],
            H_D=decision["entropy"]["H_D"],
            H_G=decision["entropy"]["H_G"],
            H_K=decision["entropy"]["H_K"],
            use_hrm=decision["activation_plan"]["use_hrm"],
            use_lcm=decision["activation_plan"]["use_lcm"],
            use_lam=decision["activation_plan"]["use_lam"],
            use_moe=decision["activation_plan"]["use_moe"],
            use_fusion=decision["activation_plan"]["use_fusion"],
            renderer_mode=decision["renderer_context"]["mode"],
            domain=domain,
            user_state=user_state,
            audit_log=decision["explain_log"]
        )
        
        return plan
    
    def explain(self, decision: Dict) -> str:
        """
        Generate human-readable explanation of routing decision.
        
        Args:
            decision: Result from route()
            
        Returns:
            Human-readable explanation string
        """
        return self.explainability_logger.format_log_human_readable(
            decision["explain_log"]
        )
    
    def compute_ontology_mass(self, text: str) -> Dict:
        """Compute ontology mass only (for testing/debugging)."""
        return self.ontology_computer.compute_mass(text)
    
    def classify_intent(
        self,
        text: str,
        domain: Optional[str] = None
    ) -> tuple[IntentType, Dict]:
        """Classify intent only (for testing/debugging)."""
        return self.intent_classifier.classify(text, domain)
    
    def compute_entropy(
        self,
        layer_activations: Dict,
        lower_mass: float,
        upper_mass: float,
        intent_strength: float = 1.0
    ) -> Dict:
        """Compute entropy only (for testing/debugging)."""
        return self.entropy_adapter.compute_all(
            layer_activations=layer_activations,
            lower_mass=lower_mass,
            upper_mass=upper_mass,
            intent_strength=intent_strength
        )
    
    def select_tier(
        self,
        lower_mass: float,
        upper_mass: float,
        H_D: Optional[float] = None,
        H_G: Optional[float] = None
    ) -> tuple[TierType, Dict]:
        """Select tier only (for testing/debugging)."""
        return self.tier_selector.select_tier(
            lower_mass=lower_mass,
            upper_mass=upper_mass,
            H_D=H_D,
            H_G=H_G
        )
    
    def get_version(self) -> str:
        """Get MLCR version."""
        return self.version
    
    def get_component_status(self) -> Dict[str, str]:
        """Get status of all components."""
        return {
            "ontology_computer": "active",
            "intent_classifier": "active",
            "entropy_adapter": "active (proxies)",
            "tier_selector": "active",
            "expert_router": "active",
            "renderer_context_builder": "active",
            "explainability_logger": "active",
            "version": self.version
        }


# Convenience function for quick routing
def route_query(text: str, domain: Optional[str] = None) -> Dict:
    """
    Quick routing function.
    
    Usage:
        decision = route_query("What is the price?", domain="trading")
    """
    mlcr = MLCR()
    context = {"domain": domain} if domain else None
    return mlcr.route(text, context)
