"""Stage-1 parser → varṇa-mapping INTEGRATION audit (docs/data-only).

Determines whether the corrected native-Sanskrit parser's atomic varṇas resolve correctly and COMPLETELY
against the current varṇa mapping table. This is a STRUCTURAL faithfulness audit, NOT semantic validation: it
does not judge whether resulting meanings are correct, authors no meanings, selects no polarity, runs no judge.

Reads (read-only): the corrected parser (sanskrit_stage1_parser), frozen/varna_polarity_table_v3.json, the
provenance register, and frozen/word_list.json (the existing IAST-derived Sanskrit seed list). Emits new
docs/data artifacts only. No parser / table / Track-G / provenance change.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL.
"""
import csv
import json
import pathlib

import sanskrit_stage1_parser as P

HERE = pathlib.Path(__file__).resolve().parent
TABLE = json.load(open(HERE / "frozen" / "varna_polarity_table_v3_1_metadata_refreeze.json", encoding="utf-8"))
REG = json.load(open(HERE / "varna_provenance_register" / "varna_provenance_register.json", encoding="utf-8"))
SEED = json.load(open(HERE / "frozen" / "word_list.json", encoding="utf-8"))
OUT = HERE / "stage1_mapping_integration"

# ---- parser bare-consonant IAST  ->  table key (the canonical identity bridge) ----------------------------------
PARSER_CONS_TO_KEY = {
    "k": "ka", "kh": "kha", "g": "ga", "gh": "gha", "ṅ": "nga",
    "c": "ca", "ch": "cha", "j": "ja", "jh": "jha", "ñ": "nya",
    "ṭ": "tta", "ṭh": "ttha", "ḍ": "dda", "ḍh": "ddha", "ṇ": "nna",
    "t": "ta", "th": "tha", "d": "da", "dh": "dha", "n": "na",
    "p": "pa", "ph": "pha", "b": "ba", "bh": "bha", "m": "ma",
    "y": "ya", "r": "ra", "l": "la", "v": "va",
    "ś": "sha", "ṣ": "ssa", "s": "sa", "h": "ha",
    "ḷ": None,   # retroflex lateral ळ — NO table key
}
# 'ksha' (kṣa) is a table key with NO parser producer: the parser decomposes क्ष -> क + ष (k + ṣ).
KEY_NO_PARSER_PRODUCER = "ksha"

REG_FLAGS = {r["varna"]: r["flags"] for r in REG["varnas"]}
# v3.1 metadata refreeze: active status now uses native_parser_reachable (authoritative), not the deprecated
# English-G2P practically_reachable flag. D3/D4 reachability contradictions are resolved by this scoping.
NPR = {k: bool(v.get("native_parser_reachable")) for k, v in TABLE["varnas"].items()}
EGB = {k: bool(v.get("english_g2p_bridge_reachable", v.get("practically_reachable"))) for k, v in TABLE["varnas"].items()}


def _pole_prov(key):
    for r in REG["varnas"]:
        if r["varna"] == key:
            return r["poles"]["binding"]["provenance_status"], r["poles"]["liberating"]["provenance_status"]
    return None, None


def resolve_consonant(iast):
    """Classify a recognized-consonant parser identity against the table."""
    key = PARSER_CONS_TO_KEY.get(iast, "__unmapped__")
    if key is None:
        return {"table_key": None, "status": "MISSING_TABLE_ENTRY",
                "note": "retroflex lateral ळ has no entry in the 34-key table"}
    if key == "__unmapped__":
        return {"table_key": None, "status": "UNRESOLVED_IDENTITY",
                "note": f"parser unit {iast!r} not in the identity bridge"}
    flags = REG_FLAGS.get(key, [])
    # D3/D4 resolved: reachability is native_parser_reachable (authoritative). No CONTRADICTORY_ENTRY remains for
    # reachability; the deprecated English-bridge coverage is retained separately for provenance.
    status = "EXACT_ACTIVE" if NPR[key] else "EXACT_INACTIVE"
    return {"table_key": key, "status": status, "table_active_flag": NPR[key],
            "english_g2p_bridge_reachable": EGB[key], "provenance_flags": flags}


# ---- IAST -> Devanāgarī (AUDIT-INPUT HELPER ONLY; not part of the parser) ----------------------------------------
# Validated by round-trip: parse(devanagari).transliteration_iast must reproduce the IAST spelling.
_C = {"k": "क", "kh": "ख", "g": "ग", "gh": "घ", "ṅ": "ङ", "c": "च", "ch": "छ", "j": "ज", "jh": "झ", "ñ": "ञ",
      "ṭ": "ट", "ṭh": "ठ", "ḍ": "ड", "ḍh": "ढ", "ṇ": "ण", "t": "त", "th": "थ", "d": "द", "dh": "ध", "n": "न",
      "p": "प", "ph": "फ", "b": "ब", "bh": "भ", "m": "म", "y": "य", "r": "र", "l": "ल", "v": "व",
      "ś": "श", "ṣ": "ष", "s": "स", "h": "ह", "ḷ": "ळ"}
_VI = {"a": "अ", "ā": "आ", "i": "इ", "ī": "ई", "u": "उ", "ū": "ऊ", "ṛ": "ऋ", "ṝ": "ॠ", "e": "ए", "ai": "ऐ",
       "o": "ओ", "au": "औ"}
_VM = {"a": "", "ā": "ा", "i": "ि", "ī": "ी", "u": "ु", "ū": "ू", "ṛ": "ृ", "ṝ": "ॄ", "e": "े", "ai": "ै",
       "o": "ो", "au": "ौ"}
_MK = {"ṃ": "ं", "ḥ": "ः"}
_CONS2 = {c for c in _C if len(c) == 2}
_VOW2 = {v for v in _VI if len(v) == 2}


def iast_to_devanagari(s):
    toks = []
    i = 0
    while i < len(s):
        if s[i:i + 2] in _CONS2:
            toks.append(("C", s[i:i + 2])); i += 2
        elif s[i] in _C:
            toks.append(("C", s[i])); i += 1
        elif s[i:i + 2] in _VOW2:
            toks.append(("V", s[i:i + 2])); i += 2
        elif s[i] in _VI:
            toks.append(("V", s[i])); i += 1
        elif s[i] in _MK:
            toks.append(("M", s[i])); i += 1
        else:
            toks.append(("?", s[i])); i += 1
    out, pending = [], False
    for t, val in toks:
        if t == "C":
            if pending:
                out.append(P.VIRAMA)
            out.append(_C[val]); pending = True
        elif t == "V":
            if pending:
                out.append(_VM[val]); pending = False
            else:
                out.append(_VI[val])
        elif t == "M":
            pending = False
            out.append(_MK[val])
        else:
            out.append(val)
    if pending:
        out.append(P.VIRAMA)
    return "".join(out)


def resolve_unit(u):
    """Resolve one parsed atomic unit to a mapping status."""
    t = u["type"]
    if t == "consonant":
        r = resolve_consonant(u["unit"])
    elif t == "vowel":
        r = {"table_key": None, "status": "MISSING_TABLE_ENTRY",
             "note": "vowels carry no entry in the current consonant-only table"}
    elif t == "anusvara":
        r = {"table_key": None, "status": "MISSING_TABLE_ENTRY", "note": "anusvāra ṃ has no table entry"}
    elif t == "visarga":
        r = {"table_key": None, "status": "MISSING_TABLE_ENTRY", "note": "visarga ḥ has no table entry"}
    elif t == "nasalization":
        r = {"table_key": None, "status": "MISSING_TABLE_ENTRY", "note": "candrabindu has no table entry"}
    elif t == "marker":
        r = {"table_key": None, "status": "NON_SEMANTIC_MARKER", "note": "orthographic marker, not a varṇa"}
    else:  # unsupported
        r = {"table_key": None, "status": "UNSUPPORTED_ORTHOGRAPHIC_UNIT",
             "note": "non-classical / unresolved orthographic base"}
    return {"devanagari": u["devanagari"], "parser_unit": u["unit"], "type": t,
            "inherent_inserted": u["inherent_inserted"], **r}


def audit_word(devanagari, iast=None, gloss=None):
    rec = P.parse(devanagari)
    resolutions = [resolve_unit(u) for u in rec["atomic_varnas"]
                   if u["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization", "marker", "unsupported")]
    statuses = [r["status"] for r in resolutions]
    n_missing = sum(s == "MISSING_TABLE_ENTRY" for s in statuses)
    n_contra = sum(s == "CONTRADICTORY_ENTRY" for s in statuses)
    n_unsup = sum(s in ("UNSUPPORTED_ORTHOGRAPHIC_UNIT", "UNRESOLVED_IDENTITY") for s in statuses)
    n_exact = sum(s in ("EXACT_ACTIVE", "EXACT_INACTIVE", "ALIASED_EXACT") for s in statuses)
    if n_contra:
        word_status = "CONTRADICTORY_MAPPING"
    elif n_exact == 0:
        word_status = "UNMAPPABLE"
    elif n_missing or n_unsup:
        word_status = "PARTIALLY_MAPPABLE"
    else:
        word_status = "FULLY_MAPPABLE"
    # order + multiplicity integrity (phonological units only)
    parser_seq = [u["unit"] for u in rec["atomic_varnas"]
                  if u["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization")]
    resolved_seq = [r["parser_unit"] for r in resolutions
                    if r["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization")]
    return {
        "word_devanagari": devanagari,
        "iast": rec["transliteration_iast"],
        "iast_intended": iast,
        "gloss": gloss,
        "round_trip_ok": (iast is None) or (rec["transliteration_iast"] == iast),
        "aksharas": [a["devanagari"] for a in rec["aksharas"]],
        "atomic_varnas": resolutions,
        "atomic_count": len(parser_seq),
        "resolution_count": len(resolved_seq),
        "order_preserved": parser_seq == resolved_seq,
        "multiplicity_preserved": len(parser_seq) == len(resolved_seq),
        "word_status": word_status,
        "n_exact": n_exact, "n_missing": n_missing, "n_contradictory": n_contra, "n_unsupported": n_unsup,
    }


# ---- audited word sets -----------------------------------------------------------------------------------------
# correctness-probe words (IAST -> Devanāgarī via helper); each exercises a specific distinction (Section D)
PROBE = [
    ("gati", "dental t"), ("koṭi", "retroflex ṭa"), ("nata", "dental na+ta"), ("naṭa", "retroflex ṭa"),
    ("śiva", "palatal ś"), ("viṣṇu", "retroflex ṣa + ṇa"), ("rasa", "dental sa"),
    ("khaga", "aspirated kha vs g"), ("gaja", "voiced g/j"),
    ("aṅga", "velar nasal ṅ"), ("pañca", "palatal nasal ñ"), ("kaṇṭha", "retroflex ṇ+ṭh"),
    ("danta", "dental n"), ("kampa", "labial nasal m"),
    ("ṛtu", "vocalic ṛ (independent)"), ("rāma", "consonantal r"), ("kṛṣṇa", "vocalic ṛ + r-cluster"),
    ("saṃskāra", "anusvāra ṃ"), ("haṃsa", "h + anusvāra"), ("duḥkha", "visarga ḥ vs aspirate"),
    ("kṣatra", "kṣa conjunct decomposition"), ("sattva", "gemination t+t+v"), ("anna", "gemination n+n"),
    ("bala", "inherent a"), ("agni", "independent a onset"), ("kāla", "dependent ā"),
    ("dharma", "repha r"), ("buddhi", "d+dh cluster"), ("ānanda", "long ā onset + nd"),
    ("śraddhā", "śr + ddh clusters"),
]


def build():
    OUT.mkdir(exist_ok=True)
    warnings_iast_helper = []

    # ---------- A. identity bridge ----------
    bridge = []
    # consonants (parser inventory, incl ḷ)
    deva_of = {v[0]: k for k, v in P.CONSONANTS.items()}   # iast -> devanagari grapheme
    for iast in ["k", "kh", "g", "gh", "ṅ", "c", "ch", "j", "jh", "ñ", "ṭ", "ṭh", "ḍ", "ḍh", "ṇ",
                 "t", "th", "d", "dh", "n", "p", "ph", "b", "bh", "m", "y", "r", "l", "v", "ś", "ṣ", "s", "h", "ḷ"]:
        r = resolve_consonant(iast)
        key = r.get("table_key")
        b_prov, l_prov = _pole_prov(key) if key else (None, None)
        asp = P.CONSONANTS[deva_of[iast]][1]
        bridge.append({
            "devanagari": deva_of[iast], "parser_unit": iast, "iast": iast, "phonological_class": "consonant",
            "aspirated": asp, "parser_type": "consonant", "table_key": key, "mapping_status": r["status"],
            "table_active_flag": r.get("table_active_flag"), "provenance_flags": r.get("provenance_flags", []),
            "binding_pole_provenance": b_prov, "liberating_pole_provenance": l_prov,
            "note": r.get("note", "native parser reaches this grapheme regardless of the table's old-bridge flag"),
        })
    # vowels (independent identities)
    for deva, (iast, length) in P.IND_VOWELS.items():
        bridge.append({
            "devanagari": deva, "parser_unit": iast, "iast": iast, "phonological_class": f"vowel_{length}",
            "aspirated": None, "parser_type": "vowel", "table_key": None, "mapping_status": "MISSING_TABLE_ENTRY",
            "table_active_flag": None, "provenance_flags": [], "binding_pole_provenance": None,
            "liberating_pole_provenance": None, "note": "no vowel entries exist in the current table"})
    # marks
    for deva, iast, cls, note in [(P.ANUSVARA, "ṃ", "anusvara", "no anusvāra entry"),
                                  (P.VISARGA, "ḥ", "visarga", "no visarga entry"),
                                  (P.CANDRABINDU, "m̐", "nasalization", "no candrabindu entry")]:
        bridge.append({"devanagari": deva, "parser_unit": iast, "iast": iast, "phonological_class": cls,
                       "aspirated": None, "parser_type": cls, "table_key": None,
                       "mapping_status": "MISSING_TABLE_ENTRY", "table_active_flag": None, "provenance_flags": [],
                       "binding_pole_provenance": None, "liberating_pole_provenance": None, "note": note})
    # markers / unsupported exemplars
    bridge.append({"devanagari": P.AVAGRAHA, "parser_unit": "'", "iast": "'", "phonological_class": "marker",
                   "aspirated": None, "parser_type": "marker", "table_key": None,
                   "mapping_status": "NON_SEMANTIC_MARKER", "table_active_flag": None, "provenance_flags": [],
                   "binding_pole_provenance": None, "liberating_pole_provenance": None,
                   "note": "avagraha — orthographic marker"})
    bridge.append({"devanagari": "क़", "parser_unit": "क़", "iast": "qa(nukta)", "phonological_class": "unsupported",
                   "aspirated": None, "parser_type": "unsupported", "table_key": None,
                   "mapping_status": "UNSUPPORTED_ORTHOGRAPHIC_UNIT", "table_active_flag": None,
                   "provenance_flags": [], "binding_pole_provenance": None, "liberating_pole_provenance": None,
                   "note": "non-classical nukta base — no canonical varṇa identity"})

    # ---------- B. word-by-word resolution (probes + seed list) ----------
    words = []
    for iast, gloss in PROBE:
        deva = iast_to_devanagari(iast)
        w = audit_word(deva, iast=iast, gloss=gloss)
        if not w["round_trip_ok"]:
            warnings_iast_helper.append({"iast": iast, "produced": w["iast"], "devanagari": deva})
        words.append(w)

    # seed-list words (IAST -> Devanāgarī helper), with round-trip flag; excluded from stats if it doesn't round-trip
    seed_words = []
    for entry in SEED["words"]:
        iast = entry["spelling"]
        deva = iast_to_devanagari(iast)
        w = audit_word(deva, iast=iast)
        w["word_id"] = entry["word_id"]
        w["old_varna_sequence"] = entry["varna_sequence"]
        if not w["round_trip_ok"]:
            warnings_iast_helper.append({"iast": iast, "produced": w["iast"], "devanagari": deva})
        seed_words.append(w)

    # ---------- C. coverage matrix ----------
    cons_bridge = [b for b in bridge if b["parser_type"] == "consonant"]
    def _count(pred, src=cons_bridge):
        return sum(1 for b in src if pred(b))
    unit_cov = {
        "parser_emittable_classical_units": len(bridge) - 2,  # minus the 2 marker/unsupported exemplars
        "consonants_total": 34, "vowels_total": 14, "anusvara": 1, "visarga": 1, "candrabindu": 1,
        "consonant_exact_active": _count(lambda b: b["mapping_status"] == "EXACT_ACTIVE"),
        "consonant_exact_inactive": _count(lambda b: b["mapping_status"] == "EXACT_INACTIVE"),
        "consonant_contradictory": _count(lambda b: b["mapping_status"] == "CONTRADICTORY_ENTRY"),
        "consonant_missing": _count(lambda b: b["mapping_status"] == "MISSING_TABLE_ENTRY"),
        "vowel_resolved": 0, "vowel_missing": 14,
        "anusvara_resolved": 0, "visarga_resolved": 0, "candrabindu_resolved": 0,
        "aspirates_total": 10,
        "aspirates_with_entry": sum(1 for b in cons_bridge if b["aspirated"] and b["table_key"]),
        "aspirates_active": sum(1 for b in cons_bridge if b["aspirated"] and b["mapping_status"] == "EXACT_ACTIVE"),
        "table_keys_without_parser_producer": [KEY_NO_PARSER_PRODUCER],
        # D3/D4 RESOLVED (v3.1): active status now uses native_parser_reachable. All producing consonants are
        # native-active; the historical English-bridge gap is retained below for provenance, no longer a contradiction.
        "native_reachable_but_table_inactive": [],
        "english_bridge_inactive_but_native_reachable_historical": sorted(
            b["table_key"] for b in cons_bridge
            if b["table_key"] and not EGB.get(b["table_key"]) and NPR.get(b["table_key"])),
    }

    # frequency-weighted coverage over the seed corpus (round-tripping words only)
    from collections import Counter
    freq = Counter()
    freq_status = Counter()
    for w in seed_words:
        if not w["round_trip_ok"]:
            continue
        for r in w["atomic_varnas"]:
            if r["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization"):
                freq[r["parser_unit"]] += 1
                freq_status[r["status"]] += 1
    total_tokens = sum(freq_status.values())
    freq_cov = {
        "total_phonological_tokens": total_tokens,
        "by_status": dict(freq_status),
        "pct_exact_active": round(100 * freq_status.get("EXACT_ACTIVE", 0) / total_tokens, 1) if total_tokens else 0,
        "pct_any_table_entry": round(100 * (freq_status.get("EXACT_ACTIVE", 0) + freq_status.get("EXACT_INACTIVE", 0)
                                            + freq_status.get("CONTRADICTORY_ENTRY", 0)) / total_tokens, 1) if total_tokens else 0,
        "pct_missing": round(100 * freq_status.get("MISSING_TABLE_ENTRY", 0) / total_tokens, 1) if total_tokens else 0,
    }

    # ---------- F. Track-G / seed old-vs-new decomposition diff ----------
    diffs = []
    for w in seed_words:
        if not w["round_trip_ok"]:
            diffs.append({"word_id": w["word_id"], "iast": w["iast_intended"], "round_trip_ok": False,
                          "note": "IAST->Devanāgarī helper did not round-trip; excluded from structural comparison"})
            continue
        new_cons = [PARSER_CONS_TO_KEY.get(r["parser_unit"]) for r in w["atomic_varnas"] if r["type"] == "consonant"]
        new_cons = [c for c in new_cons if c]
        old = w["old_varna_sequence"]
        new_full = [r["parser_unit"] for r in w["atomic_varnas"]
                    if r["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization")]
        n_vowels = sum(1 for r in w["atomic_varnas"] if r["type"] == "vowel")
        n_marks = sum(1 for r in w["atomic_varnas"] if r["type"] in ("anusvara", "visarga", "nasalization"))
        flags = []
        if n_vowels:
            flags.append("OLD_DROPPED_VOWELS")
        if n_marks:
            flags.append("OLD_OMITTED_ANUSVARA_OR_VISARGA")
        if new_cons != old:
            flags.append("CONSONANT_SEQUENCE_DIFFERS")
        diffs.append({"word_id": w["word_id"], "iast": w["iast_intended"], "round_trip_ok": True,
                      "old_consonant_only": old, "new_consonant_keys": new_cons,
                      "new_full_atomic": new_full, "n_vowels_recovered": n_vowels, "n_marks_recovered": n_marks,
                      "consonants_match": new_cons == old, "flags": flags})

    # ---------- discrepancies ----------
    discrepancies = {
        "identity_bridge_mismatches": [b for b in bridge if b["mapping_status"] == "UNRESOLVED_IDENTITY"],
        "contradictory_entries": [b["table_key"] for b in cons_bridge if b["mapping_status"] == "CONTRADICTORY_ENTRY"],
        "missing_categories": {
            "vowels": [b["iast"] for b in bridge if b["parser_type"] == "vowel"],
            "anusvara": True, "visarga": True, "candrabindu": True,
            "retroflex_lateral_la": "ḷ (ळ) has no table key",
        },
        "table_keys_without_parser_producer": [KEY_NO_PARSER_PRODUCER],
        "d3_d4_reachability_status": "RESOLVED_BY_METADATA_REFREEZE_v3_1 (active status uses native_parser_reachable)",
        "native_reachable_but_table_inactive": [],
        "english_bridge_inactive_but_native_reachable_historical": sorted(
            b["table_key"] for b in cons_bridge
            if b["table_key"] and not EGB.get(b["table_key"]) and NPR.get(b["table_key"])),
        "pole_provenance_flags_on_keys": {b["table_key"]: b["provenance_flags"]
                                          for b in cons_bridge if b["provenance_flags"]},
        "iast_helper_non_round_trip": warnings_iast_helper,
    }

    # ---------- readiness verdict ----------
    verdict = "BLOCKED_BY_MISSING_VOWEL_AND_MARKER_MAPPINGS"
    verdict_reason = (
        "The identity bridge is clean (33/33 recognized consonants resolve 1:1 to distinct table keys, no "
        "collapses), but the FULL parsed inventory is not mappable: all 14 vowels, anusvāra, visarga and "
        "candrabindu are MISSING_TABLE_ENTRY, and frequency-weighted these dominate every word. Two entries "
        "(tta/dda) are CONTRADICTORY (table marks them unreachable while the native parser emits them). No word "
        "with a vowel is FULLY_MAPPABLE under the current consonant-only table.")

    # ---------- write artifacts ----------
    (OUT / "identity_bridge.json").write_text(json.dumps({"bridge": bridge}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "word_resolution.json").write_text(json.dumps(
        {"probe_words": words, "seed_words": seed_words}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "coverage_summary.json").write_text(json.dumps(
        {"unit_level": unit_cov, "frequency_weighted": freq_cov}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "discrepancies.json").write_text(json.dumps(discrepancies, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "trackg_decomposition_diff.json").write_text(json.dumps({"diffs": diffs}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # flat CSV of the identity bridge
    with open(OUT / "identity_bridge.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["devanagari", "parser_unit", "iast", "phonological_class", "aspirated", "parser_type",
                     "table_key", "mapping_status", "table_active_flag", "provenance_flags",
                     "binding_pole_provenance", "liberating_pole_provenance"])
        for b in bridge:
            wr.writerow([b["devanagari"], b["parser_unit"], b["iast"], b["phonological_class"], b["aspirated"],
                         b["parser_type"], b["table_key"], b["mapping_status"], b["table_active_flag"],
                         ";".join(b["provenance_flags"]), b["binding_pole_provenance"], b["liberating_pole_provenance"]])

    return {"bridge": bridge, "words": words, "seed_words": seed_words, "unit_cov": unit_cov,
            "freq_cov": freq_cov, "diffs": diffs, "discrepancies": discrepancies,
            "verdict": verdict, "verdict_reason": verdict_reason}


if __name__ == "__main__":
    res = build()
    uc, fc = res["unit_cov"], res["freq_cov"]
    print("VERDICT:", res["verdict"])
    print(f"consonants: active={uc['consonant_exact_active']} inactive={uc['consonant_exact_inactive']} "
          f"contradictory={uc['consonant_contradictory']} missing={uc['consonant_missing']}")
    print(f"vowels resolved={uc['vowel_resolved']}/14  anusvara/visarga/candrabindu resolved=0/3")
    print(f"aspirates: with_entry={uc['aspirates_with_entry']}/10 active={uc['aspirates_active']}/10")
    print(f"freq-weighted: tokens={fc['total_phonological_tokens']} active={fc['pct_exact_active']}% "
          f"any_entry={fc['pct_any_table_entry']}% missing={fc['pct_missing']}%")
    rt = sum(1 for w in res["seed_words"] if w["round_trip_ok"])
    print(f"seed words round-tripped: {rt}/{len(res['seed_words'])}")
    fm = sum(1 for w in res["seed_words"] if w["round_trip_ok"] and w["word_status"] == "FULLY_MAPPABLE")
    pm = sum(1 for w in res["seed_words"] if w["round_trip_ok"] and w["word_status"] == "PARTIALLY_MAPPABLE")
    print(f"seed word status: FULLY={fm} PARTIALLY={pm}")
    diffs_dropvow = sum(1 for d in res["diffs"] if d.get("round_trip_ok") and "OLD_DROPPED_VOWELS" in d.get("flags", []))
    print(f"seed words where OLD decomposition dropped vowels: {diffs_dropvow}")
