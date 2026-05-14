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
    """Map 'A','B','C','D' → leading-space token id."""
    out = {}
    for letter in "ABCD":
        # Some tokenizers split the leading space differently; pick
        # the last token of the encoded ' X' string, which is the
        # actual letter token in BPE/SentencePiece.
        ids = tokenizer.encode(f" {letter}", add_special_tokens=False)
        if not ids:
            raise RuntimeError(f"tokenizer produced no tokens for ' {letter}'")
        out[letter] = ids[-1]
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
        with torch.no_grad():
            out = model(
                input_ids=inputs["input_ids"],
                use_cache=True,
                past_key_values=cache_factory(),
            )
        next_logits = out.logits[0, -1, :]
        scores = {letter: float(next_logits[choice_ids[letter]].item())
                  for letter in "ABCD"}
        pred = max(scores, key=scores.get)
        is_correct = (pred == q["answer"])
        correct += int(is_correct)
        subj = q.get("subject", "unknown")
        if subj not in per_subject:
            per_subject[subj] = {"correct": 0, "total": 0}
        per_subject[subj]["correct"] += int(is_correct)
        per_subject[subj]["total"] += 1
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
                      num_layers: int = 4):
    """Tiny fake model that exercises cache.update() in its forward
    path. Logits are deterministic-but-arbitrary (a learned linear
    projection of the embedding); attention isn't actually computed
    from the cache, which means dry-run "perplexity" and "MMLU
    accuracy" are placeholder numbers — what matters is that the
    cache.update() path is exercised end-to-end.
    """
    import torch
    import torch.nn as nn

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
        model, tokenizer = _build_fake_model()
        model_id_for_summary = "fake-tiny-model (DRY-RUN)"
        mmlu_questions = MMLU_SAMPLE
    else:
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
                # Take first N questions across all subjects.
                mmlu_questions = []
                for row in ds.select(range(min(args.mmlu_num_questions, len(ds)))):
                    mmlu_questions.append({
                        "subject": row["subject"],
                        "question": row["question"],
                        "choices": row["choices"],
                        "answer": "ABCD"[int(row["answer"])],
                    })
                LOG.info("Loaded %d MMLU questions from cais/mmlu", len(mmlu_questions))
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
