"""Build the native Stage-1 MERGED lexicon per the operator authority ruling (docs/data/code-only).

Operator ruling:
  - v3.1 (varna_polarity_table_v3_1_metadata_refreeze.json) is authoritative for CONSONANT identity + poles.
  - varna_lens/lexicon_authoritative_varna.json is authoritative for VOWEL / anusvāra / visarga poles.
  - Do NOT import consonant rows from the lens where they overlap v3.1 (esp. its stale sha/ssa/ha).
  - Create a NEW versioned artifact; never modify the three source artifacts in place.

This authors NO new meaning: consonant poles are copied verbatim from v3.1; vowel/anusvāra/visarga poles are copied
verbatim from the lens and marked AUTHORED_PROVISIONAL / DEVELOPMENT_ONLY / NOT_EMPIRICALLY_VALIDATED (with the prior
NO_SIGNAL result referenced, not treated as deletion). Structure, not validated meaning.
"""
import copy
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
V31_PATH = HERE / "frozen" / "varna_polarity_table_v3_1_metadata_refreeze.json"
LEX_PATH = ROOT / "varna_lens" / "lexicon_authoritative_varna.json"
REG_PATH = HERE / "varna_provenance_register" / "varna_provenance_register.json"
OUT_PATH = HERE / "frozen" / "varna_native_stage1_merged_v1.json"

V31 = json.load(open(V31_PATH, encoding="utf-8"))["varnas"]
LEX = json.load(open(LEX_PATH, encoding="utf-8"))
REG = {r["varna"]: r for r in json.load(open(REG_PATH, encoding="utf-8"))["varnas"]}

# parser bare-consonant IAST -> v3.1 key (identity bridge; ksha has no parser producer)
PARSER_CONS_TO_KEY = {
    "k": "ka", "kh": "kha", "g": "ga", "gh": "gha", "ṅ": "nga", "c": "ca", "ch": "cha", "j": "ja", "jh": "jha",
    "ñ": "nya", "ṭ": "tta", "ṭh": "ttha", "ḍ": "dda", "ḍh": "ddha", "ṇ": "nna", "t": "ta", "th": "tha", "d": "da",
    "dh": "dha", "n": "na", "p": "pa", "ph": "pha", "b": "ba", "bh": "bha", "m": "ma", "y": "ya", "r": "ra",
    "l": "la", "v": "va", "ś": "sha", "ṣ": "ssa", "s": "sa", "h": "ha",
}
DEVA_CONS = {"k": "क", "kh": "ख", "g": "ग", "gh": "घ", "ṅ": "ङ", "c": "च", "ch": "छ", "j": "ज", "jh": "झ",
             "ñ": "ञ", "ṭ": "ट", "ṭh": "ठ", "ḍ": "ड", "ḍh": "ढ", "ṇ": "ण", "t": "त", "th": "थ", "d": "द",
             "dh": "ध", "n": "न", "p": "प", "ph": "फ", "b": "ब", "bh": "भ", "m": "म", "y": "य", "r": "र",
             "l": "ल", "v": "व", "ś": "श", "ṣ": "ष", "s": "स", "h": "ह"}
# vowel/marker parser unit -> lens key (operator-specified bridge)
VOWEL_BRIDGE = {"a": "a", "ā": "aa", "i": "i", "ī": "ii", "u": "u", "ū": "uu",
                "e": "e", "ai": "ai", "o": "o", "au": "au"}
MARK_BRIDGE = {"ṃ": ("am", "anusvara", "ं"), "ḥ": ("ah", "visarga", "ः")}
MISSING_UNITS = [("ṛ", "ऋ", "vowel"), ("ṝ", "ॠ", "vowel"), ("l̥", "ऌ", "vowel"), ("l̥̄", "ॡ", "vowel"),
                 ("m̐", "ँ", "candrabindu")]

NO_SIGNAL_REF = ("varna_lens/RESULTS_ACOUSTIC_SIGNAL.md + RESULTS_ACOUSTIC_SIGNAL_CORRECTED_LEXICON.md "
                 "(pre-registered NO_SIGNAL, twice; row RETAINED not deleted)")


def _aliases(key):
    r = LEX.get("_romanization", {}).get(key)
    return r["plain_input"] if r else []


def consonant_pole_hash(rows_or_v31, is_v31=False):
    if is_v31:
        # compare over the 33 producible keys (ksha has no parser producer and is not a merged row)
        d = {k: (rows_or_v31[k]["worldly_binding_distortion"], rows_or_v31[k]["spiritual_liberating_reading"])
             for k in rows_or_v31 if k != "ksha"}
    else:
        d = {r["source_key"]: (r["binding_vritti"], r["liberating_vritti"])
             for r in rows_or_v31 if r["category"] == "consonant" and r["source_key"]}
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def build():
    rows = []
    conflict_notes = []

    # ---- consonants: v3.1 verbatim ----
    for iast, key in PARSER_CONS_TO_KEY.items():
        v = V31[key]
        rows.append({
            "canonical_parser_unit": iast, "devanagari": DEVA_CONS[iast], "iast": iast, "category": "consonant",
            "source_artifact": "frozen/varna_polarity_table_v3_1_metadata_refreeze.json", "source_key": key,
            "binding_vritti": v["worldly_binding_distortion"], "liberating_vritti": v["spiritual_liberating_reading"],
            "binding_pole_provenance": REG[key]["poles"]["binding"]["provenance_status"],
            "liberating_pole_provenance": REG[key]["poles"]["liberating"]["provenance_status"],
            "activation_scope": "CONFIRMATORY_BACKBONE",
            "empirical_status_note": "v3.1 consonant backbone (b1_2 source + operator primary-text corrections); "
                                     "used in the B1 line (see B1.10 control-extension result).",
            "parser_reachable": bool(v.get("native_parser_reachable")),
            "aliases": _aliases(key),
        })
    # rejected lens consonant rows (esp. sha/ssa/ha) — recorded, NOT imported
    for key in ("sha", "ssa", "ha"):
        lb = LEX["consonants"][key]["binding_state"]
        lb = lb.get("sanskrit") or lb.get("english") if isinstance(lb, dict) else lb
        conflict_notes.append({"key": key, "rejected_source": "varna_lens/lexicon_authoritative_varna.json",
                               "rejected_binding": lb, "kept_source": "v3.1", "kept_binding": V31[key]["worldly_binding_distortion"],
                               "reason": "operator ruling: v3.1 primary-text-corrected consonant is authoritative; "
                                         "lens row is stale (sibilant swap / ha-night)."})

    # ḷ (retroflex lateral) — parser emits it but v3.1 has no key: explicit out-of-scope
    rows.append({
        "canonical_parser_unit": "ḷ", "devanagari": "ळ", "iast": "ḷ", "category": "consonant",
        "source_artifact": None, "source_key": None, "binding_vritti": None, "liberating_vritti": None,
        "binding_pole_provenance": "OUT_OF_SCOPE", "liberating_pole_provenance": "OUT_OF_SCOPE",
        "activation_scope": "OUT_OF_SCOPE", "empirical_status_note": "retroflex lateral (extended Vedic/regional); "
        "no v3.1 key; parser emits it but it is outside the classical 34-key inventory.",
        "parser_reachable": True, "aliases": _aliases("lla")})

    # ---- vowels: lens verbatim, AUTHORED_PROVISIONAL / DEVELOPMENT_ONLY ----
    lex_vowels = LEX["vowels"]
    lex_deva = {v: LEX["_romanization"][k]["deva"] for k, v in
                [(x, x) for x in lex_vowels]}  # key->deva via romanization
    for unit, key in VOWEL_BRIDGE.items():
        e = lex_vowels[key]
        rows.append({
            "canonical_parser_unit": unit, "devanagari": LEX["_romanization"][key]["deva"], "iast": unit,
            "category": "vowel", "source_artifact": "varna_lens/lexicon_authoritative_varna.json", "source_key": key,
            "binding_vritti": e["binding_state"], "liberating_vritti": e["liberating_state"],
            "binding_pole_provenance": "AUTHORED_PROVISIONAL", "liberating_pole_provenance": "AUTHORED_PROVISIONAL",
            "activation_scope": "DEVELOPMENT_ONLY",
            "empirical_status_note": "NOT_EMPIRICALLY_VALIDATED; " + NO_SIGNAL_REF,
            "parser_reachable": True, "aliases": _aliases(key),
        })
    # anusvāra + visarga from lens (am / ah)
    for unit, (key, cat, deva) in MARK_BRIDGE.items():
        e = lex_vowels[key]
        rows.append({
            "canonical_parser_unit": unit, "devanagari": deva, "iast": unit, "category": cat,
            "source_artifact": "varna_lens/lexicon_authoritative_varna.json", "source_key": key,
            "binding_vritti": e["binding_state"], "liberating_vritti": e["liberating_state"],
            "binding_pole_provenance": "AUTHORED_PROVISIONAL", "liberating_pole_provenance": "AUTHORED_PROVISIONAL",
            "activation_scope": "DEVELOPMENT_ONLY",
            "empirical_status_note": "NOT_EMPIRICALLY_VALIDATED; " + NO_SIGNAL_REF,
            "parser_reachable": True, "aliases": _aliases(key),
        })
    # ---- explicit missing rows (never silently omitted) ----
    for unit, deva, cat in MISSING_UNITS:
        rows.append({
            "canonical_parser_unit": unit, "devanagari": deva, "iast": unit, "category": cat,
            "source_artifact": None, "source_key": None, "binding_vritti": None, "liberating_vritti": None,
            "binding_pole_provenance": "MISSING_TABLE_ENTRY", "liberating_pole_provenance": "MISSING_TABLE_ENTRY",
            "activation_scope": "MISSING", "empirical_status_note": "no mapping in v3.1 or the varṇa-lens lexicon.",
            "parser_reachable": (cat != "candrabindu") if unit not in ("ṝ", "l̥", "l̥̄") else True, "aliases": []})

    # ---- MECHANICAL ASSERTION: merged consonant pole content == v3.1 ----
    h_v31 = consonant_pole_hash(V31, is_v31=True)
    h_merged = consonant_pole_hash(rows)
    assert h_v31 == h_merged, "merged consonant pole content DIVERGES from v3.1 — abort"
    # sha/ssa/ha specifically come from v3.1
    for k in ("sha", "ssa", "ha"):
        row = next(r for r in rows if r["source_key"] == k)
        assert row["binding_vritti"] == V31[k]["worldly_binding_distortion"]
        assert row["source_artifact"].endswith("v3_1_metadata_refreeze.json")

    merged = {
        "artifact_type": "varna_native_stage1_merged_lexicon",
        "schema_version": "native_merged_v1",
        "operator_ruling": {
            "consonant_authority": "frozen/varna_polarity_table_v3_1_metadata_refreeze.json",
            "vowel_marker_authority": "varna_lens/lexicon_authoritative_varna.json (vowels + am/ah only)",
            "consonant_lens_rows_imported": False,
            "rejected_conflicting_consonants": ["sha", "ssa", "ha"],
        },
        "source_precedence": "consonants ← v3.1 (verbatim); vowels/anusvāra/visarga ← varṇa-lens (verbatim, "
                             "AUTHORED_PROVISIONAL); no averaging/merging of conflicting mappings.",
        "consonant_pole_content_hash": h_merged,
        "consonant_pole_content_hash_matches_v31": (h_v31 == h_merged),
        "ksha_note": "no compound kṣa producer — the parser decomposes क्ष → k + ṣ; kṣa is not a merged row.",
        "provenance_definitions": {
            "AUTHORED_PROVISIONAL": "pole text authored (no primary-text source_quote); development-only",
            "DEVELOPMENT_ONLY": "not eligible for a confirmatory mechanism until provenance is raised",
            "NOT_EMPIRICALLY_VALIDATED": "no positive empirical signal; see the referenced NO_SIGNAL results",
            "CONFIRMATORY_BACKBONE": "v3.1 consonant backbone already used by the B1 line",
            "MISSING_TABLE_ENTRY": "no mapping exists in either source",
            "OUT_OF_SCOPE": "outside the classical inventory",
        },
        "rows": rows,
        "conflict_notes": conflict_notes,
        "guardrails": "No new meaning authored; sources unmodified; authored vowels NOT relabelled as attested. "
                      "Structure, not validated meaning.",
    }
    OUT_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return merged


if __name__ == "__main__":
    m = build()
    from collections import Counter
    cats = Counter(r["category"] for r in m["rows"])
    scopes = Counter(r["activation_scope"] for r in m["rows"])
    print("wrote", OUT_PATH.name)
    print("rows:", len(m["rows"]), dict(cats))
    print("scopes:", dict(scopes))
    print("consonant pole hash == v3.1:", m["consonant_pole_content_hash_matches_v31"])
    print("conflicts recorded:", [c["key"] for c in m["conflict_notes"]])
