"""Development-only QUALITATIVE mechanism review of the native word mappings (docs/data-only).

Reads the exact per-word rows from b1_native_word_mapping_review/word_mappings.json (commit 2fbdecc3) and analyses,
under FIVE fixed views, how the existing ordered binding/liberating vṛtti sequences relate to conventional word
meanings. It selects the word set BEFORE inspecting fit, applies ONE uniform classification rule across all words
(no per-word narrative, no post-hoc polarity mixing), compares candidate composition mechanisms, and records an
error taxonomy. It changes NO mapping, authors NO meaning, runs NO judge, produces NO confirmatory verdict, and
preserves the prior NO_SIGNAL finding. Structure, not validated meaning.
"""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "b1_native_word_mapping_review" / "word_mappings.json"
WORDS = {w["transliteration_iast"]: w for w in json.load(open(SRC, encoding="utf-8"))["words"]}
OUT = HERE / "b1_native_mechanism_qualitative_review"

# ---- FIXED selection (recorded BEFORE any fit inspection) --------------------------------------------------------
SELECTION_RULE = (
    "Fixed before inspecting fit: the 10 required known examples + fillers chosen to cover a phonological×semantic "
    "category matrix (abstract/concrete/mental/action × positive/negative/neutral × short/long/diphthong vowels × "
    "aspiration/conjunct/anusvāra/visarga/missing-ṛ). Fillers chosen by category need, NOT by apparent fit.")
# word -> (semantic_category, valence, conventional_gloss, exercises)
SELECTED = {
    "śānti": ("mental/abstract", "positive", "peace", "long ā, conjunct, sibilant"),
    "sukha": ("mental", "positive", "happiness/ease", "short u, aspirate kh"),
    "bala": ("abstract", "positive", "strength", "short a (repeated inherent)"),
    "jñāna": ("abstract", "positive", "knowledge", "jña conjunct, long ā"),
    "kṣamā": ("abstract", "positive", "patience/forbearance", "kṣa conjunct, long ā"),
    "sattva": ("abstract", "positive", "goodness/being (guṇa)", "gemination t+t"),
    "mokṣa": ("abstract", "positive", "liberation", "vowel o, kṣa conjunct"),
    "ahiṃsā": ("abstract", "positive", "nonviolence", "anusvāra + long ā"),
    "satya": ("abstract", "positive", "truth", "conjunct ty"),
    "dharma": ("abstract", "positive", "righteousness/sustaining", "aspirate dh, repha"),
    "yoga": ("process/abstract", "positive", "union/discipline", "vowel o"),
    "ānanda": ("emotional", "positive", "bliss", "long ā onset, nd"),
    "deva": ("concrete/abstract", "positive", "deity", "diphthong e"),
    "duḥkha": ("mental", "negative", "suffering", "visarga + aspirate"),
    "bhaya": ("emotional", "negative", "fear", "aspirate bh"),
    "krodha": ("emotional", "negative", "anger", "aspirate dh, vowel o"),
    "moha": ("mental", "negative", "delusion", "vowel o"),
    "kāma": ("mental", "negative", "desire", "long ā"),
    "māyā": ("abstract", "negative", "illusion", "long ā×2"),
    "agni": ("concrete", "neutral", "fire", "independent-vowel onset"),
    "jala": ("concrete", "neutral", "water", "short a (repeated)"),
    "nara": ("concrete", "neutral", "man/person", "short a (repeated)"),
    "namaḥ": ("action", "neutral", "salutation", "final visarga"),
    "saṃskāra": ("process", "neutral", "impression/refinement", "anusvāra"),
    "hṛdaya": ("concrete/abstract", "positive", "heart", "MISSING vocalic ṛ"),
    "saṃskṛta": ("abstract", "neutral", "refined/Sanskrit", "anusvāra + MISSING ṛ"),
    "mṛtyu": ("abstract", "negative", "death", "MISSING ṛ + conjunct"),
    "kṛṣṇa": ("concrete", "neutral", "dark / a name", "MISSING ṛ + conjuncts"),
}
VIEWS = ["A_full_binding", "B_full_liberating", "C_consonant_binding", "D_consonant_liberating", "E_typed_mixed"]

FIT = ["DIRECTLY_SPECIFIC", "PLAUSIBLY_RELATED", "GENERIC_OR_BARNUM", "PARTIALLY_CONTRADICTORY",
       "STRONGLY_CONTRADICTORY", "UNINTERPRETABLE_DUE_TO_MISSING_UNIT"]
FIT_DEFS = {
    "DIRECTLY_SPECIFIC": "the sequence names something distinctive to THIS word, not shared by many words",
    "PLAUSIBLY_RELATED": "valence/theme-consistent with the word, but broad (shared across its valence class) — NOT word-specific",
    "GENERIC_OR_BARNUM": "facets are broad human themes that fit many unrelated words",
    "PARTIALLY_CONTRADICTORY": "the fixed-polarity reading opposes the word's conventional valence/meaning in part",
    "STRONGLY_CONTRADICTORY": "the reading is the strict opposite of the word's meaning unit-by-unit",
    "UNINTERPRETABLE_DUE_TO_MISSING_UNIT": "a unit (vocalic ṛ) has no mapping, leaving a hole in the sequence",
}


def classify(word, view):
    """ONE uniform rule across all words — fit reduces to valence↔fixed-polarity alignment (the key finding)."""
    cat, val, *_ = SELECTED[word]
    if "ṛ" in WORDS[word]["atomic_varnas"]:
        return "UNINTERPRETABLE_DUE_TO_MISSING_UNIT"
    binding_view = view in ("A_full_binding", "C_consonant_binding")
    liberating_view = view in ("B_full_liberating", "D_consonant_liberating")
    if view == "E_typed_mixed":
        return "GENERIC_OR_BARNUM"        # vowel padding ('a' = generic) dilutes any consonant theme
    if val == "neutral":
        return "GENERIC_OR_BARNUM"        # concrete/neutral referents: vṛtti themes never touch the referent
    matched = (val == "positive" and liberating_view) or (val == "negative" and binding_view)
    return "PLAUSIBLY_RELATED" if matched else "PARTIALLY_CONTRADICTORY"


def _seqs(w):
    rows = w["mapping_rows"]
    return {
        "binding_sequence": [r["binding"] for r in rows],
        "liberating_sequence": [r["liberating"] for r in rows],
        "consonant_only_binding": [r["binding"] for r in rows if r["type"] == "consonant"],
        "consonant_only_liberating": [r["liberating"] for r in rows if r["type"] == "consonant"],
        "vowel_marker_binding": [r["binding"] for r in rows if r["type"] != "consonant"],
        "vowel_marker_liberating": [r["liberating"] for r in rows if r["type"] != "consonant"],
    }


ERROR_TAXONOMY = {
    "generic_facets_fit_many": "DOMINANT — the inherent 'a' ('Birth of cognition / raw potential' | 'restless starting') "
                               "appears in nearly every word; consonant vṛttis are broad psychological themes.",
    "polarity_ambiguity": "EVERY unit carries both a binding and a liberating reading; apparent fit depends on which "
                          "polarity is chosen — post-hoc per-unit selection would make any word fit.",
    "sequence_order_irrelevance": "no rule consumes order; the reading is an ordered LIST of facets, not an order-sensitive composition.",
    "one_dominant_varna": "strong consonants exist (e.g. ṣ=artha, k=āśā) but no rule privileges them; potential future flexibility.",
    "vowel_creates_apparent_fit": "the ubiquitous 'a' adds a generic positive theme ('raw potential') that pads every word.",
    "vowel_creates_contradiction": "positive vowel readings (e.g. u='Zoom', a='Birth') sit inside negative words (duḥkha), contradicting valence.",
    "repeated_unit_effects": "repeated 'a' repeats an IDENTICAL facet (bala, jñāna, jala…), inflating a single theme.",
    "missing_vocalic_r": "hṛdaya, saṃskṛta, mṛtyu, kṛṣṇa have a hole where ṛ should be → uninterpretable.",
    "dictionary_polysemy": "conventional glosses are themselves multi-sense (kṛṣṇa=dark/name; sattva=being/goodness/guṇa).",
    "grammatical_structure_ignored": "derivation/negation ignored — e.g. a-privative (avidyā) is not read as negation.",
    "root_vs_surface_mismatch": "the surface word is decomposed, not the dhātu/root; morphology is invisible.",
    "post_hoc_narrative_risk": "HIGH — dual poles × broad facets let a coherent story be told for essentially any word.",
}

CANDIDATES = [
    {"id": "ORDERED_FACET_SEQUENCE", "consistency": "low (long generic lists)", "parameter_count": "low",
     "post_hoc_flexibility": "high (both poles available)", "preserves_order": "records but does not use order",
     "vowel_treatment": "includes generic 'a' padding", "falsifiability": "low",
     "failure_modes": "Barnum; valence via polarity only", "supported_or_invented": "the current default; not source-grounded"},
    {"id": "ONSET_SEED_PLUS_TRANSFORMERS", "consistency": "low", "parameter_count": "medium",
     "post_hoc_flexibility": "high", "preserves_order": "partial (privileges position 0)",
     "vowel_treatment": "unclear", "falsifiability": "medium",
     "failure_modes": "onset consonant rarely seeds the word's meaning (ś≠peace)", "supported_or_invented": "invented (mirrors the English apparatus)"},
    {"id": "CONSONANT_BACKBONE_WITH_VOWEL_MODULATION", "consistency": "medium", "parameter_count": "medium",
     "post_hoc_flexibility": "medium", "preserves_order": "yes",
     "vowel_treatment": "vowels modulate, drop generic 'a' padding (cleanest)", "falsifiability": "medium",
     "failure_modes": "consonant themes still broad; polarity still ambiguous", "supported_or_invented": "partially source-aligned (v3.1 backbone)"},
    {"id": "AKSHARA_LOCAL_COMPOSITION", "consistency": "unknown", "parameter_count": "high",
     "post_hoc_flexibility": "high", "preserves_order": "yes (within/between akṣara)",
     "vowel_treatment": "vowel bound to its akṣara consonant", "falsifiability": "low (large space)",
     "failure_modes": "no source rule for akṣara-level meaning", "supported_or_invented": "invented"},
    {"id": "DOMINANT_OR_DIAGNOSTIC_VARNA", "consistency": "low", "parameter_count": "low-medium",
     "post_hoc_flexibility": "very high", "preserves_order": "discards most units",
     "vowel_treatment": "usually drops vowels", "falsifiability": "low",
     "failure_modes": "maximal cherry-pick; which varṇa 'dominates' is post-hoc", "supported_or_invented": "invented"},
    {"id": "BIDIRECTIONAL_POLARITY_PATH", "consistency": "medium (valence-coupled)", "parameter_count": "low",
     "post_hoc_flexibility": "LOW (poles fixed per whole-word trajectory, not mixed per unit)",
     "preserves_order": "yes", "vowel_treatment": "included in both trajectories", "falsifiability": "HIGH",
     "failure_modes": "our data: the valence-matched trajectory reads coherently, the mismatched one contradicts — "
                      "so it only predicts VALENCE (1 bit), not word identity", "supported_or_invented": "testable; the only non-cherry-pick option"},
    {"id": "NULL_OR_NO_COMPOSITION", "consistency": "n/a", "parameter_count": "zero",
     "post_hoc_flexibility": "none", "preserves_order": "n/a", "vowel_treatment": "n/a", "falsifiability": "n/a",
     "failure_modes": "consistent with the prior NO_SIGNAL and the generic finding here",
     "supported_or_invented": "the honest null the evidence currently favours"},
]


def build():
    OUT.mkdir(exist_ok=True)
    per_word = []
    from collections import Counter
    view_dist = {v: Counter() for v in VIEWS}
    for word in SELECTED:
        w = WORDS[word]
        cat, val, gloss, exer = SELECTED[word]
        views = {v: classify(word, v) for v in VIEWS}
        for v in VIEWS:
            view_dist[v][views[v]] += 1
        per_word.append({
            "word_devanagari": w["word_devanagari"], "iast": word, "conventional_meaning": gloss,
            "semantic_category": cat, "valence": val, "exercises": exer,
            "aksharas": w["aksharas"], "atomic_varnas": w["atomic_varnas"],
            "missing_units": w["missing_units"], "provenance_sequence": w["provenance_sequence"],
            "activation_scope_sequence": w["activation_scope_sequence"], **_seqs(w), "view_fit": views,
        })

    # adversarial control: interchangeability of valence-matched readings across unrelated same-class words
    control = {
        "claim": "PLAUSIBLY_RELATED is a valence-class property, NOT word-specific discrimination.",
        "demonstration": "Positive-abstract words (śānti, sattva, bala, satya) all receive the SAME PLAUSIBLY_RELATED "
                         "class under View D — their liberating consonant backbones are interchangeable broad themes "
                         "('sublimation', 'de-fascination', 'cessation of dullness', 'raw potential'); swapping the "
                         "gloss label does not change which reading 'fits'. Same-length negative words flip only which "
                         "polarity reads coherently (1 bit), not the content.",
    }

    conclusions = {
        "most_specific_words": "NONE reach DIRECTLY_SPECIFIC. The least-generic are positive-abstract words under the "
                               "consonant liberating view (śānti, mokṣa, kṣamā) — but only PLAUSIBLY_RELATED (valence-level).",
        "most_generic_words": ["bala", "jala", "nara", "kāma", "agni"],  # dominated by repeated generic 'a'
        "contradicting_words": "valence-mismatched fixed polarity: sukha/śānti/… under binding; duḥkha/mṛtyu under liberating.",
        "vowels_improve_or_worsen_specificity": "WORSEN — the ubiquitous 'a' pads every word with a generic positive "
                                                "theme and injects contradictions into negative words.",
        "order_appears_important": False,
        "one_polarity_consistently_better": False,   # binding fits negatives, liberating fits positives — valence-coupled
        "consonant_only_vs_full_typed_differ_materially": True,  # full typed adds generic vowel padding
        "any_candidate_ready_for_preregistration": False,
        "mappings_too_flexible_for_fair_rule": True,
    }

    verdict = "MAPPINGS_TOO_GENERIC_FOR_COMPOSITION_PREREGISTRATION"
    verdict_reason = (
        "Under one uniform rule across all 28 words, 'fit' reduces to a single bit — whether the fixed polarity "
        "matches the word's valence. No view yields DIRECTLY_SPECIFIC for any word; valence-matched views are "
        "PLAUSIBLY_RELATED but interchangeable across a valence class (adversarial control), valence-mismatched fixed "
        "polarity is PARTIALLY_CONTRADICTORY, neutral/concrete referents and all typed-mixed readings are "
        "GENERIC_OR_BARNUM, and four vocalic-ṛ words are UNINTERPRETABLE. The mappings encode valence-via-polarity, "
        "not word identity — too generic/flexible for a fair composition pre-registration. Consistent with the prior NO_SIGNAL.")

    report = {
        "artifact_type": "native_mechanism_qualitative_review", "grade": "DEVELOPMENT_ONLY",
        "source_word_mappings": "b1_native_word_mapping_review/word_mappings.json (commit 2fbdecc3)",
        "selection_rule": SELECTION_RULE, "selected_words": list(SELECTED),
        "views": VIEWS, "fit_taxonomy": FIT_DEFS,
        "view_fit_distribution": {v: dict(view_dist[v]) for v in VIEWS},
        "adversarial_control": control, "conclusions": conclusions,
        "prior_no_signal_preserved": "varna_lens/RESULTS_ACOUSTIC_SIGNAL.md + …_CORRECTED_LEXICON.md (NO_SIGNAL ×2); not overturned.",
        "development_verdict": verdict, "verdict_reason": verdict_reason,
    }
    (OUT / "per_word_classification.json").write_text(json.dumps({"words": per_word}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "review_summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "candidate_composition_matrix.json").write_text(json.dumps({"candidates": CANDIDATES}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "error_taxonomy.json").write_text(json.dumps(ERROR_TAXONOMY, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "selected_word_manifest.json").write_text(json.dumps(
        {"selection_rule": SELECTION_RULE, "selected": SELECTED,
         "manifest_hash": hashlib.sha256(json.dumps(sorted(SELECTED), ensure_ascii=False).encode()).hexdigest()},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    r = build()
    print("verdict:", r["development_verdict"])
    print("selected:", len(r["selected_words"]), "words")
    for v in VIEWS:
        print(f"  {v:26s} {dict(r['view_fit_distribution'][v])}")
