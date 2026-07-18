#!/usr/bin/env python3
"""Read-only extractor: 33 confirmatory consonants -> classical-association layer.
Joins the frozen merged lexicon (binding/liberating glosses) to the corrected
v3.1 polarity table (classical_associations, guṇa, tattva, deity, provenance).
NOTHING is inferred: tattva/guṇa/deity are set only when the source text states
them explicitly; otherwise MISSING. Preserves exact source wording."""
import json, hashlib, re

BASE = "frozen/"
MERGED = BASE + "varna_native_stage1_merged_v1.json"
V31 = BASE + "varna_polarity_table_v3_1_metadata_refreeze.json"
V2 = "track_g_varna_polarity_table_v2_named_vritti.json"
SRCLEX = "b1_2_mapping_fidelity/b1_2_varna_source_lexicon.json"
CLASSVER = "b1_2_mapping_fidelity/b1_2_varna_classical_verifications.json"

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

HASHES = {p: sha(p) for p in [MERGED, V31, V2, SRCLEX, CLASSVER]}

merged = json.load(open(MERGED))
v31 = json.load(open(V31))["varnas"]
conf = [r for r in merged["rows"]
        if r.get("source_artifact") == "frozen/varna_polarity_table_v3_1_metadata_refreeze.json"]

# --- explicit-only extractors (no inference) --------------------------------
def extract_guna(text):
    if not text: return "MISSING", None
    for token, norm in (("tamoguṇa", "tamas (static)"),
                        ("rajoguṇa", "rajas (mutative)"),
                        ("sattvaguṇa", "sattva (sentient)")):
        if token in text:
            return norm, token
    return "MISSING", None

def extract_tattva(text):
    if not text: return "MISSING", None
    for token, norm in (("agnitattva", "agni / fire"),
                        ("kṣititattva", "kṣiti / earth (pṛthvī)"),
                        ("jalatattva", "jala / water"),
                        ("ether (ākāśa) factor", "ākāśa / ether"),):
        if token in text:
            return norm, token
    # y: air/vāyu explicitly flagged as a motion/tattva association
    if "vāyu" in text and "tattva association" in text:
        return "vāyu / air", "vāyu (motion/tattva association)"
    return "MISSING", None

def extract_deity(text):
    if not text: return "MISSING", None
    if "Varuṇa Deva" in text:
        return "Varuṇa", "Varuṇa Deva (rain-god)"
    return "MISSING", None

def status_from_prov(prov):
    if prov in ("PRIMARY_ATTESTED", "SECONDARY_ATTESTED"):
        return "ATTESTED"
    if prov in ("AUTHORED_PROVISIONAL", "INFERRED"):
        return "DEVELOPMENT_ONLY"
    return "DEVELOPMENT_ONLY"

SWAP_KEYS = {"sha", "ssa"}  # the resolved sibilant swap

rows = []
for i, r in enumerate(conf, 1):
    unit = r["canonical_parser_unit"]
    sk = r["source_key"]
    e = v31.get(sk, {})
    ca = e.get("classical_associations")
    guna_norm, guna_src = extract_guna(ca)
    tattva_norm, tattva_src = extract_tattva(ca)
    deity_norm, deity_src = extract_deity(ca)
    prov = r.get("binding_pole_provenance")
    notes = []
    if sk in SWAP_KEYS:
        notes.append("RESOLVED sibilant swap: this guṇa/puruṣārtha was mis-filed in "
                     "b1_1 draft / b1_2_varna_source_lexicon / track_g_v2 (śa<->ṣa) and "
                     "corrected at v3.1 per primary text; see VARNA_SHA_SWAP_PROVENANCE_AUDIT.md")
    if ca is None:
        notes.append("no classical_associations field in v3.1 source (MISSING, not inferred)")
    rows.append({
        "index": i,
        "atomic_varna": unit,
        "stable_id": "cons_" + sk,
        "iast": r.get("iast"),
        "devanagari": r.get("devanagari"),
        "source_key_v31": sk,
        "unicode_codepoints": [f"U+{ord(c):04X}" for c in unit],
        "binding_gloss": r.get("binding_vritti"),
        "liberating_gloss": r.get("liberating_vritti"),
        "tattva_association": tattva_norm,
        "tattva_source_verbatim": tattva_src,
        "guna_association": guna_norm,
        "guna_source_verbatim": guna_src,
        "deity_association": deity_norm,
        "deity_source_verbatim": deity_src,
        "classical_or_philosophical_association_verbatim": ca if ca else "MISSING",
        "primary_text_citation": e.get("source_quote_verified"),
        "attested_vs_authored_verbatim": e.get("attested_vs_authored"),
        "binding_pole_provenance": prov,
        "source_status": status_from_prov(prov),
        "guna_tattva_deity_status": ("ATTESTED" if (guna_norm != "MISSING" or tattva_norm != "MISSING"
                                                    or deity_norm != "MISSING") else "MISSING"),
        "provenance_path": [
            "b1_2_varna_classical_verifications.json (primary-text authority; swap detected here)",
            "-> b1_2_varna_source_lexicon.json / b1_1 draft (swap present for śa/ṣa)",
            "-> track_g_varna_polarity_table_v2_named_vritti.json (swap present for śa/ṣa)",
            "-> frozen/varna_polarity_table_v3_1_metadata_refreeze.json (CORRECTED)",
            "-> frozen/varna_native_stage1_merged_v1.json (consumed by feature-lift study)"
        ],
        "ambiguity_or_conflict_notes": notes,
        "artifact_hashes": {"merged_v1": HASHES[MERGED], "polarity_v3_1": HASHES[V31]},
    })

tattva_cov = [r["atomic_varna"] for r in rows if r["tattva_association"] != "MISSING"]
guna_cov = [r["atomic_varna"] for r in rows if r["guna_association"] != "MISSING"]
deity_cov = [r["atomic_varna"] for r in rows if r["deity_association"] != "MISSING"]
no_classical = [r["atomic_varna"] for r in rows if r["classical_or_philosophical_association_verbatim"] == "MISSING"]

out = {
    "schema": "varna_classical_associations_33_v1",
    "label": "READ_ONLY_EXTRACTION / EXPLICIT_ONLY_NO_INFERENCE",
    "n_consonants": len(rows),
    "source_precedence": "corrected v3.1 (primary-text-verified) joined to frozen merged lexicon",
    "explicit_value_vocabulary": ["ATTESTED", "DEVELOPMENT_ONLY", "MISSING", "CONFLICTED"],
    "coverage": {
        "tattva": {"count": len(tattva_cov), "varnas": tattva_cov},
        "guna": {"count": len(guna_cov), "varnas": guna_cov},
        "deity": {"count": len(deity_cov), "varnas": deity_cov},
        "no_classical_association_field": {"count": len(no_classical), "varnas": no_classical},
    },
    "resolved_swap": {"phonemes": ["ś", "ṣ"],
                      "verdict": "SWAP_PROVENANCE_RESOLVED_NO_DATA_ERROR",
                      "detail": "See VARNA_SHA_SWAP_PROVENANCE_AUDIT.md"},
    "artifact_hashes": HASHES,
    "rows": rows,
}
json.dump(out, open("varna_classical_associations_33.json", "w"),
          ensure_ascii=False, indent=2)
print(json.dumps({"n": len(rows), "tattva": tattva_cov, "guna": guna_cov,
                  "deity": deity_cov, "no_classical": no_classical}, ensure_ascii=False, indent=2))
