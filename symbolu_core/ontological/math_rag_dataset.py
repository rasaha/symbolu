"""
Ontological Engine - Math RAG Dataset
======================================

Comprehensive math reasoning dataset for training without external dependencies.
Covers multiple math domains: arithmetic, algebra, geometry, logic, and word problems.

Usage:
    from symbolu_core.ontological.math_rag_dataset import MathRAGDataset

    # Generate and save dataset
    dataset = MathRAGDataset.generate(count=1000)
    dataset.save("data/math_rag.json")

    # Load from file
    dataset = MathRAGDataset.load("data/math_rag.json")
    texts = dataset.get_texts()
"""

import json
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class MathProblem:
    """A single math problem with solution."""
    question: str
    solution: str
    answer: str
    category: str  # arithmetic, algebra, geometry, logic, word_problem
    difficulty: str  # easy, medium, hard

    def to_text(self) -> str:
        """Convert to training text format."""
        return f"Problem: {self.question}\nSolution: {self.solution}\nAnswer: {self.answer}"


class MathRAGDataset:
    """
    Comprehensive math reasoning dataset generator.

    Categories:
    - arithmetic: Basic operations, order of operations
    - algebra: Equations, expressions, variables
    - geometry: Areas, perimeters, volumes
    - logic: Deductive reasoning, sequences
    - word_problem: Multi-step real-world problems
    """

    DOMAIN = "reasoning"

    def __init__(self, problems: List[MathProblem] = None):
        self.problems = problems or []

    def __len__(self) -> int:
        return len(self.problems)

    def get_texts(self) -> List[str]:
        """Get all problems as training texts."""
        return [p.to_text() for p in self.problems]

    def get_by_category(self, category: str) -> List[MathProblem]:
        """Filter problems by category."""
        return [p for p in self.problems if p.category == category]

    def save(self, path: str) -> None:
        """Save dataset to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "count": len(self.problems),
            "problems": [asdict(p) for p in self.problems]
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"Saved {len(self.problems)} math problems to {path}")

    @classmethod
    def load(cls, path: str) -> "MathRAGDataset":
        """Load dataset from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        problems = [MathProblem(**p) for p in data["problems"]]
        print(f"Loaded {len(problems)} math problems from {path}")
        return cls(problems)

    @classmethod
    def generate(cls, count: int = 500, seed: int = None) -> "MathRAGDataset":
        """
        Generate comprehensive math dataset.

        Args:
            count: Total number of problems to generate
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

        problems = []

        # Distribute across categories
        per_category = count // 5

        problems.extend(cls._generate_arithmetic(per_category))
        problems.extend(cls._generate_algebra(per_category))
        problems.extend(cls._generate_geometry(per_category))
        problems.extend(cls._generate_logic(per_category))
        problems.extend(cls._generate_word_problems(count - 4 * per_category))

        random.shuffle(problems)

        print(f"Generated {len(problems)} math problems")
        return cls(problems)

    @classmethod
    def _generate_arithmetic(cls, count: int) -> List[MathProblem]:
        """Generate arithmetic problems."""
        problems = []

        templates = [
            # Addition
            {
                "q": "What is {a} + {b}?",
                "s": "{a} + {b} = {c}",
                "op": lambda a, b: a + b,
                "diff": "easy"
            },
            {
                "q": "Calculate: {a} + {b} + {d}",
                "s": "First, {a} + {b} = {ab}. Then {ab} + {d} = {c}",
                "op": lambda a, b, d=0: (a + b, a + b + d),
                "diff": "medium"
            },
            # Subtraction
            {
                "q": "What is {a} - {b}?",
                "s": "{a} - {b} = {c}",
                "op": lambda a, b: a - b,
                "diff": "easy"
            },
            # Multiplication
            {
                "q": "What is {a} × {b}?",
                "s": "{a} × {b} = {c}",
                "op": lambda a, b: a * b,
                "diff": "easy"
            },
            {
                "q": "Calculate {a} × {b} × {d}",
                "s": "First, {a} × {b} = {ab}. Then {ab} × {d} = {c}",
                "op": lambda a, b, d=1: (a * b, a * b * d),
                "diff": "medium"
            },
            # Division
            {
                "q": "What is {a} ÷ {b}?",
                "s": "{a} ÷ {b} = {c}",
                "op": lambda a, b: a // b,
                "diff": "easy"
            },
            # Order of operations
            {
                "q": "Calculate: {a} + {b} × {d}",
                "s": "Following order of operations, first multiply: {b} × {d} = {bd}. Then add: {a} + {bd} = {c}",
                "op": lambda a, b, d=1: (b * d, a + b * d),
                "diff": "medium"
            },
            {
                "q": "What is ({a} + {b}) × {d}?",
                "s": "First, parentheses: {a} + {b} = {ab}. Then multiply: {ab} × {d} = {c}",
                "op": lambda a, b, d=1: (a + b, (a + b) * d),
                "diff": "medium"
            },
            # Fractions
            {
                "q": "What is {a}/{b} + {d}/{b}?",
                "s": "Same denominator, so add numerators: ({a} + {d})/{b} = {c}/{b}",
                "op": lambda a, b, d=1: (a + d, f"{a + d}/{b}"),
                "diff": "medium"
            },
            # Percentages
            {
                "q": "What is {p}% of {a}?",
                "s": "{p}% of {a} = {p}/100 × {a} = {c}",
                "op": lambda a, p=10: a * p // 100,
                "diff": "medium"
            },
        ]

        for i in range(count):
            template = random.choice(templates)
            a = random.randint(10, 100)
            b = random.randint(2, 20)
            d = random.randint(2, 10)
            p = random.choice([10, 20, 25, 50, 75])

            # Ensure clean division
            if "÷" in template["q"]:
                a = b * random.randint(2, 10)

            try:
                result = template["op"](a, b, d) if "d}" in template["q"] else template["op"](a, b)

                if isinstance(result, tuple):
                    ab_or_bd, c = result
                    q = template["q"].format(a=a, b=b, d=d, p=p)
                    s = template["s"].format(a=a, b=b, d=d, ab=ab_or_bd, bd=ab_or_bd, c=c, p=p)
                    ans = str(c)
                else:
                    c = result
                    q = template["q"].format(a=a, b=b, d=d, p=p)
                    s = template["s"].format(a=a, b=b, d=d, c=c, p=p)
                    ans = str(c)

                problems.append(MathProblem(
                    question=q,
                    solution=s,
                    answer=ans,
                    category="arithmetic",
                    difficulty=template["diff"]
                ))
            except:
                continue

        return problems[:count]

    @classmethod
    def _generate_algebra(cls, count: int) -> List[MathProblem]:
        """Generate algebra problems."""
        problems = []

        # Linear equations
        for _ in range(count // 3):
            a = random.randint(2, 10)
            b = random.randint(1, 20)
            x = random.randint(1, 10)
            c = a * x + b

            problems.append(MathProblem(
                question=f"Solve for x: {a}x + {b} = {c}",
                solution=f"Subtract {b} from both sides: {a}x = {c - b}. Divide by {a}: x = {c - b}/{a} = {x}",
                answer=str(x),
                category="algebra",
                difficulty="medium"
            ))

        # Expressions
        for _ in range(count // 3):
            a = random.randint(2, 10)
            b = random.randint(1, 10)
            x = random.randint(1, 5)

            problems.append(MathProblem(
                question=f"Evaluate {a}x + {b} when x = {x}",
                solution=f"Substitute x = {x}: {a}({x}) + {b} = {a * x} + {b} = {a * x + b}",
                answer=str(a * x + b),
                category="algebra",
                difficulty="easy"
            ))

        # Quadratic (simple)
        for _ in range(count - 2 * (count // 3)):
            x1 = random.randint(1, 5)
            x2 = random.randint(1, 5)
            # (x - x1)(x - x2) = x² - (x1+x2)x + x1*x2
            b = -(x1 + x2)
            c = x1 * x2

            b_str = f"- {-b}" if b < 0 else f"+ {b}"
            c_str = f"+ {c}" if c >= 0 else f"- {-c}"

            problems.append(MathProblem(
                question=f"Find the roots of x² {b_str}x {c_str} = 0",
                solution=f"Factor: (x - {x1})(x - {x2}) = 0. So x = {x1} or x = {x2}",
                answer=f"x = {x1}, {x2}",
                category="algebra",
                difficulty="hard"
            ))

        return problems

    @classmethod
    def _generate_geometry(cls, count: int) -> List[MathProblem]:
        """Generate geometry problems."""
        problems = []

        # Rectangle area
        for _ in range(count // 4):
            l = random.randint(5, 20)
            w = random.randint(3, 15)
            problems.append(MathProblem(
                question=f"Find the area of a rectangle with length {l} and width {w}.",
                solution=f"Area = length × width = {l} × {w} = {l * w}",
                answer=str(l * w),
                category="geometry",
                difficulty="easy"
            ))

        # Rectangle perimeter
        for _ in range(count // 4):
            l = random.randint(5, 20)
            w = random.randint(3, 15)
            problems.append(MathProblem(
                question=f"Find the perimeter of a rectangle with length {l} and width {w}.",
                solution=f"Perimeter = 2(length + width) = 2({l} + {w}) = 2 × {l + w} = {2 * (l + w)}",
                answer=str(2 * (l + w)),
                category="geometry",
                difficulty="easy"
            ))

        # Triangle area
        for _ in range(count // 4):
            b = random.randint(4, 20)
            h = random.randint(3, 15)
            problems.append(MathProblem(
                question=f"Find the area of a triangle with base {b} and height {h}.",
                solution=f"Area = (1/2) × base × height = (1/2) × {b} × {h} = {b * h // 2}",
                answer=str(b * h // 2),
                category="geometry",
                difficulty="easy"
            ))

        # Circle area (approximate)
        for _ in range(count - 3 * (count // 4)):
            r = random.randint(2, 10)
            area = round(3.14159 * r * r, 2)
            problems.append(MathProblem(
                question=f"Find the area of a circle with radius {r}. Use π ≈ 3.14.",
                solution=f"Area = π × r² = 3.14 × {r}² = 3.14 × {r * r} ≈ {area}",
                answer=str(area),
                category="geometry",
                difficulty="medium"
            ))

        return problems

    @classmethod
    def _generate_logic(cls, count: int) -> List[MathProblem]:
        """Generate logic and reasoning problems."""
        problems = []

        # Number sequences
        for _ in range(count // 3):
            start = random.randint(1, 10)
            step = random.randint(2, 5)
            seq = [start + i * step for i in range(5)]
            next_val = start + 5 * step

            problems.append(MathProblem(
                question=f"What is the next number in the sequence: {', '.join(map(str, seq))}, ?",
                solution=f"The pattern is adding {step} each time. {seq[-1]} + {step} = {next_val}",
                answer=str(next_val),
                category="logic",
                difficulty="medium"
            ))

        # Geometric sequences
        for _ in range(count // 3):
            start = random.randint(1, 5)
            ratio = random.randint(2, 3)
            seq = [start * (ratio ** i) for i in range(4)]
            next_val = start * (ratio ** 4)

            problems.append(MathProblem(
                question=f"What is the next number in the sequence: {', '.join(map(str, seq))}, ?",
                solution=f"The pattern is multiplying by {ratio} each time. {seq[-1]} × {ratio} = {next_val}",
                answer=str(next_val),
                category="logic",
                difficulty="medium"
            ))

        # Deductive reasoning
        deductive_templates = [
            {
                "q": "If all A are B, and all B are C, and X is an A, what can we conclude about X?",
                "s": "Since X is an A, and all A are B, X must be B. Since X is B, and all B are C, X must be C.",
                "a": "X is C"
            },
            {
                "q": "If P implies Q, and Q implies R, and P is true, what is the truth value of R?",
                "s": "P is true. P implies Q, so Q is true. Q implies R, so R is true.",
                "a": "R is true"
            },
            {
                "q": "If it rains, the ground is wet. The ground is wet. Can we conclude it rained?",
                "s": "No. The ground being wet is a necessary condition for rain, but not sufficient. The ground could be wet for other reasons (sprinkler, spill).",
                "a": "No, this would be affirming the consequent fallacy"
            },
        ]

        for _ in range(count - 2 * (count // 3)):
            template = random.choice(deductive_templates)
            problems.append(MathProblem(
                question=template["q"],
                solution=template["s"],
                answer=template["a"],
                category="logic",
                difficulty="hard"
            ))

        return problems

    @classmethod
    def _generate_word_problems(cls, count: int) -> List[MathProblem]:
        """Generate multi-step word problems."""
        problems = []

        names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]
        items = ["apples", "books", "coins", "marbles", "stickers", "cards", "candies", "pencils"]

        # Shopping problems
        for _ in range(count // 4):
            name = random.choice(names)
            item = random.choice(items)
            price = random.randint(2, 10)
            qty = random.randint(3, 10)
            money = price * qty + random.randint(5, 20)
            total = price * qty
            change = money - total

            problems.append(MathProblem(
                question=f"{name} buys {qty} {item} at ${price} each. If {name} pays with ${money}, how much change does {name} get?",
                solution=f"Total cost = {qty} × ${price} = ${total}. Change = ${money} - ${total} = ${change}",
                answer=f"${change}",
                category="word_problem",
                difficulty="medium"
            ))

        # Distance/Speed problems
        for _ in range(count // 4):
            speed = random.randint(30, 70)
            time = random.randint(2, 5)
            distance = speed * time

            problems.append(MathProblem(
                question=f"A car travels at {speed} mph for {time} hours. How far does it travel?",
                solution=f"Distance = Speed × Time = {speed} × {time} = {distance} miles",
                answer=f"{distance} miles",
                category="word_problem",
                difficulty="easy"
            ))

        # Work problems
        for _ in range(count // 4):
            rate1 = random.randint(2, 5)
            rate2 = random.randint(2, 5)
            hours = random.randint(3, 8)
            total = (rate1 + rate2) * hours

            name1, name2 = random.sample(names, 2)

            problems.append(MathProblem(
                question=f"{name1} can paint {rate1} walls per hour and {name2} can paint {rate2} walls per hour. Working together for {hours} hours, how many walls can they paint?",
                solution=f"Combined rate = {rate1} + {rate2} = {rate1 + rate2} walls/hour. Total = {rate1 + rate2} × {hours} = {total} walls",
                answer=f"{total} walls",
                category="word_problem",
                difficulty="medium"
            ))

        # Age problems
        for _ in range(count - 3 * (count // 4)):
            age1 = random.randint(25, 45)
            diff = random.randint(20, 30)
            age2 = age1 - diff
            years = random.randint(5, 15)

            name1, name2 = random.sample(names, 2)

            problems.append(MathProblem(
                question=f"{name1} is {age1} years old and {name2} is {age2} years old. In {years} years, what will be the sum of their ages?",
                solution=f"In {years} years: {name1} = {age1 + years}, {name2} = {age2 + years}. Sum = {age1 + years} + {age2 + years} = {age1 + age2 + 2 * years}",
                answer=str(age1 + age2 + 2 * years),
                category="word_problem",
                difficulty="medium"
            ))

        return problems


def create_math_rag_dataset(
    output_path: str = "data/math_rag.json",
    count: int = 1000,
    seed: int = 42,
) -> MathRAGDataset:
    """
    Generate and save a math RAG dataset.

    Args:
        output_path: Where to save the dataset
        count: Number of problems to generate
        seed: Random seed for reproducibility

    Returns:
        The generated dataset
    """
    dataset = MathRAGDataset.generate(count=count, seed=seed)
    dataset.save(output_path)
    return dataset


# CLI support
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Math RAG Dataset")
    parser.add_argument("--count", type=int, default=1000, help="Number of problems")
    parser.add_argument("--output", type=str, default="data/math_rag.json", help="Output path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    dataset = create_math_rag_dataset(
        output_path=args.output,
        count=args.count,
        seed=args.seed,
    )

    # Print sample
    print("\nSample problems:")
    for i, p in enumerate(dataset.problems[:3]):
        print(f"\n--- Problem {i+1} ({p.category}, {p.difficulty}) ---")
        print(p.to_text())
