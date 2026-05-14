"""Track E (route B) — Quality evaluation of TurboQuant-compressed KV
on a HuggingFace causal LM, *without* a vLLM ``cache_kv`` hook.

Drives perplexity (Wikitext-2 raw) and MMLU-subset accuracy on a model
once with the standard ``DynamicCache`` (baseline) and once with
``TurboQuantCache`` (lossy KV). Reports the deltas. Closes the
"is the §15.2 cosine real generation quality?" question, conditional
on the Track D real-value cosine result not having already failed
(see ``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §16.4).

CLI
---

  # Full GPU run
  python -m ctm_bench.scripts.track_e_quality_eval \
      --model Qwen/Qwen2.5-7B-Instruct \
      --eval perplexity,mmlu \
      --mmlu-num-questions 200 \
      --output-dir bench_out/track_e/

  # CPU dry-run — exercises cache.update() plumbing + output schema
  # without HF model download or dataset access. Verifies the script
  # before paying for GPU time.
  python -m ctm_bench.scripts.track_e_quality_eval \
      --dry-run --eval perplexity,mmlu \
      --output-dir bench_out/track_e_dryrun/

Pod / cost estimate
-------------------

Qwen2.5-7B FP16 on A100 80GB:

* Model load + tokenizer:       ~5 min
* Wikitext perplexity (1 chunk, 1024 tokens), baseline + TQ: ~2 min
* MMLU 200 questions, baseline + TQ: ~30-45 min
* Total: ~45-60 min, ~$1.00-$1.20 spot

Dry-run on CPU: ~5 seconds.

Decision tree (post-§15.4)
--------------------------

* MMLU delta within ±0.5 pt → green-light cache_kv hook (route A).
* MMLU delta > 1 pt regression → pause Tier 2; investigate per-layer
  sensitivity, possibly raise angle_bits or disable QJL.
* Perplexity ratio > 1.05 with MMLU within gate → likely a per-head
  outlier issue; investigate before routing through the hook.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


LOG = logging.getLogger("track_e")


def _check_transformers_version() -> None:
    """Hard-fail early if transformers < 5.0.

    The cache layer surface (``DynamicCache.layers[i].keys``) used by
    Track D's capture step and the ``TurboQuantCache(DynamicCache)``
    subclass both depend on the 5.x ``CacheLayer`` refactor. On 4.x
    these wouldn't fail until mid-eval, after the model has loaded and
    GPU time has been spent.
    """
    try:
        import transformers  # type: ignore
    except ImportError:
        raise SystemExit(
            "transformers not installed. Run: pip install --upgrade 'transformers>=5.0'"
        )
    major = int(transformers.__version__.split(".")[0])
    if major < 5:
        raise SystemExit(
            f"transformers {transformers.__version__} detected; this script "
            f"requires >= 5.0 for the DynamicCache.layers[i].keys API. "
            f"Run: pip install --upgrade 'transformers>=5.0'"
        )


# --------------------------------------------------------------------------- #
# Inline dataset for perplexity                                               #
#                                                                             #
# A self-contained chunk of public-domain text so the eval doesn't depend on  #
# the HF datasets library (which is firewalled on some pods). For a real run  #
# you'd swap this for a Wikitext-2 chunk; the API is identical.               #
# --------------------------------------------------------------------------- #

PERPLEXITY_TEXT = """\
The history of artificial intelligence began in antiquity with myths,
stories, and rumors of artificial beings endowed with intelligence
or consciousness by master craftsmen. The seeds of modern AI were
planted by philosophers who attempted to describe the process of
human thinking as the mechanical manipulation of symbols. This work
culminated in the invention of the programmable digital computer in
the 1940s, a machine based on the abstract essence of mathematical
reasoning. This device and the ideas behind it inspired a handful
of scientists to begin seriously discussing the possibility of
building an electronic brain. The field of AI research was founded
at a workshop held on the campus of Dartmouth College during the
summer of 1956. Those who attended would become the leaders of AI
research for many decades. Many of them predicted that a machine as
intelligent as a human being would exist in no more than a generation,
and they were given millions of dollars to make this vision come true.
Eventually it became obvious that researchers had grossly underestimated
the difficulty of the project. In 1973, in response to criticism and
continued pressure to fund AI projects, the British and U.S. governments
stopped funding undirected research into artificial intelligence.
The next several years would later be called an AI winter, a period
when obtaining funding for AI projects was difficult.
"""


# --------------------------------------------------------------------------- #
# Inline MMLU-style sample (5 questions across 5 subjects)                    #
#                                                                             #
# For a real run, swap this for the canonical cais/mmlu subset. This sample   #
# is enough to validate the prompt formatting + scoring logic on dry-run.     #
# --------------------------------------------------------------------------- #

MMLU_SAMPLE = [
    {
        "subject": "high_school_physics",
        "question": "What force keeps planets in orbit around the Sun?",
        "choices": ["Magnetism", "Gravity", "Friction", "Static electricity"],
        "answer": "B",
    },
    {
        "subject": "elementary_mathematics",
        "question": "What is 7 multiplied by 8?",
        "choices": ["54", "55", "56", "64"],
        "answer": "C",
    },
    {
        "subject": "world_history",
        "question": "In which year did World War II end?",
        "choices": ["1943", "1944", "1945", "1946"],
        "answer": "C",
    },
    {
        "subject": "chemistry",
        "question": "What is the chemical symbol for gold?",
        "choices": ["Gd", "Go", "Au", "Ag"],
        "answer": "C",
    },
    {
        "subject": "computer_science",
        "question": "Which data structure uses LIFO ordering?",
        "choices": ["Queue", "Stack", "Heap", "Tree"],
        "answer": "B",
    },
]


# --------------------------------------------------------------------------- #
# Result schema                                                               #
# --------------------------------------------------------------------------- #


@dataclass
class PerplexityRow:
    cache_type: str            # "baseline" or "turboquant"
    text_chars: int
    text_tokens: int
    perplexity: float
    nll_per_token: float


@dataclass
class MMLURow:
    cache_type: str
    num_questions: int
    correct: int
    accuracy: float
    per_subject: dict


@dataclass
class TrackESummary:
    model_id: str
    dtype: str
    eval_kinds: List[str]
    turboquant_config: dict
    perplexity: List[PerplexityRow] = field(default_factory=list)
    mmlu: List[MMLURow] = field(default_factory=list)
    deltas: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Cache factories                                                             #
# --------------------------------------------------------------------------- #


def _baseline_cache_factory() -> Callable[[], Any]:
    from transformers.cache_utils import DynamicCache
    return lambda: DynamicCache()


def _turboquant_cache_factory(*, angle_bits: int, segment_dim: int, enable_qjl: bool, backend: str) -> Callable[[], Any]:
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    def factory():
        return TurboQuantCache(
            angle_bits=angle_bits,
            segment_dim=segment_dim,
            enable_qjl=enable_qjl,
            backend=backend,
        )
    return factory


# --------------------------------------------------------------------------- #
# Perplexity                                                                  #
# --------------------------------------------------------------------------- #


def compute_perplexity(
    *, model, tokenizer, text: str, cache_factory: Callable[[], Any], cache_type: str,
) -> PerplexityRow:
    import torch
    import torch.nn.functional as F
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    input_ids = inputs["input_ids"]
    with torch.no_grad():
        out = model(input_ids=input_ids, use_cache=True, past_key_values=cache_factory())
    logits = out.logits
    shift_logits = logits[:, :-1, :].contiguous()
    shift_labels = input_ids[:, 1:].contiguous()
    nll = F.cross_entropy(
        shift_logits.view(-1, shift_logits.size(-1)),
        shift_labels.view(-1),
        reduction="mean",
    )
    nll_val = float(nll.item())
    return PerplexityRow(
        cache_type=cache_type,
        text_chars=len(text),
        text_tokens=int(input_ids.shape[1]),
        perplexity=float(math.exp(nll_val)),
        nll_per_token=nll_val,
    )


# --------------------------------------------------------------------------- #
# MMLU                                                                        #
# --------------------------------------------------------------------------- #


def _format_mmlu_prompt(q: dict) -> str:
    return (
        f"The following is a multiple-choice question. Output only the "
        f"letter of the correct answer (A, B, C, or D).\n\n"
        f"Question: {q['question']}\n"
        f"A) {q['choices'][0]}\n"
        f"B) {q['choices'][1]}\n"
        f"C) {q['choices'][2]}\n"
        f"D) {q['choices'][3]}\n"
        f"Answer:"
    )


def _choice_token_ids(tokenizer) -> dict:
    """Map 'A'/'B'/'C'/'D' → list of candidate token ids.

    Different tokenizers split the leading space differently and the
    model's next-token logits after ``"Answer:"`` may favour either
    ``"A"`` (no leading space) or ``" A"`` (with leading space)
    depending on prompt-end whitespace. We collect *both* variants per
    letter; the scorer takes ``max`` across all candidate tokens to
    avoid silently dropping the high-probability answer to a tokenizer
    quirk.

    Returns ``{'A': [tok_id_1, tok_id_2, ...], ...}`` — list of one or
    two ints per letter (two if the no-space and with-space variants
    differ, one if they collapse to the same token).
    """
    out = {}
    for letter in "ABCD":
        candidates = set()
        for variant in (letter, f" {letter}"):
            ids = tokenizer.encode(variant, add_special_tokens=False)
            if not ids:
                continue
            # Last token is the letter (BPE/SentencePiece may emit a
            # leading-space sub-token first).
            candidates.add(int(ids[-1]))
        if not candidates:
            raise RuntimeError(
                f"tokenizer produced no usable tokens for letter {letter!r}; "
                f"both 'A' and ' A' encodings returned empty"
            )
        out[letter] = sorted(candidates)
    return out


def compute_mmlu_accuracy(
    *,
    model,
    tokenizer,
    questions: Sequence[dict],
    cache_factory: Callable[[], Any],
    cache_type: str,
) -> MMLURow:
    import torch

    choice_ids = _choice_token_ids(tokenizer)
    correct = 0
    per_subject: dict = {}
    for q in questions:
        prompt = _format_mmlu_prompt(q)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        cache = cache_factory()
        with torch.no_grad():
            out = model(
                input_ids=inputs["input_ids"],
                use_cache=True,
                past_key_values=cache,
            )
        next_logits = out.logits[0, -1, :]
        # For each letter, take the max log-prob across all candidate
        # tokens — handles "A" vs " A" tokenizer variants (see
        # _choice_token_ids docstring).
        scores = {
            letter: max(float(next_logits[tid].item()) for tid in choice_ids[letter])
            for letter in "ABCD"
        }
        pred = max(scores, key=scores.get)
        is_correct = (pred == q["answer"])
        correct += int(is_correct)
        subj = q.get("subject", "unknown")
        if subj not in per_subject:
            per_subject[subj] = {"correct": 0, "total": 0}
        per_subject[subj]["correct"] += int(is_correct)
        per_subject[subj]["total"] += 1
        # Bug 3 fix: explicit per-iteration cleanup. Each ``cache`` and
        # ``out`` holds a few MB of GPU tensors; Python ref-counting
        # frees them on loop end but PyTorch's caching allocator may
        # hold the underlying buffers. ``empty_cache()`` returns them
        # to the OS so a 200-question loop doesn't drift toward OOM.
        del out, cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return MMLURow(
        cache_type=cache_type,
        num_questions=len(questions),
        correct=correct,
        accuracy=correct / len(questions) if questions else 0.0,
        per_subject={k: {**v, "accuracy": v["correct"] / v["total"]}
                     for k, v in per_subject.items()},
    )


# --------------------------------------------------------------------------- #
# Dry-run fake model                                                          #
# --------------------------------------------------------------------------- #


def _build_fake_model(*, vocab_size: int = 200, hidden: int = 64,
                      num_kv_heads: int = 4, head_dim: int = 128,
                      num_layers: int = 4, seed: int = 42):
    """Tiny fake model that exercises cache.update() in its forward
    path. Logits are deterministic-but-arbitrary (a learned linear
    projection of the embedding); attention isn't actually computed
    from the cache, which means dry-run "perplexity" and "MMLU
    accuracy" are placeholder numbers — what matters is that the
    cache.update() path is exercised end-to-end.

    The ``seed`` argument pins module init so the committed dry-run
    JSONs at ``Bench/bench_out/track_e_dryrun/`` are reproducible.
    Without it, two ``--dry-run`` invocations produce different
    perplexity numbers from the same input.
    """
    import torch
    import torch.nn as nn
    torch.manual_seed(seed)

    class FakeLM(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Embedding(vocab_size, hidden)
            self.k_proj = nn.Linear(hidden, num_kv_heads * head_dim, bias=False)
            self.v_proj = nn.Linear(hidden, num_kv_heads * head_dim, bias=False)
            self.lm_head = nn.Linear(hidden, vocab_size, bias=False)
            self._device = torch.device("cpu")

        @property
        def device(self):
            return self._device

        def forward(self, input_ids=None, use_cache=False,
                    past_key_values=None, **kwargs):
            h = self.embed(input_ids)
            B, S, _ = h.shape
            k = self.k_proj(h).view(B, S, num_kv_heads, head_dim).transpose(1, 2)
            v = self.v_proj(h).view(B, S, num_kv_heads, head_dim).transpose(1, 2)
            if past_key_values is not None:
                for layer_idx in range(num_layers):
                    past_key_values.update(k, v, layer_idx=layer_idx)
            logits = self.lm_head(h)
            class _Out:
                pass
            o = _Out()
            o.logits = logits
            o.past_key_values = past_key_values
            return o

    class FakeTokenizer:
        def __init__(self):
            # 26 lowercase + 26 uppercase + digits + space + punct ≈ vocab
            self._vocab = {chr(c): c - 32 for c in range(33, min(33 + vocab_size, 127))}

        def encode(self, text, add_special_tokens=True, **kwargs):
            ids = []
            for ch in text:
                if ch in self._vocab:
                    ids.append(self._vocab[ch])
                else:
                    ids.append(0)
            return ids

        def __call__(self, text, return_tensors=None, **kwargs):
            import torch
            ids = self.encode(text, add_special_tokens=True)
            t = torch.tensor([ids], dtype=torch.long)
            class _BatchOut:
                def __init__(self, ids):
                    self.input_ids = ids
                    self.data = {"input_ids": ids}
                def to(self, device):
                    return self
                def __getitem__(self, k):
                    return self.data[k]
                def keys(self):
                    return self.data.keys()
                def __iter__(self):
                    return iter(self.data)
            return _BatchOut(t)

    model = FakeLM().eval()
    tokenizer = FakeTokenizer()
    return model, tokenizer


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="track_e_quality_eval",
        description=(
            "Track E (route B) — quality eval of TurboQuant-compressed "
            "KV on HF transformers. No vLLM, no cache_kv hook."
        ),
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument(
        "--dtype", default="float16",
        choices=["float16", "bfloat16", "float32"],
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--eval", default="perplexity,mmlu",
        help="Comma-separated: perplexity,mmlu",
    )
    parser.add_argument(
        "--mmlu-num-questions", type=int, default=200,
        help="MMLU subset size (real run only; dry-run uses inline 5).",
    )
    parser.add_argument(
        "--mmlu-seed", type=int, default=2026,
        help=(
            "Seed for shuffling cais/mmlu before subsetting. Default "
            "2026 so two runs report against the same questions. "
            "Change only for std-error estimation across seeds."
        ),
    )
    parser.add_argument("--angle-bits", type=int, default=3)
    parser.add_argument("--segment-dim", type=int, default=128)
    parser.add_argument(
        "--no-qjl", action="store_true",
        help="Disable QJL residual projection.",
    )
    parser.add_argument(
        "--turboquant-backend", default="torch",
        choices=["numpy", "torch"],
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    eval_kinds = [s.strip() for s in args.eval.split(",") if s.strip()]
    enable_qjl = not args.no_qjl

    # ----- Load model -----
    if args.dry_run:
        LOG.info("DRY RUN: building fake tiny model")
        # Still version-check so a 4.x pod fails loud in dry-run, not
        # mid-Qwen-load 5 minutes later.
        _check_transformers_version()
        model, tokenizer = _build_fake_model()
        model_id_for_summary = "fake-tiny-model (DRY-RUN)"
        mmlu_questions = MMLU_SAMPLE
    else:
        _check_transformers_version()
        LOG.info("Loading %s (dtype=%s, device=%s)", args.model, args.dtype, args.device)
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch_dtype = getattr(torch, args.dtype)
        device_map = args.device if args.device != "auto" else "auto"
        tokenizer = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch_dtype, device_map=device_map,
        )
        model.eval()
        model_id_for_summary = args.model

        # Real-run MMLU questions: try to load cais/mmlu subset.
        if "mmlu" in eval_kinds:
            try:
                from datasets import load_dataset
                ds = load_dataset("cais/mmlu", "all", split="test")
                # Bug 2 fix: ``cais/mmlu`` orders its test split by
                # subject, so taking the first N puts all questions in
                # one subject (typically ``abstract_algebra`` for small
                # N). Shuffle with a fixed seed before subsetting so
                # the sample is representative across the 57 MMLU
                # subjects.
                ds = ds.shuffle(seed=args.mmlu_seed)
                mmlu_questions = []
                for row in ds.select(range(min(args.mmlu_num_questions, len(ds)))):
                    mmlu_questions.append({
                        "subject": row["subject"],
                        "question": row["question"],
                        "choices": row["choices"],
                        "answer": "ABCD"[int(row["answer"])],
                    })
                subjects_seen = sorted({q["subject"] for q in mmlu_questions})
                LOG.info(
                    "Loaded %d MMLU questions from cais/mmlu across %d subjects "
                    "(seed=%d)",
                    len(mmlu_questions), len(subjects_seen), args.mmlu_seed,
                )
            except Exception as exc:
                LOG.warning(
                    "MMLU dataset load failed (%s); falling back to inline sample (5 questions)",
                    exc,
                )
                mmlu_questions = MMLU_SAMPLE
        else:
            mmlu_questions = MMLU_SAMPLE

    baseline_factory = _baseline_cache_factory()
    tq_factory = _turboquant_cache_factory(
        angle_bits=args.angle_bits,
        segment_dim=args.segment_dim,
        enable_qjl=enable_qjl,
        backend=args.turboquant_backend,
    )

    summary = TrackESummary(
        model_id=model_id_for_summary,
        dtype=args.dtype,
        eval_kinds=eval_kinds,
        turboquant_config=dict(
            angle_bits=args.angle_bits,
            segment_dim=args.segment_dim,
            enable_qjl=enable_qjl,
            backend=args.turboquant_backend,
        ),
    )

    if "perplexity" in eval_kinds:
        LOG.info("Perplexity: baseline...")
        base = compute_perplexity(
            model=model, tokenizer=tokenizer, text=PERPLEXITY_TEXT,
            cache_factory=baseline_factory, cache_type="baseline",
        )
        LOG.info("Perplexity: turboquant...")
        tq = compute_perplexity(
            model=model, tokenizer=tokenizer, text=PERPLEXITY_TEXT,
            cache_factory=tq_factory, cache_type="turboquant",
        )
        summary.perplexity = [base, tq]
        summary.deltas["perplexity_ratio"] = tq.perplexity / base.perplexity
        summary.deltas["nll_delta"] = tq.nll_per_token - base.nll_per_token
        LOG.info(
            "  baseline ppl=%.4f  turboquant ppl=%.4f  ratio=%.4f",
            base.perplexity, tq.perplexity, summary.deltas["perplexity_ratio"],
        )

    if "mmlu" in eval_kinds:
        LOG.info("MMLU: baseline (%d questions)...", len(mmlu_questions))
        base = compute_mmlu_accuracy(
            model=model, tokenizer=tokenizer, questions=mmlu_questions,
            cache_factory=baseline_factory, cache_type="baseline",
        )
        LOG.info("MMLU: turboquant...")
        tq = compute_mmlu_accuracy(
            model=model, tokenizer=tokenizer, questions=mmlu_questions,
            cache_factory=tq_factory, cache_type="turboquant",
        )
        summary.mmlu = [base, tq]
        summary.deltas["mmlu_accuracy_delta_pt"] = (tq.accuracy - base.accuracy) * 100.0
        LOG.info(
            "  baseline acc=%.4f  turboquant acc=%.4f  delta=%.2fpt",
            base.accuracy, tq.accuracy, summary.deltas["mmlu_accuracy_delta_pt"],
        )

    out_path = args.output_dir / "results.json"
    with open(out_path, "w") as f:
        json.dump(asdict(summary), f, indent=2)
    LOG.info("Wrote %s", out_path)

    print()
    print("=" * 60)
    print(f"Track E summary — {summary.model_id}")
    print("=" * 60)
    if summary.perplexity:
        b, t = summary.perplexity
        print(f"  Perplexity:")
        print(f"    baseline:    {b.perplexity:.4f}  (NLL/tok {b.nll_per_token:.4f})")
        print(f"    turboquant:  {t.perplexity:.4f}  (NLL/tok {t.nll_per_token:.4f})")
        print(f"    ratio:       {summary.deltas['perplexity_ratio']:.4f}  (gate ≤ 1.05)")
    if summary.mmlu:
        b, t = summary.mmlu
        print(f"  MMLU:")
        print(f"    baseline:    {b.accuracy * 100:.2f}%   ({b.correct}/{b.num_questions})")
        print(f"    turboquant:  {t.accuracy * 100:.2f}%   ({t.correct}/{t.num_questions})")
        delta = summary.deltas['mmlu_accuracy_delta_pt']
        gate = "PASS (within ±0.5pt)" if abs(delta) <= 0.5 else (
            "PARTIAL (within ±1.0pt)" if abs(delta) <= 1.0 else "REGRESSION (> 1.0pt)"
        )
        print(f"    delta:       {delta:+.2f}pt  → {gate}")
    print()
    print(f"  Full results: {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
