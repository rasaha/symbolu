#!/usr/bin/env python3
"""
Synthetic Reasoning Dataset Generator
======================================

Generates structured reasoning examples for training the phase accumulator
to learn step-by-step state tracking. Each example is a text sequence with
explicit chain-of-thought reasoning that the model learns via next-token prediction.

Categories:
  1. Arithmetic chains   - multi-step math with intermediate results
  2. Logic chains        - if/then deduction over facts
  3. State tracking      - object tracking through transformations
  4. Pattern completion  - sequence extrapolation with reasoning

Output: A tokenized .pt file compatible with TextDataset in data.py

Usage:
    python -m symbolu.training.scripts.generate_reasoning_dataset \
        --output data_cache/reasoning_train.pt \
        --num_examples 50000 \
        --tokenizer gpt2 \
        --max_seq_len 512
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import List

import torch


# =============================================================================
# GENERATORS
# =============================================================================


def gen_arithmetic_chain(rng: random.Random) -> str:
    """Multi-step arithmetic with intermediate results.

    Example:
        Question: Compute step by step: 14 + 7 - 3 * 2
        Step 1: 14 + 7 = 21
        Step 2: 21 - 3 = 18
        Step 3: 18 * 2 = 36
        Answer: 36
    """
    num_steps = rng.randint(2, 5)
    ops = ['+', '-', '*']
    value = rng.randint(1, 50)
    chain_parts = [str(value)]
    steps = []

    for i in range(num_steps):
        op = rng.choice(ops)
        if op == '*':
            operand = rng.randint(2, 5)
        elif op == '-':
            operand = rng.randint(1, min(value, 20)) if value > 1 else 1
        else:
            operand = rng.randint(1, 30)

        chain_parts.append(f"{op} {operand}")
        prev = value

        if op == '+':
            value = prev + operand
        elif op == '-':
            value = prev - operand
        else:
            value = prev * operand

        steps.append(f"Step {i+1}: {prev} {op} {operand} = {value}")

    question = f"Question: Compute step by step: {' '.join(chain_parts)}"
    reasoning = "\n".join(steps)
    return f"{question}\n{reasoning}\nAnswer: {value}"


def gen_logic_chain(rng: random.Random) -> str:
    """If/then deduction over stated facts.

    Example:
        Facts:
        - All dogs are animals.
        - Rex is a dog.
        - All animals need water.
        Question: Does Rex need water?
        Step 1: Rex is a dog. (given)
        Step 2: All dogs are animals, so Rex is an animal.
        Step 3: All animals need water, so Rex needs water.
        Answer: Yes, Rex needs water.
    """
    templates = [
        {
            "entities": ["cats", "mammals", "living things"],
            "names": ["Whiskers", "Luna", "Mittens", "Shadow"],
            "properties": ["need food", "can grow", "have cells"],
        },
        {
            "entities": ["roses", "flowers", "plants"],
            "names": ["the red rose", "the garden rose", "the wild rose"],
            "properties": ["need sunlight", "produce oxygen", "have roots"],
        },
        {
            "entities": ["sparrows", "birds", "vertebrates"],
            "names": ["Tweety", "the house sparrow", "the little sparrow"],
            "properties": ["have a skeleton", "can move", "need energy"],
        },
        {
            "entities": ["salmon", "fish", "aquatic animals"],
            "names": ["the Pacific salmon", "the river salmon", "the young salmon"],
            "properties": ["live in water", "need oxygen", "can swim"],
        },
        {
            "entities": ["oak trees", "trees", "plants"],
            "names": ["the old oak", "the garden oak", "the tallest oak"],
            "properties": ["have roots", "need water", "produce oxygen"],
        },
    ]

    t = rng.choice(templates)
    name = rng.choice(t["names"])
    prop = rng.choice(t["properties"])
    e0, e1, e2 = t["entities"]

    text = (
        f"Facts:\n"
        f"- All {e0} are {e1}.\n"
        f"- {name} is a {e0[:-1] if e0.endswith('s') else e0}.\n"
        f"- All {e1} are {e2}.\n"
        f"- All {e2} {prop}.\n"
        f"Question: Does {name} {prop}?\n"
        f"Step 1: {name} is a {e0[:-1] if e0.endswith('s') else e0}. (given)\n"
        f"Step 2: All {e0} are {e1}, so {name} is a {e1[:-1] if e1.endswith('s') else e1}.\n"
        f"Step 3: All {e1} are {e2}, so {name} is a {e2[:-1] if e2.endswith('s') else e2}.\n"
        f"Step 4: All {e2} {prop}, so {name} {prop}.\n"
        f"Answer: Yes, {name} {prop}."
    )
    return text


def gen_state_tracking(rng: random.Random) -> str:
    """Track objects through a sequence of operations.

    Example:
        Setup: There is a red ball in box A and a blue ball in box B.
        Action 1: Move the red ball from box A to box C.
        State: box A is empty, box B has blue ball, box C has red ball.
        Action 2: Swap the contents of box B and box C.
        State: box A is empty, box B has red ball, box C has blue ball.
        Question: Where is the red ball?
        Answer: The red ball is in box B.
    """
    colors = ["red", "blue", "green", "yellow", "white"]
    objects = ["ball", "cube", "marble", "coin", "key"]
    containers = ["box A", "box B", "box C", "box D"]

    num_objects = rng.randint(2, 3)
    num_containers = num_objects + rng.randint(1, 2)
    sel_containers = containers[:num_containers]

    items = []
    for i in range(num_objects):
        items.append(f"{rng.choice(colors)} {rng.choice(objects)}")
    # Deduplicate
    items = list(dict.fromkeys(items))[:num_objects]

    # Initial placement
    state = {c: None for c in sel_containers}
    for i, item in enumerate(items):
        state[sel_containers[i]] = item

    def state_str():
        parts = []
        for c in sel_containers:
            if state[c]:
                parts.append(f"{c} has {state[c]}")
            else:
                parts.append(f"{c} is empty")
        return ", ".join(parts) + "."

    setup_parts = []
    for c in sel_containers:
        if state[c]:
            setup_parts.append(f"a {state[c]} in {c}")
    setup = "Setup: There is " + " and ".join(setup_parts) + "."

    actions = []
    num_actions = rng.randint(1, 3)
    for step in range(num_actions):
        action_type = rng.choice(["move", "swap"])

        if action_type == "move":
            occupied = [c for c in sel_containers if state[c] is not None]
            empty = [c for c in sel_containers if state[c] is None]
            if not occupied or not empty:
                continue
            src = rng.choice(occupied)
            dst = rng.choice(empty)
            item = state[src]
            state[src] = None
            state[dst] = item
            actions.append(
                f"Action {step+1}: Move the {item} from {src} to {dst}.\n"
                f"State: {state_str()}"
            )
        else:
            non_empty = [c for c in sel_containers if state[c] is not None]
            if len(non_empty) < 2:
                continue
            c1, c2 = rng.sample(non_empty, 2)
            state[c1], state[c2] = state[c2], state[c1]
            actions.append(
                f"Action {step+1}: Swap the contents of {c1} and {c2}.\n"
                f"State: {state_str()}"
            )

    # Ask about a random item
    occupied = [c for c in sel_containers if state[c] is not None]
    if occupied:
        ask_container = rng.choice(occupied)
        ask_item = state[ask_container]
        question = f"Question: Where is the {ask_item}?"
        answer = f"Answer: The {ask_item} is in {ask_container}."
    else:
        question = "Question: Are all containers empty?"
        answer = "Answer: Yes, all containers are empty."

    return "\n".join([setup] + actions + [question, answer])


def gen_pattern_completion(rng: random.Random) -> str:
    """Sequence extrapolation with explicit reasoning.

    Example:
        Sequence: 2, 4, 8, 16, ?
        Step 1: 4 / 2 = 2, so each term is multiplied by 2.
        Step 2: 8 / 4 = 2, confirmed.
        Step 3: 16 * 2 = 32.
        Answer: 32
    """
    pattern_type = rng.choice(["multiply", "add", "square_add", "alternate"])

    if pattern_type == "multiply":
        base = rng.randint(1, 5)
        factor = rng.randint(2, 4)
        seq = [base]
        for _ in range(4):
            seq.append(seq[-1] * factor)
        shown = seq[:4]
        answer_val = seq[4]
        steps = (
            f"Step 1: {shown[1]} / {shown[0]} = {factor}, so each term is multiplied by {factor}.\n"
            f"Step 2: {shown[2]} / {shown[1]} = {factor}, confirmed.\n"
            f"Step 3: {shown[3]} * {factor} = {answer_val}."
        )
    elif pattern_type == "add":
        base = rng.randint(1, 20)
        diff = rng.randint(2, 10)
        seq = [base + i * diff for i in range(5)]
        shown = seq[:4]
        answer_val = seq[4]
        steps = (
            f"Step 1: {shown[1]} - {shown[0]} = {diff}, so each term increases by {diff}.\n"
            f"Step 2: {shown[2]} - {shown[1]} = {diff}, confirmed.\n"
            f"Step 3: {shown[3]} + {diff} = {answer_val}."
        )
    elif pattern_type == "square_add":
        base = rng.randint(1, 5)
        seq = [base]
        for i in range(1, 5):
            seq.append(seq[-1] + i * i)
        shown = seq[:4]
        answer_val = seq[4]
        diffs = [shown[i+1] - shown[i] for i in range(3)]
        steps = (
            f"Step 1: Differences are {diffs[0]}, {diffs[1]}, {diffs[2]} (perfect squares: 1, 4, 9).\n"
            f"Step 2: Next difference should be 16 (4^2).\n"
            f"Step 3: {shown[3]} + 16 = {answer_val}."
        )
    else:  # alternate
        a = rng.randint(1, 10)
        b = rng.randint(1, 10)
        inc_a = rng.randint(1, 5)
        inc_b = rng.randint(1, 5)
        seq = []
        for i in range(5):
            if i % 2 == 0:
                seq.append(a + (i // 2) * inc_a)
            else:
                seq.append(b + (i // 2) * inc_b)
        shown = seq[:4]
        answer_val = seq[4]
        steps = (
            f"Step 1: Odd positions: {shown[0]}, {shown[2]} — increase by {inc_a}.\n"
            f"Step 2: Even positions: {shown[1]}, {shown[3]} — increase by {inc_b}.\n"
            f"Step 3: Next is odd position: {shown[2]} + {inc_a} = {answer_val}."
        )

    shown_str = ", ".join(str(x) for x in shown)
    return f"Sequence: {shown_str}, ?\n{steps}\nAnswer: {answer_val}"


def gen_word_problem(rng: random.Random) -> str:
    """Simple word problems with step-by-step solutions.

    Example:
        Question: Alice has 12 apples. She gives 3 to Bob and then buys 7 more. How many does she have?
        Step 1: Alice starts with 12 apples.
        Step 2: She gives 3 to Bob: 12 - 3 = 9.
        Step 3: She buys 7 more: 9 + 7 = 16.
        Answer: Alice has 16 apples.
    """
    names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank"]
    items = ["apples", "books", "coins", "marbles", "stickers", "cards"]

    name = rng.choice(names)
    item = rng.choice(items)
    start = rng.randint(5, 50)

    actions = []
    value = start
    num_actions = rng.randint(2, 4)
    other_names = [n for n in names if n != name]

    for i in range(num_actions):
        action_type = rng.choice(["give", "receive", "buy", "lose"])
        amount = rng.randint(1, min(value, 15)) if value > 1 else 1

        if action_type == "give":
            other = rng.choice(other_names)
            new_val = value - amount
            actions.append({
                "desc": f"gives {amount} to {other}",
                "step": f"{value} - {amount} = {new_val}",
                "verb": f"gives {amount} to {other}",
            })
            value = new_val
        elif action_type == "receive":
            other = rng.choice(other_names)
            new_val = value + amount
            actions.append({
                "desc": f"receives {amount} from {other}",
                "step": f"{value} + {amount} = {new_val}",
                "verb": f"receives {amount} from {other}",
            })
            value = new_val
        elif action_type == "buy":
            new_val = value + amount
            actions.append({
                "desc": f"buys {amount} more",
                "step": f"{value} + {amount} = {new_val}",
                "verb": f"buys {amount} more",
            })
            value = new_val
        else:
            new_val = value - amount
            actions.append({
                "desc": f"loses {amount}",
                "step": f"{value} - {amount} = {new_val}",
                "verb": f"loses {amount}",
            })
            value = new_val

    # Build question
    action_desc = " ".join(
        f"{'She' if i > 0 else name} {a['desc']}."
        for i, a in enumerate(actions)
    )
    question = f"Question: {name} has {start} {item}. {action_desc} How many does {name} have?"

    steps = [f"Step 1: {name} starts with {start} {item}."]
    for i, a in enumerate(actions):
        pronoun = "She" if i > 0 else name
        steps.append(f"Step {i+2}: {pronoun} {a['verb']}: {a['step']}.")

    return f"{question}\n" + "\n".join(steps) + f"\nAnswer: {name} has {value} {item}."


# =============================================================================
# MAIN GENERATOR
# =============================================================================

GENERATORS = [
    gen_arithmetic_chain,
    gen_logic_chain,
    gen_state_tracking,
    gen_pattern_completion,
    gen_word_problem,
]


def generate_examples(num_examples: int, seed: int = 42) -> List[str]:
    """Generate a list of reasoning examples."""
    rng = random.Random(seed)
    examples = []
    for i in range(num_examples):
        gen = rng.choice(GENERATORS)
        examples.append(gen(rng))
    return examples


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic reasoning dataset")
    parser.add_argument("--output", type=str, default="data_cache/reasoning_gpt2.pt",
                        help="Output path for tokenized .pt file")
    parser.add_argument("--num_examples", type=int, default=50000,
                        help="Number of reasoning examples to generate")
    parser.add_argument("--val_fraction", type=float, default=0.05,
                        help="Fraction of examples for validation")
    parser.add_argument("--tokenizer", type=str, default="gpt2",
                        help="Tokenizer to use")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    parser.add_argument("--max_seq_len", type=int, default=512,
                        help="Max sequence length (for info only, not enforced)")
    args = parser.parse_args()

    print(f"Generating {args.num_examples:,} synthetic reasoning examples...")
    start = time.time()
    examples = generate_examples(args.num_examples, seed=args.seed)
    gen_time = time.time() - start
    print(f"  Generated in {gen_time:.1f}s")

    # Show sample
    print(f"\n--- Sample example ---")
    print(examples[0])
    print(f"--- End sample ---\n")

    # Split train/val
    split_idx = int(len(examples) * (1 - args.val_fraction))
    train_examples = examples[:split_idx]
    val_examples = examples[split_idx:]

    # Tokenize
    print(f"Tokenizing with {args.tokenizer}...")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    # Join with separator and tokenize
    separator = "\n\n"
    train_text = separator.join(train_examples)
    val_text = separator.join(val_examples)

    train_tokens = torch.tensor(tokenizer.encode(train_text), dtype=torch.long)
    val_tokens = torch.tensor(tokenizer.encode(val_text), dtype=torch.long)

    print(f"  Train: {len(train_tokens):,} tokens ({len(train_examples):,} examples)")
    print(f"  Val:   {len(val_tokens):,} tokens ({len(val_examples):,} examples)")
    print(f"  Avg tokens/example: {len(train_tokens) / len(train_examples):.0f}")

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"train": train_tokens, "val": val_tokens}, output_path)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Saved to {output_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
