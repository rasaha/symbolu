"""Deterministic builder for the B1.9 POLE-LOGIC SANITY scaffold (docs/data build; NO model, NO generation).

Pole-logic sanity/coherence check ONLY. For each target word W we take W's OWN varṇa facet packets at the
referent-CORRECT pole and at the FLIPPED pole, and (later) have blind judges rate 1-7 how DIRECTLY each packet
describes each of: W + synonyms (same sense/pole) and opposite/contrast words (true antonyms). Two PRIMARY
diagnostics at aggregation:

    INT     = (correct→target/syn + flipped→opposites) − (flipped→target/syn + correct→opposites)   # coherence
    Cell ①  = correct-pole packet fit to target/synonyms                                            # word-level fit

INT>0 alone shows only pole-label/valence coherence; a HIGH Cell ① is required to claim the correct packet
directly fits the word-family. INT positive but Cell ① low => the test does NOT support word-level packet coherence.

CURATED-CONTRAST MODE (this version):
  - synonyms  = PRIMARY WordNet noun synset lemmas only (tight, same-sense) — this removes cross-sense noise like
                lock→curl / terror→brat (those came from OTHER synsets). Operator curates the final list.
  - opposites = TRUE WordNet antonyms of W (and its primary-synset synonyms) ONLY. The opposite-pole ITEM-WORD pool
                is NO LONGER used (it made INT mostly measure generic binding/liberating valence).
  - operator overrides: frozen/b1_9_pole_sanity_overrides.json (word -> {synonyms:[...], opposites:[...]}) is merged
                and takes precedence, so the operator's curated same-sense synonyms + true antonyms survive rebuilds.
  - any short/verb-antonym/wrong-sense slot is FLAGGED as NEEDS_MANUAL_REPLACEMENT (never silently pool-filled).

Reuses the APPROVED b1_9_pole_did_items (all 24 words; canonical consonant-only varṇas; referent correct/flipped
poles) for the packets. The word-group table is a DRAFT and must be operator-APPROVED (word_groups_approved=true)
BEFORE any run — anti-circularity. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL, no ontology/semantic-truth/Sanskrit-
privilege claim. Consonant-only (inherited). B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
POLE_ITEMS_FILE = FROZEN / "b1_9_pole_did_items.json"          # APPROVED source of words/varṇas/poles/context
OVERRIDES_FILE = FROZEN / "b1_9_pole_sanity_overrides.json"    # operator-curated synonyms/opposites (merged; wins)
ITEMS_FILE = FROZEN / "b1_9_pole_sanity_items.json"
SCAFFOLD_FILE = FROZEN / "b1_9_pole_sanity_scaffold.json"

TARGET_SYN = 4
TARGET_OPP = 4
BINDING = "worldly_binding_distortion"
LIBERATING = "spiritual_liberating_reading"
NEEDS = "NEEDS_MANUAL_REPLACEMENT"


def _sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


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


def _first_gloss(word):
    from nltk.corpus import wordnet as wn
    ss = wn.synsets(word.replace("-", "_"), pos=wn.NOUN) or wn.synsets(word.replace("-", "_"))
    return ss[0].definition() if ss else ""


def _has_noun_sense(word):
    from nltk.corpus import wordnet as wn
    return bool(wn.synsets(word.replace(" ", "_").replace("-", "_"), pos=wn.NOUN))


def harvest_synonyms(word, itemset):
    """PRIMARY WordNet noun synset ONLY (tight, same-sense). Single-token lemmas; exclude W and other item words.
    Filling from other synsets is DELIBERATELY not done (that is what produced lock→curl / terror→brat)."""
    from nltk.corpus import wordnet as wn
    sss = wn.synsets(word.replace("-", "_"), pos=wn.NOUN)
    if not sss:
        return []
    primary = sss[0]
    out = []
    for l in primary.lemmas():
        n = l.name().replace("_", " ")
        nl = n.lower()
        if " " in n or nl == word.lower() or nl in itemset:
            continue
        if nl not in {s["word"].lower() for s in out}:
            out.append({"word": n, "role": "synonym", "gloss": primary.definition(),
                        "synset": primary.name(), "source": "wordnet_primary_synset"})
    return out[:TARGET_SYN]


def harvest_opposites(word, syn_words):
    """TRUE WordNet antonyms of W and its primary-synset synonyms ONLY. NO opposite-pole item-word fill. Each is
    tagged noun_sense (verb-only antonyms like 'agitate' are flagged so the operator can replace with a noun)."""
    from nltk.corpus import wordnet as wn
    opp, seen = [], {word.lower(), *[s.lower() for s in syn_words]}
    for probe in [word, *syn_words]:
        for ss in wn.synsets(probe.replace("-", "_")):
            for l in ss.lemmas():
                for a in l.antonyms():
                    n = a.name().replace("_", " ")
                    nl = n.lower()
                    if " " in n or nl in seen:
                        continue
                    seen.add(nl)
                    opp.append({"word": n, "role": "opposite", "gloss": _first_gloss(n), "synset": None,
                                "source": "wordnet_antonym", "noun_sense": _has_noun_sense(n)})
    return opp[:TARGET_OPP]


def _load_overrides():
    """Operator-curated synonyms/opposites. Keys starting with '_' are notes and ignored. Empty arrays => no
    override for that field (fall back to auto-harvest + flag)."""
    if OVERRIDES_FILE.exists():
        try:
            d = json.loads(OVERRIDES_FILE.read_text())
            return {k: v for k, v in d.items() if not k.startswith("_")}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _curated_entries(words, role):
    out = []
    for w in words:
        out.append({"word": w, "role": role, "gloss": _first_gloss(w), "synset": None,
                    "source": "operator_curated", **({"noun_sense": _has_noun_sense(w)} if role == "opposite" else {})})
    return out


def _prior_approval() -> bool:
    if ITEMS_FILE.exists():
        try:
            return json.loads(ITEMS_FILE.read_text()).get("word_groups_approved") is True
        except Exception:  # noqa: BLE001
            return False
    return False


def build():
    table = json.loads(V2_TABLE_FILE.read_text())["varnas"]
    pole = json.loads(POLE_ITEMS_FILE.read_text())
    assert pole.get("classification_approved") is True, "pole-DiD classification must be approved (source of truth)"
    approved = _prior_approval()
    overrides = _load_overrides()
    src = pole["items"]
    itemset = {p["target_text"].lower() for p in src}

    items, flags = [], []
    for p in src:
        w = p["target_text"]
        correct, flipped = p["correct_pole"], p["flipped_pole"]
        ov = overrides.get(w, {})
        # synonyms: operator override wins; else PRIMARY-synset only
        if ov.get("synonyms"):
            syns = _curated_entries(ov["synonyms"], "synonym")[:TARGET_SYN]
        else:
            syns = harvest_synonyms(w, itemset)
        # opposites: operator override wins; else TRUE antonyms only (no pool fill)
        if ov.get("opposites"):
            opps = _curated_entries(ov["opposites"], "opposite")[:TARGET_OPP]
        else:
            opps = harvest_opposites(w, [s["word"] for s in syns])

        needs = []
        if len(syns) < TARGET_SYN and not ov.get("synonyms"):
            needs.append(f"synonyms {len(syns)}/{TARGET_SYN} (primary-synset only) — add same-sense synonyms via overrides")
        if len(opps) < TARGET_OPP and not ov.get("opposites"):
            needs.append(f"opposites {len(opps)}/{TARGET_OPP} (WordNet antonyms only) — add TRUE antonyms/contrast via overrides")
        bad_pos = [o["word"] for o in opps if o.get("noun_sense") is False]
        if bad_pos:
            needs.append(f"opposites lack a noun sense (verb antonyms?) — replace via overrides: {bad_pos}")
        if not opps:
            needs.append("NO opposites — item cannot form D_opposite / INT until opposites are curated")
        if needs:
            flags.append({"item_id": p["item_id"], "word": w, "status": NEEDS, "issues": needs})

        target_entry = {"word": w, "role": "target", "gloss": _first_gloss(w), "synset": None, "source": "target"}
        items.append({
            "item_id": p["item_id"], "target_text": w, "context_text": p["context_text"],
            "plane": p["plane"], "correct_pole": correct, "flipped_pole": flipped,
            "varna_sequence": p["varna_sequence"],
            "correct_packet": _pole_facets(p["varna_sequence"], correct, table),
            "flipped_packet": _pole_facets(p["varna_sequence"], flipped, table),
            "target": target_entry, "synonyms": syns, "opposites": opps,
            "candidate_pool": [target_entry, *syns, *opps],
            "needs_manual_replacement": needs,
            "curation_status": "operator_curated" if (ov.get("synonyms") and ov.get("opposites")) else
                               ("wordnet_draft_needs_curation" if needs else "wordnet_draft"),
        })

    fully = sum(1 for it in items if it["curation_status"] == "operator_curated")
    items_doc = {
        "artifact_type": "b1_9_pole_sanity_items",
        "status": "APPROVED" if approved else "DRAFT_REQUIRES_OPERATOR_SIGNOFF",
        "representation_version": "B1.9_pole_sanity", "word_groups_approved": approved,
        "question": "Do W's correct-pole facets read as directly describing W/synonyms, and W's flipped-pole "
                    "facets as describing true opposite/contrast words? (pole-label + word-level coherence)",
        "primary_diagnostics": {
            "INT": "(correct→target/syn + flipped→opposites) − (flipped→target/syn + correct→opposites)",
            "cell_1": "correct-pole packet fit to target/synonyms"},
        "interpretation_rule": "INT>0 alone => pole-label/VALENCE coherence only. Cell① HIGH is REQUIRED to claim "
                               "the correct packet directly fits the word-family. INT positive but Cell① low => "
                               "does NOT support word-level packet coherence.",
        "scope_disclaimer": "Pole-logic sanity ONLY. NOT ontology, Sanskrit privilege, semantic truth, generation "
                            "utility, or word-specific varṇa mapping. No generation, no readings.",
        "packet_source": "RAW correct/flipped facet text from track_g_varna_polarity_table_v2 for W's canonical "
                         "consonant-only varṇas (reused from the APPROVED pole-DiD items). No new derivation.",
        "synonym_source": "PRIMARY WordNet noun synset ONLY (tight same-sense); NO cross-synset fill (that produced "
                          "lock→curl / terror→brat). Operator override wins.",
        "opposite_source": "TRUE WordNet antonyms of W and its synonyms ONLY. Opposite-pole ITEM-WORD pool is NOT "
                           "used (it made INT measure generic binding/liberating valence). Operator override wins.",
        "overrides_file": OVERRIDES_FILE.name + " (word -> {synonyms:[...], opposites:[...]}); merged & takes "
                          "precedence; survives rebuilds. Fill it to curate same-sense synonyms + true antonyms.",
        "curation_warning": f"{NEEDS} items must be hand-curated via the overrides file before approval. Do NOT "
                            "approve wrong-sense synonyms or verb 'antonyms'. Do not revise after seeing any rating.",
        "vowel_omission_limitation": "Consonant-only (inherited). Vowels VOWEL_NO_PROFILE and dropped; adding vowels "
                                     "needs a sourced table + new representation + separate prereg — NOT here.",
        "anti_circularity": "Approve (word_groups_approved=true) BEFORE any rating run. Gate refuses otherwise.",
        "source_hashes": {"track_g_varna_polarity_table_v2_named_vritti.json": _sha(V2_TABLE_FILE),
                          "b1_9_pole_did_items.json": _sha(POLE_ITEMS_FILE),
                          "b1_9_pole_sanity_overrides.json": _sha(OVERRIDES_FILE) if OVERRIDES_FILE.exists() else None},
        "target_synonyms_per_item": TARGET_SYN, "target_opposites_per_item": TARGET_OPP,
        "n_items": len(items), "n_fully_curated": fully, "n_need_manual": len(flags),
        "coverage_flags": flags, "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "items": items,
    }
    ITEMS_FILE.write_text(json.dumps(items_doc, ensure_ascii=False, indent=2))

    scaf = {
        "artifact_type": "b1_9_pole_sanity_scaffold", "status": "FROZEN",
        "representation_version": "B1.9_pole_sanity",
        "primary_diagnostics": items_doc["primary_diagnostics"], "word_groups_approved": approved,
        "source_hashes": {"b1_9_pole_sanity_items.json": _sha(ITEMS_FILE),
                          "track_g_varna_polarity_table_v2_named_vritti.json": _sha(V2_TABLE_FILE)},
        "note": "Direct packet-rating sanity test (NO generation). Curated-contrast opposites (true antonyms, not "
                "opposite-pole item words). Two primary diagnostics: INT (coherence) + Cell① (word-level fit). "
                "B1.4b′ NULL_RETURN_BOTTOM.",
        "n_items": len(items), "items": items,
    }
    SCAFFOLD_FILE.write_text(json.dumps(scaf, ensure_ascii=False, indent=2))
    return items_doc, scaf


if __name__ == "__main__":
    idoc, scaf = build()
    print(f"wrote {ITEMS_FILE.name} + {SCAFFOLD_FILE.name} | items={idoc['n_items']} "
          f"fully_curated={idoc['n_fully_curated']} need_manual={idoc['n_need_manual']} "
          f"approved={idoc['word_groups_approved']}")
    for it in scaf["items"]:
        tag = "" if not it["needs_manual_replacement"] else "  <<NEEDS_MANUAL"
        print(f"  {it['item_id']} {it['target_text']:12} {it['correct_pole'].split('_')[0]:8} "
              f"syn={[s['word'] for s in it['synonyms']]} opp={[o['word'] for o in it['opposites']]}{tag}")
