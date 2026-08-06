"""Fixed reversible lexical tokenizer with ASCII-character fallback."""
from __future__ import annotations

from collections.abc import Iterable
import re

from .config import (
    ASCII_VOCAB_SIZE,
    BOS_ID,
    EOS_ID,
    FROZEN_LEXEMES,
    LEXEME_BASE_ID,
    PAD_ID,
    VOCAB_SIZE,
)

_CHUNK_RE = re.compile(r"[A-Za-z_]+|\d+|\s+|.", flags=re.DOTALL)
_LEXEME_TO_ID = {text: LEXEME_BASE_ID + index for index, text in enumerate(FROZEN_LEXEMES)}
_ID_TO_LEXEME = {token_id: text for text, token_id in _LEXEME_TO_ID.items()}


class LexicalTokenizer:
    """Tokenize frozen protocol lexemes atomically and all other ASCII as characters.

    The mapping is fixed at import time, data-independent, and exactly reversible.
    Inputs outside 7-bit ASCII are rejected rather than silently normalized.
    """

    vocab_size = VOCAB_SIZE
    pad_id = PAD_ID
    bos_id = BOS_ID
    eos_id = EOS_ID

    def encode(self, text: str, *, add_bos: bool = False, add_eos: bool = False) -> list[int]:
        if not isinstance(text, str):
            raise TypeError("text must be str")
        try:
            text.encode("ascii", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("tokenizer accepts only 7-bit ASCII") from exc
        tokens: list[int] = []
        for chunk in _CHUNK_RE.findall(text):
            lexeme_id = _LEXEME_TO_ID.get(chunk)
            if lexeme_id is not None:
                tokens.append(lexeme_id)
            else:
                tokens.extend(ord(char) for char in chunk)
        if add_bos:
            tokens.insert(0, self.bos_id)
        if add_eos:
            tokens.append(self.eos_id)
        return tokens

    def decode(self, ids: Iterable[int], *, skip_special: bool = True) -> str:
        parts: list[str] = []
        for token_id in ids:
            token = int(token_id)
            if token in {self.pad_id, self.bos_id, self.eos_id}:
                if skip_special:
                    continue
                raise ValueError("special tokens are not text")
            if 0 <= token < ASCII_VOCAB_SIZE:
                parts.append(chr(token))
            elif token in _ID_TO_LEXEME:
                parts.append(_ID_TO_LEXEME[token])
            else:
                raise ValueError(f"unknown token ID: {token}")
        return "".join(parts)
