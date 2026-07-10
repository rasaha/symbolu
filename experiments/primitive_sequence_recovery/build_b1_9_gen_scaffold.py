"""Deterministic builder for the B1.9 GENERATION scaffold (docs/data build; NO model, NO generation, NO network).

Reads the frozen B1.9 targets, the v2 named-vṛtti table, the frozen distant-source map, and the B1.8
context-resolved scaffold (for its frozen resolver decisions), and writes
frozen/b1_9_gen_targets_scaffolds.json with, per item, the facet bullet lists for each generation arm:

  Resolver-free (named_attribute root gloss; NO pole selected — matches the B1.9 embedding test):
    AUTHENTIC_MAPPING            = W's OWN varṇa named_attribute facets
    DISTANT_SOURCE_MAPPING       = W′'s OWN varṇa named_attribute facets (W′ = frozen distant source; CORRECTED)
  Context-resolved poles (B1.8 resolver picks ONE pole per word from context; SAME selected polarity per pair):
    AUTHENTIC_RESOLVED_POLE      = W's varṇas at W's selected pole (== B1.8 KCPR_SELECTED text)
    DISTANT_SOURCE_RESOLVED_POLE = W′'s varṇas at W's SAME selected pole (CORRECTED control, resolved)
  Comparison control:
    SCRAMBLED_WITHIN_POOL        = seeded within-pool derangement of W's varṇas (OLD B1.8-style control)

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
B1_8_SCAFFOLD_FILE = FROZEN / "b1_8_context_resolved_targets_scaffolds.json"
OUT_FILE = FROZEN / "b1_9_gen_targets_scaffolds.json"

SCRAMBLE_SEED = 20260710


def _seq_varnas(item):
    out = []
    for v in item["varna_sequence"]:
        k = v.get("varna") if isinstance(v, dict) else v
        if k and k not in out:
            out.append(k)
    return out


def _resolved_facets(varnas, pole_field, table):
    """One facet per varṇa = the text of the SELECTED pole (worldly_binding_distortion OR
    spiritual_liberating_reading). Same rendering B1.8 KCPR_SELECTED used; dedup preserved order."""
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
    b18 = {t["item_id"]: t for t in json.loads(B1_8_SCAFFOLD_FILE.read_text())["targets"]}
    by_id = {t["item_id"]: t for t in targets["targets"]}
    all_varnas = list(table.keys())

    items = []
    for t in targets["targets"]:
        iid = t["item_id"]
        auth_v = _seq_varnas(t)
        src_id = dmap[iid]
        src = by_id[src_id]
        src_v = _seq_varnas(src)
        pole = b18[iid]["RESOLVER_DECISION"]         # 'worldly_binding_distortion' | 'spiritual_liberating_reading'
        sel_plane = b18[iid]["SELECTED_PLANE"]
        auth_resolved = _resolved_facets(auth_v, pole, table)
        # sanity: authentic resolved text must equal B1.8's frozen KCPR_SELECTED text for W
        b18_texts = [f["text"] for f in b18[iid]["KCPR_LAYER1_SELECTED_FRAME"].values()]
        assert [f["text"] for f in auth_resolved] == list(dict.fromkeys(b18_texts)), f"resolved mismatch {iid}"
        items.append({
            "item_id": iid,
            "TARGET_TEXT": t["target_text"],
            "CONTEXT_TEXT": t["context_text"],
            "STRATUM": t["stratum"],
            "PLANE": t["plane"],
            "SELECTED_POLE": pole,
            "SELECTED_PLANE": sel_plane,
            "authentic_varnas": auth_v,
            "distant_source_item_id": src_id,
            "distant_source_target_text": src["target_text"],
            "distant_source_varnas": src_v,
            "ARM_FACETS": {
                "AUTHENTIC_MAPPING": _facets(auth_v, table),
                "DISTANT_SOURCE_MAPPING": _facets(src_v, table),
                "AUTHENTIC_RESOLVED_POLE": auth_resolved,
                "DISTANT_SOURCE_RESOLVED_POLE": _resolved_facets(src_v, pole, table),
                "SCRAMBLED_WITHIN_POOL": _scramble_within_pool(iid, auth_v, all_varnas, table),
            },
        })

    doc = {
        "artifact_type": "b1_9_gen_targets_scaffolds",
        "status": "FROZEN",
        "representation_version": "B1.9_generation_corrected_control",
        "facet_field": "named_attribute",
        "primary_contrast_resolver_free": "AUTHENTIC_MAPPING vs DISTANT_SOURCE_MAPPING",
        "primary_contrast_resolved": "AUTHENTIC_RESOLVED_POLE vs DISTANT_SOURCE_RESOLVED_POLE",
        "scramble_seed": SCRAMBLE_SEED,
        "source_hashes": {
            "b1_9_targets.json": hashlib.sha256(TARGETS_FILE.read_bytes()).hexdigest(),
            "track_g_varna_polarity_table_v2_named_vritti.json": hashlib.sha256(V2_TABLE_FILE.read_bytes()).hexdigest(),
            "b1_9_gen_distant_source_map.json": hashlib.sha256(DISTANT_MAP_FILE.read_bytes()).hexdigest(),
            "b1_8_context_resolved_targets_scaffolds.json": hashlib.sha256(B1_8_SCAFFOLD_FILE.read_bytes()).hexdigest(),
        },
        "note": "Two corrected primary contrasts: (resolver-free) AUTHENTIC_MAPPING vs DISTANT_SOURCE_MAPPING on "
                "named_attribute, and (resolved) AUTHENTIC_RESOLVED_POLE vs DISTANT_SOURCE_RESOLVED_POLE where W's "
                "context-selected pole (from B1.8) is applied to W's vs W′'s varṇas. SCRAMBLED_WITHIN_POOL is the "
                "old near-synonym control. Baselines carry no facets. NO generation. B1.4b′ NULL_RETURN_BOTTOM.",
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
              f"({it['distant_source_target_text']:8}) pole={it['SELECTED_POLE'][:9]:9} "
              f"auth={len(it['ARM_FACETS']['AUTHENTIC_MAPPING'])} "
              f"dist={len(it['ARM_FACETS']['DISTANT_SOURCE_MAPPING'])} "
              f"authR={len(it['ARM_FACETS']['AUTHENTIC_RESOLVED_POLE'])} "
              f"distR={len(it['ARM_FACETS']['DISTANT_SOURCE_RESOLVED_POLE'])}")
