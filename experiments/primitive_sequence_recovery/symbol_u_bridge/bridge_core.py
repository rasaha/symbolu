#!/usr/bin/env python3
"""Symbol-U deterministic bridge core (stages 2–5 of SYMBOL_U_CONCERN_TO_CONCEPT_BRIDGE_SPEC_V1.md).

Given an already-resolved concern id (or a Sanskrit concept word directly), deterministically produce:
    concern id -> canonical Sanskrit concept (frozen table) -> varṇas (frozen parser) -> binding-vṛtti glosses
        (frozen v3 mappings), with graceful abstention and inspectable provenance.

OUT OF SCOPE (they need an LLM, not this script):
    S1  concern extraction  (raw user text -> concern id)      -> caller supplies the concern id
    S6  reflective synthesis (glosses -> natural reflection)    -> returned field `reflection` is always None here

Everything here is deterministic and read-only: the frozen parser, v3 mapping table, concern ontology, and
concern→concept table are loaded and NEVER modified. The reflection this eventually feeds is auxiliary and
non-authoritative.

CLI:
    python bridge_core.py --concern C0016
    python bridge_core.py --concept धन
    python bridge_core.py --all-concerns
    python bridge_core.py --concern C9999          # -> NO_APPLICABLE_CONCEPT
    add --json for machine-readable output; --verify to hash-check the frozen inputs.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent            # …/symbol_u_bridge
EXPT = HERE.parent                                        # …/primitive_sequence_recovery
PARSER_PATH  = EXPT / "sanskrit_stage1_parser.py"
LEXICON_PATH = EXPT / "frozen" / "varna_native_stage1_merged_v3.json"
ONTOLOGY_PATH = HERE / "concern_ontology_v1.json"
CONCEPT_PATH  = HERE / "concern_to_sanskrit_concept_v1.json"

# Expected frozen-input hashes (advisory; --verify enforces). Sourced from the frozen artifacts.
EXPECT = {
    "parser":  "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947",
    "lexicon": "65116f371aca9f24ba2cce080c458a7a878f9af4ae50562d3f518567e681d33f",
}
# B1.12 synthesis confidence hint (per the bridge spec's confidence model): the agreement-stable varṇas.
B1_12_TIER1_VARNAS = {"d", "s", "v", "y"}


def _sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def _load_parser():
    spec = importlib.util.spec_from_file_location("sanskrit_stage1_parser", PARSER_PATH)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def load_frozen():
    parser = _load_parser()
    lexicon = {r["canonical_parser_unit"]: r for r in json.load(open(LEXICON_PATH, encoding="utf-8"))["rows"]}
    concepts = {e["concern_id"]: e["canonical_concept"]
                for e in json.load(open(CONCEPT_PATH, encoding="utf-8"))["entries"]}
    labels = {c["id"]: c["label"] for c in json.load(open(ONTOLOGY_PATH, encoding="utf-8"))["concerns"]}
    return parser, lexicon, concepts, labels

def provenance():
    return {"parser_sha256": _sha(PARSER_PATH), "lexicon_v3_sha256": _sha(LEXICON_PATH),
            "concept_table_sha256": _sha(CONCEPT_PATH), "ontology_sha256": _sha(ONTOLOGY_PATH),
            "note": "auxiliary, non-authoritative symbolic reflection input; deterministic; frozen inputs unchanged"}

def decompose(parser, lexicon, devanagari):
    """Devanāgarī word -> ordered consonant varṇas with binding-vṛtti glosses (mapped ones only carry a gloss)."""
    r = parser.parse(devanagari)
    out = []
    for v in r["atomic_varnas"]:
        if v["type"] != "consonant":
            continue
        u = v["unit"]; row = lexicon.get(u)
        mapped = bool(row and row.get("activation_scope") == "CONFIRMATORY_BACKBONE" and row.get("binding_vritti"))
        out.append({"varna": u, "is_mapped": mapped,
                    "mapping_gloss": row["binding_vritti"] if mapped else None,
                    "b1_12_tier1": u in B1_12_TIER1_VARNAS})
    return r["transliteration_iast"], out

def bridge(concern_id=None, concept_word=None, frozen=None):
    """Deterministic bridge result. Supply a concern_id (looked up in the frozen table) OR a Devanāgarī concept_word.
    Returns a dict with status in {OK, NO_APPLICABLE_CONCEPT, NO_MAPPED_VARNA}."""
    parser, lexicon, concepts, labels = frozen or load_frozen()
    result = {"status": None, "concern_id": concern_id, "concern_label": labels.get(concern_id),
              "sanskrit_word": None, "iast": None, "varnas": [], "mapping_glosses": [],
              "reflection": None,  # S6 is an LLM step, intentionally not produced here
              "provenance": provenance()}
    # Stage 3: concern id -> canonical concept (deterministic table lookup) — or a directly supplied word
    if concept_word is None:
        if concern_id not in concepts:                       # Stage 4 abstention
            result["status"] = "NO_APPLICABLE_CONCEPT"; return result
        cc = concepts[concern_id]; concept_word = cc["devanagari"]; result["sanskrit_word"] = cc["iast"]
    else:
        result["sanskrit_word"] = None
    # Stage 5: parse + map
    iast, units = decompose(parser, lexicon, concept_word)
    result["iast"] = iast
    result["varnas"] = [u["varna"] for u in units]
    result["mapping_glosses"] = [u for u in units if u["is_mapped"]]
    if not result["mapping_glosses"]:
        result["status"] = "NO_MAPPED_VARNA"; return result
    n_tier1 = sum(1 for u in result["mapping_glosses"] if u["b1_12_tier1"])
    result["status"] = "OK"
    result["confidence_hint"] = {"n_mapped": len(result["mapping_glosses"]),
                                 "n_b1_12_tier1": n_tier1,
                                 "note": "B1.12 found d/s/v/y the most agreement-stable varṇas; more Tier-1 => steadier"}
    return result

def _print_human(res):
    print(f"[{res['status']}] concern={res.get('concern_id')} ({res.get('concern_label')}) "
          f"word={res.get('sanskrit_word')} ({res.get('iast')})")
    for u in res["mapping_glosses"]:
        tag = "  (Tier-1)" if u["b1_12_tier1"] else ""
        print(f"   {u['varna']:3s} -> {u['mapping_gloss']}{tag}")
    if res["status"] == "NO_MAPPED_VARNA":
        print("   (no mapped consonants — symbolic layer abstains)")

def main():
    ap = argparse.ArgumentParser(description="Symbol-U deterministic bridge core (stages 2–5).")
    ap.add_argument("--concern", help="concern id, e.g. C0016")
    ap.add_argument("--concept", help="Devanāgarī concept word directly, e.g. धन")
    ap.add_argument("--all-concerns", action="store_true", help="run every concern in the frozen ontology")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verify", action="store_true", help="hash-check frozen parser + mapping table")
    a = ap.parse_args()
    if a.verify:
        for k, path in (("parser", PARSER_PATH), ("lexicon", LEXICON_PATH)):
            got = _sha(path); ok = got == EXPECT[k]
            print(f"{'OK ' if ok else 'MISMATCH '}{k}: {got}")
        if not a.concern and not a.concept and not a.all_concerns:
            return
    frozen = load_frozen()
    if a.all_concerns:
        _, _, concepts, _ = frozen
        results = [bridge(concern_id=cid, frozen=frozen) for cid in sorted(concepts)]
        if a.json: print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for r in results: _print_human(r)
        return
    if not a.concern and not a.concept:
        ap.error("give --concern, --concept, or --all-concerns")
    res = bridge(concern_id=a.concern, concept_word=a.concept, frozen=frozen)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else None) if a.json else _print_human(res)

if __name__ == "__main__":
    main()
