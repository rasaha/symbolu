"""
Custom Vocabulary for STL
=========================

Allows organizations to define domain-specific terms, acronyms, and jargon
that STL should recognize and route correctly.

Schema:
    {
        "version": "1.0",
        "organization": "Acme Corp",
        "terms": [
            {
                "term": "JIRA",
                "expansion": "issue tracking system",
                "phonemes": ["JH", "IH", "R", "AH"],  # Optional
                "layer_affinities": {                  # Optional
                    "O3_EXECUTION": 0.8,
                    "O7_REASONING": 0.6
                },
                "intent": "action",                    # Optional override
                "synonyms": ["ticket", "issue"]        # Optional
            }
        ]
    }

Usage:
    from symbolu.hybrid.vocabulary import VocabularyLoader, CustomVocabulary

    # Load vocabulary
    vocab = VocabularyLoader.from_file("company_terms.json")

    # Use with router
    router = SemanticRouter(vocabulary=vocab)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import json
from pathlib import Path


@dataclass
class CustomTerm:
    """
    A custom term definition.

    Attributes:
        term: The term/acronym (e.g., "JIRA", "K8s", "HIPAA")
        expansion: Full expansion or description
        phonemes: Optional phoneme sequence (ARPABET)
        layer_affinities: Optional explicit layer scores (0.0 to 1.0)
        intent: Optional intent override (action, reasoning, etc.)
        synonyms: Optional list of synonyms
        category: Optional category for grouping
    """
    term: str
    expansion: str
    phonemes: Optional[Tuple[str, ...]] = None
    layer_affinities: Optional[Dict[str, float]] = None
    intent: Optional[str] = None
    synonyms: Tuple[str, ...] = ()
    category: Optional[str] = None

    def get_layer_vector(self) -> Optional[Tuple[float, ...]]:
        """
        Convert layer affinities to a 12D vector.

        Returns:
            Tuple of 12 floats, or None if no affinities defined
        """
        if not self.layer_affinities:
            return None

        from symbolu.resonance import LAYER_NAMES

        vector = []
        for layer in LAYER_NAMES:
            vector.append(self.layer_affinities.get(layer, 0.0))

        return tuple(vector)


@dataclass
class CustomVocabulary:
    """
    A collection of custom terms for an organization.

    Attributes:
        version: Schema version
        organization: Organization name
        terms: Dictionary mapping lowercase terms to CustomTerm
        synonyms: Dictionary mapping synonyms to primary terms
    """
    version: str = "1.0"
    organization: str = ""
    terms: Dict[str, CustomTerm] = field(default_factory=dict)
    synonyms: Dict[str, str] = field(default_factory=dict)

    def lookup(self, word: str) -> Optional[CustomTerm]:
        """
        Look up a word in the vocabulary.

        Args:
            word: Word to look up (case-insensitive)

        Returns:
            CustomTerm if found, None otherwise
        """
        word_lower = word.lower()

        # Direct lookup
        if word_lower in self.terms:
            return self.terms[word_lower]

        # Synonym lookup
        if word_lower in self.synonyms:
            primary = self.synonyms[word_lower]
            return self.terms.get(primary)

        return None

    def has_term(self, word: str) -> bool:
        """Check if vocabulary contains this term."""
        return self.lookup(word) is not None

    def get_intent_override(self, word: str) -> Optional[str]:
        """Get explicit intent override for a term."""
        term = self.lookup(word)
        if term and term.intent:
            return term.intent
        return None

    def get_layer_vector(self, word: str) -> Optional[Tuple[float, ...]]:
        """Get explicit layer vector for a term."""
        term = self.lookup(word)
        if term:
            return term.get_layer_vector()
        return None

    def add_term(self, term: CustomTerm) -> None:
        """Add a term to the vocabulary."""
        self.terms[term.term.lower()] = term

        # Index synonyms
        for syn in term.synonyms:
            self.synonyms[syn.lower()] = term.term.lower()

    def merge(self, other: "CustomVocabulary") -> None:
        """Merge another vocabulary into this one."""
        for term in other.terms.values():
            self.add_term(term)


class VocabularyLoader:
    """
    Loads custom vocabularies from files.

    Supported formats:
    - JSON (.json)
    - YAML (.yaml, .yml) - if PyYAML installed
    """

    @staticmethod
    def from_file(path: str) -> CustomVocabulary:
        """
        Load vocabulary from a file.

        Args:
            path: Path to vocabulary file

        Returns:
            CustomVocabulary instance
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Vocabulary file not found: {path}")

        suffix = path.suffix.lower()

        if suffix == ".json":
            return VocabularyLoader._load_json(path)
        elif suffix in (".yaml", ".yml"):
            return VocabularyLoader._load_yaml(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    @staticmethod
    def _load_json(path: Path) -> CustomVocabulary:
        """Load from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return VocabularyLoader._parse_data(data)

    @staticmethod
    def _load_yaml(path: Path) -> CustomVocabulary:
        """Load from YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML files: pip install pyyaml")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return VocabularyLoader._parse_data(data)

    @staticmethod
    def _parse_data(data: Dict[str, Any]) -> CustomVocabulary:
        """Parse vocabulary data from dict."""
        vocab = CustomVocabulary(
            version=data.get("version", "1.0"),
            organization=data.get("organization", ""),
        )

        for term_data in data.get("terms", []):
            term = CustomTerm(
                term=term_data["term"],
                expansion=term_data.get("expansion", term_data["term"]),
                phonemes=tuple(term_data["phonemes"]) if "phonemes" in term_data else None,
                layer_affinities=term_data.get("layer_affinities"),
                intent=term_data.get("intent"),
                synonyms=tuple(term_data.get("synonyms", [])),
                category=term_data.get("category"),
            )
            vocab.add_term(term)

        return vocab

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> CustomVocabulary:
        """Load vocabulary from a dictionary."""
        return VocabularyLoader._parse_data(data)


# Pre-defined vocabulary templates for common domains

TECH_VOCABULARY_TEMPLATE = {
    "version": "1.0",
    "organization": "Tech Template",
    "terms": [
        {
            "term": "API",
            "expansion": "application programming interface",
            "intent": "action",
            "layer_affinities": {"O3_ACTING": 0.7, "O6_REASONING": 0.6},
            "synonyms": ["endpoint", "interface"],
            "category": "development",
        },
        {
            "term": "K8s",
            "expansion": "Kubernetes container orchestration",
            "intent": "action",
            "layer_affinities": {"O3_ACTING": 0.8, "O5_DIRECTING": 0.5},
            "synonyms": ["kubernetes", "kube"],
            "category": "infrastructure",
        },
        {
            "term": "CI/CD",
            "expansion": "continuous integration and deployment",
            "intent": "action",
            "layer_affinities": {"O3_ACTING": 0.9, "O5_DIRECTING": 0.4},
            "synonyms": ["pipeline", "cicd"],
            "category": "development",
        },
        {
            "term": "PR",
            "expansion": "pull request code review",
            "intent": "action",
            "layer_affinities": {"O3_ACTING": 0.6, "O6_REASONING": 0.7},
            "synonyms": ["pull request", "merge request", "MR"],
            "category": "development",
        },
        {
            "term": "SLA",
            "expansion": "service level agreement",
            "intent": "reasoning",
            "layer_affinities": {"O6_REASONING": 0.7, "O5_DIRECTING": 0.5},
            "category": "operations",
        },
    ],
}

FINANCE_VOCABULARY_TEMPLATE = {
    "version": "1.0",
    "organization": "Finance Template",
    "terms": [
        {
            "term": "ROI",
            "expansion": "return on investment",
            "intent": "reasoning",
            "layer_affinities": {"O6_REASONING": 0.8, "O7_PURPOSING": 0.5},
            "category": "metrics",
        },
        {
            "term": "KPI",
            "expansion": "key performance indicator",
            "intent": "reasoning",
            "layer_affinities": {"O6_REASONING": 0.7, "O5_DIRECTING": 0.6},
            "synonyms": ["metric", "indicator"],
            "category": "metrics",
        },
        {
            "term": "P&L",
            "expansion": "profit and loss statement",
            "intent": "reasoning",
            "layer_affinities": {"O6_REASONING": 0.8, "O4_TAGGING": 0.4},
            "synonyms": ["income statement", "PnL"],
            "category": "accounting",
        },
        {
            "term": "EBITDA",
            "expansion": "earnings before interest taxes depreciation amortization",
            "intent": "reasoning",
            "layer_affinities": {"O6_REASONING": 0.9},
            "category": "accounting",
        },
    ],
}

HEALTHCARE_VOCABULARY_TEMPLATE = {
    "version": "1.0",
    "organization": "Healthcare Template",
    "terms": [
        {
            "term": "HIPAA",
            "expansion": "health insurance portability accountability act",
            "intent": "reasoning",
            "layer_affinities": {"O6_REASONING": 0.6, "O5_DIRECTING": 0.7},
            "category": "compliance",
        },
        {
            "term": "EMR",
            "expansion": "electronic medical record",
            "intent": "action",
            "layer_affinities": {"O3_ACTING": 0.6, "O4_TAGGING": 0.7},
            "synonyms": ["EHR", "medical record"],
            "category": "systems",
        },
        {
            "term": "PHI",
            "expansion": "protected health information",
            "intent": "reasoning",
            "layer_affinities": {"O6_REASONING": 0.5, "O5_DIRECTING": 0.6},
            "category": "compliance",
        },
    ],
}


def get_template_vocabulary(domain: str) -> CustomVocabulary:
    """
    Get a pre-defined vocabulary template for a domain.

    Args:
        domain: Domain name (tech, finance, healthcare)

    Returns:
        CustomVocabulary with common terms for that domain
    """
    templates = {
        "tech": TECH_VOCABULARY_TEMPLATE,
        "finance": FINANCE_VOCABULARY_TEMPLATE,
        "healthcare": HEALTHCARE_VOCABULARY_TEMPLATE,
    }

    if domain.lower() not in templates:
        raise ValueError(f"Unknown domain: {domain}. Available: {list(templates.keys())}")

    return VocabularyLoader.from_dict(templates[domain.lower()])
