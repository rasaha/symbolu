"""C×R×S MATCH-filter wrapper (a.k.a. CSR Match-Filter Wrapper).

A pairwise (term, domain) compatibility gate: MATCH(term, domain) = C × R × S, where
  C = ontological allowance (phonemic 12D profile vs ontology rules),
  R = structural realization strength (phonemic 12D profile vs domain template),
  S = external semantic coherence (NON-phonemic firewall).
It constrains the answer-space of a base LLM; it is NOT the CSR field and NOT STL. No governance,
no generation-injection, no logits. See docs/CSR_MATCH_FILTER_WRAPPER_DESIGN.md.
"""

from .match import (
    CSRMatchDecision,
    CSRMatchFilterWrapper,
    CSRMatchScore,
    CSRMatchTrace,
    CSRThresholds,
    DEFAULT_THRESHOLDS,
    build_prompt_frame,
    build_trace,
    compute_constraint,
    compute_realization,
    csr_alignment,
    decide,
    dominant_terms,
    score_match,
)
from .profile import compute_12d_profile, compute_12d_profile_dict, dominant_layers
from .registry import (
    DOMAIN_REGISTRY,
    DOMAIN_TEMPLATES,
    LAYERS_12,
    ONTOLOGY_OVERRIDES,
    ONTOLOGY_RULES,
    DomainTemplate,
    OntologyRule,
    derive_ontology_rule,
    ontology_rule,
)
from .semantic import (
    SemanticCoherenceAdapter,
    compute_semantic_coherence,
    hashing_embed,
    make_demo_adapter,
)

__all__ = [
    "LAYERS_12", "OntologyRule", "DomainTemplate", "DOMAIN_TEMPLATES", "ONTOLOGY_RULES",
    "DOMAIN_REGISTRY", "compute_12d_profile", "compute_12d_profile_dict", "dominant_layers",
    "SemanticCoherenceAdapter", "hashing_embed", "make_demo_adapter",
    "compute_semantic_coherence", "compute_constraint", "compute_realization", "decide",
    "score_match", "build_trace", "build_prompt_frame", "csr_alignment", "dominant_terms",
    "derive_ontology_rule", "ontology_rule", "ONTOLOGY_OVERRIDES", "CSRMatchScore",
    "CSRMatchTrace", "CSRMatchDecision", "CSRThresholds", "DEFAULT_THRESHOLDS",
    "CSRMatchFilterWrapper",
]
