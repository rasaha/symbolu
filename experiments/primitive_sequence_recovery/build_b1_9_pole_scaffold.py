"""Deterministic builder for the B1.9 POLE-SENSITIVITY scaffold (docs/data build; NO model, NO generation).

For each word W, renders TWO facet sets over W's OWN varṇas that differ in EXACTLY ONE thing — the pole:
  POLE_CORRECT  = W's varṇas at the pole assigned by the frozen referent-ontology rule
                  (frozen/b1_9_pole_referent_classification.json)
  POLE_FLIPPED  = W's varṇas at the OPPOSITE pole
Same word, same context, same varṇas, same plane. Only the pole text (worldly_binding_distortion vs
spiritual_liberating_reading) changes. This isolates whether the binding/liberating RESOLUTION carries meaning,
with zero content confound. B1.4b′ remains NULL_RETURN_BOTTOM.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
TARGETS_FILE = FROZEN / "b1_9_targets.json"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
CLASSIFICATION_FILE = FROZEN / "b1_9_pole_referent_classification.json"
OUT_FILE = FROZEN / "b1_9_pole_scaffold.json"

BINDING = "worldly_binding_distortion"
LIBERATING = "spiritual_liberating_reading"


def _seq_varnas(item):
    out = []
    for v in item["varna_sequence"]:
        k = v.get("varna") if isinstance(v, dict) else v
        if k and k not in out:
            out.append(k)
    return out


def _pole_facets(varnas, pole_field, table):
    out, seen = [], set()
    for v in varnas:
        e = table.get(v)
        if not e:
            continue
        t = str(e.get(pole_field, "")).strip()
        if t and t not in seen:
            seen.add(t)
            out.append({"varna": v, "text": t})
    return out


def build():
    targets = json.loads(TARGETS_FILE.read_text())
    table = json.loads(V2_TABLE_FILE.read_text())["varnas"]
    cls = json.loads(CLASSIFICATION_FILE.read_text())
    correct_by = {c["item_id"]: c["correct_pole"] for c in cls["items"]}

    items = []
    for t in targets["targets"]:
        iid = t["item_id"]
        vs = _seq_varnas(t)
        correct = correct_by[iid]
        flipped = LIBERATING if correct == BINDING else BINDING
        items.append({
            "item_id": iid,
            "TARGET_TEXT": t["target_text"],
            "CONTEXT_TEXT": t["context_text"],
            "STRATUM": t["stratum"],
            "PLANE": t["plane"],
            "CORRECT_POLE": correct,
            "FLIPPED_POLE": flipped,
            "varnas": vs,
            "ARM_FACETS": {
                "POLE_CORRECT": _pole_facets(vs, correct, table),
                "POLE_FLIPPED": _pole_facets(vs, flipped, table),
            },
        })

    doc = {
        "artifact_type": "b1_9_pole_scaffold",
        "status": "FROZEN",
        "representation_version": "B1.9_pole_sensitivity",
        "primary_contrast": "POLE_CORRECT vs POLE_FLIPPED",
        "classification_approved": cls.get("classification_approved", False),
        "source_hashes": {
            "b1_9_targets.json": hashlib.sha256(TARGETS_FILE.read_bytes()).hexdigest(),
            "track_g_varna_polarity_table_v2_named_vritti.json": hashlib.sha256(V2_TABLE_FILE.read_bytes()).hexdigest(),
            "b1_9_pole_referent_classification.json": hashlib.sha256(CLASSIFICATION_FILE.read_bytes()).hexdigest(),
        },
        "note": "POLE_CORRECT vs POLE_FLIPPED differ ONLY in pole (same word/varṇas/context/plane). Correct pole "
                "from the frozen referent-ontology classification. NO generation. B1.4b′ NULL_RETURN_BOTTOM.",
        "n_items": len(items),
        "items": items,
    }
    OUT_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    return doc


if __name__ == "__main__":
    d = build()
    print("wrote", OUT_FILE.name, "| items:", d["n_items"], "| classification_approved:", d["classification_approved"])
    for it in d["items"]:
        print(f"  {it['item_id']} {it['TARGET_TEXT']:8} correct={it['CORRECT_POLE'].split('_')[0]:9} "
              f"flipped={it['FLIPPED_POLE'].split('_')[0]:9} "
              f"nfacets={len(it['ARM_FACETS']['POLE_CORRECT'])}")
