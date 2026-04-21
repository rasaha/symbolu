"""§4 Source Framework — public API.

Exports the `Source` protocol plus in-process implementations.

`HuggingFaceSource` and `make_paraphrased_prompt` import torch /
transformers lazily inside their constructors; simply importing
this package does not pull an ML stack (§4.4 docstring).
"""

from __future__ import annotations

from .base import Source, stable_softmax, truncating_valid_mask
from .huggingface import HuggingFaceSource
from .mock import MockSource
from .paraphrase import DEFAULT_REWRITE_INSTRUCTION, make_paraphrased_prompt

__all__ = [
    "DEFAULT_REWRITE_INSTRUCTION",
    "HuggingFaceSource",
    "MockSource",
    "Source",
    "make_paraphrased_prompt",
    "stable_softmax",
    "truncating_valid_mask",
]
