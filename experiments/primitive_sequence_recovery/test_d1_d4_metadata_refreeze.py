"""Assertions for the D1–D4 metadata-only re-freeze (v3.1). NO network, NO model.

Proves the six required invariants: caveats agree with entries; native vs English reachability are separate;
tta/dda/tha are native-reachable; deprecated English-bridge limits remain documented; NO pole content changed;
all source/provenance references intact. Structure, not validated meaning.
"""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
V3 = json.load(open(HERE / "frozen" / "varna_polarity_table_v3.json", encoding="utf-8"))
V31 = json.load(open(HERE / "frozen" / "varna_polarity_table_v3_1_metadata_refreeze.json", encoding="utf-8"))
POLE_EXCLUDE = {"bridge_reachable", "practically_reachable", "english_g2p_bridge_reachable", "native_parser_reachable"}
CITATION_FIELDS = ("source_note", "source_quote_verified", "provenance", "attested_vs_authored",
                   "worldly_binding_distortion", "spiritual_liberating_reading", "classical_associations",
                   "classical_side_attested", "primary_text_scope", "classical_discrepancy")


def _pole_hash(table):
    pole = {k: {f: v for f, v in ent.items() if f not in POLE_EXCLUDE} for k, ent in table["varnas"].items()}
    return hashlib.sha256(json.dumps(pole, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


# 1. pa/ṭha caveats agree with their per-varṇa entries
def test_pa_tha_caveats_agree_with_entries():
    cav = V31["important_caveats"]
    assert "RESOLVED" in cav[1] and "PARTIALLY INVERTS" not in cav[1]
    assert "no inversion flag remains" in V31["varnas"]["pa"]["attested_vs_authored"]
    assert "RESOLVED" in cav[3] and "is unresolved" not in cav[3]
    assert V31["varnas"]["ttha"]["classical_discrepancy"].startswith("RESOLVED")


# 2. native vs English-G2P reachability are separate fields/scopes
def test_reachability_fields_separate():
    assert "reachability_model" in V31
    for ent in V31["varnas"].values():
        assert "native_parser_reachable" in ent
        assert "english_g2p_bridge_reachable" in ent
    # they are genuinely distinct for at least the D3 keys
    assert V31["varnas"]["tta"]["native_parser_reachable"] != V31["varnas"]["tta"]["english_g2p_bridge_reachable"]


# 3. tta, dda, tha are native-parser reachable
def test_tta_dda_tha_native_reachable():
    for k in ("tta", "dda", "tha"):
        assert V31["varnas"][k]["native_parser_reachable"] is True


# 4. deprecated English-bridge limitations remain represented
def test_english_bridge_limits_documented():
    cav = V31["important_caveats"]
    assert any(c.startswith("DEPRECATED ENGLISH-G2P BRIDGE ONLY:") for c in cav)
    # english_g2p_bridge_reachable preserves the historical ~19/34 coverage
    egb = sum(1 for e in V31["varnas"].values() if e["english_g2p_bridge_reachable"])
    assert egb == 19
    assert V31["reachability_model"]["practically_reachable"].startswith("DEPRECATED")


# 5. NO pole content changed
def test_no_pole_content_changed():
    assert _pole_hash(V3) == _pole_hash(V31)
    assert V31["metadata_refreeze"]["pole_content_hash"] == _pole_hash(V3)
    # register pole-provenance counts unchanged vs the pre-refreeze classification
    import b1_varna_provenance_register as R
    reg, _ = R.build()
    assert reg["validation"]["pole_provenance_counts"] == {
        "PRIMARY_ATTESTED": 26, "AUTHORED_PROVISIONAL": 27, "INFERRED": 13, "SECONDARY_ATTESTED": 2}


# 6. all source/provenance references intact (byte-identical per varṇa)
def test_source_provenance_intact():
    for k, ent in V3["varnas"].items():
        for f in CITATION_FIELDS:
            assert ent.get(f) == V31["varnas"][k].get(f), f"{k}.{f} changed"


# D1–D4 resolved in the regenerated register; v3.json byte-unchanged
def test_register_resolved_and_v3_frozen():
    import b1_varna_provenance_register as R
    reg, _ = R.build()
    assert reg["readiness_verdict"] == "BLOCKED_BY_PROVENANCE_GAPS"
    assert reg["validation"]["n_unresolved_contradictions"] == 0
    resolved = {c["id"] for c in reg["contradictions"] if c.get("status", "").startswith("RESOLVED")}
    assert {"D1", "D2", "D3", "D4"} <= resolved
    assert hashlib.sha256((HERE / "frozen" / "varna_polarity_table_v3.json").read_bytes()).hexdigest() \
        == "d3ff8efd0775b78c92b66bf11cd5eec75aaf4354015551be1c22d6ba8494d0b3"
