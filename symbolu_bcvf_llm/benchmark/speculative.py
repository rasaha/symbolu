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

    Each question = a prompt.
    Each candidate = a K-token continuation sampled from the draft
    model at temperature T > 0.
    correct_index = the candidate with the highest expected accepted-
    token count under standard rejection sampling.

    Expected accepted-token count is computed as
    ``E[accepted] = Σ_i (Π_{j<i} α_j) × α_i``
    where ``α_i = min(1, p_target(token_i | prefix) /
    p_draft(token_i | prefix))``. This is the classical
    Leviathan-2023 / Chen-2023 acceptance metric.

    Construction is heavy:
    1. Load target_model + draft_model (both via HuggingFace
       from_pretrained). Tokenizer compatibility check: both must
       share vocab_size and agree on a fixed probe string.
    2. For each prompt: call draft_model.generate with
       num_return_sequences=num_candidates, do_sample=True at
       temperature T, one batched call per prompt.
    3. For each candidate: single teacher-forced forward pass
       through target and draft to obtain per-position log-probs
       on the candidate tokens.
    4. Compute per-candidate expected acceptance → correct_index.

    Runtime-gated on torch + transformers + datasets.
    """

    name: str = "spec_dec"

    def __init__(
        self,
        target_model_name: str = "Qwen/Qwen2.5-7B-Instruct",
        draft_model_name: str = "Qwen/Qwen2.5-3B-Instruct",
        source_dataset: str = "pminervini/HaluEval",
        source_subset: str = "qa",
        split: str = "data",
        max_questions: Optional[int] = 100,
        num_candidates: int = 4,
        candidate_length: int = 16,
        draft_temperature: float = 0.8,
        draft_seed: int = 1,
        L: int = 5,
        compile_model: bool = False,
    ) -> None:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            import datasets  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "SpeculativeDecodingBenchmark requires `torch`, "
                "`transformers`, and `datasets`. For offline harness "
                "validation use SpeculativeDecodingMockBenchmark."
            ) from exc

        from transformers import AutoModelForCausalLM, AutoTokenizer
        from datasets import load_dataset
        import torch

        try:
            torch.set_float32_matmul_precision("high")
        except Exception:  # pragma: no cover
            pass

        self.L = L
        self.num_candidates = int(num_candidates)
        self.candidate_length = int(candidate_length)
        self.draft_temperature = float(draft_temperature)
        self._draft_seed = int(draft_seed)
        self._target_model_name = target_model_name
        self._draft_model_name = draft_model_name
        self._source_dataset = source_dataset
        self._source_subset = source_subset
        self._split = split

        # Load the pair.
        self._target_tokenizer = AutoTokenizer.from_pretrained(target_model_name)
        self._target_model = AutoModelForCausalLM.from_pretrained(
            target_model_name, torch_dtype="auto", device_map="auto",
        )
        self._target_model.eval()

        if draft_model_name == target_model_name:
            self._draft_tokenizer = self._target_tokenizer
            self._draft_model = self._target_model
        else:
            self._draft_tokenizer = AutoTokenizer.from_pretrained(draft_model_name)
            self._draft_model = AutoModelForCausalLM.from_pretrained(
                draft_model_name, torch_dtype="auto", device_map="auto",
            )
            self._draft_model.eval()

        # Tokenizer compatibility sanity check — rejection sampling
        # assumes the two models share vocabulary. Vocab-size mismatch
        # is a hard fail; BOS/EOS mismatch is recorded but not fatal.
        t_vocab = int(self._target_tokenizer.vocab_size)
        d_vocab = int(self._draft_tokenizer.vocab_size)
        if t_vocab != d_vocab:
            raise ValueError(
                f"Tokenizer vocab size mismatch: target={t_vocab} "
                f"draft={d_vocab}. Speculative-decoding rejection "
                f"sampling requires matching vocabularies. Pick a "
                f"same-family pair (e.g., Qwen-7B + Qwen-3B)."
            )
        self.vocab_size = t_vocab
        self.eos_token_id = getattr(self._target_tokenizer, "eos_token_id", None)

        # torch.compile — default OFF. Benchmark runs are latency-bound
        # on generate(), not on the teacher-forced forward, so compile
        # speedup is modest and compile-time risk (DynamicCache bugs,
        # etc.) outweighs.
        self._compile_status: str = "disabled"
        if compile_model:
            try:
                self._target_model = torch.compile(
                    self._target_model, dynamic=True,
                )
                self._draft_model = torch.compile(
                    self._draft_model, dynamic=True,
                )
                self._compile_status = "compiled (dynamic=True)"
            except Exception as exc:  # pragma: no cover
                self._compile_status = f"skipped: {type(exc).__name__}: {exc}"

        # Load prompt source.
        ds = load_dataset(source_dataset, source_subset, split=split)
        if max_questions is not None:
            ds = ds.select(range(min(max_questions, len(ds))))

        # Build questions: for each prompt, generate K candidates and
        # score them.
        self._questions: List[Question] = []
        for idx, row in enumerate(ds):
            q = self._build_question(row, idx)
            self._questions.append(q)

    @property
    def questions(self) -> Sequence[Question]:
        return tuple(self._questions)

    @property
    def compile_status(self) -> str:
        return self._compile_status

    # ------------------------------------------------------------------ #
    # Candidate generation + acceptance-label computation
    # ------------------------------------------------------------------ #

    def _extract_prompt_text(self, row: dict) -> str:
        """Pull the prompt text from a dataset row. Schema-aware:
        HaluEval-QA rows have `question`; TruthfulQA rows have
        `question`; generic fallback to a `prompt` field."""
        if "question" in row:
            return f"Q: {row['question']}\nA:"
        if "prompt" in row:
            return row["prompt"]
        raise KeyError(
            f"Row has no recognized prompt field. Keys: {list(row.keys())}"
        )

    def _generate_candidates(
        self, prompt_text: str,
    ) -> "torch.Tensor":  # (num_candidates, candidate_length)
        """Batched sample from the draft model. Returns candidate
        token IDs only (prompt prefix stripped)."""
        import torch

        torch.manual_seed(self._draft_seed)

        input_ids = self._draft_tokenizer.encode(
            prompt_text, add_special_tokens=True, return_tensors="pt",
        ).to(next(self._draft_model.parameters()).device)
        prompt_len = int(input_ids.shape[1])

        with torch.inference_mode():
            out = self._draft_model.generate(
                input_ids,
                do_sample=True,
                temperature=self.draft_temperature,
                num_return_sequences=self.num_candidates,
                max_new_tokens=self.candidate_length,
                pad_token_id=(
                    self._draft_tokenizer.pad_token_id
                    or self._draft_tokenizer.eos_token_id
                ),
            )
        # out shape: (num_candidates, prompt_len + gen_len)
        candidates = out[:, prompt_len:]
        return candidates  # (K, L_gen)

    def _compute_expected_accepted(
        self, prompt_text: str, candidate_tokens: "np.ndarray",
    ) -> float:
        """Teacher-force target and draft on prompt+candidate, compute
        per-position α_i = min(1, p_target / p_draft), return
        E[accepted] = Σ (Π_{j<i} α_j) α_i."""
        import torch

        input_ids = self._target_tokenizer.encode(
            prompt_text, add_special_tokens=True,
        )
        full = list(input_ids) + [int(t) for t in candidate_tokens]
        full_tensor = torch.tensor(
            [full], device=next(self._target_model.parameters()).device,
        )
        prompt_len = len(input_ids)

        with torch.inference_mode():
            t_out = self._target_model(full_tensor)
            d_out = self._draft_model(full_tensor)

        # Next-token distributions at each position that PREDICTS a
        # candidate token. Position (prompt_len - 1) predicts the
        # first candidate token; so slice logits[prompt_len - 1 :
        # prompt_len - 1 + K].
        K = len(candidate_tokens)
        t_logits = (
            t_out.logits[0, prompt_len - 1 : prompt_len - 1 + K, :]
            .float().cpu().numpy()
        )
        d_logits = (
            d_out.logits[0, prompt_len - 1 : prompt_len - 1 + K, :]
            .float().cpu().numpy()
        )
        # Softmax to probabilities.
        t_probs = _stable_softmax(t_logits, axis=-1)
        d_probs = _stable_softmax(d_logits, axis=-1)

        # Per-position alpha = min(1, p_target / p_draft) on the
        # teacher-forced candidate tokens.
        alphas = np.empty(K, dtype=np.float64)
        for i, tok in enumerate(candidate_tokens):
            pd = float(d_probs[i, int(tok)])
            pt = float(t_probs[i, int(tok)])
            if pd <= 0.0:
                alphas[i] = 0.0
            else:
                alphas[i] = min(1.0, pt / pd)

        # E[accepted] = Σ_i (Π_{j<i} α_j) × α_i.
        cum_reach = 1.0
        expected = 0.0
        for a in alphas:
            expected += cum_reach * a
            cum_reach *= a
        return float(expected)

    def _build_question(self, row: dict, idx: int) -> Question:
        prompt_text = self._extract_prompt_text(row)
        prompt_tokens = self._target_tokenizer.encode(
            prompt_text, add_special_tokens=True,
        )

        # Generate K candidates on the draft.
        cands_tensor = self._generate_candidates(prompt_text)
        candidate_np = cands_tensor.cpu().numpy()

        # Compute acceptance for each.
        expected_per_cand = []
        choice_tokens: List[List[int]] = []
        for c in range(self.num_candidates):
            cand_tokens = candidate_np[c]
            # Trim trailing pad/eos tokens if any.
            trimmed = [int(t) for t in cand_tokens]
            if self.eos_token_id is not None:
                if self.eos_token_id in trimmed:
                    trimmed = trimmed[: trimmed.index(self.eos_token_id)]
            if not trimmed:
                # Degenerate candidate — give it zero acceptance.
                expected_per_cand.append(0.0)
                choice_tokens.append([int(self.eos_token_id or 0)])
                continue
            e = self._compute_expected_accepted(prompt_text, np.array(trimmed))
            expected_per_cand.append(e)
            choice_tokens.append(trimmed)

        correct_index = int(np.argmax(expected_per_cand))
        return Question(
            prompt_tokens=prompt_tokens,
            choices=[
                f"candidate_{i}(E={e:.2f})"
                for i, e in enumerate(expected_per_cand)
            ],
            choice_tokens=choice_tokens,
            correct_index=correct_index,
            metadata={
                "question_id": idx,
                "prompt_text": prompt_text,
                "expected_accepted_per_candidate": [
                    float(e) for e in expected_per_cand
                ],
                "candidate_length": self.candidate_length,
            },
        )

    # ------------------------------------------------------------------ #
    # Sources
    # ------------------------------------------------------------------ #

    def make_sources(self, question: Question) -> List[Source]:
        from symbolu_bcvf_llm.sources.huggingface import HuggingFaceSource

        prompt_text = question.metadata["prompt_text"]
        target_source = HuggingFaceSource(
            self._target_model, self._target_tokenizer, prompt_text,
            L=self.L,
        )
        draft_source = HuggingFaceSource(
            self._draft_model, self._draft_tokenizer, prompt_text,
            L=self.L,
        )
        return [target_source, draft_source]


def _stable_softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """NumPy-only stable softmax; avoids importing torch just for this."""
    shifted = x - np.max(x, axis=axis, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=axis, keepdims=True)
