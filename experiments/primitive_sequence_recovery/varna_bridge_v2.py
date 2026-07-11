"""Bridge v2 = v1 phoneme->varṇa mapping + retroflex-cluster context rule (Phase 1).

Recovers the retroflex series the flat v1 bridge misses. English /t/,/d/ before /r/ are phonetically
retroflex-flavoured (drum, train), so:
    t -> ṭa (tta),  d -> ḍa (dda)   WHEN immediately followed by /r/;   the /r/ still emits 'ra' (Route B).
Everything else is byte-identical to v1. Phase 1 only (dr, tr). nr/shr/ny and the aspirates are NOT touched.

STATUS: operator-APPROVED (go), IMPLEMENTED, but NOT YET APPLIED to any experiment. The frozen v1 bridge and
every hashed declaration/result are unchanged. Going live requires: re-derive affected sequences (only 'dread'
among frozen items), re-freeze declarations, and a fresh prereg — before any test authoring (anti-circularity).

Resonance / phonetic-fidelity refinement only — no ontology, no semantic-truth claim, no GENUTILITY_*, no
ONTOLOGICAL_SIGNAL. B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import json
import pathlib
from typing import Dict, List, Optional

HERE = pathlib.Path(__file__).resolve().parent
BRIDGE_V1 = HERE / "frozen" / "b1_6_phoneme_to_varna_bridge_manifest.json"

# dental stop -> retroflex when the next phoneme is /r/
RETROFLEX_BEFORE_R = {"t": "tta", "d": "dda"}
TRIGGER = "r"


def base_mapping() -> Dict[str, str]:
    return json.loads(BRIDGE_V1.read_text())["bridge_table"]["mapping"]


def phonemes_to_varnas(phonemes: List[str], mapping: Optional[Dict[str, str]] = None) -> List[str]:
    """Apply v1 mapping + the Phase-1 retroflex-cluster rule. The /r/ that triggers retroflexion is itself
    still mapped normally (Route B: r survives). Unsupported/vowel phonemes are dropped, exactly as in v1."""
    mp = mapping if mapping is not None else base_mapping()
    out: List[str] = []
    n = len(phonemes)
    for i, p in enumerate(phonemes):
        nxt = phonemes[i + 1] if i + 1 < n else None
        if p in RETROFLEX_BEFORE_R and nxt == TRIGGER:
            out.append(RETROFLEX_BEFORE_R[p])      # t->tta / d->dda ; the following 'r' maps to 'ra' next iter
        elif p in mp:
            out.append(mp[p])
        # else: dropped (VOWEL_NO_PROFILE / UNSUPPORTED_NO_VARNA), same as v1
    return out


def word_to_varnas(word: str) -> List[str]:
    """Convenience: canonical Stage A′ (A_PRIME_EN) decomposition + bridge v2. Hyphen-split like the v1 path."""
    import stage_a_prime_coverage as A
    phs: List[str] = []
    for tok in word.split("-"):
        phs += A.normalize(tok, "A_PRIME_EN")["phonemes"]
    return phonemes_to_varnas(phs)


if __name__ == "__main__":
    for w in ["drum", "train", "dread", "dry", "tree", "peace", "terror", "cat"]:
        print(f"  {w:8} -> {word_to_varnas(w)}")
