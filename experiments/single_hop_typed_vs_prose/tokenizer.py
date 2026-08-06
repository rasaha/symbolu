"""Fixed, reversible, data-independent lexical tokenizer.

IDs 0..127 are literal ASCII characters. IDs 128..130 are PAD/BOS/EOS.
IDs 131..199 are immutable protocol lexemes. Encoding uses deterministic
longest-match lexeme recognition and falls back to one ASCII character.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

ASCII_SIZE: Final[int] = 128
PAD_ID: Final[int] = 128
BOS_ID: Final[int] = 129
EOS_ID: Final[int] = 130
LEXEME_START: Final[int] = 131

LEXEMES: Final[tuple[str, ...]] = (
    "\n<OUTPUT>\n",
    "Within tenant ",
    ", the following records are authorized.",
    "The question concerns ",
    " is a ",
    " with ",
    " is associated with ",
    " through the relation ",
    "Evidence reference ",
    " supports the relation between ",
    " contradicts the relation between ",
    " and ",
    " belongs to a different tenant and is not authorized here.",
    "No relation of type ",
    " is recorded for ",
    "no listed attributes",
    '"tenant_id":',
    '"query":',
    '"entities":',
    '"relations":',
    '"evidence":',
    '"operation":',
    '"entity_type":',
    '"entity_id":',
    '"display_name":',
    '"attributes":',
    '"relation_type":',
    '"source_entity_type":',
    '"source_entity_id":',
    '"target_entity_type":',
    '"target_entity_id":',
    '"evidence_ref":',
    '"supports_relation":',
    '"stance":',
    '"admissible":',
    '"status":',
    '"selected_entity_id":',
    '"selected_relation_type":',
    '"relation_supported":',
    '"evidence_refs":',
    '"reason_code":',
    '"ANSWERED"',
    '"INSUFFICIENT_EVIDENCE"',
    '"supports"',
    '"contradicts"',
    "true",
    "false",
    "null",
    '"select_entity"',
    '"select_relation_target"',
    '"validate_relation"',
    '"select_evidence"',
    '"invoice"',
    '"contract"',
    '"vendor"',
    '"employee"',
    '"department"',
    '"belongs_to_contract"',
    '"approved_vendor"',
    '"assigned_to"',
    '"member_of"',
    '"MATCH_FOUND"',
    '"RELATION_SUPPORTED"',
    '"EVIDENCE_FOUND"',
    '"NO_AUTHORIZED_RELATION"',
    '"RELATION_UNSUPPORTED"',
    '"TENANT_BLOCKED"',
    '"CONFLICT"',
    '"IDENTITY_MATCH"',
)

if len(LEXEMES) != 69 or len(set(LEXEMES)) != 69:
    raise RuntimeError("the frozen tokenizer requires exactly 69 unique lexemes")


@dataclass(frozen=True)
class LexicalTokenizer:
    """Lossless tokenizer with no learned or corpus-derived state."""

    pad_id: int = PAD_ID
    bos_id: int = BOS_ID
    eos_id: int = EOS_ID

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_ordered",
            tuple(sorted(enumerate(LEXEMES), key=lambda item: (-len(item[1]), item[0]))),
        )

    @property
    def vocab_size(self) -> int:
        return 200

    def encode(self, text: str) -> list[int]:
        try:
            text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("model-visible text must be ASCII") from exc
        ids: list[int] = []
        cursor = 0
        while cursor < len(text):
            match: tuple[int, str] | None = None
            for index, lexeme in self._ordered:
                if text.startswith(lexeme, cursor):
                    match = (index, lexeme)
                    break
            if match is None:
                ids.append(ord(text[cursor]))
                cursor += 1
            else:
                index, lexeme = match
                ids.append(LEXEME_START + index)
                cursor += len(lexeme)
        return ids

    def decode(self, ids: Iterable[int], *, skip_special: bool = False) -> str:
        parts: list[str] = []
        for token_id in ids:
            if 0 <= token_id < ASCII_SIZE:
                parts.append(chr(token_id))
            elif LEXEME_START <= token_id < self.vocab_size:
                parts.append(LEXEMES[token_id - LEXEME_START])
            elif token_id in (self.pad_id, self.bos_id, self.eos_id):
                if not skip_special:
                    raise ValueError("special tokens have no textual decoding")
            else:
                raise ValueError(f"token ID outside frozen vocabulary: {token_id}")
        return "".join(parts)

    def round_trip(self, text: str) -> str:
        return self.decode(self.encode(text))
