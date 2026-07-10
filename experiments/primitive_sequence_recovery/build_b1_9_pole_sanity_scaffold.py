"""Deterministic builder for the B1.9 POLE-LOGIC SANITY scaffold (docs/data build; NO model, NO generation).

Pole-logic sanity/coherence check ONLY. For each target word W we take W's OWN varṇa facet packets at the
referent-CORRECT pole and at the FLIPPED pole, and (later) have blind judges rate 1-7 how DIRECTLY each packet
describes each of: W + synonyms (same pole) and opposite/contrast words (opposite pole). Primary statistic
(at aggregation):

    D_target   = mean(correct-pole fit to W/synonyms) − mean(flipped-pole fit to W/synonyms)      # expect > 0
    D_opposite = mean(correct-pole fit to opposites)  − mean(flipped-pole fit to opposites)        # expect < 0
    INT = D_target − D_opposite                                                                    # expect > 0

This tests only whether the two pole labels behave as coherent, directional descriptors. It does NOT test
ontology, Sanskrit privilege, semantic truth, generation utility, or word-specific varṇa mapping. NO generation,
NO readings — packets are the RAW facet text from the frozen v2 table.

Reuses the APPROVED b1_9_pole_did_items (all 24 words; canonical consonant-only varṇas; referent correct/flipped
poles). Synonyms from WordNet noun synsets; opposites from WordNet antonyms then filled from the OPPOSITE-POLE word
pool (the other 11-12 items). Each candidate carries a sense gloss so ratings are sense-clear and uniform (no
target-vs-distractor tell). Words with < TARGET_SYN clean synonyms are FLAGGED (not dropped — all 24 are kept) for
the operator to fill by hand. The word-group table is a DRAFT and must be operator-APPROVED
(word_groups_approved=true) BEFORE any run — anti-circularity, exactly like the pole classification.

No GENUTILITY_*, no ONTOLOGICAL_SIGNAL, no ontology/semantic-truth/Sanskrit-privilege claim. Consonant-only
(vowels dropped — inherited limitation). B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
POLE_ITEMS_FILE = FROZEN / "b1_9_pole_did_items.json"          # APPROVED source of words/varṇas/poles/context
ITEMS_FILE = FROZEN / "b1_9_pole_sanity_items.json"
SCAFFOLD_FILE = FROZEN / "b1_9_pole_sanity_scaffold.json"

TARGET_SYN = 4
TARGET_OPP = 4
BINDING = "worldly_binding_distortion"
LIBERATING = "spiritual_liberating_reading"


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


def harvest_synonyms(word, itemset):
    """WordNet noun synonyms: primary synset first, then fill. Single-token lemmas; exclude the word and other
    item words. Sense-tagged. May return fewer than TARGET_SYN (flagged, not dropped)."""
    from nltk.corpus import wordnet as wn
    key = word.replace("-", "_")
    syns = []
    for ss in wn.synsets(key, pos=wn.NOUN):
        for l in ss.lemmas():
            n = l.name().replace("_", " ")
            nl = n.lower()
            if " " in n or nl == word.lower() or nl in itemset:
                continue
            if nl not in {s["word"].lower() for s in syns}:
                syns.append({"word": n, "role": "synonym", "gloss": ss.definition(), "synset": ss.name(),
                             "source": "wordnet_synset"})
        if len(syns) >= TARGET_SYN:
            break
    return syns[:TARGET_SYN]


def harvest_opposites(word, syn_words, opposite_pool):
    """WordNet antonyms of W and its synonyms first (direct contrast); then fill from the opposite-pole word pool
    to TARGET_OPP. Sense-tagged with source. `opposite_pool` = list of the opposite-pole item words (dicts)."""
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
                    opp.append({"word": n, "role": "opposite", "gloss": _first_gloss(n),
                                "synset": None, "source": "wordnet_antonym"})
    for pw in opposite_pool:
        if len(opp) >= TARGET_OPP:
            break
        nl = pw["word"].lower()
        if nl in seen:
            continue
        seen.add(nl)
        opp.append({"word": pw["word"], "role": "opposite", "gloss": pw["gloss"],
                    "synset": None, "source": "opposite_pole_pool"})
    return opp[:TARGET_OPP]


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
    src = pole["items"]
    itemset = {p["target_text"].lower() for p in src}
    # opposite-pole pools: liberating words <-> binding words
    lib_pool = [{"word": p["target_text"], "gloss": _first_gloss(p["target_text"])}
                for p in src if p["correct_pole"] == LIBERATING]
    bind_pool = [{"word": p["target_text"], "gloss": _first_gloss(p["target_text"])}
                 for p in src if p["correct_pole"] == BINDING]

    items, flags = [], []
    for p in src:
        w = p["target_text"]
        correct, flipped = p["correct_pole"], p["flipped_pole"]
        syns = harvest_synonyms(w, itemset)
        opp_pool = bind_pool if correct == LIBERATING else lib_pool
        opps = harvest_opposites(w, [s["word"] for s in syns], opp_pool)
        if len(syns) < TARGET_SYN:
            flags.append({"word": w, "issue": f"only {len(syns)}/{TARGET_SYN} WordNet synonyms — operator fill"})
        if len(opps) < TARGET_OPP:
            flags.append({"word": w, "issue": f"only {len(opps)}/{TARGET_OPP} opposites — operator fill"})
        target_entry = {"word": w, "role": "target", "gloss": _first_gloss(w), "synset": None, "source": "target"}
        items.append({
            "item_id": p["item_id"], "target_text": w, "context_text": p["context_text"],
            "plane": p["plane"], "correct_pole": correct, "flipped_pole": flipped,
            "varna_sequence": p["varna_sequence"],
            "correct_packet": _pole_facets(p["varna_sequence"], correct, table),
            "flipped_packet": _pole_facets(p["varna_sequence"], flipped, table),
            "target": target_entry, "synonyms": syns, "opposites": opps,
            # W + synonyms are the "target/synonyms" role-group; opposites are the "opposite/contrast" group
            "candidate_pool": [target_entry, *syns, *opps],
        })

    items_doc = {
        "artifact_type": "b1_9_pole_sanity_items",
        "status": "APPROVED" if approved else "DRAFT_REQUIRES_OPERATOR_SIGNOFF",
        "representation_version": "B1.9_pole_sanity", "word_groups_approved": approved,
        "question": "Do W's correct-pole facets read as directly describing W/synonyms, and W's flipped-pole "
                    "facets as describing the opposite-pole words? (pole-label coherence only)",
        "primary_statistic": "INT = D_target − D_opposite; "
                             "D_target = mean(correct fit to W/syn) − mean(flipped fit to W/syn); "
                             "D_opposite = mean(correct fit to opposites) − mean(flipped fit to opposites).",
        "expected_if_coherent": "D_target > 0, D_opposite < 0, INT > 0.",
        "scope_disclaimer": "Pole-logic sanity ONLY. NOT ontology, Sanskrit privilege, semantic truth, generation "
                            "utility, or word-specific varṇa mapping. No generation, no readings.",
        "packet_source": "RAW correct/flipped facet text from track_g_varna_polarity_table_v2 for W's canonical "
                         "consonant-only varṇas (reused from the APPROVED pole-DiD items). No new derivation.",
        "synonym_source": "WordNet noun synsets (primary first, then fill); single-token; item words excluded; "
                          "sense-tagged.",
        "opposite_source": "WordNet antonyms of W and its synonyms first (direct contrast); filled from the "
                           "OPPOSITE-POLE item-word pool to reach TARGET_OPP. Each tagged with its source.",
        "sense_gloss_note": "Every candidate (target/synonym/opposite) carries a WordNet sense gloss so ratings are "
                            "sense-clear and UNIFORM (no target-vs-distractor tell). W's narrative context_text is "
                            "recorded for sense selection but is NOT shown to blind judges (it names W).",
        "curation_warning": "WordNet fill can cross senses and the opposite-pole-pool fills are pole-opposite not "
                            "strict antonyms. OPERATOR MUST review every synonym/opposite sense before approval and "
                            "hand-edit weak entries; do NOT approve mismatched senses.",
        "vowel_omission_limitation": "Consonant-only (inherited). Vowels VOWEL_NO_PROFILE and dropped; adding vowels "
                                     "needs a sourced table + new representation + separate prereg — NOT here.",
        "anti_circularity": "Approve (word_groups_approved=true) BEFORE any rating run. Do not revise after seeing "
                            "any rating.",
        "source_hashes": {"track_g_varna_polarity_table_v2_named_vritti.json": _sha(V2_TABLE_FILE),
                          "b1_9_pole_did_items.json": _sha(POLE_ITEMS_FILE)},
        "target_synonyms_per_item": TARGET_SYN, "target_opposites_per_item": TARGET_OPP,
        "n_items": len(items), "coverage_flags": flags,
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "items": items,
    }
    ITEMS_FILE.write_text(json.dumps(items_doc, ensure_ascii=False, indent=2))

    scaf = {
        "artifact_type": "b1_9_pole_sanity_scaffold", "status": "FROZEN",
        "representation_version": "B1.9_pole_sanity",
        "primary_statistic": items_doc["primary_statistic"], "word_groups_approved": approved,
        "source_hashes": {"b1_9_pole_sanity_items.json": _sha(ITEMS_FILE),
                          "track_g_varna_polarity_table_v2_named_vritti.json": _sha(V2_TABLE_FILE)},
        "note": "Direct packet-rating sanity test (NO generation). Each of W's correct/flipped packets is rated "
                "1-7 for DIRECT fit against W+synonyms and opposite words; anti-contrastive instruction. "
                "INT crossover = pole-label coherence. B1.4b′ NULL_RETURN_BOTTOM.",
        "n_items": len(items), "items": items,
    }
    SCAFFOLD_FILE.write_text(json.dumps(scaf, ensure_ascii=False, indent=2))
    return items_doc, scaf


if __name__ == "__main__":
    idoc, scaf = build()
    print(f"wrote {ITEMS_FILE.name} + {SCAFFOLD_FILE.name} | items={idoc['n_items']} "
          f"flags={len(idoc['coverage_flags'])} approved={idoc['word_groups_approved']}")
    for it in scaf["items"]:
        print(f"  {it['item_id']} {it['target_text']:12} {it['correct_pole'].split('_')[0]:8} "
              f"syn={[s['word'] for s in it['synonyms']]} opp={[o['word'] for o in it['opposites']]}")
    if idoc["coverage_flags"]:
        print("  FLAGS:", idoc["coverage_flags"])
