"""The governed output-format wrapper for the BBH seven-object logical-deduction pilot.

The wrapper appends **one** instruction — the answer format the ``bbh-ld7.v2`` scorer
reads — to an upstream item, byte for byte unchanged. It asks for no reasoning, forbids
none, and requests, stores and exposes no chain of thought: the workflows decide how
they reason, and only the final response's last ``ANSWER:`` line is ever scored.

The wrapper never sees an expected answer. Wrapping is **not idempotent by design**:
re-wrapping is refused rather than silently appending a second instruction, because a
second instruction would change the committed case text and therefore the case digest.
"""

from __future__ import annotations

WRAPPER_ID = "bbh_answer_format_wrapper.v1"

ANSWER_INSTRUCTION = (
    "End your response with a single final line of the form 'ANSWER: X', where X is "
    "exactly one of the option letters A, B, C, D, E, F or G. Only the last line "
    "beginning with 'ANSWER:' is read."
)

_SEPARATOR = "\n\n"


class PromptWrapError(ValueError):
    """The item cannot be wrapped as the governed rule requires."""


def is_wrapped(text: str) -> bool:
    """True when the governed instruction is already present anywhere in the text."""
    if not isinstance(text, str):
        raise PromptWrapError("text must be a string")
    return ANSWER_INSTRUCTION in text


def wrap_query(item_text: str) -> str:
    """Return the upstream item followed by the governed instruction.

    The upstream text is preserved exactly: no stripping, no normalization, no
    re-encoding. Refuses an empty item and refuses an already-wrapped one."""
    if not isinstance(item_text, str):
        raise PromptWrapError("item_text must be a string")
    if not item_text.strip():
        raise PromptWrapError("item_text must not be blank")
    if is_wrapped(item_text):
        raise PromptWrapError("item_text already carries the governed answer-format instruction")
    return item_text + _SEPARATOR + ANSWER_INSTRUCTION


__all__ = ["WRAPPER_ID", "ANSWER_INSTRUCTION", "PromptWrapError", "is_wrapped", "wrap_query"]
