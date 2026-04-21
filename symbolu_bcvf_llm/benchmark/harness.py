"""§6.4 benchmark harness — run the three §1.10 decoders and return
per-question correctness + latency arrays.

Given a `Benchmark`, the harness iterates over each `Question`,
scores every choice under each decoder (§6.3 teacher-forced MC),
picks `argmax` over per-choice log-prob sums, and records whether
the prediction matches `correct_index`.

Three decoders per §1.10:
  vanilla              — `score_choice_vanilla`  (A0 baseline)
  conventional_blend   — `score_choice_blend`    (baseline to beat)
  bcvf_trust           — `score_choice_trust`    (§5 V1 consumer)

Per-question latency is wall-clock time of the scoring loop for
that (decoder, question) pair. This is the latency measure §1.10
cares about (per-question latency ratio between decoders).

Fresh `Source` instances are produced for *every* (question,
choice, decoder) triple via the `Benchmark.make_sources` factory.
This is deliberately wasteful in the real-model case (recomputes
prompt KV-cache per choice) but trivially cheap in `MockSource`
and keeps the contract clean. §9 V2 can optimize via KV
snapshots on the HF path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig
from symbolu_bcvf_llm.trust.shaper import TrustShaperConfig

from .dataset import Benchmark, Question
from .scoring import (
    score_choice_blend,
    score_choice_trust,
    score_choice_vanilla,
)


DecoderName = str   # "vanilla" | "conventional_blend" | "bcvf_trust"


@dataclass
class BenchmarkRunResult:
    """Per-decoder outcome over a full benchmark run."""

    decoder_name: DecoderName
    num_questions: int
    per_question_correct: np.ndarray              # (N,) bool
    per_question_predicted: np.ndarray            # (N,) int
    per_question_latency_s: np.ndarray            # (N,) float
    per_question_scores: List[List[float]]        # (N, K) log-prob per choice
    accuracy: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkRunBundle:
    """Container for the three-decoder comparison on one seed."""

    benchmark_name: str
    seed: int
    results: Dict[DecoderName, BenchmarkRunResult]


def _score_question(
    benchmark: Benchmark,
    question: Question,
    decoder_name: DecoderName,
    bcvf_config: BCVFLLMConfig,
    trust_config: TrustShaperConfig,
) -> tuple[int, List[float], float]:
    """Score every choice under `decoder_name`, return
    (predicted_index, per_choice_scores, elapsed_s)."""
    scores: List[float] = []
    start = time.perf_counter()
    for choice_tokens in question.choice_tokens:
        sources = benchmark.make_sources(question)
        if decoder_name == "vanilla":
            s = score_choice_vanilla(sources, choice_tokens)
        elif decoder_name == "conventional_blend":
            s = score_choice_blend(sources, choice_tokens)
        elif decoder_name == "bcvf_trust":
            s = score_choice_trust(
                sources, choice_tokens,
                bcvf_config=bcvf_config,
                trust_config=trust_config,
            )
        else:
            raise ValueError(f"unknown decoder {decoder_name!r}")
        scores.append(float(s))
    elapsed = time.perf_counter() - start
    predicted = int(np.argmax(scores))
    return predicted, scores, elapsed


def run_benchmark(
    benchmark: Benchmark,
    decoders: Sequence[DecoderName] = (
        "vanilla", "conventional_blend", "bcvf_trust"
    ),
    bcvf_config: Optional[BCVFLLMConfig] = None,
    trust_config: Optional[TrustShaperConfig] = None,
    max_questions: Optional[int] = None,
    seed: int = 0,
    progress_callback: Optional[Callable[[int, int, DecoderName], None]] = None,
) -> BenchmarkRunBundle:
    """Run each decoder against the benchmark.

    Returns a bundle with per-decoder `BenchmarkRunResult`; the
    caller feeds these into §6.5 threshold evaluation.
    """
    cfg = bcvf_config or BCVFLLMConfig()
    t_cfg = trust_config or TrustShaperConfig()
    questions = list(benchmark.questions)
    if max_questions is not None:
        questions = questions[:max_questions]
    N = len(questions)

    results: Dict[DecoderName, BenchmarkRunResult] = {}
    for decoder_name in decoders:
        correct = np.zeros(N, dtype=bool)
        predicted = np.zeros(N, dtype=np.int64)
        latency = np.zeros(N, dtype=np.float64)
        scores_list: List[List[float]] = []
        for i, question in enumerate(questions):
            pred, scores, elapsed = _score_question(
                benchmark, question, decoder_name, cfg, t_cfg
            )
            predicted[i] = pred
            correct[i] = (pred == question.correct_index)
            latency[i] = elapsed
            scores_list.append(scores)
            if progress_callback is not None:
                progress_callback(i + 1, N, decoder_name)
        results[decoder_name] = BenchmarkRunResult(
            decoder_name=decoder_name,
            num_questions=N,
            per_question_correct=correct,
            per_question_predicted=predicted,
            per_question_latency_s=latency,
            per_question_scores=scores_list,
            accuracy=float(correct.mean()) if N > 0 else 0.0,
            metadata={"seed": seed},
        )

    return BenchmarkRunBundle(
        benchmark_name=benchmark.name,
        seed=seed,
        results=results,
    )
