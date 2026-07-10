"""Deterministic mock tests for the B1.10 pole-context micro-test harness. NO real model, NO network.

Proves (per the build request):
  1. exactly 12 rating cells are produced (3 words x 2 contexts x 2 packets);
  2. packets are byte-equal / hash-equal to the frozen v3 table sources;
  3. randomization is deterministic under a seed (and seed-sensitive);
  4. no pole labels / varṇa tags / system names leak into judge prompts;
  5. the statistic calculation matches the prereg formula exactly (hand-set scores);
  6. no real model calls occur (FakeJudge only; is_real is False).

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import hashlib
import json
import pathlib

import build_b1_9_pole_did_scaffold as B0
import varna_bridge_active as AB
import run_b1_10_pole_context_microtest as R

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- 1. 12 cells
def test_twelve_cells_exactly():
    cells = R.build_cells(R.load_items())
    assert len(cells) == 12
    # 3 words x 2 contexts x 2 packets, each combination present exactly once
    combos = {(c["word"], c["context_pole"], c["packet_pole"]) for c in cells}
    assert len(combos) == 12
    for w in ("happy", "peace", "love"):
        for ctx in ("binding", "liberating"):
            for pkt in ("binding", "liberating"):
                assert (w, ctx, pkt) in combos
    assert [c["cell_id"] for c in cells] == [f"C{i:02d}" for i in range(1, 13)]


def test_run_produces_12_cells():
    part = R.run(mock=True)
    assert part["n_cells"] == 12 and part["n_rated"] == 12 and part["n_failures"] == 0


# ---------------------------------------------------------------- 2. packets byte-equal to frozen v3
def test_packets_byte_equal_to_frozen_v3():
    items = R.load_items()
    table = json.loads((FROZEN / "varna_polarity_table_v3.json").read_text())["varnas"]
    for wd in items["words"]:
        w = wd["word"]
        seq = AB.word_to_varnas(w)
        assert wd["varna_sequence"] == seq, f"{w}: stored seq != active-bridge seq"
        for pole_key, pole_field in (("binding", B0.BINDING), ("liberating", B0.LIBERATING)):
            # rebuild the deduped facet list live from the frozen v3 table and require exact text equality
            seen, expected = set(), []
            for v in seq:
                txt = table[v][pole_field]
                if txt in seen:
                    continue
                seen.add(txt); expected.append({"varna": v, "text": txt})
            assert wd["packets"][pole_key] == expected, f"{w}/{pole_key}: packet text drift vs frozen v3"


def test_items_pin_frozen_source_hashes():
    items = R.load_items()
    assert items["source_hashes"]["varna_polarity_table_v3.json"] == _sha(FROZEN / "varna_polarity_table_v3.json")
    assert items["source_hashes"]["stage_a_prime_coverage.py"] == _sha(HERE / "stage_a_prime_coverage.py")


# ---------------------------------------------------------------- 3. deterministic randomization
def test_shuffle_deterministic_under_seed():
    a = [c["cell_id"] + "|" + c["word"] + "|" + c["context_pole"] + "|" + c["packet_pole"]
         for c in R.build_cells(R.load_items(), seed=R.DEFAULT_SEED)]
    b = [c["cell_id"] + "|" + c["word"] + "|" + c["context_pole"] + "|" + c["packet_pole"]
         for c in R.build_cells(R.load_items(), seed=R.DEFAULT_SEED)]
    assert a == b   # same seed -> identical order


def test_shuffle_seed_sensitive():
    order1 = [(c["word"], c["context_pole"], c["packet_pole"]) for c in R.build_cells(R.load_items(), seed=1)]
    order2 = [(c["word"], c["context_pole"], c["packet_pole"]) for c in R.build_cells(R.load_items(), seed=2)]
    assert order1 != order2   # different seed -> (very likely) different order; both are permutations of the same set
    assert set(order1) == set(order2)


# ---------------------------------------------------------------- 4. no leak into judge prompts
def test_no_pole_labels_leak_in_prompts():
    cells = R.build_cells(R.load_items())
    for c in cells:
        # the judge-visible packager asserts blinding; it must not raise
        pkg = R.make_judge_visible(c)
        assert set(pkg.keys()) == {"cell_id", "prompt"}
        low = pkg["prompt"].lower()
        for tok in ("binding", "liberating", "worldly_binding", "spiritual_liberating",
                    "context_pole", "packet_pole", "correct_pole", "flipped_pole", "symbolu", "varna", "varṇa"):
            assert tok not in low, f"{c['cell_id']}: leaked {tok!r}"
        assert "[" not in pkg["prompt"], f"{c['cell_id']}: bracketed varṇa tag leaked"
        # the pole names of THIS cell must not appear as words
        assert R.leaked_judge_tokens(pkg["prompt"]) == []


def test_blinding_raises_on_injected_label():
    cells = R.build_cells(R.load_items())
    bad = dict(cells[0])
    bad["prompt"] = cells[0]["prompt"] + "\n(this is the binding packet)"
    try:
        R.make_judge_visible(bad)
        assert False, "expected INVALID_BLINDING"
    except ValueError as e:
        assert "INVALID_BLINDING" in str(e)


# ---------------------------------------------------------------- 5. statistic matches prereg
def _rows(scores):
    """scores: {(word, ctx, pkt): score} -> rating rows."""
    return [{"word": w, "context_pole": ctx, "packet_pole": pkt, "score": s}
            for (w, ctx, pkt), s in scores.items()]


def test_statistic_matches_prereg_formula():
    # one word, hand-set: Pb|Cb=5, Pl|Cb=2, Pl|Cl=6, Pb|Cl=1
    scores = {("happy", "binding", "binding"): 5, ("happy", "binding", "liberating"): 2,
              ("happy", "liberating", "liberating"): 6, ("happy", "liberating", "binding"): 1}
    agg = R.aggregate(_rows(scores))
    pw = agg["per_word"]["happy"]
    assert pw["binding_direction_margin"] == 5 - 2          # 3
    assert pw["liberating_direction_margin"] == 6 - 1       # 5
    assert pw["context_pole_margin"] == (5 - 2) + (6 - 1)   # 8
    assert pw["cell_means"] == {"Pb|Cb": 5, "Pl|Cb": 2, "Pl|Cl": 6, "Pb|Cl": 1}
    assert agg["aggregate_mean_margin"] == 8.0


def test_aggregate_mean_over_words():
    scores = {}
    # happy margin 8 (as above); peace margin 0 (all equal); love margin -2
    for (w, ctx, pkt), s in {("happy", "binding", "binding"): 5, ("happy", "binding", "liberating"): 2,
                             ("happy", "liberating", "liberating"): 6, ("happy", "liberating", "binding"): 1,
                             ("peace", "binding", "binding"): 3, ("peace", "binding", "liberating"): 3,
                             ("peace", "liberating", "liberating"): 3, ("peace", "liberating", "binding"): 3,
                             ("love", "binding", "binding"): 1, ("love", "binding", "liberating"): 2,
                             ("love", "liberating", "liberating"): 2, ("love", "liberating", "binding"): 3}.items():
        scores[(w, ctx, pkt)] = s
    agg = R.aggregate(_rows(scores))
    assert agg["per_word"]["peace"]["context_pole_margin"] == 0
    assert agg["per_word"]["love"]["context_pole_margin"] == (1 - 2) + (2 - 3)   # -2
    assert agg["aggregate_mean_margin"] == (8 + 0 + -2) / 3


def test_cell_means_average_replicates():
    # two replicates for one cell -> mean is used
    rows = _rows({("happy", "binding", "liberating"): 2, ("happy", "liberating", "liberating"): 6,
                  ("happy", "liberating", "binding"): 1})
    rows += [{"word": "happy", "context_pole": "binding", "packet_pole": "binding", "score": 4},
             {"word": "happy", "context_pole": "binding", "packet_pole": "binding", "score": 6}]
    agg = R.aggregate(rows)
    assert agg["per_word"]["happy"]["cell_means"]["Pb|Cb"] == 5.0   # (4+6)/2


# ---------------------------------------------------------------- 6. no real model calls
def test_no_real_model_calls():
    j = R.FakeJudge()
    assert j.is_real is False and j.backend == "fake_judge"
    part = R.run(mock=True)
    assert part["judge_is_real"] is False
    assert part["mode"] == "MOCK"
    # source has no ML/LLM client imports
    src = (HERE / "run_b1_10_pole_context_microtest.py").read_text()
    for banned in ("import torch", "import transformers", "openai", "requests", "http"):
        assert banned not in src, f"unexpected client import: {banned}"


def test_real_run_refused_without_gate():
    try:
        R.run(mock=False, judge=None, decl_path=None)
        assert False, "expected PermissionError"
    except PermissionError as e:
        assert "real run requires" in str(e)


def test_real_run_refused_with_fake_judge_even_if_decl_missing():
    # a fabricated decl path that doesn't exist must be refused by the freeze gate
    try:
        R.run(mock=False, judge=R.FakeJudge(), decl_path=pathlib.Path("/nonexistent_decl.json"))
        assert False, "expected PermissionError"
    except PermissionError as e:
        assert "EVIDENCE_FREEZE gate refused" in str(e)


# ---------------------------------------------------------------- guardrails / no verdict
def test_no_verdict_or_guardrail_tokens_emitted():
    part = R.run(mock=True)
    agg = R.aggregate(part["ratings"])
    blob = json.dumps(part) + json.dumps(agg)
    assert "GENUTILITY" not in blob
    assert "ONTOLOGICAL_SIGNAL" not in blob
    for verdict in ("PASS", "FAIL", "LEGIBLE", "VALIDATED", "PROVES"):
        assert verdict not in blob
    assert part["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    assert agg["track_b_status"] == "BLOCKED"


def test_parse_rating():
    assert R.parse_rating("Score: 4\nWhy: because")[0] == 4
    assert R.parse_rating("no score here")[0] is None
    assert R.parse_rating("Score: 9\nWhy: x")[0] is None   # out of range
