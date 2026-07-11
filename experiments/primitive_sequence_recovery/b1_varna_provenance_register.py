"""B1 — Varṇa-mechanism PROVENANCE REGISTER generator (docs/data-only, Part E Step 1).

Purpose: classify the provenance of EVERY pole, phonological rule, and word-composition
assumption in the CURRENT active varṇa mechanism, so an inventory decision can be made on
evidence rather than on the appearance of completeness. This script READS frozen sources and
EMITS new register artifacts only. It changes NO mapping, NO run01 artifact, NO Track G file,
NO frozen table, and asserts NO ontology / semantic-truth / Sanskrit-privilege / generation
-utility claim. Structure, not validated meaning.

Sources of truth (read-only):
  - frozen/varna_polarity_table_v3.json      (per-varṇa poles + attested_vs_authored + meta caveats)
  - varna_bridge_active.word_to_varnas       (the ACTIVE decomposition actually run)
  - build_b1_10_control_ext.VARNA_PLAIN      (the facet render map — only 11 varṇas)

Eight provenance statuses (per pole / per rule):
  PRIMARY_ATTESTED     — stated by the operator-supplied primary classical text.
  SECONDARY_ATTESTED   — the NAME/vṛtti is attested but the pole reading is the lexicon's, not a
                         primary-text pole contrast.
  INFERRED             — attested faculty/direction, but the binding↔liberating SPLIT is derived
                         by applying the framework's principle (not stated as a pole in-source).
  AUTHORED_PROVISIONAL — pole text supplied by the lexicon/researcher; no primary-text support.
  CONTRADICTORY        — two source artifacts (table vs meta vs code) assert conflicting facts.
  MISSING              — inventory category that carries NO meaning in the current mechanism.
  OUT_OF_SCOPE         — deliberately excluded from the current mechanism.
  UNRESOLVED           — flagged in-source as an open question, not settled either way.

The per-pole CLASSIFICATION below was assigned by reading each varṇa's own `attested_vs_authored`
statement (quoted as `basis`) plus the table's `important_caveats`. It does NOT invent meaning,
does NOT promote authored liberating poles to attested, and does NOT infer a positive opposite
from a sourced binding pole; where a pole is authored it is marked authored.
"""
import csv
import hashlib
import json
import pathlib

import varna_bridge_active as AB
import build_b1_10_control_ext as BUILD

HERE = pathlib.Path(__file__).resolve().parent
TABLE_PATH = HERE / "frozen" / "varna_polarity_table_v3.json"
OUT = HERE / "varna_provenance_register"
SRC = "frozen/varna_polarity_table_v3.json#varnas"

# ---- phonological grid (structure only; standard Sanskrit varṇa classification) ----------------
# place ∈ velar/palatal/retroflex/dental/labial/glottal ; manner ∈ stop/nasal/semivowel/sibilant/aspirate
PHON = {
    "ka":  ("velar", "stop", "unvoiced", "unaspirated"),
    "kha": ("velar", "stop", "unvoiced", "aspirated"),
    "ga":  ("velar", "stop", "voiced", "unaspirated"),
    "gha": ("velar", "stop", "voiced", "aspirated"),
    "nga": ("velar", "nasal", "voiced", "unaspirated"),
    "ca":  ("palatal", "stop", "unvoiced", "unaspirated"),
    "cha": ("palatal", "stop", "unvoiced", "aspirated"),
    "ja":  ("palatal", "stop", "voiced", "unaspirated"),
    "jha": ("palatal", "stop", "voiced", "aspirated"),
    "nya": ("palatal", "nasal", "voiced", "unaspirated"),
    "tta": ("retroflex", "stop", "unvoiced", "unaspirated"),
    "ttha":("retroflex", "stop", "unvoiced", "aspirated"),
    "dda": ("retroflex", "stop", "voiced", "unaspirated"),
    "ddha":("retroflex", "stop", "voiced", "aspirated"),
    "nna": ("retroflex", "nasal", "voiced", "unaspirated"),
    "ta":  ("dental", "stop", "unvoiced", "unaspirated"),
    "tha": ("dental", "stop", "unvoiced", "aspirated"),
    "da":  ("dental", "stop", "voiced", "unaspirated"),
    "dha": ("dental", "stop", "voiced", "aspirated"),
    "na":  ("dental", "nasal", "voiced", "unaspirated"),
    "pa":  ("labial", "stop", "unvoiced", "unaspirated"),
    "pha": ("labial", "stop", "unvoiced", "aspirated"),
    "ba":  ("labial", "stop", "voiced", "unaspirated"),
    "bha": ("labial", "stop", "voiced", "aspirated"),
    "ma":  ("labial", "nasal", "voiced", "unaspirated"),
    "ya":  ("palatal", "semivowel", "voiced", "unaspirated"),
    "ra":  ("retroflex", "semivowel", "voiced", "unaspirated"),
    "la":  ("dental", "semivowel", "voiced", "unaspirated"),
    "va":  ("labial", "semivowel", "voiced", "unaspirated"),
    "sha": ("palatal", "sibilant", "unvoiced", "unaspirated"),
    "ssa": ("retroflex", "sibilant", "unvoiced", "unaspirated"),
    "sa":  ("dental", "sibilant", "unvoiced", "unaspirated"),
    "ha":  ("glottal", "aspirate", "voiced", "aspirated"),
    "ksha":("conjunct", "conjunct", "unvoiced", "unaspirated"),  # k + ṣa
}

DEVA = {
    "ka":"क","kha":"ख","ga":"ग","gha":"घ","nga":"ङ","ca":"च","cha":"छ","ja":"ज","jha":"झ","nya":"ञ",
    "tta":"ट","ttha":"ठ","dda":"ड","ddha":"ढ","nna":"ण","ta":"त","tha":"थ","da":"द","dha":"ध","na":"न",
    "pa":"प","pha":"फ","ba":"ब","bha":"भ","ma":"म","ya":"य","ra":"र","la":"ल","va":"व",
    "sha":"श","ssa":"ष","sa":"स","ha":"ह","ksha":"क्ष",
}

# ---- per-pole provenance classification (assigned from each varṇa's attested_vs_authored) -------
# fmt: {key: (binding_status, liberating_status, [flags], basis_binding, basis_liberating)}
B, L = "binding", "liberating"
PA, SA, IN, AP = "PRIMARY_ATTESTED", "SECONDARY_ATTESTED", "INFERRED", "AUTHORED_PROVISIONAL"
CO, UN = "CONTRADICTORY", "UNRESOLVED"

CLASSIFICATION = {
    # NAME+DEFINITION binding, lexicon-authored liberating
    "ba":  (PA, AP, [], "ba = avajñā vṛtti (neglect of what has value) — BINDING pole attested (NAME + rich DEFINITION).",
            "regard that attends to worth — lexicon-supplied, supported by the passage's proper-attitude ideal."),
    "cha": (PA, AP, [], "cha = vikalatā vṛtti (nervous breakdown) — MATCHES the binding pole (NAME + DEFINITION).",
            "steadiness that keeps function intact under load — lexicon/framework-supplied; no liberating pole in-source."),
    "da":  (PA, AP, [], "da = peevishness/irritability (krodha/karkaśatā), contrary-reaction illustration — BINDING pole (NAME + DEFINITION).",
            "forbearance — lexicon-supplied."),
    "ddha":(PA, AP, [], "ddha = piśunatā vṛtti (sadistic cruelty), vividly illustrated — BINDING pole (NAME + rich DEFINITION).",
            "compassion shielding the maligned — lexicon-supplied, though least-pain/Neohumanism contrast supports it."),
    "ja":  (PA, AP, [], "ja = ahaṃkāra vṛtti (ego), Aurangzeb illustration of the inflated 'I' — BINDING pole (NAME + ILLUSTRATION).",
            "agency without inflating the I — lexicon-supplied; passage illustrates only the inflated form."),
    "jha": (PA, AP, [], "jha = lolupatā/lobha/lolatā vṛttis (greed), illustrated by nolā — BINDING pole (NAME + ETYMOLOGY).",
            "sufficiency-that-releases — lexicon/framework-supplied; passage gives no pole contrast."),
    "ma":  (PA, AP, [], "ma = praṇāśa (annihilation) + praśraya (indulgence) — BINDING pole (NAME + gloss).",
            "disciplined containment that holds form — lexicon-supplied."),
    "nya": (PA, AP, [], "nya = kapaṭatā vṛtti (hypocrisy), three illustrated forms — all BINDING pole (NAME + FORMS).",
            "transparency, inner=outer — lexicon-supplied; passage illustrates only the hypocritical form."),
    "ya":  (PA, AP, [], "ya = aviśvāsa vṛtti (lack of confidence), illustrated + air/vāyu movement — BINDING pole attested (NAME + DEFINITION).",
            "self-efficacy — lexicon-supplied."),

    # richly-attested binding + attested liberating DIRECTION (wording authored) => liberating INFERRED
    "bha": (PA, IN, [], "bha = mūrcchā vṛtti (losing common sense under a ripu's spell) — attested (NAME + DEFINITION + cure).",
            "pratyāhāra/kīrtana is the ATTESTED remedy/direction; the exact liberated-mode wording is lexicon-supplied."),
    "dha": (PA, IN, [], "dha = tṛṣṇā (limitless craving) — BINDING pole richly attested.",
            "divert all thought to Parama Puruṣa is the ATTESTED cure; 'quenched at its root' wording lexicon-supplied."),
    "na":  (PA, IN, [], "na = moha vṛtti (blind attachment), four categories richly illustrated — BINDING pole.",
            "indifference + redirection to Parama Puruṣa is the ATTESTED direction; wording lexicon-supplied."),
    "ta":  (PA, IN, [], "ta = jāḍya/nidrā (staticity, dullness, inertness) — BINDING pole richly attested.",
            "liberation from jāḍya via expansion, attested through the Tantra etymology; wording lexicon-supplied."),

    # attested faculty/name, binding↔liberating SPLIT applies the framework => binding INFERRED, liberating AUTHORED
    "ga":  (IN, AP, [], "ceṣṭā vṛtti (effort) is attested and valuable in both spheres; the passage does NOT label a binding pole.",
            "poised effort-that-rests / elevating will-force — framework restlessness-vs-poise principle, lexicon-consistent."),
    "ka":  (IN, AP, [], "āśā vṛtti (hope that goads action) is attested; the source does NOT split it into poles.",
            "aspiring hope held without attachment — general attachment principle applied."),
    "kha": (IN, AP, [], "cintā vṛtti attested with personal/impersonal modes; passage does NOT label them binding/liberating.",
            "composed impersonal reflection — framework fixation-vs-detachment principle applied."),
    "nga": (IN, AP, [], "dambha vṛtti (vanity) attested; passage does NOT split it into poles.",
            "conduct without performance — framework display-vs-unselfconscious principle applied."),

    # both poles supported by the passage's own contrast => both PRIMARY_ATTESTED (light authored)
    "gha": (PA, PA, [], "mamatā bounded by time/space/individuality — the binding (bounded attachment) pole, directly supported.",
            "mamatā made to TRANSCEND those boundaries — the liberating pole, directly supported by the passage's contrast."),
    "la":  (PA, PA, [], "kruratā (cruelty) as binding — attested.",
            "compassion/karuṇā as the EXPLICIT counter-measure — attested (both poles; light authored)."),
    "ra":  (PA, PA, [], "sarvanāśa (defeatism) as binding — attested; ra is classically DUAL.",
            "prāṇaśakti / 'I am destined to win' as the liberating direction — attested (both poles in source)."),
    "tta": (PA, PA, ["REACHABILITY_CONTRADICTION"],
            "uncontrolled vitarka (garrulous overstatement — the abusive gentleman) — attested binding pole.",
            "pramita vāk (balanced, measured speech — the helpful gentleman) — attested liberating pole (both in source)."),

    # NAME_ONLY: source explicitly says BOTH poles lexicon-supplied
    "ca":  (AP, AP, [], "viveka distorted (discernment hardening) — lexicon-supplied; NAME ONLY, no pole contrast in-source.",
            "falsehood-discerning insight without egoic superimposition — lexicon-supplied (highest authored component)."),
    "dda": (AP, AP, [], "lajjā as inhibition — lexicon-supplied; NAME ONLY (lajjā attested only as one of the eight pāshas).",
            "acting unhindered by social shame — lexicon-supplied; no pole contrast in-source."),
    "nna": (AP, AP, [], "īrṣyā (envy) as binding — lexicon-supplied; NAME ONLY, no pole contrast in-source.",
            "muditā (sympathetic gladness) — lexicon-supplied; no pole contrast in-source."),

    # NAME+DEF but the ENTRY itself says both poles lexicon-supplied (name matches, pole wording authored)
    "pha": (SA, AP, [], "bhaya vṛtti (fear) attested (NAME + ETIOLOGY, one of eight pāshas); binding=collapse/flight matches the name (lexicon wording).",
            "abhaya / steadiness — authored."),
    "tha": (SA, AP, ["DOC_VS_CODE_TH"],
            "viśāda vṛtti (melancholy) attested (NAME + DEFINITION); binding=dejection matches the name (lexicon wording). Note: थ = aspirated dental stop, NOT English /θ,ð/.",
            "warm buoyancy lifting dejection — authored."),

    # liberating-oriented varṇas (attested liberating side; binding is the DISTORTION)
    "sa":  (IN, PA, [], "sattva clung to as purity/superiority (the golden chain) — standard reading of sattvic attachment (INFERRED).",
            "sa = mokṣa (unqualified liberation) + sattvaguṇa — ATTESTED, classical side liberating-oriented."),
    "va":  (IN, PA, [], "ensconcement gone rigid (over-holding) — the DISTORTION of the attested liberating pole (INFERRED).",
            "va = dharma = ensconcement in one's original stance / 'that which sustains' — ATTESTED, liberating-oriented (light authored)."),
    "sha": (PA, IN, ["SIBILANT_SWAP"],
            "śa = tamoguṇa (static) + kāma (physical worldly desire) — BINDING pole (kāma) ATTESTED (primary text).",
            "sublimation toward mokṣa — INFERRED from the puruṣārtha hierarchy, not stated as a pole."),
    "ksha":(AP, IN, [], "aparā-vidyā owned as control/dogma — lexicon-supplied split.",
            "kṣa = aparā-vidyā (mundane knowledge), complement to ha (parā-vidyā) — attested faculty; instrumental-knowledge reading INFERRED (standard aparā/parā)."),

    # ha: admitted researcher back-fit (both poles authored)
    "ha":  (AP, AP, ["BACK_FIT"],
            "outward/visible vision — researcher-imposed split over attested associations; motivated partly by making 'happy' cohere.",
            "intuitional vision (parā-vidyā), inner/subtle — researcher-imposed split (freeze + pre-register required)."),

    # ssa: pole texts imported from the lexicon's MIS-FILED 'sha' entry
    "ssa": (AP, AP, ["SIBILANT_SWAP"],
            "artha as possessive acquisition — lexicon-supplied AND taken from the lexicon's MIS-FILED 'sha' entry (name ṣa=artha+rajoguṇa is attested).",
            "purposeful action without bondage — lexicon-supplied, from the mis-filed entry."),

    # pa: v3 OPTION B (hatred=binding); meta caveat is stale
    "pa":  (PA, IN, ["META_STALE_PA"],
            "pa = ghṛṇā (hatred/revulsion) — classically THE FETTER OF HATRED (a pāsha) = BINDING (v3 option B, attested).",
            "upward anurakti → devotion — the attested liberating DIRECTION (INFERRED as pole)."),

    # ttha: entry resolves anutāpa; meta caveat still calls it unresolved
    "ttha":(PA, AP, ["META_STALE_TTHA"],
            "ṭha = anutāpa vṛtti (repentance), defined; anutāpa/paścāttāpa='after-heat' etymology — BINDING pole attested.",
            "repentance discharged into acceptance — lexicon-supplied; passage defines the state, not a pole contrast."),
}

# vowels / anusvāra / visarga carry NO meaning in the current mechanism
MISSING_INVENTORY = {
    "vowels": {"members": ["a","ā","i","ī","u","ū","ṛ","ṝ","ḷ","e","ai","o","au"],
               "status": "MISSING",
               "note": "The current mechanism is CONSONANT-ONLY: the decomposer emits no vowel varṇa and the "
                       "polarity table contains none. Vowels carry no binding/liberating pole. Do NOT add meaning here."},
    "anusvara": {"members": ["ṃ (ं)"], "status": "MISSING",
                 "note": "Anusvāra is not emitted by the active bridge and has no pole. Missing, not excluded-by-design."},
    "visarga": {"members": ["ḥ (ः)"], "status": "MISSING",
                "note": "Visarga is not emitted by the active bridge and has no pole. Missing, not excluded-by-design."},
}


def _active_reachable(key):
    """Empirically: can the ACTIVE bridge emit this varṇa on a plausible English input? (probe set)."""
    probes = ["true", "control", "drum", "dread", "faith", "doubt", "freedom", "patience", "courage",
              "pride", "greed", "calm", "boredom", "grief", "peace", "fear", "hope", "love", "trust",
              "joy", "anger", "shame", "wonder", "focus", "clarity", "night", "the", "this", "king",
              "gong", "sing", "measure", "azure", "vision", "yoga", "raja", "shanti", "moksha",
              "church", "choice", "nature", "anthill", "pothole", "thick"]
    for w in probes:
        if key in AB.word_to_varnas(w):
            return True
    return False


def varna_record(key):
    v = json.load(open(TABLE_PATH, encoding="utf-8"))["varnas"][key]
    place, manner, voicing, aspiration = PHON[key]
    b_status, l_status, flags, b_basis, l_basis = CLASSIFICATION[key]
    table_reachable = bool(v.get("practically_reachable"))
    code_reachable = _active_reachable(key)
    rendered = (key, "binding") in BUILD.VARNA_PLAIN
    # active status, with the code-vs-table reachability conflicts surfaced (not silently reconciled)
    if code_reachable and not table_reachable:
        active_status = "ACTIVE_CONTRADICTS_TABLE"    # code emits it; table says practically_reachable=False (D3: tta/dda)
    elif code_reachable:
        active_status = "ACTIVE"
    elif table_reachable:
        active_status = "INACTIVE_CONTRADICTS_TABLE"  # table says reachable; active bridge never emits it (D4: tha, th->ta)
    else:
        active_status = "INACTIVE"
    usability = ("USABLE_IN_PROSE_PACKETS" if (rendered and code_reachable)
                 else "ACTIVE_BUT_NOT_RENDERED" if code_reachable
                 else "INACTIVE_NOT_USABLE")
    return {
        "varna": key,
        "devanagari": DEVA[key],
        "transliteration": v.get("transliteration"),
        "sanskrit_label": v.get("sanskrit_label"),
        "phonology": {"place": place, "manner": manner, "voicing": voicing, "aspiration": aspiration},
        "bridge_reachable_table_field": bool(v.get("bridge_reachable")),
        "practically_reachable_table_field": table_reachable,
        "active_bridge_emits": code_reachable,
        "active_status": active_status,
        "rendered_in_facet_map": rendered,
        "usability_verdict": usability,
        "poles": {
            "binding": {"text": v.get("worldly_binding_distortion"), "provenance_status": b_status, "basis": b_basis},
            "liberating": {"text": v.get("spiritual_liberating_reading"), "provenance_status": l_status, "basis": l_basis},
        },
        "primary_text_scope": v.get("primary_text_scope"),
        "classical_side_attested": v.get("classical_side_attested"),
        "classical_review_status": v.get("classical_review_status"),
        "attested_vs_authored_quote": v.get("attested_vs_authored"),
        "flags": flags,
        "source_location": f"{SRC}.{key}",
    }


# ---- Part C: phonological / composition RULES, each classified ---------------------------------
RULES = [
    ("vowels_dropped", "Vowels are dropped entirely; only consonant varṇas are emitted.",
     "OUT_OF_SCOPE",
     "Consonant-only by construction (varna_bridge_active). Deliberate mechanism scope, but it means every "
     "vowel-borne distinction is discarded — an assumption, not an attested rule."),
    ("aspiration_excluded", "Aspiration is ignored across the stop series (/tʰ/ top and /t/ stop both → ta).",
     "OUT_OF_SCOPE",
     "The table's ASPIRATION COLLAPSE caveat: aspirated word-initial stops classically differ; the bridge collapses them."),
    ("consonant_clusters_presplit", "G2P pre-splits clusters (tr→t+r, dr→d+r) before the bridge sees them.",
     "CONTRADICTORY",
     "The table caveat says clusters pre-split to DENTAL da/ta so retroflex ṭa/ḍa are 'never produced'; but the "
     "ACTIVE bridge's retroflex rule DOES emit ṭa/ḍa (true→ṭa, drum→ḍa). Code vs table conflict (D3)."),
    ("retroflex_before_r", "d/t before r → retroflex ḍa/ṭa (bridge v2 retroflex rule).",
     "CONTRADICTORY",
     "Present and firing in varna_bridge_active, but the table declares it NOT retrofitted and marks ṭa/ḍa "
     "practically_reachable=False. Conflict (D3)."),
    ("th_to_ta", "Merged English 'th' (/θ/ and /ð/) → ta (dental unaspirated stop).",
     "CONTRADICTORY",
     "The ACTIVE bridge (thfix) maps th→ta; the table's TH MIS-MAPPING caveat still says th→tha (viṣāda). "
     "Code vs meta-caveat conflict (D4). Also: /θ,ð/ are fricatives Sanskrit lacks — the target is a convention, not attested."),
    ("dh_inert", "'dh'→da is pre-wired but inert (the G2P never emits dh).",
     "INFERRED", "Structural placeholder; no input path activates it."),
    ("anusvara_ignored", "Anusvāra (ṃ) is not produced.", "MISSING", "No emission path; no pole."),
    ("visarga_ignored", "Visarga (ḥ) is not produced.", "MISSING", "No emission path; no pole."),
    ("sandhi_none", "No sandhi (junction) transformation is applied across word-internal boundaries.",
     "OUT_OF_SCOPE", "Sanskrit phonology's core combinatorics are absent; words are treated as flat phoneme strings."),
    ("gemination_collapsed", "Gemination / doubled consonants are not distinguished.",
     "OUT_OF_SCOPE", "No length distinction survives to a varṇa."),
    ("order_discarded", "Word rule is an UNORDERED, DEDUPED bag/set of varṇas (facet union).",
     "OUT_OF_SCOPE",
     "The code (build_b1_10_control_ext) unions facets over a deduped set; sequence, position, and multiplicity "
     "are all discarded. This is the composition assumption the hypothesis most depends on and is NOT attested."),
    ("multiplicity_discarded", "Repeated varṇas count once (dedup).", "OUT_OF_SCOPE",
     "A varṇa appearing twice contributes the same as once; no intensity/weighting."),
    ("position_discarded", "Initial/medial/final position carries no weight.", "OUT_OF_SCOPE",
     "Classical readings often privilege the initial varṇa; the mechanism does not."),
    ("polarity_selection", "Each cell selects one pole (binding OR liberating) per varṇa for the packet.",
     "AUTHORED_PROVISIONAL",
     "The binding/liberating split itself is authored for most varṇas (see per-pole register); pole selection "
     "inherits that provenance."),
    ("facet_union", "Packet meaning = union of the per-varṇa facet renderings (VARNA_PLAIN).",
     "AUTHORED_PROVISIONAL",
     "Facet render map covers ONLY 11 varṇas (ba da ga ka la ma na pa ra ta tta); all other varṇas have no render "
     "→ any word using them yields an invalid packet (see Gate G0)."),
    ("transliteration_normalization", "Fixed grapheme→varṇa transliteration keys (ba, tta, …).",
     "INFERRED", "Structural convention; internally consistent, not a meaning claim."),
    ("orthography_over_phonology", "Decomposition is driven by English SPELLING via the G2P, not by pronunciation.",
     "CONTRADICTORY",
     "The stated intent (Sanskrit-first / pronunciation-based) conflicts with the actual spelling-driven pipeline "
     "(e.g. faith→ta via 'th', doubt→da+ba+ta). Intent vs implementation conflict."),
]


def rule_record(rid, desc, status, note):
    return {"rule_id": rid, "description": desc, "provenance_status": status, "note": note}


# ---- Part D: word-level composition, three layers kept DISTINCT (not reconciled) ---------------
WORD_COMPOSITION_LAYERS = {
    "layer_1_code_actually_does": {
        "source": "varna_bridge_active.word_to_varnas + build_b1_10_control_ext (VARNA_PLAIN, packet build)",
        "operations": [
            "English spelling → G2P phonemes (grapheme-driven).",
            "Phonemes → consonant varṇas only; vowels dropped; aspiration excluded.",
            "Retroflex rule (d/t before r → ḍa/ṭa); merged 'th' → ta.",
            "Collapse to an UNORDERED, DEDUPED set of varṇas.",
            "Render each varṇa's selected pole via VARNA_PLAIN (11 varṇas only); UNION the facets.",
        ],
        "discards": ["vowels", "order", "position", "multiplicity", "aspiration", "sandhi", "gemination"],
        "provenance_status": "OUT_OF_SCOPE",
        "note": "This is what the mechanism computes. It is a structural procedure, not a validated-meaning claim.",
    },
    "layer_2_docs_claim": {
        "source": "frozen/varna_polarity_table_v3.json meta + B1 docs",
        "claim": "A word's resonance is the composition of its constituent varṇa poles; the table supplies the poles.",
        "provenance_status": "AUTHORED_PROVISIONAL",
        "note": "The docs describe a per-varṇa pole table; they do NOT establish that an unordered facet-union over a "
                "spelling-derived consonant set recovers word meaning. Silent gaps vs Layer 1 are recorded, not reconciled.",
    },
    "layer_3_hypothesis_requires": {
        "source": "Symbol-U hypothesis (varṇas carry meaning)",
        "requirement": "For the mechanism to test the hypothesis, the composition must be (a) pronunciation-based, "
                       "(b) faithful to attested per-varṇa meaning, and (c) sensitive to order/position/multiplicity "
                       "to the extent classical readings are.",
        "provenance_status": "UNRESOLVED",
        "note": "The hypothesis's requirements are NOT met by Layer 1 (spelling-driven, unordered, deduped, "
                "consonant-only, 28/34 liberating poles authored). Gap is stated, not closed.",
    },
}


def build():
    OUT.mkdir(exist_ok=True)
    varnas = [varna_record(k) for k in sorted(CLASSIFICATION.keys())]
    rules = [rule_record(*r) for r in RULES]

    # ---- validation / recomputed counts ----
    pole_counts = {}
    for rec in varnas:
        for side in ("binding", "liberating"):
            s = rec["poles"][side]["provenance_status"]
            pole_counts[s] = pole_counts.get(s, 0) + 1
    rule_counts = {}
    for r in rules:
        rule_counts[r["provenance_status"]] = rule_counts.get(r["provenance_status"], 0) + 1
    active_counts = {}
    for rec in varnas:
        active_counts[rec["active_status"]] = active_counts.get(rec["active_status"], 0) + 1

    contradictions = [
        {"id": "D1", "kind": "DOC_VS_DOC", "flag": "META_STALE_PA",
         "conflict": "important_caveats says pa 'PARTIALLY INVERTS the source-attested pole'; the pa entry says "
                     "v3 follows the attested assignment and 'no inversion flag remains'.",
         "artifacts": ["frozen/varna_polarity_table_v3.json#important_caveats", f"{SRC}.pa"]},
        {"id": "D2", "kind": "DOC_VS_DOC", "flag": "META_STALE_TTHA",
         "conflict": "important_caveats calls ṭha's night/moon vs 'Repentance' reading 'unresolved'; the ttha entry "
                     "treats anutāpa as the vṛtti and night/moon as associations (resolved).",
         "artifacts": ["frozen/varna_polarity_table_v3.json#important_caveats", f"{SRC}.ttha"]},
        {"id": "D3", "kind": "CODE_VS_TABLE", "flag": "REACHABILITY_CONTRADICTION",
         "conflict": "Table sets tta/dda practically_reachable=False and the caveat says retroflex ṭa/ḍa are 'never "
                     "produced'; the ACTIVE bridge emits them (true→ṭa; control→ṭa; drum→ḍa; dread→ḍa).",
         "artifacts": [f"{SRC}.tta", f"{SRC}.dda", "varna_bridge_active.word_to_varnas"]},
        {"id": "D4", "kind": "CODE_VS_DOC", "flag": "DOC_VS_CODE_TH",
         "conflict": "important_caveats' TH MIS-MAPPING says 'th' → tha (viṣāda/melancholy); the ACTIVE bridge (thfix) "
                     "maps merged 'th' (/θ,ð/) → ta (faith→ta).",
         "artifacts": ["frozen/varna_polarity_table_v3.json#important_caveats", "varna_bridge_active.word_to_varnas"]},
        {"id": "D5", "kind": "PROVENANCE_HAZARD", "flag": "SIBILANT_SWAP",
         "conflict": "śa/ṣa are swapped in v2 AND the lexicon; v3 follows the primary text, but ssa's pole TEXTS are "
                     "imported from the lexicon's mis-filed 'sha' entry (documented, resolved-in-v3 hazard, not an open conflict).",
         "artifacts": [f"{SRC}.sha", f"{SRC}.ssa"]},
        {"id": "D6", "kind": "PROVENANCE_HAZARD", "flag": "BACK_FIT",
         "conflict": "ha's binding/liberating split is 'researcher-imposed; motivated partly by making \"happy\" cohere' "
                     "— an admitted back-fit (self-consistent across table + meta, but authored, not attested).",
         "artifacts": [f"{SRC}.ha", "frozen/varna_polarity_table_v3.json#important_caveats"]},
    ]
    unresolved_contradictions = [c for c in contradictions if c["kind"].endswith(("VS_DOC", "VS_TABLE")) or c["kind"] == "CODE_VS_DOC"]

    missing_categories = list(MISSING_INVENTORY.keys())

    readiness = "BLOCKED_BY_SOURCE_CONTRADICTIONS"
    readiness_reason = (
        "Four cross-artifact contradictions (D1 pa meta-stale, D2 ṭha meta-stale, D3 tta/dda code-vs-table "
        "reachability, D4 th code-vs-doc) must be resolved before any inventory decision. Secondary blocker: "
        f"{pole_counts.get('AUTHORED_PROVISIONAL', 0)} authored-provisional poles and a wholly MISSING vowel inventory."
    )

    validation = {
        "n_varnas_classified": len(varnas),
        "all_34_accounted": len(varnas) == 34,
        "pole_provenance_counts": pole_counts,
        "n_poles_total": sum(pole_counts.values()),
        "rule_provenance_counts": rule_counts,
        "active_status_counts": active_counts,
        "n_rendered_in_facet_map": sum(1 for r in varnas if r["rendered_in_facet_map"]),
        "missing_inventory_categories": missing_categories,
        "n_unresolved_contradictions": len(unresolved_contradictions),
    }

    register = {
        "artifact_type": "varna_provenance_register",
        "schema_version": "1.0",
        "scope": "Part E Step 1 — provenance of the CURRENT active varṇa mechanism (docs/data-only).",
        "sources_read": {
            "table": SRC,
            "active_bridge": "varna_bridge_active.word_to_varnas (bridge_v2_plus_theta_eth_ta)",
            "facet_map": "build_b1_10_control_ext.VARNA_PLAIN (11 varṇas)",
        },
        "status_definitions": {
            "PRIMARY_ATTESTED": "stated by the operator-supplied primary classical text",
            "SECONDARY_ATTESTED": "vṛtti NAME attested; pole reading is the lexicon's, not a primary-text pole contrast",
            "INFERRED": "attested faculty/direction, but the binding↔liberating SPLIT applies the framework's principle",
            "AUTHORED_PROVISIONAL": "pole text lexicon/researcher-supplied; no primary-text support",
            "CONTRADICTORY": "two source artifacts (table/meta/code) assert conflicting facts",
            "MISSING": "inventory category carrying NO meaning in the current mechanism",
            "OUT_OF_SCOPE": "deliberately excluded from the current mechanism",
            "UNRESOLVED": "flagged in-source as an open question, not settled",
        },
        "varnas": varnas,
        "missing_inventory": MISSING_INVENTORY,
        "rules": rules,
        "word_composition_layers": WORD_COMPOSITION_LAYERS,
        "contradictions": contradictions,
        "unresolved_contradiction_ids": [c["id"] for c in unresolved_contradictions],
        "validation": validation,
        "readiness_verdict": readiness,
        "readiness_reason": readiness_reason,
        "guardrails": "Docs/data-only. No mapping/run01/Track G/frozen change. No ontology / semantic-truth / "
                      "Sanskrit-privilege / generation-utility claim. Structure, not validated meaning.",
    }

    reg_path = OUT / "varna_provenance_register.json"
    reg_path.write_text(json.dumps(register, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # CSV (flat per-pole)
    csv_path = OUT / "varna_provenance_register.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["varna", "devanagari", "translit", "place", "manner", "voicing", "aspiration",
                    "active_status", "rendered_in_facet_map", "pole", "pole_text",
                    "provenance_status", "flags", "source_location"])
        for rec in varnas:
            for side in ("binding", "liberating"):
                p = rec["poles"][side]
                w.writerow([rec["varna"], rec["devanagari"], rec["transliteration"],
                            rec["phonology"]["place"], rec["phonology"]["manner"], rec["phonology"]["voicing"],
                            rec["phonology"]["aspiration"], rec["active_status"], rec["rendered_in_facet_map"],
                            side, p["text"], p["provenance_status"], ";".join(rec["flags"]), rec["source_location"]])

    rule_path = OUT / "rule_provenance_register.json"
    rule_path.write_text(json.dumps({"rules": rules, "counts": rule_counts}, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")

    wc_path = OUT / "word_composition_layers.json"
    wc_path.write_text(json.dumps(WORD_COMPOSITION_LAYERS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return register, {"register": reg_path, "csv": csv_path, "rules": rule_path, "word_composition": wc_path}


def _sha16(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:16]


if __name__ == "__main__":
    reg, paths = build()
    print("readiness:", reg["readiness_verdict"])
    print("pole counts:", reg["validation"]["pole_provenance_counts"])
    print("rule counts:", reg["validation"]["rule_provenance_counts"])
    print("active counts:", reg["validation"]["active_status_counts"])
    print("all 34:", reg["validation"]["all_34_accounted"])
    print("unresolved contradictions:", reg["validation"]["n_unresolved_contradictions"])
    for name, p in paths.items():
        print(f"  {name}: {p.name}  sha16={_sha16(p)}")
