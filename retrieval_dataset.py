#!/usr/bin/env python3
"""
Retrieval-Enriched Training Dataset Generator.

Creates synthetic retrieval tasks to teach Phase Attention models
to preserve unique markers through compressed state.

Based on Google's recommendation:
- 90% WikiText + 10% Synthetic Retrieval during "warm-up" phase
- Teaches model to "protect" specific keys in phase state

Usage:
    python retrieval_dataset.py --output retrieval_train.json --num_samples 10000

Then modify train.py to mix this with WikiText at 10% ratio.
"""

import argparse
import json
import random
import string
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple
import hashlib


@dataclass
class RetrievalSample:
    """A single retrieval training sample."""
    context: str
    question: str
    answer: str
    needle_position: float  # 0.0 = start, 1.0 = end
    context_length: int
    task_type: str


class RetrievalDatasetGenerator:
    """Generate synthetic retrieval training data."""

    def __init__(self, seed: int = 42):
        random.seed(seed)

        # Diverse filler text patterns (Wikipedia-style)
        self.filler_templates = [
            "The {noun} was established in {year} and has since become known for its {adj} {noun2}.",
            "According to {source}, the {noun} reached a population of {number} by {year}.",
            "In {year}, {person} published a study on {topic} which showed that {finding}.",
            "The {adj} {noun} of {place} is characterized by {feature} and {feature2}.",
            "{person} was born in {place} and later moved to {place2} to study {topic}.",
            "Research conducted by {institution} revealed that {finding} affects {percentage}% of cases.",
            "The historical significance of {noun} dates back to {year} when {event} occurred.",
            "During the {period}, {place} experienced significant changes in its {aspect}.",
        ]

        self.nouns = ["system", "organization", "institution", "framework", "method", "process",
                      "structure", "network", "community", "region", "development", "approach"]
        self.adjectives = ["significant", "notable", "remarkable", "substantial", "considerable",
                          "prominent", "distinctive", "innovative", "traditional", "modern"]
        self.places = ["London", "Paris", "New York", "Tokyo", "Berlin", "Sydney", "Toronto",
                      "Amsterdam", "Stockholm", "Singapore", "Boston", "Chicago"]
        self.persons = ["Dr. Smith", "Professor Johnson", "Dr. Williams", "Professor Brown",
                       "Dr. Davis", "Professor Miller", "Dr. Wilson", "Professor Moore"]
        self.topics = ["economics", "biology", "physics", "chemistry", "mathematics",
                      "psychology", "sociology", "anthropology", "linguistics", "philosophy"]
        self.institutions = ["MIT", "Stanford", "Oxford", "Cambridge", "Harvard", "Berkeley",
                            "Caltech", "ETH Zurich", "Imperial College", "Princeton"]

        # Key-Value task templates
        self.kv_templates = [
            "The secret code for {entity} is {value}.",
            "Remember: {entity} has the key {value}.",
            "IMPORTANT: The {entity} password is {value}.",
            "Note that {entity} uses code {value}.",
            "The identifier for {entity} is set to {value}.",
            "For {entity}, use access code {value}.",
        ]

        # Question templates
        self.question_templates = [
            "What is the code for {entity}?",
            "What is the key for {entity}?",
            "What password is used for {entity}?",
            "What is the identifier for {entity}?",
            "What access code does {entity} use?",
        ]

        # Entity names
        self.entities = [
            "Project Alpha", "System Beta", "Module Gamma", "Service Delta",
            "Account Epsilon", "Database Zeta", "Server Eta", "Network Theta",
            "Gateway Iota", "Portal Kappa", "Cluster Lambda", "Node Mu",
        ]

    def generate_filler_sentence(self) -> str:
        """Generate a single filler sentence."""
        template = random.choice(self.filler_templates)

        replacements = {
            "{noun}": random.choice(self.nouns),
            "{noun2}": random.choice(self.nouns),
            "{adj}": random.choice(self.adjectives),
            "{place}": random.choice(self.places),
            "{place2}": random.choice(self.places),
            "{person}": random.choice(self.persons),
            "{topic}": random.choice(self.topics),
            "{institution}": random.choice(self.institutions),
            "{year}": str(random.randint(1900, 2024)),
            "{number}": f"{random.randint(1, 999)},{random.randint(100, 999)}",
            "{percentage}": str(random.randint(10, 95)),
            "{source}": random.choice(self.institutions),
            "{finding}": f"the {random.choice(self.adjectives)} {random.choice(self.nouns)}",
            "{feature}": f"{random.choice(self.adjectives)} {random.choice(self.nouns)}",
            "{feature2}": f"{random.choice(self.adjectives)} {random.choice(self.nouns)}",
            "{period}": f"{random.randint(1800, 2000)}s",
            "{aspect}": random.choice(self.nouns),
            "{event}": f"the {random.choice(self.adjectives)} {random.choice(self.nouns)} was established",
        }

        result = template
        for key, value in replacements.items():
            result = result.replace(key, value, 1)
        return result

    def generate_filler_text(self, num_sentences: int) -> str:
        """Generate filler text of specified length."""
        sentences = [self.generate_filler_sentence() for _ in range(num_sentences)]
        return " ".join(sentences)

    def generate_uuid(self) -> str:
        """Generate a random UUID-like code."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    def generate_numeric_code(self) -> str:
        """Generate a numeric passcode."""
        return ''.join(random.choices(string.digits, k=random.choice([6, 8, 10])))

    def generate_alphanumeric_key(self) -> str:
        """Generate an alphanumeric key."""
        prefix = ''.join(random.choices(string.ascii_uppercase, k=3))
        suffix = ''.join(random.choices(string.digits, k=4))
        return f"{prefix}-{suffix}"

    # =========================================================================
    # Task Type 1: Single Key-Value Retrieval
    # =========================================================================

    def generate_kv_retrieval(self, context_sentences: int = 50,
                               needle_position: float = 0.5) -> RetrievalSample:
        """Generate a key-value retrieval task."""
        # Generate the needle (key-value pair)
        entity = random.choice(self.entities)
        value_type = random.choice(["uuid", "numeric", "alphanumeric"])

        if value_type == "uuid":
            value = self.generate_uuid()
        elif value_type == "numeric":
            value = self.generate_numeric_code()
        else:
            value = self.generate_alphanumeric_key()

        kv_template = random.choice(self.kv_templates)
        needle = kv_template.format(entity=entity, value=value)

        # Generate filler
        before_sentences = int(context_sentences * needle_position)
        after_sentences = context_sentences - before_sentences

        filler_before = self.generate_filler_text(before_sentences)
        filler_after = self.generate_filler_text(after_sentences)

        context = f"{filler_before} {needle} {filler_after}"

        # Generate question
        q_template = random.choice(self.question_templates)
        question = q_template.format(entity=entity)

        return RetrievalSample(
            context=context,
            question=question,
            answer=value,
            needle_position=needle_position,
            context_length=len(context.split()),
            task_type="kv_single"
        )

    # =========================================================================
    # Task Type 2: Multi-Key Retrieval
    # =========================================================================

    def generate_multi_kv_retrieval(self, context_sentences: int = 80,
                                     num_keys: int = 3) -> RetrievalSample:
        """Generate a multi-key retrieval task."""
        # Generate multiple key-value pairs
        entities = random.sample(self.entities, num_keys)
        pairs = []

        for entity in entities:
            value = self.generate_uuid()
            kv_template = random.choice(self.kv_templates)
            needle = kv_template.format(entity=entity, value=value)
            pairs.append((entity, value, needle))

        # Distribute needles throughout the context
        sentences_per_section = context_sentences // (num_keys + 1)

        sections = []
        for i, (entity, value, needle) in enumerate(pairs):
            filler = self.generate_filler_text(sentences_per_section)
            sections.append(f"{filler} {needle}")

        # Add final filler section
        sections.append(self.generate_filler_text(sentences_per_section))

        context = " ".join(sections)

        # Ask about a random key
        target_entity, target_value, _ = random.choice(pairs)
        q_template = random.choice(self.question_templates)
        question = q_template.format(entity=target_entity)

        return RetrievalSample(
            context=context,
            question=question,
            answer=target_value,
            needle_position=0.5,  # Distributed
            context_length=len(context.split()),
            task_type="kv_multi"
        )

    # =========================================================================
    # Task Type 3: Ordered List Retrieval
    # =========================================================================

    def generate_ordered_list_retrieval(self, context_sentences: int = 50,
                                         list_length: int = 5) -> RetrievalSample:
        """Generate an ordered list retrieval task."""
        # Generate list items
        items = [self.generate_uuid() for _ in range(list_length)]
        list_text = f"The ordered sequence is: {', '.join(items)}. Remember this exact order."

        # Position in context
        position = random.uniform(0.2, 0.8)
        before_sentences = int(context_sentences * position)
        after_sentences = context_sentences - before_sentences

        filler_before = self.generate_filler_text(before_sentences)
        filler_after = self.generate_filler_text(after_sentences)

        context = f"{filler_before} {list_text} {filler_after}"

        # Ask about a specific position
        target_position = random.randint(1, list_length)
        ordinal = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh"][target_position - 1]
        question = f"What is the {ordinal} item in the ordered sequence?"
        answer = items[target_position - 1]

        return RetrievalSample(
            context=context,
            question=question,
            answer=answer,
            needle_position=position,
            context_length=len(context.split()),
            task_type="ordered_list"
        )

    # =========================================================================
    # Task Type 4: Factual Recall
    # =========================================================================

    def generate_factual_recall(self, context_sentences: int = 50) -> RetrievalSample:
        """Generate a factual recall task with realistic facts."""
        # Generate a memorable fact
        fact_templates = [
            ("The capital of {country} was changed to {city} in {year}.",
             "What city became the capital of {country}?", "{city}"),
            ("{person} discovered {discovery} at {place} in {year}.",
             "What did {person} discover?", "{discovery}"),
            ("The population of {place} reached exactly {number} in {year}.",
             "What was the population of {place} in {year}?", "{number}"),
            ("{company} was founded by {person} in {year} with initial funding of ${amount}.",
             "How much initial funding did {company} receive?", "${amount}"),
        ]

        countries = ["Atlantica", "Pacifica", "Nordland", "Southland", "Eastonia", "Westmark"]
        cities = ["New Haven", "Brightport", "Clearwater", "Greendale", "Bluefield", "Redstone"]
        discoveries = ["Element-X", "Protocol-7", "Compound-Z", "Theory-Q", "Formula-R"]
        companies = ["TechCorp", "DataSys", "CloudNet", "AILabs", "QuantumIO", "NeuralTech"]

        template, q_template, a_template = random.choice(fact_templates)

        values = {
            "{country}": random.choice(countries),
            "{city}": random.choice(cities),
            "{year}": str(random.randint(1950, 2023)),
            "{person}": random.choice(self.persons),
            "{discovery}": random.choice(discoveries),
            "{place}": random.choice(self.places),
            "{number}": f"{random.randint(1, 9)},{random.randint(100, 999)},{random.randint(100, 999)}",
            "{company}": random.choice(companies),
            "{amount}": f"{random.randint(1, 99)},{random.randint(100, 999)},{random.randint(100, 999)}",
        }

        fact = template
        question = q_template
        answer = a_template

        for key, value in values.items():
            fact = fact.replace(key, value)
            question = question.replace(key, value)
            answer = answer.replace(key, value)

        # Build context
        position = random.uniform(0.2, 0.8)
        before = int(context_sentences * position)
        after = context_sentences - before

        context = f"{self.generate_filler_text(before)} {fact} {self.generate_filler_text(after)}"

        return RetrievalSample(
            context=context,
            question=question,
            answer=answer,
            needle_position=position,
            context_length=len(context.split()),
            task_type="factual"
        )

    # =========================================================================
    # Task Type 5: Copy/Repeat Task (simpler, for warm-up)
    # =========================================================================

    def generate_copy_task(self, context_sentences: int = 30) -> RetrievalSample:
        """Generate a simple copy/repeat task."""
        # Generate a short memorable sequence
        sequence = self.generate_uuid()
        marker = f"MEMORIZE THIS: {sequence}"

        position = random.uniform(0.3, 0.7)
        before = int(context_sentences * position)
        after = context_sentences - before

        context = f"{self.generate_filler_text(before)} {marker} {self.generate_filler_text(after)}"
        question = "What sequence were you asked to memorize?"

        return RetrievalSample(
            context=context,
            question=question,
            answer=sequence,
            needle_position=position,
            context_length=len(context.split()),
            task_type="copy"
        )

    # =========================================================================
    # Dataset Generation
    # =========================================================================

    def generate_dataset(self, num_samples: int,
                          context_range: Tuple[int, int] = (30, 100)) -> List[Dict]:
        """Generate a diverse retrieval dataset."""
        samples = []

        task_generators = [
            (self.generate_kv_retrieval, 0.35),
            (self.generate_multi_kv_retrieval, 0.20),
            (self.generate_ordered_list_retrieval, 0.15),
            (self.generate_factual_recall, 0.15),
            (self.generate_copy_task, 0.15),
        ]

        for i in range(num_samples):
            # Select task type based on weights
            r = random.random()
            cumulative = 0
            generator = None

            for gen, weight in task_generators:
                cumulative += weight
                if r < cumulative:
                    generator = gen
                    break

            if generator is None:
                generator = task_generators[0][0]

            # Vary context length
            context_sentences = random.randint(*context_range)

            # Vary needle position for single-key tasks
            if generator == self.generate_kv_retrieval:
                position = random.choice([0.1, 0.25, 0.5, 0.75, 0.9])
                sample = generator(context_sentences=context_sentences, needle_position=position)
            else:
                sample = generator(context_sentences=context_sentences)

            # Format for training
            training_text = f"{sample.context}\n\nQuestion: {sample.question}\nAnswer: {sample.answer}"

            samples.append({
                "text": training_text,
                "context": sample.context,
                "question": sample.question,
                "answer": sample.answer,
                "task_type": sample.task_type,
                "needle_position": sample.needle_position,
                "context_length": sample.context_length,
            })

            if (i + 1) % 1000 == 0:
                print(f"Generated {i + 1}/{num_samples} samples...")

        return samples


def main():
    parser = argparse.ArgumentParser(description="Generate Retrieval-Enriched Training Dataset")
    parser.add_argument("--output", type=str, default="retrieval_train.json",
                        help="Output file path")
    parser.add_argument("--num_samples", type=int, default=10000,
                        help="Number of samples to generate")
    parser.add_argument("--min_context", type=int, default=30,
                        help="Minimum context sentences")
    parser.add_argument("--max_context", type=int, default=100,
                        help="Maximum context sentences")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")

    args = parser.parse_args()

    print(f"Generating {args.num_samples} retrieval samples...")
    generator = RetrievalDatasetGenerator(seed=args.seed)

    samples = generator.generate_dataset(
        num_samples=args.num_samples,
        context_range=(args.min_context, args.max_context)
    )

    # Save to JSON
    with open(args.output, 'w') as f:
        json.dump(samples, f, indent=2)

    print(f"\nDataset saved to: {args.output}")
    print(f"Total samples: {len(samples)}")

    # Print statistics
    task_counts = {}
    for sample in samples:
        task_type = sample["task_type"]
        task_counts[task_type] = task_counts.get(task_type, 0) + 1

    print("\nTask distribution:")
    for task, count in sorted(task_counts.items()):
        print(f"  {task}: {count} ({count/len(samples)*100:.1f}%)")

    avg_length = sum(s["context_length"] for s in samples) / len(samples)
    print(f"\nAverage context length: {avg_length:.0f} words")

    # Show example
    print("\n" + "="*60)
    print("EXAMPLE SAMPLE:")
    print("="*60)
    example = random.choice(samples)
    print(f"Task: {example['task_type']}")
    print(f"Needle Position: {example['needle_position']:.1%}")
    print(f"Context (truncated): {example['context'][:200]}...")
    print(f"Question: {example['question']}")
    print(f"Answer: {example['answer']}")


if __name__ == "__main__":
    main()
