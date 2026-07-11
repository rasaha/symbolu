"""Deterministic mock tests for the B1.10 CONTROL EXTENSION harness. NO real model, NO network.

Proves: exactly 72 cells; source hashes pinned; original B1.10 artifacts unchanged; no target/pole/varṇa/system
leakage; Tier-1 = valence only; Tier-2 = generic source-condition only; Tier-3 preserves the intended v3 facet
content in plain English (hidden provenance) with no Sanskrit; length/register parity; overlap limits;
deterministic shuffle; aggregation matches hand-calculated examples; missing-data rules; tier-identifiability
diagnostic near chance; no real model calls.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import hashlib
import json
import pathlib
import re

import build_b1_10_control_ext as BLD
import build_b1_9_pole_did_scaffold as B0
import run_b1_10_control_ext as R

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- 72 cells
def test_exactly_72_cells():
    cells = R.build_cells(R.load_items())
    assert len(cells) == 72
    combos = {(c["word"], c["context_pole"], c["tier"], c["packet_pole"]) for c in cells}
    assert len(combos) == 72                      # 6 words x 2 ctx x 3 tiers x 2 poles, each once
    for w in R.TARGET_WORDS:
        for ctx in R.POLES:
            for t in R.TIERS:
                for p in R.POLES:
                    assert (w, ctx, t, p) in combos
    assert [c["cell_id"] for c in cells] == [f"E{i:02d}" for i in range(1, 73)]


def test_run_produces_72():
    part = R.run(mock=True)
    assert part["n_cells"] == 72 and part["n_rated"] == 72 and part["n_failures"] == 0


# ---------------------------------------------------------------- source hashes pinned
def test_source_hashes_pinned():
    items = R.load_items()
    assert items["source_hashes"]["varna_polarity_table_v3.json"] == _sha(FROZEN / "varna_polarity_table_v3.json")
    assert items["source_hashes"]["stage_a_prime_coverage.py"] == _sha(HERE / "stage_a_prime_coverage.py")


# ---------------------------------------------------------------- original B1.10 artifacts unchanged
def test_original_b1_10_artifacts_unchanged():
    assert _sha(FROZEN / "b1_10_pole_context_microtest_items.json") == \
        "9d70bb863f49ba06b84dd2eb5463b04d95755fe0b7b371c1d2ebcd3b1832b3bd"
    assert _sha(FROZEN / "b1_10_EVIDENCE_FREEZE_DECLARED.json") == \
        "e34b21735785ac0dd8a4444fbfcbfa0857082f92f2d429b5b09e1db8aadf6b1a"


# ---------------------------------------------------------------- no leakage in judge prompts
def test_no_leakage_in_prompts():
    for c in R.build_cells(R.load_items()):
        pkg = R.make_judge_visible(c)             # raises on any leak
        assert set(pkg.keys()) == {"cell_id", "prompt"}
        # every packet facet is ascii, no pole/varṇa/system token, no target word
        for f in c["packet_facets"]:
            assert R.packet_leaks(f) == [], f"{c['cell_id']}: {f!r}"
            assert f.isascii()
        # no bracket tag anywhere
        assert "[" not in pkg["prompt"]


def test_blinding_raises_on_injected_target_word():
    c = dict(R.build_cells(R.load_items())[0])
    c = {**c, "packet_facets": c["packet_facets"] + ["this clearly names pride outright"]}
    try:
        R.make_judge_visible(c)
        assert False, "expected INVALID_BLINDING"
    except ValueError as e:
        assert "INVALID_BLINDING" in str(e)


# ---------------------------------------------------------------- Tier-1 valence only
def test_tier1_valence_only():
    # Tier-1 facets must NOT contain source-condition vocabulary (others/approval/compare/self/etc.)
    banned = re.compile(r"\b(other|others|outside|approval|compare|comparing|itself|self|needing|depends|"
                        r"result|loosely|let|lets|grip|grips|clutch)\b", re.I)
    items = R.load_items()
    for wd in items["words"]:
        for pole in R.POLES:
            for f in wd["packets"]["valence"][pole]:
                assert not banned.search(f["text"]), f"Tier-1 leaked source-condition: {f['text']!r}"
    # and Tier-1 pools are exactly the fixed pools (first-N)
    assert items["tier1_fixed"]["negative_pool"] == BLD.TIER1_NEG
    assert items["tier1_fixed"]["positive_pool"] == BLD.TIER1_POS


# ---------------------------------------------------------------- Tier-2 generic source-condition only
def test_tier2_generic_source_condition_only():
    # Tier-2 must be generic (no specific affect vocabulary from Tier-3), and must be the fixed pools
    items = R.load_items()
    assert items["tier2_fixed"]["other_conditioned_pool"] == BLD.TIER2_OTHER
    assert items["tier2_fixed"]["self_grounded_pool"] == BLD.TIER2_SELF
    affect = re.compile(r"\b(contempt|contemptuous|torpor|cruel|cruelty|indulg|fixation|striving|goodwill|"
                        r"compassion|forbearance|wakefulness)\b", re.I)
    for wd in items["words"]:
        for pole in R.POLES:
            for f in wd["packets"]["source_condition"][pole]:
                assert not affect.search(f["text"]), f"Tier-2 leaked specific affect: {f['text']!r}"


# ---------------------------------------------------------------- Tier-3 preserves v3 content + hidden provenance
def test_tier3_preserves_v3_provenance_plain_english():
    items = R.load_items()
    table = json.loads((FROZEN / "varna_polarity_table_v3.json").read_text())["varnas"]
    import varna_bridge_active as AB
    for wd in items["words"]:
        seq = AB.word_to_varnas(wd["word"])
        # dedup preserving order
        seen, uniq = set(), []
        for v in seq:
            if v not in seen:
                seen.add(v); uniq.append(v)
        for pole_key, pole_field in (("binding", B0.BINDING), ("liberating", B0.LIBERATING)):
            facets = wd["packets"]["specific"][pole_key]
            assert [f["provenance_varna"] for f in facets] == uniq          # one clause per v3 varṇa, in order
            for f in facets:
                assert f["provenance_v3_facet"] == table[f["provenance_varna"]][pole_field]  # exact v3 provenance
                assert f["text"].isascii()                                  # plain English, no Sanskrit diacritics
                assert R.packet_leaks(f["text"]) == []


# ---------------------------------------------------------------- length / register parity
def test_register_parity():
    items = R.load_items()
    per_tier_wc = {t: [] for t in R.TIERS}
    for wd in items["words"]:
        n = wd["facet_count"]
        for t in R.TIERS:
            for pole in R.POLES:
                facets = wd["packets"][t][pole]
                assert len(facets) == n           # facet count matches v3 N for every tier
                for f in facets:
                    wc = len(f["text"].split())
                    per_tier_wc[t].append(wc)
                    assert 8 <= wc <= 14           # clause length band
                    assert "," not in f["text"]    # no commas in any tier (register match)
    means = {t: sum(v) / len(v) for t, v in per_tier_wc.items()}
    assert max(means.values()) - min(means.values()) <= 2.0    # mean word-count within 2 across tiers


# ---------------------------------------------------------------- overlap limits
def test_overlap_within_cap():
    items = R.load_items()
    for wd in items["words"]:
        assert wd["tier2_tier3_content_jaccard"] <= items["jaccard_cap"]
    # zero VERBATIM clause reuse between Tier-2 and any Tier-3 clause
    t2 = set(BLD.TIER2_OTHER) | set(BLD.TIER2_SELF)
    t3 = {v for v in BLD.VARNA_PLAIN.values()}
    assert t2.isdisjoint(t3)


# ---------------------------------------------------------------- deterministic shuffle
def test_deterministic_and_seed_sensitive_shuffle():
    a = [(c["word"], c["tier"], c["context_pole"], c["packet_pole"]) for c in R.build_cells(R.load_items(), seed=1)]
    b = [(c["word"], c["tier"], c["context_pole"], c["packet_pole"]) for c in R.build_cells(R.load_items(), seed=1)]
    c2 = [(c["word"], c["tier"], c["context_pole"], c["packet_pole"]) for c in R.build_cells(R.load_items(), seed=2)]
    assert a == b and a != c2 and set(a) == set(c2)


# ---------------------------------------------------------------- aggregation matches hand calc
def _rows(d):
    return [{"word": w, "context_pole": ctx, "tier": t, "packet_pole": p, "score": s}
            for (w, ctx, t, p), s in d.items()]


def test_aggregation_matches_hand_calc():
    d = {}
    # one word "pride", all three tiers, hand-set:
    # specific: Pb|Cb=6 Pl|Cb=1 Pl|Cl=6 Pb|Cl=1 -> bind 5, lib 5, margin 10
    # valence : Pb|Cb=5 Pl|Cb=2 Pl|Cl=5 Pb|Cl=2 -> bind 3, lib 3, margin 6
    # source  : Pb|Cb=5 Pl|Cb=1 Pl|Cl=6 Pb|Cl=2 -> bind 4, lib 4, margin 8
    for (t, cells) in [("specific", (6, 1, 6, 1)), ("valence", (5, 2, 5, 2)), ("source_condition", (5, 1, 6, 2))]:
        b_cb, l_cb, l_cl, b_cl = cells
        d[("pride", "binding", t, "binding")] = b_cb
        d[("pride", "binding", t, "liberating")] = l_cb
        d[("pride", "liberating", t, "liberating")] = l_cl
        d[("pride", "liberating", t, "binding")] = b_cl
    agg = R.aggregate(_rows(d), n_total_cells=12)
    pw = agg["per_word"]["pride"]
    assert pw["specific_margin"] == 10
    assert pw["valence_margin"] == 6
    assert pw["generic_source_condition_margin"] == 8
    assert pw["increment_over_valence"] == 10 - 6            # 4
    assert pw["increment_over_source_condition"] == 10 - 8   # 2
    assert pw["tiers"]["specific"]["binding_direction_margin"] == 5
    assert pw["tiers"]["specific"]["liberating_direction_margin"] == 5
    assert agg["aggregate"]["increment_over_source_condition"] == 2


# ---------------------------------------------------------------- missing-data rules
def test_missing_data_excludes_incomplete_word():
    # full pride (as above) + a partial word "doubt" missing one specific cell -> doubt excluded from aggregate
    d = {}
    for (t, cells) in [("specific", (6, 1, 6, 1)), ("valence", (5, 2, 5, 2)), ("source_condition", (5, 1, 6, 2))]:
        b_cb, l_cb, l_cl, b_cl = cells
        for (ctx, p, val) in [("binding", "binding", b_cb), ("binding", "liberating", l_cb),
                              ("liberating", "liberating", l_cl), ("liberating", "binding", b_cl)]:
            d[("pride", ctx, t, p)] = val
    rows = _rows(d)
    # doubt: give all but one specific cell
    rows += [{"word": "doubt", "context_pole": "binding", "tier": "specific", "packet_pole": "binding", "score": 4}]
    agg = R.aggregate(rows, n_total_cells=24)
    assert "doubt" in agg["excluded_incomplete_words"]
    assert agg["per_word"]["doubt"]["incomplete"] is True
    assert "pride" in agg["complete_words"]


def test_missing_data_inconclusive_threshold():
    # only 1 of 72 cells present -> >15% missing -> inconclusive
    agg = R.aggregate([{"word": "pride", "context_pole": "binding", "tier": "specific",
                        "packet_pole": "binding", "score": 3}], n_total_cells=72)
    assert agg["status"] == "inconclusive_missing_data"


# ---------------------------------------------------------------- tier-identifiability near chance
def test_tier_identifiability_near_chance():
    diag = R.tier_identifiability(R.load_items())
    # style-only classifier must be near chance (1/3); allow a small margin
    assert diag["style_only_loo_accuracy"] <= 0.42, diag["style_only_loo_accuracy"]


# ---------------------------------------------------------------- no real model calls
def test_no_real_model_calls():
    assert R.FakeJudge().is_real is False
    part = R.run(mock=True)
    assert part["judge_is_real"] is False and part["mode"] == "MOCK"
    src = (HERE / "run_b1_10_control_ext.py").read_text()
    for banned in ("import torch", "import transformers", "openai", "requests"):
        assert banned not in src


def test_real_run_refused():
    try:
        R.run(mock=False, judge=R.FakeJudge(), decl_path=None)
        assert False, "expected PermissionError"
    except PermissionError as e:
        assert "real run requires" in str(e)


# ---------------------------------------------------------------- no verdict / guardrail tokens
def test_no_verdict_tokens():
    part = R.run(mock=True)
    agg = R.aggregate(part["ratings"])
    blob = json.dumps(part) + json.dumps(agg)
    assert "GENUTILITY" not in blob and "ONTOLOGICAL_SIGNAL" not in blob
    for v in ("PASS", "FAIL", "VALIDATED", "PROVES"):
        assert v not in blob
    assert part["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
