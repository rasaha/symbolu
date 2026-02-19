"""
Harder Binding Stress Test (Benchmark A)
==========================================

Tests whether quadratic advantage scales with difficulty.

Three difficulty tiers with increasing:
  - Sequence length (more tokens per example)
  - Distractor count (more interference)
  - Nested clause depth (deeper embedding)
  - Number of entities (more confusable names)
  - Multi-hop chain length (longer reasoning paths)

If quadratic advantage grows with difficulty -> real structural benefit.
If advantage shrinks -> overfitting to easy patterns.

Difficulty tiers:
  EASY:   5-6 names, 2-4 distractors, depth 1-2, chains 2-3
  MEDIUM: 7-10 names, 5-8 distractors, depth 2-3, chains 3-4
  HARD:   10-16 names, 8-14 distractors, depth 3-4, chains 4-6
"""

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from resonant_model.dataset import (
    BindingDataset,
    BindingExample,
    FailureType,
    TemplateType,
    NAMES,
    OBJECTS,
    DISTRACTOR_TEMPLATES,
    _pick_names,
    _pick_objects,
)


class DifficultyTier(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class DifficultyConfig:
    """Parameters for a difficulty tier."""
    min_names: int
    max_names: int
    min_distractors: int
    max_distractors: int
    min_nesting: int
    max_nesting: int
    min_chain_len: int
    max_chain_len: int
    max_seq_len: int


DIFFICULTY_CONFIGS = {
    DifficultyTier.EASY: DifficultyConfig(
        min_names=5, max_names=6,
        min_distractors=2, max_distractors=4,
        min_nesting=1, max_nesting=2,
        min_chain_len=2, max_chain_len=3,
        max_seq_len=512,
    ),
    DifficultyTier.MEDIUM: DifficultyConfig(
        min_names=7, max_names=10,
        min_distractors=5, max_distractors=8,
        min_nesting=2, max_nesting=3,
        min_chain_len=3, max_chain_len=4,
        max_seq_len=512,
    ),
    DifficultyTier.HARD: DifficultyConfig(
        min_names=10, max_names=16,
        min_distractors=8, max_distractors=14,
        min_nesting=3, max_nesting=4,
        min_chain_len=4, max_chain_len=6,
        max_seq_len=512,
    ),
}

# Extended name pool for hard difficulty (need >8 unique names)
EXTENDED_NAMES = list(NAMES) + [
    "Yara", "Zane", "Bella", "Caleb", "Diana", "Ethan",
    "Fiona", "Gavin", "Holly", "Ivan", "Julia", "Kurt",
    "Luna", "Miles", "Nora", "Oscar",
]

# Extended distractor templates for harder distractors that
# introduce more confusing name mentions
HARD_DISTRACTOR_TEMPLATES = list(DISTRACTOR_TEMPLATES) + [
    "{name} mentioned something about {name2} earlier.",
    "Someone told {name} that {name2} was coming.",
    "{name} and {name2} had spoken briefly before.",
    "According to {name}, the situation with {name2} was complicated.",
    "{name} overheard {name2} talking about the matter.",
    "Both {name} and {name2} were present at the time.",
    "{name} recalled what {name2} had said yesterday.",
    "Neither {name} nor {name2} knew the full story.",
    "{name} disagreed with {name2} about the outcome.",
    "{name} had warned {name2} about this possibility.",
]


def _pick_extended_names(rng: random.Random, count: int) -> List[str]:
    """Pick distinct names from the extended pool."""
    return rng.sample(EXTENDED_NAMES, min(count, len(EXTENDED_NAMES)))


def _make_hard_distractors(
    rng: random.Random,
    names: List[str],
    count: int,
) -> List[str]:
    """Generate harder distractors that mention multiple names."""
    distractors = []
    for _ in range(count):
        template = rng.choice(HARD_DISTRACTOR_TEMPLATES)
        name = rng.choice(names)
        if "{name2}" in template:
            other_names = [n for n in names if n != name]
            name2 = rng.choice(other_names) if other_names else name
            distractors.append(template.format(name=name, name2=name2))
        else:
            distractors.append(template.format(name=name))
    return distractors


def _interleave_hard(
    rng: random.Random,
    sentences: List[str],
    distractors: List[str],
) -> Tuple[str, int]:
    """Interleave distractors more aggressively — some between every sentence."""
    if not distractors:
        passage = " ".join(sentences)
        return passage, len(passage.split())

    result = []
    dist_idx = 0

    for i, sent in enumerate(sentences):
        # Insert 1-3 distractors before each sentence (except first sometimes)
        if i > 0 and dist_idx < len(distractors):
            n_insert = rng.randint(1, min(3, len(distractors) - dist_idx))
            for _ in range(n_insert):
                if dist_idx < len(distractors):
                    result.append(distractors[dist_idx])
                    dist_idx += 1
        result.append(sent)

    # Remaining distractors scattered at end
    while dist_idx < len(distractors):
        result.insert(rng.randint(0, len(result)), distractors[dist_idx])
        dist_idx += 1

    passage = " ".join(result)
    return passage, len(passage.split())


# ─── Hard Template Generators ────────────────────────────────────────────────

def _generate_hard_give_receive(
    rng: random.Random,
    example_id: int,
    cfg: DifficultyConfig,
) -> BindingExample:
    """Multi-object transfer with confusing intermediaries."""
    num_names = rng.randint(cfg.min_names, cfg.max_names)
    names = _pick_extended_names(rng, num_names)
    objects = _pick_objects(rng, min(3, len(OBJECTS)))

    # Multiple transfers to create confusion
    giver = names[0]
    intermediary = names[1]
    receiver = names[2]
    obj = objects[0]

    core = [
        f"{giver} gave the {obj} to {intermediary}.",
        f"Then {intermediary} passed the {obj} to {receiver}.",
    ]

    # Add a second object transfer as red herring
    if len(objects) > 1 and len(names) > 3:
        obj2 = objects[1]
        red_herring = names[3]
        core.append(f"{red_herring} also gave a {obj2} to {giver}.")

    num_dist = rng.randint(cfg.min_distractors, cfg.max_distractors)
    distractors = _make_hard_distractors(rng, names, num_dist)
    passage, sep_dist = _interleave_hard(rng, core, distractors)
    question = f"Who currently has the {obj}?"

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.GIVE_RECEIVE,
        passage=passage,
        question=question,
        correct_answer=receiver,
        all_names=names,
        all_objects=objects,
        num_distractors=num_dist,
        separation_distance=sep_dist,
        nesting_depth=2,
        role_assignments={
            "giver": giver, "intermediary": intermediary,
            "receiver": receiver, "object": obj,
        },
    )


def _generate_hard_accusation(
    rng: random.Random,
    example_id: int,
    cfg: DifficultyConfig,
) -> BindingExample:
    """Deep accusation chains with multiple layers."""
    depth = rng.randint(cfg.min_nesting, cfg.max_nesting)
    num_names = rng.randint(max(cfg.min_names, depth + 2), cfg.max_names)
    names = _pick_extended_names(rng, num_names)

    if depth == 2:
        core = [f"{names[0]} accused {names[1]} of blaming {names[2]}."]
        question = f"Who did {names[1]} blame?"
        correct = names[2]
    elif depth == 3:
        core = [
            f"{names[0]} told {names[1]} that {names[2]} "
            f"accused {names[3]} of stealing.",
        ]
        question = f"According to {names[2]}, who stole?"
        correct = names[3]
    else:  # depth >= 4
        core = [
            f"{names[0]} claimed that {names[1]} reported that "
            f"{names[2]} told {names[3]} about {names[4]} lying.",
        ]
        question = f"In {names[2]}'s telling to {names[3]}, who lied?"
        correct = names[4]

    num_dist = rng.randint(cfg.min_distractors, cfg.max_distractors)
    distractors = _make_hard_distractors(rng, names, num_dist)
    passage, sep_dist = _interleave_hard(rng, core, distractors)

    roles = {f"entity_{i}": n for i, n in enumerate(names[:depth + 1])}

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.ACCUSATION_CHAIN,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=[],
        num_distractors=num_dist,
        separation_distance=sep_dist,
        nesting_depth=depth,
        role_assignments=roles,
    )


def _generate_hard_nested_clause(
    rng: random.Random,
    example_id: int,
    cfg: DifficultyConfig,
) -> BindingExample:
    """Deeply nested relative clauses."""
    depth = rng.randint(cfg.min_nesting, cfg.max_nesting)
    num_names = rng.randint(max(cfg.min_names, depth + 2), cfg.max_names)
    names = _pick_extended_names(rng, num_names)
    obj = _pick_objects(rng, 1)[0]

    if depth == 2:
        core = [
            f"{names[0]}, who {names[1]} had met at the conference, "
            f"handed the {obj} to {names[2]}.",
        ]
        question = f"Who received the {obj}?"
        correct = names[2]
    elif depth == 3:
        core = [
            f"{names[0]}, who {names[1]} had warned "
            f"after {names[2]} raised concerns, "
            f"gave the {obj} to {names[3]}.",
        ]
        question = f"Who gave the {obj} away?"
        correct = names[0]
    else:  # depth >= 4
        core = [
            f"{names[0]}, who {names[1]} told "
            f"that {names[2]}, who {names[3]} had introduced, "
            f"was trustworthy, gave the {obj} to {names[4]}.",
        ]
        question = f"Who was introduced by {names[3]}?"
        correct = names[2]

    num_dist = rng.randint(cfg.min_distractors, cfg.max_distractors)
    distractors = _make_hard_distractors(rng, names, num_dist)
    passage, sep_dist = _interleave_hard(rng, core, distractors)

    roles = {f"entity_{i}": n for i, n in enumerate(names[:depth + 2])}

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.NESTED_CLAUSE,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=[obj],
        num_distractors=num_dist,
        separation_distance=sep_dist,
        nesting_depth=depth,
        role_assignments=roles,
    )


def _generate_hard_multi_hop(
    rng: random.Random,
    example_id: int,
    cfg: DifficultyConfig,
) -> BindingExample:
    """Long multi-hop chains with distractors between each step."""
    chain_len = rng.randint(cfg.min_chain_len, cfg.max_chain_len)
    num_names = rng.randint(max(cfg.min_names, chain_len + 2), cfg.max_names)
    names = _pick_extended_names(rng, num_names)
    obj = _pick_objects(rng, 1)[0]

    chain = names[:chain_len]
    core = []
    for i in range(len(chain) - 1):
        if i == 0:
            core.append(f"{chain[i]} had the {obj} and passed it to {chain[i+1]}.")
        else:
            verbs = ["gave it to", "handed it to", "passed it to", "transferred it to"]
            verb = rng.choice(verbs)
            core.append(f"Then {chain[i]} {verb} {chain[i+1]}.")

    question = f"Who has the {obj} now?"
    correct = chain[-1]

    num_dist = rng.randint(cfg.min_distractors, cfg.max_distractors)
    distractors = _make_hard_distractors(rng, names, num_dist)
    passage, sep_dist = _interleave_hard(rng, core, distractors)

    roles = {f"step_{i}": name for i, name in enumerate(chain)}
    roles["final_holder"] = chain[-1]

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.MULTI_HOP,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=[obj],
        num_distractors=num_dist,
        separation_distance=sep_dist,
        nesting_depth=chain_len - 1,
        role_assignments=roles,
    )


def _generate_hard_borrow_lend(
    rng: random.Random,
    example_id: int,
    cfg: DifficultyConfig,
) -> BindingExample:
    """Multi-object borrowing/lending with more participants."""
    num_names = rng.randint(cfg.min_names, cfg.max_names)
    names = _pick_extended_names(rng, num_names)
    objects = _pick_objects(rng, min(4, len(OBJECTS)))

    borrower = names[0]
    lender = names[1]
    recipient = names[2]
    obj1 = objects[0]
    obj2 = objects[1]

    core = [
        f"{borrower} borrowed the {obj1} from {lender} "
        f"and lent the {obj2} to {recipient}.",
    ]

    # Add more transfers for confusion
    if len(names) > 4 and len(objects) > 2:
        core.append(
            f"Meanwhile, {names[3]} returned the {objects[2]} to {names[4]}."
        )

    q_type = rng.choice(["lender", "recipient"])
    if q_type == "lender":
        question = f"Who originally had the {obj1}?"
        correct = lender
    else:
        question = f"Who received the {obj2}?"
        correct = recipient

    num_dist = rng.randint(cfg.min_distractors, cfg.max_distractors)
    distractors = _make_hard_distractors(rng, names, num_dist)
    passage, sep_dist = _interleave_hard(rng, core, distractors)

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.BORROW_LEND,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=objects,
        num_distractors=num_dist,
        separation_distance=sep_dist,
        nesting_depth=1,
        role_assignments={
            "borrower": borrower, "lender": lender,
            "recipient": recipient, "obj1": obj1, "obj2": obj2,
        },
    )


HARD_GENERATORS = {
    TemplateType.GIVE_RECEIVE: _generate_hard_give_receive,
    TemplateType.ACCUSATION_CHAIN: _generate_hard_accusation,
    TemplateType.BORROW_LEND: _generate_hard_borrow_lend,
    TemplateType.NESTED_CLAUSE: _generate_hard_nested_clause,
    TemplateType.MULTI_HOP: _generate_hard_multi_hop,
}


def generate_harder_dataset(
    num_examples: int = 200,
    seed: int = 42,
    difficulty: DifficultyTier = DifficultyTier.MEDIUM,
) -> BindingDataset:
    """
    Generate a harder binding dataset at the specified difficulty tier.

    Args:
        num_examples: Number of examples to generate.
        seed: Random seed for reproducibility.
        difficulty: Difficulty tier (EASY, MEDIUM, HARD).

    Returns:
        BindingDataset with harder examples.
    """
    rng = random.Random(seed)
    cfg = DIFFICULTY_CONFIGS[difficulty]
    template_types = list(TemplateType)
    examples: List[BindingExample] = []

    for i in range(num_examples):
        template = template_types[i % len(template_types)]
        generator = HARD_GENERATORS[template]
        example = generator(rng, i, cfg)
        examples.append(example)

    return BindingDataset(examples=examples, seed=seed)
