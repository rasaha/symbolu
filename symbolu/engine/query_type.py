"""
Query Type Classifier
=====================

Classifies queries as either PROBLEM (seeking solutions) or INFORMATION (seeking knowledge).

Cross-domain reasoning is only valuable for PROBLEM queries where patterns from
other domains can provide insight. For INFORMATION queries, cross-domain adds
noise without value.

Examples:
    PROBLEM:
        - "My startup co-founders disagree on direction"
        - "How do I handle family conflict?"
        - "What should I do about market volatility?"
        - "I'm struggling with team communication"

    INFORMATION:
        - "What is quantum entanglement?"
        - "How do cells divide?"
        - "Explain the theory of relativity"
        - "What causes market crashes?"

Usage:
    from symbolu.engine.query_type import classify_query_type, QueryType

    query_type = classify_query_type("My co-founders disagree")
    if query_type == QueryType.PROBLEM:
        # Enable cross-domain reasoning
        ...
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Set
import re


class QueryType(Enum):
    """Type of query based on user intent."""
    PROBLEM = "problem"        # User has a problem, seeking solutions
    INFORMATION = "information"  # User wants knowledge, seeking facts


@dataclass
class QueryTypeResult:
    """Result of query type classification."""
    query_type: QueryType
    confidence: float
    indicators_found: Tuple[str, ...]
    reason: str


# Problem indicators - patterns that suggest user is seeking solutions
PROBLEM_STARTERS = {
    "my ",
    "i have ",
    "i'm ",
    "im ",
    "we have ",
    "our ",
    "i need to ",
    "i want to ",
    "how do i ",
    "how can i ",
    "how should i ",
    "what should i ",
    "what do i ",
    "help me ",
    "i'm struggling ",
    "i'm dealing ",
    "i'm facing ",
}

PROBLEM_KEYWORDS = {
    "problem",
    "issue",
    "challenge",
    "struggle",
    "conflict",
    "disagree",
    "disagreement",
    "failing",
    "failed",
    "broken",
    "stuck",
    "help",
    "solve",
    "fix",
    "handle",
    "deal with",
    "cope",
    "overcome",
    "trouble",
    "difficult",
    "difficulty",
    "worried",
    "anxious",
    "stressed",
    "frustrated",
    "confused",
}

PROBLEM_PATTERNS = [
    r"what (should|can|do) (i|we) do",
    r"how (do|can|should) (i|we) (deal|cope|handle|fix|solve|manage)",
    r"(my|our) .+ (is|are) (not|failing|broken|struggling)",
    r"i('m| am) (having|facing|dealing|struggling)",
    r"need (help|advice|guidance|suggestions?)",
]

# Information indicators - patterns that suggest user wants knowledge
INFORMATION_STARTERS = {
    "what is ",
    "what are ",
    "what was ",
    "what were ",
    "how does ",
    "how do ",  # Without "I" following
    "how did ",
    "why does ",
    "why do ",
    "why did ",
    "why is ",
    "why are ",
    "explain ",
    "describe ",
    "define ",
    "tell me about ",
    "tell me what ",
    "what causes ",
    "what caused ",
    "who is ",
    "who was ",
    "when did ",
    "where is ",
    "where did ",
}

INFORMATION_KEYWORDS = {
    "definition",
    "meaning",
    "concept",
    "theory",
    "principle",
    "history",
    "origin",
    "explanation",
    "describe",
    "overview",
    "introduction",
    "basics",
    "fundamentals",
}

INFORMATION_PATTERNS = [
    r"^(what|how|why|when|where|who) (is|are|was|were|does|do|did) ",
    r"explain .+ (to me|please)?$",
    r"(tell|teach) me (about|what|how|why)",
    r"what (is|are) the .+ of",
    r"how (does|do) .+ work",
]


def classify_query_type(query: str) -> QueryTypeResult:
    """
    Classify a query as PROBLEM or INFORMATION.

    This enables gating cross-domain reasoning to only activate for
    problem-solving queries where cross-domain patterns add value.

    Args:
        query: Input query text

    Returns:
        QueryTypeResult with type, confidence, and reasoning
    """
    query_lower = query.lower().strip()
    indicators_found = []

    problem_score = 0.0
    info_score = 0.0

    # Check problem starters
    for starter in PROBLEM_STARTERS:
        if query_lower.startswith(starter):
            problem_score += 0.4
            indicators_found.append(f"starter:{starter.strip()}")
            break

    # Check information starters
    for starter in INFORMATION_STARTERS:
        if query_lower.startswith(starter):
            info_score += 0.4
            indicators_found.append(f"starter:{starter.strip()}")
            break

    # Check problem keywords
    for keyword in PROBLEM_KEYWORDS:
        if keyword in query_lower:
            problem_score += 0.15
            indicators_found.append(f"keyword:{keyword}")
            if problem_score >= 0.8:
                break

    # Check information keywords
    for keyword in INFORMATION_KEYWORDS:
        if keyword in query_lower:
            info_score += 0.15
            indicators_found.append(f"keyword:{keyword}")
            if info_score >= 0.8:
                break

    # Check problem patterns (regex)
    for pattern in PROBLEM_PATTERNS:
        if re.search(pattern, query_lower):
            problem_score += 0.3
            indicators_found.append(f"pattern:problem")
            break

    # Check information patterns (regex)
    for pattern in INFORMATION_PATTERNS:
        if re.search(pattern, query_lower):
            info_score += 0.3
            indicators_found.append(f"pattern:information")
            break

    # Determine type based on scores
    if problem_score > info_score:
        query_type = QueryType.PROBLEM
        confidence = min(1.0, problem_score)
        reason = f"Problem indicators ({problem_score:.2f}) > Information ({info_score:.2f})"
    elif info_score > problem_score:
        query_type = QueryType.INFORMATION
        confidence = min(1.0, info_score)
        reason = f"Information indicators ({info_score:.2f}) > Problem ({problem_score:.2f})"
    else:
        # Default to INFORMATION when ambiguous (safer - don't add cross-domain noise)
        query_type = QueryType.INFORMATION
        confidence = 0.5
        reason = "Ambiguous - defaulting to information (scores tied)"

    return QueryTypeResult(
        query_type=query_type,
        confidence=confidence,
        indicators_found=tuple(indicators_found),
        reason=reason,
    )


def is_problem_query(query: str, min_confidence: float = 0.3) -> bool:
    """
    Quick check if a query is a problem-seeking query.

    Args:
        query: Input query text
        min_confidence: Minimum confidence to consider as problem

    Returns:
        True if query is classified as PROBLEM with sufficient confidence
    """
    result = classify_query_type(query)
    return result.query_type == QueryType.PROBLEM and result.confidence >= min_confidence
