"""
Ontology Mass Computation - Keyword-Based Layer Mapping
========================================================

Maps query text to 10-layer ontology via keyword matching.
This is a MECHANICAL approximation - NOT the real Symbol-U formula.

Version: v3.1
Status: Production
"""

import re
from typing import Dict, List, Tuple


# 10-Layer Ontology Keywords (from Symbol-U)
ONTOLOGY_KEYWORDS = {
    # LOWER TIER (Layers 1-5: Concrete/Manifest)
    1: {  # Execution (Karma)
        "keywords": [
            "do", "does", "doing", "action", "execute", "perform", "activity",
            "work", "task", "operation", "process", "function", "behavior",
            "implement", "carry out", "conduct", "run", "operate"
        ],
        "label": "Execution"
    },
    2: {  # Identity (Nāma-rūpa)
        "keywords": [
            "identity", "name", "label", "tag", "title", "role", "designation",
            "identify", "called", "known as", "referred to", "labeled",
            "classification", "category", "type", "kind"
        ],
        "label": "Identity"
    },
    3: {  # Form (Rūpa)
        "keywords": [
            "form", "shape", "body", "appearance", "structure", "physical",
            "material", "looks like", "visible", "spatial", "geometric",
            "size", "dimensions", "configuration", "layout"
        ],
        "label": "Form"
    },
    4: {  # Cognition (Manas)
        "keywords": [
            "think", "thought", "mind", "perception", "aware", "consciousness",
            "mental", "cognitive", "understand", "comprehend", "perceive",
            "sense", "notice", "recognize", "realize", "know"
        ],
        "label": "Cognition"
    },
    5: {  # Agency (Ahaṅkāra)
        "keywords": [
            "agency", "control", "ego", "self", "will", "autonomy", "choice",
            "power", "decide", "determine", "influence", "manage", "govern",
            "authority", "responsibility", "ownership", "doership"
        ],
        "label": "Agency"
    },
    
    # UPPER TIER (Layers 6-10: Abstract/Symbolic)
    6: {  # Reasoning (Buddhi)
        "keywords": [
            "why", "because", "reason", "reasoning", "logic", "rational",
            "intellect", "wisdom", "judgment", "discernment", "analysis",
            "discriminate", "evaluate", "assess", "conclude", "infer", "deduce"
        ],
        "label": "Reasoning"
    },
    7: {  # Purpose (Dharma)
        "keywords": [
            "purpose", "meaning", "direction", "calling", "dharma", "mission",
            "path", "destiny", "goal", "aim", "intention", "significance",
            "value", "worth", "importance", "relevance", "point"
        ],
        "label": "Purpose"
    },
    8: {  # Observation (Sākṣin)
        "keywords": [
            "observe", "witness", "watch", "awareness", "presence", "notice",
            "see", "perceive", "reflect", "contemplate", "introspect",
            "meta-cognition", "mindfulness", "detached", "objective"
        ],
        "label": "Observation"
    },
    9: {  # Essence (Ātman)
        "keywords": [
            "essence", "core", "soul", "self", "true nature", "being",
            "existence", "am", "is", "are", "fundamental", "essential",
            "intrinsic", "inherent", "authentic", "genuine", "real"
        ],
        "label": "Essence"
    },
    10: {  # Absolute (Brahman)
        "keywords": [
            "absolute", "universal", "infinite", "eternal", "transcendent",
            "ultimate", "supreme", "cosmic", "divine", "sacred", "spiritual",
            "oneness", "unity", "totality", "wholeness", "everything"
        ],
        "label": "Absolute"
    }
}


class OntologyMassComputer:
    """
    Computes ontology mass via keyword matching.
    
    This is a MECHANICAL proxy - NOT the real Symbol-U formula.
    Real ontology computation belongs in Symbol-U Core.
    """
    
    def __init__(self):
        self.ontology_map = ONTOLOGY_KEYWORDS
    
    def compute_mass(self, text: str) -> Dict[str, float]:
        """
        Compute ontology mass distribution.
        
        Args:
            text: Query text to analyze
            
        Returns:
            {
                "lower_mass": float (0-1),
                "upper_mass": float (0-1),
                "layer_activations": {1: 0.2, 2: 0.0, ...},
                "matched_keywords": [(layer, keyword), ...]
            }
        """
        text_lower = text.lower()
        tokens = re.findall(r'\b\w+\b', text_lower)
        
        # Track layer activations
        layer_hits = {i: 0 for i in range(1, 11)}
        matched_keywords = []
        
        # Match keywords to layers
        for layer, info in self.ontology_map.items():
            keywords = info["keywords"]
            for keyword in keywords:
                # Check for exact word match
                if keyword in tokens or keyword in text_lower:
                    layer_hits[layer] += 1
                    matched_keywords.append((layer, keyword))
        
        # Normalize to probabilities
        total_hits = sum(layer_hits.values())
        if total_hits == 0:
            # Default to mid-range if no matches
            layer_activations = {i: 0.1 for i in range(1, 11)}
            lower_mass = 0.5
            upper_mass = 0.5
        else:
            layer_activations = {
                i: layer_hits[i] / total_hits 
                for i in range(1, 11)
            }
            
            # Compute tier masses
            lower_mass = sum(layer_activations[i] for i in range(1, 6))
            upper_mass = sum(layer_activations[i] for i in range(6, 11))
        
        return {
            "lower_mass": round(lower_mass, 3),
            "upper_mass": round(upper_mass, 3),
            "layer_activations": {
                i: round(v, 3) for i, v in layer_activations.items()
            },
            "matched_keywords": matched_keywords,
            "dominant_layer": max(layer_activations, key=layer_activations.get),
            "dominant_label": self.ontology_map[
                max(layer_activations, key=layer_activations.get)
            ]["label"]
        }
    
    def get_layer_label(self, layer_id: int) -> str:
        """Get human-readable label for layer."""
        return self.ontology_map.get(layer_id, {}).get("label", "Unknown")
    
    def explain_mass(self, mass_result: Dict) -> List[str]:
        """Generate human-readable explanation of mass computation."""
        explanations = []
        
        explanations.append(
            f"Lower Mass: {mass_result['lower_mass']} "
            f"(Layers 1-5: Concrete/Manifest)"
        )
        explanations.append(
            f"Upper Mass: {mass_result['upper_mass']} "
            f"(Layers 6-10: Abstract/Symbolic)"
        )
        explanations.append(
            f"Dominant Layer: {mass_result['dominant_layer']} "
            f"({mass_result['dominant_label']})"
        )
        
        # Show top activated layers
        activations = mass_result['layer_activations']
        top_layers = sorted(
            activations.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:3]
        
        explanations.append("Top Activated Layers:")
        for layer_id, activation in top_layers:
            if activation > 0:
                label = self.get_layer_label(layer_id)
                explanations.append(f"  - Layer {layer_id} ({label}): {activation}")
        
        return explanations


# Singleton instance
_ontology_computer = None

def get_ontology_computer() -> OntologyMassComputer:
    """Get singleton ontology mass computer."""
    global _ontology_computer
    if _ontology_computer is None:
        _ontology_computer = OntologyMassComputer()
    return _ontology_computer
