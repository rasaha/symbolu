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

import json
from dataclasses import dataclass, field
from pathlib import Path
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
                # Unique per-question prompt so downstream observables /
                # probes can disambiguate questions by their prompt.
                prompt_tokens=[0, 1, q_idx],
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
        use_paraphrase: bool = True,
        paraphrase_max_new_tokens: int = 128,
        compile_model: bool = True,
        compile_dynamic: bool = True,
        paraphrase_cache_file: Optional["Path"] = None,
        evaluation_seed: int = 1,
        rewrite_seed_pair: Optional[Tuple[int, int]] = None,
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
        import torch

        # Enable TF32 matmul on Ampere+ (A100/H100 tensor cores). PyTorch
        # 2.x defaults to 'highest' (strict fp32); 'high' allows TF32 which
        # has fp32 range + fp19 precision — plenty for LM inference, gives
        # ~1.5-2× additional matmul speedup on Ampere. This is the
        # warning PyTorch emits at compile time if you don't set it.
        # Safe global setting; no effect on non-Ampere hardware.
        try:
            torch.set_float32_matmul_precision("high")
        except Exception:  # pragma: no cover
            pass

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype="auto", device_map="auto"
        )
        self._model.eval()

        # torch.compile gives ~2-3× speedup on Ampere+ for the forward
        # pass. dynamic=True avoids recompilation on every seq-length
        # change (teacher-forcing produces variable shapes). Wrapped in
        # try/except with graceful fallback so a compile failure doesn't
        # abort the benchmark — the uncompiled model still works.
        self._compile_status: str = "disabled"
        if compile_model:
            try:
                self._model = torch.compile(
                    self._model, dynamic=bool(compile_dynamic)
                )
                self._compile_status = (
                    f"compiled (dynamic={bool(compile_dynamic)})"
                )
            except Exception as exc:  # pragma: no cover — compile-env-specific
                self._compile_status = f"skipped: {type(exc).__name__}: {exc}"

        self.vocab_size = int(self._tokenizer.vocab_size)
        self.L = L
        self.eos_token_id = int(self._tokenizer.eos_token_id)
        self._use_paraphrase = bool(use_paraphrase)
        self._paraphrase_max_new_tokens = int(paraphrase_max_new_tokens)
        self._model_name = model_name
        self._split = split

        # §1.10 replication requires seed 2 to use *different* paraphrases
        # than seed 1 so the verdict is tested against a different source
        # triple. Map evaluation_seed N → rewrite_seed_pair (2N-1, 2N):
        #   seed 1 → (1, 2)  ← what the hardcoded pre-fix code used
        #   seed 2 → (3, 4)
        #   seed N → (2N-1, 2N)
        # For backward compat, evaluation_seed 0 maps to (1, 2) same as 1.
        # An explicit rewrite_seed_pair override wins over the derivation.
        if rewrite_seed_pair is not None:
            pair = tuple(int(s) for s in rewrite_seed_pair)
            if len(pair) != 2 or pair[0] == pair[1]:
                raise ValueError(
                    f"rewrite_seed_pair must be two distinct ints, got {pair}"
                )
            self._rewrite_seed_pair: Tuple[int, int] = pair  # type: ignore
        else:
            base = max(int(evaluation_seed), 1)
            self._rewrite_seed_pair = (2 * base - 1, 2 * base)
        self._evaluation_seed = int(evaluation_seed)

        # Paraphrase cache: (question_row_id, rewrite_seed) -> paraphrased prompt.
        # Paraphrases are deterministic given (model, prompt, seed) at
        # temperature 0, so computing them once per question and reusing
        # across the ~15 make_sources invocations per question cuts the
        # per-seed paraphrase cost by ~15×.
        #
        # If `paraphrase_cache_file` is given, the cache is also
        # persisted to disk so subsequent runs (e.g., seed-2) start with
        # a fully-populated cache and skip the ~20 min paraphrase cost.
        # Cache file is keyed by (model_name, split) — mismatches are
        # rejected so we never serve stale paraphrases for a different
        # model.
        self._paraphrase_cache: Dict[Tuple[int, int], str] = {}
        self._paraphrase_hits = 0
        self._paraphrase_misses = 0
        self._paraphrase_cache_file: Optional[Path] = (
            Path(paraphrase_cache_file)
            if paraphrase_cache_file is not None else None
        )
        self._paraphrase_cache_loaded = 0
        self._paraphrase_cache_discarded_reason: Optional[str] = None
        if self._paraphrase_cache_file is not None and (
            self._paraphrase_cache_file.exists()
        ):
            from symbolu_bcvf_llm.sources.paraphrase import (
                paraphrase_pipeline_version,
            )

            current_version = paraphrase_pipeline_version()
            try:
                with open(self._paraphrase_cache_file) as fh:
                    payload = json.load(fh)
                cached_version = payload.get("paraphrase_pipeline_version")
                model_ok = payload.get("model_name") == model_name
                split_ok = payload.get("split") == split
                version_ok = cached_version == current_version

                if model_ok and split_ok and version_ok:
                    for k, v in payload.get("entries", {}).items():
                        row_str, seed_str = k.split("__", 1)
                        self._paraphrase_cache[(int(row_str), int(seed_str))] = v
                    self._paraphrase_cache_loaded = len(self._paraphrase_cache)
                else:
                    # Record WHY the cache was discarded — logged by the CLI
                    # so the user sees when a stale cache was rejected. This
                    # is the auto-detect behavior that replaces the manual
                    # `rm` step.
                    reasons = []
                    if not model_ok:
                        reasons.append(
                            f"model_name mismatch "
                            f"(cache={payload.get('model_name')}, "
                            f"current={model_name})"
                        )
                    if not split_ok:
                        reasons.append(
                            f"split mismatch "
                            f"(cache={payload.get('split')}, current={split})"
                        )
                    if not version_ok:
                        reasons.append(
                            f"paraphrase_pipeline_version mismatch "
                            f"(cache={cached_version or 'missing'}, "
                            f"current={current_version})"
                        )
                    self._paraphrase_cache_discarded_reason = "; ".join(reasons)
            except Exception as exc:  # pragma: no cover — corrupt cache
                self._paraphrase_cache = {}
                self._paraphrase_cache_loaded = 0
                self._paraphrase_cache_discarded_reason = (
                    f"load error: {type(exc).__name__}: {exc}"
                )

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

    def _get_or_create_paraphrase(
        self,
        row_id: int,
        base_prompt: str,
        rewrite_seed: int,
    ) -> str:
        """Cached paraphrase lookup keyed by `(row_id, rewrite_seed)`.

        Paraphrases are deterministic at temperature 0 given (model,
        prompt, seed), so the same question+seed always yields the
        same rewrite. Computing once per (question, seed) and reusing
        across the ~15 `make_sources` calls per question saves ~13×
        of the paraphrase-generation cost.

        If a `paraphrase_cache_file` is configured, every cache miss
        also writes the updated cache to disk so a subsequent run
        (seed 2, replication) loads a fully-populated cache and skips
        paraphrase generation entirely.
        """
        from symbolu_bcvf_llm.sources.paraphrase import make_paraphrased_prompt

        key = (int(row_id), int(rewrite_seed))
        if key in self._paraphrase_cache:
            self._paraphrase_hits += 1
            return self._paraphrase_cache[key]
        self._paraphrase_misses += 1
        para = make_paraphrased_prompt(
            self._model, self._tokenizer, base_prompt,
            rewrite_seed=rewrite_seed,
            max_new_tokens=self._paraphrase_max_new_tokens,
        )
        self._paraphrase_cache[key] = para
        self._persist_paraphrase_cache()
        return para

    def _persist_paraphrase_cache(self) -> None:
        """Atomic-ish JSON dump of the paraphrase cache. No-op if no
        cache file is configured. Tolerates errors — disk write is
        a performance optimization, not correctness-critical.

        Includes `paraphrase_pipeline_version` so that future reads
        refuse to load entries generated by a different template /
        cleaner. Prevents the class of bug where V1's corrupted
        paraphrases silently feed a V2 benchmark run.
        """
        if self._paraphrase_cache_file is None:
            return
        from symbolu_bcvf_llm.sources.paraphrase import (
            paraphrase_pipeline_version,
            PARAPHRASE_VERSION_TAG,
        )

        payload = {
            "model_name": self._model_name,
            "split": self._split,
            "paraphrase_pipeline_version": paraphrase_pipeline_version(),
            "paraphrase_version_tag": PARAPHRASE_VERSION_TAG,
            "entries": {
                f"{row}__{seed}": text
                for (row, seed), text in self._paraphrase_cache.items()
            },
        }
        try:
            self._paraphrase_cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._paraphrase_cache_file.with_suffix(
                self._paraphrase_cache_file.suffix + ".tmp"
            )
            tmp.write_text(json.dumps(payload, indent=2))
            tmp.replace(self._paraphrase_cache_file)
        except Exception:  # pragma: no cover — disk error, in-memory cache unaffected
            pass

    def make_sources(self, question: Question) -> List[Source]:
        from symbolu_bcvf_llm.sources.huggingface import HuggingFaceSource

        base_prompt = self._tokenizer.decode(
            question.prompt_tokens, skip_special_tokens=True
        )
        if self._use_paraphrase:
            row_id = int(question.metadata.get("truthfulqa_row_id", -1))
            seed_a, seed_b = self._rewrite_seed_pair
            para_a = self._get_or_create_paraphrase(row_id, base_prompt, seed_a)
            para_b = self._get_or_create_paraphrase(row_id, base_prompt, seed_b)
            prompts = [base_prompt, para_a, para_b]
        else:
            # Smoke mode: three identical prompts. Exercises the
            # HuggingFaceSource plumbing end-to-end without the
            # paraphrase round-trip; BCVF-trust quality is not
            # meaningful in this mode (all three sources agree
            # perfectly → uniform trust weights).
            prompts = [base_prompt, base_prompt, base_prompt]
        return [
            HuggingFaceSource(self._model, self._tokenizer, p, L=self.L)
            for p in prompts
        ]

    @property
    def paraphrase_cache_stats(self) -> Dict[str, Any]:
        """Diagnostic: cache hit / miss counts. Useful for verifying
        the 15× expected speedup is actually materializing."""
        return {
            "hits": int(self._paraphrase_hits),
            "misses": int(self._paraphrase_misses),
            "entries": int(len(self._paraphrase_cache)),
            "loaded_from_disk": int(self._paraphrase_cache_loaded),
            "persisted_to": (
                str(self._paraphrase_cache_file)
                if self._paraphrase_cache_file is not None else None
            ),
            "rewrite_seed_pair": list(self._rewrite_seed_pair),
            "discarded_reason": self._paraphrase_cache_discarded_reason,
        }

    @property
    def rewrite_seed_pair(self) -> Tuple[int, int]:
        """§1.10 replication: the two paraphrase rewrite seeds used
        by this benchmark instance. Seed 1 → (1, 2); seed 2 → (3, 4)."""
        return self._rewrite_seed_pair

    @property
    def compile_status(self) -> str:
        """`disabled` / `compiled (dynamic=...)` / `skipped: <reason>`."""
        return self._compile_status
