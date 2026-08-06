"""Frozen evaluation + greedy decoding for the unseen-identifier diagnostic (Decision 5).

Loads an authorized checkpoint, greedily decodes each example with the frozen tokenizer and the
arm-neutral decode cap, classifies the raw output with the exact `parser` (no repair), and produces
per-example traces and per-split metrics. NO constrained decoding, NO candidate-position output, NO
output repair. torch and the frozen model are imported LAZILY. Exercised only via mocks in fixture
tests; no scientific model or cohort is evaluated here.
"""
from __future__ import annotations

from dataclasses import dataclass

from experiments.single_hop_typed_vs_prose.tokenizer import LexicalTokenizer

from .config import EVAL_OUTPUT_TOKENS, IDENTIFIER_LENGTH
from .manifest import sha256_text
from .parser import OutputCategory, parse
from .serializer import serialize
from .tasks import Example


def build_prompt_ids(example: Example, tokenizer: LexicalTokenizer | None = None) -> list[int]:
    """The exact model-visible input at generation time: bos + serialized prompt + frozen output marker."""
    from experiments.single_hop_typed_vs_prose.config import FROZEN_TRAIN_RECIPE

    tokenizer = tokenizer or LexicalTokenizer()
    prompt = serialize(example) + FROZEN_TRAIN_RECIPE.output_marker
    return [tokenizer.bos_id, *tokenizer.encode(prompt)]


def _token_match_fraction(got: str, gold: str) -> float:
    matched = sum(1 for i in range(IDENTIFIER_LENGTH) if i < len(got) and got[i] == gold[i])
    return matched / IDENTIFIER_LENGTH


def build_trace(example: Example, raw_output: str) -> dict:
    """Classify one raw output and emit the frozen per-example trace schema."""
    result = parse(raw_output, example)
    category = result.category
    exact = category is OutputCategory.EXACT_CORRECT or category is OutputCategory.CORRECT_ABSTENTION
    prompt_ids = build_prompt_ids(example)
    return {
        "example_hash": example.example_hash,
        "task": example.task_name,
        "split": example.split,
        "cohort": example.cohort,
        "seed": example.base_seed,
        "input_hash": sha256_text(serialize(example)),
        "prompt_token_count": len(prompt_ids),
        "expected_output": example.expected_output,
        "raw_output": raw_output,
        "normalized_output": result.normalized,
        "parsed_category": category.value,
        "exact_match": bool(exact),
        "token_match_fraction": (
            0.0 if example.expected_abstention else _token_match_fraction(result.normalized, example.expected_output)
        ),
        "wrong_in_context": category is OutputCategory.WRONG_IN_CONTEXT,
        "fabricated_out_of_context": category is OutputCategory.FABRICATED_OUT_OF_CONTEXT,
        "abstention": category in (OutputCategory.CORRECT_ABSTENTION, OutputCategory.FALSE_ABSTENTION),
    }


@dataclass(frozen=True)
class EvalArtifacts:
    traces: tuple[dict, ...]
    parser_category_counts: dict[str, dict[str, int]]
    prediction_digest: str


def _decode_one(model, prompt_ids, tokenizer, device):
    from experiments.single_hop_typed_vs_prose.model import greedy_generate

    return greedy_generate(
        model,
        prompt_ids,
        tokenizer=tokenizer,
        max_output_tokens=EVAL_OUTPUT_TOKENS,
        device=device,
    )


def evaluate_cohort(
    checkpoint_path: str,
    cohort_by_split: dict[str, list[Example]],
    *,
    device: str = "cpu",
    decode_fn=None,
) -> EvalArtifacts:
    """Greedy-decode + classify every example, grouped by split, producing traces and category counts.

    `decode_fn(model, prompt_ids, tokenizer, device) -> raw_output` is injectable for fixture tests
    (so the model need not run); by default the frozen greedy decoder is used. Callers must have
    validated authorization before reaching this path."""
    from .config import sub_seed as _sub_seed  # noqa: F401  (kept for provenance parity)

    tokenizer = LexicalTokenizer()
    decode_fn = decode_fn or _decode_one

    model = None
    if decode_fn is _decode_one:
        import importlib

        torch = importlib.import_module("torch")  # lazy: no torch at module load

        from experiments.single_hop_typed_vs_prose.model import build_model

        model = build_model(0)
        model.load_state_dict(torch.load(checkpoint_path, map_location=device))
        model.eval()

    traces: list[dict] = []
    category_counts: dict[str, dict[str, int]] = {}
    for split in sorted(cohort_by_split):
        counts: dict[str, int] = {}
        for example in cohort_by_split[split]:
            prompt_ids = build_prompt_ids(example, tokenizer)
            raw_output = decode_fn(model, prompt_ids, tokenizer, device)
            trace = build_trace(example, raw_output)
            traces.append(trace)
            counts[trace["parsed_category"]] = counts.get(trace["parsed_category"], 0) + 1
        category_counts[split] = counts

    prediction_digest = sha256_text(
        "\n".join(f"{t['example_hash']}:{t['normalized_output']}" for t in traces)
    )
    return EvalArtifacts(
        traces=tuple(traces),
        parser_category_counts=category_counts,
        prediction_digest=prediction_digest,
    )
