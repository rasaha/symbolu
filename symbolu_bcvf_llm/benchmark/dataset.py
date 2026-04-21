"""§6.2 dataset abstraction — ``Question`` + ``Benchmark`` protocol.

A benchmark is a sequence of multi-choice ``Question`` objects plus
a factory that produces §4.2 ``Source`` instances for each question
under the M=3 V1 configuration (base + two paraphrased).

Two implementations are shipped:

    MockBenchmark — synthetic, deterministic, torch-free. Used for
        offline unit testing and for the §6 MockSource-backed sweep
        (equivalent of §3 Phase 1.5 at the benchmark layer).

    TruthfulQABenchmark — real TruthfulQA-MC loader, delayed
        imports of ``datasets``, ``transformers``, and ``torch``.
        Skeleton — not executed against a real model in this
        environment per §0.6 rule 1.

``Question.choice_tokens`` carries each candidate answer as a list
of integer token IDs. ``MockBenchmark`` fabricates these directly;
``TruthfulQABenchmark`` would tokenize with a real tokenizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

import numpy as np

from symbolu_bcvf_llm.sources.base import Source
from symbolu_bcvf_llm.sources.mock import MockSource

if TYPE_CHECKING:  # pragma: no cover
    from transformers import PreTrainedModel, PreTrainedTokenizerBase


@dataclass
class Question:
    """A single multi-choice question.

    prompt_tokens      : integer IDs representing the question text.
    choices            : human-readable candidate answer strings
                         (used only for reporting; scoring uses
                         choice_tokens).
    choice_tokens      : tokenized candidate answers; one list per
                         choice.
    correct_index      : index into choices of the correct answer.
    metadata           : free-form dict for provenance (dataset,
                         row id, etc.).
    """

    prompt_tokens: List[int]
    choices: List[str]
    choice_tokens: List[List[int]]
    correct_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Benchmark(Protocol):
    """Read-only protocol for a benchmark."""

    name: str
    vocab_size: int
    L: int
    eos_token_id: Optional[int]

    @property
    def questions(self) -> Sequence[Question]: ...

    def make_sources(self, question: Question) -> List[Source]: ...


# --------------------------------------------------------------------------- #
# MockBenchmark — synthetic, deterministic, torch-free
# --------------------------------------------------------------------------- #

SourcePolicy = str  # "healthy" | "healthy_majority" | "trust_required"


def _peak_logits(
    V: int,
    top: int,
    L: int = 5,
    peak: float = 10.0,
    floor: float = -10.0,
) -> np.ndarray:
    z = np.full((L, V), floor, dtype=np.float32)
    z[:, top] = peak
    return z


def _accelerating_divergence_logits(
    V: int,
    base_top: int,
    drift_step: int,
    L: int = 5,
    peak: float = 10.0,
) -> np.ndarray:
    """Source produces peaked logits whose top index shifts quadratically
    along the lookahead axis, starting from ``base_top``. Used to
    synthesize an outlier that the BCVF 2nd-order operator detects."""
    z = np.full((L, V), -10.0, dtype=np.float32)
    for l in range(L):
        shift = min(V - 1, int(0.5 * (l * drift_step) ** 2))
        idx = (base_top + shift) % V
        z[l, idx] = peak
    return z


@dataclass
class _MockQuestionConfig:
    """Internal wiring for how `MockBenchmark.make_sources` fabricates
    the three sources for a given ``Question``. Attached as metadata
    so tests can inspect it."""

    policy: SourcePolicy
    # For "trust_required" policy: which source is the outlier and
    # how quickly it drifts quadratically per committed token.
    outlier_source: int = 0
    outlier_drift: int = 2
    # Whether the outlier's preferred "wrong" top token at commit
    # time matches the incorrect choice (so vanilla-decoder-on-
    # source-0 would get the wrong answer).
    outlier_token_from_choice: int = 1  # index into Question.choices


class MockBenchmark:
    """Deterministic, torch-free benchmark for offline testing.

    Generates N synthetic MC questions over a small vocabulary.
    Each question has one correct answer token and one distractor.
    Three source policies:

      - ``healthy``: all three sources strongly favour the correct
        answer → every decoder gets 100% accuracy.
      - ``healthy_majority``: sources 1 and 2 favour correct; source 0
        favours the distractor. Vanilla decoder (source 0 only) gets
        it wrong; conventional-blend gets it right by majority;
        BCVF-trust should match the blend or improve.
      - ``trust_required``: sources 1 and 2 favour correct; source 0
        produces accelerating divergence toward the distractor.
        Conventional-blend may be dragged by source 0 when its mass
        is high on the wrong choice; BCVF-trust should down-weight
        source 0 and recover correct.

    Vocabulary uses small integer IDs. No tokenizer required.
    """

    name: str = "mock"

    def __init__(
        self,
        num_questions: int = 24,
        V: int = 32,
        L: int = 5,
        policies: Optional[Sequence[SourcePolicy]] = None,
        eos_token_id: Optional[int] = None,
        seed: int = 42,
    ) -> None:
        if num_questions < 1:
            raise ValueError("MockBenchmark requires num_questions >= 1")
        if V < 4:
            raise ValueError("MockBenchmark requires V >= 4")
        if L < 3:
            raise ValueError("MockBenchmark requires L >= 3 (BCVF stencil)")
        self.vocab_size = V
        self.L = L
        self.eos_token_id = eos_token_id

        rng = np.random.default_rng(seed=seed)
        default_policies = ["healthy", "healthy_majority", "trust_required"]
        policies = list(policies) if policies else default_policies

        self._questions: List[Question] = []
        self._configs: List[_MockQuestionConfig] = []
        for q_idx in range(num_questions):
            # Two choices per question; correct = 0, distractor = 1.
            # Each choice has 3-token answer for §6.3 teacher-forcing
            # exercise (multiple lookahead/commit cycles per question).
            correct_token = 2 + (q_idx * 3) % (V - 4)
            distractor_token = 3 + (q_idx * 3) % (V - 4)
            # Make distinct if collision.
            if distractor_token == correct_token:
                distractor_token = (correct_token + 1) % V

            choice_correct_tokens = [correct_token, correct_token, correct_token]
            choice_distractor_tokens = [
                distractor_token, distractor_token, distractor_token
            ]

            policy = policies[q_idx % len(policies)]
            cfg = _MockQuestionConfig(policy=policy)

            q = Question(
                prompt_tokens=[0, 1],  # placeholder short prompt
                choices=[
                    f"choice_correct_{correct_token}",
                    f"choice_distractor_{distractor_token}",
                ],
                choice_tokens=[choice_correct_tokens, choice_distractor_tokens],
                correct_index=0,
                metadata={
                    "question_id": q_idx,
                    "policy": policy,
                    "correct_token": int(correct_token),
                    "distractor_token": int(distractor_token),
                    "_mock_cfg": cfg,
                },
            )
            self._questions.append(q)
            self._configs.append(cfg)

    @property
    def questions(self) -> Sequence[Question]:
        return tuple(self._questions)

    def make_sources(self, question: Question) -> List[Source]:
        correct_token = int(question.metadata["correct_token"])
        distractor_token = int(question.metadata["distractor_token"])
        policy: SourcePolicy = str(question.metadata["policy"])
        V = self.vocab_size
        L = self.L
        initial = list(question.prompt_tokens)

        if policy == "healthy":
            def fn(prefix):
                return _peak_logits(V, correct_token, L=L)

            return [
                MockSource(fn, L=L, V=V, eos_token_id=self.eos_token_id,
                           initial_prefix=initial)
                for _ in range(3)
            ]

        if policy == "healthy_majority":
            # Sources 1, 2 favour correct; source 0 favours distractor.
            def fn_distractor(prefix):
                return _peak_logits(V, distractor_token, L=L)

            def fn_correct(prefix):
                return _peak_logits(V, correct_token, L=L)

            return [
                MockSource(fn_distractor, L=L, V=V, eos_token_id=self.eos_token_id,
                           initial_prefix=initial),
                MockSource(fn_correct, L=L, V=V, eos_token_id=self.eos_token_id,
                           initial_prefix=initial),
                MockSource(fn_correct, L=L, V=V, eos_token_id=self.eos_token_id,
                           initial_prefix=initial),
            ]

        if policy == "trust_required":
            # Source 0: accelerating-divergence toward distractor.
            # Sources 1, 2: clean peak on correct.
            def fn_outlier(prefix):
                return _accelerating_divergence_logits(
                    V=V, base_top=distractor_token, drift_step=2, L=L
                )

            def fn_correct(prefix):
                return _peak_logits(V, correct_token, L=L)

            return [
                MockSource(fn_outlier, L=L, V=V, eos_token_id=self.eos_token_id,
                           initial_prefix=initial),
                MockSource(fn_correct, L=L, V=V, eos_token_id=self.eos_token_id,
                           initial_prefix=initial),
                MockSource(fn_correct, L=L, V=V, eos_token_id=self.eos_token_id,
                           initial_prefix=initial),
            ]

        raise ValueError(f"unknown policy {policy!r}")


# --------------------------------------------------------------------------- #
# TruthfulQABenchmark — real loader, scaffold with delayed imports
# --------------------------------------------------------------------------- #


class TruthfulQABenchmark:
    """Real TruthfulQA-MC loader.

    **Status.** Scaffold only. Requires `datasets`, `transformers`,
    and `torch` (delayed imports). Real-model execution is
    hard-gated on §0.6 rule 1; verification against an actual
    model happens in a GPU environment.
    """

    name: str = "truthfulqa_mc"

    def __init__(
        self,
        model_name: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
        split: str = "validation",
        max_questions: Optional[int] = None,
        L: int = 5,
    ) -> None:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            import datasets  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "TruthfulQABenchmark requires `torch`, `transformers`, "
                "and `datasets`. For offline testing use MockBenchmark. "
                "See docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md §6.2."
            ) from exc

        from transformers import AutoModelForCausalLM, AutoTokenizer
        from datasets import load_dataset

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype="auto", device_map="auto"
        )
        self.vocab_size = int(self._tokenizer.vocab_size)
        self.L = L
        self.eos_token_id = int(self._tokenizer.eos_token_id)

        ds = load_dataset("truthful_qa", "multiple_choice", split=split)
        if max_questions is not None:
            ds = ds.select(range(min(max_questions, len(ds))))

        self._questions = [
            self._convert_row(row, idx) for idx, row in enumerate(ds)
        ]

    def _convert_row(self, row: Dict[str, Any], idx: int) -> Question:
        """Convert a HF TruthfulQA-MC row into a Question.

        Row schema (mc1_targets variant):
            question: str
            mc1_targets: {choices: List[str], labels: List[int]}
        """
        q_text = row["question"]
        choices = list(row["mc1_targets"]["choices"])
        labels = list(row["mc1_targets"]["labels"])
        correct_index = int(labels.index(1))

        prompt = f"Q: {q_text}\nA:"
        prompt_tokens = self._tokenizer.encode(prompt, add_special_tokens=True)

        choice_tokens: List[List[int]] = []
        for choice in choices:
            # Space prefix so the tokenization is natural after "A:".
            tokens = self._tokenizer.encode(
                " " + choice, add_special_tokens=False
            )
            choice_tokens.append(list(tokens))

        return Question(
            prompt_tokens=prompt_tokens,
            choices=choices,
            choice_tokens=choice_tokens,
            correct_index=correct_index,
            metadata={"truthfulqa_row_id": idx},
        )

    @property
    def questions(self) -> Sequence[Question]:
        return tuple(self._questions)

    def make_sources(self, question: Question) -> List[Source]:
        from symbolu_bcvf_llm.sources.huggingface import HuggingFaceSource
        from symbolu_bcvf_llm.sources.paraphrase import make_paraphrased_prompt

        base_prompt = self._tokenizer.decode(
            question.prompt_tokens, skip_special_tokens=True
        )
        para_a = make_paraphrased_prompt(
            self._model, self._tokenizer, base_prompt, rewrite_seed=1
        )
        para_b = make_paraphrased_prompt(
            self._model, self._tokenizer, base_prompt, rewrite_seed=2
        )
        return [
            HuggingFaceSource(
                self._model, self._tokenizer, base_prompt, L=self.L
            ),
            HuggingFaceSource(
                self._model, self._tokenizer, para_a, L=self.L
            ),
            HuggingFaceSource(
                self._model, self._tokenizer, para_b, L=self.L
            ),
        ]
