"""Re-derive the B1.9 pole-DiD items + scaffold under the ACTIVE Fidelity Bundle v1 mapping
(v3 table + combined bridge retroflex+θð→ta). Produces NEW *_bundle_v1.json artifacts; the v2/v1-era files are
left byte-unchanged. Fresh approval is REQUIRED (classification_approved reset to false). Mapping labels stamped.

Reuses the same 24-word ITEMS_SPEC and the same seeded W→W′ derangement as the v2-era builder (no re-selection);
only the varṇa SEQUENCES (active bridge) and the pole PACKET text (v3 table) differ. Under the bundle only `dread`'s
sequence changes (da,ra,da → ḍa,ra,da); all 24 packets change because v3 rewrote the poles.

Resonance / phonetic-fidelity refinement only — no GENUTILITY_*, no ONTOLOGICAL_SIGNAL, no semantic-truth/ontology/
Sanskrit-privilege claim. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b + Track B remain blocked.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

import build_b1_9_pole_did_scaffold as B0     # ITEMS_SPEC, _wprime_map, _pole_facets, BINDING, LIBERATING
import varna_bridge_active as AB               # active bridge (retroflex + θð→ta); labels

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V3_TABLE = FROZEN / "varna_polarity_table_v3.json"
BRIDGE_MANIFEST = FROZEN / "varna_polarity_bridge_v3.json"
DECOMPOSER = HERE / "stage_a_prime_coverage.py"
ITEMS_OUT = FROZEN / "b1_9_pole_did_items_bundle_v1.json"
SCAF_OUT = FROZEN / "b1_9_pole_did_scaffold_bundle_v1.json"


def _sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def canonical_varnas(word: str) -> list:
    """Active-mapping varṇa sequence: canonical Stage A′ decompose + combined bridge (retroflex + θð→ta)."""
    return AB.word_to_varnas(word)


def _prior_approval() -> bool:
    # Fresh approval is REQUIRED under the new mapping era; do NOT carry v2-era approval across a mapping change.
    if ITEMS_OUT.exists():
        try:
            return json.loads(ITEMS_OUT.read_text()).get("classification_approved") is True
        except Exception:  # noqa: BLE001
            return False
    return False


def build():
    table = json.loads(V3_TABLE.read_text())["varnas"]
    approved = _prior_approval()
    labels = AB.labels()

    items = []
    for i, (word, ctx, rtype, plane, correct) in enumerate(B0.ITEMS_SPEC, 1):
        vs = canonical_varnas(word)
        assert all(v in table for v in vs), f"{word}: out-of-table varṇa {vs}"
        assert len(vs) >= 2, f"{word}: thin ({vs})"
        items.append({"item_id": f"pd-{i:02d}", "target_text": word, "context_text": ctx,
                      "referent_type": rtype, "plane": plane, "correct_pole": correct,
                      "flipped_pole": B0.LIBERATING if correct == B0.BINDING else B0.BINDING, "varna_sequence": vs})

    items_doc = {
        "artifact_type": "b1_9_pole_did_items", "mapping_era": labels["mapping_era"], "table": labels["table"],
        "bridge": labels["bridge"], "aspiration_applied": labels["aspiration_applied"],
        "status": "APPROVED" if approved else "DRAFT_REQUIRES_FRESH_OPERATOR_SIGNOFF_UNDER_BUNDLE_V1",
        "representation_version": "B1.9_pole_did", "classification_approved": approved,
        "fresh_approval_note": "Mapping changed (v2/v1 -> fidelity_bundle_v1). v2-era classification_approved does "
                               "NOT carry over; the operator must re-approve the classification on the NEW packets.",
        "varna_derivation": "ACTIVE bundle: canonical Stage A′ (A_PRIME_EN) + combined bridge (retroflex t/d+r -> "
                            "ṭa/ḍa; /θ,ð/ merged th -> ta). G2P untouched. Aspiration EXCLUDED.",
        "not_comparable_note": "Bundle-era packets differ from v2/v1-era packets; results are NOT direct deltas "
                               "against v2/v1-era results. A more faithful mapping does not reopen prior nulls.",
        "source_hashes": {"varna_polarity_table_v3.json": _sha(V3_TABLE),
                          "varna_polarity_bridge_v3.json": _sha(BRIDGE_MANIFEST),
                          "stage_a_prime_coverage.py": _sha(DECOMPOSER)},
        "n_items": len(items), "n_liberating": sum(1 for x in items if x["correct_pole"] == B0.LIBERATING),
        "n_binding": sum(1 for x in items if x["correct_pole"] == B0.BINDING),
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "track_b_status": "BLOCKED", "items": items,
    }
    ITEMS_OUT.write_text(json.dumps(items_doc, ensure_ascii=False, indent=2))

    by = {x["item_id"]: x for x in items}
    wmap = B0._wprime_map([x["item_id"] for x in items])          # same seeded derangement as v2-era
    scaf_items = []
    for x in items:
        wp = by[wmap[x["item_id"]]]
        own, ctrl = x["varna_sequence"], wp["varna_sequence"]
        correct, flipped = x["correct_pole"], x["flipped_pole"]
        scaf_items.append({
            "item_id": x["item_id"], "TARGET_TEXT": x["target_text"], "CONTEXT_TEXT": x["context_text"],
            "REFERENT_TYPE": x["referent_type"], "PLANE": x["plane"],
            "CORRECT_POLE": correct, "FLIPPED_POLE": flipped, "varnas": own,
            "wprime_item_id": wp["item_id"], "wprime_target_text": wp["target_text"], "wprime_varnas": ctrl,
            "ARM_FACETS": {
                "OWN_CORRECT_POLE":     B0._pole_facets(own,  correct, table),
                "OWN_FLIPPED_POLE":     B0._pole_facets(own,  flipped, table),
                "CONTROL_CORRECT_POLE": B0._pole_facets(ctrl, correct, table),
                "CONTROL_FLIPPED_POLE": B0._pole_facets(ctrl, flipped, table),
            },
        })
    scaf = {
        "artifact_type": "b1_9_pole_did_scaffold", "status": "FROZEN_BUNDLE_V1",
        "mapping_era": labels["mapping_era"], "table": labels["table"], "bridge": labels["bridge"],
        "representation_version": "B1.9_pole_did", "classification_approved": approved,
        "wprime_seed": B0.WPRIME_SEED,
        "source_hashes": {"b1_9_pole_did_items_bundle_v1.json": _sha(ITEMS_OUT),
                          "varna_polarity_table_v3.json": _sha(V3_TABLE)},
        "not_comparable_note": items_doc["not_comparable_note"],
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "n_items": len(scaf_items), "items": scaf_items,
    }
    SCAF_OUT.write_text(json.dumps(scaf, ensure_ascii=False, indent=2))
    return items_doc, scaf


if __name__ == "__main__":
    idoc, scaf = build()
    print(f"wrote {ITEMS_OUT.name} + {SCAF_OUT.name} | items={idoc['n_items']} "
          f"approved={idoc['classification_approved']} era={idoc['mapping_era']}")
    print(f"items sha    : {_sha(ITEMS_OUT)}")
    print(f"scaffold sha : {_sha(SCAF_OUT)}")
    # show the one sequence that changes
    for it in idoc["items"]:
        if it["target_text"] == "dread":
            print("  dread sequence (bundle):", it["varna_sequence"])
