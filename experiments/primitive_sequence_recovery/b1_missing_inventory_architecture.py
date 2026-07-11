"""Stage-1 missing-inventory ARCHITECTURE DECISION generator (docs/data-only).

Decides the FUNCTIONAL TYPE (role) of every currently-missing Stage-1 unit — 14 vowels, anusvāra, visarga,
candrabindu, and the retroflex lateral ḷ — BEFORE any meaning is authored or inferred. It authors NO meaning, NO
pole, NO polarity; it edits NO table and runs NO experiment. It emits a role matrix (no semantic glosses), a
candidate-model comparison, a source-claim evidence ledger, and an unresolved-question register.

Authoritative base: parser freeze a1988394 / schema 1.1; integration audit f83d8dc8; D1–D4 reconciliation 26d680c9;
metadata v3.1 re-freeze 1856c56f (active table varna_polarity_table_v3_1_metadata_refreeze.json).

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. No binding/liberating words appear here.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "missing_inventory_architecture"

CANDIDATE_ROLES = [
    "SEMANTIC_PRIMITIVE", "POLARITY_BEARING_PRIMITIVE", "TRANSITION_OPERATOR", "MODIFIER",
    "CARRIER_OR_SUPPORT", "COMPOSITION_BOUNDARY_OPERATOR", "PHONOLOGICAL_MARKER_ONLY",
    "CONTEXTUAL_REALIZATION_OPERATOR", "UNRESOLVED_ROLE", "OUT_OF_SCOPE",
]
PROV_CLASSES = ["PRIMARY_ATTESTED", "SECONDARY_ATTESTED", "INFERRED", "AUTHORED_PROVISIONAL",
                "CONTRADICTORY", "MISSING", "OUT_OF_SCOPE", "UNRESOLVED"]

# ---- A. source-claim evidence ledger -----------------------------------------------------------------------------
SOURCE_LEDGER = [
    {"id": "S1", "claim": "The native varṇa theory (Sarkar) assigns acoustic roots to the vowels (a ā i ī u ū ṛ ṝ ḷ "
                          "e ai o au) and to aṃ/aḥ; none are present in the current table.",
     "location": "B1_SANSKRIT_FIRST_STAGING_AUDIT_AND_PLAN.md#A.1",
     "provenance": "SECONDARY_ATTESTED", "scope": "all vowels + anusvāra + visarga",
     "implies": "root-bearing / primitive-like content per theory; but per-unit content is MISSING (not in b1_2 lexicon)",
     "inference_label": "asserts a theory-level claim; the per-vowel root CONTENT is not reproduced in-repo"},
    {"id": "S2", "claim": "Patent architecture assigns vowels a positional FIELD role (first consonant=seed, final "
                          "consonant=transformer, interior consonants=unresolved, vowels=field); an opt-in variant "
                          "lets a word-initial vowel take a seed role.",
     "location": "H2_PATENT_TECHNICAL_BRIEF.md#L22",
     "provenance": "AUTHORED_PROVISIONAL", "scope": "vowels (English G2P apparatus)",
     "implies": "structural/positional role, NOT a per-vowel meaning; this is the DEPRECATED English pipeline, not the native theory",
     "inference_label": "engineering role of the English apparatus; explicitly not a native-theory claim"},
    {"id": "S3", "claim": "Vowel-initial positional-polarity variant reads authored per-vowel polar-state fields from "
                          "a development lexicon; labelled NOT semantic evidence and keyed off English EY→e, not Sanskrit a.",
     "location": "H2_EXPERIMENTAL_VOWEL_POSITIONAL_POLARITY_MEMO.md",
     "provenance": "AUTHORED_PROVISIONAL", "scope": "vowels (development lexicon)",
     "implies": "authored vowel poles EXIST in a dev lexicon but are unattested and English-motivated",
     "inference_label": "development-only; the memo itself disclaims semantic/ontology/Sanskrit-privilege weight"},
    {"id": "S4", "claim": "By construction, the a-privative prefix and vowel length carry meaning-flipping contrast: "
                          "vidyā↔avidyā, himsā↔ahimsā (privative a), nara↔nārī (length/gender) — identical consonant "
                          "skeletons, opposite/contrastive meanings.",
     "location": "DROPPED_VOWEL_ANTONYM_PROBE.md",
     "provenance": "PRIMARY_ATTESTED", "scope": "privative a + vowel length (a natural experiment on the frozen corpus)",
     "implies": "vowels/prefix/length are semantically LOAD-BEARING (existence proof); refutes consonant-only as a COMPLETE theory",
     "inference_label": "structural existence proof about WHERE contrast lives — not a per-vowel pole assignment"},
    {"id": "S5", "claim": "The active native table (v3.1) contains 34 consonant entries and NO vowel / anusvāra / "
                          "visarga / candrabindu entries.",
     "location": "frozen/varna_polarity_table_v3_1_metadata_refreeze.json",
     "provenance": "MISSING", "scope": "vowels + anusvāra + visarga + candrabindu",
     "implies": "the semantic content for every missing category is absent — not droppable, not yet authored",
     "inference_label": "direct artifact fact"},
    {"id": "S6", "claim": "Open questions in the staging plan: 'is an aspirated stop a distinct varṇa with its own "
                          "root, or a modifier? does anusvāra carry a nasal root? does word-position weight a varṇa?'",
     "location": "B1_SANSKRIT_FIRST_STAGING_AUDIT_AND_PLAN.md#B.3",
     "provenance": "UNRESOLVED", "scope": "anusvāra (nasal root?), positional weighting",
     "implies": "the role of anusvāra (primitive-with-root vs modifier) is explicitly OPEN in-repo",
     "inference_label": "self-declared open question"},
    {"id": "S7", "claim": "The frozen native parser preserves vowels/anusvāra/visarga/candrabindu as ordered atomic "
                          "units with NO meaning; 45% of seed-corpus phonological tokens are these missing categories.",
     "location": "B1_STAGE1_PARSER_FREEZE_RECORD.md; stage1_mapping_integration/coverage_summary.json",
     "provenance": "PRIMARY_ATTESTED", "scope": "all missing categories",
     "implies": "structural preservation is done; the missing categories dominate token frequency",
     "inference_label": "direct artifact fact"},
]

# ---- B. per-unit role decisions (NO meanings) --------------------------------------------------------------------
VOWELS = [("अ", "a", "short", "simple"), ("आ", "ā", "long", "simple"), ("इ", "i", "short", "simple"),
          ("ई", "ī", "long", "simple"), ("उ", "u", "short", "simple"), ("ऊ", "ū", "long", "simple"),
          ("ऋ", "ṛ", "short", "vocalic_sonorant"), ("ॠ", "ṝ", "long", "vocalic_sonorant"),
          ("ऌ", "l̥", "short", "vocalic_sonorant"), ("ॡ", "l̥̄", "long", "vocalic_sonorant"),
          ("ए", "e", "long", "diphthongal"), ("ऐ", "ai", "long", "diphthongal"),
          ("ओ", "o", "long", "diphthongal"), ("औ", "au", "long", "diphthongal")]

VOWEL_ROW_COMMON = {
    "category": "vowel",
    "stage1_scope": "IN_SCOPE_STRUCTURAL",         # parser emits it; structurally preserved
    "candidate_roles": ["POLARITY_BEARING_PRIMITIVE", "SEMANTIC_PRIMITIVE", "TRANSITION_OPERATOR",
                        "CONTEXTUAL_REALIZATION_OPERATOR", "MODIFIER", "UNRESOLVED_ROLE"],
    "recommended_role": "UNRESOLVED_ROLE",
    "primary_candidate": "POLARITY_BEARING_PRIMITIVE",   # per S1 (Sarkar acoustic roots)
    "secondary_candidate": "CONTEXTUAL_REALIZATION_OPERATOR",  # per S2 (patent FIELD/positional)
    "role_provenance": "UNRESOLVED",   # S1 (theory: primitive) vs S2 (apparatus: field) conflict; content MISSING
    "independent_semantic_entry_allowed": False,   # requires sourcing Sarkar vowel roots first (S1 content MISSING)
    "polarity_allowed": "UNRESOLVED",  # theory claims 'roots', not that they are polar
    "modifies_previous": "UNRESOLVED",  # dependent sign realizes the preceding consonant's syllable (structural), meaning-effect unknown
    "modifies_next": False,
    "composition_effect": "LOAD_BEARING_STRUCTURAL (S4: privative-a and length flip meaning); mechanism UNRESOLVED",
    "independent_dependent_same_identity": True,   # parser already unifies independent vowel and dependent sign
    "required_evidence_before_activation": "PRIMARY/SECONDARY-attested Sarkar acoustic root per vowel; and a sourced "
                                           "determination of whether the root is polar (pole) or an operator/transition role",
}


def vowel_row(deva, unit, length, subtype):
    row = dict(VOWEL_ROW_COMMON)
    row.update({"devanagari": deva, "canonical_unit": unit, "length": length, "vowel_subtype": subtype})
    uq = []
    if length == "long":
        uq.append("does length change ROLE or only magnitude? (S4 shows length is contrastive: nara↔nārī)")
    if subtype == "vocalic_sonorant":
        uq.append("does vocalic ṛ/ḷ behave as an ordinary vowel or need separate (syllabic-sonorant) treatment?")
    if unit == "a":
        uq.append("the privative/inherent 'a' is the highest-frequency unit and the S4 negation carrier — "
                  "does it hold a distinct role from other vowels?")
    row["unresolved_questions"] = uq or ["individual differentiation vs shared category role is unsourced"]
    row["individual_differentiation_evidence"] = ("S4 (privative a; length) — structural only, per-unit poles UNSOURCED"
                                                  if unit == "a" or length == "long" else "none sourced")
    return row


MARK_ROWS = [
    {"devanagari": "ं", "canonical_unit": "ṃ", "category": "anusvara", "stage1_scope": "IN_SCOPE_STRUCTURAL",
     "candidate_roles": ["PHONOLOGICAL_MARKER_ONLY", "MODIFIER", "CONTEXTUAL_REALIZATION_OPERATOR",
                         "POLARITY_BEARING_PRIMITIVE", "UNRESOLVED_ROLE"],
     "recommended_role": "UNRESOLVED_ROLE",
     "primary_candidate": "MODIFIER",   # nasalization modifier (phonological)
     "secondary_candidate": "POLARITY_BEARING_PRIMITIVE",  # S1 claims aṃ has an acoustic root; S6 leaves it OPEN
     "role_provenance": "UNRESOLVED",
     "independent_semantic_entry_allowed": False, "polarity_allowed": "UNRESOLVED",
     "modifies_previous": True, "modifies_next": False,
     "composition_effect": "nasalization of the syllable; canonical ṃ kept DISTINCT from any homorganic-nasal resolution",
     "required_evidence_before_activation": "sourced answer to S6 ('does anusvāra carry a nasal root?'); until then "
                                            "canonical marker only",
     "unresolved_questions": ["nasalization modifier vs root-bearing primitive (S1 vs S6)",
                              "must the canonical ṃ ever be replaced by a homorganic nasal for composition? (kept separate for now)"]},
    {"devanagari": "ः", "canonical_unit": "ḥ", "category": "visarga", "stage1_scope": "IN_SCOPE_STRUCTURAL",
     "candidate_roles": ["MODIFIER", "COMPOSITION_BOUNDARY_OPERATOR", "CONTEXTUAL_REALIZATION_OPERATOR",
                         "POLARITY_BEARING_PRIMITIVE", "UNRESOLVED_ROLE"],
     "recommended_role": "UNRESOLVED_ROLE",
     "primary_candidate": "MODIFIER",   # exhalation/release
     "secondary_candidate": "COMPOSITION_BOUNDARY_OPERATOR",
     "role_provenance": "UNRESOLVED",
     "independent_semantic_entry_allowed": False, "polarity_allowed": "UNRESOLVED",
     "modifies_previous": True, "modifies_next": False,
     "composition_effect": "release/exhalation and frequent word/pada boundary; MUST NOT be collapsed into h",
     "required_evidence_before_activation": "sourced acoustic root (S1 aḥ) or an explicit modifier/boundary decision",
     "unresolved_questions": ["release modifier vs boundary operator vs root-bearing primitive",
                              "distinct from h — do not merge"]},
    {"devanagari": "ँ", "canonical_unit": "m̐", "category": "candrabindu", "stage1_scope": "OUT_OF_SCOPE_CLASSICAL_CORE",
     "candidate_roles": ["PHONOLOGICAL_MARKER_ONLY", "MODIFIER", "OUT_OF_SCOPE", "UNRESOLVED_ROLE"],
     "recommended_role": "PHONOLOGICAL_MARKER_ONLY",
     "primary_candidate": "PHONOLOGICAL_MARKER_ONLY",
     "secondary_candidate": "OUT_OF_SCOPE",
     "role_provenance": "MISSING",   # no source claim assigns candrabindu a root
     "independent_semantic_entry_allowed": False, "polarity_allowed": "NO",
     "modifies_previous": True, "modifies_next": False,
     "composition_effect": "vowel nasalization (metadata); kept DISTINCT from anusvāra; largely Vedic/vernacular",
     "required_evidence_before_activation": "first a scope justification that classical Sanskrit uses it as a varṇa; "
                                            "no source currently assigns it a root",
     "unresolved_questions": ["is candrabindu in classical-core scope at all? (no source claim found)"]},
    {"devanagari": "ळ", "canonical_unit": "ḷ", "category": "retroflex_lateral", "stage1_scope": "OUT_OF_SCOPE_EXTENDED_VEDIC",
     "candidate_roles": ["OUT_OF_SCOPE", "SEMANTIC_PRIMITIVE", "UNRESOLVED_ROLE"],
     "recommended_role": "OUT_OF_SCOPE",
     "primary_candidate": "OUT_OF_SCOPE",
     "secondary_candidate": "UNRESOLVED_ROLE",
     "role_provenance": "OUT_OF_SCOPE",   # Vedic/Marathi; not in the classical 34-key inventory
     "independent_semantic_entry_allowed": False, "polarity_allowed": "NO",
     "modifies_previous": False, "modifies_next": False,
     "composition_effect": "consonantal; the parser emits it but the table has no key — extended Vedic/regional, not classical core",
     "required_evidence_before_activation": "a scope justification to admit an extended Vedic inventory; do NOT create a "
                                            "table mapping without that justification",
     "unresolved_questions": ["retain in an extended Vedic inventory or exclude from Stage 1 entirely?"]},
]

# ---- C. candidate-model comparison -------------------------------------------------------------------------------
MODELS = [
    {"id": "A", "name": "Full primitive symmetry",
     "desc": "every vowel and marker receives a polar pole like consonants",
     "source_support": "PARTIAL — S1 says vowels have acoustic roots, but NOT that the roots are polar; forcing "
                       "full polar symmetry over-assumes (guardrail caution).",
     "authored_parameters_required": "HIGH (2 poles × 18 units = ~36 authored, all currently MISSING)",
     "parser_compatible": True, "table_compatible": "requires large authored extension",
     "falsifiability": "LOW (many free parameters invite post-hoc fit)", "back_fit_risk": "HIGH",
     "composition_effect": "every unit contributes a pole", "explains_45pct_without_inventing": False},
    {"id": "B", "name": "Consonant semantics, vowel transitions",
     "desc": "consonants carry propensity; vowels control transition/direction/activation/linkage",
     "source_support": "PARTIAL — matches the patent FIELD/positional apparatus (S2, AUTHORED) but conflicts with "
                       "S1 (Sarkar vowel roots).",
     "authored_parameters_required": "MEDIUM (a transition rule, few parameters)",
     "parser_compatible": True, "table_compatible": "vowels get operator roles, not table rows",
     "falsifiability": "MEDIUM", "back_fit_risk": "MEDIUM",
     "composition_effect": "vowels operate on consonant sequence", "explains_45pct_without_inventing": True},
    {"id": "C", "name": "Hierarchical akṣara model",
     "desc": "meaning arises at the consonant-vowel/akṣara unit; neither interpreted independently",
     "source_support": "PARTIAL — the patent permits 'syllabic or phonetic units'; the parser already emits an "
                       "akṣara layer. But no source gives akṣara-level meanings.",
     "authored_parameters_required": "VERY HIGH (per-akṣara inventory is combinatorial)",
     "parser_compatible": True, "table_compatible": "orthogonal to a per-varṇa table",
     "falsifiability": "LOW (huge space)", "back_fit_risk": "HIGH",
     "composition_effect": "unit of meaning = akṣara", "explains_45pct_without_inventing": False},
    {"id": "D", "name": "Mixed typed inventory",
     "desc": "consonants=primitives; vowels=operators/modulators; anusvāra/candrabindu=nasalization; visarga=release/boundary",
     "source_support": "STRONGEST STRUCTURAL FIT — S4 (vowels load-bearing, heterogeneous from consonants) + guardrail "
                       "(don't clone consonant model) + S1 (vowels have their OWN roots) → typed classes. Vowel role "
                       "sub-cell (polar primitive vs operator) remains UNRESOLVED between S1 and S2.",
     "authored_parameters_required": "LOW-MEDIUM (typed roles, vowel specifics deferred to a provenance study)",
     "parser_compatible": True, "table_compatible": "additive typed sections; no consonant change",
     "falsifiability": "HIGH (each typed role is a distinct testable claim)", "back_fit_risk": "LOW-MEDIUM",
     "composition_effect": "heterogeneous per class", "explains_45pct_without_inventing": True},
    {"id": "E", "name": "Consonant-only semantic core",
     "desc": "vowels and markers preserved structurally but contribute NO semantic content",
     "source_support": "REFUTED as COMPLETE by S4 (privative-a and length flip meaning); tenable ONLY as an explicit, "
                       "declared partial scope, not as the theory.",
     "authored_parameters_required": "ZERO (no new content)",
     "parser_compatible": True, "table_compatible": True,
     "falsifiability": "HIGH but already contradicted for the a-privative/length cases",
     "back_fit_risk": "NONE", "composition_effect": "vowels/marks inert",
     "explains_45pct_without_inventing": "only by declaring 45% out of semantic scope"},
]

# ---- D. decision criteria (ranking is qualitative, source-anchored) ----------------------------------------------
CRITERIA = ["source_fidelity", "parameter_minimality", "preservation_of_phonological_information", "determinism",
            "compatibility_with_ordered_parser_output", "resistance_to_semantic_back_fitting", "falsifiability",
            "ability_to_preregister_composition", "compatibility_with_native_before_english",
            "separation_of_structure_from_validated_meaning"]

# per-criterion best model(s); D wins source-fidelity+falsifiability+back-fit-resistance among models that keep vowels
CRITERION_RANKING = {
    "source_fidelity": ["D", "A", "B", "C", "E"],
    "parameter_minimality": ["E", "D", "B", "A", "C"],
    "preservation_of_phonological_information": ["D", "C", "A", "B", "E"],
    "determinism": ["A", "B", "C", "D", "E"],   # all deterministic; tie
    "compatibility_with_ordered_parser_output": ["D", "B", "C", "A", "E"],
    "resistance_to_semantic_back_fitting": ["E", "D", "B", "C", "A"],
    "falsifiability": ["D", "E", "B", "A", "C"],
    "ability_to_preregister_composition": ["D", "B", "E", "A", "C"],
    "compatibility_with_native_before_english": ["D", "A", "C", "E", "B"],
    "separation_of_structure_from_validated_meaning": ["D", "E", "C", "B", "A"],
}

# ---- E. provenance policy for future inventory completion --------------------------------------------------------
PROVENANCE_POLICY = {
    "confirmatory_mechanism_admits": ["PRIMARY_ATTESTED", "SECONDARY_ATTESTED"],
    "requires_separate_stated_derivation": ["INFERRED"],
    "development_only_never_confirmatory": ["AUTHORED_PROVISIONAL"],
    "must_not_be_silently_ignored": ["MISSING"],
    "absence_may_be_an_explicit_decision": True,
    "authored_provisional_permitted_in_confirmatory_stage1": False,
    "evidence_required_before": {
        "independent_semantic_gloss": "PRIMARY_ATTESTED or SECONDARY_ATTESTED source root for the specific unit",
        "polar_pole": "sourced evidence that the unit's root is POLAR (not merely that a root exists) — S1 does not establish this",
        "transition_role": "a sourced or separately-derived (INFERRED, labelled) compositional rule",
        "modifier_role": "sourced phonological role (e.g. anusvāra nasalization) — structural, still no meaning",
        "context_dependent_realization_rule": "a deterministic, pre-registered rule kept distinct from canonical output",
    },
}


def build():
    OUT.mkdir(exist_ok=True)
    rows = [vowel_row(*v) for v in VOWELS] + MARK_ROWS

    # validation: no meanings / banned words anywhere
    blob = json.dumps({"rows": rows, "ledger": SOURCE_LEDGER, "models": MODELS, "policy": PROVENANCE_POLICY},
                      ensure_ascii=False)
    for banned in ("binding", "liberating", "GENUTILITY", "ONTOLOGICAL_SIGNAL"):
        assert banned.lower() not in blob.lower(), f"banned token {banned!r} leaked into the decision artifacts"
    for r in rows:
        assert r["recommended_role"] in CANDIDATE_ROLES
        assert r["role_provenance"] in PROV_CLASSES

    architecture_verdict = "RECOMMEND_TYPED_MIXED_INVENTORY"
    architecture_reason = (
        "Model D (typed-mixed) is the minimal structure jointly forced by the sources: S4 proves vowels/prefix/length "
        "are meaning-load-bearing (refuting E as a complete theory) yet heterogeneous from consonants (so not the "
        "consonant pole model, per the guardrail); S1 says vowels/aṃ/aḥ have their OWN roots (so not mere carriers). "
        "Typed classes with distinct roles fit all three while deferring the one genuinely conflicted sub-question — "
        "the vowel role cell (polar primitive per S1 vs positional operator per the deprecated English apparatus S2) — "
        "to a provenance study. Chosen for source fidelity + falsifiability + back-fit resistance, NOT coverage.")
    readiness_verdict = "READY_FOR_MISSING_INVENTORY_PROVENANCE_STUDY"
    readiness_reason = (
        "The typed structure is decided, but every missing unit's semantic content is MISSING and the vowel/anusvāra/"
        "visarga role cells are UNRESOLVED between S1 (Sarkar roots) and S2 (patent field). The ready next step is a "
        "provenance study that sources the Sarkar acoustic roots for vowels + aṃ/aḥ from primary text and determines "
        "whether each root is polar or an operator — NOT composition pre-registration, NOT semantic word testing.")

    role_matrix = {
        "artifact_type": "missing_inventory_role_matrix",
        "contains_semantic_glosses": False,
        "candidate_role_vocabulary": CANDIDATE_ROLES,
        "provenance_classes": PROV_CLASSES,
        "units": rows,
        "category_level_roles": {
            "vowels": {"recommended_role": "UNRESOLVED_ROLE", "primary_candidate": "POLARITY_BEARING_PRIMITIVE",
                       "secondary_candidate": "CONTEXTUAL_REALIZATION_OPERATOR",
                       "independent_semantic_entry_allowed": False, "polarity_allowed": "UNRESOLVED"},
            "anusvara": {"recommended_role": "UNRESOLVED_ROLE", "primary_candidate": "MODIFIER",
                         "polarity_allowed": "UNRESOLVED"},
            "visarga": {"recommended_role": "UNRESOLVED_ROLE", "primary_candidate": "MODIFIER",
                        "polarity_allowed": "UNRESOLVED"},
            "candrabindu": {"recommended_role": "PHONOLOGICAL_MARKER_ONLY", "polarity_allowed": "NO"},
            "retroflex_lateral_la": {"recommended_role": "OUT_OF_SCOPE", "polarity_allowed": "NO"},
        },
    }
    (OUT / "role_matrix.json").write_text(json.dumps(role_matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "model_comparison.json").write_text(json.dumps(
        {"models": MODELS, "criteria": CRITERIA, "criterion_ranking": CRITERION_RANKING,
         "architecture_verdict": architecture_verdict, "architecture_reason": architecture_reason},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "source_claim_ledger.json").write_text(json.dumps({"ledger": SOURCE_LEDGER}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    unresolved = []
    for r in rows:
        for q in r["unresolved_questions"]:
            unresolved.append({"unit": r["canonical_unit"], "category": r["category"], "question": q})
    unresolved.append({"unit": "*vowels*", "category": "vowel",
                       "question": "Are the Sarkar vowel acoustic roots POLAR (poles) or non-polar operator/transition roles? "
                                   "(S1 asserts roots exist but not that they are polar.)"})
    (OUT / "unresolved_questions.json").write_text(json.dumps({"unresolved": unresolved}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "provenance_policy.json").write_text(json.dumps(PROVENANCE_POLICY, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {"rows": rows, "architecture_verdict": architecture_verdict, "readiness_verdict": readiness_verdict,
            "architecture_reason": architecture_reason, "readiness_reason": readiness_reason,
            "n_units": len(rows), "n_unresolved": len(unresolved)}


if __name__ == "__main__":
    r = build()
    print("architecture:", r["architecture_verdict"])
    print("readiness   :", r["readiness_verdict"])
    print("units:", r["n_units"], "(14 vowels + anusvāra + visarga + candrabindu + ḷ)")
    print("unresolved questions:", r["n_unresolved"])
