"""CPU tests for the Bhava/ontology supervised probe (generation-quality track).

Pure-Python tier (always runs): schema validation, JSONL loading, decision-category logic, report
generation. numpy tier (skips if numpy absent): probe trainer on toy separable data + feature
matrix building. No torch / GPU / checkpoint required.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

from cg_ablation import probe_schema as PS       # noqa: E402
from cg_ablation import probe_decide as PD        # noqa: E402


# ===========================================================================
# Tier 1 — pure Python
# ===========================================================================

class TestSchema:
    def test_valid_row_normalized(self):
        r = PS.validate_row({"id": "x", "label": True, "label_type": "correctness"})
        assert r["label"] == 1 and r["prompt"] == "" and r["metadata"] == {}

    def test_rejects_governance_label(self):
        for lt in ("trust_score", "tool_safety", "governance", "risk", "policy_violation"):
            with pytest.raises(PS.ProbeSchemaError):
                PS.validate_row({"id": "x", "label": 1, "label_type": lt})

    def test_rejects_unknown_label(self):
        with pytest.raises(PS.ProbeSchemaError):
            PS.validate_row({"id": "x", "label": 1, "label_type": "vibes"})

    def test_rejects_nonbinary_label(self):
        with pytest.raises(PS.ProbeSchemaError):
            PS.validate_row({"id": "x", "label": 2, "label_type": "correctness"})

    def test_missing_key(self):
        with pytest.raises(PS.ProbeSchemaError):
            PS.validate_row({"id": "x", "label": 1})

    def test_allowed_set_is_generation_quality(self):
        assert PS.ALLOWED_LABEL_TYPES == frozenset({
            "correctness", "format_validity", "constraint_satisfaction",
            "groundedness", "reasoning_correctness"})

    def test_load_fixture(self):
        rows = PS.load_probe_jsonl(_ABL / "probe_data" / "fixture_tiny.jsonl")
        assert len(rows) == 7
        assert {r["label_type"] for r in rows} <= PS.ALLOWED_LABEL_TYPES
        grouped = PS.group_by_label_type(rows)
        assert "correctness" in grouped


class TestDecisionLogic:
    def _r(self, auroc, beats, sel=0.1):
        # beats=True => decodable, tight CI above 0.5; else CI spans 0.5
        ci = [0.55, auroc + 0.05] if beats else [0.40, 0.62]
        return {"auroc": auroc, "auroc_ci": ci, "beats_chance": beats,
                "balanced_accuracy": auroc, "selectivity": sel, "f1": auroc,
                "accuracy": auroc, "chance": 0.5, "brier": 0.2}

    def _sig(self, better):
        return {"delta_acc": 0.1 if better else 0.0, "ci": [0.05, 0.15] if better else [-0.1, 0.1],
                "mcnemar_p": 0.01 if better else 0.5, "significant": better,
                "direction": "cand_better" if better else "tie"}

    def test_insufficient_data_small_n(self):
        res = {"bhava_only": self._r(0.9, True), "hidden_only": self._r(0.9, True)}
        v = PD.decide(res, {}, n=10, min_per_class=8)
        assert v["decision"] == "INSUFFICIENT_DATA"

    def test_no_signal(self):
        res = {"bhava_only": self._r(0.5, False), "hidden_only": self._r(0.5, False)}
        v = PD.decide(res, {}, n=100, min_per_class=8)
        assert v["decision"] == "NO_SIGNAL"

    def test_hidden_only_signal(self):
        res = {"bhava_only": self._r(0.5, False), "hidden_only": self._r(0.85, True),
               "hidden_plus_bhava": self._r(0.85, True)}
        v = PD.decide(res, {"hidden_plus_bhava_vs_hidden": self._sig(False)}, n=100, min_per_class=8)
        assert v["decision"] == "HIDDEN_ONLY_SIGNAL"

    def test_bhava_weak_signal(self):
        res = {"bhava_only": self._r(0.62, True), "hidden_only": self._r(0.85, True),
               "hidden_plus_bhava": self._r(0.85, True)}
        v = PD.decide(res, {"hidden_plus_bhava_vs_hidden": self._sig(False)}, n=100, min_per_class=8)
        assert v["decision"] == "BHAVA_WEAK_SIGNAL"

    def test_bhava_complementary(self):
        res = {"bhava_only": self._r(0.6, True), "hidden_only": self._r(0.8, True),
               "hidden_plus_bhava": self._r(0.88, True)}
        v = PD.decide(res, {"hidden_plus_bhava_vs_hidden": self._sig(True)}, n=100, min_per_class=8)
        assert v["decision"] == "BHAVA_COMPLEMENTARY_SIGNAL"
        assert PD.continues_bhava(v["decision"])

    def test_continue_requires_both_conditions(self):
        # bhava decodable but NO complement -> WEAK (park), NOT continue
        res = {"bhava_only": self._r(0.82, True), "hidden_only": self._r(0.55, False),
               "hidden_plus_bhava": self._r(0.82, True)}
        v = PD.decide(res, {"hidden_plus_bhava_vs_hidden": self._sig(False)}, n=100, min_per_class=8)
        assert v["decision"] == "BHAVA_WEAK_SIGNAL" and not PD.continues_bhava(v["decision"])

    def test_complement_without_decodable_bhava_parks(self):
        # complement significant but bhava_only NOT decodable -> must NOT continue (strict rule)
        res = {"bhava_only": self._r(0.5, False), "hidden_only": self._r(0.8, True),
               "hidden_plus_bhava": self._r(0.85, True)}
        v = PD.decide(res, {"hidden_plus_bhava_vs_hidden": self._sig(True)}, n=100, min_per_class=8)
        assert not PD.continues_bhava(v["decision"])

    def test_bhava_strong(self):
        res = {"bhava_only": self._r(0.86, True), "hidden_only": self._r(0.8, True),
               "hidden_plus_bhava": self._r(0.9, True)}
        v = PD.decide(res, {"hidden_plus_bhava_vs_hidden": self._sig(True)}, n=100, min_per_class=8)
        assert v["decision"] == "BHAVA_STRONG_SIGNAL"

    def test_parks_vs_continues(self):
        assert PD.parks_bhava("HIDDEN_ONLY_SIGNAL")
        assert PD.parks_bhava("BHAVA_WEAK_SIGNAL")
        assert PD.parks_bhava("NO_SIGNAL")
        assert not PD.parks_bhava("BHAVA_COMPLEMENTARY_SIGNAL")
        assert PD.continues_bhava("BHAVA_STRONG_SIGNAL")


class TestReportGeneration:
    def test_report_from_synthetic_results(self, tmp_path):
        import importlib
        rep_mod = importlib.import_module("bhava_probe_report")
        # minimal results.json the report can render
        results = {"model": "logreg", "k": 5, "by_label_type": {
            "correctness": {
                "n": 100, "pos": 50, "neg": 50,
                "results": {
                    "bhava_only": {"accuracy": 0.55, "acc_ci": [0.5, 0.6], "auroc": 0.55,
                                   "f1": 0.5, "chance": 0.5, "selectivity": 0.05, "beats_chance": False},
                    "hidden_only": {"accuracy": 0.85, "acc_ci": [0.8, 0.9], "auroc": 0.85,
                                    "f1": 0.85, "chance": 0.5, "selectivity": 0.3, "beats_chance": True},
                },
                "paired": {"hidden_plus_bhava_vs_hidden": {"delta_acc": 0.0, "ci": [-0.05, 0.05],
                           "mcnemar_p": 0.6, "significant": False, "direction": "tie"}},
                "verdict": {"decision": "HIDDEN_ONLY_SIGNAL", "reasons": ["hidden predicts; bhava ~chance"],
                            "answers": {"bhava_beats_chance": False, "bhava_complements_hidden": False}},
            }}}
        (tmp_path / "results.json").write_text(json.dumps(results))
        (tmp_path / "config.json").write_text(json.dumps({"model_id": "stub"}))
        summary = rep_mod.build(tmp_path)
        assert (tmp_path / "report.md").exists() and (tmp_path / "summary.json").exists()
        assert summary["overall_decision"] == "PARK_CG"
        assert "HIDDEN_ONLY_SIGNAL" in (tmp_path / "report.md").read_text()


class TestDatasetBuilder:
    """The generate→score labeling produces correct objective labels (scoring is pure)."""

    def _mod(self):
        import importlib
        return importlib.import_module("build_probe_dataset")

    def test_exact_match_scoring(self):
        B = self._mod()
        assert B.score_generation({"kind": "exact_match", "answer": 42}, "work #### 42") == 1
        assert B.score_generation({"kind": "exact_match", "answer": 42}, "#### 41") == 0

    def test_constraint_scoring(self):
        B = self._mod()
        sc = {"kind": "constraint", "constraints": [{"type": "one_of", "value": ["yes", "no"]}]}
        assert B.score_generation(sc, "YES") == 1
        assert B.score_generation(sc, "maybe") == 0

    def test_json_scoring(self):
        B = self._mod()
        sc = {"kind": "json", "required_keys": ["name", "age"]}
        assert B.score_generation(sc, '{"name":"x","age":3}') == 1
        assert B.score_generation(sc, '{"name":"x"}') == 0

    def test_pool_integrity(self):
        pool_path = _ABL / "probe_pool" / "pool.jsonl"
        rows = [json.loads(l) for l in pool_path.read_text().splitlines() if l.strip()]
        assert len(rows) >= 200
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids))
        for r in rows:
            assert {"id", "prompt", "label_type", "scorer"} <= set(r)
            assert r["label_type"] in PS.ALLOWED_LABEL_TYPES

    def test_pool_balanced_correctness_and_no_format_leak(self):
        from collections import Counter
        pool_path = _ABL / "probe_pool" / "pool.jsonl"
        rows = [json.loads(l) for l in pool_path.read_text().splitlines() if l.strip()]
        c = Counter(r["label_type"] for r in rows)
        # format_validity dropped (template-leaked); correctness has a large graded pool.
        assert "format_validity" not in c
        assert c["correctness"] >= 100
        # graded-difficulty present: trivial single-op and hard multi-step both exist
        prompts = " ".join(r["prompt"] for r in rows if r["label_type"] == "correctness")
        assert "What is" in prompts and "depot" in prompts


class TestReportWarnings:
    def _mod(self):
        import importlib
        return importlib.import_module("bhava_probe_report")

    def test_single_class_warning(self):
        W = self._mod().data_warnings({"pos": 40, "neg": 0, "results": {}})
        assert any("SINGLE-CLASS" in w for w in W)

    def test_too_few_warning(self):
        W = self._mod().data_warnings({"pos": 3, "neg": 90, "results": {}})
        assert any("TOO FEW" in w for w in W)

    def test_imbalance_warning(self):
        W = self._mod().data_warnings({"pos": 13, "neg": 87, "results": {}})
        assert any("CLASS IMBALANCE" in w for w in W)

    def test_hidden_below_chance_warning(self):
        W = self._mod().data_warnings({"pos": 50, "neg": 50,
                                       "results": {"hidden_only": {"auroc": 0.35}}})
        assert any("HIDDEN BASELINE" in w for w in W)

    def test_leakage_warning(self):
        res = {k: {"auroc": 1.0} for k in ("bhava_only", "hidden_only", "hidden_plus_bhava")}
        W = self._mod().data_warnings({"pos": 30, "neg": 50, "results": res})
        assert any("LEAKED" in w for w in W)


# ===========================================================================
# Tier 2 — numpy (skips if numpy absent)
# ===========================================================================

try:
    import numpy as np  # noqa: F401
    _HAS_NP = True
except Exception:
    _HAS_NP = False

npmark = pytest.mark.skipif(not _HAS_NP, reason="numpy required for probe trainer tests")


@npmark
class TestProbeTrainer:
    def test_learns_separable(self):
        import numpy as np
        from cg_ablation import probe_train as PT
        rng = np.random.RandomState(0)
        n = 120
        y = (rng.rand(n) > 0.5).astype(int)
        X = (y[:, None] * 2 - 1) * 1.5 + rng.randn(n, 4) * 0.5
        r = PT.evaluate_feature_set(X, y, k=5, seed=0, n_boot=300)
        assert r["accuracy"] > 0.8 and r["beats_chance"] and r["selectivity"] > 0.2

    def test_noise_does_not_beat_chance(self):
        import numpy as np
        from cg_ablation import probe_train as PT
        rng = np.random.RandomState(1)
        n = 120
        y = (rng.rand(n) > 0.5).astype(int)
        X = rng.randn(n, 4)
        r = PT.evaluate_feature_set(X, y, k=5, seed=0, n_boot=300)
        assert not r["beats_chance"]

    def test_auroc_and_paired(self):
        import numpy as np
        from cg_ablation import probe_train as PT
        rng = np.random.RandomState(2)
        n = 100
        y = (rng.rand(n) > 0.5).astype(int)
        good = (y[:, None] * 2 - 1) + rng.randn(n, 3) * 0.6
        noise = rng.randn(n, 3)
        rg = PT.evaluate_feature_set(good, y, k=5, seed=0, n_boot=300)
        rn = PT.evaluate_feature_set(noise, y, k=5, seed=0, n_boot=300)
        assert 0.0 <= rg["auroc"] <= 1.0 and rg["auroc"] > rn["auroc"]
        pr = PT.paired_vs_reference(y, rn["oof_correct"], rg["oof_correct"])
        assert pr["direction"] == "cand_better"


@npmark
class TestPerGroupPCA:
    def test_pca_keeps_bhava_from_being_swamped(self):
        import numpy as np
        from cg_ablation import probe_train as PT, probe_features as PF
        rng = np.random.RandomState(0)
        n = 120
        y = (rng.rand(n) > 0.5).astype(int)
        bhava = (y[:, None] * 2 - 1) * 1.2 + rng.randn(n, 12) * 0.6   # signal
        hidden = rng.randn(n, 4096)                                   # noise
        rb = PT.evaluate_groups({"bhava": bhava}, y, reduce_groups=PF.HIDDEN_KEYS,
                                pca_dim=24, n_boot=200)
        rh = PT.evaluate_groups({"hidden_pooled": hidden}, y, reduce_groups=PF.HIDDEN_KEYS,
                                pca_dim=24, n_boot=200)
        rhpb = PT.evaluate_groups({"hidden_pooled": hidden, "bhava": bhava}, y,
                                  reduce_groups=PF.HIDDEN_KEYS, pca_dim=24, n_boot=200)
        assert rb["beats_chance"]                       # bhava decodable
        assert not rh["beats_chance"]                   # hidden noise ~chance (NOT below)
        assert rhpb["auroc"] > 0.7                       # bhava survives concatenation

    def test_pca_gives_near_chance_on_noise(self):
        import numpy as np
        from cg_ablation import probe_train as PT
        rng = np.random.RandomState(1)
        n = 100
        y = np.zeros(n, int); y[rng.choice(n, 13, replace=False)] = 1
        hidden = rng.randn(n, 4096)   # pure noise -> a fair baseline must be ~chance
        with_pca = PT.evaluate_feature_set(hidden, y, pca_dim=24, n_boot=200)
        assert abs(with_pca["auroc"] - 0.5) < 0.2 and not with_pca["beats_chance"]


@npmark
class TestSingleClassHandling:
    def test_single_class_auroc_is_nan(self):
        import numpy as np
        from cg_ablation import probe_train as PT
        y = np.ones(40, int)           # all positive — degenerate
        X = np.random.RandomState(0).randn(40, 8)
        r = PT.evaluate_feature_set(X, y, n_boot=100)
        import math
        assert math.isnan(r["auroc"]) and not r["beats_chance"]


@npmark
class TestFeatureBuilder:
    def test_build_matrix_from_arrays(self):
        import numpy as np
        from cg_ablation import probe_features as PF
        arrays = {"bhava": np.zeros((5, 12)), "bhava_entropy": np.zeros(5),
                  "hidden_pooled": np.zeros((5, 8)), "state32": np.zeros((5, 32))}
        assert PF.build_matrix_from_arrays(arrays, "hidden_plus_bhava").shape == (5, 20)
        assert PF.build_matrix_from_arrays(arrays, "bhava_only").shape == (5, 13)
        assert "hidden_only" in PF.available_sets_arrays(arrays)
        assert "delta_bhava_only" not in PF.available_sets_arrays(arrays)
