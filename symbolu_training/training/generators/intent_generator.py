"""
Intent Pair Generator
=====================

Generates query-intent pairs for router training.
Uses templates and variations to create diverse training data.
"""

import random
from typing import List, Dict, Tuple
from symbolu_training.training.schemas import QueryIntentPair, IntentLabel


# Template-based query generation
# Each intent has templates with placeholders
INTENT_TEMPLATES: Dict[IntentLabel, List[Tuple[str, str]]] = {
    IntentLabel.REASONING: [
        ("Calculate {math_op} of {numbers}", "math"),
        ("How does {scientific_concept} work?", "science"),
        ("Explain the relationship between {concept_a} and {concept_b}", "science"),
        ("What is the logical flaw in {argument}?", "logic"),
        ("Solve this problem: {problem}", "math"),
        ("Why does {phenomenon} happen?", "science"),
        ("What causes {effect}?", "science"),
        ("Analyze the {subject} data", "analysis"),
        ("Compare {option_a} vs {option_b}", "analysis"),
        ("What's the best approach for {technical_task}?", "technical"),
        ("Debug this {code_issue}", "technical"),
        ("Optimize {system} for {goal}", "technical"),
        ("Prove that {statement}", "logic"),
        ("What are the implications of {decision}?", "analysis"),
        ("How would you approach {complex_problem}?", "problem_solving"),
    ],
    IntentLabel.RELATIONSHIP: [
        ("I feel {emotion} about {situation}", "emotional"),
        ("How do I deal with {relationship_issue}?", "relationship"),
        ("My {person} doesn't understand me", "relationship"),
        ("I'm struggling with {emotional_challenge}", "emotional"),
        ("How can I improve my relationship with {person}?", "relationship"),
        ("I need support with {personal_issue}", "emotional"),
        ("Why do I feel {negative_emotion}?", "emotional"),
        ("How do I express {feeling} to {person}?", "communication"),
        ("I'm worried about {concern}", "emotional"),
        ("Help me understand my feelings about {topic}", "emotional"),
        ("How do I build trust with {person}?", "relationship"),
        ("I feel disconnected from {group}", "social"),
        ("How do I cope with {loss_or_change}?", "emotional"),
        ("I need advice about {personal_dilemma}", "advice"),
        ("How do I set boundaries with {person}?", "relationship"),
    ],
    IntentLabel.ACTION: [
        ("Book a {reservation_type} for {date}", "travel"),
        ("Send an email to {recipient} about {topic}", "communication"),
        ("Create a {document_type} for {purpose}", "productivity"),
        ("Schedule a meeting with {participants}", "productivity"),
        ("Order {item} from {source}", "shopping"),
        ("Set a reminder for {task} at {time}", "productivity"),
        ("Run the {script_name} script", "technical"),
        ("Deploy {application} to {environment}", "technical"),
        ("Update {system} with {changes}", "technical"),
        ("Execute {command} on {target}", "technical"),
        ("Install {software} on {device}", "technical"),
        ("Backup {data} to {location}", "technical"),
        ("Start the {process}", "operations"),
        ("Stop the {service}", "operations"),
        ("Make a reservation at {place}", "booking"),
    ],
    IntentLabel.CREATIVE: [
        ("Write a {genre} story about {theme}", "writing"),
        ("Compose a {style} poem about {subject}", "poetry"),
        ("Design a {design_type} for {purpose}", "design"),
        ("Create a {art_form} inspired by {inspiration}", "art"),
        ("Generate ideas for {creative_project}", "brainstorming"),
        ("Write lyrics for a song about {topic}", "music"),
        ("Imagine a world where {premise}", "worldbuilding"),
        ("Describe {scene} in vivid detail", "descriptive"),
        ("Create a character who {trait}", "character"),
        ("Write a dialogue between {character_a} and {character_b}", "dialogue"),
        ("Invent a new {invention_type}", "invention"),
        ("Compose a {musical_form} in {style}", "music"),
        ("Design a logo for {brand}", "design"),
        ("Write a {format} about {topic}", "writing"),
        ("Create a metaphor for {abstract_concept}", "literary"),
    ],
    IntentLabel.REFLECTIVE: [
        ("What is the meaning of {philosophical_concept}?", "philosophy"),
        ("Why do we {human_behavior}?", "philosophy"),
        ("What does it mean to {abstract_action}?", "existential"),
        ("How should I think about {life_question}?", "philosophy"),
        ("What is the nature of {abstract_noun}?", "philosophy"),
        ("Reflect on the concept of {concept}", "contemplation"),
        ("What can we learn from {historical_event}?", "wisdom"),
        ("How do different cultures view {topic}?", "cultural"),
        ("What is the purpose of {activity}?", "existential"),
        ("Contemplate {deep_question}", "contemplation"),
        ("What wisdom is there in {saying}?", "wisdom"),
        ("How has {concept} evolved over time?", "historical"),
        ("What does {quote} really mean?", "interpretation"),
        ("Explore the paradox of {paradox}", "philosophy"),
        ("What is truth in the context of {domain}?", "epistemology"),
    ],
    IntentLabel.GENERAL: [
        ("Tell me about {topic}", "general"),
        ("What is {thing}?", "definition"),
        ("Who was {person}?", "biography"),
        ("When did {event} happen?", "history"),
        ("Where is {place}?", "geography"),
        ("How do you {action}?", "how_to"),
        ("What's the weather like in {location}?", "weather"),
        ("What time is it in {timezone}?", "time"),
        ("Give me some facts about {subject}", "facts"),
        ("Summarize {content}", "summary"),
        ("Translate {text} to {language}", "translation"),
        ("Define {term}", "definition"),
        ("List {items} for {purpose}", "list"),
        ("What are examples of {category}?", "examples"),
        ("Help me with {vague_request}", "general"),
    ],
}

# Fillers for template placeholders
FILLERS: Dict[str, List[str]] = {
    "math_op": ["the integral", "the derivative", "the sum", "the product", "the factorial"],
    "numbers": ["1 to 100", "prime numbers", "these values", "the sequence"],
    "scientific_concept": ["quantum entanglement", "photosynthesis", "gravity", "DNA replication", "neural networks"],
    "concept_a": ["mass", "energy", "time", "entropy", "consciousness"],
    "concept_b": ["space", "matter", "velocity", "information", "behavior"],
    "argument": ["this statement", "the thesis", "the hypothesis", "the claim"],
    "problem": ["2x + 5 = 15", "finding the optimal path", "minimizing cost", "the traveling salesman"],
    "phenomenon": ["the aurora", "tidal waves", "earthquakes", "lightning"],
    "effect": ["climate change", "inflation", "population growth", "urbanization"],
    "subject": ["sales", "user engagement", "performance", "market"],
    "option_a": ["Python", "React", "AWS", "PostgreSQL", "microservices"],
    "option_b": ["JavaScript", "Vue", "Azure", "MongoDB", "monolith"],
    "technical_task": ["scaling the system", "improving latency", "reducing costs", "debugging"],
    "code_issue": ["memory leak", "race condition", "null pointer", "infinite loop"],
    "system": ["the database", "the API", "the cache", "the pipeline"],
    "goal": ["speed", "reliability", "cost efficiency", "security"],
    "statement": ["P implies Q", "the theorem holds", "the algorithm is correct"],
    "decision": ["this change", "the merger", "the policy", "the investment"],
    "complex_problem": ["distributed consensus", "resource allocation", "optimization"],

    "emotion": ["anxious", "sad", "confused", "overwhelmed", "hopeful", "frustrated"],
    "situation": ["my job", "my relationship", "this decision", "my future"],
    "relationship_issue": ["trust issues", "communication problems", "growing apart", "conflicts"],
    "person": ["my partner", "my parent", "my friend", "my boss", "my sibling"],
    "emotional_challenge": ["loneliness", "grief", "anxiety", "self-doubt", "anger"],
    "negative_emotion": ["empty", "lost", "stuck", "broken", "alone"],
    "feeling": ["gratitude", "love", "frustration", "disappointment", "appreciation"],
    "concern": ["my health", "my career", "my family", "the future"],
    "topic": ["change", "commitment", "success", "failure", "love"],
    "group": ["my family", "my friends", "my community", "my team"],
    "loss_or_change": ["a breakup", "job loss", "moving", "loss of a loved one"],
    "personal_dilemma": ["career vs family", "staying vs leaving", "honesty vs kindness"],

    "reservation_type": ["flight", "hotel", "restaurant", "car rental", "appointment"],
    "date": ["tomorrow", "next week", "March 15th", "this weekend"],
    "recipient": ["John", "the team", "HR", "the client", "support"],
    "document_type": ["report", "presentation", "spreadsheet", "proposal", "contract"],
    "purpose": ["the meeting", "the project", "the review", "the deadline"],
    "participants": ["the team", "stakeholders", "leadership", "engineering"],
    "item": ["supplies", "equipment", "groceries", "parts"],
    "source": ["Amazon", "the vendor", "the store", "online"],
    "task": ["the meeting", "the deadline", "the call", "the payment"],
    "time": ["3 PM", "tomorrow morning", "next Monday", "in an hour"],
    "script_name": ["deploy", "backup", "test", "cleanup", "migrate"],
    "application": ["the app", "the service", "the website", "the API"],
    "environment": ["production", "staging", "development", "testing"],
    "changes": ["the new features", "bug fixes", "the update", "patches"],
    "command": ["restart", "status check", "health check", "rotate logs"],
    "target": ["the server", "the cluster", "the container", "the VM"],
    "software": ["Docker", "Node.js", "Python", "the package"],
    "device": ["my laptop", "the server", "the phone", "the tablet"],
    "data": ["the database", "user files", "logs", "configurations"],
    "location": ["the cloud", "the backup drive", "S3", "the NAS"],
    "process": ["the server", "the job", "the workflow", "the batch"],
    "service": ["the API", "the worker", "the scheduler", "nginx"],
    "place": ["the restaurant", "the hotel", "the venue", "the spa"],

    "genre": ["fantasy", "mystery", "romance", "sci-fi", "horror", "comedy"],
    "theme": ["redemption", "love", "adventure", "betrayal", "discovery"],
    "style": ["haiku", "sonnet", "free verse", "limerick", "ballad"],
    "design_type": ["logo", "website", "poster", "UI", "icon"],
    "art_form": ["painting", "sculpture", "photograph", "illustration"],
    "inspiration": ["nature", "technology", "emotions", "history", "dreams"],
    "creative_project": ["a novel", "a game", "a brand", "a film", "a startup"],
    "scene": ["a sunset over the ocean", "a bustling city", "a quiet forest"],
    "trait": ["overcomes fear", "seeks truth", "loves deeply", "fights injustice"],
    "character_a": ["a wizard", "a detective", "an AI", "a rebel"],
    "character_b": ["a dragon", "a victim", "a human", "an authority"],
    "invention_type": ["gadget", "app", "material", "transportation method"],
    "musical_form": ["symphony", "jazz piece", "electronic track", "folk song"],
    "format": ["essay", "script", "blog post", "short story", "monologue"],
    "abstract_concept": ["time", "love", "freedom", "death", "hope"],
    "brand": ["a tech startup", "a cafe", "a fitness brand", "a nonprofit"],

    "philosophical_concept": ["consciousness", "free will", "justice", "beauty", "ethics"],
    "human_behavior": ["seek meaning", "form groups", "create art", "fear death"],
    "abstract_action": ["be authentic", "find purpose", "achieve happiness"],
    "life_question": ["death", "suffering", "success", "failure", "purpose"],
    "abstract_noun": ["time", "reality", "consciousness", "existence"],
    "concept": ["identity", "morality", "truth", "knowledge", "wisdom"],
    "historical_event": ["the Renaissance", "World War II", "the Industrial Revolution"],
    "activity": ["work", "art", "science", "religion", "philosophy"],
    "deep_question": ["why we exist", "what happens after death", "the nature of self"],
    "saying": ["know thyself", "this too shall pass", "all is one"],
    "paradox": ["free will vs determinism", "the ship of Theseus", "Zeno's arrow"],
    "domain": ["science", "religion", "philosophy", "art", "politics"],
    "quote": ["I think therefore I am", "God is dead", "The unexamined life"],

    "thing": ["blockchain", "machine learning", "quantum computing", "CRISPR"],
    "event": ["the moon landing", "the French Revolution", "the Big Bang"],
    "location": ["Tokyo", "Paris", "New York", "remote places"],
    "timezone": ["EST", "PST", "GMT", "JST"],
    "action": ["make pasta", "tie a tie", "change a tire", "meditate"],
    "content": ["this article", "the chapter", "the meeting notes", "the report"],
    "text": ["hello world", "this sentence", "the document"],
    "language": ["Spanish", "French", "Japanese", "German", "Chinese"],
    "term": ["ontology", "epistemology", "hermeneutics", "phenomenology"],
    "items": ["tools", "resources", "steps", "ingredients", "tips"],
    "category": ["programming languages", "cognitive biases", "logical fallacies"],
    "vague_request": ["something", "this thing", "my question", "what I need"],
}


class IntentPairGenerator:
    """
    Generates query-intent pairs for router training.

    Usage:
        generator = IntentPairGenerator()
        pairs = generator.generate(count=1000)
    """

    def __init__(self, seed: int = 42):
        """Initialize with random seed for reproducibility."""
        self.random = random.Random(seed)
        self.templates = INTENT_TEMPLATES
        self.fillers = FILLERS

    def generate(self, count: int = 1000, balanced: bool = True) -> List[QueryIntentPair]:
        """
        Generate query-intent pairs.

        Args:
            count: Total number of pairs to generate
            balanced: If True, generate equal amounts per intent

        Returns:
            List of QueryIntentPair objects
        """
        pairs: List[QueryIntentPair] = []
        intents = list(IntentLabel)

        if balanced:
            per_intent = count // len(intents)
            for intent in intents:
                for _ in range(per_intent):
                    pair = self._generate_pair(intent)
                    pairs.append(pair)
            # Fill remaining with random intents
            remaining = count - len(pairs)
            for _ in range(remaining):
                intent = self.random.choice(intents)
                pairs.append(self._generate_pair(intent))
        else:
            for _ in range(count):
                intent = self.random.choice(intents)
                pairs.append(self._generate_pair(intent))

        self.random.shuffle(pairs)
        return pairs

    def _generate_pair(self, intent: IntentLabel) -> QueryIntentPair:
        """Generate a single query-intent pair."""
        templates = self.templates[intent]
        template, domain = self.random.choice(templates)

        # Fill placeholders
        query = self._fill_template(template)

        return QueryIntentPair(
            query=query,
            intent=intent,
            domain=domain,
            confidence=1.0,
            source="synthetic",
            metadata={"template": template},
        )

    def _fill_template(self, template: str) -> str:
        """Fill placeholders in a template."""
        result = template
        # Find all placeholders
        import re
        placeholders = re.findall(r'\{(\w+)\}', template)

        for placeholder in placeholders:
            if placeholder in self.fillers:
                value = self.random.choice(self.fillers[placeholder])
                result = result.replace(f"{{{placeholder}}}", value, 1)
            else:
                # Unknown placeholder, use generic filler
                result = result.replace(f"{{{placeholder}}}", "something", 1)

        return result

    def generate_variations(
        self,
        base_pairs: List[QueryIntentPair],
        variations_per_pair: int = 3,
    ) -> List[QueryIntentPair]:
        """
        Generate variations of existing pairs for data augmentation.

        Args:
            base_pairs: Original pairs to augment
            variations_per_pair: Number of variations per pair

        Returns:
            List of augmented QueryIntentPair objects
        """
        augmented: List[QueryIntentPair] = []

        for pair in base_pairs:
            for _ in range(variations_per_pair):
                variation = self._create_variation(pair)
                augmented.append(variation)

        return augmented

    def _create_variation(self, pair: QueryIntentPair) -> QueryIntentPair:
        """Create a variation of a query by applying transformations."""
        query = pair.query
        transformations = [
            self._add_politeness,
            self._add_context,
            self._rephrase_question,
            self._add_urgency,
        ]

        transform = self.random.choice(transformations)
        new_query = transform(query)

        return QueryIntentPair(
            query=new_query,
            intent=pair.intent,
            domain=pair.domain,
            confidence=0.9,  # Slightly lower confidence for augmented
            source="augmented",
            metadata={"original": pair.query, "transform": transform.__name__},
        )

    def _add_politeness(self, query: str) -> str:
        """Add polite prefix/suffix."""
        prefixes = ["Could you please ", "Would you mind ", "I'd appreciate if you could ", "Please "]
        suffixes = [", please?", ", if possible.", ", thanks!", ""]
        prefix = self.random.choice(prefixes)
        suffix = self.random.choice(suffixes)
        return prefix + query.lower() + suffix

    def _add_context(self, query: str) -> str:
        """Add context to the query."""
        contexts = [
            "I'm working on a project and I need to know: ",
            "For my research, ",
            "I've been thinking about this: ",
            "Quick question: ",
            "I'm curious about something: ",
        ]
        return self.random.choice(contexts) + query

    def _rephrase_question(self, query: str) -> str:
        """Rephrase as a different question type."""
        if query.startswith("How"):
            return query.replace("How", "What's the way to", 1)
        elif query.startswith("What"):
            return query.replace("What", "Can you tell me what", 1)
        elif query.startswith("Why"):
            return query.replace("Why", "What's the reason", 1)
        return "Can you help with: " + query

    def _add_urgency(self, query: str) -> str:
        """Add urgency to the query."""
        urgencies = [
            "Urgently need to know: ",
            "This is important: ",
            "Quick question - ",
            "Need help ASAP: ",
        ]
        return self.random.choice(urgencies) + query
