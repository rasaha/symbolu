#!/usr/bin/env python3
"""Build per-word mapped consonant occurrences (occurrence-level, multiplicity preserved) with exact frozen glosses.

Reads the frozen parser and the corrected v3 lexicon. Used ONLY at scoring time (the runner supplies the frozen
mapping glosses to the models). It is never used during word-list selection (that firewall is upstream).
"""
from __future__ import annotations
import json, pathlib, importlib.util

EXPT = pathlib.Path(__file__).resolve().parent.parent   # experiments/primitive_sequence_recovery
LEXICON = EXPT / "frozen" / "varna_native_stage1_merged_v3.json"
PARSER = EXPT / "sanskrit_stage1_parser.py"

def _load_parser():
    spec = importlib.util.spec_from_file_location("sanskrit_stage1_parser", PARSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def load_lexicon():
    rows = json.load(open(LEXICON, encoding="utf-8"))["rows"]
    return {r["canonical_parser_unit"]: r for r in rows}

def word_occurrences(dev):
    """Return list of occurrences for a Devanāgarī word:
    [{occurrence_index, varna, type, is_mapped, mapping_gloss}] for consonant units, multiplicity preserved."""
    parser = _load_parser()
    lex = load_lexicon()
    r = parser.parse(dev)
    occ = []
    idx = 0
    for v in r["atomic_varnas"]:
        if v["type"] != "consonant":
            continue
        u = v["unit"]
        row = lex.get(u)
        mapped = bool(row and row.get("activation_scope") == "CONFIRMATORY_BACKBONE" and row.get("binding_vritti"))
        occ.append({
            "occurrence_index": idx,
            "varna": u,
            "is_mapped": mapped,
            "mapping_gloss": row["binding_vritti"] if mapped else None,
        })
        idx += 1
    return {"iast_parser": r["transliteration_iast"], "warnings": r.get("warnings", []), "occurrences": occ}
