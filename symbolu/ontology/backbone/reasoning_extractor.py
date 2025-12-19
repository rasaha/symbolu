"""
Reasoning Extractor
===================

Extracts reasoning patterns, causal chains, and insights from content
to create ExperientialObjects.

This is a rule-based extractor that identifies:
- Causal relationships (A causes B)
- Sequences and processes
- Patterns (cycles, escalations, transformations)
- Key insights and transferable principles
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import re

from .experiential import (
    ExperientialObject,
    PatternType,
    ReasoningStrength,
    CausalChain,
    ApplicabilityCondition,
    create_experiential,
)
from .encoder import DimensionalVector, Dimension, encode_10d


@dataclass
class ExtractedPattern:
    """A pattern extracted from content."""
    pattern_type: PatternType
    pattern_name: str
    evidence: List[str]
    confidence: ReasoningStrength


@dataclass
class ExtractedCausalChain:
    """A causal chain extracted from content."""
    steps: List[str]
    connectors: List[str]  # Words linking steps (caused, led to, etc.)
    confidence: ReasoningStrength


@dataclass
class ExtractionResult:
    """Complete extraction result from content."""
    patterns: List[ExtractedPattern]
    causal_chains: List[ExtractedCausalChain]
    key_entities: List[str]
    key_actions: List[str]
    suggested_insight: str
    suggested_transferable: List[str]


# =============================================================================
# Pattern Detection
# =============================================================================

# Causal connectors
CAUSAL_PATTERNS = re.compile(
    r'\b(because|caused|led to|resulted in|therefore|thus|hence|'
    r'consequently|as a result|due to|owing to|effect of|'
    r'triggered|sparked|initiated|produced|created|generated)\b',
    re.IGNORECASE
)

# Sequence markers
SEQUENCE_PATTERNS = re.compile(
    r'\b(first|then|next|after|before|finally|subsequently|'
    r'followed by|preceded by|later|earlier|began|ended|'
    r'step \d|phase \d|stage \d)\b',
    re.IGNORECASE
)

# Transformation markers
TRANSFORMATION_PATTERNS = re.compile(
    r'\b(became|transformed|evolved|changed into|turned into|'
    r'developed into|grew into|morphed|converted|shifted to|'
    r'transition|metamorphosis)\b',
    re.IGNORECASE
)

# Bifurcation/split markers
BIFURCATION_PATTERNS = re.compile(
    r'\b(split|divided|separated|bifurcated|branched|'
    r'broke apart|fell apart|diverged|fractured|'
    r'north.+south|two.+sides|opposing)\b',
    re.IGNORECASE
)

# Convergence/merge markers
CONVERGENCE_PATTERNS = re.compile(
    r'\b(merged|united|combined|converged|joined|'
    r'came together|unified|consolidated|integrated|'
    r'fusion|synthesis|union)\b',
    re.IGNORECASE
)

# Cycle markers
CYCLE_PATTERNS = re.compile(
    r'\b(cycle|cyclical|recurring|repeated|periodic|'
    r'boom.+bust|rise.+fall|ebb.+flow|'
    r'again and again|pattern repeats)\b',
    re.IGNORECASE
)

# Escalation markers
ESCALATION_PATTERNS = re.compile(
    r'\b(escalat|intensif|amplif|increas|grew|'
    r'more and more|increasingly|mounting|'
    r'spiral|snowball|compound)\b',
    re.IGNORECASE
)

# Threshold/tipping point markers
THRESHOLD_PATTERNS = re.compile(
    r'\b(threshold|tipping point|breaking point|'
    r'critical mass|point of no return|'
    r'finally|suddenly|at last|reached)\b',
    re.IGNORECASE
)

# Domain transfer indicators
DOMAIN_INDICATORS = {
    "politics": re.compile(r'\b(government|political|congress|parliament|vote|election|law|policy)\b', re.I),
    "economics": re.compile(r'\b(market|economy|financial|price|cost|trade|business|profit)\b', re.I),
    "family": re.compile(r'\b(family|parent|child|sibling|marriage|divorce|household)\b', re.I),
    "organization": re.compile(r'\b(company|organization|team|department|management|employee)\b', re.I),
    "biology": re.compile(r'\b(cell|organism|species|evolution|genetic|biological)\b', re.I),
    "psychology": re.compile(r'\b(mind|behavior|emotion|cognitive|mental|psychological)\b', re.I),
    "technology": re.compile(r'\b(technology|software|system|computer|digital|algorithm)\b', re.I),
    "nature": re.compile(r'\b(nature|environment|climate|ecosystem|weather|natural)\b', re.I),
}


def detect_patterns(text: str) -> List[ExtractedPattern]:
    """Detect reasoning patterns in text."""
    patterns = []

    # Check each pattern type
    pattern_checks = [
        (CAUSAL_PATTERNS, PatternType.CAUSAL, "causal_relationship"),
        (TRANSFORMATION_PATTERNS, PatternType.TRANSFORMATION, "transformation"),
        (BIFURCATION_PATTERNS, PatternType.BIFURCATION, "bifurcation"),
        (CONVERGENCE_PATTERNS, PatternType.CONVERGENCE, "convergence"),
        (CYCLE_PATTERNS, PatternType.CYCLICAL, "cyclical_pattern"),
        (ESCALATION_PATTERNS, PatternType.ESCALATION, "escalation"),
        (THRESHOLD_PATTERNS, PatternType.THRESHOLD, "threshold_crossing"),
    ]

    for pattern, ptype, name in pattern_checks:
        matches = pattern.findall(text)
        if matches:
            confidence = ReasoningStrength.STRONG if len(matches) >= 3 else \
                         ReasoningStrength.MODERATE if len(matches) >= 1 else \
                         ReasoningStrength.WEAK
            patterns.append(ExtractedPattern(
                pattern_type=ptype,
                pattern_name=name,
                evidence=matches[:5],
                confidence=confidence,
            ))

    return patterns


def extract_causal_chains(text: str) -> List[ExtractedCausalChain]:
    """Extract causal chains from text."""
    chains = []

    # Look for explicit causal statements
    # Pattern: X (caused/led to/resulted in) Y
    causal_regex = re.compile(
        r'([A-Z][^.]*?)\s+(caused|led to|resulted in|triggered|produced)\s+([^.]+)',
        re.IGNORECASE
    )

    for match in causal_regex.finditer(text):
        cause = match.group(1).strip()
        connector = match.group(2).strip()
        effect = match.group(3).strip()

        # Clean up
        cause = re.sub(r'^(the|a|an)\s+', '', cause, flags=re.I)
        effect = re.sub(r'^(the|a|an)\s+', '', effect, flags=re.I)

        if len(cause) > 5 and len(effect) > 5:
            chains.append(ExtractedCausalChain(
                steps=[cause[:50], effect[:50]],
                connectors=[connector],
                confidence=ReasoningStrength.MODERATE,
            ))

    # Look for sequence chains
    # Pattern: First X, then Y, finally Z
    sequence_parts = re.split(r'\b(first|then|next|finally|after that)\b', text, flags=re.I)
    if len(sequence_parts) >= 5:  # At least 2 sequence markers
        steps = []
        for i, part in enumerate(sequence_parts):
            if part.lower() not in ['first', 'then', 'next', 'finally', 'after that']:
                clean = part.strip(' ,.')
                if len(clean) > 10:
                    steps.append(clean[:50])

        if len(steps) >= 2:
            chains.append(ExtractedCausalChain(
                steps=steps[:5],
                connectors=["sequence"],
                confidence=ReasoningStrength.MODERATE,
            ))

    return chains


def extract_key_entities(text: str) -> List[str]:
    """Extract key entities (proper nouns, important terms)."""
    entities = []

    # Proper nouns (capitalized words not at sentence start)
    proper_nouns = re.findall(r'(?<=[.!?]\s)[A-Z][a-z]+|(?<=\s)[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', text)
    entities.extend(proper_nouns[:10])

    # Quoted terms
    quoted = re.findall(r'"([^"]+)"', text)
    entities.extend(quoted[:5])

    return list(set(entities))


def extract_key_actions(text: str) -> List[str]:
    """Extract key actions/verbs."""
    actions = []

    # Strong action verbs
    action_pattern = re.compile(
        r'\b(attack|defend|create|destroy|build|collapse|'
        r'rise|fall|grow|decline|fight|win|lose|'
        r'transform|change|evolve|divide|unite)\b',
        re.IGNORECASE
    )

    matches = action_pattern.findall(text)
    return list(set(matches))[:10]


def suggest_transferable_domains(text: str, source_domain: str) -> List[str]:
    """Suggest domains this reasoning could transfer to."""
    transferable = []

    for domain, pattern in DOMAIN_INDICATORS.items():
        if domain != source_domain:
            # Check if the pattern TYPE would apply
            if pattern.search(text):
                transferable.append(domain)

    # Add generic transferable domains based on pattern type
    patterns = detect_patterns(text)
    for p in patterns:
        if p.pattern_type == PatternType.BIFURCATION:
            transferable.extend(["politics", "family", "organization"])
        elif p.pattern_type == PatternType.ESCALATION:
            transferable.extend(["economics", "psychology", "nature"])
        elif p.pattern_type == PatternType.CYCLICAL:
            transferable.extend(["economics", "nature", "psychology"])
        elif p.pattern_type == PatternType.TRANSFORMATION:
            transferable.extend(["biology", "psychology", "technology"])

    return list(set(transferable))[:5]


def generate_insight(text: str, patterns: List[ExtractedPattern], chains: List[ExtractedCausalChain]) -> str:
    """Generate an insight statement from extracted patterns."""
    if not patterns and not chains:
        return "General observation without clear causal pattern"

    parts = []

    # Use strongest pattern
    if patterns:
        strongest = max(patterns, key=lambda p:
            2 if p.confidence == ReasoningStrength.STRONG else
            1 if p.confidence == ReasoningStrength.MODERATE else 0)

        pattern_insights = {
            PatternType.CAUSAL: "demonstrates cause-and-effect relationship",
            PatternType.TRANSFORMATION: "shows transformation from one state to another",
            PatternType.BIFURCATION: "illustrates how systems split under pressure",
            PatternType.CONVERGENCE: "shows how separate elements can unite",
            PatternType.CYCLICAL: "reveals recurring cyclical pattern",
            PatternType.ESCALATION: "demonstrates escalating/intensifying dynamics",
            PatternType.THRESHOLD: "shows threshold effect with sudden change",
        }
        parts.append(pattern_insights.get(strongest.pattern_type, "shows structural pattern"))

    # Add causal chain insight
    if chains:
        chain = chains[0]
        if len(chain.steps) >= 2:
            parts.append(f"progression from '{chain.steps[0][:30]}' to '{chain.steps[-1][:30]}'")

    return "This " + " and ".join(parts) if parts else "Pattern detected"


# =============================================================================
# Main Extraction Function
# =============================================================================

def extract_reasoning(text: str, domain: str = "unknown") -> ExtractionResult:
    """
    Extract all reasoning components from text.

    Args:
        text: Content to analyze
        domain: Source domain of content

    Returns:
        ExtractionResult with patterns, chains, entities, and suggestions
    """
    patterns = detect_patterns(text)
    chains = extract_causal_chains(text)
    entities = extract_key_entities(text)
    actions = extract_key_actions(text)
    insight = generate_insight(text, patterns, chains)
    transferable = suggest_transferable_domains(text, domain)

    return ExtractionResult(
        patterns=patterns,
        causal_chains=chains,
        key_entities=entities,
        key_actions=actions,
        suggested_insight=insight,
        suggested_transferable=transferable,
    )


def extract_and_create_experiential(
    content: str,
    domain: str,
    reference: Optional[str] = None,
    custom_insight: Optional[str] = None,
    custom_tags: Optional[List[str]] = None,
) -> ExperientialObject:
    """
    Extract reasoning and create an ExperientialObject.

    Convenience function that combines extraction and creation.

    Args:
        content: Source content
        domain: Source domain
        reference: Optional reference ID
        custom_insight: Override auto-generated insight
        custom_tags: Additional tags

    Returns:
        ExperientialObject ready for storage
    """
    result = extract_reasoning(content, domain)

    # Determine pattern name
    pattern_name = "general_observation"
    if result.patterns:
        pattern_name = result.patterns[0].pattern_name

    # Get causal steps
    causal_steps = None
    if result.causal_chains:
        causal_steps = result.causal_chains[0].steps

    # Build tags
    tags = list(custom_tags) if custom_tags else []
    tags.extend(result.key_actions[:3])

    return create_experiential(
        content=content,
        domain=domain,
        pattern_name=pattern_name,
        insight=custom_insight or result.suggested_insight,
        causal_steps=causal_steps,
        transferable_to=result.suggested_transferable,
        tags=tags,
        reference=reference,
    )
