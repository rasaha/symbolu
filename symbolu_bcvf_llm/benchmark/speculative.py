"""§12 Speculative-decoding benchmark adapters.

Two classes:

  SpeculativeDecodingMockBenchmark
    Synthetic, deterministic, torch-free. Lets the §11 probe harness
    exercise a 2-source (target, draft) configuration without needing
    real models loaded. Validates that observables transfer from the
    hallucination problem to the spec-dec problem at the plumbing
    level.

  SpeculativeDecodingBenchmark
    Real target + draft model pair. DEFERRED — skeleton only in this
    commit; full implementation (candidate generation + acceptance
    labels via rejection sampling) is next-session work. The class
    raises NotImplementedError until the implementation lands.

Shape:
- Each question is a prompt.
- Choices are candidate draft continuations (K tokens each).
- correct_index = the candidate with highest expected acceptance
  rate (for mock: synthesized ground-truth; for real: computed by
  running target on each candidate).
- make_sources returns a length-2 list: [target_source, draft_source].
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np

from .dataset import Question
from symbolu_bcvf_llm.sources.base import Source
from symbolu_bcvf_llm.sources.mock import MockSource


def _peak_logits(V: int, top: int, L: int = 5, peak: float = 10.0) -> np.ndarray:
    z = np.full((L, V), -peak, dtype=np.float32)
    z[:, top] = peak
    return z


def _noisy_peak_logits(
    V: int, top: int, L: int = 5, peak: float = 5.0, noise_std: float = 0.5,
    seed: int = 0,
) -> np.ndarray:
    """Soft peak + Gaussian noise: the draft model's analog of a target
    distribution. Lower peak height (less confident) + random jitter
    (imperfect imitation of target)."""
    rng = np.random.default_rng(seed)
    z = rng.normal(0.0, noise_std, size=(L, V)).astype(np.float32)
    z[:, top] += peak
    return z


class SpeculativeDecodingMockBenchmark:
    """Synthetic 2-source (target, draft) benchmark.

    Each question has `num_candidates` candidate draft continuations.
    Exactly one candidate is "correct" (i.e., its first token matches
    the target's peaked distribution). The others are distractors
    that the target would reject under standard rejection sampling.

    The mock sources are deterministic peaked distributions:
      - target peaks sharply on `correct_token` (peak=10, noise=0).
      - draft peaks softly on `correct_token` (peak=5, noise=0.5).

    Both sources are CANDIDATE-AGNOSTIC at lookahead time — the
    observable's per-candidate score comes from inspecting the
    candidate tokens against the sources' (identical-across-candidates)
    distributions. Matches §11 probe-harness semantics.

    Pure NumPy, no torch. Serves two purposes:
      1. Validates the existing observable family on M=2.
      2. Gives us end-to-end plumbing + an offline CI fixture for
         the speculative-decoding pivot.
    """

    name: str = "spec_dec_mock"

    def __init__(
        self,
        num_questions: int = 24,
        num_candidates: int = 3,
        K: int = 5,
        V: int = 32,
        seed: int = 0,
    ) -> None:
        if num_questions < 1:
            raise ValueError("num_questions must be >= 1")
        if num_candidates < 2:
            raise ValueError("num_candidates must be >= 2 (need a contrast)")
        if K < 1:
            raise ValueError("K (draft length) must be >= 1")
        if V < 4:
            raise ValueError("V (vocab size) must be >= 4")

        self.num_questions = num_questions
        self.num_candidates = num_candidates
        self.K = K
        self.vocab_size = V
        self.L = K   # lookahead window matches draft length
        self.eos_token_id: Optional[int] = None
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._questions: List[Question] = []
        self._targets: List[int] = []   # correct_token per question

        for q_idx in range(num_questions):
            correct_token = 2 + (q_idx * 3) % (V - 4)
            self._targets.append(int(correct_token))

            choice_tokens: List[List[int]] = []
            # "Correct" candidate: K tokens, first token = correct_token
            correct_choice = [correct_token] + list(
                self._rng.integers(2, V, size=K - 1)
            )
            choice_tokens.append([int(t) for t in correct_choice])

            # Distractor candidates: first token ≠ correct_token
            for _ in range(num_candidates - 1):
                while True:
                    first = int(self._rng.integers(2, V))
                    if first != correct_token:
                        break
                tail = list(self._rng.integers(2, V, size=K - 1))
                choice_tokens.append([first] + [int(t) for t in tail])

            self._questions.append(Question(
                prompt_tokens=[0, 1, q_idx],
                choices=[f"candidate_{i}" for i in range(num_candidates)],
                choice_tokens=choice_tokens,
                correct_index=0,
                metadata={
                    "question_id": q_idx,
                    "correct_token": int(correct_token),
                    "K": K,
                },
            ))

    @property
    def questions(self) -> Sequence[Question]:
        return tuple(self._questions)

    def make_sources(self, question: Question) -> List[Source]:
        correct_token = int(question.metadata["correct_token"])
        V = self.vocab_size
        L = self.L
        q_idx = int(question.metadata["question_id"])

        target = MockSource(
            lambda p: _peak_logits(V, correct_token, L=L, peak=10.0),
            L=L, V=V,
        )
        draft = MockSource(
            lambda p, q_idx=q_idx: _noisy_peak_logits(
                V, correct_token, L=L, peak=5.0, noise_std=0.5,
                seed=self._seed * 1_000 + q_idx,
            ),
            L=L, V=V,
        )
        return [target, draft]


class SpeculativeDecodingBenchmark:
    """Real target+draft model speculative-decoding benchmark.

    DEFERRED — skeleton only. Full implementation pending next
    session. When filled in, this class will:

    1. Load target_model + draft_model as independent HuggingFaceSource
       wrappers.
    2. For each prompt in the underlying dataset, sample K
       candidate draft continuations from draft_model at T>0.
    3. For each candidate, run target_model in teacher-forced mode
       to get per-position target distributions.
    4. Compute per-position acceptance labels under the standard
       rejection-sampling rule (Leviathan et al. 2023, Chen et al.
       2023): P(accept token t) = min(1, p_target(t) / p_draft(t)).
    5. Aggregate per-candidate acceptance rate; label
       correct_index = argmax(acceptance_rate).

    Use the mock class (`SpeculativeDecodingMockBenchmark`) for
    offline probe-harness validation until the real pipeline lands.
    """

    name: str = "spec_dec"

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "SpeculativeDecodingBenchmark real-model pipeline is not yet "
            "implemented. Use SpeculativeDecodingMockBenchmark for "
            "offline harness validation. Real implementation is next-"
            "session work per §12."
        )
