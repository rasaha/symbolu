"""Docs/data-only preregistration + Stage-F feasibility generator for the Sanskrit symbolic-profile study.

Emits the frozen preregistration artifacts (closed attribute inventory, word-eligibility spec, packet-projection
spec, AND-composition spec, morphology baseline, controls, scoring/analysis plan, success/kill criteria, outcome
taxonomy, held-out split) and runs the DETERMINISTIC Stage-F feasibility gates over the frozen inputs it can read.

NO study, NO judges, NO raters, NO model calls, NO network. Does NOT modify the parser, varṇa mappings, merged
lexicon, prior packets, or prior results — it only READS the merged lexicon to demonstrate the packet-projection
feasibility gate. Structure, not validated meaning. All prior negative results are preserved.
"""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
MERGED = json.loads((HERE / "frozen" / "varna_native_stage1_merged_v1.json").read_text(encoding="utf-8"))
OUT = HERE / "symbolic_profile_prereg"

# ---- confirmatory consonant vṛtti glosses (READ ONLY, for the projection-feasibility demonstration) ----
CONS_ROWS = [r for r in MERGED["rows"] if r["category"] == "consonant" and r.get("source_key")
             and r["activation_scope"] == "CONFIRMATORY_BACKBONE"]

# lexicons for the deterministic domain-mismatch scan (auditable, fixed here)
REFERENT_ATTR_TERMS = [
    "animal", "animate", "living", "creature", "beast", "plant", "tree", "leaf", "root", "flower",
    "water", "river", "ocean", "sky", "cloud", "rain", "stone", "metal", "earth", "mountain",
    "large", "small", "big", "tiny", "heavy", "light", "tall", "colour", "color", "shape", "body",
    "terrestrial", "aquatic", "aerial", "four-legged", "winged", "horn", "tusk", "trunk", "wheel",
    "object", "tool", "vessel", "food", "grain", "salt", "fire", "sun", "moon", "star", "wood", "iron",
]
TENDENCY_TERMS = [
    "hope", "grasping", "clinging", "craving", "desire", "longing", "attachment", "possessive", "mine",
    "anxious", "rumination", "worry", "fear", "doubt", "distrust", "striving", "effort", "restless",
    "ego", "vanity", "pride", "self", "doership", "discernment", "judgment", "cruelty", "harm", "envy",
    "resentment", "irritability", "anger", "restraint", "indulgence", "delusion", "entrancement",
    "compassion", "regard", "neglect", "steadiness", "confidence", "aversion", "greed", "arrogance",
]


def scan_domain():
    """Deterministic: do the confirmatory glosses carry TENDENCY content or REFERENT-ATTRIBUTE content?"""
    text = " ".join((r["binding_vritti"] + " " + r["liberating_vritti"]).lower() for r in CONS_ROWS)
    tend = sorted({t for t in TENDENCY_TERMS if t in text})
    ref = sorted({t for t in REFERENT_ATTR_TERMS if t in text})
    return {"n_confirmatory_glosses": 2 * len(CONS_ROWS),
            "tendency_terms_found": tend, "n_tendency_terms": len(tend),
            "referent_attribute_terms_found": ref, "n_referent_attribute_terms": len(ref),
            "conclusion": ("the frozen packet vocabulary is psychological-tendency content and carries essentially "
                           "no referent-attribute content; there is no principled, non-narrative deterministic map "
                           "from tendency-space into a referent-attribute inventory")}


# =====================================================================================================
# FROZEN PREREGISTRATION ARTIFACTS (specifications; execution is gated by Stage F)
# =====================================================================================================
def attribute_inventory():
    # grounded in EXTERNAL semantic-attribute sources, NOT tailored to packets
    dims = [
        ("animacy", "animate ⟷ inanimate", "Binder et al. 2016 (Social/Human); classic animacy norms"),
        ("living", "living ⟷ non-living", "semantic feature norms (McRae et al. 2005)"),
        ("concreteness", "concrete ⟷ abstract", "Brysbaert et al. 2014 concreteness norms"),
        ("size", "large ⟷ small", "Binder et al. 2016 (Vision/Size)"),
        ("weight", "heavy ⟷ light", "Binder et al. 2016 (Somatic/Weight)"),
        ("mobility", "mobile ⟷ stationary", "Binder et al. 2016 (Motion)"),
        ("agency", "agentive ⟷ non-agentive", "Binder et al. 2016 (Cognition/Social)"),
        ("boundedness", "bounded ⟷ diffuse", "qualia/ontology (Pustejovsky); count/mass"),
        ("naturalness", "natural ⟷ constructed", "artifact vs natural-kind ontology"),
        ("domain", "terrestrial ⟷ aquatic ⟷ aerial", "ecological domain (categorical)"),
        ("ontological_type", "object ⟷ process ⟷ quality ⟷ relation", "lexical ontology (categorical)"),
        ("valence", "positive ⟷ negative", "Osgood Evaluation; Warriner et al. 2013"),
        ("potency", "forceful ⟷ gentle", "Osgood Potency"),
        ("activity", "active ⟷ passive", "Osgood Activity"),
        ("harm", "beneficial ⟷ harmful", "affective/functional norm"),
    ]
    return {
        "policy": "FIXED, externally-defined, closed inventory; NO free-text profile writing; NO packet-specific "
                  "attributes; NO target-word names; NO open 'other' field; clear bipolar/categorical anchors.",
        "external_basis": ["Osgood, Suci & Tannenbaum 1957 (Evaluation/Potency/Activity)",
                           "Binder et al. 2016 experiential attribute norms",
                           "Brysbaert et al. 2014 concreteness", "McRae et al. 2005 feature norms",
                           "Warriner et al. 2013 valence"],
        "rating_scale": "7-point bipolar for bipolar dims; single-select for categorical dims; 'cannot determine' allowed",
        "dimensions": [{"name": n, "anchors": a, "source": s, "why_included": "general cross-lexical property, "
                        "not tailored to any packet"} for n, a, s in dims],
        "frozen": True, "n_dimensions": len(dims)}


def eligibility_spec():
    return {
        "primary_word_requirements": [
            "native Sanskrit form with canonical Devanāgarī",
            "deterministically parsed by the frozen Stage-1 parser (round-trip)",
            "monomorphemic / simplex under the predeclared criterion below",
            "etymologically opaque or conventionalized (rūḍha), NOT transparently compositional",
            "supported by >=2 independent lexicographic sources",
            "consonant backbone uses ONLY confirmatory mappings; no contradictory mapping",
            "selected WITHOUT inspecting any packet-to-profile fit"],
        "exclusions": ["transparent compounds", "obvious root+affix (yaugika) derivations whose profile is "
                       "predictable from morphology", "words chosen because their packet looks convincing",
                       "words whose profile cannot be independently measured", "unresolved textual identity"],
        "decision_tree": [
            "1. Parse round-trips under the frozen parser? no -> EXCLUDE(parse).",
            "2. Backbone uses only confirmatory consonants, no contradiction? no -> EXCLUDE(mapping).",
            "3. Morphological status by >=2 sources: simplex/rūḍha vs derived/yaugika. derived -> EXCLUDE(derived).",
            "4. Etymological transparency: is a synchronic root+affix analysis available and profile-predictive? "
            "yes -> EXCLUDE(transparent).",
            "5. Conventionalized vs synchronically compositional: compositional -> EXCLUDE(compositional).",
            "6. Independent profile measurable (>=2 lexicographic sources + ratable)? no -> EXCLUDE(unmeasurable).",
            "7. Uncertain on (3)-(5) after two sources -> EXCLUDE(uncertain) (conservative; never weaken to grow N)."],
        "required_sources_examples": ["Mayrhofer EWA (etymology)", "Monier-Williams (senses/derivation)",
                                      "Amarakośa / nighaṇṭu (attestation)", "Whitney roots (derivation)"],
        "auditability": "every inclusion/exclusion records word, decision, rule id, and the two sources consulted",
        "min_sample": {"development": 40, "confirmatory_preferred": "60-100",
                       "balance": "across semantic + grammatical categories; variation in length, consonant count, "
                                  "vowel pattern, attribute profile",
                       "on_shortfall": "PREREG_BLOCKED_BY_INSUFFICIENT_OPAQUE_LEXEMES; never weaken eligibility"}}


def packet_projection_spec():
    return {
        "requirement": "ONE deterministic (or tightly-constrained, reproducible) transformation from the COMPLETE "
                       "packet into the SAME closed attribute space, identical for every word, frozen before profiles.",
        "must": ["apply identically to all words", "consume ALL confirmatory mappings under the AND operator",
                 "define order treatment, repeated-varṇa treatment, contradiction logging, missing-unit handling",
                 "prohibit per-word polarity selection", "prohibit target-aware wording", "hard capacity limit",
                 "two independent implementations produce byte-identical predictions"],
        "prohibited": ["free human/LLM narration of packet meaning",
                       "an unconstrained LLM 'interpretation' substituting for a defined projection"],
        "domain_feasibility": scan_domain(),
        "gate": ("the projection maps the packet into the attribute inventory. The frozen packet is TENDENCY-valued "
                 "(psychological dispositions); the attribute inventory is REFERENT-property valued. No principled, "
                 "non-narrative deterministic function from tendency-space to referent-property-space is provided by "
                 "the frozen mappings, and none can be constructed without the prohibited narrative bridge. A frozen "
                 "text-embedder + cosine is rejected: it is a prohibited unconstrained interpretation and would be "
                 "driven by surface lexical overlap (leakage), not a defined composition. => gate NOT satisfied."),
        "on_undefinable": "PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION"}


def and_composition_spec():
    return {
        "operationalization_options_to_choose_from": ["set intersection of asserted attributes",
            "element-wise minimum support (fuzzy AND)", "element-wise product", "logical constraint satisfaction"],
        "operator_requirements": ["consume ALL eligible mappings (no facet cherry-picking)",
            "record contradictions rather than discard", "produce ONE reproducible profile", "identical across words",
            "non-adaptive to target meaning", "byte-identical across two independent implementations"],
        "status": "DEFINABLE in the abstract, but INERT: it operates on per-varṇa attribute vectors that only exist "
                  "AFTER the packet-projection maps each mapping into the attribute space. Since the projection gate "
                  "is not satisfied (see packet_projection_spec), the AND operator has no admissible inputs.",
        "blocked_upstream_by": "PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION"}


def morphology_baseline_spec():
    return {
        "requirement": "even for the opaque/simplex primary set, record for every word: any traditional/historical "
                       "derivation; whether it predicts any closed attributes; confidence + source; a morphology "
                       "profile in the SAME attribute space.",
        "incremental_validity_rule": "the varṇa packet must beat dictionary-only, morphology/etymology, and generic "
                                     "semantic-class baselines. If morphology >= true packet -> MORPHOLOGY_EXPLAINS_PROFILE.",
        "feasibility_in_environment": "REQUIRES external etymological sources (Mayrhofer EWA, Whitney, Monier-Williams) "
                                      "not available here; cannot be constructed deterministically in-environment.",
        "on_infeasible": "PREREG_BLOCKED_BY_MORPHOLOGY_BASELINE"}


def control_spec():
    return {"arms": {
        "T": "true word profile vs its frozen true packet projection",
        "X": "profile vs another eligible word's packet (frozen derangement)",
        "R": "structure-preserving randomized varṇa→mapping assignment",
        "S": "same packet members, scrambled order (order-effect probe)",
        "P": "true packet projections vs randomly reassigned word profiles (profile swap)",
        "G": "generic profile matched for valence/density/attribute prevalence",
        "M": "profile predicted from independent morphology/etymology only",
        "D": "profile predicted from dictionary semantic class only (no varṇa)"},
        "matching": ["profile density", "attribute prevalence", "word length", "packet length", "valence",
                     "concreteness", "grammatical class where practical"],
        "status": "constructible in the abstract; all semantic arms depend on the (blocked) packet projection."}


def scoring_plan():
    return {"fit_components": ["attribute precision", "attribute recall/coverage", "F-score",
                               "contradiction penalty", "weighted profile similarity"],
            "fit_definition": "Fit(prediction, profile) = a single frozen mechanical function applied IDENTICALLY to "
                              "T,X,R,S,P,G,M,D. NO free-form 'joint coherence' unless reduced to an exact function.",
            "primary_contrast": "Δ = Fit(T) − max(Fit(X), Fit(R), Fit(P), Fit(G), Fit(M), Fit(D))",
            "order_effect": "Fit(T) − Fit(S)",
            "statistics": "cluster bootstrap over WORDS, BCa 95% CI on Δ; permutation over packet↔profile pairing; "
                          "held-out replication; capacity/MDL bound; lookup-table + word-specific-exception ban."}


def success_kill():
    return {"conjunctive_all_required": [
        "T > X", "T > R", "T > profile-swap P", "T > generic G", "T > dictionary D", "T > morphology M",
        "primary Δ CI excludes zero", "direction replicates on held-out words",
        "not driven only by valence or one semantic class", "survives exclusion of pre-flagged transparent words",
        "profile-swap margin collapses as expected", "inter-rater reliability passes frozen threshold"],
        "no_absolute_fit": "success is NEVER declared from absolute fit alone"}


def outcome_taxonomy():
    return {"primary_one_of": ["SYMBOLIC_PROFILE_SIGNAL_REPLICATES", "GENERIC_PROFILE_FIT_EXPLAINS",
            "MORPHOLOGY_EXPLAINS_PROFILE", "RANDOM_ASSIGNMENT_EXPLAINS", "ORDER_NOT_INFORMATIVE",
            "PROFILE_TARGET_NOT_RELIABLE", "NO_SYMBOLIC_PROFILE_SIGNAL", "STUDY_BLOCKED_BY_INSUFFICIENT_DATA",
            "STUDY_BLOCKED_BY_UNDEFINED_PROJECTION"],
            "stage_F_projected_outcome_if_run_now": "STUDY_BLOCKED_BY_UNDEFINED_PROJECTION"}


def heldout_split():
    return {"procedure": ["split eligible words into development + untouched confirmatory BEFORE any scoring",
                          "freeze attribute inventory + packet-projection using ONLY permissible sources + dev set",
                          "no tuning on confirmatory profiles", "capacity well below memorizing word-profile pairs",
                          "lookup tables and word-specific exceptions forbidden"]}


def profile_collection_plan():
    return {"raters_blind_to": ["varṇa mappings", "packets", "study hypothesis", "true/foil assignment",
                                "packet-derived predictions"],
            "raters_receive": ["Sanskrit word", "controlled dictionary definition / profile source",
                               "fixed attribute questionnaire"],
            "predefine": ["min number of raters", "qualification criteria", "rating scale",
                          "missing/uncertain handling", "inter-rater reliability threshold", "aggregation rule"],
            "conflict_of_interest": "no author of mappings/packets/hypotheses may supply confirmatory profiles",
            "on_low_reliability": "PROFILE_TARGET_NOT_RELIABLE",
            "status": "PLAN ONLY; no rater is run in this preregistration; reliability is established at run time."}


# =====================================================================================================
# STAGE-F FEASIBILITY GATES
# =====================================================================================================
def feasibility():
    proj = packet_projection_spec()
    gates = {
        "attribute_inventory_finalized": {"pass": True, "detail": "closed inventory grounded in external norms"},
        "eligibility_rule_defined": {"pass": True, "detail": "decision tree specified"},
        "candidate_words_sourced_and_min_sample": {"pass": False,
            "detail": "requires external lexicographic/etymological sources (Mayrhofer EWA, Monier-Williams, "
                      "Amarakośa) NOT available in this environment; eligibility must not be adjudicated from memory "
                      "(unauditable + violates the auditability rule). Sufficiency of >=40 opaque lexemes cannot be "
                      "established here.", "verdict_if_binding": "PREREG_BLOCKED_BY_INSUFFICIENT_OPAQUE_LEXEMES"},
        "deterministic_packet_projection_defined": {"pass": False,
            "detail": "DOMAIN MISMATCH: packet is tendency-valued, inventory is referent-property valued; no "
                      "principled non-narrative projection exists; frozen-embedder rescue is prohibited + leakage-"
                      "driven.", "verdict_if_binding": "PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION"},
        "and_operator_has_admissible_inputs": {"pass": False,
            "detail": "operator is definable but inert without the (blocked) projection"},
        "mechanical_scoring_defined": {"pass": True, "detail": "frozen Fit function + primary Δ specified"},
        "morphology_baseline_feasible": {"pass": False,
            "detail": "requires external etymology sources unavailable here",
            "verdict_if_binding": "PREREG_BLOCKED_BY_MORPHOLOGY_BASELINE"},
        "matched_controls_feasible": {"pass": True, "detail": "definable; depend on the blocked projection"},
        "heldout_split_feasible": {"pass": True, "detail": "procedure specified"},
        "profile_reliability_plan_defined": {"pass": True, "detail": "plan only; reliability TBD at run"},
    }
    all_pass = all(g["pass"] for g in gates.values())
    # the DEEPEST (conceptual, not solvable by sourcing words) blocker is primary
    readiness = ("READY_FOR_BLIND_PROFILE_COLLECTION_AND_PACKET_FREEZE" if all_pass
                 else "PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION")
    unmet = [k for k, g in gates.items() if not g["pass"]]
    return {"gates": gates, "all_gates_pass": all_pass, "unmet_gates": unmet,
            "primary_blocker": "UNDEFINED_PACKET_PROJECTION (domain mismatch: tendency-space vs referent-attribute "
                               "space) — not resolvable by sourcing more words",
            "secondary_blockers": ["candidate words not sourceable in-environment (INSUFFICIENT_OPAQUE_LEXEMES "
                                   "not establishable here)", "morphology baseline needs external sources"],
            "domain_scan": proj["domain_feasibility"],
            "readiness_verdict": readiness,
            "study_outcome_if_run_now": "STUDY_BLOCKED_BY_UNDEFINED_PROJECTION",
            "what_would_unblock": ["redefine the prediction target so packet and profile share ONE domain "
                                   "(e.g. an experiential/tendency inventory the packet actually populates) — but "
                                   "then the 'referent profile' target dissolves and the hypothesis must be "
                                   "reformulated", "OR supply a principled, non-narrative, capacity-limited "
                                   "tendency→referent-attribute map derived independently of the target words "
                                   "(none is known)"]}


def build():
    OUT.mkdir(exist_ok=True)
    artifacts = {
        "closed_attribute_inventory.json": attribute_inventory(),
        "word_eligibility_spec.json": eligibility_spec(),
        "candidate_word_inventory.json": {"n_eligible_established": 0, "words": [],
            "note": "EMPTY BY DESIGN: eligibility requires external lexicographic sources unavailable here; words "
                    "are NOT invented and NOT chosen from memory (auditability + no-packet-fit rules)."},
        "packet_projection_spec.json": packet_projection_spec(),
        "and_composition_spec.json": and_composition_spec(),
        "morphology_baseline_spec.json": morphology_baseline_spec(),
        "control_spec.json": control_spec(),
        "scoring_analysis_plan.json": scoring_plan(),
        "success_kill_criteria.json": success_kill(),
        "outcome_taxonomy.json": outcome_taxonomy(),
        "heldout_split_procedure.json": heldout_split(),
        "blind_profile_collection_protocol.json": profile_collection_plan(),
        "feasibility_report.json": feasibility(),
    }
    hashes = {}
    for name, obj in artifacts.items():
        p = OUT / name
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    index = {"prereg": "B1_SYMBOLIC_PROFILE", "stage": "F_feasibility",
             "readiness_verdict": artifacts["feasibility_report.json"]["readiness_verdict"],
             "study_outcome_if_run_now": "STUDY_BLOCKED_BY_UNDEFINED_PROJECTION",
             "does_not_modify": ["parser", "varṇa mappings", "merged lexicon", "prior packets", "prior results"],
             "frozen_hashes": hashes}
    (OUT / "freeze_index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                                           encoding="utf-8")
    return index


if __name__ == "__main__":
    idx = build()
    fr = json.loads((OUT / "feasibility_report.json").read_text())
    print("readiness verdict:", idx["readiness_verdict"])
    print("unmet gates:", fr["unmet_gates"])
    print("domain scan: tendency terms =", fr["domain_scan"]["n_tendency_terms"],
          "| referent-attribute terms =", fr["domain_scan"]["n_referent_attribute_terms"])
