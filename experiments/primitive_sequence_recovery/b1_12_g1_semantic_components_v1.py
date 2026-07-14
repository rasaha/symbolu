#!/usr/bin/env python3
"""B1.12 Gate-G1 — coverage-complete ordered component-descriptor instrument (v1.2) — firewalled builder.

Replaces the underdetermined opaque-ID task (reassessment bb2051e) with a semantic ordered-component task.
Role-separated stages (emulated via separate functions + separate commits):

  stage1_inventory()   Role A — extract the required (type,unit) inventory from the FROZEN G0 parser outputs and
                       the frozen-lexicon source status. Does NOT read selected-word meanings.
  stage2_descriptors() Role B — author descriptors PER VARṆA IDENTITY, verbatim from the frozen merged lexicon
                       (Tier A, fixed 'binding' pole), + a mechanical case/whitespace normalization (no
                       truncation/paraphrase). Receives ONLY identities + lexicon, never the word->meaning map.
  stage3_audit()       Role C — descriptor quality / source / coverage / leakage audits + A/B/D render spec +
                       evaluator-task spec; emits the versioned G1 verdict.

Deterministic; NO judges, NO run, NO contexts beyond rigid templates. Does not alter G0/pool/parser/lexicon.
EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results" / "b1_12_g1_semantic_components_v1"
G0_PARSER_OUTPUTS = HERE / "results" / "b1_12_g0_audit_v1" / "parser_outputs.json"
LEXICON = HERE / "frozen" / "varna_native_stage1_merged_v1.json"
POOL = HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json"

SELECTED = ["W03", "W15", "W20", "W23", "W30", "W35"]
FIXED_POLE = "binding"          # declared fixed polarity; no switching across entries
PROGRESSION_TERMS = ["becomes", "leads to", "transforms", "resolves", "culminates", "balances", "removes"]
# lexical markers of the affliction/psychological-tendency domain (for domain classification only)
AFFLICTION_MARKERS = ["desire", "attachment", "doubt", "grasping", "clinging", "melancholy", "striving",
                      "irritability", "hypocrisy", "ego", "moha", "kāma", "infatuation", "defeat", "longing",
                      "peevish", "fixation", "inflation", "self-absorption", "obsessive", "dejection",
                      "concealment", "sattvic", "aviśvāsa", "viśāda", "sarvanāśa", "over"]


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _norm(text):
    """Mechanical normalization ONLY: collapse whitespace + lowercase first char. No truncation/paraphrase."""
    t = re.sub(r"\s+", " ", text).strip()
    return t[:1].lower() + t[1:] if t else t


# ---------------------------------------------------------------- stage 1 (Role A)
def stage1_inventory():
    OUT.mkdir(parents=True, exist_ok=True)
    po = {w["id"]: w for w in json.loads(G0_PARSER_OUTPUTS.read_text())["words"]}
    lex = {r["canonical_parser_unit"]: r for r in json.loads(LEXICON.read_text(encoding="utf-8"))["rows"]}
    # union of identities across the selected six (frozen set; instrument completion, not word selection)
    ident_rows = {}
    for c in SELECTED:
        for u in po[c]["atomic_varnas"]:
            key = (u["type"], u["unit"])
            rec = ident_rows.setdefault(key, {"type": u["type"], "unit": u["unit"],
                                              "aspirated": u.get("aspirated"), "occurrences": 0})
            rec["occurrences"] += 1
    identities = []
    for (t, u), rec in sorted(ident_rows.items()):
        lr = lex.get(u)
        covered = lr is not None and (lr.get(f"{FIXED_POLE}_vritti") not in (None, ""))
        identities.append({
            "identity_type": t, "unit": u, "aspirated": rec["aspirated"], "occurrences": rec["occurrences"],
            "in_frozen_lexicon": lr is not None,
            "activation_scope": (lr.get("activation_scope") if lr else None),
            "category": (lr.get("category") if lr else None),
            "source_backed": covered, "source_tier": ("A_SOURCE_BACKED" if covered else "B_DEVELOPMENTAL_GAP"),
        })
    inv = {
        "schema": "b1_12_required_varna_inventory_v1",
        "label": "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE",
        "role": "A_INVENTORY_EXTRACTOR (did NOT read selected-word meanings)",
        "selected_six": SELECTED, "fixed_pole": FIXED_POLE,
        "n_distinct_identities": len(identities),
        "n_source_backed": sum(1 for i in identities if i["source_backed"]),
        "n_developmental_gap": sum(1 for i in identities if not i["source_backed"]),
        "vowels": sorted(i["unit"] for i in identities if i["identity_type"] == "vowel"),
        "consonants": sorted(i["unit"] for i in identities if i["identity_type"] == "consonant"),
        "identities": identities,
        "provenance": {"g0_parser_outputs_sha256": _sha(G0_PARSER_OUTPUTS),
                       "lexicon_sha256": _sha(LEXICON)},
    }
    (OUT / "required_varna_inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2,
                                                                  sort_keys=True), encoding="utf-8")
    cov = {
        "schema": "b1_12_coverage_report_v1",
        "selected_set_coverage_pct": round(100.0 * inv["n_source_backed"] / inv["n_distinct_identities"], 2),
        "n_required": inv["n_distinct_identities"], "n_source_backed": inv["n_source_backed"],
        "n_developmental_gap": inv["n_developmental_gap"],
        "coverage_outcome": ("G1_COMPONENT_COVERAGE_COMPLETE" if inv["n_developmental_gap"] == 0
                             else "G1_COMPONENT_COVERAGE_INCOMPLETE"),
        "note": ("all required identities have a frozen binding-pole gloss (consonants CONFIRMATORY_BACKBONE, "
                 "vowels DEVELOPMENT_ONLY); coverage is complete from the merged lexicon (not from VARNA_PLAIN)."),
    }
    (OUT / "coverage_report.json").write_text(json.dumps(cov, indent=2, sort_keys=True), encoding="utf-8")
    return inv, cov


# ---------------------------------------------------------------- stage 2 (Role B)
def stage2_descriptors():
    inv = json.loads((OUT / "required_varna_inventory.json").read_text())
    lex = {r["canonical_parser_unit"]: r for r in json.loads(LEXICON.read_text(encoding="utf-8"))["rows"]}
    entries = []
    for i, ident in enumerate(inv["identities"], 1):
        u, t = ident["unit"], ident["identity_type"]
        lr = lex.get(u)
        orig = (lr.get(f"{FIXED_POLE}_vritti") if lr else None)
        prov = (lr.get(f"{FIXED_POLE}_pole_provenance") if lr else None)
        if orig:
            entries.append({
                "atomic_identity": f"{t}:{u}", "stable_component_id": f"C{i:02d}",
                "source_tier": "A_SOURCE_BACKED", "source_status": ident["activation_scope"],
                "original_frozen_gloss": orig,
                "normalized_component_descriptor": _norm(orig),
                "source_reference": f"frozen/varna_native_stage1_merged_v1.json#{u} ({FIXED_POLE}_vritti)",
                "source_hash": _sha(LEXICON),
                "review_status": "PENDING_STAGE3_AUDIT",
                "development_only": ident["activation_scope"] == "DEVELOPMENT_ONLY",
                "notes": f"provenance:{prov}", "polarity": FIXED_POLE,
            })
        else:
            entries.append({
                "atomic_identity": f"{t}:{u}", "stable_component_id": f"C{i:02d}",
                "source_tier": "B_DEVELOPMENTAL_GAP", "source_status": "UNMAPPED",
                "original_frozen_gloss": None, "normalized_component_descriptor": None,
                "source_reference": None, "source_hash": None, "review_status": "UNMAPPED",
                "development_only": True, "notes": "no frozen gloss; would require developmental authoring",
                "polarity": FIXED_POLE,
            })
    dmap = {"schema": "b1_12_component_descriptor_map_draft_v1", "fixed_pole": FIXED_POLE,
            "normalization": "mechanical whitespace-collapse + first-char lowercase; NO truncation/paraphrase",
            "n_entries": len(entries), "entries": entries}
    (OUT / "component_descriptor_map_draft.json").write_text(json.dumps(dmap, ensure_ascii=False, indent=2,
                                                                        sort_keys=True), encoding="utf-8")
    # source audit
    src = {"schema": "b1_12_component_descriptor_source_audit_v1",
           "n_entries": len(entries),
           "n_tier_A_source_backed": sum(1 for e in entries if e["source_tier"] == "A_SOURCE_BACKED"),
           "n_tier_B_developmental": sum(1 for e in entries if e["source_tier"] == "B_DEVELOPMENTAL_GAP"),
           "n_unmapped": sum(1 for e in entries if e["review_status"] == "UNMAPPED"),
           "all_source_backed_verbatim_preserved": all(
               e["original_frozen_gloss"] is not None for e in entries if e["source_tier"] == "A_SOURCE_BACKED"),
           "lexicon_sha256": _sha(LEXICON),
           "polarity_consistent_no_switching": True,
           "note": "every source-backed entry preserves the exact frozen binding-pole gloss verbatim."}
    (OUT / "component_descriptor_source_audit.json").write_text(json.dumps(src, indent=2, sort_keys=True),
                                                                encoding="utf-8")
    return dmap, src


# ---------------------------------------------------------------- stage 3 (Role C)
def _domain_of(text):
    tl = text.lower()
    return "affliction_tendency" if any(m in tl for m in AFFLICTION_MARKERS) else "other"


def stage3_audit():
    inv = json.loads((OUT / "required_varna_inventory.json").read_text())
    cov = json.loads((OUT / "coverage_report.json").read_text())
    dmap = json.loads((OUT / "component_descriptor_map_draft.json").read_text())
    pool = {w["id"]: w for w in json.loads(POOL.read_text(encoding="utf-8"))["words"]}
    entries = [e for e in dmap["entries"] if e["normalized_component_descriptor"]]

    # ---- descriptor quality diagnostics (descriptor-level ONLY) ----
    descs = [e["normalized_component_descriptor"] for e in entries]
    lens = [len(d) for d in descs]
    vowel_lens = [len(e["normalized_component_descriptor"]) for e in entries
                  if e["atomic_identity"].startswith("vowel:")]
    cons_lens = [len(e["normalized_component_descriptor"]) for e in entries
                 if e["atomic_identity"].startswith("consonant:")]
    dev_lens = [len(e["normalized_component_descriptor"]) for e in entries if e["development_only"]]
    conf_lens = [len(e["normalized_component_descriptor"]) for e in entries if not e["development_only"]]
    exact_dupes = len(descs) - len(set(descs))
    prog_hits = {e["atomic_identity"]: [w for w in PROGRESSION_TERMS
                                        if w in e["normalized_component_descriptor"].lower()]
                 for e in entries if any(w in e["normalized_component_descriptor"].lower()
                                         for w in PROGRESSION_TERMS)}
    # embedded illustrative examples / parentheticals (prose-packet confound signal)
    example_hits = {e["atomic_identity"]: True for e in entries
                    if "(" in e["original_frozen_gloss"] or "'" in e["original_frozen_gloss"]
                    or "—" in e["original_frozen_gloss"]}
    domains = {e["atomic_identity"]: _domain_of(e["original_frozen_gloss"]) for e in entries}
    n_affliction = sum(1 for d in domains.values() if d == "affliction_tendency")

    def sep(a, b):   # ranges disjoint? -> perfect length classifier
        return (min(a) > max(b)) or (min(b) > max(a)) if (a and b) else False
    length_leak_vowel_consonant = sep(vowel_lens, cons_lens)
    tier_leak = sep(dev_lens, conf_lens)

    quality_outcomes = []
    if exact_dupes:
        quality_outcomes.append("DESCRIPTOR_COLLAPSE")
    if length_leak_vowel_consonant:
        quality_outcomes.append("DESCRIPTOR_LENGTH_LEAKAGE")
    if tier_leak:
        quality_outcomes.append("DESCRIPTOR_SOURCE_TIER_LEAKAGE")
    if n_affliction >= len(entries) * 0.6:
        quality_outcomes.append("DESCRIPTOR_NEUTRALITY_FAILURE")   # affliction-domain, orthogonal to referents
    if not quality_outcomes:
        quality_outcomes.append("DESCRIPTOR_MAP_READY")

    quality = {
        "schema": "b1_12_descriptor_quality_audit_v1",
        "n_descriptors": len(descs), "exact_duplicates": exact_dupes,
        "length_min_max_mean": [min(lens), max(lens), round(sum(lens) / len(lens), 1)],
        "vowel_length_range": [min(vowel_lens), max(vowel_lens)] if vowel_lens else None,
        "consonant_length_range": [min(cons_lens), max(cons_lens)] if cons_lens else None,
        "development_length_range": [min(dev_lens), max(dev_lens)] if dev_lens else None,
        "confirmatory_length_range": [min(conf_lens), max(conf_lens)] if conf_lens else None,
        "length_leakage_vowel_vs_consonant_disjoint": length_leak_vowel_consonant,
        "source_tier_leakage_dev_vs_conf_disjoint": tier_leak,
        "progression_term_hits": prog_hits,
        "embedded_example_or_parenthetical_hits": sorted(example_hits.keys()),
        "n_with_embedded_examples": len(example_hits),
        "descriptor_domain": domains, "n_affliction_tendency": n_affliction,
        "candidate_meaning_domain": "ordinary_concrete_referent",
        "domain_match": False,
        "quality_outcomes": quality_outcomes,
    }
    (OUT / "descriptor_quality_audit.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2,
                                                                  sort_keys=True), encoding="utf-8")

    # ---- A/B/D render spec (rigid, non-narrative) ----
    render_spec = {
        "schema": "b1_12_arm_render_spec_v1",
        "template": "position i: <normalized_component_descriptor>   (one line per varṇa, no connectives)",
        "arm_A_true_order": "components in exact frozen pronunciation-derived order; repetition preserved",
        "arm_B_scramble": {"same_multiset": True, "same_count": True, "same_template": True,
                           "fixed_seed": 20260101, "must_differ_from_A": True, "no_resample_after_output": True},
        "arm_D_unordered_inventory": {"same_multiset": True, "canonical_order": "by stable_component_id",
                                      "no_pronunciation_order_semantics": True, "same_footprint": True},
        "optional_arm_E_bigram": "secondary only; ordered adjacent descriptor pairs",
        "prohibited": ["synthesized prose paragraphs", "connectives between positions",
                       "progression/causal language", "word-level packet prose"],
        "blocked_reason_if_any": None,
    }
    (OUT / "arm_render_spec.json").write_text(json.dumps(render_spec, ensure_ascii=False, indent=2,
                                                         sort_keys=True), encoding="utf-8")

    # ---- leakage control spec (definitions + spec-level findings; NO judges run) ----
    leakage_spec = {
        "schema": "b1_12_leakage_control_spec_v1",
        "primary_task": "candidate-relative semantic matching; choose the ordinary meaning best represented",
        "required_ablations": ["first_position_only", "last_position_only", "unordered_descriptor_inventory",
                               "single_most_diagnostic_descriptor", "descriptor_content_masked",
                               "candidate_meanings_without_component_info"],
        "leakage_tolerance": "any ablation baseline at or above chance (1/6) beyond CI => CONTROL_LEAKAGE",
        "spec_level_findings": {
            "descriptor_length_leaks_cv_pattern": length_leak_vowel_consonant,
            "note": ("with the frozen descriptors, vowel vs consonant descriptor LENGTH is perfectly separable, "
                     "so content-UNmasked formatting already exposes each word's consonant/vowel skeleton "
                     "(a strong structural fingerprint) BEFORE any judge is run — a pre-run leakage failure."),
        },
    }
    (OUT / "leakage_control_spec.json").write_text(json.dumps(leakage_spec, ensure_ascii=False, indent=2,
                                                             sort_keys=True), encoding="utf-8")

    # ---- verdict ----
    coverage_complete = cov["coverage_outcome"] == "G1_COMPONENT_COVERAGE_COMPLETE"
    descriptor_ready = quality_outcomes == ["DESCRIPTOR_MAP_READY"]
    leakage_ok = not leakage_spec["spec_level_findings"]["descriptor_length_leaks_cv_pattern"]
    domain_ok = quality["domain_match"]
    if not coverage_complete:
        verdict = "G1_BLOCKED_COMPONENT_COVERAGE"
    elif not descriptor_ready or not domain_ok:
        verdict = "G1_BLOCKED_DESCRIPTOR_QUALITY"
    elif not leakage_ok:
        verdict = "G1_BLOCKED_CONTROL_LEAKAGE"
    else:
        verdict = "G1_READY_FOR_SEMANTIC_ORDER_USABILITY_PROBE"

    manifest_verdict = {
        "coverage_complete": coverage_complete, "descriptor_ready": descriptor_ready,
        "domain_match": domain_ok, "pre_run_length_leakage": not leakage_ok,
        "quality_outcomes": quality_outcomes, "verdict": verdict,
    }
    (OUT / "g1_v1_2_verdict.json").write_text(json.dumps(manifest_verdict, indent=2, sort_keys=True),
                                              encoding="utf-8")
    return {"quality": quality, "verdict": verdict, "coverage": cov}


if __name__ == "__main__":
    inv, cov = stage1_inventory()
    dmap, src = stage2_descriptors()
    res = stage3_audit()
    print(json.dumps({"coverage_pct": cov["selected_set_coverage_pct"],
                      "coverage_outcome": cov["coverage_outcome"],
                      "n_source_backed": inv["n_source_backed"], "n_gap": inv["n_developmental_gap"],
                      "quality_outcomes": res["quality"]["quality_outcomes"],
                      "vowel_len_range": res["quality"]["vowel_length_range"],
                      "consonant_len_range": res["quality"]["consonant_length_range"],
                      "n_affliction": res["quality"]["n_affliction_tendency"],
                      "domain_match": res["quality"]["domain_match"],
                      "verdict": res["verdict"]}, ensure_ascii=False, indent=2))
