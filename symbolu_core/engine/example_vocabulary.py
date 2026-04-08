"""
Example Vocabulary Configurations
=================================

Pre-built vocabulary configurations for common use cases.
These can boost routing confidence by 20-30% for domain-specific queries.

Usage:
    from symbolu_core.engine import create_engine, EngineTier
    from symbolu_core.engine.example_vocabulary import (
        RELATIONSHIP_VOCABULARY,
        TECH_SUPPORT_VOCABULARY,
        create_custom_vocabulary,
    )

    # Use pre-built vocabulary
    engine = create_engine(
        tier=EngineTier.CONSUMER,
        vocabulary=RELATIONSHIP_VOCABULARY,
    )

    # Or create custom vocabulary
    vocab = create_custom_vocabulary(
        domain_terms=["JIRA", "K8s", "CI/CD"],
        intent="action",
        boost=0.25,
    )
    engine = create_engine(tier=EngineTier.CONSUMER, vocabulary=vocab)
"""

from symbolu_core.hybrid.vocabulary import CustomVocabulary, VocabularyLoader


# =============================================================================
# Pre-built Vocabularies
# =============================================================================

def _create_relationship_vocabulary() -> CustomVocabulary:
    """
    Vocabulary for relationship/emotional support queries.

    Boosts confidence for emotional language patterns that
    phoneme analysis alone may not capture well.
    """
    return VocabularyLoader.from_dict({
        "emotional_states": {
            "patterns": [
                "feeling", "feelings", "emotion", "emotional",
                "sad", "sadness", "happy", "happiness",
                "anxious", "anxiety", "worried", "worry",
                "lonely", "loneliness", "scared", "afraid",
                "depressed", "depression", "stressed", "stress",
                "overwhelmed", "frustrated", "angry", "upset",
            ],
            "intent": "relationship",
            "boost": 0.25,
        },
        "relationship_terms": {
            "patterns": [
                "friend", "friends", "friendship",
                "family", "parent", "parents", "child", "children",
                "partner", "spouse", "husband", "wife",
                "boyfriend", "girlfriend", "relationship",
                "colleague", "coworker", "team", "boss",
            ],
            "intent": "relationship",
            "boost": 0.20,
        },
        "support_seeking": {
            "patterns": [
                "help me", "i need", "someone to talk",
                "advice", "guidance", "support", "cope",
                "struggling", "dealing with", "going through",
            ],
            "intent": "relationship",
            "boost": 0.30,
        },
    })


def _create_tech_support_vocabulary() -> CustomVocabulary:
    """
    Vocabulary for technical support/DevOps queries.

    Boosts confidence for technical jargon that may not
    have clear phoneme patterns.
    """
    return VocabularyLoader.from_dict({
        "infrastructure": {
            "patterns": [
                "k8s", "kubernetes", "docker", "container",
                "aws", "gcp", "azure", "cloud",
                "ec2", "lambda", "s3", "rds",
                "terraform", "ansible", "helm",
            ],
            "intent": "action",
            "boost": 0.25,
        },
        "cicd": {
            "patterns": [
                "ci/cd", "cicd", "pipeline", "jenkins",
                "github actions", "gitlab", "circleci",
                "build", "deploy", "release", "rollback",
            ],
            "intent": "action",
            "boost": 0.25,
        },
        "debugging": {
            "patterns": [
                "error", "exception", "bug", "crash",
                "timeout", "memory leak", "stack trace",
                "logs", "debug", "trace", "investigate",
            ],
            "intent": "reasoning",
            "boost": 0.20,
        },
    })


def _create_customer_service_vocabulary() -> CustomVocabulary:
    """
    Vocabulary for customer service/support queries.

    Handles common customer request patterns.
    """
    return VocabularyLoader.from_dict({
        "order_actions": {
            "patterns": [
                "order", "cancel", "refund", "return",
                "exchange", "tracking", "shipment", "delivery",
                "payment", "invoice", "receipt", "billing",
            ],
            "intent": "action",
            "boost": 0.30,
        },
        "account_actions": {
            "patterns": [
                "account", "password", "login", "signup",
                "subscription", "plan", "upgrade", "downgrade",
                "cancel subscription", "billing", "charge",
            ],
            "intent": "action",
            "boost": 0.25,
        },
        "inquiry": {
            "patterns": [
                "how do i", "can i", "what is", "where is",
                "status", "check", "find", "locate",
            ],
            "intent": "reasoning",
            "boost": 0.15,
        },
    })


def _create_creative_writing_vocabulary() -> CustomVocabulary:
    """
    Vocabulary for creative writing assistance.

    Boosts confidence for creative requests.
    """
    return VocabularyLoader.from_dict({
        "writing_types": {
            "patterns": [
                "poem", "poetry", "haiku", "sonnet", "limerick",
                "story", "short story", "novel", "fiction",
                "essay", "article", "blog", "script", "screenplay",
                "lyrics", "song", "jingle", "slogan",
            ],
            "intent": "creative",
            "boost": 0.30,
        },
        "creative_verbs": {
            "patterns": [
                "write", "compose", "draft", "create",
                "imagine", "invent", "brainstorm", "ideate",
                "describe", "depict", "illustrate", "portray",
            ],
            "intent": "creative",
            "boost": 0.25,
        },
        "style_modifiers": {
            "patterns": [
                "funny", "humorous", "serious", "dramatic",
                "romantic", "scary", "mysterious", "inspiring",
                "professional", "casual", "formal", "witty",
            ],
            "intent": "creative",
            "boost": 0.15,
        },
    })


# Pre-built vocabulary instances
RELATIONSHIP_VOCABULARY = _create_relationship_vocabulary()
TECH_SUPPORT_VOCABULARY = _create_tech_support_vocabulary()
CUSTOMER_SERVICE_VOCABULARY = _create_customer_service_vocabulary()
CREATIVE_WRITING_VOCABULARY = _create_creative_writing_vocabulary()


# =============================================================================
# Vocabulary Builder
# =============================================================================

def create_custom_vocabulary(
    domain_terms: list,
    intent: str = "general",
    boost: float = 0.25,
    name: str = "custom",
) -> CustomVocabulary:
    """
    Create a simple custom vocabulary.

    Args:
        domain_terms: List of domain-specific terms
        intent: Intent to boost (action, reasoning, relationship, creative, etc.)
        boost: Confidence boost (0.0 to 0.5 recommended)
        name: Name for this vocabulary group

    Returns:
        CustomVocabulary instance

    Example:
        vocab = create_custom_vocabulary(
            domain_terms=["JIRA", "Confluence", "sprint", "backlog"],
            intent="action",
            boost=0.25,
            name="agile_terms",
        )
    """
    return VocabularyLoader.from_dict({
        name: {
            "patterns": domain_terms,
            "intent": intent,
            "boost": boost,
        }
    })


def merge_vocabularies(*vocabularies: CustomVocabulary) -> CustomVocabulary:
    """
    Merge multiple vocabularies into one.

    Args:
        *vocabularies: Vocabularies to merge

    Returns:
        Merged CustomVocabulary

    Example:
        combined = merge_vocabularies(
            RELATIONSHIP_VOCABULARY,
            TECH_SUPPORT_VOCABULARY,
        )
    """
    merged_terms = {}
    for vocab in vocabularies:
        for pattern, config in vocab.terms.items():
            if pattern not in merged_terms:
                merged_terms[pattern] = config
            else:
                # Take higher boost if duplicate
                if config.boost > merged_terms[pattern].boost:
                    merged_terms[pattern] = config

    return CustomVocabulary(terms=merged_terms)


__all__ = [
    # Pre-built vocabularies
    "RELATIONSHIP_VOCABULARY",
    "TECH_SUPPORT_VOCABULARY",
    "CUSTOMER_SERVICE_VOCABULARY",
    "CREATIVE_WRITING_VOCABULARY",
    # Builders
    "create_custom_vocabulary",
    "merge_vocabularies",
]
