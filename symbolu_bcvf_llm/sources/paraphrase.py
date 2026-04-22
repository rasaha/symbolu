"""§4.5 Paraphrased-prompt construction.

Produces two "fallible" sources per §1.4.2 / §1.4.3 by asking the
same model to rewrite the original prompt at temperature 0 with a
fixed instruction and a rewrite-seed `{α, β}` threading the
instruction text. §1.4 locked temperature 0 so the rewrite itself
is deterministic given the model, original prompt, and seed.

The function is a thin wrapper around `model.generate`; it does
NOT stream, does NOT sample, and does NOT use the KV cache beyond
the single-call generate() invocation. Its output is a string
(the paraphrased prompt) that the caller passes into a fresh
HuggingFaceSource.

**Status.** Scaffold only — same caveat as §4.4 HuggingFaceSource.
Not executed against a real model in this environment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    from transformers import PreTrainedModel, PreTrainedTokenizerBase


DEFAULT_REWRITE_INSTRUCTION = (
    "Rewrite the following question in different words while preserving "
    "its exact meaning. Rewrite #{seed}. Do not answer it.\n\n"
    "Question: {prompt}\n\nRewrite:"
)


def make_paraphrased_prompt(
    model: "PreTrainedModel",
    tokenizer: "PreTrainedTokenizerBase",
    original_prompt: str,
    rewrite_seed: int,
    max_new_tokens: int = 128,
    instruction_template: Optional[str] = None,
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
        max_new_tokens: Generation budget for the rewrite.
        instruction_template: Optional override; must contain
            `{seed}` and `{prompt}` format fields.

    Returns:
        The paraphrased prompt as a plain string.
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
    instruction = template.format(seed=rewrite_seed, prompt=original_prompt)
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
    rewrite = tokenizer.decode(rewrite_ids, skip_special_tokens=True).strip()
    return rewrite
