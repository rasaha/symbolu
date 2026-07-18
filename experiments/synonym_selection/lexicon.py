"""Loader for varna_lens/lexicon_wordformation.json (the CURATED word-formation table).

Reads ONLY the `word_formation_reading` (binding/in-combination) field — NOT the engine's
`binding_state`, which differs from this curated table on ca/ra/va/sa/ha/kṣa and the vowels.
This module loads the table; it computes no fit and makes no semantic claim.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_LEXICON = (Path(__file__).resolve().parents[2] /
                   "varna_lens" / "lexicon_wordformation.json")


def load_readings(path=DEFAULT_LEXICON):
    """Return (cons_readings, vow_readings, cons_vocab).

    cons_readings : consonant key -> word_formation_reading english (the binding pole)
    vow_readings  : vowel key     -> word_formation_reading english
    cons_vocab    : sorted list of DISTINCT consonant reading labels (the confirmatory space)
    """
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    cons = {k: v["word_formation_reading"]["english"] for k, v in d["consonants"].items()}
    vow = {k: v["word_formation_reading"]["english"] for k, v in d.get("vowels", {}).items()}
    vocab = sorted(set(cons.values()))
    return cons, vow, vocab


def vocab_index(vocab) -> dict[str, int]:
    return {label: i for i, label in enumerate(vocab)}
