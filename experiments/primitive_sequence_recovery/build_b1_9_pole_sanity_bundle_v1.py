"""Re-derive the B1.9 pole-sanity items + scaffold under the ACTIVE Fidelity Bundle v1 mapping
(v3 table + combined bridge). Reads the BUNDLE pole-DiD items (sequences under the active bridge) and the v3 table
(pole facets). Synonyms/opposites reuse the same WordNet harvest + overrides as the v2-era pole-sanity builder.

Produces NEW *_bundle_v1.json artifacts; the v2-era pole-sanity files are left byte-unchanged. Fresh sign-off is
REQUIRED: word_groups_approved is reset to false (v2-era approval, if any, does NOT carry across a mapping-era
change). Mapping labels stamped. Resonance / phonetic-fidelity refinement only — no GENUTILITY_*, no
ONTOLOGICAL_SIGNAL, no semantic-truth/ontology/Sanskrit-privilege claim. B1.4b′ remains NULL_RETURN_BOTTOM.
Original B1.4b + Track B remain blocked.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

import build_b1_9_pole_sanity_scaffold as PS   # reuse harvest/_pole_facets/_first_gloss/_load_overrides/etc.
import varna_bridge_active as AB

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V3_TABLE = FROZEN / "varna_polarity_table_v3.json"
POLE_ITEMS = FROZEN / "b1_9_pole_did_items_bundle_v1.json"   # bundle-era source (active sequences/poles)
ITEMS_OUT = FROZEN / "b1_9_pole_sanity_items_bundle_v1.json"
SCAF_OUT = FROZEN / "b1_9_pole_sanity_scaffold_bundle_v1.json"


def _sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _prior_approval() -> bool:
    if ITEMS_OUT.exists():
        try:
            return json.loads(ITEMS_OUT.read_text()).get("word_groups_approved") is True
        except Exception:  # noqa: BLE001
            return False
    return False


def build():
    table = json.loads(V3_TABLE.read_text())["varnas"]
    pole = json.loads(POLE_ITEMS.read_text())
    approved = _prior_approval()
    overrides = PS._load_overrides()
    labels = AB.labels()
    itemset = {p["target_text"].lower() for p in pole["items"]}

    items, flags = [], []
    for p in pole["items"]:
        w = p["target_text"]
        correct = p["correct_pole"]
        ov = overrides.get(w, {})
        syns = PS._curated_entries(ov["synonyms"], "synonym")[:PS.TARGET_SYN] if ov.get("synonyms") \
            else PS.harvest_synonyms(w, itemset)
        opps = PS._curated_entries(ov["opposites"], "opposite")[:PS.TARGET_OPP] if ov.get("opposites") \
            else PS.harvest_opposites(w, [s["word"] for s in syns])
        needs = []
        if len(syns) < PS.TARGET_SYN and not ov.get("synonyms"):
            needs.append(f"synonyms {len(syns)}/{PS.TARGET_SYN} — curate via overrides")
        if len(opps) < PS.TARGET_OPP and not ov.get("opposites"):
            needs.append(f"opposites {len(opps)}/{PS.TARGET_OPP} — curate via overrides")
        if not opps:
            needs.append("NO opposites — item cannot form D_opposite / INT until curated")
        if needs:
            flags.append({"item_id": p["item_id"], "word": w, "status": PS.NEEDS, "issues": needs})
        target_entry = {"word": w, "role": "target", "gloss": PS._first_gloss(w), "synset": None, "source": "target"}
        items.append({
            "item_id": p["item_id"], "target_text": w, "context_text": p["context_text"],
            "plane": p["plane"], "correct_pole": correct, "varna_sequence": p["varna_sequence"],
            "correct_pole_facets": PS._pole_facets(p["varna_sequence"], correct, table),   # v3 facets
            "synonyms": syns, "opposites": opps,
            "candidate_words": [w] + [s["word"] for s in syns] + [o["word"] for o in opps],
            "forbidden_words": sorted({c.lower() for c in ([w] + [s["word"] for s in syns] + [o["word"] for o in opps])}),
            "needs_manual_replacement": needs,
        })

    items_doc = {
        "artifact_type": "b1_9_pole_sanity_items", "mapping_era": labels["mapping_era"], "table": labels["table"],
        "bridge": labels["bridge"], "aspiration_applied": labels["aspiration_applied"],
        "status": "APPROVED" if approved else "DRAFT_REQUIRES_FRESH_OPERATOR_SIGNOFF_UNDER_BUNDLE_V1",
        "representation_version": "B1.9_pole_sanity", "word_groups_approved": approved,
        "fresh_approval_note": "Mapping changed (v2/v1 -> fidelity_bundle_v1). word_groups_approved does NOT carry "
                               "over; operator must re-approve the synonym/opposite table on the NEW packets.",
        "packet_source": "v3 table pole facets; sequences from the active bundle bridge.",
        "not_comparable_note": "Bundle-era packets differ from v2/v1-era; results are NOT direct deltas. A more "
                               "faithful mapping does not reopen prior nulls.",
        "source_hashes": {"varna_polarity_table_v3.json": _sha(V3_TABLE),
                          "b1_9_pole_did_items_bundle_v1.json": _sha(POLE_ITEMS)},
        "n_items": len(items), "n_need_manual": len(flags), "coverage_flags": flags,
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "track_b_status": "BLOCKED", "items": items,
    }
    ITEMS_OUT.write_text(json.dumps(items_doc, ensure_ascii=False, indent=2))
    scaf = {
        "artifact_type": "b1_9_pole_sanity_scaffold", "status": "FROZEN_BUNDLE_V1",
        "mapping_era": labels["mapping_era"], "table": labels["table"], "bridge": labels["bridge"],
        "representation_version": "B1.9_pole_sanity", "word_groups_approved": approved,
        "source_hashes": {"b1_9_pole_sanity_items_bundle_v1.json": _sha(ITEMS_OUT)},
        "not_comparable_note": items_doc["not_comparable_note"],
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "n_items": len(items), "items": items,
    }
    SCAF_OUT.write_text(json.dumps(scaf, ensure_ascii=False, indent=2))
    return items_doc


if __name__ == "__main__":
    idoc = build()
    print(f"wrote {ITEMS_OUT.name} + {SCAF_OUT.name} | items={idoc['n_items']} "
          f"word_groups_approved={idoc['word_groups_approved']} need_manual={idoc['n_need_manual']} "
          f"era={idoc['mapping_era']}")
    print(f"items sha: {_sha(ITEMS_OUT)} | scaffold sha: {_sha(SCAF_OUT)}")
