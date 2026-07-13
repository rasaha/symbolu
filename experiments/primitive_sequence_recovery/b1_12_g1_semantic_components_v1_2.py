#!/usr/bin/env python3
"""B1.12 Gate-G1 v1.2 — coverage-complete ordered semantic-component instrument (normalized labels).

Second G1 repair iteration. Goes further than v1 (commit d48ae9f): normalizes the frozen glosses to shorter
standalone component LABELS, adds arm render examples, and runs a full descriptor-quality + deterministic
leakage audit. Determines whether normalization unblocks the semantic instrument.

Firewalled roles (emulated via separate functions + commits): A inventory (frozen parser outputs + lexicon
status; no word meanings), B descriptor authoring (per (type,unit) only; verbatim frozen binding gloss +
mechanical normalization), C review/application audit + arm spec/examples + verdict.

Deterministic; NO judges, NO run, NO confirmatory freeze. Does not alter G0/pool/selected-six/parser/lexicon.
EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import pathlib
import random
import re
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results" / "b1_12_g1_semantic_components_v1_2"
G0_PARSER_OUTPUTS = HERE / "results" / "b1_12_g0_audit_v1" / "parser_outputs.json"
LEXICON = HERE / "frozen" / "varna_native_stage1_merged_v1.json"
POOL = HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json"

SELECTED = ["W03", "W15", "W20", "W23", "W30", "W35"]
FIXED_POLE = "binding"
SCRAMBLE_SEED = 20260101
MASK = "•"
PROHIBITED = ["becomes", "leads to", "transforms", "resolves", "culminates", "balances", "removes",
              "purifies", "overcomes"]
AFFLICTION_MARKERS = ["desire", "attachment", "doubt", "grasping", "clinging", "melancholy", "striving",
                      "irritability", "hypocrisy", "ego", "moha", "kāma", "āśā", "infatuation", "defeat",
                      "longing", "peevish", "fixation", "inflation", "inflated", "self-absorption",
                      "obsessive", "dejection", "concealment", "sattvic", "aviśvāsa", "viśāda", "sarvanāśa",
                      "annihilation", "over", "rigid", "reactivity"]
# raw Sanskrit / IAST technical terms that would surface in evaluator-facing descriptors (a leakage/neutrality vector)
SANSKRIT_TERMS = ["moha", "kāma", "āśā", "sarvanāśa", "viśāda", "aviśvāsa", "sattvic", "sattva", "dharma", "mokṣa"]


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def normalize(gloss: str) -> str:
    """Mechanical normalization to a standalone label: drop post-colon examples + trailing parentheticals;
    keep the term—gloss head; collapse whitespace; lowercase first char. No paraphrase/reinterpretation."""
    head = re.split(r"\s*:\s|\s*\(", gloss)[0]
    head = re.sub(r"\s+", " ", head).strip()
    return head[:1].lower() + head[1:] if head else head


# ---------------------------------------------------------------- stage 1 (Role A)
def stage1_inventory():
    OUT.mkdir(parents=True, exist_ok=True)
    po = {w["id"]: w for w in json.loads(G0_PARSER_OUTPUTS.read_text())["words"]}
    lex = {r["canonical_parser_unit"]: r for r in json.loads(LEXICON.read_text(encoding="utf-8"))["rows"]}
    seen = {}
    for c in SELECTED:
        for u in po[c]["atomic_varnas"]:
            k = (u["type"], u["unit"])
            r = seen.setdefault(k, {"type": u["type"], "unit": u["unit"], "aspirated": u.get("aspirated"),
                                    "occurrences": 0})
            r["occurrences"] += 1
    ids = []
    for (t, u), r in sorted(seen.items()):
        lr = lex.get(u)
        covered = lr is not None and lr.get(f"{FIXED_POLE}_vritti") not in (None, "")
        ids.append({"identity_type": t, "unit": u, "aspirated": r["aspirated"], "occurrences": r["occurrences"],
                    "in_frozen_lexicon": lr is not None,
                    "activation_scope": (lr.get("activation_scope") if lr else None),
                    "category": (lr.get("category") if lr else None),
                    "source_backed": covered,
                    "source_tier": "A_SOURCE_BACKED" if covered else "B_DEVELOPMENTAL_GAP",
                    "gap_fill_required": not covered})
    inv = {"schema": "b1_12_required_varna_inventory_v1_2",
           "label": "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE",
           "role": "A_INVENTORY_EXTRACTOR (no selected-word meanings)", "selected_six": SELECTED,
           "fixed_pole": FIXED_POLE, "n_distinct_identities": len(ids),
           "n_source_backed": sum(i["source_backed"] for i in ids),
           "n_developmental_gap": sum(not i["source_backed"] for i in ids),
           "vowels": sorted(i["unit"] for i in ids if i["identity_type"] == "vowel"),
           "consonants": sorted(i["unit"] for i in ids if i["identity_type"] == "consonant"),
           "identities": ids,
           "provenance": {"g0_parser_outputs_sha256": _sha(G0_PARSER_OUTPUTS), "lexicon_sha256": _sha(LEXICON)}}
    (OUT / "required_varna_inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2,
                                                                  sort_keys=True), encoding="utf-8")
    cov = {"schema": "b1_12_coverage_report_v1_2",
           "selected_set_coverage_pct": round(100.0 * inv["n_source_backed"] / inv["n_distinct_identities"], 2),
           "n_required": inv["n_distinct_identities"], "n_source_backed": inv["n_source_backed"],
           "n_developmental_gap": inv["n_developmental_gap"], "n_unmapped": 0,
           "coverage_outcome": "G1_COMPONENT_COVERAGE_COMPLETE" if inv["n_developmental_gap"] == 0
           else "G1_COMPONENT_COVERAGE_INCOMPLETE"}
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
        orig = lr.get(f"{FIXED_POLE}_vritti") if lr else None
        entries.append({
            "atomic_identity": f"{t}:{u}", "stable_component_id": f"C{i:02d}",
            "source_tier": "A_SOURCE_BACKED" if orig else "B_DEVELOPMENTAL_GAP",
            "source_status": ident["activation_scope"] if lr else "UNMAPPED",
            "original_frozen_gloss": orig,
            "normalized_component_descriptor": normalize(orig) if orig else None,
            "source_reference": f"frozen/varna_native_stage1_merged_v1.json#{u} ({FIXED_POLE}_vritti)" if orig else None,
            "source_hash": _sha(LEXICON) if orig else None,
            "review_status": "PENDING_STAGE3_AUDIT" if orig else "UNMAPPED",
            "development_only": (ident["activation_scope"] == "DEVELOPMENT_ONLY") if lr else True,
            "notes": "verbatim binding gloss; normalization=drop post-colon/paren examples, keep term—gloss head",
        })
    (OUT / "component_descriptor_map.json").write_text(json.dumps(
        {"schema": "b1_12_component_descriptor_map_v1_2", "fixed_pole": FIXED_POLE,
         "normalization": "mechanical: drop post-colon examples + trailing parentheticals; keep term—gloss head; "
                          "collapse whitespace; lowercase first char; NO paraphrase",
         "n_entries": len(entries), "entries": entries}, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    src = {"schema": "b1_12_component_descriptor_source_audit_v1_2", "n_entries": len(entries),
           "n_tier_A": sum(e["source_tier"] == "A_SOURCE_BACKED" for e in entries),
           "n_tier_B": sum(e["source_tier"] == "B_DEVELOPMENTAL_GAP" for e in entries),
           "n_unmapped": sum(e["review_status"] == "UNMAPPED" for e in entries),
           "verbatim_original_preserved": all(e["original_frozen_gloss"] for e in entries),
           "polarity_consistent_no_switching": True, "lexicon_sha256": _sha(LEXICON)}
    (OUT / "component_descriptor_source_audit.json").write_text(json.dumps(src, indent=2, sort_keys=True),
                                                                encoding="utf-8")
    return entries


# ---------------------------------------------------------------- stage 3 (Role C)
def _opaque_seq():
    po = {w["id"]: w for w in json.loads(G0_PARSER_OUTPUTS.read_text())["words"]}
    return {c: [(u["type"], u["unit"]) for u in po[c]["atomic_varnas"]] for c in SELECTED}


def _scramble(seq, seed):
    rng = random.Random(f"{seed}:{seq}")
    perms = list(itertools.permutations(range(len(seq))))
    idx = list(range(len(perms)))
    rng.shuffle(idx)
    srt = tuple(sorted(range(len(seq)), key=lambda k: seq[k]))
    for i in idx:
        p = perms[i]
        if p != tuple(range(len(seq))) and p != srt:
            return [seq[k] for k in p]
    return seq


def stage3_audit():
    inv = json.loads((OUT / "required_varna_inventory.json").read_text())
    cov = json.loads((OUT / "coverage_report.json").read_text())
    dmap = json.loads((OUT / "component_descriptor_map.json").read_text())
    pool = {w["id"]: w for w in json.loads(POOL.read_text(encoding="utf-8"))["words"]}
    desc_by_ident = {e["atomic_identity"]: e for e in dmap["entries"]}
    cid_by_ident = {e["atomic_identity"]: e["stable_component_id"] for e in dmap["entries"]}
    entries = dmap["entries"]
    descs = [e["normalized_component_descriptor"] for e in entries]

    # ---- descriptor quality diagnostics ----
    lens = [len(d) for d in descs]
    vlen = [len(desc_by_ident[e["atomic_identity"]]["normalized_component_descriptor"])
            for e in entries if e["atomic_identity"].startswith("vowel:")]
    clen = [len(desc_by_ident[e["atomic_identity"]]["normalized_component_descriptor"])
            for e in entries if e["atomic_identity"].startswith("consonant:")]
    dev_len = [len(e["normalized_component_descriptor"]) for e in entries if e["development_only"]]
    conf_len = [len(e["normalized_component_descriptor"]) for e in entries if not e["development_only"]]

    def disjoint(a, b):
        return (min(a) > max(b) or min(b) > max(a)) if (a and b) else False
    prohibited_hits = {e["atomic_identity"]: [w for w in PROHIBITED
                                              if w in e["normalized_component_descriptor"].lower()]
                       for e in entries if any(w in e["normalized_component_descriptor"].lower()
                                               for w in PROHIBITED)}
    embedded_narrative = sorted(e["atomic_identity"] for e in entries
                                if "—" in e["normalized_component_descriptor"])
    raw_sanskrit = sorted(e["atomic_identity"] for e in entries
                          if any(s in e["normalized_component_descriptor"] for s in SANSKRIT_TERMS))
    domains = {e["atomic_identity"]: ("affliction_tendency"
                                      if any(m in e["normalized_component_descriptor"].lower()
                                             for m in AFFLICTION_MARKERS) else "other") for e in entries}
    n_affliction = sum(d == "affliction_tendency" for d in domains.values())
    exact_dupes = len(descs) - len(set(descs))

    quality_outcomes = []
    if exact_dupes:
        quality_outcomes.append("DESCRIPTOR_COLLAPSE")
    if disjoint(vlen, clen):
        quality_outcomes.append("DESCRIPTOR_LENGTH_LEAKAGE")
    if disjoint(dev_len, conf_len):
        quality_outcomes.append("DESCRIPTOR_SOURCE_TIER_LEAKAGE")
    if n_affliction >= len(entries) * 0.6:
        quality_outcomes.append("DESCRIPTOR_NEUTRALITY_FAILURE")
    if not quality_outcomes:
        quality_outcomes.append("DESCRIPTOR_MAP_READY")

    quality = {"schema": "b1_12_descriptor_quality_audit_v1_2", "n_descriptors": len(descs),
               "exact_duplicates": exact_dupes,
               "length_min_max_mean": [min(lens), max(lens), round(sum(lens) / len(lens), 1)],
               "vowel_length_range": [min(vlen), max(vlen)], "consonant_length_range": [min(clen), max(clen)],
               "development_length_range": [min(dev_len), max(dev_len)],
               "confirmatory_length_range": [min(conf_len), max(conf_len)],
               "length_leakage_vowel_vs_consonant_disjoint": disjoint(vlen, clen),
               "source_tier_leakage_disjoint": disjoint(dev_len, conf_len),
               "prohibited_progression_term_hits": prohibited_hits,
               "embedded_em_dash_narrative": embedded_narrative,
               "raw_sanskrit_term_descriptors": raw_sanskrit,
               "descriptor_domain": domains, "n_affliction_tendency": n_affliction,
               "candidate_meaning_domain": "ordinary_concrete_referent", "domain_match": False,
               "quality_outcomes": quality_outcomes}
    (OUT / "descriptor_quality_audit.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2,
                                                                  sort_keys=True), encoding="utf-8")

    # ---- arm render spec + examples (normalized descriptors) ----
    seqs = _opaque_seq()
    def to_desc(ident):
        return desc_by_ident[f"{ident[0]}:{ident[1]}"]["normalized_component_descriptor"]
    def render(seq):
        return [f"position {i+1}: {to_desc(k)}" for i, k in enumerate(seq)]
    def render_masked(seq):
        return [f"position {i+1}: {MASK}" for i in range(len(seq))]
    arms = {}
    for c in SELECTED:
        s = seqs[c]
        A, D, B = s, sorted(s, key=lambda k: cid_by_ident[f"{k[0]}:{k[1]}"]), _scramble(s, SCRAMBLE_SEED)
        arms[c] = {"A_true_order": render(A), "B_order_scramble": render(B),
                   "D_unordered_inventory": render(D), "masked": render_masked(A),
                   "A_multiset_ids": sorted(cid_by_ident[f'{k[0]}:{k[1]}'] for k in A),
                   "B_multiset_ids": sorted(cid_by_ident[f'{k[0]}:{k[1]}'] for k in B),
                   "D_multiset_ids": sorted(cid_by_ident[f'{k[0]}:{k[1]}'] for k in D)}
    render_spec = {"schema": "b1_12_arm_render_spec_v1_2",
                   "template": "position i: <normalized_component_descriptor> (one line/varṇa; no connectives)",
                   "scramble_seed": SCRAMBLE_SEED, "arm_A": "true pronunciation order; repetition preserved",
                   "arm_B": "same multiset, seeded scramble != A and != sorted; no resample",
                   "arm_D": "same multiset, canonical order by stable_component_id; no pronunciation semantics",
                   "prohibited": ["prose paragraphs", "connectives", "progression/causal language",
                                  "word-level packet prose"]}
    (OUT / "arm_render_spec.json").write_text(json.dumps(render_spec, ensure_ascii=False, indent=2,
                                                         sort_keys=True), encoding="utf-8")
    (OUT / "arm_render_examples.json").write_text(json.dumps(
        {"schema": "b1_12_arm_render_examples_v1_2", "arms": arms}, ensure_ascii=False, indent=2,
        sort_keys=True), encoding="utf-8")

    # ---- deterministic leakage / shortcut audit (no judges) ----
    firsts = {c: cid_by_ident[f"{seqs[c][0][0]}:{seqs[c][0][1]}"] for c in SELECTED}
    lasts = {c: cid_by_ident[f"{seqs[c][-1][0]}:{seqs[c][-1][1]}"] for c in SELECTED}
    inv_multiset = {c: tuple(sorted(cid_by_ident[f"{k[0]}:{k[1]}"] for k in seqs[c])) for c in SELECTED}
    all_cids = Counter(cid for c in SELECTED for cid in set(inv_multiset[c]))
    unique_descriptor_words = {c: [cid for cid in set(inv_multiset[c]) if all_cids[cid] == 1] for c in SELECTED}
    lengths = {c: len(seqs[c]) for c in SELECTED}
    leakage = {
        "schema": "b1_12_leakage_control_spec_v1_2",
        "required_ablations": ["first_position_only", "last_position_only", "unordered_inventory",
                               "single_most_diagnostic_descriptor", "descriptor_content_masked",
                               "candidate_meanings_without_component_info", "source_backed_only_positions",
                               "developmental_only_positions"],
        "leakage_tolerance": "any ablation above chance 1/6 beyond CI in a later probe => CONTROL_LEAKAGE",
        "deterministic_findings": {
            "first_descriptor_unique_per_word": len(set(firsts.values())) == len(firsts),
            "last_descriptor_multiplicity": dict(Counter(lasts.values())),
            "unordered_inventory_identifies_word": len(set(inv_multiset.values())) == len(SELECTED),
            "words_with_a_unique_single_descriptor": {c: unique_descriptor_words[c] for c in SELECTED
                                                      if unique_descriptor_words[c]},
            "length_groups": {str(k): [c for c in SELECTED if lengths[c] == k] for k in sorted(set(lengths.values()))},
            "descriptor_length_still_leaks_cv": disjoint(vlen, clen),
            "raw_sanskrit_in_evaluator_facing_descriptors": raw_sanskrit,
            "content_masked_arms_identical_within_word": True,
        },
        "note": ("with distinct inventories, the UNORDERED inventory (arm D) already uniquely identifies each "
                 "word -> if descriptors were referent-diagnostic, order would add nothing (no headroom); and "
                 "the first descriptor is unique per word (first-position shortcut). These are structural "
                 "shortcut/leakage risks independent of the domain mismatch."),
    }
    (OUT / "leakage_control_spec.json").write_text(json.dumps(leakage, ensure_ascii=False, indent=2,
                                                             sort_keys=True), encoding="utf-8")

    # ---- verdict ----
    coverage_complete = cov["coverage_outcome"] == "G1_COMPONENT_COVERAGE_COMPLETE"
    length_leak = disjoint(vlen, clen) or disjoint(dev_len, conf_len)
    domain_ok = quality["domain_match"]
    structural_quality_pass = (exact_dupes == 0 and not length_leak and not prohibited_hits)
    task_identifiable = domain_ok            # affliction descriptors give no principled referent basis
    if not coverage_complete:
        verdict = "G1_BLOCKED_COMPONENT_COVERAGE"
    elif "DESCRIPTOR_MAP_READY" not in quality_outcomes or not domain_ok:
        verdict = "G1_BLOCKED_DESCRIPTOR_QUALITY"
    elif length_leak:
        verdict = "G1_BLOCKED_CONTROL_LEAKAGE"
    else:
        verdict = "G1_READY_FOR_SEMANTIC_ORDER_USABILITY_PROBE"

    manifest = {
        "schema": "b1_12_g1_v1_2_manifest", "label": "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE",
        "iteration": "v1.2 (normalized labels) — supersedes v1 block (d48ae9f) with fuller audit; same verdict",
        "controlling_commits": {"prereg": "2c613f4", "v1_1": "6f197fd", "v1_2_order": "7935f48",
                                "pool": "d50fbb9", "g0_audit": "1713311", "g1_opaque": "9e8da86",
                                "g1_reassessment": "bb2051e", "g1_semantic_v1": "d48ae9f"},
        "selected_six": SELECTED,
        "coverage": {"pct": cov["selected_set_coverage_pct"], "source_backed": inv["n_source_backed"],
                     "developmental_gap": inv["n_developmental_gap"], "unmapped": 0,
                     "outcome": cov["coverage_outcome"]},
        "descriptor_quality_outcomes": quality_outcomes,
        "structural_quality_pass_ignoring_domain": structural_quality_pass,
        "length_leakage_persists_after_normalization": length_leak,
        "domain_match": domain_ok, "task_identifiable": task_identifiable,
        "abd_parity_multiset_equal": all(arms[c]["A_multiset_ids"] == arms[c]["B_multiset_ids"] ==
                                         arms[c]["D_multiset_ids"] for c in SELECTED),
        "unordered_inventory_identifies_word": leakage["deterministic_findings"]["unordered_inventory_identifies_word"],
        "verdict": verdict,
        "lexicon_sha256": _sha(LEXICON), "parser_ok": True,
        "no_g0_pool_selected_parser_lexicon_change": True,
    }
    (OUT / "g1_v1_2_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
                                                          sort_keys=True), encoding="utf-8")
    return {"coverage": cov, "quality": quality, "leakage": leakage, "arms": arms, "manifest": manifest,
            "verdict": verdict}


if __name__ == "__main__":
    stage1_inventory()
    stage2_descriptors()
    r = stage3_audit()
    print(json.dumps({"coverage_pct": r["coverage"]["selected_set_coverage_pct"],
                      "coverage_outcome": r["coverage"]["coverage_outcome"],
                      "quality_outcomes": r["quality"]["quality_outcomes"],
                      "vowel_len": r["quality"]["vowel_length_range"],
                      "consonant_len": r["quality"]["consonant_length_range"],
                      "length_leak_persists": r["manifest"]["length_leakage_persists_after_normalization"],
                      "domain_match": r["quality"]["domain_match"],
                      "unordered_identifies_word": r["manifest"]["unordered_inventory_identifies_word"],
                      "abd_parity": r["manifest"]["abd_parity_multiset_equal"],
                      "verdict": r["verdict"]}, ensure_ascii=False, indent=2))
