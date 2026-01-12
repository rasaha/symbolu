"""
Knowledge Harvester for Master Chat
====================================

Extracts knowledge nuggets from conversation turns and classifies
them into appropriate buckets based on ontological signals.

The harvester runs after each turn to:
1. Extract factual statements, preferences, and decisions
2. Classify extractions by bucket category
3. Compute importance scores
4. Store in appropriate buckets with embeddings

Harvesting is deterministic and rule-based (no LLM in the core loop),
with optional LLM enhancement for complex extractions.

Version: 1.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from uuid import uuid4

from .bucket_models import (
    Bucket,
    BucketCategory,
    BucketEntry,
    MessageSignals,
    LAYER_TO_BUCKET,
)

# =============================================================================
# Salience Scoring (Vritti vs Samskara Distinction)
# =============================================================================

# Linguistic markers for permanence vs temporariness
STRONG_MARKERS = re.compile(
    r"\b(always|never|every|prefer|hate|love|need|must|"
    r"is defined as|rule is|principle is|i am a|my name is|"
    r"decided|chose|learned|discovered|realized)\b",
    re.IGNORECASE,
)

WEAK_MARKERS = re.compile(
    r"\b(maybe|perhaps|guess|might|could|possibly|sometimes|"
    r"feeling like|think maybe|not sure|wondering|suppose)\b",
    re.IGNORECASE,
)


def calculate_salience(
    text: str,
    signals: Optional[MessageSignals] = None,
    is_novel: bool = True,
) -> float:
    """
    Calculate heuristic salience score for extracted content.

    Uses linguistic markers and ontological signals to determine
    if content is a permanent "Samskara" (worth storing) vs a
    temporary "Vritti" (conversational noise).

    Args:
        text: The extracted content text
        signals: Optional ontological signals for the turn
        is_novel: Whether this is unlike existing bucket entries

    Returns:
        Salience score [0.0, 1.0] - higher = more permanent/important
    """
    score = 0.5  # Base score

    # 1. Linguistic markers (±0.25)
    strong_matches = len(STRONG_MARKERS.findall(text))
    weak_matches = len(WEAK_MARKERS.findall(text))

    if strong_matches > 0:
        score += min(0.25, strong_matches * 0.1)
    if weak_matches > 0:
        score -= min(0.25, weak_matches * 0.1)

    # 2. Signal intensity - biological encoding strength (±0.2)
    # High Sattva (clarity) or Rajas (activity) = stronger encoding
    # Tamas (inertia) = weaker encoding
    if signals and signals.guna_distribution:
        sattva = signals.guna_distribution.get("sattva", 0.0)
        rajas = signals.guna_distribution.get("rajas", 0.0)
        tamas = signals.guna_distribution.get("tamas", 0.0)

        # Clarity and activity enhance memory encoding
        intensity = (sattva * 0.6 + rajas * 0.4) - (tamas * 0.2)
        score += intensity * 0.2

    # 3. Novelty boost (+0.15)
    # New/unique information is more valuable
    if is_novel:
        score += 0.15

    # 4. Content length heuristic (±0.1)
    # Very short or very long content is less reliable
    word_count = len(text.split())
    if 5 <= word_count <= 50:
        score += 0.05  # Good length
    elif word_count < 3 or word_count > 100:
        score -= 0.1  # Too short or too long

    # 5. Entity presence boost (+0.1)
    # Content with named entities is more specific/valuable
    if re.search(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', text):
        score += 0.05

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, score))


# =============================================================================
# Extraction Patterns (Rule-Based)
# =============================================================================

@dataclass
class ExtractionPattern:
    """
    Rule-based pattern for extracting knowledge from text.

    Attributes:
        name: Pattern identifier
        pattern: Compiled regex pattern
        bucket_hint: Suggested bucket category
        importance_modifier: Adjustment to base importance score
        entity_groups: Regex groups that contain entities
    """
    name: str
    pattern: re.Pattern
    bucket_hint: BucketCategory
    importance_modifier: float = 0.0
    entity_groups: Tuple[int, ...] = ()


# Preference patterns
PREFERENCE_PATTERNS = [
    ExtractionPattern(
        name="explicit_preference",
        pattern=re.compile(
            r"(?:i|I)\s+(?:prefer|like|love|enjoy|want|need)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.PREFERENCES,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="explicit_dislike",
        pattern=re.compile(
            r"(?:i|I)\s+(?:don't like|hate|dislike|avoid|can't stand)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.PREFERENCES,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="style_preference",
        pattern=re.compile(
            r"(?:i|I)\s+(?:usually|always|typically|tend to)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.PREFERENCES,
        importance_modifier=0.05,
        entity_groups=(1,),
    ),
]

# Self/Identity patterns
IDENTITY_PATTERNS = [
    ExtractionPattern(
        name="self_identity",
        pattern=re.compile(
            r"(?:i|I)\s+am\s+(?:a|an)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SELF,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="work_identity",
        pattern=re.compile(
            r"(?:i|I)\s+work\s+(?:at|for|as|in)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SELF,
        importance_modifier=0.2,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="personal_fact",
        pattern=re.compile(
            r"(?:my|My)\s+(name|age|job|role|title|company|team)\s+is\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SELF,
        importance_modifier=0.25,
        entity_groups=(2,),
    ),
]

# Action/Task patterns
ACTION_PATTERNS = [
    ExtractionPattern(
        name="task_statement",
        pattern=re.compile(
            r"(?:i|I)\s+(?:need to|have to|must|should|will)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.ACTIONS,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="planning",
        pattern=re.compile(
            r"(?:i'm|I'm|I am)\s+(?:going to|planning to|working on)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.ACTIONS,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
]

# Decision patterns
DECISION_PATTERNS = [
    ExtractionPattern(
        name="explicit_decision",
        pattern=re.compile(
            r"(?:i|I)\s+(?:decided|chose|picked|selected|went with)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.DECISIONS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="choice_rationale",
        pattern=re.compile(
            r"(?:i|I)\s+(?:chose|picked)\s+(.+?)\s+because\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.DECISIONS,
        importance_modifier=0.2,
        entity_groups=(1, 2),
    ),
]

# Learning patterns
LEARNING_PATTERNS = [
    ExtractionPattern(
        name="learned_fact",
        pattern=re.compile(
            r"(?:i|I)\s+(?:learned|discovered|found out|realized)\s+(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.LEARNING,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="understanding",
        pattern=re.compile(
            r"(?:i|I)\s+(?:understand|know|figured out)\s+(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.LEARNING,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
]

# Goal/Aspiration patterns
ASPIRATION_PATTERNS = [
    ExtractionPattern(
        name="goal_statement",
        pattern=re.compile(
            r"(?:my|My)\s+goal\s+is\s+(?:to\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.ASPIRATIONS,
        importance_modifier=0.2,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="aspiration",
        pattern=re.compile(
            r"(?:i|I)\s+(?:want to|hope to|dream of|aspire to)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.ASPIRATIONS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
]

# Relationship patterns
RELATIONSHIP_PATTERNS = [
    ExtractionPattern(
        name="person_reference",
        pattern=re.compile(
            r"(?:my|My)\s+(wife|husband|partner|friend|colleague|boss|manager|mentor|team)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.RELATIONSHIPS,
        importance_modifier=0.15,
        entity_groups=(1, 2),
    ),
    ExtractionPattern(
        name="works_with",
        pattern=re.compile(
            r"(?:i|I)\s+(?:work with|collaborate with|report to)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.RELATIONSHIPS,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
]

# Project patterns
PROJECT_PATTERNS = [
    ExtractionPattern(
        name="project_mention",
        pattern=re.compile(
            r"(?:the|my|our)\s+(.+?)\s+project\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.PROJECTS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="building",
        pattern=re.compile(
            r"(?:i'm|I'm|we're|We're)\s+building\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.PROJECTS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
]

# Emotion patterns
EMOTION_PATTERNS = [
    ExtractionPattern(
        name="feeling_state",
        pattern=re.compile(
            r"(?:i|I)\s+(?:feel|am feeling|'m feeling)\s+(happy|sad|frustrated|excited|worried|anxious|stressed|confident|confused)(?:\s+about\s+(.+?))?(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.EMOTIONS,
        importance_modifier=0.1,
        entity_groups=(1, 2),
    ),
    ExtractionPattern(
        name="emotional_reaction",
        pattern=re.compile(
            r"(?:that|this|it)\s+(?:makes me|made me)\s+(happy|sad|angry|frustrated|excited|nervous|anxious|relieved|proud|disappointed)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.EMOTIONS,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="concern_expression",
        pattern=re.compile(
            r"(?:i'm|I'm|I am)\s+(?:worried|concerned|nervous|anxious)\s+(?:about|that)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.EMOTIONS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
]

# Values/Beliefs patterns
VALUES_PATTERNS = [
    ExtractionPattern(
        name="belief_statement",
        pattern=re.compile(
            r"(?:i|I)\s+(?:believe|think|feel)\s+(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.VALUES,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="importance_statement",
        pattern=re.compile(
            r"(?:it's|It's|it is|It is)\s+(?:important|crucial|essential|vital)\s+(?:to me\s+)?(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.VALUES,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="value_expression",
        pattern=re.compile(
            r"(?:i|I)\s+(?:value|prioritize|care about|appreciate)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.VALUES,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="principle_statement",
        pattern=re.compile(
            r"(?:my|My)\s+(?:philosophy|principle|approach|belief)\s+is\s+(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.VALUES,
        importance_modifier=0.2,
        entity_groups=(1,),
    ),
]

# Technical/Skills patterns
SKILLS_PATTERNS = [
    ExtractionPattern(
        name="skill_statement",
        pattern=re.compile(
            r"(?:i|I)\s+(?:know|use|work with|am familiar with|have experience with)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.LEARNING,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="expertise_claim",
        pattern=re.compile(
            r"(?:i'm|I'm|I am)\s+(?:good at|experienced in|skilled at|proficient in|an expert in)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SELF,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="tool_usage",
        pattern=re.compile(
            r"(?:i|I|we|We)\s+(?:use|are using|have been using)\s+(.+?)\s+(?:for|to)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SYSTEMS,
        importance_modifier=0.1,
        entity_groups=(1, 2),
    ),
    ExtractionPattern(
        name="tech_stack",
        pattern=re.compile(
            r"(?:our|my|the)\s+(?:tech stack|stack|tooling|infrastructure)\s+(?:includes|uses|is)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SYSTEMS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
]

# Analysis/Reasoning patterns
ANALYSIS_PATTERNS = [
    ExtractionPattern(
        name="comparison",
        pattern=re.compile(
            r"(.+?)\s+is\s+(?:better|worse|faster|slower|cheaper|more expensive)\s+than\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.ANALYSIS,
        importance_modifier=0.1,
        entity_groups=(1, 2),
    ),
    ExtractionPattern(
        name="tradeoff_analysis",
        pattern=re.compile(
            r"(?:the|The)\s+(?:tradeoff|trade-off|downside|upside|advantage|disadvantage)\s+(?:is|of)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.ANALYSIS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="evaluation",
        pattern=re.compile(
            r"(?:i|I)\s+(?:think|found|evaluated|assessed|concluded)\s+(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.ANALYSIS,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="pros_cons",
        pattern=re.compile(
            r"(?:the|The)\s+(?:pros|cons|benefits|drawbacks)\s+(?:are|include)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.ANALYSIS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
]

# Systems/Process patterns
SYSTEMS_PATTERNS = [
    ExtractionPattern(
        name="process_description",
        pattern=re.compile(
            r"(?:our|my|the)\s+(?:process|workflow|procedure|approach)\s+(?:is|involves)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SYSTEMS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="team_structure",
        pattern=re.compile(
            r"(?:our|my|the)\s+team\s+(?:is|has|includes|consists of)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SYSTEMS,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="organization_fact",
        pattern=re.compile(
            r"(?:at|in)\s+(?:my|our)\s+(?:company|organization|team|department)\s*,?\s+(?:we|they)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SYSTEMS,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
]

# Temporal/Deadline patterns
TEMPORAL_PATTERNS = [
    ExtractionPattern(
        name="deadline",
        pattern=re.compile(
            r"(?:the|my|our)\s+deadline\s+(?:is|for)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.TEMPORAL,
        importance_modifier=0.2,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="time_constraint",
        pattern=re.compile(
            r"(?:i|I|we|We)\s+(?:need to|have to|must)\s+(?:finish|complete|deliver)\s+(?:by|before)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.TEMPORAL,
        importance_modifier=0.2,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="schedule_mention",
        pattern=re.compile(
            r"(?:on|this|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month|year)\s+(?:i|I|we|We)\s+(?:will|are going to|plan to)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.TEMPORAL,
        importance_modifier=0.15,
        entity_groups=(1, 2),
    ),
    ExtractionPattern(
        name="recurring_schedule",
        pattern=re.compile(
            r"(?:every|each)\s+(day|week|month|monday|tuesday|wednesday|thursday|friday)\s+(?:i|I|we|We)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.TEMPORAL,
        importance_modifier=0.1,
        entity_groups=(1, 2),
    ),
]

# Closure/Completion patterns
CLOSURE_PATTERNS = [
    ExtractionPattern(
        name="completion",
        pattern=re.compile(
            r"(?:i|I|we|We)\s+(?:finished|completed|done with|wrapped up)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.CLOSURE,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="resolution",
        pattern=re.compile(
            r"(?:the|that|this)\s+(?:issue|problem|bug|question)\s+(?:was|is|has been)\s+(?:resolved|fixed|answered|solved)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.CLOSURE,
        importance_modifier=0.1,
        entity_groups=(),
    ),
    ExtractionPattern(
        name="no_longer",
        pattern=re.compile(
            r"(?:i|I|we|We)\s+(?:no longer|don't|stopped|quit)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.CLOSURE,
        importance_modifier=0.1,
        entity_groups=(1,),
    ),
]

# Synthesis/Pattern patterns
SYNTHESIS_PATTERNS = [
    ExtractionPattern(
        name="pattern_recognition",
        pattern=re.compile(
            r"(?:i|I)\s+(?:noticed|see|observe)\s+(?:a\s+)?(?:pattern|trend|connection)\s+(?:that|where|in)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SYNTHESIS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="insight",
        pattern=re.compile(
            r"(?:the|The)\s+(?:key|main|important)\s+(?:insight|takeaway|lesson)\s+(?:is|was)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SYNTHESIS,
        importance_modifier=0.2,
        entity_groups=(1,),
    ),
    ExtractionPattern(
        name="connection",
        pattern=re.compile(
            r"(.+?)\s+(?:is connected to|relates to|is similar to|reminds me of)\s+(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.SYNTHESIS,
        importance_modifier=0.1,
        entity_groups=(1, 2),
    ),
]

# Extended relationship patterns
EXTENDED_RELATIONSHIP_PATTERNS = [
    ExtractionPattern(
        name="named_person",
        pattern=re.compile(
            r"(?:my|My)\s+(?:friend|colleague|coworker|partner|client|customer)\s+([A-Z][a-z]+)\s+(.+?)(?:\.|$)",
        ),
        bucket_hint=BucketCategory.RELATIONSHIPS,
        importance_modifier=0.2,
        entity_groups=(1, 2),
    ),
    ExtractionPattern(
        name="interaction",
        pattern=re.compile(
            r"(?:i|I)\s+(?:met with|talked to|spoke with|emailed|called|messaged)\s+(.+?)(?:\s+about\s+(.+?))?(?:\.|$)",
            re.IGNORECASE,
        ),
        bucket_hint=BucketCategory.RELATIONSHIPS,
        importance_modifier=0.1,
        entity_groups=(1, 2),
    ),
    ExtractionPattern(
        name="team_member",
        pattern=re.compile(
            r"([A-Z][a-z]+)\s+(?:is|was)\s+(?:on my team|my teammate|working with me|helping me)(?:\.|$)",
        ),
        bucket_hint=BucketCategory.RELATIONSHIPS,
        importance_modifier=0.15,
        entity_groups=(1,),
    ),
]

# All patterns grouped
ALL_PATTERNS: Dict[str, List[ExtractionPattern]] = {
    "preferences": PREFERENCE_PATTERNS,
    "identity": IDENTITY_PATTERNS,
    "actions": ACTION_PATTERNS,
    "decisions": DECISION_PATTERNS,
    "learning": LEARNING_PATTERNS,
    "aspirations": ASPIRATION_PATTERNS,
    "relationships": RELATIONSHIP_PATTERNS + EXTENDED_RELATIONSHIP_PATTERNS,
    "projects": PROJECT_PATTERNS,
    "emotions": EMOTION_PATTERNS,
    "values": VALUES_PATTERNS,
    "skills": SKILLS_PATTERNS,
    "analysis": ANALYSIS_PATTERNS,
    "systems": SYSTEMS_PATTERNS,
    "temporal": TEMPORAL_PATTERNS,
    "closure": CLOSURE_PATTERNS,
    "synthesis": SYNTHESIS_PATTERNS,
}


# =============================================================================
# Harvested Fact
# =============================================================================

@dataclass
class HarvestedFact:
    """
    A single fact extracted from conversation text.

    Attributes:
        content: The extracted content
        source_text: Original text this was extracted from
        pattern_name: Name of the pattern that matched
        bucket_hint: Suggested bucket category
        importance_score: Base importance [0.0, 1.0]
        entities: Extracted named entities
        confidence: Extraction confidence [0.0, 1.0]
    """
    content: str
    source_text: str
    pattern_name: str
    bucket_hint: BucketCategory
    importance_score: float = 0.5
    entities: List[str] = field(default_factory=list)
    confidence: float = 0.8


# =============================================================================
# Knowledge Harvester
# =============================================================================

class KnowledgeHarvester:
    """
    Extracts and classifies knowledge from conversation turns.

    Uses rule-based pattern matching for core extraction,
    with ontological signal analysis for classification refinement.
    """

    def __init__(
        self,
        min_content_length: int = 10,
        max_content_length: int = 500,
        min_confidence: float = 0.5,
    ):
        """
        Initialize the harvester.

        Args:
            min_content_length: Minimum characters for valid extraction
            max_content_length: Maximum characters before truncation
            min_confidence: Minimum confidence to keep extraction
        """
        self.min_content_length = min_content_length
        self.max_content_length = max_content_length
        self.min_confidence = min_confidence

        # Flatten patterns for iteration
        self.patterns: List[ExtractionPattern] = []
        for pattern_list in ALL_PATTERNS.values():
            self.patterns.extend(pattern_list)

    def harvest(
        self,
        text: str,
        signals: Optional[MessageSignals] = None,
        source_turn_id: Optional[str] = None,
        role: str = "user",
    ) -> List[HarvestedFact]:
        """
        Extract knowledge facts from text.

        Args:
            text: Text to harvest from
            signals: Optional ontological signals for classification
            source_turn_id: ID of the source conversation turn
            role: Message role ("user" or "assistant")

        Returns:
            List of HarvestedFact objects
        """
        if not text or len(text.strip()) < self.min_content_length:
            return []

        facts: List[HarvestedFact] = []

        # Apply all patterns
        for pattern in self.patterns:
            matches = pattern.pattern.finditer(text)

            for match in matches:
                # Extract content from match
                content = match.group(0).strip()

                # Extract entities from specified groups
                entities = []
                for group_idx in pattern.entity_groups:
                    try:
                        entity = match.group(group_idx)
                        if entity:
                            entities.append(entity.strip())
                    except IndexError:
                        pass

                # Validate content
                if len(content) < self.min_content_length:
                    continue
                if len(content) > self.max_content_length:
                    content = content[:self.max_content_length] + "..."

                # Compute importance using salience scoring
                salience = calculate_salience(content, signals, is_novel=True)
                importance = salience + pattern.importance_modifier

                # Boost importance for user messages (their own statements)
                if role == "user":
                    importance += 0.1

                importance = min(1.0, max(0.0, importance))

                # Create harvested fact
                fact = HarvestedFact(
                    content=content,
                    source_text=text[:200],  # Keep snippet of source
                    pattern_name=pattern.name,
                    bucket_hint=pattern.bucket_hint,
                    importance_score=importance,
                    entities=entities,
                    confidence=0.8,
                )

                facts.append(fact)

        # If we have signals, use them to refine classification
        if signals:
            facts = self._refine_with_signals(facts, signals)

        # Deduplicate similar facts
        facts = self._deduplicate_facts(facts)

        return facts

    def harvest_turn(
        self,
        user_message: str,
        assistant_response: str,
        signals: Optional[MessageSignals] = None,
        turn_id: Optional[str] = None,
    ) -> List[HarvestedFact]:
        """
        Harvest from a complete conversation turn (user + assistant).

        Args:
            user_message: User's message
            assistant_response: Assistant's response
            signals: Ontological signals for the turn
            turn_id: Turn identifier

        Returns:
            Combined list of harvested facts
        """
        turn_id = turn_id or str(uuid4())

        # Harvest from user message (primary source)
        user_facts = self.harvest(
            user_message,
            signals=signals,
            source_turn_id=turn_id,
            role="user",
        )

        # Harvest from assistant response (secondary)
        # Only extract facts that reference user info
        assistant_facts = self._harvest_assistant_references(
            assistant_response,
            signals=signals,
            source_turn_id=turn_id,
        )

        return user_facts + assistant_facts

    def classify_to_bucket(
        self,
        fact: HarvestedFact,
        signals: Optional[MessageSignals] = None,
    ) -> BucketCategory:
        """
        Determine the best bucket for a harvested fact.

        Uses the fact's bucket_hint as primary signal,
        refined by ontological signals if available.

        Args:
            fact: The harvested fact
            signals: Optional ontological signals

        Returns:
            Best matching BucketCategory
        """
        # Start with pattern hint
        bucket = fact.bucket_hint

        # If we have strong ontological signal, use layer mapping
        if signals:
            dominant_layer = signals.get_dominant_layer()

            # Only override if layer is strongly activated
            if signals.ontology_layers.get(dominant_layer, 0) > 0.6:
                layer_bucket = LAYER_TO_BUCKET.get(dominant_layer)
                if layer_bucket:
                    # Check if layer bucket is compatible with hint
                    if self._buckets_compatible(fact.bucket_hint, layer_bucket):
                        bucket = layer_bucket

        return bucket

    def create_bucket_entry(
        self,
        fact: HarvestedFact,
        bucket_category: BucketCategory,
        signals: Optional[MessageSignals] = None,
        embedding: Optional[List[float]] = None,
    ) -> BucketEntry:
        """
        Create a BucketEntry from a harvested fact.

        Args:
            fact: The harvested fact
            bucket_category: Target bucket
            signals: Ontological signals snapshot
            embedding: Optional semantic embedding

        Returns:
            BucketEntry ready for storage
        """
        signal_snapshot = None
        if signals:
            signal_snapshot = {
                "dominant_layer": signals.get_dominant_layer(),
                "kosha_level": signals.get_kosha_level(),
                "dominant_vritti": signals.dominant_vritti,
                "dominant_guna": signals.get_dominant_guna(),
                "normalized_entropy": signals.normalized_entropy,
            }

        return BucketEntry(
            entry_id=str(uuid4()),
            content=fact.content,
            source_turn_id="",  # Will be set by caller
            timestamp=datetime.utcnow(),
            importance_score=fact.importance_score,
            confidence_score=fact.confidence,
            summary=self._generate_summary(fact),
            source_message=fact.source_text,
            signal_snapshot=signal_snapshot,
            entities=fact.entities,
            metadata={
                "pattern_name": fact.pattern_name,
                "bucket_hint": fact.bucket_hint.value,
            },
            embedding=embedding,
        )

    def _refine_with_signals(
        self,
        facts: List[HarvestedFact],
        signals: MessageSignals,
    ) -> List[HarvestedFact]:
        """Refine fact classification using ontological signals."""
        refined = []

        for fact in facts:
            # Boost importance for facts matching signal profile
            importance_boost = 0.0

            # Check if fact category matches dominant layer
            dominant_layer = signals.get_dominant_layer()
            layer_bucket = LAYER_TO_BUCKET.get(dominant_layer)

            if layer_bucket == fact.bucket_hint:
                importance_boost += 0.1

            # High entropy suggests important/novel information
            if signals.normalized_entropy > 0.6:
                importance_boost += 0.05

            # Apply boost
            fact.importance_score = min(1.0, fact.importance_score + importance_boost)

            refined.append(fact)

        return refined

    def _harvest_assistant_references(
        self,
        text: str,
        signals: Optional[MessageSignals],
        source_turn_id: str,
    ) -> List[HarvestedFact]:
        """
        Extract facts from assistant responses that reference user info.

        Only captures statements where assistant confirms/restates user info.
        """
        facts = []

        # Patterns for assistant confirming user info
        confirmation_patterns = [
            re.compile(
                r"(?:you mentioned|you said|you're|you are)\s+(.+?)(?:\.|,|$)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:your|Your)\s+(goal|preference|decision|project)\s+(.+?)(?:\.|$)",
                re.IGNORECASE,
            ),
        ]

        for pattern in confirmation_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                content = match.group(0).strip()
                if len(content) >= self.min_content_length:
                    fact = HarvestedFact(
                        content=content,
                        source_text=text[:200],
                        pattern_name="assistant_confirmation",
                        bucket_hint=BucketCategory.SELF,  # Default for confirmations
                        importance_score=0.4,  # Lower importance for indirect
                        confidence=0.6,
                    )
                    facts.append(fact)

        return facts

    def _deduplicate_facts(
        self,
        facts: List[HarvestedFact],
        similarity_threshold: float = 0.8,
    ) -> List[HarvestedFact]:
        """Remove near-duplicate facts, keeping highest importance."""
        if len(facts) <= 1:
            return facts

        # Simple deduplication based on content overlap
        unique_facts: List[HarvestedFact] = []

        for fact in facts:
            is_duplicate = False

            for existing in unique_facts:
                # Simple Jaccard similarity on words
                words1 = set(fact.content.lower().split())
                words2 = set(existing.content.lower().split())

                if not words1 or not words2:
                    continue

                intersection = len(words1 & words2)
                union = len(words1 | words2)
                similarity = intersection / union if union > 0 else 0

                if similarity > similarity_threshold:
                    is_duplicate = True
                    # Keep the one with higher importance
                    if fact.importance_score > existing.importance_score:
                        unique_facts.remove(existing)
                        unique_facts.append(fact)
                    break

            if not is_duplicate:
                unique_facts.append(fact)

        return unique_facts

    def _generate_summary(self, fact: HarvestedFact) -> Optional[str]:
        """Generate a brief summary of the fact."""
        # For now, just truncate if long
        if len(fact.content) <= 100:
            return None

        # Find sentence boundary
        truncated = fact.content[:100]
        last_period = truncated.rfind(".")
        if last_period > 50:
            return truncated[:last_period + 1]

        return truncated + "..."

    @staticmethod
    def _buckets_compatible(
        hint: BucketCategory,
        layer_bucket: BucketCategory,
    ) -> bool:
        """Check if two bucket categories are compatible."""
        # Define compatibility groups
        compatibility_groups = [
            {BucketCategory.SELF, BucketCategory.PREFERENCES, BucketCategory.VALUES},
            {BucketCategory.ACTIONS, BucketCategory.PROJECTS, BucketCategory.DECISIONS},
            {BucketCategory.LEARNING, BucketCategory.ANALYSIS, BucketCategory.SYNTHESIS},
            {BucketCategory.ASPIRATIONS, BucketCategory.VALUES},
            {BucketCategory.RELATIONSHIPS, BucketCategory.EMOTIONS},
        ]

        for group in compatibility_groups:
            if hint in group and layer_bucket in group:
                return True

        return hint == layer_bucket


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Main class
    "KnowledgeHarvester",
    # Data classes
    "HarvestedFact",
    "ExtractionPattern",
    # Salience scoring
    "calculate_salience",
    "STRONG_MARKERS",
    "WEAK_MARKERS",
    # Pattern collections
    "ALL_PATTERNS",
]
