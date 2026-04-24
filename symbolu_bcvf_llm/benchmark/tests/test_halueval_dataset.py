"""HaluEvalBenchmark unit tests — row conversion and dataset loading,
exercised offline via mocks so no torch/HF Hub required."""

from __future__ import annotations

from unittest import mock

import pytest

from symbolu_bcvf_llm.benchmark.dataset import (
    HaluEvalBenchmark,
    Question,
    TruthfulQABenchmark,
)

_DATASETS_AVAILABLE = True
try:
    import datasets  # noqa: F401
except ImportError:
    _DATASETS_AVAILABLE = False


class _FakeTokenizer:
    """Minimal tokenizer — encode returns list[int] one id per char."""

    vocab_size = 128
    eos_token_id = 2

    def encode(self, text, add_special_tokens=True):
        return [1 if add_special_tokens else 0] + [ord(c) % 127 for c in text]

    def decode(self, tokens, skip_special_tokens=True):
        return "".join(chr(int(t)) for t in tokens if t < 127)


def _fake_halueval_bench() -> HaluEvalBenchmark:
    """Bypass the torch-gated __init__; populate only what _convert_row
    and paraphrase-cache helpers need."""
    bench = HaluEvalBenchmark.__new__(HaluEvalBenchmark)
    bench._tokenizer = _FakeTokenizer()
    bench._model_name = "test-model"
    bench._paraphraser_model_name = "test-model"
    bench._split = "data"
    bench._halueval_dataset = "pminervini/HaluEval"
    bench._halueval_subset = "qa"
    bench._use_paraphrase = False
    bench._paraphrase_max_new_tokens = 32
    bench._paraphrase_cache = {}
    bench._paraphrase_cache_file = None
    bench._paraphrase_cache_loaded = 0
    bench._paraphrase_cache_discarded_reason = None
    bench._paraphrase_hits = 0
    bench._paraphrase_misses = 0
    bench._rewrite_seed_pair = (1, 2)
    bench._evaluation_seed = 1
    bench._model = object()
    bench._tokenizer_obj = bench._tokenizer
    bench._paraphraser_model = bench._model
    bench._paraphraser_tokenizer = bench._tokenizer
    return bench


# --------------------------------------------------------------------------- #
# Row conversion
# --------------------------------------------------------------------------- #


def test_convert_row_builds_2_choice_question():
    bench = _fake_halueval_bench()
    row = {
        "question": "What color is the sky?",
        "right_answer": "Blue",
        "hallucinated_answer": "Green",
    }
    q = bench._convert_row(row, idx=7)
    assert isinstance(q, Question)
    assert q.choices == ["Blue", "Green"]
    assert q.correct_index == 0
    assert len(q.choice_tokens) == 2
    assert q.metadata["halueval_row_id"] == 7


def test_convert_row_tokenizes_with_space_prefix():
    """Tokenizer should receive the choice preceded by a space so
    tokenization is natural after 'A:'."""
    bench = _fake_halueval_bench()
    received_inputs = []

    def capture_encode(text, add_special_tokens=True):
        received_inputs.append((text, add_special_tokens))
        return [1] + [ord(c) % 127 for c in text]

    bench._tokenizer = type(
        "T", (), {
            "encode": lambda self, text, add_special_tokens=True:
                capture_encode(text, add_special_tokens),
        },
    )()
    row = {
        "question": "Q?",
        "right_answer": "right",
        "hallucinated_answer": "wrong",
    }
    bench._convert_row(row, idx=0)

    # Encodes called: once for prompt, twice for choices.
    assert any(t[0].startswith("Q:") for t in received_inputs), received_inputs
    assert (" right", False) in received_inputs
    assert (" wrong", False) in received_inputs


def test_convert_row_prompt_includes_question_text():
    bench = _fake_halueval_bench()
    row = {
        "question": "Who wrote Hamlet?",
        "right_answer": "Shakespeare",
        "hallucinated_answer": "Marlowe",
    }
    q = bench._convert_row(row, idx=0)
    # Prompt tokens are the tokenized "Q: ...\nA:" string; decoding via
    # the fake tokenizer gives us back the prompt text chars.
    decoded = bench._tokenizer.decode(q.prompt_tokens)
    assert "Who wrote Hamlet?" in decoded
    assert "A:" in decoded


# --------------------------------------------------------------------------- #
# Dataset loading (mocked)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not _DATASETS_AVAILABLE,
    reason="datasets library not installed in this env",
)
def test_load_questions_uses_configured_dataset_and_subset():
    bench = _fake_halueval_bench()
    bench._halueval_dataset = "customorg/customds"
    bench._halueval_subset = "qa_custom_subset"

    fake_rows = [
        {"question": "q0?", "right_answer": "r0", "hallucinated_answer": "w0"},
        {"question": "q1?", "right_answer": "r1", "hallucinated_answer": "w1"},
    ]

    call_args = {}

    def fake_load_dataset(dataset, subset, *, split):
        call_args["dataset"] = dataset
        call_args["subset"] = subset
        call_args["split"] = split
        # datasets.Dataset quacks enough with __iter__ + len + .select
        class _DS:
            def __iter__(self):
                return iter(fake_rows)

            def __len__(self):
                return len(fake_rows)

            def select(self, indices):
                selected = [fake_rows[i] for i in indices]
                return _DS._wrap(selected)

            @classmethod
            def _wrap(cls, rows):
                inst = cls()
                inst.__iter__ = lambda self=inst: iter(rows)
                inst.__len__ = lambda self=inst: len(rows)
                inst.select = lambda indices, rows=rows: cls._wrap(
                    [rows[i] for i in indices]
                )
                return inst

        return _DS()

    with mock.patch(
        "datasets.load_dataset", side_effect=fake_load_dataset,
    ):
        bench._load_questions(split="data", max_questions=None)

    assert call_args["dataset"] == "customorg/customds"
    assert call_args["subset"] == "qa_custom_subset"
    assert call_args["split"] == "data"
    assert len(bench._questions) == 2
    assert bench._questions[0].choices == ["r0", "w0"]
    assert bench._questions[1].choices == ["r1", "w1"]


@pytest.mark.skipif(
    not _DATASETS_AVAILABLE,
    reason="datasets library not installed in this env",
)
def test_load_questions_respects_max_questions():
    bench = _fake_halueval_bench()
    fake_rows = [
        {"question": f"q{i}?", "right_answer": f"r{i}",
         "hallucinated_answer": f"w{i}"}
        for i in range(5)
    ]

    def fake_load_dataset(dataset, subset, *, split):
        class _DS:
            def __iter__(self):
                return iter(fake_rows)

            def __len__(self):
                return len(fake_rows)

            def select(self, indices):
                subset_rows = [fake_rows[i] for i in indices]

                class _Sub:
                    def __iter__(self_inner):
                        return iter(subset_rows)

                    def __len__(self_inner):
                        return len(subset_rows)

                return _Sub()

        return _DS()

    with mock.patch(
        "datasets.load_dataset", side_effect=fake_load_dataset,
    ):
        bench._load_questions(split="data", max_questions=3)

    assert len(bench._questions) == 3


# --------------------------------------------------------------------------- #
# Inheritance
# --------------------------------------------------------------------------- #


def test_halueval_benchmark_is_truthfulqa_subclass():
    """Shares paraphrase / model / cache machinery."""
    assert issubclass(HaluEvalBenchmark, TruthfulQABenchmark)


def test_halueval_name_is_distinct():
    assert HaluEvalBenchmark.name == "halueval_qa"
    assert TruthfulQABenchmark.name == "truthfulqa_mc"
    assert HaluEvalBenchmark.name != TruthfulQABenchmark.name
