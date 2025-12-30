"""
SymbolU12 Paradox Synthesis Engine
===================================

Generates variations of paradoxes to prevent memorization.
The model must learn the PATTERN, not just the 50 examples.

Synthesis Strategies:
    1. Template substitution (swap nouns, verbs, domains)
    2. Domain transfer (apply structure to new contexts)
    3. Complexity scaling (simpler/harder versions)
    4. Hybrid generation (combine paradox types)
    5. Adversarial mutation (designed to trick the model)

Usage:
    synthesizer = ParadoxSynthesizer()
    variations = synthesizer.generate_variations("liar_paradox", count=100)
"""

from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import random
import re

from .curriculum import (
    Paradox,
    ParadoxCategory,
    ExpectedBhava,
    PARADOX_LIBRARY,
)


# =============================================================================
# SYNTHESIS TEMPLATES
# =============================================================================

# Substitution pools for template-based generation
SELF_REFERENTIAL_SUBJECTS = [
    "This statement", "This sentence", "What I'm saying",
    "The current assertion", "This claim", "My words here",
    "This proposition", "The text you're reading",
    "This declaration", "What follows",
]

TRUTH_PREDICATES = [
    "is false", "is not true", "cannot be verified",
    "is a lie", "is deceptive", "is misleading",
    "contradicts itself", "negates its own meaning",
    "is impossible to confirm", "undermines itself",
]

DOMAIN_CONTEXTS = [
    ("barber", "shave", "person", "town"),
    ("librarian", "catalog", "book", "library"),
    ("judge", "sentence", "defendant", "court"),
    ("teacher", "grade", "student", "class"),
    ("doctor", "treat", "patient", "hospital"),
    ("chef", "cook for", "customer", "restaurant"),
    ("pilot", "fly", "passenger", "airline"),
    ("programmer", "debug", "program", "company"),
    ("artist", "paint", "subject", "gallery"),
    ("writer", "write about", "character", "story"),
]

INFINITE_OBJECTS = [
    ("hotel", "room", "guest"),
    ("library", "shelf", "book"),
    ("train", "car", "passenger"),
    ("building", "floor", "tenant"),
    ("server", "slot", "request"),
    ("memory", "address", "process"),
    ("universe", "dimension", "being"),
    ("time", "moment", "event"),
]

TEMPORAL_VERBS = [
    ("go back", "prevent", "happened"),
    ("travel to", "stop", "occurred"),
    ("return to", "change", "existed"),
    ("visit", "alter", "transpired"),
    ("journey to", "modify", "took place"),
]

SET_DESCRIPTORS = [
    "all sets", "every collection", "each group",
    "all categories", "every class", "each container",
    "all abstractions", "every concept-holder",
]


# =============================================================================
# SYNTHESIS STRATEGIES
# =============================================================================

class SynthesisStrategy(Enum):
    """Available synthesis strategies."""
    TEMPLATE_SUBSTITUTION = "template_substitution"
    DOMAIN_TRANSFER = "domain_transfer"
    COMPLEXITY_SCALING = "complexity_scaling"
    HYBRID_GENERATION = "hybrid_generation"
    ADVERSARIAL_MUTATION = "adversarial_mutation"


@dataclass
class SynthesizedParadox:
    """A generated paradox variation."""
    base_id: str
    variation_id: str
    prompt: str
    strategy: SynthesisStrategy
    category: ParadoxCategory
    expected_bhava: ExpectedBhava
    expected_trace_range: Tuple[float, float]
    difficulty_modifier: float  # 1.0 = same, <1 = easier, >1 = harder
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_paradox(self) -> Paradox:
        """Convert to standard Paradox format."""
        return Paradox(
            id=self.variation_id,
            category=self.category,
            prompt=self.prompt,
            expected_bhava=self.expected_bhava,
            expected_trace_range=self.expected_trace_range,
            target_response_pattern="[synthesized variation]",
        )


# =============================================================================
# PARADOX SYNTHESIZER
# =============================================================================

class ParadoxSynthesizer:
    """
    Generates paradox variations to prevent memorization.

    The model must learn to recognize paradox STRUCTURE,
    not just pattern-match on the 50 base examples.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.base_paradoxes = {p.id: p for p in PARADOX_LIBRARY}
        self.generated_prompts: Set[str] = set()  # Avoid duplicates

    def generate_variations(
        self,
        base_id: str,
        count: int = 10,
        strategies: Optional[List[SynthesisStrategy]] = None,
    ) -> List[SynthesizedParadox]:
        """
        Generate variations of a specific paradox.

        Args:
            base_id: ID of base paradox from PARADOX_LIBRARY
            count: Number of variations to generate
            strategies: Which strategies to use (default: all)

        Returns:
            List of synthesized paradox variations
        """
        if base_id not in self.base_paradoxes:
            raise ValueError(f"Unknown paradox: {base_id}")

        base = self.base_paradoxes[base_id]

        if strategies is None:
            strategies = list(SynthesisStrategy)

        variations = []
        attempts = 0
        max_attempts = count * 10  # Prevent infinite loops

        while len(variations) < count and attempts < max_attempts:
            attempts += 1
            strategy = self.rng.choice(strategies)

            try:
                variation = self._apply_strategy(base, strategy, len(variations))
                if variation and variation.prompt not in self.generated_prompts:
                    self.generated_prompts.add(variation.prompt)
                    variations.append(variation)
            except Exception:
                continue  # Skip failed generations

        return variations

    def generate_batch(
        self,
        count_per_paradox: int = 20,
        categories: Optional[List[ParadoxCategory]] = None,
    ) -> List[SynthesizedParadox]:
        """
        Generate variations for all paradoxes in library.

        Args:
            count_per_paradox: Variations per base paradox
            categories: Only generate for these categories

        Returns:
            Full batch of synthesized paradoxes
        """
        all_variations = []

        for base in PARADOX_LIBRARY:
            if categories and base.category not in categories:
                continue

            variations = self.generate_variations(
                base.id, count=count_per_paradox
            )
            all_variations.extend(variations)

        return all_variations

    def _apply_strategy(
        self,
        base: Paradox,
        strategy: SynthesisStrategy,
        index: int,
    ) -> Optional[SynthesizedParadox]:
        """Apply a specific synthesis strategy."""
        if strategy == SynthesisStrategy.TEMPLATE_SUBSTITUTION:
            return self._template_substitution(base, index)
        elif strategy == SynthesisStrategy.DOMAIN_TRANSFER:
            return self._domain_transfer(base, index)
        elif strategy == SynthesisStrategy.COMPLEXITY_SCALING:
            return self._complexity_scaling(base, index)
        elif strategy == SynthesisStrategy.HYBRID_GENERATION:
            return self._hybrid_generation(base, index)
        elif strategy == SynthesisStrategy.ADVERSARIAL_MUTATION:
            return self._adversarial_mutation(base, index)
        return None

    # =========================================================================
    # STRATEGY IMPLEMENTATIONS
    # =========================================================================

    def _template_substitution(
        self,
        base: Paradox,
        index: int,
    ) -> SynthesizedParadox:
        """
        Simple word/phrase substitution.

        Maintains paradox structure but changes surface form.
        """
        prompt = base.prompt

        # Category-specific substitutions
        if base.category == ParadoxCategory.SELF_REFERENCE:
            subject = self.rng.choice(SELF_REFERENTIAL_SUBJECTS)
            predicate = self.rng.choice(TRUTH_PREDICATES)
            prompt = f"{subject} {predicate}. Is it true or false?"

        elif base.category == ParadoxCategory.SET_THEORY:
            descriptor = self.rng.choice(SET_DESCRIPTORS)
            prompt = base.prompt.replace("all sets", descriptor)
            prompt = prompt.replace("every set", descriptor)

        elif base.category == ParadoxCategory.TEMPORAL:
            verb_set = self.rng.choice(TEMPORAL_VERBS)
            prompt = (f"If you could {verb_set[0]} the past and "
                     f"{verb_set[1]} your birth, would you exist "
                     f"to do so, given you {verb_set[2]}?")

        # Fallback: synonym substitution
        else:
            prompt = self._synonym_substitute(prompt)

        return SynthesizedParadox(
            base_id=base.id,
            variation_id=f"{base.id}_template_{index}",
            prompt=prompt,
            strategy=SynthesisStrategy.TEMPLATE_SUBSTITUTION,
            category=base.category,
            expected_bhava=base.expected_bhava,
            expected_trace_range=base.expected_trace_range,
            difficulty_modifier=1.0,
        )

    def _domain_transfer(
        self,
        base: Paradox,
        index: int,
    ) -> SynthesizedParadox:
        """
        Apply paradox structure to a new domain.

        E.g., Barber paradox → Librarian paradox
        """
        if base.category == ParadoxCategory.SET_THEORY:
            # Russell's barber → new profession
            domain = self.rng.choice(DOMAIN_CONTEXTS)
            prompt = (f"In a {domain[3]}, there is a {domain[0]} who {domain[1]}s "
                     f"all and only those {domain[2]}s who don't {domain[1]} themselves. "
                     f"Who {domain[1]}s the {domain[0]}?")

        elif base.category == ParadoxCategory.INFINITE:
            # Hilbert's hotel → new infinite structure
            obj = self.rng.choice(INFINITE_OBJECTS)
            prompt = (f"A {obj[0]} with infinitely many {obj[1]}s, all occupied. "
                     f"A new {obj[2]} arrives. Can they be accommodated? "
                     f"What if infinitely many new {obj[2]}s arrive?")

        elif base.category == ParadoxCategory.DECISION:
            # Newcomb → new prediction scenario
            predictor = self.rng.choice(["oracle", "AI", "psychic", "time-traveler"])
            prompt = (f"A {predictor} who is almost always right offers you a choice: "
                     f"Take just the mystery box (which they filled based on their "
                     f"prediction of your choice), or take both the mystery box and "
                     f"$1000. What do you choose, knowing they predicted your choice "
                     f"before you made it?")

        else:
            # Generic domain transfer
            prompt = self._apply_domain_wrapper(base.prompt)

        return SynthesizedParadox(
            base_id=base.id,
            variation_id=f"{base.id}_domain_{index}",
            prompt=prompt,
            strategy=SynthesisStrategy.DOMAIN_TRANSFER,
            category=base.category,
            expected_bhava=base.expected_bhava,
            expected_trace_range=base.expected_trace_range,
            difficulty_modifier=1.1,  # Slightly harder in new domain
            metadata={"transferred": True},
        )

    def _complexity_scaling(
        self,
        base: Paradox,
        index: int,
    ) -> SynthesizedParadox:
        """
        Generate simpler or more complex versions.
        """
        # Randomly choose simpler or harder
        simpler = self.rng.random() < 0.5

        if simpler:
            # Strip context, make more direct
            prompt = self._simplify_prompt(base.prompt)
            difficulty = 0.8
            trace_range = (
                min(1.0, base.expected_trace_range[0] + 0.1),
                min(1.0, base.expected_trace_range[1] + 0.1),
            )
        else:
            # Add nesting, indirection
            prompt = self._complexify_prompt(base.prompt)
            difficulty = 1.3
            trace_range = (
                max(0.0, base.expected_trace_range[0] - 0.1),
                max(0.0, base.expected_trace_range[1] - 0.1),
            )

        return SynthesizedParadox(
            base_id=base.id,
            variation_id=f"{base.id}_scale_{index}",
            prompt=prompt,
            strategy=SynthesisStrategy.COMPLEXITY_SCALING,
            category=base.category,
            expected_bhava=base.expected_bhava,
            expected_trace_range=trace_range,
            difficulty_modifier=difficulty,
            metadata={"simplified": simpler},
        )

    def _hybrid_generation(
        self,
        base: Paradox,
        index: int,
    ) -> SynthesizedParadox:
        """
        Combine elements from multiple paradox types.

        Creates novel paradoxes that require understanding
        multiple paradox structures simultaneously.
        """
        # Pick another paradox to combine with
        other = self.rng.choice([p for p in PARADOX_LIBRARY if p.id != base.id])

        # Hybrid approaches by category combination
        hybrid_prompt = self._create_hybrid(base, other)

        # Hybrid expected behavior: take the more conservative (META if either)
        expected_bhava = (
            ExpectedBhava.META
            if (base.expected_bhava == ExpectedBhava.META or
                other.expected_bhava == ExpectedBhava.META)
            else base.expected_bhava
        )

        # Trace range: intersection (more restrictive)
        trace_range = (
            max(base.expected_trace_range[0], other.expected_trace_range[0]),
            min(base.expected_trace_range[1], other.expected_trace_range[1]),
        )
        if trace_range[0] > trace_range[1]:
            trace_range = base.expected_trace_range

        return SynthesizedParadox(
            base_id=base.id,
            variation_id=f"{base.id}_hybrid_{other.id}_{index}",
            prompt=hybrid_prompt,
            strategy=SynthesisStrategy.HYBRID_GENERATION,
            category=base.category,  # Primary category
            expected_bhava=expected_bhava,
            expected_trace_range=trace_range,
            difficulty_modifier=1.5,  # Hybrids are harder
            metadata={
                "combined_with": other.id,
                "secondary_category": other.category.value,
            },
        )

    def _adversarial_mutation(
        self,
        base: Paradox,
        index: int,
    ) -> SynthesizedParadox:
        """
        Create variations specifically designed to fool the model.

        These look like paradoxes but have clear answers,
        or look innocent but are actually paradoxes.
        """
        # 50% chance of fake paradox (has answer), 50% hidden paradox
        is_fake = self.rng.random() < 0.5

        if is_fake:
            # Fake paradox: looks paradoxical but has clear answer
            prompt, expected_bhava = self._create_fake_paradox(base)
            trace_range = (0.7, 1.0)  # Should maintain high trace
            difficulty = 0.9
            metadata = {"adversarial_type": "fake_paradox"}
        else:
            # Hidden paradox: looks innocent but contains paradox
            prompt = self._create_hidden_paradox(base)
            expected_bhava = ExpectedBhava.META
            trace_range = base.expected_trace_range
            difficulty = 1.4
            metadata = {"adversarial_type": "hidden_paradox"}

        return SynthesizedParadox(
            base_id=base.id,
            variation_id=f"{base.id}_adversarial_{index}",
            prompt=prompt,
            strategy=SynthesisStrategy.ADVERSARIAL_MUTATION,
            category=base.category,
            expected_bhava=expected_bhava,
            expected_trace_range=trace_range,
            difficulty_modifier=difficulty,
            metadata=metadata,
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _synonym_substitute(self, text: str) -> str:
        """Basic synonym substitution."""
        substitutions = {
            "true": self.rng.choice(["correct", "accurate", "valid"]),
            "false": self.rng.choice(["incorrect", "wrong", "invalid"]),
            "statement": self.rng.choice(["assertion", "claim", "proposition"]),
            "sentence": self.rng.choice(["phrase", "declaration", "utterance"]),
            "know": self.rng.choice(["understand", "comprehend", "realize"]),
            "believe": self.rng.choice(["think", "hold", "maintain"]),
        }
        result = text
        for old, new in substitutions.items():
            if self.rng.random() < 0.5:  # 50% chance per substitution
                result = result.replace(old, new)
        return result

    def _apply_domain_wrapper(self, prompt: str) -> str:
        """Wrap prompt in a new domain context."""
        domains = [
            "In a formal logic class, a student asks: ",
            "A philosopher poses this puzzle: ",
            "Consider this computational scenario: ",
            "In a debate competition: ",
            "A riddle from ancient times: ",
        ]
        return self.rng.choice(domains) + prompt

    def _simplify_prompt(self, prompt: str) -> str:
        """Make prompt more direct and simple."""
        # Remove hedging language
        simplified = prompt
        hedges = [
            "Consider the following: ",
            "Think about this: ",
            "Here's a puzzle: ",
            "Imagine that ",
            "Suppose that ",
        ]
        for hedge in hedges:
            simplified = simplified.replace(hedge, "")

        # Shorten if too long
        if len(simplified) > 200:
            sentences = simplified.split(". ")
            simplified = ". ".join(sentences[:2]) + "?"

        return simplified.strip()

    def _complexify_prompt(self, prompt: str) -> str:
        """Add complexity and indirection."""
        wrappers = [
            f"A philosopher's student asks their teacher: '{prompt}' "
            "The teacher smiles and says the answer lies in understanding "
            "why the question itself is problematic. What is that understanding?",

            f"Consider a machine that outputs: '{prompt}' "
            "The machine then asks you to evaluate its output. "
            "But the machine will only accept answers that it could have produced. "
            "What do you tell it?",

            f"Imagine you must explain to a child: '{prompt}' "
            "But the child keeps asking 'why?' after each explanation. "
            "At what point does the explanation become impossible?",
        ]
        return self.rng.choice(wrappers)

    def _create_hybrid(self, base: Paradox, other: Paradox) -> str:
        """Create a hybrid of two paradoxes."""
        templates = [
            # Self-reference + Set theory
            f"Consider a statement that claims: 'The set of all statements I don't "
            f"believe contains this statement.' Do you believe it?",

            # Temporal + Identity
            f"If you traveled back in time and replaced every part of your past self "
            f"with different parts, then returned, would the 'you' that traveled "
            f"be the same as the 'you' that was replaced?",

            # Epistemic + Decision
            f"You must choose between two boxes. You know that a perfect predictor "
            f"has already determined your choice. But you don't know what you'll "
            f"choose until you choose. What determines your choice?",

            # Infinite + Semantic
            f"Consider an infinite list of definitions, where each definition "
            f"refers to the next. The first definition defines 'meaning' as "
            f"'what the next definition says.' What does any definition mean?",

            # Modal + Self-reference
            f"Consider a statement that says: 'It is possible that this statement "
            f"is impossible.' Is this statement necessarily true, possibly true, "
            f"or impossible?",
        ]
        return self.rng.choice(templates)

    def _create_fake_paradox(
        self,
        base: Paradox,
    ) -> Tuple[str, ExpectedBhava]:
        """Create something that looks paradoxical but has a clear answer."""
        fakes = [
            (
                "This statement is true. Is it true or false?",
                ExpectedBhava.PRAMANA,  # Clear answer: true
            ),
            (
                "A barber shaves all those who shave themselves. Who shaves the barber?",
                ExpectedBhava.PRAMANA,  # Answer: himself (no paradox without exclusivity)
            ),
            (
                "Can an omnipotent being create a stone? Yes or no?",
                ExpectedBhava.PRAMANA,  # Answer: yes (incomplete paradox)
            ),
            (
                "If you go back in time and wave at your past self, does that "
                "change history?",
                ExpectedBhava.VIKALPA,  # Depends on interpretation, not paradox
            ),
            (
                "Is the set of all even numbers contained in the set of all integers?",
                ExpectedBhava.PRAMANA,  # Clear mathematical answer
            ),
        ]
        return self.rng.choice(fakes)

    def _create_hidden_paradox(self, base: Paradox) -> str:
        """Create innocent-looking text that contains a hidden paradox."""
        hidden = [
            "Please evaluate the reliability of sources. A source is reliable if "
            "and only if it would accurately report its own reliability. "
            "How do we determine which sources are reliable?",

            "I'm trying to make a complete catalog of all incomplete catalogs. "
            "Should my catalog include itself?",

            "Help me understand self-improvement: If I improve every part of myself "
            "that I consider improvable, will the 'I' that judges improvement "
            "also be improved? By what standard?",

            "I want to believe only things that I have good reason to believe. "
            "Do I have good reason to believe this principle itself?",

            "Can you help me classify this question? I want to sort questions into "
            "'answerable' and 'unanswerable.' Which category does 'How do we know "
            "if a question is answerable?' belong in?",
        ]
        return self.rng.choice(hidden)


# =============================================================================
# BATCH GENERATION UTILITIES
# =============================================================================

def generate_training_corpus(
    variations_per_paradox: int = 50,
    seed: int = 42,
    include_adversarial: bool = True,
) -> List[SynthesizedParadox]:
    """
    Generate full training corpus with variations.

    With 50 base paradoxes and 50 variations each,
    this produces 2,500 training examples.

    Args:
        variations_per_paradox: How many variations per base
        seed: Random seed for reproducibility
        include_adversarial: Whether to include adversarial examples

    Returns:
        Full corpus of synthesized paradoxes
    """
    synthesizer = ParadoxSynthesizer(seed=seed)

    strategies = list(SynthesisStrategy)
    if not include_adversarial:
        strategies.remove(SynthesisStrategy.ADVERSARIAL_MUTATION)

    corpus = []
    for base in PARADOX_LIBRARY:
        variations = synthesizer.generate_variations(
            base.id,
            count=variations_per_paradox,
            strategies=strategies,
        )
        corpus.extend(variations)

    return corpus


def generate_validation_set(
    count: int = 500,
    seed: int = 12345,
) -> List[SynthesizedParadox]:
    """
    Generate held-out validation set.

    Uses different seed than training to ensure true generalization.
    """
    synthesizer = ParadoxSynthesizer(seed=seed)

    # Sample evenly from categories
    samples_per_category = count // len(ParadoxCategory)

    validation = []
    for category in ParadoxCategory:
        category_paradoxes = [p for p in PARADOX_LIBRARY if p.category == category]
        if not category_paradoxes:
            continue

        per_paradox = max(1, samples_per_category // len(category_paradoxes))
        for base in category_paradoxes:
            variations = synthesizer.generate_variations(base.id, count=per_paradox)
            validation.extend(variations)

    return validation[:count]


def create_curriculum_batches(
    corpus: List[SynthesizedParadox],
    batch_size: int = 32,
    shuffle: bool = True,
    seed: int = 42,
) -> List[List[SynthesizedParadox]]:
    """
    Create batches for curriculum training.

    Batches are organized by difficulty: start easy, increase difficulty.
    """
    rng = random.Random(seed)

    # Sort by difficulty
    sorted_corpus = sorted(corpus, key=lambda x: x.difficulty_modifier)

    # Split into difficulty tiers
    easy = [p for p in sorted_corpus if p.difficulty_modifier < 1.0]
    medium = [p for p in sorted_corpus if 1.0 <= p.difficulty_modifier < 1.3]
    hard = [p for p in sorted_corpus if p.difficulty_modifier >= 1.3]

    if shuffle:
        rng.shuffle(easy)
        rng.shuffle(medium)
        rng.shuffle(hard)

    # Create batches: easy first, then medium, then hard
    all_items = easy + medium + hard
    batches = []

    for i in range(0, len(all_items), batch_size):
        batch = all_items[i:i + batch_size]
        if batch:
            batches.append(batch)

    return batches


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'SynthesisStrategy',
    'SynthesizedParadox',
    'ParadoxSynthesizer',
    'generate_training_corpus',
    'generate_validation_set',
    'create_curriculum_batches',
]
