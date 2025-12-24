"""
Phase-14: Layer Assigner — EXPERIMENT SANDBOX
=============================================

EXPERIMENT_ONLY = True

WARNING: This file MUST NOT be used as ontology source of truth.
Phase-14 is an AUDIT/ENFORCEMENT layer, NOT an ontology consumer.

AUTHORITATIVE SOURCE:
    - Ontology executor: symbolu.ontology.phase4a
    - Frozen data: docs/data/*.json

Assigns words to ontological layers (O1-O10) using POS-based heuristics.

Architecture:
    1. Simple POS tagging (rule-based, no external dependencies)
    2. POS → Layer mapping heuristics
    3. Context hints for disambiguation
    4. Confidence scoring

Ontological Layers:
    O5_COGNITION   - Cognitive verbs, mental states
    O4_STRUCTURE    - Creation, shaping verbs
    O3_EXECUTION     - Physical action verbs
    O4_TAGGING    - Labeling, categorizing words
    O6_AGENCY  - Commands, guidance words
    O7_REASONING  - Causal connectors, logical words
    O8_PURPOSE  - Goal, intention words
    O9_WITNESSES - Observation, meta-reflection
    O10_UNIFYING   - Synthesis, integration words
    O12_ABSOLVING - Release, resolution words
"""

EXPERIMENT_ONLY = True

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "phase13_sandbox"))

from k1_schema import OntologicalLayer


# =============================================================================
# Simple POS Tags
# =============================================================================

class SimplePOS(Enum):
    """Simplified part-of-speech tags."""
    VERB_ACTION = "VERB_ACTION"         # run, jump, make
    VERB_COGNITIVE = "VERB_COGNITIVE"   # think, believe, know
    VERB_CREATION = "VERB_CREATION"     # create, build, form
    VERB_STATE = "VERB_STATE"           # be, seem, appear
    VERB_MODAL = "VERB_MODAL"           # can, should, must
    NOUN_CONCRETE = "NOUN_CONCRETE"     # table, car, tree
    NOUN_ABSTRACT = "NOUN_ABSTRACT"     # idea, truth, freedom
    NOUN_PERSON = "NOUN_PERSON"         # man, woman, child
    ADJECTIVE = "ADJECTIVE"             # good, big, important
    ADVERB = "ADVERB"                   # quickly, very, always
    CONNECTOR = "CONNECTOR"             # because, therefore, however
    DETERMINER = "DETERMINER"           # the, a, this, that
    PREPOSITION = "PREPOSITION"         # in, on, at, with
    PRONOUN = "PRONOUN"                 # he, she, it, they
    UNKNOWN = "UNKNOWN"                 # fallback


# =============================================================================
# POS Lexicons
# =============================================================================

# Words by POS category
POS_LEXICON: Dict[SimplePOS, FrozenSet[str]] = {
    SimplePOS.VERB_COGNITIVE: frozenset([
        "think", "believe", "know", "understand", "consider", "imagine",
        "remember", "forget", "realize", "recognize", "perceive", "suppose",
        "assume", "doubt", "wonder", "feel", "sense", "expect", "hope",
        "fear", "dream", "reflect", "contemplate", "ponder", "meditate",
        "analyze", "evaluate", "judge", "decide", "reason", "infer",
        "deduce", "conclude", "comprehend", "grasp", "learn", "study",
    ]),
    SimplePOS.VERB_CREATION: frozenset([
        "create", "make", "build", "construct", "form", "shape", "design",
        "develop", "produce", "generate", "compose", "write", "paint",
        "draw", "sculpt", "craft", "manufacture", "assemble", "invent",
        "innovate", "devise", "conceive", "establish", "found", "initiate",
        "originate", "institute", "synthesize", "fabricate", "forge",
    ]),
    SimplePOS.VERB_ACTION: frozenset([
        "run", "walk", "jump", "move", "go", "come", "take", "give",
        "put", "get", "send", "bring", "carry", "push", "pull", "throw",
        "catch", "hit", "kick", "touch", "hold", "drop", "pick", "cut",
        "break", "open", "close", "turn", "stop", "start", "begin", "end",
        "continue", "finish", "complete", "do", "act", "perform", "execute",
        "implement", "apply", "use", "work", "play", "eat", "drink", "sleep",
        "wake", "sit", "stand", "lie", "rise", "fall", "fly", "swim", "climb",
        "drive", "ride", "sail", "travel", "arrive", "leave", "enter", "exit",
        "return", "reach", "pass", "cross", "follow", "lead", "chase", "catch",
        "fight", "attack", "defend", "protect", "save", "kill", "destroy",
        "catalyze", "catalyzes", "react", "transform", "process",
    ]),
    SimplePOS.VERB_STATE: frozenset([
        "be", "is", "am", "are", "was", "were", "been", "being",
        "seem", "appear", "look", "sound", "smell", "taste", "feel",
        "become", "remain", "stay", "keep", "grow", "turn", "prove",
        "exist", "live", "die", "belong", "contain", "include", "consist",
        "equal", "mean", "represent", "signify", "symbolize", "matter",
    ]),
    SimplePOS.VERB_MODAL: frozenset([
        "can", "could", "may", "might", "must", "shall", "should",
        "will", "would", "ought", "need", "dare",
    ]),
    SimplePOS.NOUN_ABSTRACT: frozenset([
        "idea", "thought", "concept", "theory", "principle", "truth",
        "beauty", "justice", "freedom", "love", "peace", "power",
        "knowledge", "wisdom", "time", "space", "energy", "force",
        "reason", "purpose", "meaning", "value", "quality", "nature",
        "essence", "existence", "reality", "possibility", "necessity",
        "cause", "effect", "result", "consequence", "relation", "connection",
        "structure", "function", "system", "process", "method", "way",
        "problem", "solution", "question", "answer", "fact", "evidence",
        "proof", "argument", "opinion", "belief", "faith", "hope",
        "fear", "joy", "happiness", "sadness", "anger", "emotion",
        "feeling", "experience", "memory", "imagination", "creativity",
        "intelligence", "consciousness", "mind", "soul", "spirit",
        "analysis", "synthesis", "reaction", "enzyme", "molecule", "protein",
    ]),
    SimplePOS.NOUN_CONCRETE: frozenset([
        "table", "chair", "door", "window", "house", "building", "room",
        "car", "train", "plane", "boat", "ship", "bus", "bicycle",
        "tree", "flower", "plant", "animal", "dog", "cat", "bird", "fish",
        "book", "paper", "pen", "computer", "phone", "machine", "tool",
        "food", "water", "air", "fire", "earth", "stone", "metal", "wood",
        "glass", "plastic", "cloth", "skin", "bone", "blood", "heart",
        "brain", "hand", "foot", "head", "eye", "ear", "nose", "mouth",
        "sun", "moon", "star", "sky", "cloud", "rain", "snow", "wind",
        "mountain", "river", "lake", "ocean", "sea", "island", "forest",
        "road", "street", "path", "bridge", "city", "town", "village",
        "cell", "data", "number", "part", "area", "point", "place",
    ]),
    SimplePOS.NOUN_PERSON: frozenset([
        "man", "woman", "child", "boy", "girl", "baby", "person", "people",
        "human", "adult", "teenager", "elder", "mother", "father", "parent",
        "son", "daughter", "brother", "sister", "sibling", "family", "friend",
        "teacher", "student", "doctor", "nurse", "lawyer", "engineer",
        "scientist", "artist", "writer", "musician", "actor", "athlete",
        "worker", "employee", "manager", "leader", "president", "king",
        "queen", "prince", "princess", "soldier", "police", "citizen",
        "neighbor", "stranger", "customer", "client", "patient", "victim",
    ]),
    SimplePOS.ADJECTIVE: frozenset([
        "good", "bad", "big", "small", "large", "little", "great", "huge",
        "tiny", "long", "short", "tall", "wide", "narrow", "thick", "thin",
        "high", "low", "deep", "shallow", "heavy", "light", "fast", "slow",
        "quick", "new", "old", "young", "ancient", "modern", "early", "late",
        "hot", "cold", "warm", "cool", "wet", "dry", "hard", "soft",
        "strong", "weak", "rich", "poor", "happy", "sad", "angry", "calm",
        "beautiful", "ugly", "pretty", "handsome", "clean", "dirty", "bright",
        "dark", "clear", "cloudy", "loud", "quiet", "sweet", "sour", "bitter",
        "important", "necessary", "possible", "impossible", "certain", "sure",
        "different", "same", "similar", "equal", "right", "wrong", "true",
        "false", "real", "fake", "free", "busy", "empty", "full", "open",
        "closed", "alive", "dead", "healthy", "sick", "safe", "dangerous",
    ]),
    SimplePOS.ADVERB: frozenset([
        "very", "really", "quite", "rather", "too", "so", "just", "only",
        "even", "also", "still", "already", "yet", "always", "never",
        "sometimes", "often", "usually", "rarely", "seldom", "ever",
        "now", "then", "soon", "later", "early", "late", "today", "tomorrow",
        "yesterday", "here", "there", "everywhere", "nowhere", "somewhere",
        "away", "back", "forward", "backward", "up", "down", "in", "out",
        "well", "badly", "quickly", "slowly", "carefully", "easily",
        "hardly", "nearly", "almost", "completely", "totally", "entirely",
        "partly", "mostly", "mainly", "generally", "especially", "particularly",
    ]),
    SimplePOS.CONNECTOR: frozenset([
        "and", "or", "but", "so", "yet", "nor", "for",
        "because", "since", "as", "if", "unless", "although", "though",
        "while", "when", "where", "whereas", "whether",
        "therefore", "thus", "hence", "consequently", "accordingly",
        "however", "nevertheless", "nonetheless", "otherwise", "instead",
        "moreover", "furthermore", "besides", "also", "additionally",
        "meanwhile", "afterward", "finally", "eventually", "ultimately",
    ]),
    SimplePOS.DETERMINER: frozenset([
        "the", "a", "an", "this", "that", "these", "those",
        "my", "your", "his", "her", "its", "our", "their",
        "some", "any", "no", "every", "each", "all", "both",
        "few", "many", "much", "more", "most", "less", "least",
        "several", "enough", "other", "another", "such", "what", "which",
    ]),
    SimplePOS.PREPOSITION: frozenset([
        "in", "on", "at", "by", "for", "with", "about", "against",
        "between", "into", "through", "during", "before", "after",
        "above", "below", "to", "from", "up", "down", "out", "off",
        "over", "under", "again", "further", "then", "once", "near",
        "around", "among", "across", "behind", "beyond", "within",
        "without", "along", "toward", "upon", "until", "except",
    ]),
    SimplePOS.PRONOUN: frozenset([
        "i", "me", "my", "mine", "myself",
        "you", "your", "yours", "yourself",
        "he", "him", "his", "himself",
        "she", "her", "hers", "herself",
        "it", "its", "itself",
        "we", "us", "our", "ours", "ourselves",
        "they", "them", "their", "theirs", "themselves",
        "who", "whom", "whose", "which", "that",
        "what", "whoever", "whatever", "whichever",
        "one", "ones", "someone", "anyone", "everyone", "no one",
        "something", "anything", "everything", "nothing",
    ]),
}


def get_pos(word: str) -> SimplePOS:
    """Get POS tag for a word."""
    word_lower = word.strip().lower()

    for pos, lexicon in POS_LEXICON.items():
        if word_lower in lexicon:
            return pos

    # Suffix-based heuristics
    if word_lower.endswith("ly"):
        return SimplePOS.ADVERB
    if word_lower.endswith(("tion", "sion", "ness", "ment", "ity")):
        return SimplePOS.NOUN_ABSTRACT
    if word_lower.endswith(("ing", "ed", "es", "s")) and len(word_lower) > 4:
        # Likely verb form
        base = word_lower.rstrip("s").rstrip("e").rstrip("d").rstrip("g").rstrip("n").rstrip("i")
        if len(base) >= 2:
            return SimplePOS.VERB_ACTION
    if word_lower.endswith(("er", "or", "ist", "ian")):
        return SimplePOS.NOUN_PERSON
    if word_lower.endswith(("ful", "less", "ous", "ive", "able", "ible")):
        return SimplePOS.ADJECTIVE

    return SimplePOS.UNKNOWN


# =============================================================================
# POS → Layer Mapping
# =============================================================================

# Primary layer assignment by POS
POS_TO_LAYER: Dict[SimplePOS, OntologicalLayer] = {
    SimplePOS.VERB_COGNITIVE: OntologicalLayer.O5_COGNITION,
    SimplePOS.VERB_CREATION: OntologicalLayer.O4_STRUCTURE,
    SimplePOS.VERB_ACTION: OntologicalLayer.O3_EXECUTION,
    SimplePOS.VERB_STATE: OntologicalLayer.O3_EXECUTION,  # Default to acting
    SimplePOS.VERB_MODAL: OntologicalLayer.O6_AGENCY,
    SimplePOS.NOUN_ABSTRACT: OntologicalLayer.O5_COGNITION,
    SimplePOS.NOUN_CONCRETE: OntologicalLayer.O4_TAGGING,
    SimplePOS.NOUN_PERSON: OntologicalLayer.O4_TAGGING,
    SimplePOS.ADJECTIVE: OntologicalLayer.O4_TAGGING,
    SimplePOS.ADVERB: OntologicalLayer.O6_AGENCY,
    SimplePOS.CONNECTOR: OntologicalLayer.O7_REASONING,
    SimplePOS.DETERMINER: OntologicalLayer.O4_TAGGING,
    SimplePOS.PREPOSITION: OntologicalLayer.O7_REASONING,
    SimplePOS.PRONOUN: OntologicalLayer.O4_TAGGING,
    SimplePOS.UNKNOWN: OntologicalLayer.O4_TAGGING,  # Default
}


# Override lexicons for specific layers
LAYER_OVERRIDE_LEXICON: Dict[OntologicalLayer, FrozenSet[str]] = {
    OntologicalLayer.O6_AGENCY: frozenset([
        "should", "must", "need", "require", "demand", "command", "order",
        "direct", "guide", "lead", "instruct", "tell", "ask", "request",
        "suggest", "recommend", "advise", "urge", "encourage", "persuade",
        "convince", "compel", "force", "allow", "permit", "let", "forbid",
        "prohibit", "prevent", "stop", "enable", "empower", "authorize",
    ]),
    OntologicalLayer.O7_REASONING: frozenset([
        "because", "since", "therefore", "thus", "hence", "consequently",
        "accordingly", "so", "if", "then", "unless", "although", "though",
        "whereas", "while", "however", "nevertheless", "nonetheless",
        "cause", "effect", "result", "reason", "explain", "justify",
        "prove", "demonstrate", "show", "indicate", "imply", "suggest",
        "infer", "deduce", "conclude", "analyze", "evaluate", "compare",
        "contrast", "distinguish", "differentiate", "correlate", "relate",
    ]),
    OntologicalLayer.O8_PURPOSE: frozenset([
        "aim", "goal", "purpose", "objective", "target", "intention",
        "intent", "plan", "strategy", "mission", "vision", "aspiration",
        "ambition", "desire", "want", "wish", "hope", "expect", "anticipate",
        "intend", "mean", "design", "destine", "seek", "pursue", "strive",
        "endeavor", "attempt", "try", "aspire", "yearn", "long",
    ]),
    OntologicalLayer.O9_WITNESSES: frozenset([
        "observe", "watch", "notice", "see", "perceive", "witness",
        "monitor", "track", "follow", "survey", "examine", "inspect",
        "scrutinize", "study", "analyze", "investigate", "explore",
        "review", "assess", "evaluate", "measure", "record", "document",
        "note", "remark", "comment", "reflect", "contemplate", "consider",
        "meta", "self", "aware", "conscious", "mindful", "introspect",
    ]),
    OntologicalLayer.O10_UNIFYING: frozenset([
        "unify", "unite", "combine", "merge", "integrate", "synthesize",
        "consolidate", "harmonize", "reconcile", "bridge", "connect",
        "link", "join", "bind", "tie", "gather", "collect", "assemble",
        "aggregate", "accumulate", "converge", "coalesce", "fuse", "blend",
        "mix", "mingle", "whole", "complete", "total", "all", "together",
    ]),
    OntologicalLayer.O12_ABSOLVING: frozenset([
        "absolve", "forgive", "pardon", "excuse", "release", "free",
        "liberate", "emancipate", "discharge", "acquit", "exonerate",
        "clear", "vindicate", "resolve", "settle", "conclude", "finish",
        "end", "close", "complete", "terminate", "cease", "stop", "halt",
        "abandon", "relinquish", "surrender", "let go", "accept", "peace",
    ]),
}


def get_layer_override(word: str) -> Optional[OntologicalLayer]:
    """Check if word has a layer override."""
    word_lower = word.strip().lower()
    for layer, lexicon in LAYER_OVERRIDE_LEXICON.items():
        if word_lower in lexicon:
            return layer
    return None


# =============================================================================
# Layer Assignment Result
# =============================================================================

@dataclass(frozen=True)
class LayerAssignment:
    """Result of layer assignment."""
    word: str
    layer: OntologicalLayer
    pos: SimplePOS
    confidence: float               # 0.0 to 1.0
    source: str                     # "override", "pos_mapping", "default"
    assignment_hash: str


def compute_assignment_hash(word: str, layer: OntologicalLayer) -> str:
    """Compute deterministic hash for assignment."""
    content = f"{word.lower()}|{layer.value}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]


# =============================================================================
# Context Hints
# =============================================================================

@dataclass(frozen=True)
class ContextHint:
    """Contextual information that can influence layer assignment."""
    preceding_words: Tuple[str, ...] = ()
    following_words: Tuple[str, ...] = ()
    sentence_type: str = "declarative"  # declarative, interrogative, imperative
    domain: str = ""                     # e.g., "scientific", "legal", "casual"


# Context patterns that suggest specific layers
CONTEXT_PATTERNS: Dict[str, OntologicalLayer] = {
    # Question patterns → O5_COGNITION
    "why": OntologicalLayer.O5_COGNITION,
    "how": OntologicalLayer.O5_COGNITION,
    "what if": OntologicalLayer.O5_COGNITION,
    # Command patterns → O6_AGENCY
    "please": OntologicalLayer.O6_AGENCY,
    "you should": OntologicalLayer.O6_AGENCY,
    "you must": OntologicalLayer.O6_AGENCY,
    # Causal patterns → O7_REASONING
    "because of": OntologicalLayer.O7_REASONING,
    "due to": OntologicalLayer.O7_REASONING,
    "as a result": OntologicalLayer.O7_REASONING,
    # Purpose patterns → O8_PURPOSE
    "in order to": OntologicalLayer.O8_PURPOSE,
    "so that": OntologicalLayer.O8_PURPOSE,
    "for the purpose": OntologicalLayer.O8_PURPOSE,
}


def apply_context_adjustment(
    base_layer: OntologicalLayer,
    word: str,
    context: Optional[ContextHint]
) -> Tuple[OntologicalLayer, float]:
    """
    Adjust layer based on context.

    Returns (adjusted_layer, confidence_modifier)
    """
    if context is None:
        return base_layer, 1.0

    # Check preceding words for context patterns
    preceding_text = " ".join(context.preceding_words).lower()
    for pattern, layer in CONTEXT_PATTERNS.items():
        if pattern in preceding_text:
            return layer, 0.9  # High confidence from context

    # Imperative sentences boost DIRECTING
    if context.sentence_type == "imperative":
        if base_layer == OntologicalLayer.O3_EXECUTION:
            return OntologicalLayer.O6_AGENCY, 0.85

    # Scientific domain boosts certain layers
    if context.domain == "scientific":
        if base_layer == OntologicalLayer.O3_EXECUTION:
            # Scientific actions often involve reasoning
            return OntologicalLayer.O7_REASONING, 0.8

    return base_layer, 1.0


# =============================================================================
# Layer Assigner
# =============================================================================

@dataclass(frozen=True)
class LayerAssigner:
    """
    Assigns words to ontological layers.

    Uses POS tagging + heuristics + context hints.
    """

    def assign(
        self,
        word: str,
        context: Optional[ContextHint] = None
    ) -> LayerAssignment:
        """Assign a word to an ontological layer."""
        word_clean = word.strip().lower()

        # Step 1: Check override lexicon
        override_layer = get_layer_override(word_clean)
        if override_layer is not None:
            return LayerAssignment(
                word=word_clean,
                layer=override_layer,
                pos=get_pos(word_clean),
                confidence=0.95,
                source="override",
                assignment_hash=compute_assignment_hash(word_clean, override_layer),
            )

        # Step 2: Get POS tag
        pos = get_pos(word_clean)

        # Step 3: Map POS to layer
        base_layer = POS_TO_LAYER.get(pos, OntologicalLayer.O4_TAGGING)

        # Step 4: Apply context adjustment
        final_layer, conf_modifier = apply_context_adjustment(base_layer, word_clean, context)

        # Step 5: Calculate confidence
        base_confidence = 0.8 if pos != SimplePOS.UNKNOWN else 0.5
        confidence = base_confidence * conf_modifier

        source = "context_adjusted" if final_layer != base_layer else "pos_mapping"
        if pos == SimplePOS.UNKNOWN:
            source = "default"

        return LayerAssignment(
            word=word_clean,
            layer=final_layer,
            pos=pos,
            confidence=confidence,
            source=source,
            assignment_hash=compute_assignment_hash(word_clean, final_layer),
        )

    def assign_batch(
        self,
        words: Tuple[str, ...],
        context: Optional[ContextHint] = None
    ) -> Tuple[LayerAssignment, ...]:
        """Assign multiple words to layers."""
        return tuple(self.assign(w, context) for w in words)

    def get_layer_words(self, layer: OntologicalLayer) -> Set[str]:
        """Get words known to map to a layer (from override lexicon)."""
        return set(LAYER_OVERRIDE_LEXICON.get(layer, frozenset()))


# =============================================================================
# Factory Functions
# =============================================================================

def create_assigner() -> LayerAssigner:
    """Create layer assigner."""
    return LayerAssigner()


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Enums
    "SimplePOS",
    # Data classes
    "LayerAssignment",
    "ContextHint",
    # Main class
    "LayerAssigner",
    # Functions
    "create_assigner",
    "get_pos",
    "get_layer_override",
    "apply_context_adjustment",
    "compute_assignment_hash",
    # Constants
    "POS_LEXICON",
    "POS_TO_LAYER",
    "LAYER_OVERRIDE_LEXICON",
    "CONTEXT_PATTERNS",
]
