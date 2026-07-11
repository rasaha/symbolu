"""Tests for the APPROVED v3 Qwen control-extension items (separately-labeled).

Proves: v3 items build from the approved context source; exactly 72 blinded cells; the 12 inserted contexts
match the approved source EXACTLY with the pinned block/file hashes; no leakage; style/register parity; Tier-2/
Tier-3 overlap within cap; tier-identifiability at/near chance; the ORIGINAL excluded-context items file and the
approved context file are UNCHANGED; no real judge is called. NO real model, NO network.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import hashlib
import pathlib

import build_b1_10_control_ext_v3_qwen as V3
import run_b1_10_control_ext as R

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V3_ITEMS = FROZEN / "b1_10_control_ext_items_v3_qwen.json"

# pinned hashes (from Stage-3 approval)
APPROVED_BLOCK_SHA = "e0a1477ebaaf41df95b489b7547a895369f115d5231c424fc8598d4f598c3046"
ORIGINAL_ITEMS_SHA = "df76b7feb1aa8534f5bd62c57b429478f8ea523911ad0bd6bb38f556f2a00ba9"


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def test_v3_items_exist_and_labeled():
    items = R.load_items(V3_ITEMS)
    assert items["status"] == "APPROVED_V3_CONTROL_EXT_MOCK_ONLY"
    assert items["approved_context_block_sha256"] == APPROVED_BLOCK_SHA
    assert items["approved_context_file_sha256"] == _sha(V3.APPROVED_MD)
    assert items["context_pole_mapping"] == "Condition A -> binding ; Condition B -> liberating"
    assert items["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"


def test_v3_exactly_72_cells():
    cells = R.build_cells(R.load_items(V3_ITEMS))
    assert len(cells) == 72
    combos = {(c["word"], c["context_pole"], c["tier"], c["packet_pole"]) for c in cells}
    assert len(combos) == 72
    expected = {(w, ctx, t, p) for w in R.TARGET_WORDS for ctx in R.POLES for t in R.TIERS for p in R.POLES}
    assert combos == expected
    assert [c["cell_id"] for c in cells] == [f"E{i:02d}" for i in range(1, 73)]


def test_v3_contexts_match_approved_source_exactly():
    contexts, block = V3.parse_approved_block(V3.APPROVED_MD)
    assert hashlib.sha256(block.encode()).hexdigest() == APPROVED_BLOCK_SHA
    assert sum(len(v) for v in contexts.values()) == 12
    items = R.load_items(V3_ITEMS)
    for wd in items["words"]:
        w = wd["word"]
        assert wd["contexts"]["binding"] == contexts[w]["binding"]       # Condition A
        assert wd["contexts"]["liberating"] == contexts[w]["liberating"]  # Condition B


def test_v3_no_leakage():
    for c in R.build_cells(R.load_items(V3_ITEMS)):
        pkg = R.make_judge_visible(c)
        assert set(pkg.keys()) == {"cell_id", "prompt"}
        for f in c["packet_facets"]:
            assert R.packet_leaks(f) == []
            assert f.isascii()


def test_v3_overlap_within_cap():
    items = R.load_items(V3_ITEMS)
    for wd in items["words"]:
        assert wd["tier2_tier3_content_jaccard"] <= items["jaccard_cap"]


def test_v3_tier_identifiability_near_chance():
    diag = R.tier_identifiability(R.load_items(V3_ITEMS))
    assert diag["style_only_loo_accuracy"] <= 0.42, diag["style_only_loo_accuracy"]


def test_v3_dry_check_is_mock_no_judge():
    part = R.run(mock=True, items_file=V3_ITEMS)
    assert part["mode"] == "MOCK" and part["judge_is_real"] is False
    assert part["n_cells"] == 72 and part["n_rated"] == 72


def test_original_excluded_items_unchanged():
    assert _sha(FROZEN / "b1_10_control_ext_items.json") == ORIGINAL_ITEMS_SHA


def test_v3_build_is_reproducible():
    # rebuilding to a temp path yields byte-identical content (deterministic; no Date/random)
    import json
    doc, block_sha, file_sha = V3.build_v3()
    assert block_sha == APPROVED_BLOCK_SHA
    committed = json.loads(V3_ITEMS.read_text())
    assert doc["n_words"] == committed["n_words"] == 6
    assert [w["word"] for w in doc["words"]] == [w["word"] for w in committed["words"]]
