"""
Ontological Engine - Domain-Specific Dataset Loaders
=====================================================

Dataset loaders for training with contrastive loss:
1. GSM8KDataset: Grade school math problems (reasoning)
2. ROCStoriesDataset: Story completion (creativity)
3. ContrastiveDataset: Pairs samples for contrastive learning

Usage:
    from symbolu.ontological.domain_datasets import (
        GSM8KDataset, ROCStoriesDataset, ContrastiveDataset
    )

    # Load datasets
    gsm8k = GSM8KDataset.load_from_huggingface()
    roc = ROCStoriesDataset.load_from_file("rocstories.csv")

    # Create contrastive pairs
    contrastive = ContrastiveDataset(
        reasoning_texts=gsm8k.get_texts(),
        creativity_texts=roc.get_texts(),
    )
"""

import json
import csv
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from symbolu.ontological.types import TrainingExample


@dataclass
class DomainSample:
    """A single sample from a domain dataset."""
    text: str
    domain: str  # "reasoning" or "creativity"
    metadata: Optional[Dict] = None


class GSM8KDataset:
    """
    GSM8K (Grade School Math 8K) dataset loader.

    Contains 8.5K grade school math problems for reasoning training.
    Each problem has a question and step-by-step solution.

    Source: https://huggingface.co/datasets/openai/gsm8k
    """

    DOMAIN = "reasoning"

    def __init__(self, samples: List[DomainSample] = None):
        self.samples = samples or []

    def __len__(self) -> int:
        return len(self.samples)

    def get_texts(self) -> List[str]:
        """Get all text samples."""
        return [s.text for s in self.samples]

    def to_training_examples(self) -> List[TrainingExample]:
        """Convert to TrainingExample format with O6_REASONING label."""
        return [
            TrainingExample(
                text=s.text,
                dimension_labels={"O7_REASONING": 0.9, "O5_COGNITION": 0.7},
                reasoning_label=0.9,
            )
            for s in self.samples
        ]

    @classmethod
    def load_from_jsonl(cls, path: str, max_samples: int = None) -> "GSM8KDataset":
        """
        Load from JSONL file (GSM8K format).

        Expected format per line:
            {"question": "...", "answer": "..."}
        """
        samples = []
        path = Path(path)

        if not path.exists():
            print(f"Warning: GSM8K file not found: {path}")
            return cls(samples)

        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if max_samples and i >= max_samples:
                    break

                try:
                    data = json.loads(line.strip())
                    question = data.get("question", "")
                    answer = data.get("answer", "")

                    # Combine question and answer for full context
                    text = f"Problem: {question}\nSolution: {answer}"

                    samples.append(DomainSample(
                        text=text,
                        domain=cls.DOMAIN,
                        metadata={"question": question, "answer": answer}
                    ))
                except json.JSONDecodeError:
                    continue

        print(f"Loaded {len(samples)} GSM8K samples")
        return cls(samples)

    @classmethod
    def load_from_huggingface(
        cls,
        split: str = "train",
        max_samples: int = 1000,
    ) -> "GSM8KDataset":
        """
        Load directly from HuggingFace datasets.

        Requires: pip install datasets
        """
        try:
            from datasets import load_dataset

            print(f"Loading GSM8K from HuggingFace ({split})...")
            dataset = load_dataset("openai/gsm8k", "main", split=split)

            samples = []
            for i, item in enumerate(dataset):
                if max_samples and i >= max_samples:
                    break

                question = item.get("question", "")
                answer = item.get("answer", "")
                text = f"Problem: {question}\nSolution: {answer}"

                samples.append(DomainSample(
                    text=text,
                    domain=cls.DOMAIN,
                    metadata={"question": question, "answer": answer}
                ))

            print(f"Loaded {len(samples)} GSM8K samples")
            return cls(samples)

        except ImportError:
            raise ImportError(
                "HuggingFace datasets required. Install with: pip install datasets"
            )

    @classmethod
    def create_synthetic(cls, count: int = 100) -> "GSM8KDataset":
        """Create synthetic math reasoning samples for testing."""
        templates = [
            "If Alice has {a} apples and Bob has {b} apples, how many apples do they have together? Answer: {a} + {b} = {c} apples.",
            "A train travels {a} miles in {b} hours. What is its average speed? Answer: {a} / {b} = {c} miles per hour.",
            "There are {a} students in a class. If {b} are absent, how many are present? Answer: {a} - {b} = {c} students.",
            "A rectangle has length {a} and width {b}. What is its area? Answer: {a} × {b} = {c} square units.",
            "If {a} people share {b} pizzas equally, how much pizza does each person get? Answer: {b} / {a} = {c:.2f} pizzas each.",
        ]

        samples = []
        for i in range(count):
            template = random.choice(templates)
            a = random.randint(2, 50)
            b = random.randint(2, 20)

            if "+" in template:
                c = a + b
            elif "/ {b}" in template:
                c = a / b
            elif "-" in template:
                c = a - b
            elif "×" in template:
                c = a * b
            else:
                c = b / a

            text = template.format(a=a, b=b, c=c)
            samples.append(DomainSample(
                text=text,
                domain=cls.DOMAIN,
                metadata={"synthetic": True}
            ))

        return cls(samples)


class ROCStoriesDataset:
    """
    ROCStories dataset loader for story completion.

    Contains 50K five-sentence stories for creativity training.

    Source: https://cs.rochester.edu/nlp/rocstories/
    Note: Dataset requires registration to download.
    """

    DOMAIN = "creativity"

    def __init__(self, samples: List[DomainSample] = None):
        self.samples = samples or []

    def __len__(self) -> int:
        return len(self.samples)

    def get_texts(self) -> List[str]:
        """Get all text samples."""
        return [s.text for s in self.samples]

    def to_training_examples(self) -> List[TrainingExample]:
        """Convert to TrainingExample format with O2_FORMING label."""
        return [
            TrainingExample(
                text=s.text,
                dimension_labels={"O4_STRUCTURE": 0.9, "O10_UNIFYING": 0.7},
                creativity_label=0.9,
            )
            for s in self.samples
        ]

    @classmethod
    def load_from_csv(cls, path: str, max_samples: int = None) -> "ROCStoriesDataset":
        """
        Load from CSV file (ROCStories format).

        Expected columns: storyid, storytitle, sentence1-5
        """
        samples = []
        path = Path(path)

        if not path.exists():
            print(f"Warning: ROCStories file not found: {path}")
            return cls(samples)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_samples and i >= max_samples:
                    break

                # Combine all sentences
                sentences = [
                    row.get(f"sentence{j}", "")
                    for j in range(1, 6)
                ]
                text = " ".join(s for s in sentences if s)

                if text:
                    samples.append(DomainSample(
                        text=text,
                        domain=cls.DOMAIN,
                        metadata={
                            "story_id": row.get("storyid"),
                            "title": row.get("storytitle"),
                        }
                    ))

        print(f"Loaded {len(samples)} ROCStories samples")
        return cls(samples)

    @classmethod
    def load_from_huggingface(
        cls,
        max_samples: int = 1000,
    ) -> "ROCStoriesDataset":
        """
        Load story dataset from HuggingFace.

        Uses 'hellaswag' or similar as ROCStories requires registration.
        """
        try:
            from datasets import load_dataset

            print("Loading story dataset from HuggingFace...")
            # Using WritingPrompts as a publicly available creative writing dataset
            dataset = load_dataset("euclaise/writingprompts", split="train")

            samples = []
            for i, item in enumerate(dataset):
                if max_samples and i >= max_samples:
                    break

                # WritingPrompts has 'prompt' and 'story' fields
                prompt = item.get("prompt", "")
                story = item.get("story", "")

                # Use story or prompt, whichever is available
                text = story if story else prompt
                if len(text) > 500:  # Truncate long stories
                    text = text[:500] + "..."

                if text:
                    samples.append(DomainSample(
                        text=text,
                        domain=cls.DOMAIN,
                        metadata={"source": "writingprompts"}
                    ))

            print(f"Loaded {len(samples)} story samples")
            return cls(samples)

        except Exception as e:
            print(f"Failed to load from HuggingFace: {e}")
            print("Creating synthetic stories instead...")
            return cls.create_synthetic(max_samples)

    @classmethod
    def create_synthetic(cls, count: int = 100) -> "ROCStoriesDataset":
        """Create synthetic creative writing samples for testing."""
        story_starts = [
            "Once upon a time, in a distant kingdom, there lived a",
            "The old lighthouse keeper had a secret that",
            "When the music box opened, something magical happened:",
            "In the garden of forgotten dreams, a young artist discovered",
            "The last train of the night carried passengers who",
            "Under the ancient oak tree, two strangers met and",
            "The letter arrived on a stormy night, containing news that",
            "In the city where it always rains, there was one place where",
            "The clockmaker's daughter inherited more than just watches:",
            "Between the pages of the dusty book, she found",
        ]

        story_middles = [
            "nobody would believe. Years passed, and the memory faded, until one day",
            "changed everything. The villagers whispered about miracles and magic.",
            "beautiful dreams began to unfold. Colors danced in the air as",
            "their paths intertwined in unexpected ways. Neither knew that",
            "a hidden world emerged from the shadows. Ancient beings stirred as",
            "secrets of the past came flooding back. Time seemed to stop when",
            "impossible possibilities became reality. The boundaries between worlds blurred.",
            "forgotten melodies filled the silence. Hearts that were broken began to heal.",
        ]

        story_ends = [
            "And from that day forward, nothing was ever quite the same.",
            "The mystery remains unsolved to this day, waiting for someone brave enough to uncover the truth.",
            "They learned that magic exists for those who believe in it.",
            "The story continues, passed down through generations like a precious heirloom.",
            "Some say you can still hear the echoes of that extraordinary day.",
            "And so, the adventure was just beginning.",
        ]

        samples = []
        for i in range(count):
            start = random.choice(story_starts)
            middle = random.choice(story_middles)
            end = random.choice(story_ends)

            text = f"{start} {middle} {end}"

            samples.append(DomainSample(
                text=text,
                domain=cls.DOMAIN,
                metadata={"synthetic": True}
            ))

        return cls(samples)


class ContrastiveDataset:
    """
    Dataset for contrastive learning with triplets.

    Creates (anchor, positive, negative) triplets where:
    - anchor: sample from one domain
    - positive: another sample from same domain
    - negative: sample from opposite domain
    """

    def __init__(
        self,
        reasoning_texts: List[str],
        creativity_texts: List[str],
    ):
        self.reasoning_texts = reasoning_texts
        self.creativity_texts = creativity_texts

        # Create indices for sampling
        self._reasoning_indices = list(range(len(reasoning_texts)))
        self._creativity_indices = list(range(len(creativity_texts)))

    def __len__(self) -> int:
        # Total triplets possible (2 domains × samples per domain)
        return len(self.reasoning_texts) + len(self.creativity_texts)

    def get_triplet(self, idx: int) -> Tuple[str, str, str, str]:
        """
        Get a triplet (anchor, positive, negative, anchor_domain).

        Returns:
            (anchor_text, positive_text, negative_text, domain)
        """
        if idx < len(self.reasoning_texts):
            # Reasoning anchor
            anchor_domain = "reasoning"
            anchor_idx = idx
            anchor = self.reasoning_texts[anchor_idx]

            # Positive: another reasoning sample
            pos_indices = [i for i in self._reasoning_indices if i != anchor_idx]
            if pos_indices:
                positive = self.reasoning_texts[random.choice(pos_indices)]
            else:
                positive = anchor  # Fallback if only one sample

            # Negative: creativity sample
            negative = random.choice(self.creativity_texts)

        else:
            # Creativity anchor
            anchor_domain = "creativity"
            anchor_idx = idx - len(self.reasoning_texts)
            anchor = self.creativity_texts[anchor_idx]

            # Positive: another creativity sample
            pos_indices = [i for i in self._creativity_indices if i != anchor_idx]
            if pos_indices:
                positive = self.creativity_texts[random.choice(pos_indices)]
            else:
                positive = anchor

            # Negative: reasoning sample
            negative = random.choice(self.reasoning_texts)

        return anchor, positive, negative, anchor_domain

    def get_batch(
        self,
        batch_size: int,
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Get a batch of triplets.

        Returns:
            (anchors, positives, negatives, domains)
        """
        indices = random.sample(range(len(self)), min(batch_size, len(self)))

        anchors, positives, negatives, domains = [], [], [], []
        for idx in indices:
            a, p, n, d = self.get_triplet(idx)
            anchors.append(a)
            positives.append(p)
            negatives.append(n)
            domains.append(d)

        return anchors, positives, negatives, domains


def create_contrastive_dataset(
    gsm8k_samples: int = 500,
    stories_samples: int = 500,
    use_huggingface: bool = True,
    gsm8k_path: str = None,
    stories_path: str = None,
) -> ContrastiveDataset:
    """
    Factory function to create a ContrastiveDataset.

    Args:
        gsm8k_samples: Number of GSM8K samples
        stories_samples: Number of story samples
        use_huggingface: Try loading from HuggingFace first
        gsm8k_path: Path to local GSM8K JSONL file
        stories_path: Path to local ROCStories CSV file

    Returns:
        ContrastiveDataset ready for training
    """
    # Load reasoning data (GSM8K)
    if gsm8k_path:
        gsm8k = GSM8KDataset.load_from_jsonl(gsm8k_path, max_samples=gsm8k_samples)
    elif use_huggingface:
        try:
            gsm8k = GSM8KDataset.load_from_huggingface(max_samples=gsm8k_samples)
        except Exception as e:
            print(f"HuggingFace load failed: {e}")
            gsm8k = GSM8KDataset.create_synthetic(gsm8k_samples)
    else:
        gsm8k = GSM8KDataset.create_synthetic(gsm8k_samples)

    # Load creativity data (Stories)
    if stories_path:
        stories = ROCStoriesDataset.load_from_csv(stories_path, max_samples=stories_samples)
    elif use_huggingface:
        try:
            stories = ROCStoriesDataset.load_from_huggingface(max_samples=stories_samples)
        except Exception:
            stories = ROCStoriesDataset.create_synthetic(stories_samples)
    else:
        stories = ROCStoriesDataset.create_synthetic(stories_samples)

    return ContrastiveDataset(
        reasoning_texts=gsm8k.get_texts(),
        creativity_texts=stories.get_texts(),
    )
