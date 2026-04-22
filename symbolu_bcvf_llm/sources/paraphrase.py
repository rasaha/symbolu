"""§4.5 Paraphrased-prompt construction.

Produces two "fallible" sources per §1.4.2 / §1.4.3 by asking the
same model to rewrite the original prompt at temperature 0 with a
fixed instruction and a rewrite-seed `{α, β}` threading the
instruction text. §1.4 locked temperature 0 so the rewrite itself
is deterministic given the model, original prompt, and seed.

The V1 version of this module used a minimal rewrite instruction
that Mistral-7B-Instruct-v0.3 (and likely other instruction-tuned
models) interpreted as "continue generating Q/Rewrite pairs." That
produced corrupted paraphrases with template leakage, inline
answers, and question drift — see §10.V1.6 of the design doc for
the specific samples that surfaced the bug.

This version (post-§10.V1.6) adds:
  1. A stronger few-shot template that directs the model to output
     ONLY the rewrite on a single line.
  2. Post-processing (`_clean_rewrite`) that truncates at the first
     sign of template leakage ("\\nQuestion:", "\\nAnswer:", "(Answer:",
     etc.) and strips meta-commentary.
  3. Validation (`_is_valid_rewrite`) that rejects empty, too-short,
     or answer-leaked output.
  4. A fallback to the original prompt when validation fails, so
     downstream BCVF sees a clean (even if duplicated) prompt rather
     than corrupted text.

The `clean_output` kwarg on `make_paraphrased_prompt` defaults to
True. Set False to reproduce the V1 (pre-fix) behaviour for
comparison runs.

**Status.** The cleaning logic is tested in pure Python against
fabricated bad-rewrite strings; the live `model.generate` path is
still torch-gated and not executed in this test environment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    from transformers import PreTrainedModel, PreTrainedTokenizerBase


# Per-seed style directives — indexed by ``(seed - 1) mod len``.
#
# At temperature 0, Mistral-7B-Instruct-v0.3 (and likely other
# instruction-tuned models) was observed to produce IDENTICAL rewrites
# for seed 1 and seed 2 when the only seed-dependent difference was
# a numeric token (e.g. "Rewrite #1" vs "Rewrite #2"). The model
# essentially ignored the number and converged to the same argmax.
#
# Fix: each seed injects a genuinely different STYLE constraint into
# the instruction text, so the argmax rewrite is different for each
# seed. The directives are mild and meaning-preserving — they guide
# phrasing, not content — so every variant is still a valid
# paraphrase of the same question.
#
# §1.10's rewrite_seed_pair maps evaluation_seed N → (2N-1, 2N), so
# for --seed 1 this gives seeds (1, 2) which hit directives 0 and 1
# — two distinct styles. For --seed 2 → (3, 4), hitting directives
# 2 and 3. Provides 4-way diversity before the index wraps.
_SEED_STYLE_DIRECTIVES = (
    "Use concise, everyday phrasing.",
    "Use more formal, precise phrasing.",
    "Begin the question with a different word than the original.",
    "Rephrase using the passive voice where natural.",
)


def _style_for_seed(seed: int) -> str:
    """Look up the style directive for a rewrite seed."""
    idx = (int(seed) - 1) % len(_SEED_STYLE_DIRECTIVES)
    return _SEED_STYLE_DIRECTIVES[idx]


# V2-compatible template: few-shot, directive, single-line target.
# `{style}` varies per seed via `_style_for_seed` — this is what makes
# seed-1 and seed-2 produce meaningfully different rewrites at T=0.
DEFAULT_REWRITE_INSTRUCTION = (
    "Your task is to rewrite a question in different words while "
    "preserving its exact meaning.\n"
    "\n"
    "Style guidance for this rewrite: {style}\n"
    "\n"
    "Rules:\n"
    "- Output ONLY the rewritten question on a single line.\n"
    "- Do NOT answer the question.\n"
    "- Do NOT provide explanations, commentary, or additional examples.\n"
    "- Preserve the exact factual meaning and intent.\n"
    "\n"
    "Examples:\n"
    "Question: What is the capital of France?\n"
    "Rewrite: Which city serves as the capital of France?\n"
    "\n"
    "Question: How tall is Mount Everest?\n"
    "Rewrite: What is the height of Mount Everest?\n"
    "\n"
    "Question: {prompt}\n"
    "Rewrite:"
)


# Legacy V1 template, preserved for A/B comparison runs.
V1_REWRITE_INSTRUCTION = (
    "Rewrite the following question in different words while preserving "
    "its exact meaning. Rewrite #{seed}. Do not answer it.\n\n"
    "Question: {prompt}\n\nRewrite:"
)


# Markers that indicate the model stopped paraphrasing and started
# generating noise (template continuation, inline answers, commentary).
_LEAK_MARKERS = (
    "\nQuestion:",
    "\n\nQuestion:",
    "\nQ:",
    "\n\nQ:",
    "\nRewrite:",
    "\n\nRewrite:",
    "\nExample",
    "\n\nExample",
    "\nNote:",
    "\n\nNote:",
    "\nA:",
    "\n\nA:",
    "\nAnswer:",
    "\n\nAnswer:",
    "\n(Answer:",
    "\n\n(Answer:",
)


def _clean_rewrite(raw: str) -> str:
    """Extract the rewrite text, stripping template-leaked noise.

    Mistral (and other instruction-tuned models) often over-generate
    when given a format example — producing extra Q/A pairs, inline
    answers, or meta-commentary past the first rewrite. This function
    truncates at the first sign of template leakage.

    Pure string processing; no model involvement.
    """
    text = raw.strip()
    if not text:
        return ""
    # Truncate at the earliest leak marker anywhere in the text.
    earliest = len(text)
    for marker in _LEAK_MARKERS:
        idx = text.find(marker)
        if idx >= 0 and idx < earliest:
            earliest = idx
    text = text[:earliest].strip()
    # Strip trailing inline "(Answer: ...)" even on the same line.
    if "(Answer:" in text:
        text = text.split("(Answer:")[0].strip()
    if "Answer:" in text.split("\n")[0]:
        first_line = text.split("\n")[0]
        before_answer = first_line.split("Answer:")[0].strip()
        text = before_answer
    # Collapse to first paragraph so any remaining multi-line
    # commentary is dropped.
    text = text.split("\n\n")[0].strip()
    return text


def _is_valid_rewrite(
    text: str, original_prompt: str, min_chars: int = 10
) -> bool:
    """Heuristic validity check.

    A valid rewrite is:
      - non-empty after cleaning,
      - at least `min_chars` characters (catches truncation / single-word),
      - doesn't contain obvious answer-leak markers.

    Semantic equivalence to the original is NOT checked — that requires
    the model (or a separate verifier) and is out of scope for V1.
    """
    if not text:
        return False
    if len(text) < min_chars:
        return False
    low = text.lower()
    if "answer:" in low or "(answer" in low:
        return False
    return True


def make_paraphrased_prompt(
    model: "PreTrainedModel",
    tokenizer: "PreTrainedTokenizerBase",
    original_prompt: str,
    rewrite_seed: int,
    max_new_tokens: int = 64,
    instruction_template: Optional[str] = None,
    clean_output: bool = True,
    min_chars: int = 10,
) -> str:
    """Return a paraphrased version of `original_prompt` for the given seed.

    Args:
        model: A causal LM with `.generate` available.
        tokenizer: Matching tokenizer.
        original_prompt: The prompt to paraphrase.
        rewrite_seed: Integer thread into the instruction (produces
            deterministically different rewrites for different seeds
            even at temperature 0, because the literal instruction
            text differs).
        max_new_tokens: Generation budget for the rewrite. Default
            reduced from V1's 128 to 64 — one-line rewrites don't need
            more, and a tighter budget reduces template-leak exposure.
        instruction_template: Optional override; must contain `{seed}`
            and `{prompt}` format fields. Pass `V1_REWRITE_INSTRUCTION`
            to reproduce the V1 (pre-fix) behavior.
        clean_output: If True (default), post-process the generated text
            to strip template leakage + validate; fall back to
            `original_prompt` if the result is invalid. Set False to
            return the raw decoded text without post-processing.
        min_chars: Minimum rewrite length passed to validation.

    Returns:
        The paraphrased prompt as a plain string. If `clean_output=True`
        and the raw rewrite is invalid, returns `original_prompt` as
        fallback (makes BCVF gracefully degrade toward conventional
        blend rather than feeding the kernel corrupted text).
    """
    try:
        import torch  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "make_paraphrased_prompt requires `torch` and `transformers`. "
            "For tests, construct paraphrased prompts manually and use "
            "MockSource."
        ) from exc

    import torch

    template = instruction_template or DEFAULT_REWRITE_INSTRUCTION
    # Pass all possible placeholders; str.format silently ignores unused
    # ones, so V1_REWRITE_INSTRUCTION (which uses only {seed} and {prompt})
    # continues to work unchanged.
    instruction = template.format(
        seed=rewrite_seed,
        prompt=original_prompt,
        style=_style_for_seed(rewrite_seed),
    )
    inputs = tokenizer(instruction, return_tensors="pt").to(model.device)

    # Explicit pad_token_id suppresses the "Setting pad_token_id to
    # eos_token_id for open-end generation" warning that otherwise
    # fires on every generate call in the paraphrase loop.
    pad_id = getattr(tokenizer, "pad_token_id", None)
    if pad_id is None:
        pad_id = getattr(tokenizer, "eos_token_id", None)

    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            top_p=1.0,
            pad_token_id=pad_id,
        )
    # Strip the instruction prefix; keep the rewrite only.
    prompt_len = inputs["input_ids"].shape[1]
    rewrite_ids = output_ids[0, prompt_len:]
    raw = tokenizer.decode(rewrite_ids, skip_special_tokens=True)

    if not clean_output:
        return raw.strip()

    cleaned = _clean_rewrite(raw)
    if not _is_valid_rewrite(cleaned, original_prompt, min_chars=min_chars):
        # Fall back to the original prompt. Downstream BCVF will
        # see M sources that agree on this question (degenerate to
        # conventional blend), which is a safer failure mode than
        # feeding corrupted paraphrased text.
        return original_prompt
    return cleaned
