"""Deterministic builder for the B1.9 POLE DIFF-IN-DIFF scaffold (docs/data build; NO model, NO generation).

CANONICAL varṇa derivation ONLY: stage_a_prime_coverage.normalize(word, "A_PRIME_EN") + the frozen
b1_6_phoneme_to_varna_bridge_manifest.json CONSONANT_ONLY_BRIDGE mapping — the exact path that produced the
B1.6/B1.8/B1.9 targets (verified to reproduce all 12 existing sequences). Vowels -> VOWEL_NO_PROFILE and f/z/zh ->
UNSUPPORTED_NO_VARNA are dropped (consonant-only; vowels NOT invented — see the prereg §Vowel-omission limitation).
No dedup of the varṇa sequence (repeats kept, matching the existing convention e.g. lantern -> la,na,ta,ra,na).

Builds the balanced 24-item set (12 liberating + 12 binding) and the 4-arm diff-in-diff scaffold:
  OWN_CORRECT_POLE / OWN_FLIPPED_POLE          = W's own varṇas at W's referent-correct / flipped pole
  CONTROL_CORRECT_POLE / CONTROL_FLIPPED_POLE  = a distant word W′'s varṇas at W's correct / flipped pole
Primary statistic (at aggregation): DiD = (OWN_CORRECT - OWN_FLIPPED) - (CONTROL_CORRECT - CONTROL_FLIPPED).
W′ is a frozen seeded derangement (no fixed point), chosen with NO reference to any output/score. Correct pole is
fixed by the referent-ontology rule and must be operator-APPROVED before any run. B1.4b′ remains NULL_RETURN_BOTTOM.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

import stage_a_prime_coverage as A   # CANONICAL decomposer (A_PRIME_EN)

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
BRIDGE_FILE = FROZEN / "b1_6_phoneme_to_varna_bridge_manifest.json"
DECOMPOSER_FILE = HERE / "stage_a_prime_coverage.py"
ITEMS_FILE = FROZEN / "b1_9_pole_did_items.json"
SCAFFOLD_FILE = FROZEN / "b1_9_pole_did_scaffold.json"

BINDING = "worldly_binding_distortion"
LIBERATING = "spiritual_liberating_reading"
WPRIME_SEED = 20260712

LIB = "subjectified-mental (release/realization)"
CONTRACTION = "subjectified-mental (contraction)"
PHYSICAL = "physical"
ITEMS_SPEC = [
    ("surrender",  "After years of resisting, his surrender softened the fear and opened him to peace.",           LIB, "spiritual",    LIBERATING),
    ("release",    "With one quiet breath, release moved through her body and the old clinging fell away.",          LIB, "spiritual",    LIBERATING),
    ("forgiveness","Forgiveness arose in him, not as approval of the wound, but as freedom from carrying it.",       LIB, "mental",       LIBERATING),
    ("awakening",  "The awakening came silently, as if a veil had lifted and the mind became clear.",                LIB, "spiritual",    LIBERATING),
    ("acceptance", "Acceptance settled in her heart, and the struggle against what had happened began to dissolve.", LIB, "mental",       LIBERATING),
    ("clarity",    "In stillness, clarity appeared, and the tangled fear no longer ruled his choices.",              LIB, "intellectual", LIBERATING),
    ("insight",    "The insight broke through his old pattern, showing him he was not bound by the thought.",         LIB, "intellectual", LIBERATING),
    ("letting-go", "Letting-go was not defeat; it was the moment the grip of craving loosened.",                     LIB, "mental",       LIBERATING),
    ("peace",      "Peace arose within him when the need to win finally disappeared.",                               LIB, "spiritual",    LIBERATING),
    ("compassion", "Compassion opened where judgment had been, and the heart no longer felt closed.",               LIB, "mental",       LIBERATING),
    ("equanimity", "Equanimity held steady even as praise and blame rose and passed.",                              LIB, "mental",       LIBERATING),
    ("liberation", "Liberation was felt as the end of inner bondage, not as escape from the world.",                LIB, "spiritual",    LIBERATING),
    ("anchor",     "The iron anchor lay embedded in the seabed, its heavy flukes gripping the mud and holding the hull fast.", PHYSICAL, "physical", BINDING),
    ("cage",       "The steel cage stood bolted to the floor, its bars fixed and immovable.",                       PHYSICAL, "physical", BINDING),
    ("chain",      "The rusted chain bound the gate shut, each link clamped hard to the next.",                     PHYSICAL, "physical", BINDING),
    ("wall",       "The concrete wall sealed off the yard, blocking every path through it.",                        PHYSICAL, "physical", BINDING),
    ("lock",       "The padlock held the door shut, its bolt seized and unyielding.",                               PHYSICAL, "physical", BINDING),
    ("weight",     "The lead weight pressed down on the lid, pinning it in place.",                                 PHYSICAL, "physical", BINDING),
    ("terror",     "Terror seized him and froze him at the threshold, unable to step forward.",                     CONTRACTION, "mental", BINDING),
    ("craving",    "Craving gnawed at her, driving one grasping purchase after another.",                           CONTRACTION, "mental", BINDING),
    ("dread",      "A cold dread of failure kept him clinging and rigid, unable to move.",                          CONTRACTION, "mental", BINDING),
    ("resentment", "Resentment hardened in him, replaying the wrong and refusing to let it go.",                    CONTRACTION, "mental", BINDING),
    ("obsession",  "The obsession fixed his mind on a single thought he could not release.",                        CONTRACTION, "mental", BINDING),
    ("panic",      "Panic seized the crowd, each person gripping toward the exit in blind urgency.",                CONTRACTION, "mental", BINDING),
]


def _sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _bridge():
    return json.loads(BRIDGE_FILE.read_text())["bridge_table"]


def canonical_varnas(word: str, mapping) -> list:
    """word -> varṇa keys via canonical Stage A′ (A_PRIME_EN) + bridge mapping. Vowels/unsupported dropped; NO dedup."""
    phs = []
    for tok in word.split("-"):
        phs += A.normalize(tok, "A_PRIME_EN")["phonemes"]
    return [mapping[p] for p in phs if p in mapping]


def _wprime_map(item_ids):
    ordered = sorted(item_ids, key=lambda i: hashlib.sha256(f"{WPRIME_SEED}|{i}".encode()).hexdigest())
    n = len(ordered); shift = n // 2
    return {ordered[i]: ordered[(i + shift) % n] for i in range(n)}


def _pole_facets(varnas, pole_field, table):
    out, seen = [], set()
    for v in varnas:
        e = table.get(v)
        if not e:
            continue
        t = str(e.get(pole_field, "")).strip()
        if t and t not in seen:
            seen.add(t); out.append({"varna": v, "text": t})
    return out


def build():
    table = json.loads(V2_TABLE_FILE.read_text())["varnas"]
    mapping = _bridge()["mapping"]

    items = []
    for i, (word, ctx, rtype, plane, correct) in enumerate(ITEMS_SPEC, 1):
        vs = canonical_varnas(word, mapping)
        assert all(v in table for v in vs), f"{word}: out-of-table varṇa {vs}"
        assert len(vs) >= 2, f"{word}: thin ({vs})"
        items.append({"item_id": f"pd-{i:02d}", "target_text": word, "context_text": ctx,
                      "referent_type": rtype, "plane": plane, "correct_pole": correct,
                      "flipped_pole": LIBERATING if correct == BINDING else BINDING, "varna_sequence": vs})

    items_doc = {
        "artifact_type": "b1_9_pole_did_items", "status": "DRAFT_REQUIRES_OPERATOR_SIGNOFF",
        "representation_version": "B1.9_pole_did", "classification_approved": False,
        "rule": "correct pole from the referent-ontology rule (physical/objectified/contraction -> binding; "
                "subjective release/realization/transformation -> liberating). valence NOT used.",
        "varna_derivation": "CANONICAL: stage_a_prime_coverage.normalize(word,'A_PRIME_EN') + "
                            "b1_6_phoneme_to_varna_bridge_manifest.json mapping (consonant-only; vowels dropped; "
                            "reproduces all 12 existing B1.8/B1.9 sequences). NO dedup. NO invented vowel meanings.",
        "vowel_omission_limitation": "Consonant-only. Vowels are VOWEL_NO_PROFILE and dropped; this may "
                                     "underrepresent Sanskrit svara. Adding vowels requires a sourced vowel table, "
                                     "a new representation version, a new bridge, and a separate prereg — NOT done here.",
        "wprime_selection": f"frozen seeded derangement (seed {WPRIME_SEED}), no fixed point, NO use of any output/score.",
        "anti_circularity": "Approve (classification_approved=true) BEFORE any generation. Do not revise after seeing output.",
        "source_hashes": {"stage_a_prime_coverage.py": _sha(DECOMPOSER_FILE),
                          "b1_6_phoneme_to_varna_bridge_manifest.json": _sha(BRIDGE_FILE),
                          "track_g_varna_polarity_table_v2_named_vritti.json": _sha(V2_TABLE_FILE)},
        "n_items": len(items), "n_liberating": sum(1 for x in items if x["correct_pole"] == LIBERATING),
        "n_binding": sum(1 for x in items if x["correct_pole"] == BINDING),
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "items": items,
    }
    ITEMS_FILE.write_text(json.dumps(items_doc, ensure_ascii=False, indent=2))

    by = {x["item_id"]: x for x in items}
    wmap = _wprime_map([x["item_id"] for x in items])
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
                "OWN_CORRECT_POLE":     _pole_facets(own,  correct, table),
                "OWN_FLIPPED_POLE":     _pole_facets(own,  flipped, table),
                "CONTROL_CORRECT_POLE": _pole_facets(ctrl, correct, table),
                "CONTROL_FLIPPED_POLE": _pole_facets(ctrl, flipped, table),
            },
        })
    scaf = {
        "artifact_type": "b1_9_pole_did_scaffold", "status": "FROZEN", "representation_version": "B1.9_pole_did",
        "primary_statistic": "DiD = (OWN_CORRECT - OWN_FLIPPED) - (CONTROL_CORRECT - CONTROL_FLIPPED)",
        "classification_approved": items_doc["classification_approved"], "wprime_seed": WPRIME_SEED,
        "source_hashes": {"b1_9_pole_did_items.json": _sha(ITEMS_FILE),
                          "track_g_varna_polarity_table_v2_named_vritti.json": _sha(V2_TABLE_FILE)},
        "note": "4-arm diff-in-diff; canonical consonant-only varṇas; W′ frozen distant word (seeded derangement). "
                "NO generation. B1.4b′ NULL_RETURN_BOTTOM.",
        "n_items": len(scaf_items), "items": scaf_items,
    }
    SCAFFOLD_FILE.write_text(json.dumps(scaf, ensure_ascii=False, indent=2))
    return items_doc, scaf


if __name__ == "__main__":
    idoc, scaf = build()
    print(f"wrote {ITEMS_FILE.name} + {SCAFFOLD_FILE.name} | items={idoc['n_items']} "
          f"(lib={idoc['n_liberating']}, bind={idoc['n_binding']}) approved={idoc['classification_approved']}")
    for it in scaf["items"]:
        af = it["ARM_FACETS"]
        print(f"  {it['item_id']} {it['TARGET_TEXT']:12} {it['CORRECT_POLE'].split('_')[0]:9} "
              f"varṇas={','.join(it['varnas']):22} W'={it['wprime_target_text']:11} "
              f"own={len(af['OWN_CORRECT_POLE'])} ctrl={len(af['CONTROL_CORRECT_POLE'])}")
