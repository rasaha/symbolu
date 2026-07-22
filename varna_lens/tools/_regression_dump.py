#!/usr/bin/env python3
"""Dump deterministic PSE profile + trajectory + reflection for a fixed corpus, as JSON, using the
ACTIVE varṇa→drive mapping (VARNA_LENS_MAPPING). Used by regression_old_vs_new.py, which invokes this
twice (old vs new mapping) in separate processes to avoid module-load caching. No LLM (use_llm=False)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # varna_lens/
import varna_lens as V          # noqa: E402
import pse_renderer as R        # noqa: E402

CORPUS = [
    # English (hybrid/g2p)
    "river", "kill", "compassion", "freedom", "temple", "wife", "poison", "knife", "happy", "courage",
    "xozence", "cognade",
    # IAST Sanskrit (roman) — concept words in the Symbol-U concern range + varṇa-swap-sensitive sibilants
    "kāla", "karma", "dama", "akrodha", "garva", "sneha", "dhṛti", "kleśa", "śānti", "ṣaṭ", "kṣamā", "yoga",
]


def profile(word):
    d, src, warn = V.analyze(word, model="op", hybrid=True)
    if not d:
        return {"word": word, "src": src, "unparseable": True, "warn": warn}
    signs = [a.get("vp") or a.get("db") or "" for a in d["sequence"]]  # informational
    # Which parser keys have NO active mapping (explicit abstention, e.g. ksha)?
    unmapped = [a["key"] for a in d["sequence"] if a["type"] == "C" and a["key"] not in V.CONS]
    traj = R.trajectory(word)
    ref = R.render(word, mode="essence_line", use_llm=False)
    return {
        "word": word,
        "src": src,
        "essence_short": d.get("essence_short"),
        "valence": (d.get("emergent_valence") or {}).get("lean"),
        "trajectory_roles": traj["trajectory"],
        "controlling_element": traj["controlling_element"],
        "tone": traj["tone"],
        "unmapped_varnas": unmapped,
        "reflection_essence_line": ref["layer3_reflection"],
        "honesty_ok": ref["honesty_ok"],
    }


def main():
    out = {"mapping": V.active_mapping_path().name, "profiles": [profile(w) for w in CORPUS]}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
