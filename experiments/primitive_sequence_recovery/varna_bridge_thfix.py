"""CANDIDATE: /θ,ð/ fidelity fix — remap the merged 'th' phoneme OFF tha (aspirated stop / viṣāda-melancholy) to
the DENTAL UNASPIRATED stop ta (voiceless), and pre-wire dh -> da for a FUTURE G2P that distinguishes voiced /ð/.

Why: English /θ/ (thin) and /ð/ (this) are DENTAL FRICATIVES that Sanskrit lacks. The current bridge maps them to
tha (थ, the aspirated dental STOP = viṣāda), which is wrong on manner AND massively over-triggers 'melancholy'
(the/this/that are the most frequent English words). The dental PLACE is right, so the least-wrong target is the
dental stop ta (voiceless) — NOT the aspirate tha. This explicitly moves OFF the aspirate series, so it does NOT
create an aspiration rule.

The G2P collapses BOTH /θ/ and /ð/ into a single 'th' phoneme (it never emits 'dh'), so a bridge-only fix cannot
distinguish voicing — it maps merged 'th' -> ta. 'dh' -> da is pre-wired for a future G2P that emits dh for /ð/
(currently dead: dh is never emitted). Composes cleanly with the retroflex bridge v2 (disjoint phonemes: v2 keys
on 't'/'d' before 'r'; this keys on 'th'/'dh').

STATUS: CANDIDATE ONLY — NOT APPLIED. The frozen v1 bridge, bridge v2, and the v3 table are all unchanged. Going
live would need re-derive (0 frozen items change) + re-freeze + fresh prereg. Resonance / phonetic-fidelity
refinement only — no ontology/semantic-truth/Sanskrit-privilege claim, no GENUTILITY_*, no ONTOLOGICAL_SIGNAL.
Track B remains blocked. B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
from typing import Dict, List

import varna_bridge_v2 as B2

# merged 'th' (both /θ/ and /ð/) -> ta (dental unaspirated stop). 'dh' -> da is inert until a G2P emits dh.
THFIX_OVERRIDE: Dict[str, str] = {"th": "ta", "dh": "da"}


def corrected_mapping() -> Dict[str, str]:
    return {**B2.base_mapping(), **THFIX_OVERRIDE}


def phonemes_to_varnas(phonemes: List[str], retroflex: bool = True) -> List[str]:
    """th-fix applied; retroflex=True also composes the retroflex-cluster rule (bridge v2)."""
    mp = corrected_mapping()
    if retroflex:
        return B2.phonemes_to_varnas(phonemes, mapping=mp)   # retroflex (t/d+r) + th-fix, disjoint phonemes
    return [mp[p] for p in phonemes if p in mp]


def word_to_varnas(word: str, retroflex: bool = True) -> List[str]:
    import stage_a_prime_coverage as A
    phs: List[str] = []
    for tok in word.split("-"):
        phs += A.normalize(tok, "A_PRIME_EN")["phonemes"]
    return phonemes_to_varnas(phs, retroflex=retroflex)


if __name__ == "__main__":
    for w in ["thin", "thought", "path", "faith", "this", "that", "other", "mother", "the", "three", "drum"]:
        print(f"  {w:8} -> {word_to_varnas(w)}")
