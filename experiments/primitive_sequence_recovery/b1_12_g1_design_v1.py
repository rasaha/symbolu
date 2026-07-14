#!/usr/bin/env python3
"""B1.12 — Gate G1 evaluator-facing representation & leakage feasibility (design v1). Deterministic; NO judges.

Uses the frozen G0-selected six (audit commit 1713311) and the frozen opaque-ID map rebuilt exactly as the G0
auditor did. Produces: the selected-set structural audit; a comparison of encoding Options A–E; a proposed
primary encoding + task model; deterministic arm renders (A true-order / B order-scramble / D unordered
inventory); a leakage audit with runnable tests; and a G1 verdict.

Central finding driving the design: the six selected words have DISTINCT inventories, so CROSS-WORD
identification is inventory-separable (tests inventory, not order). Therefore the primary G1 contrast is
WITHIN-WORD (A vs B vs D of the same word), where inventory and length are identical by construction and only
ORDER varies. Leakage-safe opaque IDs support a structural order-discrimination task (Model 3), not direct
semantic word recovery — hence the expected verdict G1_PASS_WITH_LIMITED_CLAIM.

DIAGNOSTIC_ONLY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE. No G0/pool/threshold/parser/map change.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import pathlib
import random
import re

import b1_12_g0_audit_v1 as G0
import sanskrit_stage1_parser as P

HERE = pathlib.Path(__file__).resolve().parent
POOL = HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json"
OUT = HERE / "results" / "b1_12_g1_design_v1"

SELECTED = ["W03", "W15", "W20", "W23", "W30", "W35"]
G1_SCRAMBLE_SEED = 20260101          # FROZEN feasibility seed (NOT the confirmatory Arm-B seed; that is later)
MASK = "•"                       # bullet for content-masked renders

# ---- IAST / Devanāgarī character classes used to prove no linguistic leakage in evaluator-facing text ----
IAST_CHARS = set("aāiīuūṛṝḷḹeaioaukgṅcjñṭḍṇtdnpbmyrlvśṣshḥṃ")  # lowercase IAST letters + diacritics
DEVANAGARI = lambda s: any("ऀ" <= ch <= "ॿ" for ch in s)


def load_opaque():
    """Rebuild the exact frozen opaque-ID map + selected-word opaque sequences (as the G0 auditor did)."""
    pool = {w["id"]: w for w in json.loads(POOL.read_text(encoding="utf-8"))["words"]}
    parsed = {cid: [(u["type"], u["unit"]) for u in P.parse(pool[cid]["devanagari"])["atomic_varnas"]]
              for cid in pool}
    distinct = sorted({i for s in parsed.values() for i in s})
    op = {i: f"U{k + 1:02d}" for k, i in enumerate(distinct)}
    seq = {cid: [op[i] for i in parsed[cid]] for cid in SELECTED}
    return pool, seq


def canonical_sorted(x):
    return sorted(x)                  # ascending opaque-id = Arm-D unordered canonical representative


def scramble(x, seed):
    """Deterministic order-scramble: same multiset, != x and != sorted(x) when the multiset permits."""
    rng = random.Random(f"{seed}:{'.'.join(x)}")
    variants = list(itertools.permutations(x))
    # deterministic candidate order: shuffle the index list, pick first perm that is a genuine scramble
    idx = list(range(len(variants)))
    rng.shuffle(idx)
    srt = tuple(sorted(x))
    xt = tuple(x)
    for i in idx:
        p = variants[i]
        if p != xt and p != srt:
            return list(p)
    return list(x)                    # degenerate (e.g. all identical tokens) — impossible for the six


# ---------------------------------------------------------------- renderers (position-tagged opaque; Option A/D)
def render_positional(tokens):
    return " ".join(f"p{i + 1}:{t}" for i, t in enumerate(tokens))


def render_masked(tokens):
    return " ".join(f"p{i + 1}:{MASK}" for i in range(len(tokens)))


def render_bigram(tokens):            # Option E
    return " ".join(f"{tokens[i]}>{tokens[i + 1]}" for i in range(len(tokens) - 1))


# ---------------------------------------------------------------- build
def build():
    OUT.mkdir(parents=True, exist_ok=True)
    pool, seq = load_opaque()

    # ---------- Step 1: selected-set structural audit ----------
    audit_words = {}
    for cid in SELECTED:
        x = seq[cid]
        audit_words[cid] = {
            "iast": pool[cid]["iast"], "gloss": pool[cid]["gloss"], "length": len(x),
            "ordered_opaque_sequence": x, "unordered_inventory": sorted(set(x)),
            "repeated_units": {u: x.count(u) for u in sorted(set(x)) if x.count(u) > 1},
            "first_unit": x[0], "last_unit": x[-1],
            "s_selforder": round(G0.s_selforder(x), 6),
            "bigrams": sorted("".join(b) for b in G0.bigrams(x)),
            "trigrams": sorted("".join(t) for t in G0.trigrams(x)),
        }
    pairs = {}
    any_same_multiset = False
    n_inventory_dominated = 0
    for a, b in itertools.combinations(SELECTED, 2):
        xa, xb = seq[a], seq[b]
        same_ms = sorted(xa) == sorted(xb)
        doi = G0.d_ord_given_inv(xa, xb)
        de = G0.d_edit(xa, xb)
        # "differs mainly by inventory" := multiset differs AND no order-specific component
        inv_dom = (not same_ms) and doi == 0.0
        any_same_multiset = any_same_multiset or same_ms
        n_inventory_dominated += int(inv_dom)
        pairs[f"{a}|{b}"] = {"d_edit": round(de, 6), "d_ord_given_inv": round(doi, 6),
                             "multiset_jaccard": round(G0.multiset_jaccard(xa, xb), 6),
                             "same_multiset_diff_order": same_ms, "inventory_dominated": inv_dom}
    n_pos_order = sum(1 for p in pairs.values() if p["d_ord_given_inv"] > 0)
    # classification (diagnostic; does NOT override G0)
    if any_same_multiset:
        classification = "MIXED_ORDER_AND_INVENTORY"
    elif n_pos_order == 0:
        classification = "INVENTORY_DOMINATED"
    elif n_pos_order >= len(pairs) * 0.6:
        classification = "ORDER_RICH"
    else:
        classification = "INVENTORY_DOMINATED" if n_inventory_dominated > n_pos_order else "MIXED_ORDER_AND_INVENTORY"
    structural_audit = {
        "schema": "b1_12_g1_selected_set_structural_audit_v1",
        "selected_six": SELECTED, "words": audit_words, "pairs": pairs,
        "n_pairs": len(pairs), "n_pairs_positive_order": n_pos_order,
        "n_pairs_zero_order": len(pairs) - n_pos_order,
        "n_pairs_inventory_dominated": n_inventory_dominated,
        "any_pair_same_multiset_diff_order": any_same_multiset,
        "all_distinct_inventories": not any_same_multiset,
        "classification": classification,
        "classification_note": ("all six words have distinct inventories and no repeated units; cross-word "
                                "discrimination is inventory-separable, so a CROSS-WORD identification task "
                                "would test inventory recognition, not order. Order must be tested WITHIN-word."),
    }
    (OUT / "selected_set_structural_audit.json").write_text(
        json.dumps(structural_audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # ---------- Step 2/7: arm renders under the proposed primary encoding (Option A/D, position-tagged) ----------
    arms = {}
    for cid in SELECTED:
        x = seq[cid]
        A_seq, D_seq, B_seq = x, canonical_sorted(x), scramble(x, G1_SCRAMBLE_SEED)
        arms[cid] = {
            "iast": pool[cid]["iast"],
            "A_true_order": {"tokens": A_seq, "render": render_positional(A_seq),
                             "masked": render_masked(A_seq)},
            "B_order_scramble": {"tokens": B_seq, "render": render_positional(B_seq),
                                 "masked": render_masked(B_seq)},
            "D_unordered_inventory": {"tokens": D_seq, "render": render_positional(D_seq),
                                      "masked": render_masked(D_seq)},
        }
    (OUT / "arm_render_examples.json").write_text(
        json.dumps({"schema": "b1_12_g1_arm_renders_v1",
                    "encoding": "position-tagged opaque IDs (Option A content + Option D formatting)",
                    "scramble_seed_feasibility_only": G1_SCRAMBLE_SEED,
                    "note": "confirmatory Arm-B seed is NOT frozen here; this seed is a feasibility instantiation",
                    "arms": arms}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # ---------- Step 4: order-vs-inventory identifiability (structural feasibility) ----------
    feas = {}
    for cid in SELECTED:
        x = seq[cid]
        A_seq, D_seq, B_seq = x, canonical_sorted(x), scramble(x, G1_SCRAMBLE_SEED)
        feas[cid] = {
            "A_B_same_multiset": sorted(A_seq) == sorted(B_seq),
            "A_B_same_length": len(A_seq) == len(B_seq),
            "A_B_diff_order": A_seq != B_seq,
            "A_D_same_units": sorted(A_seq) == sorted(D_seq),
            "D_is_canonical_sorted": D_seq == sorted(D_seq),
            "B_not_equal_sorted": B_seq != sorted(B_seq),          # scramble is a genuine non-canonical order
            "A_not_equal_D": A_seq != D_seq,                       # true order != unordered representative
            "masked_A_eq_B": render_masked(A_seq) == render_masked(B_seq),
            "masked_A_eq_D": render_masked(A_seq) == render_masked(D_seq),
        }
    feas_all_ok = all(all(v.values()) for v in feas.values())

    # ---------- Step 5: leakage audit ----------
    def has_iast(text):
        return bool(set(text.lower()) & IAST_CHARS - set("pu")) or DEVANAGARI(text)
    # note: 'p' and 'U' appear in position tags / ids; we check for IAST *letters other than* the tag chars,
    #       and any Devanāgarī — the robust check below tokenizes and inspects only the id payloads.
    def payload_tokens(render):
        return re.findall(r"U\d\d", render)
    leak_checks = {}
    # 1. no IAST/Devanāgarī anywhere in any evaluator-facing render (ids are U\d\d, tags p\d, sep ':'/space/'>')
    all_renders = []
    for cid in SELECTED:
        for arm in ("A_true_order", "B_order_scramble", "D_unordered_inventory"):
            all_renders.append(arms[cid][arm]["render"])
            all_renders.append(arms[cid][arm]["masked"])
        all_renders.append(render_bigram(seq[cid]))
    allowed = re.compile(r"^[pU0-9:>• ]+$")
    leak_checks["no_iast_or_devanagari_chars"] = all(allowed.match(r) for r in all_renders) and \
        not any(DEVANAGARI(r) for r in all_renders)
    # 2. content-masked arms are identical within each word (A==B==D masked) -> no template/length artifact
    leak_checks["masked_arms_identical_within_word"] = all(
        arms[c]["A_true_order"]["masked"] == arms[c]["B_order_scramble"]["masked"] ==
        arms[c]["D_unordered_inventory"]["masked"] for c in SELECTED)
    # 3. length within a trial is constant across arms (A/B/D same length) -> no within-trial length leak
    leak_checks["within_word_length_constant"] = all(
        len(arms[c]["A_true_order"]["tokens"]) == len(arms[c]["B_order_scramble"]["tokens"]) ==
        len(arms[c]["D_unordered_inventory"]["tokens"]) for c in SELECTED)
    # 4. CONTENT-MASKED classification: can arm be identified with content removed? (must be NO)
    #    over all words, the set of masked renders collapses by length only -> arms indistinguishable when masked
    masked_by_word = {c: arms[c]["A_true_order"]["masked"] for c in SELECTED}
    leak_checks["content_masked_arm_unclassifiable"] = leak_checks["masked_arms_identical_within_word"]
    #    content-masked word identification: masked render depends only on length; words of equal length share it
    lengths = {c: len(seq[c]) for c in SELECTED}
    len_groups = {}
    for c in SELECTED:
        len_groups.setdefault(lengths[c], []).append(c)
    leak_checks["content_masked_word_ambiguous"] = all(len(g) > 1 for g in len_groups.values())
    #    (len4: asthi,keśa,nadī ; len5: grīvā,jñāna,sūrya -> each length shared by 3, so masked -> 1/3 ambiguity)
    # 5. raw-word / transliteration substring leakage: no IAST of any selected word appears in any render
    iast_forms = [pool[c]["iast"] for c in SELECTED]
    leak_checks["no_word_transliteration_substring"] = not any(
        any(w.lower() in r.lower() for w in iast_forms) for r in all_renders)
    # 6. first/last-unit CROSS-WORD uniqueness (informational: why cross-word task leaks, motivating within-word)
    firsts = [seq[c][0] for c in SELECTED]
    lasts = [seq[c][-1] for c in SELECTED]
    cross_word_first_unique = len(set(firsts)) == len(firsts)
    leak_audit = {
        "schema": "b1_12_g1_leakage_audit_v1",
        "encoding_audited": "position-tagged opaque IDs (primary)",
        "checks": leak_checks,
        "all_leakage_checks_pass": all(leak_checks.values()),
        "cross_word_first_unit_unique": cross_word_first_unique,
        "cross_word_last_unit_multiplicity": {u: lasts.count(u) for u in sorted(set(lasts))},
        "cross_word_length_groups": {str(k): v for k, v in sorted(len_groups.items())},
        "cross_word_leakage_note": ("first opaque unit is UNIQUE per selected word -> a cross-word candidate task "
                                    "would leak the answer via the first unit; this is a further reason the "
                                    "primary task is WITHIN-word, where no cross-word choice is presented."),
        "control_leakage": (not all(leak_checks.values())),
    }
    (OUT / "leakage_audit.json").write_text(
        json.dumps(leak_audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # ---------- proposed primary encoding ----------
    primary = {
        "schema": "b1_12_g1_proposed_primary_encoding_v1",
        "encoding_id": "OPT_A_D_POSITIONAL_OPAQUE",
        "description": "position-tagged opaque ordered varṇa IDs, e.g. 'p1:U25 p2:U17 p3:U19 p4:U27'",
        "task_model": "MODEL_3_SAME_WORD_ORDER_DISCRIMINATION",
        "primary_contrast": "WITHIN-word A (true order) vs B (order-scramble); A vs D (unordered) secondary",
        "evaluator_receives": ["position-tagged opaque ID sequences for arms of a single hidden word",
                               "identical template/length across arms"],
        "evaluator_does_not_receive": ["the Sanskrit word", "IAST/Devanāgarī", "any semantic gloss",
                                       "the opaque-ID legend/meaning", "cross-word candidate list"],
        "target_answer": ("a structural order judgment (e.g. which arm is the reference's true order / whether "
                          "two renders share the same order) — NOT a word or meaning"),
        "why_true_order_could_help": ("A differs from B and D only in the ORDER of an identical multiset; any "
                                      "above-chance discrimination must use order, since inventory+length are held constant"),
        "why_inventory_alone_insufficient": ("within a trial all arms share the exact multiset and length, so "
                                             "inventory/length carry zero discriminative information"),
        "controls_matched": ("A/B/D identical token multiset, length, template, and position tags; content-masked "
                             "renders are byte-identical across arms"),
        "positive_result_supports": ("that ordered opaque varṇa composition is a recoverable, distinguishable "
                                     "STRUCTURAL signal — order is preserved and usable, not collapsed"),
        "positive_result_does_NOT_support": ["order carries semantic/word-specific meaning",
                                             "varṇa mappings are true", "Sanskrit words encode referents",
                                             "H2 (semantic) is supported", "B1.10 is rescued"],
        "rejected_alternatives": {
            "cross_word_candidate_match (Model 2)": "leaks via unique first unit + distinct inventories -> tests inventory",
            "semantic_glosses (Option C / Model 4)": "reintroduces B1.10 prose-packet confound; secondary only",
            "learned_key (Model 1)": "needs a training phase not yet designed; deferred",
        },
    }
    (OUT / "proposed_primary_encoding.json").write_text(
        json.dumps(primary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # ---------- verdict ----------
    # structural+leakage feasibility established; real-model evaluator USABILITY unresolved (no judge available)
    order_isolable = feas_all_ok
    leakage_safe = leak_audit["all_leakage_checks_pass"]
    if not leakage_safe:
        verdict = "G1_LEAKAGE_FAILURE"
    elif not order_isolable:
        verdict = "G1_INVENTORY_DOMINATED"
    else:
        # opaque encoding supports structural order-discrimination but NOT direct semantic recovery
        verdict = "G1_PASS_WITH_LIMITED_CLAIM"
    narrowed_claim = ("The B1.12 instrument can support a WITHIN-word ORDER-DISCRIMINATION task on leakage-safe "
                      "opaque varṇa compositions: it can test whether the true ordered composition is "
                      "distinguishable from its own order-scrambled and unordered-inventory versions. It CANNOT, "
                      "with this leakage-safe opaque encoding, support direct SEMANTIC word recovery — that would "
                      "require a keyed/training phase (Model 1) or semantic glosses (Model 4, which reintroduces "
                      "B1.10 prose confounds). Evaluator real-model usability is UNRESOLVED pending an available "
                      "judge panel; the verdict rests on deterministic structural + leakage feasibility.")

    manifest = {
        "schema": "b1_12_g1_manifest_v1",
        "label": "DIAGNOSTIC_ONLY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE",
        "controlling_commits": {"prereg": "2c613f4", "v1_1": "6f197fd", "v1_2": "7935f48",
                                "g0_audit": "1713311", "pool_curator": "d50fbb9"},
        "g0_verdict": "G0_PASS", "selected_six": SELECTED,
        "selected_set_classification": classification,
        "opaque_map_sha256_from_g0": None,  # filled below
        "scramble_seed_feasibility_only": G1_SCRAMBLE_SEED,
        "structural_feasibility_all_ok": order_isolable,
        "leakage_all_checks_pass": leakage_safe,
        "primary_encoding": primary["encoding_id"],
        "primary_task_model": primary["task_model"],
        "verdict": verdict,
        "narrowed_claim": narrowed_claim,
        "evaluator_real_model_usability": "UNRESOLVED_NO_JUDGE_AVAILABLE",
        "unresolved_dependencies": [
            "real-model (or human) evaluator usability of opaque order-discrimination",
            "confirmatory Arm-B scramble seed freeze",
            "final control/context design (post-G1)",
            "whether a keyed/semantic secondary arm is ever introduced (risks B1.10 confound)"],
        "no_g0_pool_threshold_parser_map_change": True,
    }
    # pin the opaque map hash from the G0 audit artifact for provenance
    g0map = HERE / "results" / "b1_12_g0_audit_v1" / "opaque_varna_id_map.json"
    if g0map.exists():
        manifest["opaque_map_sha256_from_g0"] = hashlib.sha256(g0map.read_bytes()).hexdigest()
    (OUT / "g1_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                                          encoding="utf-8")
    return {"classification": classification, "verdict": verdict, "feas_all_ok": order_isolable,
            "leakage_safe": leakage_safe, "leak_checks": leak_checks, "manifest": manifest,
            "structural_audit": structural_audit, "arms": arms}


if __name__ == "__main__":
    r = build()
    print(json.dumps({"classification": r["classification"], "verdict": r["verdict"],
                      "structural_feasibility_all_ok": r["feas_all_ok"], "leakage_safe": r["leakage_safe"],
                      "leak_checks": r["leak_checks"],
                      "example_arms_W20_jnana": {k: r["arms"]["W20"][k]["render"]
                                                 for k in ("A_true_order", "B_order_scramble",
                                                           "D_unordered_inventory")}},
                     ensure_ascii=False, indent=2))
