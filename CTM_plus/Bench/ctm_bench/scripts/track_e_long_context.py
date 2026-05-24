"""§20.4 long-context validation — perplexity at 16k/32k/50k +
needle-in-haystack retrieval.

KV compression's headline value is at long contexts where KV memory
dominates over weights. Qwen2.5-7B at 32k: weights ~14 GB, KV at FP16
~16 GB. Compression payoff is here.

This harness runs two complementary tests in a single model load:

1. **Perplexity sweep** at multiple context lengths against a long
   reference passage. The §19.4 result (1.024× ratio) was at 282
   tokens; this measures whether quality holds at the context length
   where compression actually pays off.

2. **Needle-in-haystack** retrieval at multiple (depth %, context
   length) pairs. Inserts a unique fact ("the secret code is X")
   at depth N% of a filler passage and asks the model to retrieve it.
   Tests functional capability, not just average loss — a model can
   have similar perplexity but fail to retrieve specific information
   under heavy compression.

The brief (§20.4 of the FP8-KV gap closure work) says:
"Use the same RULER / Needle-in-Haystack harness pattern from CTM+
Phase 4 closure if it exists; otherwise a perplexity sweep on a 32k
slice of the calibration corpus is acceptable."

The existing `test_needle_haystack.py` at the repo root is tied to
the in-house `symbolu.phase_transformer`; we lift its haystack /
needle template patterns but reimplement for HF transformers + the
route-B INT4PerChannelCache. Both halves of the eval run against the
same model load so the cost is one model warmup amortized over both
metrics.

CLI
---

  # Real run on Qwen2.5-7B (~$0.50, ~30 min wall on A100 40 GB):
  python -m ctm_bench.scripts.track_e_long_context \\
      --model Qwen/Qwen2.5-7B-Instruct \\
      --device cuda --dtype float16 \\
      --perplexity-text-path /tmp/wikitext_long.txt \\
      --context-lengths 4096,16384,32768 \\
      --needle-depths 0.1,0.5,0.9 \\
      --needle-samples 3 \\
      --output bench_out/track_e_audit_followups/long_context.json

  # CPU dry-run (no HF model, no GPU):
  python -m ctm_bench.scripts.track_e_long_context \\
      --dry-run \\
      --output /tmp/dry_long_context.json

What it measures
----------------

Per (context_length, cache_type):
  * Perplexity on the first `context_length` chars of the reference
    text. (chars, not tokens — same convention as
    `--perplexity-text-max-chars` in `track_e_quality_eval.py`.)
Per (context_length, depth_percent, cache_type, sample_idx):
  * Needle retrieval accuracy: did the model produce the expected
    code in the first N greedy-decoded tokens after the prompt?
  * Also records the generated text + the depth_position_tokens.

Output schema (`§20.4.v1`)
-------------------------

Top-level: `model_id`, `dtype`, `int4_config`, `context_lengths`,
`needle_depths`, `perplexity_rows`, `needle_rows`, `deltas`.
Composer (`compose_long_context_summary.py`) ingests this.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

from ctm_bench.sweep_utils import (
    check_context_window,
    cleanup_cuda_after_trial,
    save_partial_json,
)


LOG = logging.getLogger("long_context")


def _import_quality_eval_helpers():
    from ctm_bench.scripts import track_e_quality_eval as qe
    return qe


# --------------------------------------------------------------------------- #
# Haystack + needle patterns                                                  #
#                                                                             #
# Lifted from /home/user/symbolu/test_needle_haystack.py (in-house            #
# December 2025 needle-haystack harness), which targets phase_transformer.    #
# We use the same text passages so the test is comparable in shape, but      #
# the scoring / cache path is HF-transformers + INT4PerChannelCache.         #
# --------------------------------------------------------------------------- #


HAYSTACK_TEXTS: List[str] = [
    "The way to get startup ideas is not to try to think of startup ideas. "
    "It's to look for problems, preferably problems you have yourself. "
    "The very best startup ideas tend to have three things in common: "
    "they're something the founders themselves want, that they themselves can build, "
    "and that few others realize are worth doing.",

    "When you're operating on the margin of what's possible, you need a lot of "
    "drive to keep going. The founders who do best are the ones who are motivated "
    "by the problem rather than the money. They want to solve this problem. "
    "The money is just a way to keep doing it.",

    "The most common mistake startups make is to solve problems no one has. "
    "You'd be surprised how often founders build something first and only then "
    "try to find users for it. The problem is, by then it's too late.",

    "In the best case, you end up with something that users love. "
    "The most important thing to do is to build something a few users love, "
    "not something a lot of users sort of like. If you make something users love, "
    "they'll tell their friends, and it will grow organically.",

    "One of the most valuable things I learned from starting a startup was "
    "how important it is to do things that don't scale. "
    "In the early days, you should do things manually. "
    "Talk to users one at a time. Hand-deliver products.",

    "The best founders are often people who've made mistakes before. "
    "They've learned from those mistakes. They know what to avoid. "
    "Experience is valuable, but not in the way most people think.",

    "Focus is about saying no. You can't do everything. "
    "The companies that win are the ones that focus relentlessly "
    "on doing one thing very well. Everything else is a distraction.",

    "The best way to predict the future is to create it. "
    "Don't wait for opportunities; create them. "
    "The people who change the world are the ones who act, "
    "not the ones who wait for permission.",
]


# Needle templates: (statement_inserted_in_haystack, question_at_end,
# answer_format). The model is asked the question after seeing the
# haystack-with-needle; we score whether it produces the answer.
NEEDLE_TEMPLATES: List[tuple[str, str, str]] = [
    ("The secret code is {code}.", "What is the secret code?", "{code}"),
    ("The password to the vault is {code}.", "What is the password to the vault?", "{code}"),
    ("The magic number is {code}.", "What is the magic number?", "{code}"),
    ("Remember this key: {code}.", "What is the key to remember?", "{code}"),
]


def _generate_code(rng: random.Random, length: int = 6) -> str:
    """Generate a random 6-character alphanumeric code. Length-6 keeps
    the tokenizer-split footprint small (~2-3 BPE tokens) so the
    needle isn't dominated by trailing whitespace."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(rng.choice(chars) for _ in range(length))


def _build_haystack(target_chars: int, rng: random.Random) -> str:
    """Build a haystack passage of approximately `target_chars` length.
    Uses chars (not tokens) so it composes with the `--perplexity-text-max-chars`
    convention. Repeats HAYSTACK_TEXTS in random order until target hit."""
    parts: List[str] = []
    accum = 0
    while accum < target_chars:
        text = rng.choice(HAYSTACK_TEXTS)
        parts.append(text)
        accum += len(text) + 1
    return " ".join(parts)[:target_chars]


def _insert_needle_at_depth(
    haystack: str, needle: str, depth_percent: float,
) -> tuple[str, int]:
    """Insert `needle` at approximately `depth_percent` of `haystack`'s
    character length. Returns (text_with_needle, insert_position_chars).

    Char-based insertion is intentional — we control depth at the
    char layer (deterministic) and let the tokenizer handle the
    token-level position downstream. This matches the in-house
    test_needle_haystack pattern.
    """
    n = len(haystack)
    insert_at = int(n * depth_percent)
    # Round to nearest sentence boundary (period + space) for a clean
    # insertion; falls back to the exact position if no boundary
    # nearby.
    search = haystack[max(0, insert_at - 50):min(n, insert_at + 50)]
    period_offset = search.rfind(". ")
    if period_offset >= 0:
        insert_at = max(0, insert_at - 50) + period_offset + 2
    return haystack[:insert_at] + needle + " " + haystack[insert_at:], insert_at


# --------------------------------------------------------------------------- #
# Result schema                                                               #
# --------------------------------------------------------------------------- #


@dataclass
class PerplexityAtLengthRow:
    """One perplexity measurement at a specific context length."""
    cache_type: str
    context_length_chars: int
    context_length_tokens: int
    perplexity: float
    nll_per_token: float


@dataclass
class NeedleRow:
    """One needle-in-haystack measurement.

    `correct` is True when the expected `answer_code` appears in the
    first `decode_tokens` greedy-decoded outputs after the prompt.

    The §20.4 diagnostic-sprint fields below are populated on every
    trial so the sink-sweep / K-V-ablation / INT5 runs all surface the
    same decode-stability signal:

      * ``first_stutter_position`` — token index where the decode first
        starts to loop (consecutive-token repeat or an immediately
        repeating bigram). -1 means no stutter detected in the decoded
        window. The earliest stutter is the headline degradation
        signal — a needle can still be "correct" yet stutter right
        after emitting the code.
      * ``repeated_token_rate`` — 1 − (unique tokens / total tokens)
        over the decoded window. Catches AB-AB loops that a
        consecutive-only check misses.
      * ``decode_entropy_mean`` / ``decode_entropy_min`` — entropy
        (nats) of the next-token distribution at each decode step.
      * ``decode_entropy_collapsed`` — heuristic: mean decode entropy
        below ``_ENTROPY_COLLAPSE_NATS``. A collapsed distribution is
        the signature of a degenerate greedy loop.
      * ``cache_fp16_bytes`` / ``cache_compressed_bytes`` /
        ``cache_compression_ratio`` — memory footprint. For the INT4
        cache these come from the kvstore's measured byte counters;
        for the baseline DynamicCache they are the summed FP16 tensor
        bytes (ratio 1.0).
      * ``decode_tokens_per_s`` — secondary throughput signal: decoded
        tokens divided by the wall time of the greedy-decode loop.
    """
    cache_type: str
    context_length_chars: int
    context_length_tokens: int
    depth_percent: float
    sample_idx: int
    answer_code: str
    generated_text: str
    correct: bool
    first_stutter_position: int = -1
    repeated_token_rate: float = 0.0
    decode_entropy_mean: float = 0.0
    decode_entropy_min: float = 0.0
    decode_entropy_collapsed: bool = False
    cache_fp16_bytes: int = 0
    cache_compressed_bytes: int = 0
    cache_compression_ratio: float = 0.0
    decode_tokens_per_s: float = 0.0


# Heuristic threshold (nats) below which a greedy decode's mean
# next-token entropy is flagged as "collapsed" — the distribution has
# become a near-deterministic spike, the signature of a degenerate
# repeat loop. Documented as heuristic; tune against observed runs.
_ENTROPY_COLLAPSE_NATS = 0.30


def _detect_first_stutter(ids: List[int]) -> int:
    """Return the token index where the decode first starts to loop.

    Two cheap, interpretable detectors:
      1. consecutive-token repeat: ``ids[i] == ids[i-1]``.
      2. immediately repeating bigram: ``(ids[i-1], ids[i])`` equals
         ``(ids[i-3], ids[i-2])`` — catches AB-AB loops.

    Returns the earliest index either fires at, or -1 if neither does.
    """
    first = -1
    for i in range(1, len(ids)):
        if ids[i] == ids[i - 1]:
            first = i
            break
    for i in range(3, len(ids)):
        if ids[i] == ids[i - 2] and ids[i - 1] == ids[i - 3]:
            if first < 0 or i < first:
                first = i
            break
    return first


def _repeated_token_rate(ids: List[int]) -> float:
    """Fraction of decoded tokens that are non-novel: 1 − unique/total.

    A healthy decode of N tokens is mostly distinct, so this stays
    low; a degenerate loop drives it toward 1.0."""
    if not ids:
        return 0.0
    return 1.0 - (len(set(ids)) / len(ids))


def _cache_memory_stats(cache: Any) -> tuple[int, int, float]:
    """Return ``(fp16_bytes, compressed_bytes, actual_compression_ratio)``.

    The INT4 route-B cache exposes ``int4_stats`` with measured byte
    counters from the kvstore. The baseline DynamicCache has no such
    counters, so we sum its key/value tensor bytes (ratio 1.0).

    The ratio is the *actual heap* ratio (``actual_compression_ratio``),
    consistent with ``compressed_bytes`` (= ``bytes_out_actual``). For
    > 4-bit channels (e.g. K-INT8) this is lower than the theoretical
    ``compression_ratio`` — int8 storage until a sub-byte packer lands.
    """
    stats = getattr(cache, "int4_stats", None)
    if isinstance(stats, dict) and "bytes_in" in stats:
        fp16 = int(stats.get("bytes_in", 0))
        comp = int(stats.get("bytes_out_actual", 0))
        ratio = float(stats.get("actual_compression_ratio", 0.0))
        return fp16, comp, ratio
    total = 0
    layers = getattr(cache, "layers", None)
    if layers is not None:
        for layer in layers:
            for name in ("keys", "values"):
                t = getattr(layer, name, None)
                if t is not None and hasattr(t, "numel"):
                    total += int(t.element_size() * t.numel())
    else:
        for name in ("key_cache", "value_cache"):
            seq = getattr(cache, name, None) or []
            for t in seq:
                if hasattr(t, "numel"):
                    total += int(t.element_size() * t.numel())
    return total, total, 1.0


@dataclass
class LongContextSummary:
    schema_version: str = "§20.4.v2"
    model_id: str = ""
    dtype: str = ""
    int4_config: dict = field(default_factory=dict)
    context_lengths: List[int] = field(default_factory=list)
    needle_depths: List[float] = field(default_factory=list)
    perplexity_rows: List[PerplexityAtLengthRow] = field(default_factory=list)
    needle_rows: List[NeedleRow] = field(default_factory=list)
    deltas: dict = field(default_factory=dict)
    skipped_context_lengths_over_max_pos: List[int] = field(default_factory=list)
    model_max_position_embeddings: Optional[int] = None


# --------------------------------------------------------------------------- #
# Perplexity at a given char-length window                                    #
# --------------------------------------------------------------------------- #


def _compute_perplexity_at_length(
    *, model, tokenizer, text: str, cache_factory: Callable[[], Any],
    cache_type: str, context_length_chars: int,
) -> PerplexityAtLengthRow:
    """Single-forward perplexity over the first `context_length_chars`
    chars of `text`. Mirrors `track_e_quality_eval.compute_perplexity`
    but exposes the char-window as a knob."""
    import torch
    import torch.nn.functional as F
    chunk = text[:context_length_chars]
    inputs = tokenizer(chunk, return_tensors="pt").to(model.device)
    input_ids = inputs["input_ids"]
    with torch.no_grad():
        out = model(
            input_ids=input_ids, use_cache=True,
            past_key_values=cache_factory(),
        )
    logits = out.logits
    shift_logits = logits[:, :-1, :].contiguous()
    shift_labels = input_ids[:, 1:].contiguous()
    nll = F.cross_entropy(
        shift_logits.view(-1, shift_logits.size(-1)),
        shift_labels.view(-1),
        reduction="mean",
    )
    nll_val = float(nll.item())
    import math
    return PerplexityAtLengthRow(
        cache_type=cache_type,
        context_length_chars=len(chunk),
        context_length_tokens=int(input_ids.shape[1]),
        perplexity=float(math.exp(nll_val)),
        nll_per_token=nll_val,
    )


# --------------------------------------------------------------------------- #
# Needle-in-haystack                                                          #
# --------------------------------------------------------------------------- #


def _run_needle_trial(
    *, model, tokenizer, haystack: str, needle_template: tuple[str, str, str],
    code: str, depth_percent: float, cache_factory: Callable[[], Any],
    cache_type: str, decode_tokens: int, sample_idx: int,
    requested_context_length_chars: int,
) -> NeedleRow:
    """Single needle retrieval trial.

    Construct prompt = haystack-with-needle + question + "Answer:".
    Greedy-decode `decode_tokens` tokens. Mark `correct` if the answer
    code appears in the generated text (substring match — robust to
    tokenizer-level prefix variants like " ABC123" vs "ABC123").

    `requested_context_length_chars` is the upstream-chosen window
    size (e.g., 16384) used as the row's `context_length_chars`. We
    don't record the actual post-insertion length there because the
    composer joins needle rows with perplexity rows on this key —
    they need to share the same value for the same window.
    """
    import time

    import torch
    import torch.nn.functional as F
    needle_text = needle_template[0].format(code=code)
    question = needle_template[1]
    expected = needle_template[2].format(code=code)

    text_with_needle, _ = _insert_needle_at_depth(
        haystack, needle_text, depth_percent,
    )
    prompt = (
        f"{text_with_needle}\n\nQuestion: {question}\nAnswer:"
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_ids = inputs["input_ids"]
    cache = cache_factory()

    # Single forward to prefill, then greedy decode.
    with torch.no_grad():
        out = model(input_ids=input_ids, use_cache=True, past_key_values=cache)
    next_logits = out.logits[0, -1, :]

    def _entropy_nats(logits: "torch.Tensor") -> float:
        # Entropy of the next-token distribution, in nats. Computed in
        # float32 so a float16 logit tensor doesn't bias the sum.
        logp = F.log_softmax(logits.to(torch.float32), dim=-1)
        return float(-(logp.exp() * logp).sum().item())

    generated_ids: List[int] = []
    step_entropies: List[float] = [_entropy_nats(next_logits)]
    decode_t0 = time.perf_counter()
    for _ in range(decode_tokens):
        tok = int(next_logits.argmax().item())
        generated_ids.append(tok)
        with torch.no_grad():
            out = model(
                input_ids=torch.tensor([[tok]], device=model.device),
                use_cache=True, past_key_values=cache,
            )
        next_logits = out.logits[0, -1, :]
        step_entropies.append(_entropy_nats(next_logits))
    decode_seconds = time.perf_counter() - decode_t0

    generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    # Whitespace-tolerant match: the model may emit "AB C 123" instead
    # of "ABC123" if the tokenizer split the code across tokens with
    # interior spaces. Compare on whitespace-stripped strings so a
    # tokenizer-induced split doesn't get scored as a wrong answer.
    correct = (
        expected in generated_text
        or "".join(expected.split()) in "".join(generated_text.split())
    )

    entropy_mean = (
        sum(step_entropies) / len(step_entropies) if step_entropies else 0.0
    )
    entropy_min = min(step_entropies) if step_entropies else 0.0
    fp16_bytes, comp_bytes, comp_ratio = _cache_memory_stats(cache)

    return NeedleRow(
        cache_type=cache_type,
        context_length_chars=requested_context_length_chars,
        context_length_tokens=int(input_ids.shape[1]),
        depth_percent=depth_percent,
        sample_idx=sample_idx,
        answer_code=expected,
        generated_text=generated_text[:200],  # truncate for JSON size
        correct=correct,
        first_stutter_position=_detect_first_stutter(generated_ids),
        repeated_token_rate=_repeated_token_rate(generated_ids),
        decode_entropy_mean=entropy_mean,
        decode_entropy_min=entropy_min,
        decode_entropy_collapsed=bool(entropy_mean < _ENTROPY_COLLAPSE_NATS),
        cache_fp16_bytes=fp16_bytes,
        cache_compressed_bytes=comp_bytes,
        cache_compression_ratio=comp_ratio,
        decode_tokens_per_s=(
            len(generated_ids) / decode_seconds if decode_seconds > 0 else 0.0
        ),
    )


# --------------------------------------------------------------------------- #
# Deltas computation                                                          #
# --------------------------------------------------------------------------- #


def _compute_deltas(summary: LongContextSummary) -> dict:
    """Build the deltas block: per-context-length perplexity ratio,
    per-context-length needle retrieval accuracy delta."""
    out: dict = {"per_context_length": {}}
    # Group perplexity by context_length, take baseline vs int4.
    p_by_ctx: dict = {}
    for r in summary.perplexity_rows:
        p_by_ctx.setdefault(r.context_length_chars, {})[r.cache_type] = r
    for ctx, by_cache in p_by_ctx.items():
        b = by_cache.get("baseline")
        q = by_cache.get("int4-per-channel")
        block: dict = {"context_length_chars": ctx}
        if b is not None and q is not None:
            block["baseline_perplexity"] = b.perplexity
            block["int4_perplexity"] = q.perplexity
            block["perplexity_ratio"] = q.perplexity / max(b.perplexity, 1e-9)
        out["per_context_length"][f"chars={ctx}"] = block

    # Needle accuracy: aggregate over (ctx, cache); compute delta.
    n_by_ctx_cache: dict = {}
    for r in summary.needle_rows:
        key = (r.context_length_chars, r.cache_type)
        n_by_ctx_cache.setdefault(key, []).append(r)
    # Convert to per-ctx baseline-vs-int4 accuracy.
    n_by_ctx: dict = {}
    for (ctx, cache), rows in n_by_ctx_cache.items():
        acc = sum(1 for r in rows if r.correct) / len(rows) if rows else 0.0
        n_by_ctx.setdefault(ctx, {})[cache] = acc
    for ctx, by_cache in n_by_ctx.items():
        block = out["per_context_length"].setdefault(
            f"chars={ctx}", {"context_length_chars": ctx},
        )
        block["baseline_needle_accuracy"] = by_cache.get("baseline")
        block["int4_needle_accuracy"] = by_cache.get("int4-per-channel")
        if (
            by_cache.get("baseline") is not None
            and by_cache.get("int4-per-channel") is not None
        ):
            block["needle_accuracy_delta_pct"] = (
                (by_cache["int4-per-channel"] - by_cache["baseline"]) * 100.0
            )

    # §20.4 diagnostic-sprint aggregates: per-context-length decode
    # stability for the INT4 cache. These are the headline signals the
    # sink-sweep / K-V-ablation / INT5 runs are read on.
    for ctx, by_cache in n_by_ctx_cache.items():
        ctx_chars, cache_label = ctx
        if cache_label != "int4-per-channel":
            continue
        rows = by_cache
        if not rows:
            continue
        block = out["per_context_length"].setdefault(
            f"chars={ctx_chars}", {"context_length_chars": ctx_chars},
        )
        stutters = [
            r.first_stutter_position for r in rows
            if r.first_stutter_position >= 0
        ]
        block["int4_repeated_token_rate_mean"] = (
            sum(r.repeated_token_rate for r in rows) / len(rows)
        )
        block["int4_first_stutter_earliest"] = (
            min(stutters) if stutters else -1
        )
        block["int4_stutter_trial_rate"] = len(stutters) / len(rows)
        block["int4_decode_entropy_mean"] = (
            sum(r.decode_entropy_mean for r in rows) / len(rows)
        )
        block["int4_entropy_collapse_rate"] = (
            sum(1 for r in rows if r.decode_entropy_collapsed) / len(rows)
        )
        block["int4_decode_tokens_per_s_mean"] = (
            sum(r.decode_tokens_per_s for r in rows) / len(rows)
        )
        ratios = [r.cache_compression_ratio for r in rows if r.cache_compression_ratio > 0]
        block["int4_cache_compression_ratio"] = (
            sum(ratios) / len(ratios) if ratios else 0.0
        )
    return out


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="track_e_long_context",
        description=(
            "§20.4 long-context validation: perplexity at 16k/32k/50k + "
            "needle-in-haystack retrieval. Single model load, one JSON."
        ),
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument(
        "--dtype", default="float16",
        choices=["float16", "bfloat16", "float32"],
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--perplexity-text-path", type=Path, default=None,
        help=(
            "Long passage for perplexity AND haystack base text. If "
            "unset, uses the inline HAYSTACK_TEXTS repeated to length."
        ),
    )
    parser.add_argument(
        "--context-lengths", default="16000,32000,50000",
        help=(
            "Comma-separated context-length CHARS (not tokens) for "
            "perplexity + needle cells. 50k chars ≈ 12-15k tokens "
            "depending on tokenizer; size the upper end to your "
            "model's max_position_embeddings."
        ),
    )
    parser.add_argument(
        "--needle-depths", default="0.1,0.5,0.9",
        help=(
            "Comma-separated needle insertion depths as fractions of "
            "the haystack length. 0.1 = early (model can attend to a "
            "lot of subsequent text); 0.5 = middle; 0.9 = late."
        ),
    )
    parser.add_argument(
        "--needle-samples", type=int, default=3,
        help=(
            "Trials per (context_length, depth, cache_type). Each "
            "samples a different random code + needle template; the "
            "headline accuracy is correct / total. >= 3 recommended."
        ),
    )
    parser.add_argument(
        "--needle-decode-tokens", type=int, default=20,
        help=(
            "Tokens to greedy-decode when scoring needle retrieval. "
            "20 is enough for a 6-char alphanumeric code plus padding."
        ),
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--skip-perplexity", action="store_true",
        help="Skip the perplexity sweep, run only needle-in-haystack.",
    )
    parser.add_argument(
        "--skip-needle", action="store_true",
        help="Skip needle-in-haystack, run only the perplexity sweep.",
    )
    # KIVI config (§18.3 ship default).
    parser.add_argument("--k-group-size", type=int, default=32)
    parser.add_argument("--v-group-size", type=int, default=32)
    parser.add_argument("--asymmetric-int4", action="store_true", default=True)
    parser.add_argument("--no-asymmetric-int4", action="store_false",
                        dest="asymmetric_int4")
    parser.add_argument("--bits", type=int, default=4)
    # §20.4.1 adaptive precision: --k-bits / --v-bits override --bits
    # per channel. The headline config is --k-bits 8 --v-bits 4 (K at
    # INT8, V at INT4) — the long-context-safe middle ground between
    # full INT4 (K-channel breaks) and K-FP16. None = use --bits.
    parser.add_argument("--k-bits", type=int, default=None,
                        help="Override bit width for K (default: --bits).")
    parser.add_argument("--v-bits", type=int, default=None,
                        help="Override bit width for V (default: --bits).")
    parser.add_argument("--sink-size", type=int, default=0)
    # §20.4 diagnostic-sprint K/V ablation toggles. Default: quantize
    # both (the §18.3 ship config). --no-quantize-k passes K through at
    # FP16 (V-only INT4); --no-quantize-v passes V through at FP16
    # (K-only INT4). Used to isolate which channel drives the
    # long-context decode degradation.
    parser.add_argument("--no-quantize-k", action="store_false",
                        dest="quantize_k", default=True,
                        help="Pass K through at FP16 (V-only INT4 ablation).")
    parser.add_argument("--no-quantize-v", action="store_false",
                        dest="quantize_v", default=True,
                        help="Pass V through at FP16 (K-only INT4 ablation).")
    # §20.4.1 follow-on: outlier-protected K. When > 0, the top-fraction
    # K channels (by per-channel max-abs) keep their FP16 values and
    # only the rest are INT4 — the path toward ~3× compression *with*
    # K-channel quality. Sweep e.g. 0.005 / 0.01 / 0.02 / 0.04.
    parser.add_argument("--k-protect-fraction", type=float, default=0.0,
                        help="Fraction of top-magnitude K channels kept "
                             "at FP16 (outlier protection). 0 = off.")
    parser.add_argument("--k-protect-static", action="store_true", default=False,
                        help="Freeze the protected K channel set per layer "
                             "from the first (prefill) update instead of "
                             "recomputing it per block.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-version-check", action="store_true",
        help=(
            "Bypass the transformers >= 5.0 prophylactic check. The "
            "harness's INT4PerChannelCache + cache byte counter have "
            "explicit 4.x fallback paths (line 341), and the cache "
            "itself inherits from DynamicCache without using the 5.x "
            "layers[i].keys API. Used for the Phase 6.4 protect-"
            "fraction sweep which runs on venv-vllm (pinned to "
            "transformers 4.48 by vllm 0.7.3). Set only when you know "
            "the specific path you run doesn't hit 5.x-only APIs."
        ),
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    context_lengths = [
        int(s.strip()) for s in args.context_lengths.split(",") if s.strip()
    ]
    if not context_lengths:
        print("--context-lengths must list at least one length", file=sys.stderr)
        return 2
    needle_depths = [
        float(s.strip()) for s in args.needle_depths.split(",") if s.strip()
    ]
    if not args.skip_needle and not needle_depths:
        print("--needle-depths must list at least one depth", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    qe = _import_quality_eval_helpers()
    rng = random.Random(args.seed)

    # ---- Model load ----
    if args.dry_run:
        LOG.info("DRY RUN: building fake tiny model (no HF download)")
        if not args.skip_version_check:
            qe._check_transformers_version()
        model, tokenizer = qe._build_fake_model()
        model_id_for_summary = "fake-tiny-model (DRY-RUN)"
        # Cap dry-run context lengths so the fake model handles them.
        context_lengths = [min(c, 256) for c in context_lengths]
        n_samples = min(args.needle_samples, 2)
        decode_tokens = min(args.needle_decode_tokens, 4)
    else:
        if not args.skip_version_check:
            qe._check_transformers_version()
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        LOG.info("Loading %s (dtype=%s, device=%s)",
                 args.model, args.dtype, args.device)
        torch_dtype = getattr(torch, args.dtype)
        device_map = args.device if args.device != "auto" else "auto"
        tokenizer = AutoTokenizer.from_pretrained(args.model)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token_id = tokenizer.eos_token_id
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch_dtype, device_map=device_map,
        )
        model.eval()
        model_id_for_summary = args.model
        n_samples = args.needle_samples
        decode_tokens = args.needle_decode_tokens

    # ---- Build reference text ----
    if args.perplexity_text_path is not None:
        reference_text = args.perplexity_text_path.read_text()
        LOG.info(
            "Reference text loaded from %s (%d chars)",
            args.perplexity_text_path, len(reference_text),
        )
        if len(reference_text) < max(context_lengths):
            LOG.warning(
                "Reference text only %d chars but max context_length is %d; "
                "padding with HAYSTACK_TEXTS",
                len(reference_text), max(context_lengths),
            )
            reference_text += " " + _build_haystack(
                max(context_lengths) - len(reference_text), rng,
            )
    else:
        LOG.info(
            "No --perplexity-text-path; using inline HAYSTACK_TEXTS for haystack"
        )
        reference_text = _build_haystack(max(context_lengths) + 1000, rng)

    eff_k_bits = args.k_bits if args.k_bits is not None else args.bits
    eff_v_bits = args.v_bits if args.v_bits is not None else args.bits
    int4_config = {
        "quant": "int4-per-channel",
        "k_group_size": args.k_group_size,
        "v_group_size": args.v_group_size,
        "asymmetric": args.asymmetric_int4,
        "bits": args.bits,
        "k_bits": eff_k_bits,
        "v_bits": eff_v_bits,
        "sink_size": args.sink_size,
        "quantize_k": bool(args.quantize_k),
        "quantize_v": bool(args.quantize_v),
        "k_protect_fraction": args.k_protect_fraction,
        "k_protect_static": bool(args.k_protect_static),
        "scheme": (
            f"K={'per-channel INT' + str(eff_k_bits) if args.quantize_k else 'FP16'}"
            + (f" (top {args.k_protect_fraction * 100:g}% channels FP16-protected, "
               f"{'static' if args.k_protect_static else 'dynamic'})"
               if args.k_protect_fraction > 0 else "")
            + ", "
            f"V={'per-token INT' + str(eff_v_bits) if args.quantize_v else 'FP16'}, "
            f"{'asymmetric' if args.asymmetric_int4 else 'symmetric'}, "
            f"k_group={args.k_group_size}, v_group={args.v_group_size}, "
            f"sink={args.sink_size}"
        ),
    }
    summary = LongContextSummary(
        model_id=model_id_for_summary,
        dtype=args.dtype,
        int4_config=int4_config,
        context_lengths=context_lengths,
        needle_depths=needle_depths,
    )

    # H3: estimate token count for the largest requested context-chars
    # window and compare to the model's max_position_embeddings. The
    # char-based context lengths only translate to tokens after the
    # tokenizer runs — but `max_position_embeddings` is in tokens, so
    # we tokenize a probe to convert. Drop over-window cells with a
    # WARNING.
    sample_chars = reference_text[: max(context_lengths)]
    sample_tokens = len(tokenizer(sample_chars)["input_ids"]) if not args.dry_run else max(context_lengths)
    chars_per_token = (
        max(context_lengths) / max(sample_tokens, 1) if sample_tokens > 0 else 1.0
    )
    # For each ctx_chars, estimate the token count from the empirical
    # ratio and check against max_pos.
    estimated_token_lengths = [
        int(c / max(chars_per_token, 1e-6)) for c in context_lengths
    ]
    allowed_tokens, skipped_tokens, max_pos = check_context_window(
        model=model, requested_tokens=estimated_token_lengths,
    )
    allowed_set = set(allowed_tokens)
    new_context_lengths = []
    skipped_context_lengths = []
    for c, tok_est in zip(context_lengths, estimated_token_lengths):
        if tok_est in allowed_set:
            new_context_lengths.append(c)
        else:
            skipped_context_lengths.append(c)
            LOG.warning(
                "Skipping context_length=%d chars (~%d tokens) — exceeds "
                "model.config.max_position_embeddings=%d",
                c, tok_est, max_pos,
            )
    context_lengths = new_context_lengths
    summary.context_lengths = context_lengths
    summary.skipped_context_lengths_over_max_pos = skipped_context_lengths
    summary.model_max_position_embeddings = max_pos

    baseline_factory = qe._baseline_cache_factory()
    int4_factory = qe._int4_per_channel_cache_factory(
        sink_size=args.sink_size,
        k_group_size=args.k_group_size,
        v_group_size=args.v_group_size,
        asymmetric=args.asymmetric_int4,
        bits=args.bits,
        k_bits=args.k_bits,
        v_bits=args.v_bits,
        quantize_k=args.quantize_k,
        quantize_v=args.quantize_v,
        k_protect_fraction=args.k_protect_fraction,
        k_protect_static=args.k_protect_static,
    )

    # H1: write the partial JSON before any trial so the model-config
    # metadata + skipped-cells info survives a crash before the first
    # measurement.
    save_partial_json(summary, args.output)

    # ---- Perplexity sweep ----
    if not args.skip_perplexity:
        for ctx_chars in context_lengths:
            for cache_label, factory in (
                ("baseline", baseline_factory),
                ("int4-per-channel", int4_factory),
            ):
                LOG.info("Perplexity: ctx=%d cache=%s", ctx_chars, cache_label)
                row = _compute_perplexity_at_length(
                    model=model, tokenizer=tokenizer, text=reference_text,
                    cache_factory=factory, cache_type=cache_label,
                    context_length_chars=ctx_chars,
                )
                summary.perplexity_rows.append(row)
                LOG.info(
                    "  ctx=%d (%d tok) cache=%s ppl=%.4f",
                    ctx_chars, row.context_length_tokens, cache_label,
                    row.perplexity,
                )
                # H2: free GPU memory between trials so the caching
                # allocator doesn't drift toward OOM across the sweep.
                cleanup_cuda_after_trial()
                # H1: persist after each perplexity measurement.
                summary.deltas = _compute_deltas(summary)
                save_partial_json(summary, args.output)

    # ---- Needle-in-haystack ----
    if not args.skip_needle:
        for ctx_chars in context_lengths:
            # Build a haystack of this length once per context (reused
            # across depth × sample × cache to keep cells comparable).
            haystack_base = reference_text[:ctx_chars]
            for depth in needle_depths:
                for sample_idx in range(n_samples):
                    code = _generate_code(rng)
                    template = NEEDLE_TEMPLATES[
                        sample_idx % len(NEEDLE_TEMPLATES)
                    ]
                    for cache_label, factory in (
                        ("baseline", baseline_factory),
                        ("int4-per-channel", int4_factory),
                    ):
                        LOG.info(
                            "Needle: ctx=%d depth=%.2f sample=%d cache=%s code=%s",
                            ctx_chars, depth, sample_idx, cache_label, code,
                        )
                        row = _run_needle_trial(
                            model=model, tokenizer=tokenizer,
                            haystack=haystack_base, needle_template=template,
                            code=code, depth_percent=depth,
                            cache_factory=factory, cache_type=cache_label,
                            decode_tokens=decode_tokens, sample_idx=sample_idx,
                            requested_context_length_chars=ctx_chars,
                        )
                        summary.needle_rows.append(row)
                        LOG.info(
                            "  correct=%s generated=%r",
                            row.correct, row.generated_text[:60],
                        )
                        # H2: free GPU memory between trials. Each
                        # needle trial holds a fresh cache of up to
                        # 16 GB at 32k FP16 — critical.
                        cleanup_cuda_after_trial()
                        # H1: persist after each trial.
                        summary.deltas = _compute_deltas(summary)
                        save_partial_json(summary, args.output)

    summary.deltas = _compute_deltas(summary)
    save_partial_json(summary, args.output)
    print(f"Wrote {args.output}")

    # Reader-friendly stdout summary.
    print()
    print("=" * 72)
    print(f"§20.4 long-context — {model_id_for_summary}")
    print("=" * 72)
    for ctx in context_lengths:
        block = summary.deltas.get("per_context_length", {}).get(
            f"chars={ctx}", {},
        )
        ppl_ratio = block.get("perplexity_ratio")
        needle_delta = block.get("needle_accuracy_delta_pct")
        parts = [f"ctx={ctx:>6}"]
        if ppl_ratio is not None:
            parts.append(f"ppl_ratio={ppl_ratio:.4f}")
        b_n = block.get("baseline_needle_accuracy")
        i_n = block.get("int4_needle_accuracy")
        if b_n is not None and i_n is not None:
            parts.append(
                f"needle: baseline={b_n*100:.0f}% int4={i_n*100:.0f}% "
                f"Δ={needle_delta:+.0f}%"
            )
        print("  " + "  ".join(parts))
        # §20.4 diagnostic-sprint decode-stability line.
        stutter = block.get("int4_first_stutter_earliest")
        rep = block.get("int4_repeated_token_rate_mean")
        ent = block.get("int4_decode_entropy_mean")
        coll = block.get("int4_entropy_collapse_rate")
        if stutter is not None:
            print(
                "    int4 decode: "
                f"first_stutter={'none' if stutter < 0 else stutter}  "
                f"repeat_rate={rep:.2f}  entropy={ent:.2f}nats  "
                f"collapse_rate={coll*100:.0f}%"
            )
    print()
    print(f"Full per-cell detail in {args.output}.")
    print(
        "Run `python -m ctm_bench.scripts.compose_long_context_summary "
        f"--input {args.output}` to compose the §20.4 markdown table."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
