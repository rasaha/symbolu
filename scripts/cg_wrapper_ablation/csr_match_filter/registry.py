"""registry.py — domain registry for the C×R×S MATCH-filter wrapper.

Holds the 12D layer order, ontology rules (allowance), 12D domain templates (realization), and the
non-phonemic semantic material (term glosses + domain keyword sets) used by the S firewall.

These are illustrative seed values for the MVP — production should source templates/keywords from a
maintained registry and S from real embeddings. Nothing here touches governance/trust or generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

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
# These templates ARE the curated ontology (a bounded, deliberate artifact). Ontology allowance rules
# are derived from them; no per-domain hand tagging is required.
#        Pot   Idn   Exe   Str   Cog   Agy   Rsn   Prp   Wit   Uni   Int   Abs
_TEMPLATES = {
    "medicine":    [0.55, 0.80, 0.75, 0.70, 0.95, 0.65, 0.95, 0.90, 0.60, 0.75, 0.90, 0.55],
    "care":        [0.60, 0.65, 0.55, 0.55, 0.80, 0.55, 0.75, 0.90, 0.75, 0.85, 0.90, 0.70],
    "authority":   [0.60, 0.95, 0.90, 0.85, 0.70, 0.95, 0.75, 0.70, 0.40, 0.60, 0.65, 0.45],
    "law":         [0.45, 0.85, 0.70, 0.95, 0.80, 0.85, 0.90, 0.65, 0.55, 0.55, 0.60, 0.45],
    "service":     [0.55, 0.70, 0.75, 0.60, 0.60, 0.80, 0.55, 0.85, 0.60, 0.80, 0.80, 0.65],
    "commerce":    [0.50, 0.80, 0.85, 0.75, 0.55, 0.85, 0.50, 0.55, 0.35, 0.55, 0.55, 0.40],
    "fruit":       [0.85, 0.40, 0.30, 0.90, 0.20, 0.20, 0.15, 0.15, 0.55, 0.70, 0.60, 0.50],
    "technology":  [0.55, 0.60, 0.90, 0.85, 0.90, 0.70, 0.85, 0.60, 0.45, 0.55, 0.70, 0.45],
    "finance":     [0.50, 0.85, 0.85, 0.80, 0.65, 0.85, 0.70, 0.60, 0.35, 0.50, 0.55, 0.40],
    "nature":      [0.90, 0.40, 0.30, 0.60, 0.40, 0.25, 0.30, 0.50, 0.85, 0.90, 0.80, 0.70],
    "programming": [0.50, 0.55, 0.85, 0.90, 0.95, 0.60, 0.90, 0.60, 0.40, 0.50, 0.65, 0.40],
    "biology":     [0.80, 0.55, 0.50, 0.75, 0.80, 0.45, 0.70, 0.60, 0.60, 0.75, 0.85, 0.55],
    "astronomy":   [0.90, 0.45, 0.40, 0.60, 0.80, 0.30, 0.75, 0.55, 0.90, 0.85, 0.70, 0.65],
    "chemistry":   [0.60, 0.55, 0.60, 0.90, 0.85, 0.50, 0.85, 0.50, 0.45, 0.60, 0.80, 0.50],
    "mythology":   [0.75, 0.60, 0.40, 0.45, 0.55, 0.50, 0.45, 0.80, 0.90, 0.80, 0.60, 0.85],
    "heat":        [0.80, 0.45, 0.85, 0.60, 0.35, 0.80, 0.30, 0.40, 0.40, 0.55, 0.50, 0.45],
    "danger":      [0.50, 0.70, 0.85, 0.70, 0.50, 0.95, 0.45, 0.40, 0.30, 0.40, 0.40, 0.35],
    "furniture":   [0.70, 0.75, 0.35, 0.95, 0.20, 0.20, 0.15, 0.40, 0.55, 0.60, 0.60, 0.50],
    "security":    [0.50, 0.70, 0.80, 0.85, 0.85, 0.90, 0.85, 0.60, 0.50, 0.50, 0.65, 0.40],
    "agriculture": [0.85, 0.50, 0.60, 0.75, 0.45, 0.50, 0.40, 0.75, 0.60, 0.75, 0.85, 0.60],
}

_DEFINITIONS = {
    "medicine":    "diagnosis treatment healing clinical physician patient disease cure illness remedy",
    "care":        "nurture support comfort attend wellbeing compassion tending nursing therapy",
    "authority":   "power command rule control institution office govern enforce responsibility monarch",
    "law":         "legal court justice statute rights judge regulation enforce attorney advocate",
    "service":     "serve assist help provide support duty public",
    "commerce":    "trade business market buy sell money profit goods retail",
    "fruit":       "edible plant produce sweet orchard tree food botanical apple",
    "technology":  "technology engineering computing device software hardware machine innovation electronic system",
    "finance":     "finance money banking investment market currency credit economic capital trading",
    "nature":      "nature water river stream landscape environment ecosystem forest wild mountain shore",
    "programming": "programming software code computing language algorithm developer function variable script",
    "biology":     "biology life organism cell virus bacteria species evolution genetics anatomy animal",
    "astronomy":   "astronomy planet star space celestial orbit galaxy cosmos universe telescope solar",
    "chemistry":   "chemistry element compound reaction molecule atom matter metal substance acid liquid",
    "mythology":   "mythology deity god myth legend ancient divine worship ritual hero messenger roman",
    "heat":        "heat fire flame burning warmth thermal temperature combustion blaze ember",
    "danger":      "danger hazard threat risk harm warning unsafe peril emergency injury destruction",
    "furniture":   "furniture chair table seat couch household wooden domestic cabinet desk",
    "security":    "security protection defense malware computer network firewall attack hacker intrusion",
    "agriculture": "agriculture farming crop harvest soil cultivation field irrigation livestock plant",
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
# Hand-tagged rules are now OPTIONAL OVERRIDES, kept only where precision matters. Any domain with a
# 12D template gets its rule auto-derived (see derive_ontology_rule) — no per-domain tagging required.
ONTOLOGY_OVERRIDES: Dict[str, OntologyRule] = _ONTOLOGY
DOMAIN_REGISTRY: List[str] = sorted(DOMAIN_TEMPLATES)


def derive_ontology_rule(domain: str, vector: Optional[List[float]] = None,
                         required_min: float = 0.70, allowed_min: float = 0.65,
                         blocked_max: float = 0.30, k_required: int = 4) -> OntologyRule:
    """Derive an OntologyRule from a domain's 12D template (no hand tagging).

    The template already encodes which lanes a domain lives in: its high layers are required/allowed,
    its low layers are blocked. This is what makes the registry scale to arbitrary domains — author a
    template (or derive one from a definition/embedding) and the allowance rule follows.
    """
    vec = vector if vector is not None else DOMAIN_TEMPLATES[domain].vector
    ranked = sorted(zip(LAYERS_12, vec), key=lambda nv: -nv[1])
    required = [n for n, v in ranked if v >= required_min][:k_required]
    allowed = [n for n, v in zip(LAYERS_12, vec) if v >= allowed_min and n not in required]
    blocked = [n for n, v in zip(LAYERS_12, vec) if v <= blocked_max]
    return OntologyRule(domain, required, allowed, blocked)


def ontology_rule(domain: str) -> OntologyRule:
    """Resolve a domain's allowance rule: hand-tagged override if present, else derived from template."""
    if domain in ONTOLOGY_OVERRIDES:
        return ONTOLOGY_OVERRIDES[domain]
    if domain in DOMAIN_TEMPLATES:
        return derive_ontology_rule(domain)
    raise KeyError(f"unknown domain '{domain}' (no override and no template)")


# Back-compat alias: a mapping-like view that resolves overrides-or-derived on access.
class _OntologyRulesView:
    def __getitem__(self, domain: str) -> OntologyRule:
        return ontology_rule(domain)

    def __contains__(self, domain: str) -> bool:
        return domain in ONTOLOGY_OVERRIDES or domain in DOMAIN_TEMPLATES


ONTOLOGY_RULES = _OntologyRulesView()

# ----------------------------------------------------------------------------------------------- #
# DEMO / TEST FIXTURES ONLY — never required by the production path.                                #
# The S firewall sources term meaning from a definition_provider (dictionary/KB/embeddings) and     #
# similarity from an embedder; these curated tables exist purely to make the canonical doctor demo  #
# and the CPU tests deterministic. Do NOT rely on them in production.                               #
# ----------------------------------------------------------------------------------------------- #

# Demo glosses — also reused (legitimately) as a *known-concept* hint list for term extraction.
DEMO_TERM_GLOSSES: Dict[str, str] = {
    "doctor": "licensed medical practitioner who diagnoses and treats illness a healer and clinician",
    "healer": "one who restores health a practitioner of healing care and remedy",
    "authority figure": "a person with institutional power to command enforce and govern",
    "nurse": "trained practitioner who provides patient care nursing and support",
    "judge": "official who applies the law in court and renders justice",
}

# Demo curated S prior (term, domain) -> similarity in [0,1]; stands in for an embedding model.
DEMO_CURATED_SEMANTIC: Dict[tuple, float] = {
    ("doctor", "medicine"): 0.97, ("doctor", "care"): 0.86, ("doctor", "authority"): 0.48,
    ("doctor", "law"): 0.28, ("doctor", "service"): 0.55, ("doctor", "commerce"): 0.12,
    ("doctor", "fruit"): 0.02,
}

# Back-compat aliases (deprecated names). TERM_GLOSSES is consumed by term extraction as a
# known-concept list; CURATED_SEMANTIC is a demo fixture only.
TERM_GLOSSES = DEMO_TERM_GLOSSES
CURATED_SEMANTIC = DEMO_CURATED_SEMANTIC
