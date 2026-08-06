"""Frozen-model training orchestration for the unseen-identifier diagnostic (Decision 4).

Reuses the frozen model / tokenizer / trainer / config BY IMPORT (never redefined). It encodes a
cohort's serialized prompts + gold outputs into the trainer's `EncodedExample` format, asserts the
frozen recipe (parameter count == 209,728, source hashes match, no extra trainable module), then
delegates to the frozen `train_in_memory`. torch and the torch-bearing frozen model/trainer are
imported LAZILY inside functions, so importing this module has no heavy side effects.

Nothing here runs during implementation or fixture tests: training is exercised only through mocks
and structural/refusal checks. A real invocation would train exactly one authorized (seed, cohort).
"""
from __future__ import annotations

from dataclasses import dataclass

from experiments.single_hop_typed_vs_prose.tokenizer import LexicalTokenizer

from .config import EVAL_OUTPUT_TOKENS, sub_seed  # noqa: F401  (EVAL_OUTPUT_TOKENS re-exported for callers)
from .manifest import dataset_digest, example_hash_digest, frozen_recipe_source_hashes, sha256_text
from .serializer import serialize
from .tasks import Example

FROZEN_PARAMETER_COUNT = 209_728


def encode_example(example: Example, tokenizer: LexicalTokenizer | None = None):
    """Encode one Example into the frozen trainer's EncodedExample (bos + prompt + gold + eos).

    Mirrors the frozen typed-vs-prose encoding exactly: the model-visible prompt ends at the frozen
    output marker, the gold output is supervised, and the prefix is masked with the ignore index."""
    from experiments.single_hop_typed_vs_prose.config import FROZEN_MODEL_RECIPE, FROZEN_TRAIN_RECIPE
    from experiments.single_hop_typed_vs_prose.dataset import EncodedExample

    tokenizer = tokenizer or LexicalTokenizer()
    ignore = FROZEN_TRAIN_RECIPE.ignore_index
    prompt = serialize(example) + FROZEN_TRAIN_RECIPE.output_marker
    prompt_ids = tokenizer.encode(prompt)
    output_ids = tokenizer.encode(example.expected_output)
    input_prefix = 1 + len(prompt_ids)  # bos + prompt
    if input_prefix > FROZEN_MODEL_RECIPE.max_input_tokens:
        raise ValueError(
            f"input has {input_prefix} tokens, exceeds the frozen {FROZEN_MODEL_RECIPE.max_input_tokens}-token limit"
        )
    if len(output_ids) + 1 > FROZEN_MODEL_RECIPE.max_output_tokens:
        raise ValueError("gold output exceeds the frozen output-token limit")
    input_ids = (tokenizer.bos_id, *prompt_ids, *output_ids, tokenizer.eos_id)
    if len(input_ids) > FROZEN_MODEL_RECIPE.max_seq:
        raise ValueError("complete sequence exceeds frozen model context")
    labels = (*(ignore for _ in range(input_prefix)), *output_ids, tokenizer.eos_id)
    return EncodedExample(
        "UNSEEN",
        tuple(input_ids),
        tuple(labels),
        input_prefix,
        len(output_ids),
        example.example_hash,
    )


def encode_cohort(examples: list[Example], tokenizer: LexicalTokenizer | None = None) -> list:
    tokenizer = tokenizer or LexicalTokenizer()
    return [encode_example(example, tokenizer) for example in examples]


def assert_frozen_recipe(model, recorded_hashes: dict[str, str] | None = None) -> None:
    """Fail-closed: the reused model must be the exact frozen recipe (count, hashes, no extra module)."""
    count = model.parameter_count()
    if count != FROZEN_PARAMETER_COUNT:
        raise ValueError(f"parameter count {count} != frozen {FROZEN_PARAMETER_COUNT}")
    live_hashes = frozen_recipe_source_hashes()
    if recorded_hashes is not None and recorded_hashes != live_hashes:
        raise ValueError("recorded recipe hashes do not match the live frozen recipe sources")
    # No task-specific trainable head / extra module: the only submodule is the frozen LM backbone.
    child_names = {name for name, _ in model.named_children()}
    if child_names != {"lm"}:
        raise ValueError(f"unexpected trainable submodules on the reused model: {sorted(child_names)}")


@dataclass(frozen=True)
class TrainArtifacts:
    seed: int
    cohort: str
    checkpoint_path: str
    dataset_digest: str
    example_hash_digest: str
    serializer_digest: str
    initialization_digest: str
    batch_order_digest: str
    checkpoint_parameter_digest: str
    updates: int
    first_loss: float
    final_loss: float


def train_cohort(
    seed: int,
    cohort: str,
    examples: list[Example],
    checkpoint_dir: str,
    *,
    recorded_hashes: dict[str, str] | None = None,
    device: str = "cpu",
) -> TrainArtifacts:
    """Deterministically train the frozen model on one authorized (seed, cohort) and checkpoint it.

    Callers MUST have validated an authorization record and applied the reserved-seed gate before
    calling this. Determinism: init seed = sub_seed(seed, 'init'); batch order seed = sub_seed(seed,
    'batch'). The checkpoint is written atomically to <checkpoint_dir>/checkpoint.pt."""
    import importlib
    import os

    torch = importlib.import_module("torch")  # lazy: no torch at module load

    from experiments.single_hop_typed_vs_prose.model import build_model
    from experiments.single_hop_typed_vs_prose.trainer import train_in_memory

    tokenizer = LexicalTokenizer()
    serialized = [serialize(example) for example in examples]
    encoded = [encode_example(example, tokenizer) for example in examples]

    model = build_model(sub_seed(int(seed), "init"))
    assert_frozen_recipe(model, recorded_hashes)
    initialization_digest = model.parameter_digest()

    result = train_in_memory(model, encoded, seed=sub_seed(int(seed), "batch"), device=device)

    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, "checkpoint.pt")
    tmp = checkpoint_path + ".tmp"
    torch.save(model.state_dict(), tmp)
    os.replace(tmp, checkpoint_path)

    return TrainArtifacts(
        seed=int(seed),
        cohort=cohort,
        checkpoint_path=checkpoint_path,
        dataset_digest=dataset_digest(serialized),
        example_hash_digest=example_hash_digest(example.example_hash for example in examples),
        serializer_digest=sha256_text("\x00".join(serialized)),
        initialization_digest=initialization_digest,
        batch_order_digest=result.batch_order_digest,
        checkpoint_parameter_digest=result.final_parameter_digest,
        updates=result.updates,
        first_loss=result.first_loss,
        final_loss=result.final_loss,
    )
