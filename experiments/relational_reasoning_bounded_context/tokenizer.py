"""BTRR-specific frozen lexical tokenizer (Amendment 001/002).

Same deterministic longest-match algorithm as the single-hop tokenizer, but an independent frozen
lexeme inventory. The single-hop tokenizer (experiments/single_hop_typed_vs_prose/tokenizer.py) is NOT
imported or modified. IDs 0..127 literal ASCII, 128/129/130 PAD/BOS/EOS, 131..210 the 80 frozen BTRR
lexemes (id = 131 + list index). vocab_size = 211. Lossless and reversible; unknown substrings fall back
to one ASCII character (opaque IDs stay char-level).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

ASCII_SIZE: Final[int] = 128
PAD_ID: Final[int] = 128
BOS_ID: Final[int] = 129
EOS_ID: Final[int] = 130
LEXEME_START: Final[int] = 131

# Frozen 80-lexeme inventory, in ID order (id = LEXEME_START + index). Identical to Amendment 001/002.
LEXEMES: Final[tuple[str, ...]] = (
    "\n<OUTPUT>\n", "CTX ", "QRY ", "ENT ", "REL ", "EVT ", "POL ", "EVD ", " COND ", " OUT ",
    "resolve_attribute", "resolve_path_target", "latest_event_value", "path_then_latest", "apply_policy",
    "PATH_GIVEN", "PATH_DISCOVERY", "NOT_APPLICABLE",
    "invoice", "contract", "vendor", "employee", "department",
    "governed_by", "approved_vendor", "assigned_to", "member_of", "belongs_to_contract", "supplies",
    "risk", "status", "tier", "amount", "region", "value",
    "EQ", "GT", "GE", "LT", "LE", "NE",
    "LOW", "MEDIUM", "HIGH", "CRITICAL", "ACTIVE", "EXPIRED", "PENDING",
    "supports", "contradicts",
    "approval_requirement", "target_attribute", "latest_state",
    "vendor_risk", "contract_state", "assignment",
    "VP_APPROVAL_REQUIRED", "DIRECTOR_APPROVAL_REQUIRED", "AUTO_APPROVED", "MANUAL_REVIEW",
    "REJECTED", "ESCALATE_RISK", "HOLD_PENDING_EVIDENCE", "NO_ACTION",
    "Entity:", "Event:", "Policy:", "Relation:",
    '{"answer":"', '{"answer":null', '","reasoning_path":[', '],"evidence_ids":[',
    '],"status":"', '"}', '","',
    '"SUPPORTED"', '"INSUFFICIENT_EVIDENCE"', '"POLICY_NOT_APPLICABLE"', '"INVALID_RELATION_PATH"',
    "null",
)

if len(LEXEMES) != 80 or len(set(LEXEMES)) != 80:
    raise RuntimeError("the frozen BTRR tokenizer requires exactly 80 unique lexemes")

VOCAB_SIZE: Final[int] = LEXEME_START + len(LEXEMES)  # 211
assert VOCAB_SIZE == 211


@dataclass(frozen=True)
class BTRRTokenizer:
    """Lossless BTRR tokenizer with no learned or corpus-derived state."""

    pad_id: int = PAD_ID
    bos_id: int = BOS_ID
    eos_id: int = EOS_ID

    def __post_init__(self) -> None:
        # longest-match ordering (encoding only); ID assignment stays list order
        object.__setattr__(
            self, "_ordered",
            tuple(sorted(enumerate(LEXEMES), key=lambda item: (-len(item[1]), item[0]))),
        )

    @property
    def vocab_size(self) -> int:
        return VOCAB_SIZE

    def encode(self, text: str, *, add_bos: bool = False, add_eos: bool = False) -> list[int]:
        try:
            text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("model-visible text must be 7-bit ASCII") from exc
        ids: list[int] = [self.bos_id] if add_bos else []
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
        if add_eos:
            ids.append(self.eos_id)
        return ids

    def decode(self, ids: Iterable[int]) -> str:
        parts: list[str] = []
        for token_id in ids:
            if token_id in (self.pad_id, self.bos_id, self.eos_id):
                continue
            if 0 <= token_id < ASCII_SIZE:
                parts.append(chr(token_id))
            elif LEXEME_START <= token_id < VOCAB_SIZE:
                parts.append(LEXEMES[token_id - LEXEME_START])
            else:
                raise ValueError(f"token ID outside frozen BTRR vocabulary: {token_id}")
        return "".join(parts)

    def round_trip(self, text: str) -> str:
        return self.decode(self.encode(text))

    def count(self, text: str, *, add_bos: bool = True, add_eos: bool = False) -> int:
        return len(self.encode(text, add_bos=add_bos, add_eos=add_eos))
