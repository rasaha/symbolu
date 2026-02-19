"""
SCAN-style Compositional Generalization Benchmark (Benchmark B)
=================================================================

Tests whether quadratic attention helps systematic compositional
generalization — the ability to understand novel combinations of
known primitives.

Inspired by the SCAN benchmark (Lake & Baroni, 2018):
  - Train on primitive commands and simple compositions
  - Test on held-out novel compositions
  - Measure exact-match accuracy on output sequences

Our variant uses role-binding compositions:
  - Primitive actions: GIVE, TAKE, PASS, SHOW, HIDE
  - Modifiers: LEFT, RIGHT, TWICE, TO_THIRD_PARTY
  - Compositions: action + modifier combos

Training split:  All primitives + common compositions
Test split:      Novel compositions (unseen combos of seen parts)

If quadratic helps compositional generalization:
  -> Cross-task evidence for structural benefit.
If quadratic only helps binding:
  -> Effect is narrow (still real, just task-specific).

The task is framed as sequence-to-sequence mapping where the model
must output the correct role assignment given a compositional command.
We adapt this to the binding framework: the "passage" is a narrative
encoding of the command, and the "question" asks about the result.
"""

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

from resonant_model.dataset import (
    BindingDataset,
    BindingExample,
    TemplateType,
    NAMES,
    OBJECTS,
)


# ─── Compositional Grammar ──────────────────────────────────────────────────

class Action(Enum):
    GIVE = "give"
    TAKE = "take"
    PASS = "pass"
    SHOW = "show"
    HIDE = "hide"


class Modifier(Enum):
    NONE = "none"
    REVERSE = "reverse"       # swap agent/patient roles
    CHAIN = "chain"           # A -> B -> C (multi-hop)
    CONDITIONAL = "conditional"  # only if X, then action
    SIMULTANEOUS = "simultaneous"  # two actions at once


# Action templates: how each action maps to role assignments
ACTION_TEMPLATES = {
    Action.GIVE: {
        "sentence": "{agent} gave the {obj} to {patient}.",
        "question": "Who received the {obj}?",
        "answer_role": "patient",
    },
    Action.TAKE: {
        "sentence": "{agent} took the {obj} from {patient}.",
        "question": "Who lost the {obj}?",
        "answer_role": "patient",
    },
    Action.PASS: {
        "sentence": "{agent} passed the {obj} to {patient}.",
        "question": "Who has the {obj} now?",
        "answer_role": "patient",
    },
    Action.SHOW: {
        "sentence": "{agent} showed the {obj} to {patient}.",
        "question": "Who saw the {obj}?",
        "answer_role": "patient",
    },
    Action.HIDE: {
        "sentence": "{agent} hid the {obj} from {patient}.",
        "question": "Who doesn't know about the {obj}?",
        "answer_role": "patient",
    },
}


@dataclass
class Composition:
    """A specific action + modifier combination."""
    action: Action
    modifier: Modifier
    is_novel: bool = False  # True = held out for test split


def _get_all_compositions() -> List[Composition]:
    """Generate all action x modifier combinations."""
    comps = []
    for action in Action:
        for modifier in Modifier:
            comps.append(Composition(action=action, modifier=modifier))
    return comps


def _define_splits(
    seed: int = 42,
    novel_fraction: float = 0.3,
) -> Tuple[List[Composition], List[Composition]]:
    """
    Split compositions into train and test (novel) sets.

    Strategy: Hold out specific action-modifier combinations.
    Every action and every modifier appears in training,
    but some specific combos are novel.

    This tests systematic generalization: can the model
    combine known parts in new ways?
    """
    rng = random.Random(seed)
    all_comps = _get_all_compositions()

    # Ensure every action and modifier has at least one training example
    # Hold out ~30% of combinations as novel
    train_comps = []
    test_comps = []

    # Track which actions/modifiers have training examples
    action_has_train: Set[Action] = set()
    modifier_has_train: Set[Modifier] = set()

    # Shuffle for randomness
    rng.shuffle(all_comps)

    # First pass: ensure coverage
    for comp in all_comps:
        if comp.action not in action_has_train or comp.modifier not in modifier_has_train:
            train_comps.append(comp)
            action_has_train.add(comp.action)
            modifier_has_train.add(comp.modifier)

    # Second pass: split remaining
    remaining = [c for c in all_comps if c not in train_comps]
    n_test = max(1, int(len(all_comps) * novel_fraction) - len(test_comps))

    # Pick test compositions from remaining
    rng.shuffle(remaining)
    for comp in remaining[:n_test]:
        comp.is_novel = True
        test_comps.append(comp)

    # Rest goes to train
    for comp in remaining[n_test:]:
        train_comps.append(comp)

    return train_comps, test_comps


# ─── Example Generation ─────────────────────────────────────────────────────

def _generate_primitive_example(
    rng: random.Random,
    example_id: int,
    action: Action,
    names: List[str],
    obj: str,
    num_distractors: int,
) -> BindingExample:
    """Generate a primitive (no modifier) example."""
    agent = names[0]
    patient = names[1]
    template = ACTION_TEMPLATES[action]

    sentence = template["sentence"].format(
        agent=agent, patient=patient, obj=obj,
    )

    # Add distractors
    dist_sentences = []
    for _ in range(num_distractors):
        n = rng.choice(names)
        dist_sentences.append(f"{n} was nearby at the time.")
    rng.shuffle(dist_sentences)

    parts = [sentence] + dist_sentences
    passage = " ".join(parts)
    question = template["question"].format(obj=obj)
    correct = patient if template["answer_role"] == "patient" else agent

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.GIVE_RECEIVE,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=[obj],
        num_distractors=num_distractors,
        separation_distance=len(passage.split()),
        nesting_depth=1,
        role_assignments={"agent": agent, "patient": patient, "object": obj},
    )


def _generate_reverse_example(
    rng: random.Random,
    example_id: int,
    action: Action,
    names: List[str],
    obj: str,
    num_distractors: int,
) -> BindingExample:
    """Generate a REVERSE modifier example — roles swapped from typical."""
    agent = names[0]
    patient = names[1]

    # In reverse: the sentence describes the action, but roles are swapped
    # e.g., "Bob gave the book to Alice" but we ask "Who gave the book?"
    # Answer: Bob (the agent, not the patient)
    template = ACTION_TEMPLATES[action]
    sentence = template["sentence"].format(
        agent=agent, patient=patient, obj=obj,
    )

    # The twist: question asks about the agent role
    reverse_questions = {
        Action.GIVE: f"Who gave the {obj} away?",
        Action.TAKE: f"Who took the {obj}?",
        Action.PASS: f"Who passed the {obj}?",
        Action.SHOW: f"Who showed the {obj}?",
        Action.HIDE: f"Who hid the {obj}?",
    }

    dist_sentences = []
    for _ in range(num_distractors):
        n = rng.choice(names)
        dist_sentences.append(f"{n} watched from the doorway.")
    rng.shuffle(dist_sentences)

    passage = " ".join([sentence] + dist_sentences)
    question = reverse_questions[action]
    correct = agent  # reverse asks about agent

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.GIVE_RECEIVE,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=[obj],
        num_distractors=num_distractors,
        separation_distance=len(passage.split()),
        nesting_depth=1,
        role_assignments={"agent": agent, "patient": patient, "object": obj},
    )


def _generate_chain_example(
    rng: random.Random,
    example_id: int,
    action: Action,
    names: List[str],
    obj: str,
    num_distractors: int,
) -> BindingExample:
    """Generate a CHAIN modifier example — multi-hop A->B->C."""
    a, b, c = names[0], names[1], names[2]

    verb_map = {
        Action.GIVE: "gave", Action.TAKE: "took",
        Action.PASS: "passed", Action.SHOW: "showed",
        Action.HIDE: "hid",
    }
    verb = verb_map[action]

    preposition = "from" if action == Action.TAKE else "to"

    sentences = [
        f"{a} {verb} the {obj} {preposition} {b}.",
        f"Then {b} {verb} the {obj} {preposition} {c}.",
    ]

    dist_sentences = []
    for _ in range(num_distractors):
        n = rng.choice(names)
        dist_sentences.append(f"{n} didn't notice what happened.")

    all_parts = []
    all_parts.append(sentences[0])
    for d in dist_sentences[:len(dist_sentences)//2]:
        all_parts.append(d)
    all_parts.append(sentences[1])
    for d in dist_sentences[len(dist_sentences)//2:]:
        all_parts.append(d)

    passage = " ".join(all_parts)

    if action == Action.TAKE:
        question = f"Who lost the {obj} first?"
        correct = a  # A had it taken by B
    else:
        question = f"Who has the {obj} at the end?"
        correct = c  # final recipient

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.MULTI_HOP,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=[obj],
        num_distractors=num_distractors,
        separation_distance=len(passage.split()),
        nesting_depth=2,
        role_assignments={
            "step_0": a, "step_1": b, "step_2": c,
            "final": correct, "object": obj,
        },
    )


def _generate_conditional_example(
    rng: random.Random,
    example_id: int,
    action: Action,
    names: List[str],
    obj: str,
    num_distractors: int,
) -> BindingExample:
    """Generate a CONDITIONAL modifier — 'If X then action'."""
    agent = names[0]
    patient = names[1]
    condition_person = names[2]

    verb_map = {
        Action.GIVE: "gave", Action.TAKE: "took",
        Action.PASS: "passed", Action.SHOW: "showed",
        Action.HIDE: "hid",
    }
    verb = verb_map[action]
    preposition = "from" if action == Action.TAKE else "to"

    # Condition was met
    sentences = [
        f"If {condition_person} agreed, then {agent} would {action.value} "
        f"the {obj} {preposition} {patient}.",
        f"{condition_person} agreed.",
        f"So {agent} {verb} the {obj} {preposition} {patient}.",
    ]

    dist_sentences = []
    for _ in range(num_distractors):
        n = rng.choice(names)
        dist_sentences.append(f"{n} waited for the outcome.")

    all_parts = sentences[:2]
    all_parts.extend(dist_sentences)
    all_parts.append(sentences[2])

    passage = " ".join(all_parts)
    template = ACTION_TEMPLATES[action]
    question = template["question"].format(obj=obj)
    correct = patient

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.NESTED_CLAUSE,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=[obj],
        num_distractors=num_distractors,
        separation_distance=len(passage.split()),
        nesting_depth=2,
        role_assignments={
            "agent": agent, "patient": patient,
            "condition": condition_person, "object": obj,
        },
    )


def _generate_simultaneous_example(
    rng: random.Random,
    example_id: int,
    action: Action,
    names: List[str],
    obj: str,
    num_distractors: int,
) -> BindingExample:
    """Generate a SIMULTANEOUS modifier — two actions at once."""
    agent1 = names[0]
    patient1 = names[1]
    agent2 = names[2]
    patient2 = names[3]
    objects = [obj, rng.choice(OBJECTS)]
    while objects[1] == objects[0]:
        objects[1] = rng.choice(OBJECTS)

    verb_map = {
        Action.GIVE: "gave", Action.TAKE: "took",
        Action.PASS: "passed", Action.SHOW: "showed",
        Action.HIDE: "hid",
    }
    verb = verb_map[action]
    preposition = "from" if action == Action.TAKE else "to"

    sentences = [
        f"At the same time, {agent1} {verb} the {objects[0]} {preposition} "
        f"{patient1} while {agent2} {verb} the {objects[1]} {preposition} "
        f"{patient2}.",
    ]

    dist_sentences = []
    for _ in range(num_distractors):
        n = rng.choice(names)
        dist_sentences.append(f"{n} observed both transactions.")

    all_parts = sentences + dist_sentences
    passage = " ".join(all_parts)

    # Ask about second action (harder — requires tracking parallel events)
    template = ACTION_TEMPLATES[action]
    question = template["question"].format(obj=objects[1])
    correct = patient2

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.BORROW_LEND,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=objects,
        num_distractors=num_distractors,
        separation_distance=len(passage.split()),
        nesting_depth=1,
        role_assignments={
            "agent1": agent1, "patient1": patient1,
            "agent2": agent2, "patient2": patient2,
            "obj1": objects[0], "obj2": objects[1],
        },
    )


MODIFIER_GENERATORS = {
    Modifier.NONE: _generate_primitive_example,
    Modifier.REVERSE: _generate_reverse_example,
    Modifier.CHAIN: _generate_chain_example,
    Modifier.CONDITIONAL: _generate_conditional_example,
    Modifier.SIMULTANEOUS: _generate_simultaneous_example,
}


def _generate_example(
    rng: random.Random,
    example_id: int,
    comp: Composition,
    num_distractors: int,
    num_names: int,
) -> BindingExample:
    """Generate one example from a composition specification."""
    names = rng.sample(NAMES, min(num_names, len(NAMES)))
    obj = rng.choice(OBJECTS)
    generator = MODIFIER_GENERATORS[comp.modifier]
    return generator(rng, example_id, comp.action, names, obj, num_distractors)


# ─── Dataset Generation ─────────────────────────────────────────────────────

@dataclass
class SCANSplitDataset:
    """Train/test split for compositional generalization."""
    train: BindingDataset
    test: BindingDataset
    train_compositions: List[Composition]
    test_compositions: List[Composition]
    seed: int = 42


def generate_scan_dataset(
    num_train: int = 300,
    num_test: int = 100,
    seed: int = 42,
    num_distractors: int = 3,
    num_names: int = 6,
) -> SCANSplitDataset:
    """
    Generate a SCAN-style compositional generalization dataset.

    Train set: examples from training compositions (seen combos).
    Test set:  examples from novel compositions (unseen combos).

    Each composition (action + modifier) generates multiple examples
    with different names, objects, and distractors.

    Args:
        num_train: Total training examples.
        num_test: Total test examples.
        seed: Random seed.
        num_distractors: Distractors per example.
        num_names: Names per example.

    Returns:
        SCANSplitDataset with train and test splits.
    """
    rng = random.Random(seed)
    train_comps, test_comps = _define_splits(seed=seed)

    # Generate training examples
    train_examples = []
    for i in range(num_train):
        comp = train_comps[i % len(train_comps)]
        example = _generate_example(rng, i, comp, num_distractors, num_names)
        train_examples.append(example)

    # Generate test examples from novel compositions
    test_examples = []
    for i in range(num_test):
        comp = test_comps[i % len(test_comps)]
        example = _generate_example(
            rng, num_train + i, comp, num_distractors, num_names,
        )
        test_examples.append(example)

    return SCANSplitDataset(
        train=BindingDataset(examples=train_examples, seed=seed),
        test=BindingDataset(examples=test_examples, seed=seed),
        train_compositions=train_comps,
        test_compositions=test_comps,
        seed=seed,
    )
