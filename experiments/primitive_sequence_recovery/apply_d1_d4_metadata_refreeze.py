"""Apply the D1–D4 metadata-only re-freeze as a SUPERSEDING versioned table (v3.1).

Authoritative decision source: varna_table_reconciliation/d1_d4_resolution.json (reconciliation commit 26d680c9).

Why a new file instead of editing frozen/varna_polarity_table_v3.json in place: v3.json is hash-pinned by three
completed English-run evidence-freeze declarations (b1_10 / hardened v3 / b1_10). In-place editing would invalidate
prior-experiment provenance, which the re-freeze scope forbids. v3.1 supersedes v3 for NATIVE-Sanskrit use only;
v3.json stays byte-identical. Pole content is proven identical between v3 and v3.1 (metadata-only change).

Changes (metadata/documentation ONLY): important_caveats[1] (pa) and [3] (ṭha) updated to their resolved state;
caveats [4]–[8] scoped to the deprecated English-G2P bridge; per-varṇa reachability split into explicit
`native_parser_reachable` + `english_g2p_bridge_reachable` (old `practically_reachable` retained, marked deprecated);
top-level reachability_model + metadata_refreeze provenance block. NO pole, polarity, citation, or meaning changed.
"""
import copy
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "frozen" / "varna_polarity_table_v3.json"
DST = HERE / "frozen" / "varna_polarity_table_v3_1_metadata_refreeze.json"
POLE_EXCLUDE = {"bridge_reachable", "practically_reachable",   # rescoped / deprecated
                "english_g2p_bridge_reachable", "native_parser_reachable"}   # added metadata (not pole content)


def pole_content_hash(table):
    pole = {k: {f: v for f, v in ent.items() if f not in POLE_EXCLUDE} for k, ent in table["varnas"].items()}
    return hashlib.sha256(json.dumps(pole, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def build():
    src = json.load(open(SRC, encoding="utf-8"))
    t = copy.deepcopy(src)

    cav = t["important_caveats"]
    # D1 — pa: entry supersedes the stale inversion caveat
    cav[1] = ("D1 RESOLVED (see B1_VARNA_TABLE_D1_D4_RECONCILIATION.md): pa = ghṛṇā (hatred) is the BINDING pole "
              "per the attested pāsha reading; v3 option B superseded the earlier option-A inversion. The pa entry "
              "(attested_vs_authored) is authoritative — 'no inversion flag remains'.")
    # D2 — ṭha: entry already marks the discrepancy resolved
    cav[3] = ("D2 RESOLVED (see varnas.ttha.classical_discrepancy = 'RESOLVED'): ṭha (ttha) = anutāpa (repentance) "
              "is the pole axis; night/moon/bhúvarloka are ASSOCIATIONS (ha's cosmological opposite), not a competing "
              "pole. Associations vs pole axis — not a contradiction.")
    # D3 / D4 — scope the English-G2P reachability + mapping caveats to the deprecated bridge
    for idx in (4, 5, 6, 7, 8):
        if not cav[idx].startswith("DEPRECATED ENGLISH-G2P BRIDGE ONLY:"):
            cav[idx] = "DEPRECATED ENGLISH-G2P BRIDGE ONLY: " + cav[idx]
    cav.append("D3/D4 RESOLVED: the reachability caveats [4]–[8] and the per-varṇa english_g2p_bridge_reachable field "
               "describe the DEPRECATED English-G2P bridge, NOT the native Stage-1 parser. Under the native parser "
               "(frozen a1988394) every consonant grapheme is reachable and थ → tha (single aspirated dental stop) is "
               "correct. Use native_parser_reachable for native inventory decisions.")

    # per-varṇa reachability split (metadata only; pole content untouched)
    for key, ent in t["varnas"].items():
        egb = bool(ent.get("practically_reachable"))
        ent["english_g2p_bridge_reachable"] = egb                 # explicit rename of the deprecated field's meaning
        ent["native_parser_reachable"] = (key != "ksha")          # parser emits all base graphemes; kṣa decomposes to k+ṣ
        # practically_reachable retained as a deprecated alias (do NOT use for native inventory) — see reachability_model

    t["reachability_model"] = {
        "native_parser_reachable": "true iff the frozen native Stage-1 parser emits this varṇa from a Devanāgarī "
                                   "grapheme. Authoritative for native-Sanskrit inventory decisions.",
        "english_g2p_bridge_reachable": "historical coverage of the DEPRECATED English-G2P bridge (== old "
                                        "practically_reachable). Retained for provenance; NOT a native-inventory property.",
        "practically_reachable": "DEPRECATED alias of english_g2p_bridge_reachable. Native consumers must not use it.",
        "ksha_note": "ksha (kṣa) is native_parser_reachable=false because the parser decomposes क्ष → क + ष (k + ṣ); "
                     "it never emits a unified kṣa unit.",
    }
    t["metadata_refreeze"] = {
        "supersedes": "varna_polarity_table_v3.json",
        "supersession_scope": "NATIVE-Sanskrit use only; v3.json stays byte-identical for the completed English runs",
        "change_class": "METADATA_ONLY",
        "reconciliation_commit": "26d680c9",
        "resolved_contradictions": ["D1", "D2", "D3", "D4"],
        "pole_content_identical_to_v3": True,
        "pole_content_hash": pole_content_hash(src),
        "changes": ["important_caveats[1] (pa)", "important_caveats[3] (ṭha)",
                    "important_caveats[4..8] scoped to deprecated English-G2P bridge",
                    "added important_caveats[10] (D3/D4 resolution note)",
                    "per-varṇa english_g2p_bridge_reachable + native_parser_reachable",
                    "reachability_model block"],
        "unchanged": ["all binding poles", "all liberating poles", "all source citations", "attested_vs_authored",
                      "classical_discrepancy", "primary_text_scope", "classical_side_attested", "provenance"],
    }
    t["status"] = "ACTIVE_APPLIED_METADATA_REFREEZE_v3_1"

    # invariant: pole content identical
    assert pole_content_hash(src) == pole_content_hash(t), "POLE CONTENT CHANGED — abort"

    DST.write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return src, t


if __name__ == "__main__":
    src, t = build()
    h_src = pole_content_hash(src)
    h_dst = pole_content_hash(t)
    print("pole-content hash v3 :", h_src)
    print("pole-content hash v3.1:", h_dst)
    print("POLE CONTENT IDENTICAL:", h_src == h_dst)
    print("v3.json byte-unchanged:", hashlib.sha256(open(SRC, "rb").read()).hexdigest()
          == "d3ff8efd0775b78c92b66bf11cd5eec75aaf4354015551be1c22d6ba8494d0b3")
    print("wrote", DST.name)
