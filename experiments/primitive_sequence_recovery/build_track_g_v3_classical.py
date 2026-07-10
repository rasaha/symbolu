"""Build a DRAFT v3 varṇa polarity table that is GROUNDED IN THE CLASSICAL SOURCE — the careful per-varṇa
classical update that v2 did NOT do (docs/data build; NO model, NO generation, NO test re-pointing).

Method (honest, seeded — not a finished re-derivation):
  - CLASSICAL BACKBONE = b1_2_varna_source_lexicon.json. For each varṇa it carries the source-attested Sanskrit
    vṛtti label, Sarkar source_note, which pole is classically attested (classical_side), the binding/liberating
    expressions, and the rewrite_status (the LIBERATING/counter side is largely author-rewritten, not attested).
  - OPERATOR PRIMARY-TEXT CORRECTIONS = b1_2_ha_pa_fidelity_correction.json (ha, pa) layered on top, keeping the
    attested-vs-authored flags and (for pa) the note that it PARTIALLY INVERTS the source-attested pole.
  - v2 values are carried alongside for DRIFT comparison (e.g. v2 ha binding='night' = the domain of the OPPOSITE
    varṇa ṭha, which v2 dropped from its key set entirely).
  - EVERY entry gets a classical_review_status: only ha/pa are PRIMARY_TEXT_PROVIDED; all others are
    LEXICON_ATTESTED_PENDING_PRIMARY_VERIFICATION — the careful update proceeds per-varṇa as the operator supplies
    primary classical text (exactly as was done for ha, pa).

Output: frozen/track_g_varna_polarity_table_v3_classical_DRAFT.json — status DRAFT, applied=false. NOT wired into
any test; promoting it requires operator per-varṇa sign-off, then re-point builders + re-freeze + pre-register
(anti-circularity). RESONANCE refinement only — no ontology/semantic-truth/Sanskrit-privilege/GENUTILITY/
ONTOLOGICAL_SIGNAL claim. B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V2_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
LEX_FILE = HERE / "b1_2_mapping_fidelity" / "b1_2_varna_source_lexicon.json"
CORR_FILE = HERE / "b1_2_mapping_fidelity" / "b1_2_ha_pa_fidelity_correction.json"
OUT_FILE = FROZEN / "track_g_varna_polarity_table_v3_classical_DRAFT.json"

# classical ha↔ṭha note (primary text the operator supplied earlier); ṭha = ttha key
TTHA_CLASSICAL_NOTE = ("Classical (Sarkar): ṭha (ttha) is the acoustic root of nighttime, of the moon, of "
                       "bhúvarloka, and of the kāmamaya kośa — the OPPOSITE of ha (day/sun/svarloka/parā-vidyā). "
                       "The source lexicon instead glosses ttha as 'Repentance'; this discrepancy needs primary "
                       "verification before ttha's poles are fixed.")


def _sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def build():
    v2 = json.loads(V2_FILE.read_text())
    v2v = v2["varnas"]
    lex_entries = json.loads(LEX_FILE.read_text())["entries"]
    lex = {e["lexicon_key"]: e for e in lex_entries}
    corr = {c["varna"]: c for c in json.loads(CORR_FILE.read_text())["corrections"]}
    bridge_reachable = set(v2v.keys())   # the 25 keys the English G2P bridge can actually produce (test-relevant)

    varnas = {}
    for key in sorted(lex):
        e = lex[key]
        sap = e.get("source_attested_pole", {})
        v2e = v2v.get(key, {})
        # default binding/liberating = classical-lexicon expressions
        binding = e.get("binding_expression", "")
        liberating = e.get("liberating_expression", "")
        review = "LEXICON_ATTESTED_PENDING_PRIMARY_VERIFICATION"
        provenance = "b1_2_source_lexicon (Sarkar-attributed)"
        authored_note = ("Attested side = classical_side below; the OTHER pole is largely author counter-rewritten "
                         f"(lexicon rewrite_status={e.get('rewrite_status')!r}) — flagged, not validated.")
        # operator primary-text corrections for ha, pa
        if key in corr:
            pg = corr[key]["proposed_gloss"]
            binding, liberating = pg["binding"], pg["liberating"]
            review = "PRIMARY_TEXT_PROVIDED_BY_OPERATOR"
            provenance = "operator primary-text correction (b1_2_ha_pa_fidelity_correction.json)"
            authored_note = corr[key].get("source_attested_vs_authored", authored_note)

        v2_binding = v2e.get("worldly_binding_distortion")
        v2_liberating = v2e.get("spiritual_liberating_reading")
        differs = (v2_binding != binding) or (v2_liberating != liberating)
        entry = {
            "varna": e.get("varna", key), "transliteration": e.get("transliteration", key),
            "bridge_reachable": key in bridge_reachable,
            "sanskrit_label": sap.get("sanskrit_label"), "english_rendering": sap.get("english_rendering"),
            "classical_side_attested": sap.get("classical_side"),
            "source_note": e.get("source_note"),
            "worldly_binding_distortion": binding,
            "spiritual_liberating_reading": liberating,
            "functional_operation": e.get("functional_operation"),
            "contrast_boundary": e.get("contrast_boundary"),
            "attested_vs_authored": authored_note,
            "classical_review_status": review, "provenance": provenance,
            "v2_binding": v2_binding, "v2_liberating": v2_liberating, "differs_from_v2": differs,
        }
        if key == "ha":
            entry["severe_v2_drift"] = ("v2 binding='night/darkness' imported the domain of the OPPOSITE varṇa ṭha "
                                        "into ha's own cell (category error); v2 also folded the COMPOUND hao's "
                                        "táṇḍava into bare ha.")
        if key == "ttha":
            entry["classical_discrepancy"] = TTHA_CLASSICAL_NOTE
        varnas[key] = entry

    n_reach = sum(1 for k in varnas if varnas[k]["bridge_reachable"])
    n_primary = sum(1 for k in varnas if varnas[k]["classical_review_status"].startswith("PRIMARY_TEXT"))
    doc = {
        "artifact_type": "track_g_varna_polarity_table",
        "schema_version": "v3_classical_grounded",
        "representation_version": "track_g_v3_classical",
        "status": "DRAFT_REQUIRES_PER_VARNA_CLASSICAL_SIGNOFF",
        "applied": False, "wired_into_tests": False, "supersedes_when_applied": "track_g_v2_named_vritti",
        "methodology": ("Classical backbone = b1_2 source lexicon (Sarkar-attributed per varṇa) + operator "
                        "primary-text corrections (ha, pa). v2 carried alongside for drift. This is a SEEDED "
                        "framework for the careful per-varṇa classical update — NOT a finished re-derivation."),
        "how_to_complete": ("For each varṇa with classical_review_status=LEXICON_ATTESTED_PENDING_PRIMARY_"
                            "VERIFICATION, supply the primary classical text (as done for ha, pa), verify/adjust "
                            "the poles, mark attested-vs-authored, and set review status to PRIMARY_TEXT_PROVIDED."),
        "important_caveats": [
            "The LIBERATING pole is author counter-rewritten for most varṇas (lexicon rewrite_status) — not attested.",
            "pa's operator reading PARTIALLY INVERTS the source-attested pole (ghṛṇā = the binding fetter). Recorded.",
            "ha's binding/liberating SPLIT is researcher-authored over attested associations; motivated partly by "
            "making 'happy' cohere — MUST be frozen + pre-registered before any pole-test word/context authoring.",
            "ṭha (ttha) classical night/moon reading vs lexicon 'Repentance' is unresolved — see classical_discrepancy.",
            "Only 25 of 34 keys are bridge_reachable from English G2P; the 9 aspirates are reference-only.",
        ],
        "resonance_framing": "RESONANCE refinement, not validated meaning. No ontology, no semantic truth, no "
                             "Sanskrit privilege, no GENUTILITY_*, no ONTOLOGICAL_SIGNAL.",
        "to_go_live_checklist": [
            "1. Complete per-varṇa classical verification (fill PRIMARY_TEXT for the pending entries).",
            "2. Operator sign-off (set status APPLIED); rename to track_g_varna_polarity_table_v3.json.",
            "3. Re-point builders (pole-DiD / pole-sanity) to v3; re-derive packets; re-freeze declarations.",
            "4. Pre-register the pole test BEFORE authoring any target words/contexts (anti-circularity).",
            "5. Report results as RESONANCE legibility only — never validated meaning.",
        ],
        "source_hashes": {"track_g_varna_polarity_table_v2_named_vritti.json": _sha(V2_FILE),
                          "b1_2_varna_source_lexicon.json": _sha(LEX_FILE),
                          "b1_2_ha_pa_fidelity_correction.json": _sha(CORR_FILE)},
        "n_varnas": len(varnas), "n_bridge_reachable": n_reach, "n_primary_text_verified": n_primary,
        "n_pending_classical_verification": len(varnas) - n_primary,
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "motto": "Structure, not validated meaning.",
        "varnas": varnas,
    }
    OUT_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    return doc


if __name__ == "__main__":
    d = build()
    print(f"wrote {OUT_FILE.name} | n={d['n_varnas']} bridge_reachable={d['n_bridge_reachable']} "
          f"primary_verified={d['n_primary_text_verified']} pending={d['n_pending_classical_verification']} "
          f"status={d['status']}")
    for k in ("ha", "pa", "ttha", "ka", "la", "na", "nga", "ta", "va"):
        e = d["varnas"].get(k)
        if e:
            print(f"  {k:4} [{e['classical_review_status'][:12]}] {str(e['sanskrit_label']):16} "
                  f"BIND: {str(e['worldly_binding_distortion'])[:44]}")
