"""
Paraphrase Pair Generator
=========================

Generates paraphrase pairs for embedding training.
Uses semantic similarity to create positive and negative pairs.
"""

import random
from typing import List, Dict, Tuple
from symbolu.training.schemas import ParaphrasePair, QueryIntentPair, IntentLabel


# Paraphrase templates - pairs of semantically equivalent queries
PARAPHRASE_TEMPLATES: List[Tuple[str, str, str]] = [
    # (query_a, query_b, domain)
    ("How do atoms bond?", "What is chemical bonding?", "chemistry"),
    ("How do atoms bond?", "Explain atomic bonds", "chemistry"),
    ("What causes rain?", "Why does it rain?", "weather"),
    ("What causes rain?", "Explain the rain cycle", "weather"),
    ("How does photosynthesis work?", "Explain photosynthesis", "biology"),
    ("How does photosynthesis work?", "What is the process of photosynthesis?", "biology"),
    ("Calculate the derivative", "Find the derivative", "math"),
    ("Calculate the derivative", "What's the derivative of this?", "math"),
    ("I feel sad", "I'm feeling down", "emotional"),
    ("I feel sad", "I'm not happy", "emotional"),
    ("Book a flight", "Reserve a plane ticket", "travel"),
    ("Book a flight", "I need to fly somewhere", "travel"),
    ("Write a poem", "Compose a poem", "creative"),
    ("Write a poem", "Create some poetry", "creative"),
    ("What is the meaning of life?", "Why do we exist?", "philosophy"),
    ("What is the meaning of life?", "What's the purpose of existence?", "philosophy"),
    ("How do I cook pasta?", "What's the recipe for pasta?", "cooking"),
    ("How do I cook pasta?", "Steps to make pasta", "cooking"),
    ("Tell me about Python", "What is Python programming?", "technical"),
    ("Tell me about Python", "Explain Python to me", "technical"),
    ("I'm stressed about work", "Work is stressing me out", "emotional"),
    ("I'm stressed about work", "My job is causing me anxiety", "emotional"),
    ("Schedule a meeting", "Set up a meeting", "productivity"),
    ("Schedule a meeting", "Arrange a meeting time", "productivity"),
    ("Design a logo", "Create a logo", "design"),
    ("Design a logo", "Make a logo for me", "design"),
    ("What happened in WW2?", "Tell me about World War 2", "history"),
    ("What happened in WW2?", "Explain World War II", "history"),
    ("How do neural networks learn?", "What is neural network training?", "ml"),
    ("How do neural networks learn?", "Explain machine learning training", "ml"),
    ("I need relationship advice", "Help with my relationship", "relationship"),
    ("I need relationship advice", "Advice about my partner", "relationship"),
    ("Run the tests", "Execute the test suite", "technical"),
    ("Run the tests", "Start the testing process", "technical"),
    ("Write a story", "Create a narrative", "creative"),
    ("Write a story", "Compose a tale", "creative"),
    ("What is consciousness?", "Define consciousness", "philosophy"),
    ("What is consciousness?", "Explain what consciousness means", "philosophy"),
    ("Fix this bug", "Debug this issue", "technical"),
    ("Fix this bug", "Solve this problem in the code", "technical"),
]

# Dissimilar pairs - semantically different queries
DISSIMILAR_TEMPLATES: List[Tuple[str, str]] = [
    ("How do atoms bond?", "Best pizza recipe"),
    ("What causes rain?", "How to invest money"),
    ("I feel sad", "Calculate the integral"),
    ("Book a flight", "Write a poem about love"),
    ("What is the meaning of life?", "Schedule a meeting"),
    ("How do I cook pasta?", "Explain quantum physics"),
    ("Tell me about Python", "I'm feeling anxious"),
    ("Design a logo", "What happened in WW2?"),
    ("Run the tests", "What is consciousness?"),
    ("Write a story", "How do I fix my car?"),
    ("I need relationship advice", "Deploy to production"),
    ("What is gravity?", "Compose a symphony"),
    ("How does DNA work?", "Best coffee shops in Paris"),
    ("Analyze the data", "I feel overwhelmed"),
    ("Create a painting", "What is blockchain?"),
]


class ParaphrasePairGenerator:
    """
    Generates paraphrase pairs for embedding training.

    Creates both similar (positive) and dissimilar (negative) pairs
    for contrastive learning.

    Usage:
        generator = ParaphrasePairGenerator()
        pairs = generator.generate(count=1000)
    """

    def __init__(self, seed: int = 42):
        """Initialize with random seed for reproducibility."""
        self.random = random.Random(seed)
        self.paraphrase_templates = PARAPHRASE_TEMPLATES
        self.dissimilar_templates = DISSIMILAR_TEMPLATES

    def generate(
        self,
        count: int = 1000,
        similar_ratio: float = 0.6,
    ) -> List[ParaphrasePair]:
        """
        Generate paraphrase pairs.

        Args:
            count: Total number of pairs to generate
            similar_ratio: Ratio of similar pairs (default 60%)

        Returns:
            List of ParaphrasePair objects
        """
        pairs: List[ParaphrasePair] = []
        similar_count = int(count * similar_ratio)
        dissimilar_count = count - similar_count

        # Generate similar pairs
        for _ in range(similar_count):
            pair = self._generate_similar_pair()
            pairs.append(pair)

        # Generate dissimilar pairs
        for _ in range(dissimilar_count):
            pair = self._generate_dissimilar_pair()
            pairs.append(pair)

        self.random.shuffle(pairs)
        return pairs

    def _generate_similar_pair(self) -> ParaphrasePair:
        """Generate a similar (positive) pair."""
        template = self.random.choice(self.paraphrase_templates)
        query_a, query_b, domain = template

        # Apply random variations
        if self.random.random() > 0.5:
            query_a = self._apply_variation(query_a)
        if self.random.random() > 0.5:
            query_b = self._apply_variation(query_b)

        return ParaphrasePair(
            query_a=query_a,
            query_b=query_b,
            similar=True,
            similarity_score=self.random.uniform(0.8, 1.0),
            source="synthetic",
            metadata={"domain": domain},
        )

    def _generate_dissimilar_pair(self) -> ParaphrasePair:
        """Generate a dissimilar (negative) pair."""
        template = self.random.choice(self.dissimilar_templates)
        query_a, query_b = template

        # Apply random variations
        if self.random.random() > 0.5:
            query_a = self._apply_variation(query_a)
        if self.random.random() > 0.5:
            query_b = self._apply_variation(query_b)

        return ParaphrasePair(
            query_a=query_a,
            query_b=query_b,
            similar=False,
            similarity_score=self.random.uniform(0.0, 0.3),
            source="synthetic",
            metadata={},
        )

    def _apply_variation(self, query: str) -> str:
        """Apply a random variation to a query."""
        variations = [
            self._add_question_mark,
            self._lowercase,
            self._add_please,
            self._add_context,
        ]
        variation = self.random.choice(variations)
        return variation(query)

    def _add_question_mark(self, query: str) -> str:
        """Ensure query ends with question mark if it's a question."""
        if not query.endswith("?") and any(
            query.lower().startswith(w) for w in ["how", "what", "why", "when", "where", "who"]
        ):
            return query + "?"
        return query

    def _lowercase(self, query: str) -> str:
        """Convert to lowercase."""
        return query.lower()

    def _add_please(self, query: str) -> str:
        """Add please to the query."""
        return "Please " + query.lower()

    def _add_context(self, query: str) -> str:
        """Add context prefix."""
        contexts = ["I need to know: ", "Can you help with: ", "Question: "]
        return self.random.choice(contexts) + query

    def generate_from_intent_pairs(
        self,
        intent_pairs: List[QueryIntentPair],
        pairs_per_query: int = 5,
    ) -> List[ParaphrasePair]:
        """
        Generate paraphrase pairs from intent pairs.

        Creates similar pairs from same-intent queries and
        dissimilar pairs from different-intent queries.

        Args:
            intent_pairs: List of QueryIntentPair objects
            pairs_per_query: Number of pairs to generate per query

        Returns:
            List of ParaphrasePair objects
        """
        pairs: List[ParaphrasePair] = []

        # Group by intent
        by_intent: Dict[IntentLabel, List[QueryIntentPair]] = {}
        for pair in intent_pairs:
            if pair.intent not in by_intent:
                by_intent[pair.intent] = []
            by_intent[pair.intent].append(pair)

        # Generate pairs
        for intent, intent_queries in by_intent.items():
            if len(intent_queries) < 2:
                continue

            for query_pair in intent_queries:
                # Generate similar pairs (same intent)
                similar_candidates = [q for q in intent_queries if q != query_pair]
                if similar_candidates:
                    for _ in range(min(pairs_per_query // 2, len(similar_candidates))):
                        other = self.random.choice(similar_candidates)
                        pairs.append(ParaphrasePair(
                            query_a=query_pair.query,
                            query_b=other.query,
                            similar=True,
                            similarity_score=0.9,
                            source="derived",
                            metadata={"intent": intent.value},
                        ))

                # Generate dissimilar pairs (different intent)
                other_intents = [i for i in by_intent.keys() if i != intent]
                for _ in range(pairs_per_query // 2):
                    if other_intents:
                        other_intent = self.random.choice(other_intents)
                        if by_intent[other_intent]:
                            other = self.random.choice(by_intent[other_intent])
                            pairs.append(ParaphrasePair(
                                query_a=query_pair.query,
                                query_b=other.query,
                                similar=False,
                                similarity_score=0.2,
                                source="derived",
                                metadata={
                                    "intent_a": intent.value,
                                    "intent_b": other_intent.value,
                                },
                            ))

        self.random.shuffle(pairs)
        return pairs
