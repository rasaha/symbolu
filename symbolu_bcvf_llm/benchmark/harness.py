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
    _has_batched_scoring,
    score_choice_blend,
    score_choice_blend_batched,
    score_choice_trust,
    score_choice_vanilla,
    score_choice_vanilla_batched,
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
    fast_scoring: bool = True,
) -> tuple[int, List[float], float]:
    """Score every choice under `decoder_name`, return
    (predicted_index, per_choice_scores, elapsed_s).

    §6.2 Phase 2: when `fast_scoring=True` and all sources implement
    the `score_teacher_forced` protocol, vanilla + blend use the
    single-forward-pass batched scoring path (~15× speedup). The
    trust path stays on the speculation-based `lookahead/commit`
    loop to preserve §2.3.2 forward-lookahead semantics. Sources
    without batched scoring (e.g., test stubs) auto-fall-back to
    the slow path.

    Per-question source reuse: when batched scoring is active we
    construct sources ONCE per question (not per choice), since
    `score_teacher_forced` is stateless and the sources don't
    mutate across choices. This is an additional ~5× speedup by
    eliminating redundant source-construction.
    """
    scores: List[float] = []
    start = time.perf_counter()

    # Try the batched path when applicable. `make_sources` is called
    # once per question (not per choice) — sources are reused since
    # score_teacher_forced doesn't mutate state.
    can_batch = False
    if fast_scoring and decoder_name in ("vanilla", "conventional_blend"):
        probe_sources = benchmark.make_sources(question)
        needed = (
            (probe_sources[0],)
            if decoder_name == "vanilla" else probe_sources
        )
        can_batch = all(_has_batched_scoring(s) for s in needed)
        if can_batch:
            for choice_tokens in question.choice_tokens:
                if decoder_name == "vanilla":
                    s = score_choice_vanilla_batched(
                        probe_sources, choice_tokens
                    )
                else:  # conventional_blend
                    s = score_choice_blend_batched(
                        probe_sources, choice_tokens
                    )
                scores.append(float(s))

    if not can_batch:
        # Slow path: trust always, vanilla/blend when sources lack the
        # batched protocol. Per-choice source construction preserves
        # the original state semantics (commit() mutates).
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
    fast_scoring: bool = True,
    per_decoder_complete_callback: Optional[
        Callable[[DecoderName, "BenchmarkRunResult"], None]
    ] = None,
) -> BenchmarkRunBundle:
    """Run each decoder against the benchmark.

    Returns a bundle with per-decoder `BenchmarkRunResult`; the
    caller feeds these into §6.5 threshold evaluation.

    Args:
        fast_scoring: §6.2 Phase 2 optimization. When True (default)
            and sources implement `score_teacher_forced`, vanilla and
            blend scoring use the single-forward-pass batched path
            (~15× speedup). Trust stays on the speculation path
            regardless. Set False to force slow path everywhere
            (useful for debugging or verifying fast/slow parity).
        per_decoder_complete_callback: Called with `(decoder_name,
            BenchmarkRunResult)` immediately after each decoder
            finishes. Used by the CLI to incrementally write per-
            decoder CSV so a crash mid-run doesn't lose earlier
            decoders' results.
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
                benchmark, question, decoder_name, cfg, t_cfg,
                fast_scoring=fast_scoring,
            )
            predicted[i] = pred
            correct[i] = (pred == question.correct_index)
            latency[i] = elapsed
            scores_list.append(scores)
            if progress_callback is not None:
                progress_callback(i + 1, N, decoder_name)
        result = BenchmarkRunResult(
            decoder_name=decoder_name,
            num_questions=N,
            per_question_correct=correct,
            per_question_predicted=predicted,
            per_question_latency_s=latency,
            per_question_scores=scores_list,
            accuracy=float(correct.mean()) if N > 0 else 0.0,
            metadata={"seed": seed, "fast_scoring": bool(fast_scoring)},
        )
        results[decoder_name] = result
        # Fire the per-decoder callback so the CLI can flush this
        # decoder's CSV / update the manifest before the next
        # decoder starts. Mid-run crashes after this point preserve
        # at least what's been flushed.
        if per_decoder_complete_callback is not None:
            per_decoder_complete_callback(decoder_name, result)

    return BenchmarkRunBundle(
        benchmark_name=benchmark.name,
        seed=seed,
        results=results,
    )
