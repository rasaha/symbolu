"""ACTIVE canonical bridge — Fidelity Bundle v1.

Active mapping = v1 base phoneme->varṇa mapping  ∘  retroflex rule (t/d before r -> ṭa/ḍa, r survives)
                 ∘  /θ,ð/ fix (merged 'th' -> ta; 'dh' -> da pre-wired).  ASPIRATION EXCLUDED.
The G2P decomposer (stage_a_prime_coverage, A_PRIME_EN) is UNTOUCHED; both rules are bridge-level (Route B).

Labels (stamp into every bundle-era artifact):
    mapping_era = fidelity_bundle_v1
    table       = v3
    bridge      = bridge_v2_plus_theta_eth_ta

Resonance / phonetic-fidelity refinement only — no GENUTILITY_*, no ONTOLOGICAL_SIGNAL, no semantic-truth /
ontology / Sanskrit-privilege claim. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b + Track B remain blocked.
Structure, not validated meaning.
"""
from __future__ import annotations
import pathlib
from typing import List

import varna_bridge_thfix as _TF   # composes retroflex (bridge v2) + /θ,ð/->ta

MAPPING_ERA = "fidelity_bundle_v1"
TABLE = "v3"
BRIDGE = "bridge_v2_plus_theta_eth_ta"
ASPIRATION_APPLIED = False

HERE = pathlib.Path(__file__).resolve().parent
ACTIVE_TABLE = HERE / "frozen" / "varna_polarity_table_v3.json"
ACTIVE_BRIDGE_MANIFEST = HERE / "frozen" / "varna_polarity_bridge_v3.json"


def labels() -> dict:
    return {"mapping_era": MAPPING_ERA, "table": TABLE, "bridge": BRIDGE, "aspiration_applied": ASPIRATION_APPLIED}


def phonemes_to_varnas(phonemes: List[str]) -> List[str]:
    return _TF.phonemes_to_varnas(phonemes, retroflex=True)


def word_to_varnas(word: str) -> List[str]:
    return _TF.word_to_varnas(word, retroflex=True)


if __name__ == "__main__":
    print("labels:", labels())
    for w in ["dread", "drum", "train", "the", "three", "peace", "terror"]:
        print(f"  {w:8} -> {word_to_varnas(w)}")
