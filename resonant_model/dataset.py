"""
Synthetic Role-Filler Binding Dataset Generator
=================================================

Generates structured binding examples that isolate role-filler tracking
from general language modeling. Each example:

1. Assigns roles (agent, patient, recipient, etc.) to named entities.
2. Inserts distractor sentences between role assignments and queries.
3. Varies separation distance and clause nesting depth.
4. Has exactly one correct answer determined by structural parsing.

Templates:
  - Give/receive (agent -> patient via object)
  - Accusation chains (nested blame/accusation)
  - Borrow/lend (multi-object transfers)
  - Nested clauses (embedded relative clauses)
  - Multi-hop chains (transitive role tracking)
"""

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


# ─── Name and Object Pools ───────────────────────────────────────────────────

NAMES = [
    "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
    "Iris", "Jack", "Karen", "Leo", "Mona", "Nick", "Olivia", "Paul",
    "Quinn", "Rita", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xavier",
]

OBJECTS = [
    "book", "lamp", "key", "phone", "wallet", "ring", "pen", "watch",
    "bag", "coat", "scarf", "hat", "ticket", "letter", "coin", "medal",
    "laptop", "umbrella", "guitar", "camera", "telescope", "compass",
]

DISTRACTOR_TEMPLATES = [
    "Meanwhile, {name} went to the store.",
    "{name} was thinking about the weather.",
    "The room was quiet except for {name} humming a tune.",
    "{name} looked out the window and sighed.",
    "Earlier that day, {name} had eaten breakfast alone.",
    "{name} remembered a conversation from last week.",
    "Outside, {name} noticed the clouds gathering.",
    "{name} checked the time and frowned.",
    "A bird flew past while {name} was standing there.",
    "{name} adjusted their glasses and continued.",
    "The clock on the wall reminded {name} of an appointment.",
    "{name} paced back and forth in the hallway.",
]


class TemplateType(Enum):
    """Types of binding templates."""
    GIVE_RECEIVE = auto()
    ACCUSATION_CHAIN = auto()
    BORROW_LEND = auto()
    NESTED_CLAUSE = auto()
    MULTI_HOP = auto()


class FailureType(Enum):
    """Types of binding failures for error classification."""
    ROLE_SWAP = "role_swap"
    NEAREST_NAME_BIAS = "nearest_name_bias"
    OBJECT_CONFUSION = "object_confusion"
    RANDOM_GUESS = "random_guess"
    CORRECT = "correct"


@dataclass
class BindingExample:
    """A single binding benchmark example."""
    example_id: int
    template_type: TemplateType
    passage: str
    question: str
    correct_answer: str
    all_names: List[str]
    all_objects: List[str]
    num_distractors: int
    separation_distance: int      # tokens between role assignment and query
    nesting_depth: int            # depth of clause nesting
    role_assignments: Dict[str, str]  # role -> name mapping


@dataclass
class BindingDataset:
    """Collection of binding examples with metadata."""
    examples: List[BindingExample] = field(default_factory=list)
    seed: int = 42

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> BindingExample:
        return self.examples[idx]

    def __iter__(self):
        return iter(self.examples)

    @property
    def template_distribution(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for ex in self.examples:
            key = ex.template_type.name
            counts[key] = counts.get(key, 0) + 1
        return counts


# ─── Template Generators ─────────────────────────────────────────────────────

def _pick_names(rng: random.Random, count: int) -> List[str]:
    """Pick distinct names."""
    return rng.sample(NAMES, min(count, len(NAMES)))


def _pick_objects(rng: random.Random, count: int) -> List[str]:
    """Pick distinct objects."""
    return rng.sample(OBJECTS, min(count, len(OBJECTS)))


def _make_distractors(
    rng: random.Random,
    names: List[str],
    count: int,
) -> List[str]:
    """Generate distractor sentences using names from the example."""
    distractors = []
    for _ in range(count):
        template = rng.choice(DISTRACTOR_TEMPLATES)
        name = rng.choice(names)
        distractors.append(template.format(name=name))
    return distractors


def _interleave_distractors(
    rng: random.Random,
    sentences: List[str],
    distractors: List[str],
) -> Tuple[str, int]:
    """Insert distractors between sentences. Returns passage and separation distance."""
    if not distractors:
        passage = " ".join(sentences)
        return passage, len(passage.split())

    result = [sentences[0]]
    for i, sent in enumerate(sentences[1:], 1):
        # Insert some distractors before this sentence
        n_insert = min(len(distractors), rng.randint(1, max(1, len(distractors) // len(sentences))))
        for _ in range(n_insert):
            if distractors:
                result.append(distractors.pop(0))
        result.append(sent)

    # Append remaining distractors before the last content
    for d in distractors:
        result.insert(-1, d)

    passage = " ".join(result)
    # Separation distance: tokens between first role mention and last
    words = passage.split()
    return passage, len(words)


def _generate_give_receive(
    rng: random.Random,
    example_id: int,
    num_names: int,
    num_distractors: int,
) -> BindingExample:
    """Template: '[A] gave the [Object] to [B]. Who received the [Object]?'"""
    names = _pick_names(rng, num_names)
    objects = _pick_objects(rng, 1)
    obj = objects[0]
    giver = names[0]
    receiver = names[1]

    core_sentences = [
        f"{giver} gave the {obj} to {receiver}.",
    ]

    distractors = _make_distractors(rng, names, num_distractors)
    passage, sep_dist = _interleave_distractors(rng, core_sentences, distractors)
    question = f"Who received the {obj}?"

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.GIVE_RECEIVE,
        passage=passage,
        question=question,
        correct_answer=receiver,
        all_names=names,
        all_objects=objects,
        num_distractors=num_distractors,
        separation_distance=sep_dist,
        nesting_depth=1,
        role_assignments={"giver": giver, "receiver": receiver, "object": obj},
    )


def _generate_accusation_chain(
    rng: random.Random,
    example_id: int,
    num_names: int,
    num_distractors: int,
) -> BindingExample:
    """Template: '[A] accused [B] of blaming [C]. Who did [B] blame?'"""
    names = _pick_names(rng, max(num_names, 4))
    accuser = names[0]
    accused = names[1]
    blamed = names[2]

    # Vary the accusation depth
    depth = rng.choice([2, 3])

    if depth == 2:
        core_sentences = [
            f"{accuser} accused {accused} of blaming {blamed}.",
        ]
        question = f"Who did {accused} blame?"
        correct = blamed
        nesting = 2
        roles = {"accuser": accuser, "accused": accused, "blamed": blamed}
    else:
        instigator = names[3]
        core_sentences = [
            f"{accuser} told {accused} that {blamed} insulted {instigator}.",
        ]
        question = f"Who was insulted?"
        correct = instigator
        nesting = 3
        roles = {
            "teller": accuser, "listener": accused,
            "insulter": blamed, "insulted": instigator,
        }

    distractors = _make_distractors(rng, names, num_distractors)
    passage, sep_dist = _interleave_distractors(rng, core_sentences, distractors)

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.ACCUSATION_CHAIN,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=[],
        num_distractors=num_distractors,
        separation_distance=sep_dist,
        nesting_depth=nesting,
        role_assignments=roles,
    )


def _generate_borrow_lend(
    rng: random.Random,
    example_id: int,
    num_names: int,
    num_distractors: int,
) -> BindingExample:
    """Template: '[A] borrowed [Obj1] from [B] and lent [Obj2] to [C].'"""
    names = _pick_names(rng, max(num_names, 3))
    objects = _pick_objects(rng, 2)

    borrower = names[0]
    lender = names[1]
    recipient = names[2]
    obj1 = objects[0]
    obj2 = objects[1]

    core_sentences = [
        f"{borrower} borrowed the {obj1} from {lender} and lent the {obj2} to {recipient}.",
    ]

    # Ask about one of the objects
    q_type = rng.choice(["lender", "recipient"])
    if q_type == "lender":
        question = f"Who originally had the {obj1}?"
        correct = lender
    else:
        question = f"Who received the {obj2}?"
        correct = recipient

    distractors = _make_distractors(rng, names, num_distractors)
    passage, sep_dist = _interleave_distractors(rng, core_sentences, distractors)

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.BORROW_LEND,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=objects,
        num_distractors=num_distractors,
        separation_distance=sep_dist,
        nesting_depth=1,
        role_assignments={
            "borrower": borrower, "lender": lender,
            "recipient": recipient, "obj1": obj1, "obj2": obj2,
        },
    )


def _generate_nested_clause(
    rng: random.Random,
    example_id: int,
    num_names: int,
    num_distractors: int,
) -> BindingExample:
    """Template: nested relative clauses with 3-5 entities."""
    names = _pick_names(rng, max(num_names, 5))
    objects = _pick_objects(rng, 1)
    obj = objects[0]

    # Build nested clause structure
    depth = rng.choice([2, 3])

    if depth == 2:
        # "[A], who had spoken to [B], handed the [obj] to [C]."
        speaker = names[0]
        listener = names[1]
        receiver = names[2]
        core_sentences = [
            f"{speaker}, who had spoken to {listener}, handed the {obj} to {receiver}.",
        ]
        question = f"Who received the {obj}?"
        correct = receiver
        roles = {"speaker": speaker, "listener": listener, "receiver": receiver}
    else:
        # "[A], who [B] had warned about [C], gave the [obj] to [D]."
        actor = names[0]
        warner = names[1]
        warned_about = names[2]
        receiver = names[3]
        core_sentences = [
            f"{actor}, who {warner} had warned about {warned_about}, gave the {obj} to {receiver}.",
        ]
        question = f"Who gave the {obj}?"
        correct = actor
        roles = {
            "actor": actor, "warner": warner,
            "warned_about": warned_about, "receiver": receiver,
        }

    distractors = _make_distractors(rng, names, num_distractors)
    passage, sep_dist = _interleave_distractors(rng, core_sentences, distractors)

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.NESTED_CLAUSE,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=objects,
        num_distractors=num_distractors,
        separation_distance=sep_dist,
        nesting_depth=depth,
        role_assignments=roles,
    )


def _generate_multi_hop(
    rng: random.Random,
    example_id: int,
    num_names: int,
    num_distractors: int,
) -> BindingExample:
    """Template: multi-hop transitive chains requiring tracking across steps."""
    names = _pick_names(rng, max(num_names, 5))
    objects = _pick_objects(rng, 1)
    obj = objects[0]

    chain_len = rng.choice([3, 4])

    # Build a chain: A passed to B, B passed to C, C passed to D
    chain = names[:chain_len]
    core_sentences = []
    for i in range(len(chain) - 1):
        if i == 0:
            core_sentences.append(f"{chain[i]} had the {obj} and passed it to {chain[i+1]}.")
        else:
            core_sentences.append(f"Then {chain[i]} gave it to {chain[i+1]}.")

    question = f"Who has the {obj} now?"
    correct = chain[-1]

    distractors = _make_distractors(rng, names, num_distractors)
    passage, sep_dist = _interleave_distractors(rng, core_sentences, distractors)

    roles = {f"step_{i}": name for i, name in enumerate(chain)}
    roles["final_holder"] = chain[-1]

    return BindingExample(
        example_id=example_id,
        template_type=TemplateType.MULTI_HOP,
        passage=passage,
        question=question,
        correct_answer=correct,
        all_names=names,
        all_objects=objects,
        num_distractors=num_distractors,
        separation_distance=sep_dist,
        nesting_depth=chain_len - 1,
        role_assignments=roles,
    )


# ─── Dataset Generation ──────────────────────────────────────────────────────

GENERATORS = {
    TemplateType.GIVE_RECEIVE: _generate_give_receive,
    TemplateType.ACCUSATION_CHAIN: _generate_accusation_chain,
    TemplateType.BORROW_LEND: _generate_borrow_lend,
    TemplateType.NESTED_CLAUSE: _generate_nested_clause,
    TemplateType.MULTI_HOP: _generate_multi_hop,
}


def generate_dataset(
    num_examples: int = 200,
    seed: int = 42,
    min_names: int = 5,
    max_names: int = 8,
    min_distractors: int = 2,
    max_distractors: int = 6,
) -> BindingDataset:
    """
    Generate a synthetic role-filler binding dataset.

    Args:
        num_examples: Number of examples to generate.
        seed: Random seed for reproducibility.
        min_names: Minimum unique names per example.
        max_names: Maximum unique names per example.
        min_distractors: Minimum distractor sentences.
        max_distractors: Maximum distractor sentences.

    Returns:
        BindingDataset with generated examples.
    """
    rng = random.Random(seed)
    template_types = list(TemplateType)
    examples: List[BindingExample] = []

    for i in range(num_examples):
        template = template_types[i % len(template_types)]
        num_names = rng.randint(min_names, max_names)
        num_distractors = rng.randint(min_distractors, max_distractors)

        generator = GENERATORS[template]
        example = generator(rng, i, num_names, num_distractors)
        examples.append(example)

    return BindingDataset(examples=examples, seed=seed)
