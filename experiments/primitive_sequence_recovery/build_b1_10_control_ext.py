"""Build the FROZEN items for the B1.10 CONTROL EXTENSION (three packet tiers; mock-only; 6 words).

Stays inside B1.10. Creates NEW, separately-labeled files; leaves the original B1.10 pilot artifacts
(b1_10_pole_context_microtest_items.json, b1_10_EVIDENCE_FREEZE_DECLARED.json, the run artifact, the results record)
byte-unchanged.

Six words: pride, freedom, patience, courage, control, doubt. For each: two contexts (binding / liberating) with a
frozen expected pole, and SIX packets = 3 tiers x 2 poles:
  Tier 1 (valence)          — fixed generic negative / positive pools (hedonic tone only).
  Tier 2 (source_condition) — fixed generic other-conditioned / self-grounded pools (word/varṇa-agnostic).
  Tier 3 (specific)         — the word's v3 binding/liberating facets, PARAPHRASED to plain English, each clause
                              keeping HIDDEN provenance back to its original v3 facet.

All three tiers share one plain-English template (~9-13 words, "a/an <quality> <state> that <clause>"), no Sanskrit,
no varṇa/pole/system/target-word tokens. Per-word facet count N matches the v3 count (pride 3, freedom 3,
patience 4, courage 3, control 5, doubt 3); Tier-1/Tier-2 take the first N pool facets.

Resonance / phonetic-fidelity refinement only — no GENUTILITY_*, no ONTOLOGICAL_SIGNAL, no semantic-truth /
ontology / Sanskrit-privilege claim. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b + Track B blocked.
Structure, not validated meaning. No result label is produced here.
"""
from __future__ import annotations
import hashlib
import json
import pathlib
import re
from typing import Dict, List

import varna_bridge_active as AB
import build_b1_9_pole_did_scaffold as B0   # BINDING / LIBERATING field-name constants

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V3_TABLE = FROZEN / "varna_polarity_table_v3.json"
BRIDGE_MANIFEST = FROZEN / "varna_polarity_bridge_v3.json"
DECOMPOSER = HERE / "stage_a_prime_coverage.py"
ITEMS_OUT = FROZEN / "b1_10_control_ext_items.json"

WORDS = ("pride", "freedom", "patience", "courage", "control", "doubt")
JACCARD_CAP = 0.2   # Tier-2 vs Tier-3 content-lemma overlap cap (spec §5)

# ------------------------------------------------------------------ contexts + expected poles (frozen for this ext)
CONTEXTS = {
    "pride":    {"binding": "His pride fed on looking down at those beneath him, and curdled to contempt when outshone.",
                 "liberating": "Her pride was a quiet self-respect that needed no one's inferiority to stand."},
    "freedom":  {"binding": "His freedom was license: he indulged every impulse until nothing held together.",
                 "liberating": "Her freedom was inner and self-possessed, needing no escape and breaking nothing."},
    "patience": {"binding": "His patience was grudging, a resentful waiting that seethed under a still surface.",
                 "liberating": "Her patience was alert and willing, resting easily in the pace of things."},
    "courage":  {"binding": "His courage was bravado to be seen, driven by dread of looking weak before others.",
                 "liberating": "Her courage rose quietly from within, acting rightly whether or not anyone watched."},
    "control":  {"binding": "His control gripped every detail of her life, tightening whenever she slipped his hold.",
                 "liberating": "Her control was calm self-mastery: she governed her reactions and let others be free."},
    "doubt":    {"binding": "His doubt corroded everything, dismissing worth and sinking him into dull paralysis.",
                 "liberating": "Her doubt was honest inquiry that weighed things fairly and woke her mind up."},
}
EXPECTED_POLE = {"binding": "binding", "liberating": "liberating"}   # context -> expected pole

# ------------------------------------------------------------------ Tier 1: generic valence (fixed pools)
TIER1_NEG = [
    "a heavy aching mood that quietly weighs the whole body down",
    "a raw unpleasant feeling that sits sourly deep inside the chest",
    "a dull grey flatness that drains the colour out of everything",
    "a sharp uncomfortable soreness that keeps prickling away under the skin",
    "a bleak sinking tone that darkens whatever it happens to touch",
]
TIER1_POS = [
    "a light glad mood that gently lifts the whole body up",
    "a warm pleasant feeling that spreads slowly deep inside the chest",
    "a bright clear tone that adds fresh colour back to everything",
    "a soft agreeable smoothness that feels easy and quietly rather nice",
    "a fresh cheerful lift that brightens whatever it happens to touch",
]
# ------------------------------------------------------------------ Tier 2: generic source-condition (fixed pools)
# Same "a <adj> <state> that <clause>" frame as Tiers 1 & 3 (no uniform "a state that" tell; no commas).
TIER2_OTHER = [
    "a contingent mood that depends on how other people respond",
    "a needy restlessness that wants an outside result to feel whole",
    "a comparing tension that keeps sizing itself up against others",
    "a clutching unease that grips what it holds and dreads loss",
    "a propped-up confidence that leans on approval from other people",
]
TIER2_SELF = [
    "a self-resting calm that stays steady without needing anyone else",
    "a full contentment that needs no outside result to feel whole",
    "an unmeasuring ease that never sizes itself up against others",
    "a light-handed openness that holds things loosely and lets go",
    "a self-standing steadiness that needs no approval from anyone else",
]
# ------------------------------------------------------------------ Tier 3: per-varṇa plain-English render map
# keyed (varna, pole) -> plain-English clause. Shared varṇas across words get IDENTICAL renders (consistent
# provenance). Covers the 11 varṇas appearing in the six words: pa ra da ma ta na ka ga tta ba la.
VARNA_PLAIN = {
    ("pa", "binding"): "a contemptuous feeling that looks down on others and recoils",
    ("pa", "liberating"): "a warm goodwill that turns upward and wishes others well",
    ("ra", "binding"): "a collapsing sense that everything is lost and completely undone",
    ("ra", "liberating"): "a strong steady energy that moves forward with a sure resolve",
    ("da", "binding"): "a prickly reactivity that takes offence and snaps back at people",
    ("da", "liberating"): "an even unbothered steadiness that does not flare up under provocation",
    ("ma", "binding"): "a loose over-indulgence that spills outward until things fall apart",
    ("ma", "liberating"): "a disciplined restraint that holds its shape and does not spill over",
    ("ta", "binding"): "a dull sluggish heaviness that slowly sinks toward a sleepy torpor",
    ("ta", "liberating"): "an alert wakefulness that rises out of dullness into clear attention",
    ("na", "binding"): "a blind fixation that clings to one thing and loses reason",
    ("na", "liberating"): "a clear detachment that loosens fixation and frees the mind again",
    ("ka", "binding"): "a grasping hope that clutches hard at a wanted result",
    ("ka", "liberating"): "an open hopefulness that acts without clutching at the result",
    ("ga", "binding"): "a restless striving that drives on and cannot ever stop",
    ("ga", "liberating"): "a purposeful effort that works hard then rests in poise",
    ("tta", "binding"): "a bad-tempered over-talking that argues on far past the point",
    ("tta", "liberating"): "a measured to-the-point way of saying just what helps",
    ("ba", "binding"): "a careless disregard that overlooks what actually has real worth",
    ("ba", "liberating"): "an attentive regard that notices and honours what has worth",
    ("la", "binding"): "a cruel harshness that would harm the weak without care",
    ("la", "liberating"): "a protective kindness that shields the weak and eases their pain",
}


def _sha(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _dedup(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for v in seq:
        if v not in seen:
            seen.add(v); out.append(v)
    return out


_STOP = set("a an the that of to and in on it its into with without at as is are be "
            "how no not any all up down out from other others itself things".split())


def _content_lemmas(clauses: List[str]) -> set:
    toks = re.findall(r"[a-z]+", " ".join(clauses).lower())
    return {t for t in toks if t not in _STOP and len(t) > 2}


def _jaccard(a: set, b: set) -> float:
    return (len(a & b) / len(a | b)) if (a | b) else 0.0


def build() -> Dict:
    table = json.loads(V3_TABLE.read_text())["varnas"]
    words = []
    for w in WORDS:
        seq = _dedup(AB.word_to_varnas(w))
        n = len(seq)
        # Tier 3 specific packets (paraphrase + hidden provenance to v3 facet)
        spec = {}
        for pole_key, pole_field in (("binding", B0.BINDING), ("liberating", B0.LIBERATING)):
            facets = []
            for v in seq:
                plain = VARNA_PLAIN[(v, pole_key)]
                facets.append({"text": plain,
                               "provenance_varna": v,
                               "provenance_v3_facet": table[v][pole_field]})   # HIDDEN provenance
            spec[pole_key] = facets
        # Tier 1 / Tier 2 take first N pool facets (generic; no varṇa provenance)
        val = {"binding": [{"text": t} for t in TIER1_NEG[:n]],
               "liberating": [{"text": t} for t in TIER1_POS[:n]]}
        sc = {"binding": [{"text": t} for t in TIER2_OTHER[:n]],
              "liberating": [{"text": t} for t in TIER2_SELF[:n]]}
        # per-word Tier-2 vs Tier-3 overlap audit
        t3 = _content_lemmas([f["text"] for f in spec["binding"]] + [f["text"] for f in spec["liberating"]])
        t2 = _content_lemmas([f["text"] for f in sc["binding"]] + [f["text"] for f in sc["liberating"]])
        jac = round(_jaccard(t2, t3), 4)
        assert jac <= JACCARD_CAP, f"{w}: Tier2/Tier3 content Jaccard {jac} > {JACCARD_CAP}"
        words.append({
            "word": w, "varna_sequence": seq, "facet_count": n,
            "contexts": CONTEXTS[w], "expected_pole": EXPECTED_POLE,
            "packets": {"valence": val, "source_condition": sc, "specific": spec},
            "tier2_tier3_content_jaccard": jac,
        })

    doc = {
        "artifact_type": "b1_10_control_ext_items",
        "extension_of": "B1.10_pole_context", "mapping_era": AB.MAPPING_ERA, "table": AB.TABLE, "bridge": AB.BRIDGE,
        "aspiration_applied": AB.ASPIRATION_APPLIED,
        "status": "FROZEN_CONTROL_EXT_MOCK_ONLY",
        "representation_version": "B1.10_control_ext",
        "words_included": list(WORDS),
        "tiers": {"1_valence": "generic hedonic tone only",
                  "2_source_condition": "generic other-conditioned vs self-grounded (word/varṇa-agnostic)",
                  "3_specific": "word's v3 binding/liberating facets paraphrased to plain English (hidden provenance)"},
        "judge_question": ("How well does this description describe the inner experiential weather or "
                           "source-condition underlying this word in this context?"),
        "rating_scale": {"min": 0, "max": 6, "meaning": "0 = not at all, 6 = extremely well"},
        "tier1_fixed": {"negative_pool": TIER1_NEG, "positive_pool": TIER1_POS},
        "tier2_fixed": {"other_conditioned_pool": TIER2_OTHER, "self_grounded_pool": TIER2_SELF},
        "jaccard_cap": JACCARD_CAP,
        "packet_invariance_note": "Packets are context-invariant; only the context changes which pole should fit. "
                                  "All three tiers are plain-English, register/length-matched.",
        "source_hashes": {"varna_polarity_table_v3.json": _sha(V3_TABLE),
                          "varna_polarity_bridge_v3.json": _sha(BRIDGE_MANIFEST),
                          "stage_a_prime_coverage.py": _sha(DECOMPOSER)},
        "interpretation_note": "No result label emitted. increment_over_valence and increment_over_source_condition "
                               "are the primary comparisons; a positive result would show source-condition / "
                               "resonance legibility to judges ONLY — not ontology, semantic truth, Sanskrit "
                               "privilege, generation utility, or word-specific varṇa mapping.",
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "track_b_status": "BLOCKED",
        "n_words": len(words), "words": words,
    }
    ITEMS_OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    return doc


if __name__ == "__main__":
    d = build()
    print(f"wrote {ITEMS_OUT.name} | words={d['n_words']} ({', '.join(d['words_included'])})")
    for w in d["words"]:
        print(f"  {w['word']:9} N={w['facet_count']} tier2/tier3 jaccard={w['tier2_tier3_content_jaccard']}")
    print(f"items sha: {_sha(ITEMS_OUT)}")
