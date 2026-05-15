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
from typing import Any, Callable, List, Optional, Sequence, Tuple

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


LOG = logging.getLogger("track_e")


def _check_transformers_version() -> None:
    """Hard-fail early if transformers < 5.0 OR torch < 2.5.

    Two hard requirements for the route-B path:

    * ``transformers >= 5.0`` — uses ``DynamicCache.layers[i].keys`` /
      ``.values`` which is the 5.x ``CacheLayer`` refactor's surface.
    * ``torch >= 2.5`` — transformers 5.x's ``integrations/moe.py``
      calls ``torch.library.custom_op`` with PEP-563-style string type
      annotations on tensor parameters. ``torch.library.infer_schema``
      on torch < 2.5 doesn't resolve those string annotations and
      raises ``ValueError: Parameter input has unsupported type
      torch.Tensor`` at *import* time (the MoE module imports eagerly
      via the AutoModel registry, even for non-MoE models like Qwen).

    Both failures would otherwise surface mid-eval after the model has
    started loading; checking here keeps GPU dollars from being burned
    on a version-mismatch crash.
    """
    try:
        import transformers  # type: ignore
    except ImportError:
        raise SystemExit(
            "transformers not installed. Run: pip install --upgrade 'transformers>=5.0'"
        )
    try:
        import torch  # type: ignore
    except ImportError:
        raise SystemExit(
            "torch not installed. Run: pip install --upgrade torch"
        )
    t_major = int(transformers.__version__.split(".")[0])
    if t_major < 5:
        raise SystemExit(
            f"transformers {transformers.__version__} detected; this script "
            f"requires >= 5.0 for the DynamicCache.layers[i].keys API. "
            f"Run: pip install --upgrade 'transformers>=5.0'"
        )
    torch_parts = torch.__version__.split(".")
    pt_major, pt_minor = int(torch_parts[0]), int(torch_parts[1])
    if (pt_major, pt_minor) < (2, 5):
        raise SystemExit(
            f"torch {torch.__version__} detected; transformers 5.x requires "
            f"torch >= 2.5 (the MoE integration uses torch.library.custom_op "
            f"with string-annotated tensor params, which torch < 2.5 can't "
            f"resolve at import time). Run: "
            f"pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu121"
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
class GenerationRow:
    """One side-by-side generation comparison row: baseline vs compressed
    cache produce a stream of tokens from the same prompt; we measure
    how often they agree on the next token and how far their logit
    distributions diverge.

    Mode is one of:
      * ``autoregressive`` — each cache greedy-decodes its own
        trajectory. Top-1 agreement reflects "do the two caches trace
        the same exact greedy path." Drops fast under exposure bias
        (one diff token cascades). Less partner-relevant.
      * ``teacher_forced`` — baseline greedy-decodes its trajectory
        first; the compressed cache then runs through the same
        baseline-token sequence and we compare what compressed PREDICTED
        at each step. Isolates "does the compressed cache make the
        same next-token prediction given the same context." More
        partner-relevant.
    """
    cache_type: str               # "baseline" vs the quant name being compared
    mode: str                      # "autoregressive" or "teacher_forced"
    num_prompts: int
    num_generated_per_prompt: int
    total_positions: int
    top1_match_count: int          # how many positions had exact same top-1 token
    top1_agreement_rate: float     # ratio in [0, 1]
    top5_inclusion_count: int      # how many baseline-top-1 tokens were in compressed-top-5
    top5_inclusion_rate: float
    mean_kl_divergence: float      # mean KL(compressed || baseline) across positions
    max_kl_divergence: float
    sample_baseline_text: str       # first prompt's baseline generation (truncated)
    sample_compressed_text: str     # first prompt's compressed generation


@dataclass
class TrackESummary:
    model_id: str
    dtype: str
    eval_kinds: List[str]
    turboquant_config: dict
    perplexity: List[PerplexityRow] = field(default_factory=list)
    mmlu: List[MMLURow] = field(default_factory=list)
    generation: Optional[GenerationRow] = None
    deltas: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Cache factories                                                             #
# --------------------------------------------------------------------------- #


def _baseline_cache_factory() -> Callable[[], Any]:
    from transformers.cache_utils import DynamicCache
    return lambda: DynamicCache()


def _turboquant_cache_factory(
    *, angle_bits: int, segment_dim: int, enable_qjl: bool, backend: str,
    per_channel_scale: bool = False,
    sink_size: int = 0,
) -> Callable[[], Any]:
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    def factory():
        return TurboQuantCache(
            angle_bits=angle_bits,
            segment_dim=segment_dim,
            enable_qjl=enable_qjl,
            backend=backend,
            per_channel_scale=per_channel_scale,
            sink_size=sink_size,
        )
    return factory


def _int4_per_channel_cache_factory(
    *, sink_size: int = 0, k_group_size: int = 0, v_group_size: int = 0,
    asymmetric: bool = False, bits: int = 4,
    calibration_path: Optional[str] = None,
    quantize_k: bool = True, quantize_v: bool = True,
) -> Callable[[], Any]:
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    def factory():
        return INT4PerChannelCache(
            sink_size=sink_size,
            k_group_size=k_group_size,
            v_group_size=v_group_size,
            asymmetric=asymmetric,
            bits=bits,
            calibration_path=calibration_path,
            quantize_k=quantize_k,
            quantize_v=quantize_v,
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


# --------------------------------------------------------------------------- #
# Generation-mode evaluation                                                  #
#                                                                             #
# Directly tests decode quality: greedy-generate N tokens with each cache,    #
# measure how often the compressed cache picks the same next token as the    #
# baseline and how far the logit distributions diverge. Complements the      #
# perplexity / MMLU tests which only measure prefill quality (perplexity)    #
# or short-prompt accuracy (MMLU).                                            #
# --------------------------------------------------------------------------- #


GENERATION_PROMPTS: List[str] = [
    # Chat-like
    "The three primary colors are red, blue, and",
    # Code completion
    "def fibonacci(n):\n    if n <= 1:\n        return n\n    return",
    # Factual continuation
    "The capital of France is Paris, which is famous for the",
    # Multi-step reasoning
    "If Alice has 5 apples and gives 2 to Bob, she has",
    # Multilingual / mixed
    "In Japanese, the word for 'hello' is 'konnichiwa', which is written",
]


def _generate_with_cache(
    *,
    model,
    tokenizer,
    prompt: str,
    num_tokens: int,
    cache,
    forced_tokens: Optional[List[int]] = None,
) -> "Tuple[List[int], List[Any]]":
    """Decode ``num_tokens`` after ``prompt``, using ``cache`` as the
    past_key_values store.

    Args:
        forced_tokens: when ``None`` (default), greedy-decodes (each
            step's argmax becomes the next input). When provided
            (length must equal ``num_tokens``), the cache's prediction
            is RECORDED but ignored — the next input is always the
            forced token. This is teacher-forced decoding: it makes
            the cache process the same context the baseline saw, so
            the recorded predictions can be compared like-for-like.

    Returns the *picked* token IDs (= forced_tokens when forced, else
    the cache's argmax picks) and the predictive logit at each step.
    """
    import torch
    if forced_tokens is not None and len(forced_tokens) != num_tokens:
        raise ValueError(
            f"forced_tokens must have length {num_tokens}; got {len(forced_tokens)}"
        )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_ids = inputs["input_ids"]

    # Prefill.
    with torch.no_grad():
        out = model(input_ids=input_ids, use_cache=True, past_key_values=cache)
    next_token_logits = out.logits[0, -1, :]

    picked: List[int] = []
    logits_list: List[Any] = []
    for step in range(num_tokens):
        # Record this step's predictive distribution.
        logits_list.append(next_token_logits.detach().cpu().to(torch.float32))
        # In teacher-forced mode, ignore the cache's argmax and feed
        # the forced token. Otherwise greedy-pick.
        if forced_tokens is not None:
            input_token_id = int(forced_tokens[step])
        else:
            input_token_id = int(next_token_logits.argmax().item())
        picked.append(input_token_id)
        # Decode-step forward pass with the picked / forced token.
        next_token_tensor = torch.tensor([[input_token_id]], device=model.device)
        with torch.no_grad():
            out = model(
                input_ids=next_token_tensor,
                use_cache=True,
                past_key_values=cache,
            )
        next_token_logits = out.logits[0, -1, :]
    return picked, logits_list


def compute_generation_agreement(
    *,
    model,
    tokenizer,
    prompts: List[str],
    num_tokens: int,
    baseline_factory: Callable[[], Any],
    compressed_factory: Callable[[], Any],
    compressed_label: str,
    mode: str = "autoregressive",
) -> GenerationRow:
    """For each prompt, decode ``num_tokens`` with the baseline cache
    and with the compressed cache, then compare next-token picks +
    logit-distribution KL across all positions.

    Modes:
      * ``autoregressive``: each cache greedy-decodes its own
        trajectory. Top-1 agreement reflects "do they trace the
        same exact greedy path." Drops fast under exposure bias.
      * ``teacher_forced``: baseline greedy-decodes, then compressed
        re-runs with the same baseline tokens forced as input at each
        step. Top-1 agreement reflects "given the same context, does
        the compressed cache predict the same next token." More
        partner-relevant for "is the compressed cache faithful".
    """
    if mode not in ("autoregressive", "teacher_forced"):
        raise ValueError(f"mode must be autoregressive or teacher_forced; got {mode!r}")
    import torch
    import torch.nn.functional as F

    total_positions = 0
    top1_match_count = 0
    top5_inclusion_count = 0
    kl_values: List[float] = []
    sample_baseline_text = ""
    sample_compressed_text = ""

    for prompt_idx, prompt in enumerate(prompts):
        # Two independent caches — one for each generation pass.
        base_cache = baseline_factory()
        comp_cache = compressed_factory()

        base_tokens, base_logits = _generate_with_cache(
            model=model, tokenizer=tokenizer, prompt=prompt,
            num_tokens=num_tokens, cache=base_cache,
        )
        # In teacher-forced mode, we feed compressed the baseline's
        # tokens at each step (ignoring its own argmax). In
        # autoregressive mode, compressed picks freely.
        forced = base_tokens if mode == "teacher_forced" else None
        comp_tokens, comp_logits = _generate_with_cache(
            model=model, tokenizer=tokenizer, prompt=prompt,
            num_tokens=num_tokens, cache=comp_cache,
            forced_tokens=forced,
        )

        # Top-1 agreement: do baseline and compressed PREDICT the same
        # next token at each step? Always compare argmax(logits), not
        # the input/picked tokens — this works correctly in both
        # autoregressive (where input==argmax) and teacher_forced
        # (where input was forced to baseline's choice but argmax is
        # compressed's actual prediction).
        for b_log, c_log in zip(base_logits, comp_logits):
            b_pred = int(b_log.argmax().item())
            c_pred = int(c_log.argmax().item())
            if b_pred == c_pred:
                top1_match_count += 1
            total_positions += 1

        # Top-5 inclusion: is the baseline's top-1 prediction in the
        # compressed cache's top-5? (a softer compatibility measure)
        for b_log, c_logits in zip(base_logits, comp_logits):
            b_pred = int(b_log.argmax().item())
            top5 = torch.topk(c_logits, k=5).indices.tolist()
            if b_pred in top5:
                top5_inclusion_count += 1

        # KL(compressed || baseline) per step. We use the compressed
        # distribution as P (what's actually emitted in deployment) and
        # the baseline as Q (the ideal reference) — partner-relevant
        # framing of "how far is what we'd actually generate from what
        # we should generate."
        for b_log, c_log in zip(base_logits, comp_logits):
            base_log_probs = F.log_softmax(b_log, dim=-1)
            comp_log_probs = F.log_softmax(c_log, dim=-1)
            comp_probs = comp_log_probs.exp()
            kl = (comp_probs * (comp_log_probs - base_log_probs)).sum().item()
            kl_values.append(float(kl))

        # Capture the first prompt's generation for human-eyeball
        # inspection in the artefact.
        if prompt_idx == 0:
            sample_baseline_text = (
                prompt + tokenizer.decode(base_tokens, skip_special_tokens=True)
            )
            sample_compressed_text = (
                prompt + tokenizer.decode(comp_tokens, skip_special_tokens=True)
            )

        del base_cache, comp_cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    mean_kl = sum(kl_values) / len(kl_values) if kl_values else 0.0
    max_kl = max(kl_values) if kl_values else 0.0

    return GenerationRow(
        cache_type=compressed_label,
        mode=mode,
        num_prompts=len(prompts),
        num_generated_per_prompt=num_tokens,
        total_positions=total_positions,
        top1_match_count=top1_match_count,
        top1_agreement_rate=(
            top1_match_count / total_positions if total_positions else 0.0
        ),
        top5_inclusion_count=top5_inclusion_count,
        top5_inclusion_rate=(
            top5_inclusion_count / total_positions if total_positions else 0.0
        ),
        mean_kl_divergence=mean_kl,
        max_kl_divergence=max_kl,
        sample_baseline_text=sample_baseline_text[:500],
        sample_compressed_text=sample_compressed_text[:500],
    )


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

        def decode(self, ids, skip_special_tokens=True, **kwargs):
            # Inverse of encode: map int → ASCII char if in our vocab.
            inv = {v: k for k, v in self._vocab.items()}
            return "".join(inv.get(int(i), "?") for i in ids)

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
        help=(
            "Comma-separated: perplexity, mmlu, generation. "
            "'generation' greedy-decodes a fixed set of prompts with "
            "baseline and compressed caches side-by-side, reporting "
            "top-1 next-token agreement rate + mean/max KL divergence "
            "of per-step logits. Directly validates decode quality "
            "(complementing perplexity which measures prefill, MMLU "
            "which measures short-prompt accuracy)."
        ),
    )
    parser.add_argument(
        "--generation-num-tokens", type=int, default=50,
        help=(
            "Tokens to decode per prompt in --eval generation. "
            "Default 50. Each token is one decode step which exercises "
            "the cache.update() path with S=1."
        ),
    )
    parser.add_argument(
        "--generation-mode", default="autoregressive",
        choices=["autoregressive", "teacher_forced"],
        help=(
            "How to compare baseline vs compressed during generation. "
            "'autoregressive' (default): each cache greedy-decodes its "
            "own trajectory. Top-1 agreement reflects 'do they trace "
            "the same exact greedy path' — drops fast under exposure "
            "bias (1 different token cascades). "
            "'teacher_forced': baseline picks tokens, compressed runs "
            "with the same tokens forced as input at each step. Top-1 "
            "agreement reflects 'given identical context, does "
            "compressed predict the same next token' — more partner-"
            "relevant for 'is the compressed cache faithful'."
        ),
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
    parser.add_argument(
        "--quant", default="turboquant",
        choices=["turboquant", "int4-per-channel"],
        help=(
            "Which KV compression algorithm to test. "
            "'turboquant' = PolarQuant + optional QJL (the architecture-"
            "doc default; documented to fail at 3-4 bit on Qwen2.5-7B in "
            "PHASE4_GPU_FINDINGS.md §17). "
            "'int4-per-channel' = KIVI-style INT4 with per-channel K + "
            "per-token V scales; no rotation step, no polar "
            "decomposition. Recommended after the §17 PolarQuant negative "
            "result. The TurboQuant-specific flags (--angle-bits, "
            "--segment-dim, --no-qjl, --per-channel-scale) are silently "
            "ignored when --quant is int4-per-channel."
        ),
    )
    parser.add_argument(
        "--k-group-size", type=int, default=0,
        help=(
            "INT4 K quantization group size along the seq axis. "
            "0 = plain per-channel (one scale per (head, head_dim) "
            "covering all seq positions). Recommended for KIVI-style "
            "operation: 32 (smaller groups improve outlier-position "
            "resolution at marginal scale-storage cost). KIVI's "
            "published Qwen-family numbers use group_size=32 or 128."
        ),
    )
    parser.add_argument(
        "--v-group-size", type=int, default=0,
        help=(
            "INT4 V quantization group size along the head_dim axis. "
            "0 = plain per-token. For Qwen2.5-7B (head_dim=128) and "
            "group_size=32: each (seq, head) gets 4 scales (one per "
            "32 head_dim elements) instead of one."
        ),
    )
    parser.add_argument(
        "--asymmetric-int4", action="store_true",
        help=(
            "Use asymmetric (affine) INT4 quantization with scale + "
            "zero-point/offset. Maps [x_min, x_max] → [-8, +7] using "
            "all 16 bins. Symmetric (default) uses max(|x|)/7, "
            "wasting bins for asymmetric distributions. Real K-after-"
            "RoPE is typically not centred on zero — asymmetric is "
            "what KIVI's published quality numbers use. Adds one FP16 "
            "offset per scale (~6%% storage overhead). Recommended "
            "with --quant int4-per-channel; ignored otherwise."
        ),
    )
    parser.add_argument(
        "--calibration-path", type=str, default=None,
        help=(
            "Path to a .pt calibration file produced by "
            "calibrate_int4_scales.py. When provided, INT4 scales are "
            "static per-layer (loaded from this file) instead of "
            "dynamic per-block (computed from each forward's max(|x|)). "
            "Requires --k-group-size 0 --v-group-size 0 (static "
            "calibration is per-channel, not per-(channel, group)). "
            "Ignored when --quant is not int4-per-channel."
        ),
    )
    parser.add_argument(
        "--bits", type=int, default=4,
        help=(
            "Bit width per quantized value (per element). 4 (default) "
            "is the validated KIVI config. 3 is experimental — quality "
            "TBD per model; theoretical compression ~4.3× vs FP16 if "
            "quality holds. Note: actual heap savings at bits<4 "
            "require additional sub-4-bit packing work (not in this "
            "commit); the QUALITY effect of bits<4 is what this flag "
            "tests. Must be in [2, 8]."
        ),
    )
    parser.add_argument(
        "--per-channel-scale", action="store_true",
        help=(
            "KIVI-style per-channel pre-quantisation normalisation: "
            "divide K and V by their per-(head, head_dim) magnitude "
            "before PolarQuant, multiply back on decompress. Targets "
            "the K-outlier-channel failure mode that produced the 3052x "
            "perplexity blow-up at 3-bit (PHASE4_GPU_FINDINGS.md §17). "
            "Adds 2 KB of scale storage per K (or V) block (~6%% overhead)."
        ),
    )
    parser.add_argument(
        "--sink-size", type=int, default=0,
        help=(
            "StreamingLLM-style attention-sink passthrough: keep the "
            "first N positions of context at full precision; compress "
            "only positions [N:]. Targets the position-outlier failure "
            "mode where the first 1-4 tokens carry disproportionate "
            "attention mass and quantising them destroys generation "
            "quality. Reasonable values: 4 (StreamingLLM default), 8, "
            "16. Cost: ~4 KB per layer per K+V at sink_size=4 (2 bytes "
            "* 4 sink positions * 4 KV heads * 128 head_dim * 2 for K+V); "
            "negligible against the model's tens-of-GB weights. Default "
            "0 means no sink-skip."
        ),
    )
    parser.add_argument(
        "--perplexity-text-path",
        type=Path, default=None,
        help=(
            "Path to a plain-text file with the perplexity-eval input. "
            "When unset (default), the inline 282-token PERPLEXITY_TEXT "
            "(Wikipedia-style AI history) is used. Pass a long passage "
            "(e.g., a 32k-character arXiv chapter) to validate the §20.4 "
            "long-context cell — KV compression's headline value is at "
            "long contexts where KV memory dominates over weights. The "
            "input is fed as a single forward pass; check your model's "
            "max_position_embeddings before passing anything > 32k. "
            "Ignored when --eval doesn't include 'perplexity'."
        ),
    )
    parser.add_argument(
        "--perplexity-text-max-chars",
        type=int, default=None,
        help=(
            "When --perplexity-text-path is set and the file is larger "
            "than this many characters, truncate to the first N chars. "
            "Useful for sweep cells (run the same passage at different "
            "context lengths). Default: no truncation."
        ),
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
    # Pick the right cache factory based on --quant
    if args.quant == "turboquant":
        tq_factory = _turboquant_cache_factory(
            angle_bits=args.angle_bits,
            segment_dim=args.segment_dim,
            enable_qjl=enable_qjl,
            backend=args.turboquant_backend,
            per_channel_scale=args.per_channel_scale,
            sink_size=args.sink_size,
        )
        config_dict = dict(
            quant="turboquant",
            angle_bits=args.angle_bits,
            segment_dim=args.segment_dim,
            enable_qjl=enable_qjl,
            backend=args.turboquant_backend,
            per_channel_scale=args.per_channel_scale,
            sink_size=args.sink_size,
        )
    elif args.quant == "int4-per-channel":
        tq_factory = _int4_per_channel_cache_factory(
            sink_size=args.sink_size,
            k_group_size=args.k_group_size,
            v_group_size=args.v_group_size,
            asymmetric=args.asymmetric_int4,
            bits=args.bits,
            calibration_path=args.calibration_path,
        )
        config_dict = dict(
            quant="int4-per-channel",
            sink_size=args.sink_size,
            k_group_size=args.k_group_size,
            v_group_size=args.v_group_size,
            asymmetric=args.asymmetric_int4,
            bits=args.bits,
            calibration_path=args.calibration_path,
            scheme=f"K=per-channel INT{args.bits}, V=per-token INT{args.bits}"
                   + (", asymmetric" if args.asymmetric_int4 else ", symmetric")
                   + (f", calibrated[{args.calibration_path}]" if args.calibration_path else ""),
        )
    else:
        raise SystemExit(f"unknown --quant {args.quant!r}")

    summary = TrackESummary(
        model_id=model_id_for_summary,
        dtype=args.dtype,
        eval_kinds=eval_kinds,
        turboquant_config=config_dict,
    )

    # Label used in the row.cache_type field and summary output for the
    # compressed-cache leg. Reflects what --quant was actually selected
    # so a multi-algorithm artefact archive doesn't ambiguously say
    # "turboquant" for an INT4 run.
    quant_label = args.quant

    if "perplexity" in eval_kinds:
        # Choose the perplexity input. Default = inline 282-token text;
        # override = file path (used by the §20.4 long-context cell).
        if args.perplexity_text_path is not None:
            perplexity_text = args.perplexity_text_path.read_text()
            if args.perplexity_text_max_chars is not None:
                perplexity_text = perplexity_text[: args.perplexity_text_max_chars]
            LOG.info(
                "Perplexity text loaded from %s (%d chars)",
                args.perplexity_text_path, len(perplexity_text),
            )
        else:
            perplexity_text = PERPLEXITY_TEXT
        LOG.info("Perplexity: baseline...")
        base = compute_perplexity(
            model=model, tokenizer=tokenizer, text=perplexity_text,
            cache_factory=baseline_factory, cache_type="baseline",
        )
        LOG.info("Perplexity: %s...", quant_label)
        tq = compute_perplexity(
            model=model, tokenizer=tokenizer, text=perplexity_text,
            cache_factory=tq_factory, cache_type=quant_label,
        )
        summary.perplexity = [base, tq]
        summary.deltas["perplexity_ratio"] = tq.perplexity / base.perplexity
        summary.deltas["nll_delta"] = tq.nll_per_token - base.nll_per_token
        LOG.info(
            "  baseline ppl=%.4f  %s ppl=%.4f  ratio=%.4f",
            base.perplexity, quant_label, tq.perplexity,
            summary.deltas["perplexity_ratio"],
        )

    if "mmlu" in eval_kinds:
        LOG.info("MMLU: baseline (%d questions)...", len(mmlu_questions))
        base = compute_mmlu_accuracy(
            model=model, tokenizer=tokenizer, questions=mmlu_questions,
            cache_factory=baseline_factory, cache_type="baseline",
        )
        LOG.info("MMLU: %s...", quant_label)
        tq = compute_mmlu_accuracy(
            model=model, tokenizer=tokenizer, questions=mmlu_questions,
            cache_factory=tq_factory, cache_type=quant_label,
        )
        summary.mmlu = [base, tq]
        summary.deltas["mmlu_accuracy_delta_pt"] = (tq.accuracy - base.accuracy) * 100.0
        LOG.info(
            "  baseline acc=%.4f  %s acc=%.4f  delta=%.2fpt",
            base.accuracy, quant_label, tq.accuracy,
            summary.deltas["mmlu_accuracy_delta_pt"],
        )

    if "generation" in eval_kinds:
        LOG.info(
            "Generation (%s): %d prompts × %d tokens baseline-vs-%s...",
            args.generation_mode, len(GENERATION_PROMPTS),
            args.generation_num_tokens, quant_label,
        )
        gen_row = compute_generation_agreement(
            model=model, tokenizer=tokenizer,
            prompts=GENERATION_PROMPTS,
            num_tokens=args.generation_num_tokens,
            baseline_factory=baseline_factory,
            compressed_factory=tq_factory,
            compressed_label=quant_label,
            mode=args.generation_mode,
        )
        summary.generation = gen_row
        summary.deltas["generation_top1_agreement"] = gen_row.top1_agreement_rate
        summary.deltas["generation_top5_inclusion"] = gen_row.top5_inclusion_rate
        summary.deltas["generation_mean_kl"] = gen_row.mean_kl_divergence
        LOG.info(
            "  top-1 agreement %.4f (%d/%d), top-5 inclusion %.4f, mean KL %.4f",
            gen_row.top1_agreement_rate,
            gen_row.top1_match_count, gen_row.total_positions,
            gen_row.top5_inclusion_rate, gen_row.mean_kl_divergence,
        )

    out_path = args.output_dir / "results.json"
    with open(out_path, "w") as f:
        json.dump(asdict(summary), f, indent=2)
    LOG.info("Wrote %s", out_path)

    print()
    print("=" * 60)
    print(f"Track E summary — {summary.model_id}")
    print("=" * 60)
    # Width to right-align the compressed-cache label so it doesn't
    # offset the numbers vs the baseline row.
    label_w = max(len("baseline"), len(quant_label))
    if summary.perplexity:
        b, t = summary.perplexity
        print(f"  Perplexity:")
        print(f"    {'baseline'.ljust(label_w)}:  {b.perplexity:.4f}  (NLL/tok {b.nll_per_token:.4f})")
        print(f"    {quant_label.ljust(label_w)}:  {t.perplexity:.4f}  (NLL/tok {t.nll_per_token:.4f})")
        print(f"    {'ratio'.ljust(label_w)}:  {summary.deltas['perplexity_ratio']:.4f}  (gate ≤ 1.05)")
    if summary.mmlu:
        b, t = summary.mmlu
        print(f"  MMLU:")
        print(f"    {'baseline'.ljust(label_w)}:  {b.accuracy * 100:.2f}%   ({b.correct}/{b.num_questions})")
        print(f"    {quant_label.ljust(label_w)}:  {t.accuracy * 100:.2f}%   ({t.correct}/{t.num_questions})")
        delta = summary.deltas['mmlu_accuracy_delta_pt']
        # Direction-aware label: a positive delta is "compressed scored
        # higher than baseline" (usually statistical noise at small
        # sample sizes, but never a regression). Treat magnitudes
        # symmetrically when within the noise bands, but never call
        # an improvement a "regression".
        absd = abs(delta)
        if absd <= 0.5:
            gate = "PASS (within ±0.5pt)"
        elif absd <= 1.0:
            gate = "PARTIAL (within ±1.0pt)"
        elif delta < 0:
            gate = "REGRESSION (> 1.0pt)"
        else:
            # delta > 1.0pt and positive: compressed beat baseline.
            # That's not a regression — it's likely noise on a small
            # MMLU subset (e.g., 200q CI ≈ ±3.4pt). Annotate explicitly.
            gate = (
                f"IMPROVEMENT (+{delta:.2f}pt) — likely noise at "
                f"{t.num_questions}q sample size; rerun with more "
                f"questions to confirm"
            )
        print(f"    {'delta'.ljust(label_w)}:  {delta:+.2f}pt  → {gate}")
    if summary.generation:
        g = summary.generation
        print(f"  Generation ({g.mode}):")
        print(f"    prompts:               {g.num_prompts} × {g.num_generated_per_prompt} tokens")
        print(f"    top-1 agreement:       {g.top1_agreement_rate * 100:.2f}%  "
              f"({g.top1_match_count}/{g.total_positions})")
        print(f"    top-5 inclusion:       {g.top5_inclusion_rate * 100:.2f}%  "
              f"({g.top5_inclusion_count}/{g.total_positions})")
        print(f"    mean KL per step:      {g.mean_kl_divergence:.4f}")
        print(f"    max KL per step:       {g.max_kl_divergence:.4f}")
        # Sample-text comparison so a human can eyeball the first prompt
        # and see if the compressed generation is recognisable.
        print(f"    sample baseline text:  {g.sample_baseline_text[:150]!r}")
        print(f"    sample {quant_label} text: {g.sample_compressed_text[:150]!r}")
    print()
    print(f"  Full results: {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
