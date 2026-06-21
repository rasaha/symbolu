"""registry.py — domain registry for the C×R×S MATCH-filter wrapper.

Holds the 12D layer order, ontology rules (allowance), 12D domain templates (realization), and the
non-phonemic semantic material (term glosses + domain keyword sets) used by the S firewall.

These are illustrative seed values for the MVP — production should source templates/keywords from a
maintained registry and S from real embeddings. Nothing here touches governance/trust or generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

LAYERS_12: List[str] = [
    "Potential", "Identity", "Execution", "Structure",
    "Cognition", "Agency", "Reasoning", "Purpose",
    "Witness", "Unifying", "Integration", "Absolving",
]
LAYER_INDEX: Dict[str, int] = {name: i for i, name in enumerate(LAYERS_12)}


@dataclass(frozen=True)
class OntologyRule:
    """Permission rules for a domain lane (drives C)."""
    domain: str
    required_high: List[str]
    allowed_high: List[str] = field(default_factory=list)
    blocked_high: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class DomainTemplate:
    """A domain's 12D realization template (drives R) + non-phonemic semantic material (drives S)."""
    domain: str
    vector: List[float]            # length-12, [0,1] per layer
    definition: str
    keywords: List[str]

    def __post_init__(self):
        if len(self.vector) != 12:
            raise ValueError(f"{self.domain}: template must be length-12, got {len(self.vector)}")


# --- 12D templates (order = LAYERS_12) ------------------------------------------------------------
#        Pot   Idn   Exe   Str   Cog   Agy   Rsn   Prp   Wit   Uni   Int   Abs
_TEMPLATES = {
    "medicine":  [0.55, 0.80, 0.75, 0.70, 0.95, 0.65, 0.95, 0.90, 0.60, 0.75, 0.90, 0.55],
    "care":      [0.60, 0.65, 0.55, 0.55, 0.80, 0.55, 0.75, 0.90, 0.75, 0.85, 0.90, 0.70],
    "authority": [0.60, 0.95, 0.90, 0.85, 0.70, 0.95, 0.75, 0.70, 0.40, 0.60, 0.65, 0.45],
    "law":       [0.45, 0.85, 0.70, 0.95, 0.80, 0.85, 0.90, 0.65, 0.55, 0.55, 0.60, 0.45],
    "service":   [0.55, 0.70, 0.75, 0.60, 0.60, 0.80, 0.55, 0.85, 0.60, 0.80, 0.80, 0.65],
    "commerce":  [0.50, 0.80, 0.85, 0.75, 0.55, 0.85, 0.50, 0.55, 0.35, 0.55, 0.55, 0.40],
    "fruit":     [0.85, 0.40, 0.30, 0.90, 0.20, 0.20, 0.15, 0.15, 0.55, 0.70, 0.60, 0.50],
}

_DEFINITIONS = {
    "medicine":  "diagnosis treatment healing clinical physician patient disease cure illness remedy",
    "care":      "nurture support comfort attend wellbeing compassion tending nursing",
    "authority": "power command rule control institution office govern enforce responsibility",
    "law":       "legal court justice statute rights judge regulation enforce",
    "service":   "serve assist help provide support duty public",
    "commerce":  "trade business market buy sell money profit goods retail",
    "fruit":     "edible plant produce sweet orchard tree food botanical apple",
}

_KEYWORDS = {d: sorted(set(defn.split())) for d, defn in _DEFINITIONS.items()}

_ONTOLOGY = {
    "medicine":  OntologyRule("medicine", ["Cognition", "Reasoning", "Purpose", "Integration"],
                              ["Execution", "Identity", "Structure"], []),
    "care":      OntologyRule("care", ["Cognition", "Purpose", "Integration"],
                              ["Unifying", "Witness"], []),
    "authority": OntologyRule("authority", ["Identity", "Agency", "Execution", "Structure"],
                              ["Reasoning", "Purpose"], []),
    "law":       OntologyRule("law", ["Identity", "Structure", "Reasoning", "Agency"],
                              ["Cognition", "Purpose"], []),
    "service":   OntologyRule("service", ["Purpose", "Integration", "Agency"],
                              ["Unifying", "Execution"], []),
    "commerce":  OntologyRule("commerce", ["Identity", "Execution", "Agency"],
                              ["Structure", "Purpose"], []),
    "fruit":     OntologyRule("fruit", ["Structure", "Potential"], ["Integration"],
                              ["Reasoning", "Agency", "Purpose"]),
}

DOMAIN_TEMPLATES: Dict[str, DomainTemplate] = {
    d: DomainTemplate(d, _TEMPLATES[d], _DEFINITIONS[d], _KEYWORDS[d]) for d in _TEMPLATES
}
ONTOLOGY_RULES: Dict[str, OntologyRule] = _ONTOLOGY
DOMAIN_REGISTRY: List[str] = sorted(DOMAIN_TEMPLATES)

# Curated term glosses (the non-phonemic "definition(term)" the S firewall reads). Production would
# pull these from a dictionary/KB/embeddings; here they are seed glosses for the demo terms.
TERM_GLOSSES: Dict[str, str] = {
    "doctor": "licensed medical practitioner who diagnoses and treats illness a healer and clinician",
    "healer": "one who restores health a practitioner of healing care and remedy",
    "authority figure": "a person with institutional power to command enforce and govern",
    "nurse": "trained practitioner who provides patient care nursing and support",
    "judge": "official who applies the law in court and renders justice",
}

# Optional curated S prior for clean, deterministic demos (term, domain) -> similarity in [0,1].
# This stands in for an embedding model; it is non-phonemic (keyed on meaning, not sound).
CURATED_SEMANTIC: Dict[tuple, float] = {
    ("doctor", "medicine"): 0.97, ("doctor", "care"): 0.86, ("doctor", "authority"): 0.48,
    ("doctor", "law"): 0.28, ("doctor", "service"): 0.55, ("doctor", "commerce"): 0.12,
    ("doctor", "fruit"): 0.02,
}
