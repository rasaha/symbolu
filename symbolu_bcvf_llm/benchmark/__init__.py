"""§6 Phase 4 — benchmark, metrics, §1.10 threshold evaluation.

Public API:
  dataset   : Question + Benchmark protocol + MockBenchmark +
              TruthfulQABenchmark scaffold.
  scoring   : three teacher-forced MC scoring functions, one per
              §1.10 decoder.
  harness   : run_benchmark(benchmark, decoders) driver.
  metrics   : accuracy, McNemar paired test, latency stats,
              §1.10 classify_phase_six_result.
"""

from __future__ import annotations

from .dataset import (
    Benchmark,
    HaluEvalBenchmark,
    MockBenchmark,
    Question,
    TruthfulQABenchmark,
)
from .harness import (
    BenchmarkRunBundle,
    BenchmarkRunResult,
    run_benchmark,
)
from .metrics import (
    LatencyStats,
    McNemarResult,
    PhaseSixVerdict,
    accuracy,
    classify_phase_six_result,
    latency_stats,
    mcnemar_paired,
)
from .scoring import (
    score_choice_blend,
    score_choice_trust,
    score_choice_vanilla,
)

__all__ = [
    "Benchmark",
    "BenchmarkRunBundle",
    "BenchmarkRunResult",
    "LatencyStats",
    "McNemarResult",
    "HaluEvalBenchmark",
    "MockBenchmark",
    "PhaseSixVerdict",
    "Question",
    "TruthfulQABenchmark",
    "accuracy",
    "classify_phase_six_result",
    "latency_stats",
    "mcnemar_paired",
    "run_benchmark",
    "score_choice_blend",
    "score_choice_trust",
    "score_choice_vanilla",
]
