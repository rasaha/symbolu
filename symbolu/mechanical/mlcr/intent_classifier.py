"""
Intent Classification - Rule-Based Pattern Matching
====================================================

Classifies user query intent via pattern matching.
No ML/NLP pipelines - pure rule-based logic.

Version: v3.1
Status: Production
"""

import re
from typing import Optional, Dict, List, Tuple
from .activation_plan import IntentType


# Intent pattern rules (order matters - first match wins)
INTENT_PATTERNS = [
    # WHAT - Factual queries
    (IntentType.WHAT, [
        r"^what\s+(is|are|was|were|does|do)",
        r"^tell me (about|what|the)",
        r"^(define|explain|describe)",
        r"^how (much|many|often)",
        r"\b(price|cost|value|amount|number|quantity)\b"
    ]),
    
    # WHY - Causal reasoning
    (IntentType.WHY, [
        r"^why\s+(did|do|does|is|are|was|were)",
        r"^what('s| is) the (reason|cause|explanation)",
        r"\b(because|reason|cause|motive|rationale)\b",
        r"^how (come|is it that)"
    ]),
    
    # HOW - Process/method questions
    (IntentType.HOW, [
        r"^how (do i|can i|to|should i)",
        r"^what('s| is) the (process|method|way|approach)",
        r"^(show me|teach me|guide me)",
        r"\b(steps|procedure|method|technique|process)\b"
    ]),
    
    # REFLECTION - Self-reflection queries
    (IntentType.REFLECTION, [
        r"\b(i feel|i'm feeling)\b.*\b(why|how|what)\b",
        r"^(reflect on|think about) (my|our)",
        r"\b(self-reflection|introspect|contemplate)\b",
        r"\b(understand myself|know myself)\b",
        r"^why do i (keep|always|repeatedly)"
    ]),
    
    # FEELING - Emotional state
    (IntentType.FEELING, [
        r"\b(i feel|i'm feeling|feeling)\s+(anxious|worried|stressed|happy|sad)",
        r"\b(emotion|emotional|mood|sentiment)\b",
        r"^(i am|i'm)\s+(anxious|worried|stressed|overwhelmed)"
    ]),
    
    # SHOULD - Decision support
    (IntentType.SHOULD, [
        r"^should i",
        r"^(ought|must|need) i",
        r"^is it (good|bad|wise|worth)",
        r"\b(recommend|suggest|advise|opinion)\b",
        r"^what would you (recommend|suggest)"
    ]),
    
    # PLAN - Strategic planning
    (IntentType.PLAN, [
        r"^what('s| is) the best (way|strategy|approach|plan)",
        r"^how (should|would|can) (i|we) (plan|strategy|approach)",
        r"\b(strategy|plan|roadmap|blueprint|framework)\b",
        r"^help me (plan|strategy|organize)"
    ]),
    
    # WHO - Identity/persona
    (IntentType.WHO, [
        r"^who (is|are|was|were)",
        r"^what (person|people|individual)",
        r"\b(identity|person|individual|who)\b"
    ]),
    
    # COMMAND - Direct actions
    (IntentType.COMMAND, [
        r"^(create|make|build|generate|produce)",
        r"^(calculate|compute|determine|find)",
        r"^(show|display|list|give)",
        r"^(fill|complete|submit|execute)"
    ]),
    
    # META - Meta-cognitive
    (IntentType.META, [
        r"^how (do you|does this) work",
        r"^explain (your|this) (approach|method|system)",
        r"\b(meta|self-aware|introspective)\b",
        r"^what (are you|is this system)"
    ])
]


# Domain-specific intent patterns
DOMAIN_INTENT_PATTERNS = {
    "trading": [
        (IntentType.WHAT, [r"\b(price|volume|shares|stock|ticker)\b"]),
        (IntentType.WHY, [r"\b(fell|dropped|rose|rallied|moved)\b"]),
        (IntentType.COMMAND, [r"^(buy|sell|trade|order|fill|execute)"])
    ],
    "medical": [
        (IntentType.WHAT, [r"\b(symptom|diagnosis|treatment|condition)\b"]),
        (IntentType.HOW, [r"\b(treat|cure|manage|prevent)\b"])
    ],
    "emotional": [
        (IntentType.REFLECTION, [r"\b(feel|emotion|anxiety|stress)\b"]),
        (IntentType.WHY, [r"^why do i (feel|keep|always)"])
    ]
}


class IntentClassifier:
    """
    Rule-based intent classifier.
    
    Uses pattern matching to classify query intent.
    NO ML/NLP pipelines - pure deterministic logic.
    """
    
    def __init__(self):
        self.general_patterns = INTENT_PATTERNS
        self.domain_patterns = DOMAIN_INTENT_PATTERNS
    
    def classify(
        self, 
        text: str, 
        domain: Optional[str] = None
    ) -> Tuple[IntentType, Dict]:
        """
        Classify query intent.
        
        Args:
            text: Query text
            domain: Optional domain hint
            
        Returns:
            (intent_type, metadata)
        """
        text_lower = text.lower().strip()
        matched_patterns = []
        
        # Try domain-specific patterns first
        if domain and domain in self.domain_patterns:
            for intent_type, patterns in self.domain_patterns[domain]:
                for pattern in patterns:
                    if re.search(pattern, text_lower):
                        matched_patterns.append((intent_type, pattern, "domain"))
                        return intent_type, {
                            "confidence": 0.9,
                            "matched_pattern": pattern,
                            "source": "domain_specific",
                            "domain": domain
                        }
        
        # Try general patterns
        for intent_type, patterns in self.general_patterns:
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    matched_patterns.append((intent_type, pattern, "general"))
                    return intent_type, {
                        "confidence": 0.8,
                        "matched_pattern": pattern,
                        "source": "general"
                    }
        
        # Default to UNKNOWN if no matches
        return IntentType.UNKNOWN, {
            "confidence": 0.0,
            "matched_pattern": None,
            "source": "default"
        }
    
    def explain_classification(
        self, 
        intent: IntentType, 
        metadata: Dict
    ) -> str:
        """Generate human-readable explanation."""
        if intent == IntentType.UNKNOWN:
            return "Intent: UNKNOWN (no pattern matched)"
        
        confidence = metadata.get("confidence", 0.0)
        pattern = metadata.get("matched_pattern", "")
        source = metadata.get("source", "unknown")
        
        return (
            f"Intent: {intent.value} "
            f"(confidence: {confidence}, "
            f"pattern: {pattern[:50]}..., "
            f"source: {source})"
        )
    
    def get_intent_description(self, intent: IntentType) -> str:
        """Get description of intent type."""
        descriptions = {
            IntentType.WHAT: "Factual query seeking information",
            IntentType.WHY: "Causal reasoning query seeking explanation",
            IntentType.HOW: "Process/method query seeking guidance",
            IntentType.PLAN: "Strategic planning query",
            IntentType.SHOULD: "Decision support query",
            IntentType.REFLECTION: "Self-reflective query",
            IntentType.FEELING: "Emotional state query",
            IntentType.WHO: "Identity/persona query",
            IntentType.COMMAND: "Direct action command",
            IntentType.META: "Meta-cognitive query",
            IntentType.UNKNOWN: "Unclassifiable query"
        }
        return descriptions.get(intent, "Unknown intent type")


# Singleton instance
_intent_classifier = None

def get_intent_classifier() -> IntentClassifier:
    """Get singleton intent classifier."""
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = IntentClassifier()
    return _intent_classifier
