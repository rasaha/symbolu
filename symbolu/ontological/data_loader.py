"""
Ontological Engine - Data Loaders
==================================

Data loading utilities for training the ontological engine:
1. RAGDataLoader: Load training data from RAG database
2. DatasetGenerator: Generate synthetic training data
3. MixedDataLoader: Combine multiple data sources

Supports labeling based on:
- Domain tags (technical → O6, creative → O2, etc.)
- Content analysis
- Manual annotations
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Iterator
from dataclasses import dataclass, field

from symbolu.ontological.types import TrainingExample, TaskType, LAYER_NAMES


# Domain to ontological layer mappings
DOMAIN_TO_LAYERS: Dict[str, Dict[str, float]] = {
    # Technical/Reasoning domains
    "technical": {"O6_REASONING": 0.8, "O1_THINKING": 0.6, "O8_META_OBSERVING": 0.5},
    "api-reference": {"O6_REASONING": 0.9, "O3_ACTING": 0.7},
    "architecture": {"O6_REASONING": 0.8, "O2_FORMING": 0.6, "O1_THINKING": 0.7},
    "deployment": {"O3_ACTING": 0.8, "O5_DIRECTING": 0.7},
    "troubleshooting": {"O6_REASONING": 0.7, "O3_ACTING": 0.6},

    # Governance/Ethics domains
    "ai-governance": {"O6_REASONING": 0.7, "O7_PURPOSING": 0.8, "O8_META_OBSERVING": 0.7},
    "responsible-ai": {"O7_PURPOSING": 0.9, "O9_UNIFYING": 0.7, "O8_META_OBSERVING": 0.6},
    "ethics": {"O1_THINKING": 0.8, "O7_PURPOSING": 0.8, "O9_UNIFYING": 0.6},
    "compliance": {"O5_DIRECTING": 0.8, "O6_REASONING": 0.7},

    # Creative domains
    "creative": {"O2_FORMING": 0.9, "O9_UNIFYING": 0.6},
    "design": {"O2_FORMING": 0.8, "O7_PURPOSING": 0.6},
    "writing": {"O2_FORMING": 0.8, "O4_TAGGING": 0.5},

    # Action domains
    "procedural": {"O3_ACTING": 0.9, "O5_DIRECTING": 0.7},
    "instructions": {"O5_DIRECTING": 0.8, "O3_ACTING": 0.7},

    # Default
    "general": {"O1_THINKING": 0.5},
}

# Tag to task type mappings
TAG_TO_TASK: Dict[str, TaskType] = {
    "reasoning": TaskType.REASONING,
    "logic": TaskType.REASONING,
    "analysis": TaskType.REASONING,
    "proof": TaskType.REASONING,
    "creative": TaskType.CREATIVITY,
    "art": TaskType.CREATIVITY,
    "design": TaskType.CREATIVITY,
    "poetry": TaskType.CREATIVITY,
    "action": TaskType.ACTION,
    "procedure": TaskType.ACTION,
    "execute": TaskType.ACTION,
    "reflection": TaskType.REFLECTION,
    "philosophy": TaskType.REFLECTION,
    "meaning": TaskType.REFLECTION,
}


@dataclass
class RAGDocument:
    """A document from the RAG database."""
    id: str
    title: str
    domain: str
    tags: List[str]
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "RAGDocument":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            domain=data.get("domain", "general"),
            tags=data.get("tags", []),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
        )


class RAGDataLoader:
    """
    Load training data from the RAG database.

    Automatically assigns ontological labels based on:
    - Document domain (technical, creative, governance)
    - Content tags
    - Keyword patterns

    Usage:
        loader = RAGDataLoader("data/rag")
        examples = loader.load_all()
        train, val = loader.split(examples, val_ratio=0.2)
    """

    def __init__(
        self,
        rag_dir: str = "data/rag",
        chunk_size: int = 512,
        overlap: int = 64,
    ):
        self.rag_dir = Path(rag_dir)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def load_all(self) -> List[TrainingExample]:
        """Load all RAG documents as training examples."""
        examples = []

        # Find all JSON files in RAG directory
        for json_file in self.rag_dir.rglob("*.json"):
            try:
                doc_examples = self._load_document(json_file)
                examples.extend(doc_examples)
            except Exception as e:
                print(f"Error loading {json_file}: {e}")

        print(f"Loaded {len(examples)} training examples from RAG database")
        return examples

    def _load_document(self, path: Path) -> List[TrainingExample]:
        """Load a single document and create training examples."""
        with open(path, "r") as f:
            data = json.load(f)

        doc = RAGDocument.from_json(data)
        examples = []

        # Chunk the content
        chunks = self._chunk_text(doc.content)

        for i, chunk in enumerate(chunks):
            # Determine labels from domain and tags
            dimension_labels = self._get_dimension_labels(doc)
            task_type = self._get_task_type(doc)
            reasoning_label = self._get_reasoning_label(doc, chunk)
            creativity_label = self._get_creativity_label(doc, chunk)

            example = TrainingExample(
                text=chunk,
                dimension_labels=dimension_labels,
                task_type=task_type,
                reasoning_label=reasoning_label,
                creativity_label=creativity_label,
                source=f"rag:{doc.domain}/{doc.id}:{i}",
            )
            examples.append(example)

        return examples

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind(".")
                last_newline = chunk.rfind("\n")
                break_point = max(last_period, last_newline)
                if break_point > self.chunk_size // 2:
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1

            chunks.append(chunk.strip())
            start = end - self.overlap

        return chunks

    def _get_dimension_labels(self, doc: RAGDocument) -> Dict[str, float]:
        """Get ontological dimension labels from document metadata."""
        labels = {}

        # Start with domain-based labels
        if doc.domain in DOMAIN_TO_LAYERS:
            labels.update(DOMAIN_TO_LAYERS[doc.domain])

        # Add tag-based labels
        for tag in doc.tags:
            tag_lower = tag.lower()
            if tag_lower in DOMAIN_TO_LAYERS:
                for layer, score in DOMAIN_TO_LAYERS[tag_lower].items():
                    if layer not in labels or score > labels[layer]:
                        labels[layer] = score

        return labels if labels else {"O1_THINKING": 0.5}

    def _get_task_type(self, doc: RAGDocument) -> Optional[TaskType]:
        """Determine task type from tags."""
        for tag in doc.tags:
            tag_lower = tag.lower()
            if tag_lower in TAG_TO_TASK:
                return TAG_TO_TASK[tag_lower]
        return None

    def _get_reasoning_label(self, doc: RAGDocument, chunk: str) -> Optional[float]:
        """Estimate reasoning label from content."""
        reasoning_keywords = [
            "therefore", "because", "implies", "conclude",
            "reason", "logic", "proof", "derive", "infer",
            "if-then", "hence", "thus", "analysis",
        ]

        chunk_lower = chunk.lower()
        matches = sum(1 for kw in reasoning_keywords if kw in chunk_lower)

        if doc.domain in ["technical", "api-reference", "architecture"]:
            return min(0.5 + matches * 0.1, 0.95)
        elif matches > 0:
            return min(0.3 + matches * 0.1, 0.8)

        return None

    def _get_creativity_label(self, doc: RAGDocument, chunk: str) -> Optional[float]:
        """Estimate creativity label from content."""
        creative_keywords = [
            "imagine", "create", "design", "art", "beauty",
            "metaphor", "vision", "inspire", "novel", "innovative",
            "aesthetic", "express", "compose", "craft",
        ]

        chunk_lower = chunk.lower()
        matches = sum(1 for kw in creative_keywords if kw in chunk_lower)

        if doc.domain in ["creative", "design", "writing"]:
            return min(0.5 + matches * 0.1, 0.95)
        elif matches > 0:
            return min(0.2 + matches * 0.1, 0.7)

        return None

    def split(
        self,
        examples: List[TrainingExample],
        val_ratio: float = 0.2,
        seed: int = 42,
    ) -> Tuple[List[TrainingExample], List[TrainingExample]]:
        """Split examples into train and validation sets."""
        rng = random.Random(seed)
        shuffled = list(examples)
        rng.shuffle(shuffled)

        split_idx = int(len(shuffled) * (1 - val_ratio))
        return shuffled[:split_idx], shuffled[split_idx:]


class SyntheticDataGenerator:
    """
    Generate synthetic training data for ontological learning.

    Creates examples with known ontological properties for:
    - Reasoning (logical statements, proofs)
    - Creativity (metaphors, imagery)
    - Action (procedures, instructions)
    - Reflection (philosophical questions)
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

        # Templates for each category
        self.reasoning_templates = [
            "If {premise1}, and {premise2}, then we can conclude {conclusion}.",
            "The evidence suggests that {hypothesis} because {evidence}.",
            "By analyzing {subject}, we can deduce that {deduction}.",
            "Given that {assumption}, it follows logically that {result}.",
            "The proof demonstrates that {theorem} through {method}.",
        ]

        self.creativity_templates = [
            "{subject} dances like {metaphor} in the {context}.",
            "Imagine a world where {scenario} creates {outcome}.",
            "The {art_form} weaves {elements} into {creation}.",
            "Colors of {subject} paint {emotion} across {canvas}.",
            "In the garden of {domain}, {concept} blooms as {metaphor}.",
        ]

        self.action_templates = [
            "First, {step1}. Then, {step2}. Finally, {step3}.",
            "To {goal}, execute the following: {procedure}.",
            "Run {command} to {achieve} the {outcome}.",
            "Deploy {resource} by {method} before {deadline}.",
            "Initialize {system} with {parameters} for {purpose}.",
        ]

        self.reflection_templates = [
            "What is the nature of {concept} in the context of {domain}?",
            "The meaning of {subject} reveals itself through {lens}.",
            "Contemplating {topic} leads us to question {assumption}.",
            "In seeking {truth}, we discover that {insight}.",
            "The essence of {being} transcends {limitation}.",
        ]

    def generate_reasoning(self, n: int = 100) -> List[TrainingExample]:
        """Generate reasoning-focused examples."""
        examples = []
        for _ in range(n):
            template = self.rng.choice(self.reasoning_templates)
            text = self._fill_template(template, "reasoning")

            examples.append(TrainingExample(
                text=text,
                dimension_labels={"O6_REASONING": 0.9, "O1_THINKING": 0.7},
                task_type=TaskType.REASONING,
                reasoning_label=0.9,
                source="synthetic:reasoning",
            ))
        return examples

    def generate_creativity(self, n: int = 100) -> List[TrainingExample]:
        """Generate creativity-focused examples."""
        examples = []
        for _ in range(n):
            template = self.rng.choice(self.creativity_templates)
            text = self._fill_template(template, "creativity")

            examples.append(TrainingExample(
                text=text,
                dimension_labels={"O2_FORMING": 0.9, "O9_UNIFYING": 0.6},
                task_type=TaskType.CREATIVITY,
                creativity_label=0.9,
                source="synthetic:creativity",
            ))
        return examples

    def generate_action(self, n: int = 100) -> List[TrainingExample]:
        """Generate action-focused examples."""
        examples = []
        for _ in range(n):
            template = self.rng.choice(self.action_templates)
            text = self._fill_template(template, "action")

            examples.append(TrainingExample(
                text=text,
                dimension_labels={"O3_ACTING": 0.9, "O5_DIRECTING": 0.7},
                task_type=TaskType.ACTION,
                source="synthetic:action",
            ))
        return examples

    def generate_reflection(self, n: int = 100) -> List[TrainingExample]:
        """Generate reflection-focused examples."""
        examples = []
        for _ in range(n):
            template = self.rng.choice(self.reflection_templates)
            text = self._fill_template(template, "reflection")

            examples.append(TrainingExample(
                text=text,
                dimension_labels={"O1_THINKING": 0.9, "O8_META_OBSERVING": 0.7},
                task_type=TaskType.REFLECTION,
                source="synthetic:reflection",
            ))
        return examples

    def generate_mixed(self, n: int = 400) -> List[TrainingExample]:
        """Generate balanced mix of all categories."""
        per_category = n // 4
        examples = (
            self.generate_reasoning(per_category) +
            self.generate_creativity(per_category) +
            self.generate_action(per_category) +
            self.generate_reflection(per_category)
        )
        self.rng.shuffle(examples)
        return examples

    def _fill_template(self, template: str, category: str) -> str:
        """Fill template placeholders with random content."""
        fillers = {
            "reasoning": {
                "premise1": ["A is true", "the hypothesis holds", "X implies Y"],
                "premise2": ["B follows from A", "the data supports it", "Y implies Z"],
                "conclusion": ["C must be true", "the theory is valid", "X implies Z"],
                "hypothesis": ["the model is accurate", "the pattern exists"],
                "evidence": ["statistical analysis", "experimental results"],
                "subject": ["the data", "the system", "the algorithm"],
                "deduction": ["efficiency improves", "accuracy increases"],
                "assumption": ["inputs are valid", "the system is stable"],
                "result": ["outputs are correct", "the proof holds"],
                "theorem": ["convergence is guaranteed", "uniqueness exists"],
                "method": ["induction", "contradiction", "construction"],
            },
            "creativity": {
                "subject": ["time", "memory", "hope", "shadows", "dreams"],
                "metaphor": ["starlight", "whispered secrets", "autumn leaves"],
                "context": ["twilight", "morning mist", "forgotten garden"],
                "scenario": ["colors sing", "numbers dance", "silence speaks"],
                "outcome": ["new understanding", "unexpected beauty"],
                "art_form": ["poem", "painting", "symphony", "story"],
                "elements": ["emotion and logic", "light and shadow"],
                "creation": ["a masterpiece", "pure expression"],
                "emotion": ["melancholy", "joy", "wonder"],
                "canvas": ["consciousness", "the universe"],
                "domain": ["imagination", "possibility"],
                "concept": ["an idea", "a vision"],
            },
            "action": {
                "step1": ["initialize the system", "prepare the environment"],
                "step2": ["execute the command", "process the data"],
                "step3": ["verify the results", "cleanup resources"],
                "goal": ["deploy successfully", "optimize performance"],
                "procedure": ["the standard protocol", "the automated script"],
                "command": ["the build script", "the deployment pipeline"],
                "achieve": ["complete", "accomplish"],
                "outcome": ["desired state", "expected result"],
                "resource": ["the service", "the container"],
                "method": ["following best practices", "using automation"],
                "deadline": ["the release date", "the sprint end"],
                "system": ["the application", "the database"],
                "parameters": ["default settings", "custom configuration"],
                "purpose": ["production use", "testing"],
            },
            "reflection": {
                "concept": ["consciousness", "existence", "truth", "meaning"],
                "domain": ["human experience", "knowledge", "reality"],
                "subject": ["life", "purpose", "identity"],
                "lens": ["contemplation", "experience", "inquiry"],
                "topic": ["our assumptions", "fundamental questions"],
                "assumption": ["what we take for granted"],
                "truth": ["understanding", "wisdom", "clarity"],
                "insight": ["complexity underlies simplicity"],
                "being": ["existence", "awareness", "self"],
                "limitation": ["mere perception", "finite understanding"],
            },
        }

        cat_fillers = fillers.get(category, {})
        result = template

        for key, options in cat_fillers.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, self.rng.choice(options), 1)

        return result


class MixedDataLoader:
    """
    Combine multiple data sources for training.

    Usage:
        loader = MixedDataLoader()
        loader.add_rag("data/rag")
        loader.add_synthetic(500)
        examples = loader.get_all()
    """

    def __init__(self):
        self.examples: List[TrainingExample] = []

    def add_rag(
        self,
        rag_dir: str = "data/rag",
        chunk_size: int = 512,
    ) -> "MixedDataLoader":
        """Add RAG database examples."""
        loader = RAGDataLoader(rag_dir, chunk_size=chunk_size)
        self.examples.extend(loader.load_all())
        return self

    def add_synthetic(
        self,
        n: int = 400,
        seed: int = 42,
    ) -> "MixedDataLoader":
        """Add synthetic examples."""
        generator = SyntheticDataGenerator(seed=seed)
        self.examples.extend(generator.generate_mixed(n))
        return self

    def add_custom(
        self,
        examples: List[TrainingExample],
    ) -> "MixedDataLoader":
        """Add custom examples."""
        self.examples.extend(examples)
        return self

    def get_all(self) -> List[TrainingExample]:
        """Get all loaded examples."""
        return self.examples

    def split(
        self,
        val_ratio: float = 0.2,
        seed: int = 42,
    ) -> Tuple[List[TrainingExample], List[TrainingExample]]:
        """Split into train and validation sets."""
        rng = random.Random(seed)
        shuffled = list(self.examples)
        rng.shuffle(shuffled)

        split_idx = int(len(shuffled) * (1 - val_ratio))
        return shuffled[:split_idx], shuffled[split_idx:]

    def __len__(self) -> int:
        return len(self.examples)
