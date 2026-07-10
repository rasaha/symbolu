"""Deterministic builder for the B1.9 GENERATION scaffold (docs/data build; NO model, NO generation, NO network).

Reads the frozen B1.9 targets, the v2 named-vṛtti table, and the frozen distant-source map, and writes
frozen/b1_9_gen_targets_scaffolds.json with, per item, the facet bullet lists for each generation arm:

  AUTHENTIC_MAPPING        = W's OWN varṇa named_attribute facets (same content the B1.9 embedding test used)
  DISTANT_SOURCE_MAPPING   = W′'s OWN varṇa named_attribute facets (W′ = frozen distant source; CORRECTED control)
  SCRAMBLED_WITHIN_POOL    = seeded within-pool derangement of W's varṇas (the OLD B1.8-style control; carried
                             only for direct comparison, clearly secondary)

Baselines (PLAIN / GENERIC_STRUCTURED / SEMANTIC) carry no facets. B1.4b′ remains NULL_RETURN_BOTTOM.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
TARGETS_FILE = FROZEN / "b1_9_targets.json"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
DISTANT_MAP_FILE = FROZEN / "b1_9_gen_distant_source_map.json"
OUT_FILE = FROZEN / "b1_9_gen_targets_scaffolds.json"

SCRAMBLE_SEED = 20260710


def _seq_varnas(item):
    out = []
    for v in item["varna_sequence"]:
        k = v.get("varna") if isinstance(v, dict) else v
        if k and k not in out:
            out.append(k)
    return out


def _facets(varnas, table):
    """One facet per varṇa = its named_attribute (same field the B1.9 embedding test aggregated)."""
    out, seen = [], set()
    for v in varnas:
        e = table.get(v)
        if not e:
            continue
        t = str(e.get("named_attribute", "")).strip()
        if t and t not in seen:
            seen.add(t)
            out.append({"varna": v, "text": t})
    return out


def _rng(*parts):
    import random
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _scramble_within_pool(item_id, auth_varnas, all_varnas, table):
    """Seeded derangement: each authentic varṇa -> a DIFFERENT varṇa (outside W's own set) whose named_attribute
    is used. This is the within-pool near-synonym control the corrected design replaces; kept for comparison."""
    pool = [v for v in all_varnas if v not in auth_varnas]
    rng = _rng(SCRAMBLE_SEED, item_id)
    rng.shuffle(pool)
    picked = pool[:len(auth_varnas)]
    return _facets(picked, table)


def build():
    targets = json.loads(TARGETS_FILE.read_text())
    table = json.loads(V2_TABLE_FILE.read_text())["varnas"]
    dmap = json.loads(DISTANT_MAP_FILE.read_text())["map"]
    by_id = {t["item_id"]: t for t in targets["targets"]}
    all_varnas = list(table.keys())

    items = []
    for t in targets["targets"]:
        iid = t["item_id"]
        auth_v = _seq_varnas(t)
        src_id = dmap[iid]
        src = by_id[src_id]
        src_v = _seq_varnas(src)
        items.append({
            "item_id": iid,
            "TARGET_TEXT": t["target_text"],
            "CONTEXT_TEXT": t["context_text"],
            "STRATUM": t["stratum"],
            "PLANE": t["plane"],
            "authentic_varnas": auth_v,
            "distant_source_item_id": src_id,
            "distant_source_target_text": src["target_text"],
            "distant_source_varnas": src_v,
            "ARM_FACETS": {
                "AUTHENTIC_MAPPING": _facets(auth_v, table),
                "DISTANT_SOURCE_MAPPING": _facets(src_v, table),
                "SCRAMBLED_WITHIN_POOL": _scramble_within_pool(iid, auth_v, all_varnas, table),
            },
        })

    doc = {
        "artifact_type": "b1_9_gen_targets_scaffolds",
        "status": "FROZEN",
        "representation_version": "B1.9_generation_corrected_control",
        "facet_field": "named_attribute",
        "primary_contrast": "AUTHENTIC_MAPPING vs DISTANT_SOURCE_MAPPING",
        "scramble_seed": SCRAMBLE_SEED,
        "source_hashes": {
            "b1_9_targets.json": hashlib.sha256(TARGETS_FILE.read_bytes()).hexdigest(),
            "track_g_varna_polarity_table_v2_named_vritti.json": hashlib.sha256(V2_TABLE_FILE.read_bytes()).hexdigest(),
            "b1_9_gen_distant_source_map.json": hashlib.sha256(DISTANT_MAP_FILE.read_bytes()).hexdigest(),
        },
        "note": "AUTHENTIC vs DISTANT_SOURCE is the corrected primary control (W′ = frozen distant source word, "
                "its OWN authentic varṇa facets). SCRAMBLED_WITHIN_POOL is the old near-synonym control, kept for "
                "comparison only. Baselines carry no facets. NO generation performed. B1.4b′ NULL_RETURN_BOTTOM.",
        "n_items": len(items),
        "items": items,
    }
    OUT_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    return doc


if __name__ == "__main__":
    d = build()
    print("wrote", OUT_FILE.name, "| items:", d["n_items"])
    for it in d["items"]:
        print(f"  {it['item_id']} {it['TARGET_TEXT']:8} -> distant {it['distant_source_item_id']} "
              f"({it['distant_source_target_text']})  "
              f"auth={len(it['ARM_FACETS']['AUTHENTIC_MAPPING'])} "
              f"dist={len(it['ARM_FACETS']['DISTANT_SOURCE_MAPPING'])} "
              f"scr={len(it['ARM_FACETS']['SCRAMBLED_WITHIN_POOL'])}")
