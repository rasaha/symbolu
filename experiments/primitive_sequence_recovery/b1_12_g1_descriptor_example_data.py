#!/usr/bin/env python3
"""B1.12 G1 descriptor-example review — READ-ONLY data generation (no experiment, no judges, no artifact edits).

For a representative word list, derive: parser varṇa sequence + frozen binding descriptor per varṇa (verbatim +
short head) + ordinary gloss. Used to illustrate, with concrete examples, whether the affliction/tendency
descriptors relate to ordinary referents. Modifies nothing frozen; writes only a review-data JSON.
"""
from __future__ import annotations

import json
import pathlib
import re

import sanskrit_stage1_parser as P

HERE = pathlib.Path(__file__).resolve().parent
LEX = {r["canonical_parser_unit"]: r for r in
       json.loads((HERE / "frozen" / "varna_native_stage1_merged_v1.json").read_text())["rows"]}
OUT = HERE / "results" / "b1_12_g1_reviews"


def head(gloss, n=4):
    if not gloss:
        return "—(no frozen descriptor)"
    h = re.split(r"\s*:\s|\s*\(|\s*—\s*", gloss)[0]
    words = h.split()
    return " ".join(words[:n]) + ("…" if len(words) > n else "")


# selected six + ~24 representative attested words (NOT cherry-picked; deliberately spans domains incl. afflictions)
WORDS = [
    # --- the selected six ---
    ("अस्थि", "asthi", "bone", "body/SELECTED"),
    ("ग्रीवा", "grīvā", "neck", "body/SELECTED"),
    ("ज्ञान", "jñāna", "knowledge", "abstract/SELECTED"),
    ("केश", "keśa", "hair", "body/SELECTED"),
    ("नदी", "nadī", "river", "natural/SELECTED"),
    ("सूर्य", "sūrya", "sun", "natural/SELECTED"),
    # --- concrete objects ---
    ("घट", "ghaṭa", "pot", "concrete_object"),
    ("गृह", "gṛha", "house", "concrete_object"),
    ("रथ", "ratha", "chariot", "concrete_object"),
    # --- body parts ---
    ("हस्त", "hasta", "hand", "body_part"),
    ("पाद", "pāda", "foot", "body_part"),
    ("नेत्र", "netra", "eye", "body_part"),
    # --- animals ---
    ("गज", "gaja", "elephant", "animal"),
    ("अश्व", "aśva", "horse", "animal"),
    ("व्याघ्र", "vyāghra", "tiger", "animal"),
    # --- plants ---
    ("वृक्ष", "vṛkṣa", "tree", "plant"),
    ("पुष्प", "puṣpa", "flower", "plant"),
    # --- natural phenomena ---
    ("अग्नि", "agni", "fire", "natural_phenomenon"),
    ("वायु", "vāyu", "wind", "natural_phenomenon"),
    ("पर्वत", "parvata", "mountain", "natural_phenomenon"),
    # --- actions ---
    ("गमन", "gamana", "going", "action"),
    ("दान", "dāna", "giving", "action"),
    # --- emotions / afflictions (deliberately included to search for successes) ---
    ("भय", "bhaya", "fear", "emotion_negative"),
    ("क्रोध", "krodha", "anger", "emotion_negative"),
    ("लोभ", "lobha", "greed", "emotion_negative"),
    ("काम", "kāma", "desire", "emotion_negative"),
    ("हर्ष", "harṣa", "joy", "emotion_positive"),
    ("शोक", "śoka", "grief", "emotion_negative"),
    # --- abstract positive / negative ---
    ("सत्य", "satya", "truth", "abstract_positive"),
    ("धर्म", "dharma", "virtue/duty", "abstract_positive"),
    ("दुःख", "duḥkha", "suffering", "abstract_negative"),
    ("सुख", "sukha", "happiness", "abstract_positive"),
    ("शान्ति", "śānti", "peace", "abstract_positive"),
]


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for dev, iast, gloss, cat in WORDS:
        av = P.parse(dev)["atomic_varnas"]
        units = [u["unit"] for u in av]
        descs, shorts, missing = [], [], []
        for u in av:
            lr = LEX.get(u["unit"])
            g = lr.get("binding_vritti") if lr else None
            descs.append(g)
            shorts.append(head(g))
            if not g:
                missing.append(u["unit"])
        rows.append({"devanagari": dev, "iast": iast, "gloss": gloss, "category": cat,
                     "varna_sequence": units, "length": len(units),
                     "descriptor_full": descs, "descriptor_short": shorts,
                     "units_without_descriptor": missing})
    (OUT / "descriptor_example_data.json").write_text(
        json.dumps({"schema": "b1_12_g1_descriptor_example_data", "n_words": len(rows), "rows": rows},
                   ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return rows


if __name__ == "__main__":
    for r in build():
        seq = " ".join(r["varna_sequence"])
        short = " | ".join(r["descriptor_short"])
        print(f"{r['iast']:9} ({r['gloss']:13}) [{r['category']:22}] {seq}")
        print(f"          -> {short}")
