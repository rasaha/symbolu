"""
Persona Selector (v2.8.2)
==========================

Deterministic logic for selecting the appropriate persona based on:
    - Domain (trading, emotional, spiritual, medical, etc.)
    - Tier (UPPER, HYBRID, LOWER)
    - Intent (why, how, what, meaning)
    - Bhava direction (upward, downward, neutral)
    - Entropy levels (stability indicators)
    - User override (explicit user request)

Selection is purely rule-based with NO machine learning.
"""

from typing import Dict, Any, Optional
from .default_personas import DOMAIN_TO_PERSONA_MAP


class PersonaSelector:
    """
    Deterministic persona selection engine.
    
    Selection Priority (highest to lowest):
        1. User override (explicit user request)
        2. Regulated domain check (medical, legal → regulator)
        3. Domain-specific mapping (trading → analyst, emotional → friendly)
        4. Tier-based selection (UPPER → sage, LOWER → analyst/coach)
        5. Intent-based selection (why → sage, how → coach/analyst)
        6. Bhava-based adjustment (downward → friendly/coach)
        7. Fallback to neutral
    """
    
    def __init__(self):
        """Initialize selector with domain mappings."""
        self.domain_map = DOMAIN_TO_PERSONA_MAP.copy()
        
        # Regulated domains always use regulator
        self.regulated_domains = {
            "medical", "legal", "regulatory", "compliance", "healthcare"
        }
        
        # High-risk domains that benefit from analyst
        self.analytical_domains = {
            "trading", "financial", "technical", "data", "analytics", "quantitative"
        }
        
        # Emotional/support domains
        self.supportive_domains = {
            "emotional", "relationship", "personal", "wellbeing", "support", "therapy"
        }
        
        # Spiritual/philosophical domains
        self.wisdom_domains = {
            "spiritual", "philosophical", "meaning", "consciousness", "existential"
        }
    
    def auto_select(
        self,
        explain_log: Dict[str, Any],
        user_override: Optional[str] = None
    ) -> str:
        """
        Automatically select the best persona based on context.
        
        Args:
            explain_log: MLCR explain log containing metadata
            user_override: Optional explicit persona request from user
            
        Returns:
            Persona ID (str)
        """
        # PRIORITY 1: User override always wins
        if user_override:
            return user_override
        
        # Extract metadata
        meta = explain_log.get("meta", {})
        domain = meta.get("domain", "").lower()
        tier = meta.get("tier", "").upper()
        intent = meta.get("intent", "").lower()
        bhava_direction = meta.get("bhava_direction", "neutral").lower()
        
        # PRIORITY 2: Regulated domains
        if domain in self.regulated_domains:
            return "regulator"
        
        # PRIORITY 3: Domain-specific selection
        if domain in self.domain_map:
            return self.domain_map[domain]
        
        # PRIORITY 4: Domain category patterns
        if domain in self.wisdom_domains:
            return "sage"
        if domain in self.analytical_domains:
            return "analyst"
        if domain in self.supportive_domains:
            return "friendly"
        
        # PRIORITY 5: Tier-based selection
        if tier == "UPPER":
            # Upper tier suggests philosophical/abstract reasoning
            if intent in ("why", "meaning"):
                return "sage"
            return "sage"  # Default for UPPER
        
        if tier == "LOWER":
            # Lower tier suggests concrete/practical needs
            if intent == "how":
                return "coach"
            return "analyst"  # Default for LOWER
        
        # PRIORITY 6: Intent-based selection (for HYBRID or unknown tier)
        if intent == "why" or intent == "meaning":
            return "sage"
        if intent == "how":
            # Check bhava for action vs. reflection
            if bhava_direction == "downward":
                return "coach"  # Action-oriented for downward movement
            return "analyst"  # Structured for neutral/upward
        if intent == "what":
            return "analyst"
        
        # PRIORITY 7: Bhava-based adjustment
        if bhava_direction == "downward":
            # Downward suggests need for grounding/action
            return "coach"
        if bhava_direction == "upward":
            # Upward suggests receptivity to deeper meaning
            return "sage"
        
        # PRIORITY 8: Fallback to neutral
        return "neutral"
    
    def select_with_reasoning(
        self,
        explain_log: Dict[str, Any],
        user_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Select persona and provide reasoning for the selection.
        
        Args:
            explain_log: MLCR explain log containing metadata
            user_override: Optional explicit persona request from user
            
        Returns:
            Dictionary with persona_id and selection_reasoning
        """
        # Extract metadata
        meta = explain_log.get("meta", {})
        domain = meta.get("domain", "").lower()
        tier = meta.get("tier", "").upper()
        intent = meta.get("intent", "").lower()
        bhava_direction = meta.get("bhava_direction", "neutral").lower()
        
        # User override
        if user_override:
            return {
                "persona_id": user_override,
                "reasoning": f"User explicitly requested '{user_override}' persona",
                "selection_path": "user_override"
            }
        
        # Regulated domains
        if domain in self.regulated_domains:
            return {
                "persona_id": "regulator",
                "reasoning": f"Domain '{domain}' requires regulatory compliance",
                "selection_path": "regulated_domain"
            }
        
        # Domain-specific
        if domain in self.domain_map:
            persona_id = self.domain_map[domain]
            return {
                "persona_id": persona_id,
                "reasoning": f"Domain '{domain}' maps to '{persona_id}' persona",
                "selection_path": "domain_mapping"
            }
        
        # Tier-based
        if tier == "UPPER":
            if intent in ("why", "meaning"):
                return {
                    "persona_id": "sage",
                    "reasoning": f"UPPER tier with '{intent}' intent suggests philosophical inquiry",
                    "selection_path": "tier_intent"
                }
            return {
                "persona_id": "sage",
                "reasoning": "UPPER tier suggests abstract/symbolic reasoning",
                "selection_path": "tier_based"
            }
        
        if tier == "LOWER":
            if intent == "how":
                return {
                    "persona_id": "coach",
                    "reasoning": "LOWER tier with 'how' intent suggests action focus",
                    "selection_path": "tier_intent"
                }
            return {
                "persona_id": "analyst",
                "reasoning": "LOWER tier suggests concrete/practical focus",
                "selection_path": "tier_based"
            }
        
        # Intent-based
        if intent == "why" or intent == "meaning":
            return {
                "persona_id": "sage",
                "reasoning": f"Intent '{intent}' requires deeper exploration",
                "selection_path": "intent_based"
            }
        
        if intent == "how":
            if bhava_direction == "downward":
                return {
                    "persona_id": "coach",
                    "reasoning": "'How' intent with downward Bhava suggests action orientation",
                    "selection_path": "intent_bhava"
                }
            return {
                "persona_id": "analyst",
                "reasoning": "'How' intent requires structured approach",
                "selection_path": "intent_based"
            }
        
        # Bhava-based
        if bhava_direction == "downward":
            return {
                "persona_id": "coach",
                "reasoning": "Downward Bhava suggests need for grounding and action",
                "selection_path": "bhava_based"
            }
        
        if bhava_direction == "upward":
            return {
                "persona_id": "sage",
                "reasoning": "Upward Bhava suggests receptivity to deeper meaning",
                "selection_path": "bhava_based"
            }
        
        # Fallback
        return {
            "persona_id": "neutral",
            "reasoning": "No specific indicators found, using neutral persona",
            "selection_path": "fallback"
        }
    
    def add_domain_mapping(self, domain: str, persona_id: str) -> None:
        """
        Add or update a domain-to-persona mapping.
        
        Args:
            domain: Domain identifier
            persona_id: Persona to map to
        """
        self.domain_map[domain] = persona_id
    
    def remove_domain_mapping(self, domain: str) -> None:
        """
        Remove a domain-to-persona mapping.
        
        Args:
            domain: Domain identifier
        """
        if domain in self.domain_map:
            del self.domain_map[domain]
