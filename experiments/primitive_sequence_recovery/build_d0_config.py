"""Build the D0 input-bundle (d0_config.json) deterministically — NO LLM, NO scoring.

Renders arms A (real), B (scrambled-assignment), C (equal-length affliction decoy) for the
contamination-reduced word subsets, plus the controlled vocabulary, Barnum family, and seeds.
This is the D0 "input freeze" step: it produces the config the RunPod runner consumes. It does
NOT call an LLM, NOT score anything, NOT touch frozen/manifest.json / the readiness gate / Stage
A. Output is a config bundle only; profiles are generated later by the LLM (Stage 1 in the runner).

    python3 build_d0_config.py --out /workspace/d0_config.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random

_HERE = pathlib.Path(__file__).resolve().parent
_FROZEN = _HERE / "frozen"

# contamination-reduced subsets (word_ids from TRACK_D_D0_PROPOSED_PILOT_CONFIG.md §4a/§4b/§4c)
ABSTRACT_PRIMARY = ["w004", "w005", "w002", "w001", "w021", "w013", "w069", "w070"]
CONCRETE_CONTROL = ["w037", "w036", "w042", "w049", "w050", "w034", "w043", "w007", "w093", "w101"]
FAMOUS_EXPLORATORY = ["w018", "w019", "w020", "w017", "w023", "w014"]  # exploratory-only

CONTAM_TIER = {**{w: "med" for w in ABSTRACT_PRIMARY},
               "w069": "low-med",
               **{w: "low" for w in CONCRETE_CONTROL},
               **{w: "high" for w in FAMOUS_EXPLORATORY}}

CONTROLLED_VOCABULARY = [
    "calm", "peace", "serenity", "tension", "anxiety", "fear", "dread", "anger", "rage",
    "irritation", "grief", "sorrow", "sadness", "joy", "delight", "contentment", "longing",
    "craving", "desire", "attachment", "aversion", "disgust", "shame", "guilt", "pride",
    "arrogance", "humility", "trust", "doubt", "confusion", "clarity", "heaviness", "lightness",
    "warmth", "coldness", "openness", "contraction", "restlessness", "stillness", "vulnerability",
    "strength", "weakness", "hope", "despair", "love", "hatred", "compassion", "cruelty",
    "courage", "cowardice", "emptiness", "fullness", "alertness", "dullness",
]

BARNUM = {
    "I1": ["feeling", "mood", "emotion", "affect", "tension", "calm", "intensity", "warmth"],
    "I2": ["awakening", "transcendence", "surrender", "journey", "insight", "renewal"],
    "I3": ["pain", "hurt", "wound", "grief", "struggle", "loss", "heaviness", "vulnerability"],
    "I4": ["growth", "progress", "strength", "resilience", "becoming", "flourishing"],
}

SEEDS = {"scramble": 11, "decoy": 20260702, "shuffle": 0}


def _compose(atoms, atom_content):
    return " ; ".join(atom_content[a] for a in atoms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="d0_config.json")
    a = ap.parse_args()

    tau = json.loads((_FROZEN / "assignment.json").read_text(encoding="utf-8"))["tau"]
    ac = json.loads((_FROZEN / "realization_en_gloss.json").read_text(encoding="utf-8"))["atom_content"]
    wl = {w["word_id"]: w for w in json.loads((_FROZEN / "word_list.json").read_text(encoding="utf-8"))["words"]}
    mr = {m["word_id"]: m["canonical_meaning"]
          for m in json.loads((_FROZEN / "meaning_reference.json").read_text(encoding="utf-8"))["meanings"]}

    # scrambled assignment: permute gloss values across atoms (frozen seed)
    atoms_sorted = sorted(ac)
    vals = [ac[x] for x in atoms_sorted]
    random.Random(SEEDS["scramble"]).shuffle(vals)
    ac_scrambled = {atoms_sorted[i]: vals[i] for i in range(len(atoms_sorted))}

    gloss_pool = list(ac.values())
    decoy_rng = random.Random(SEEDS["decoy"])

    words = []
    for domain, ids in (("abstract_primary", ABSTRACT_PRIMARY),
                        ("concrete_control", CONCRETE_CONTROL),
                        ("famous_exploratory", FAMOUS_EXPLORATORY)):
        for wid in ids:
            w = wl[wid]
            atoms = [tau[v] for v in w["varna_sequence"]]
            A = _compose(atoms, ac)
            B = _compose(atoms, ac_scrambled)
            C = " ; ".join(decoy_rng.sample(gloss_pool, len(atoms)))   # equal-length decoy
            words.append({
                "word_id": wid,
                "spelling": w["spelling"],           # RECORDS ONLY — never sent to the LLM
                "dictionary_meaning": mr[wid],
                "pos": "noun",
                "domain": domain,
                "contamination_tier": CONTAM_TIER.get(wid, "unknown"),
                "compositions": {"A": A, "B": B, "C": C},
            })

    cfg = {
        "schema_version": "1.0",
        "note": ("D0 exploratory input bundle. Compositions use the frozen en_gloss vṛtti glosses "
                 "(English → inherent leakage; exploratory triage only). Profiles are generated "
                 "by the LLM at Stage 1. Not validation; never ONTOLOGICAL_SIGNAL; Track B BLOCKED."),
        "controlled_vocabulary": CONTROLLED_VOCABULARY,
        "barnum": BARNUM,
        "seeds": SEEDS,
        "words": words,
    }
    out = pathlib.Path(a.out)
    out.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}  |  words={len(words)} "
          f"(abstract={len(ABSTRACT_PRIMARY)}, concrete={len(CONCRETE_CONTROL)}, "
          f"famous={len(FAMOUS_EXPLORATORY)})")
    print("D0 input bundle built (deterministic, no LLM, no scoring). Track B remains blocked.")


if __name__ == "__main__":
    main()
