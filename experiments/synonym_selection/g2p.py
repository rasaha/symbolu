"""Offline g2p → varṇa keys for the synonym-selection pilot (scaffolding).

Uses a LOCAL CMUdict file (no nltk download) + the FROZEN ARPABET→varṇa map copied
verbatim from varna_lens/varna_lens.py (the `_ARPA_C` / `_ARPA_V` tables, whose
Indian-English dialect rule was "set before any outcome was seen"). We copy the map
rather than import the engine, because the engine also loads the OLD lexicon
(lexicon_authoritative.json) and pulls in nltk — neither of which this pilot uses.

This module performs NO fit and makes NO semantic claim. It only tokenizes a word's
SOUND (g2p) into varṇa keys.
"""
from __future__ import annotations

import re
from pathlib import Path

# --- FROZEN ARPABET→varṇa map (verbatim from varna_lens/varna_lens.py, _ARPA_C/_ARPA_V) ---
# Dialect rule (frozen): English alveolar stops/flap T D N DX → retroflex Ṭa/Ḍa/Ṇa;
# dental fricatives TH/DH (/θ/,/ð/) → dental ta/da. Applied uniformly, set before any outcome.
ARPA_C = {"P": "pa", "B": "ba", "T": "tta", "D": "dda", "K": "ka", "G": "ga", "M": "ma", "N": "nna",
          "NG": "nga", "F": "pha", "V": "va", "TH": "ta", "DH": "da", "S": "sa", "Z": "sa",
          "SH": "sha", "ZH": "sha", "CH": "ca", "JH": "ja", "HH": "ha", "R": "ra", "L": "la",
          "W": "va", "Y": "ya", "DX": "dda"}
ARPA_V = {"AA": "aa", "AE": "a", "AH": "a", "AO": "o", "AW": "au", "AY": "ai", "EH": "e", "ER": "a",
          "EY": "e", "IH": "i", "IY": "ii", "OW": "o", "OY": "o", "UH": "u", "UW": "uu", "AX": "a"}

_STRESS = re.compile(r"\d+$")


def parse_cmudict(path) -> dict[str, list[str]]:
    """word -> ARPABET phones (stress stripped); first pronunciation only. Offline, no nltk."""
    out: dict[str, list[str]] = {}
    for line in Path(path).read_text(encoding="latin-1").splitlines():
        line = line.strip()
        if not line or line.startswith(";;;"):
            continue
        parts = line.split()
        word = parts[0].lower()
        if word.endswith(")"):                       # variant entry like "word(2)"
            continue
        phones = [_STRESS.sub("", p) for p in parts[1:]]
        if phones:
            out.setdefault(word, phones)
    return out


def arpabet_to_varnas(phones) -> tuple[list[tuple[str, str]], list[str]]:
    """ARPABET phone list -> [(type,key)], warnings.  type ∈ {'C','V'} via the frozen map."""
    out, warn = [], []
    for ph in phones:
        base = "".join(c for c in ph if c.isalpha()).upper()
        if base in ARPA_V:
            out.append(("V", ARPA_V[base]))
        elif base in ARPA_C:
            out.append(("C", ARPA_C[base]))
        else:
            warn.append(f"unmapped ARPAbet {ph!r}")
    return out, warn


def g2p_word(word: str, cmudict: dict[str, list[str]]) -> tuple[list[tuple[str, str]], list[str]]:
    """Word -> varṇa-key sequence via local CMUdict + frozen map. Sound only (no spelling)."""
    arpa = cmudict.get(word.lower())
    if not arpa:
        return [], [f"'{word}' not in cmudict"]
    return arpabet_to_varnas(arpa)
