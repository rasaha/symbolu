"""CPU tests for the static CSR = Context x Semantic x Resonance probe (docs/STL_CSR_REFACTOR_PLAN.md).

Pure-Python tier: naming separation, feature-set construction, decision categories. numpy tier:
per-group PCA with hidden + CSR + low-dim groups, missing-feature handling. No torch/GPU/checkpoint.
"""

import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

from cg_ablation import probe_features as PF      # noqa: E402
from cg_ablation import probe_decide as PD         # noqa: E402


# ---------------------------------------------------------------------------
# Tier 1 — pure Python
# ---------------------------------------------------------------------------

class TestNamingSeparation:
    def test_state_vs_phoneme_bhava_distinct_sets(self):
        # state-Bhava (learned hidden slice) and phoneme-Bhava (vowel) are SEPARATE feature sets
        assert PF.FEATURE_SETS["state_bhava_only"] == ["state_bhava", "state_bhava_entropy"]
        assert PF.FEATURE_SETS["phoneme_bhava_only"] == ["phoneme_bhava"]
        assert PF.FEATURE_SETS["vritti_consonant_only"] == ["vritti_consonant"]
        # they never share a key
        assert set(PF.FEATURE_SETS["state_bhava_only"]).isdisjoint(PF.FEATURE_SETS["phoneme_bhava_only"])

    def test_context_is_r_ctx_not_32d(self):
        assert PF.FEATURE_SETS["context_r_ctx_only"] == ["context_r_ctx"]
        # state_32d is a SEPARATE baseline, not the context variable
        assert PF.FEATURE_SETS["state_32d"] == ["state32"]
        assert "state32" not in PF.FEATURE_SETS["context_r_ctx_only"]

    def test_csr_static_is_context_semantic_resonance(self):
        assert PF.FEATURE_SETS["csr_static"] == ["context_r_ctx", "semantic", "resonance_combined"]

    def test_resonance_split_and_combined_present(self):
        for s in ("phoneme_bhava_only", "vritti_consonant_only", "resonance_combined",
                  "phoneme_bhava_plus_vritti"):
            assert s in PF.FEATURE_SETS

    def test_legacy_bhava_sets_unchanged(self):
        # the existing bhava probe keys must NOT be renamed (backward compat)
        assert PF.FEATURE_SETS["bhava_only"] == ["bhava", "bhava_entropy"]
        assert PF.FEATURE_SETS["hidden_plus_bhava"] == ["hidden_pooled", "bhava"]

    def test_semantic_is_pca_reduced(self):
        assert "semantic" in PF.HIDDEN_KEYS and "hidden_pooled" in PF.HIDDEN_KEYS


class TestCsrDecision:
    @staticmethod
    def _r(au, beats):
        ci = [0.55, au + 0.05] if beats else [0.40, 0.62]
        return {"auroc": au, "auroc_ci": ci, "beats_chance": beats}

    @staticmethod
    def _s(better):
        return {"significant": better, "direction": "cand_better" if better else "tie"}

    def _base(self):
        return {"state_bhava_only": self._r(0.8, True), "hidden_only": self._r(0.78, True),
                "context_r_ctx_only": self._r(0.7, True), "semantic_only": self._r(0.72, True),
                "resonance_combined": self._r(0.55, False), "csr_static": self._r(0.79, True)}

    def test_strong_signal(self):
        v = PD.decide_csr(self._base(), {"hidden_plus_all_vs_hidden": self._s(True)}, n=170)
        assert v["decision"] == "CSR_STRONG_SIGNAL" and PD.csr_continues(v["decision"])

    def test_complementary(self):
        v = PD.decide_csr(self._base(), {"csr_vs_semantic": self._s(True)}, n=170)
        assert v["decision"] == "CSR_COMPLEMENTARY" and PD.csr_continues(v["decision"])

    def test_redundant(self):
        v = PD.decide_csr(self._base(), {}, n=170)
        assert v["decision"] == "CSR_REDUNDANT" and not PD.csr_continues(v["decision"])

    def test_resonance_only(self):
        res = {"resonance_combined": self._r(0.7, True), "context_r_ctx_only": self._r(0.5, False),
               "semantic_only": self._r(0.5, False), "hidden_only": self._r(0.5, False),
               "state_bhava_only": self._r(0.5, False)}
        v = PD.decide_csr(res, {}, n=170)
        assert v["decision"] == "RESONANCE_ONLY_SIGNAL"

    def test_hidden_only(self):
        res = {"hidden_only": self._r(0.8, True), "state_bhava_only": self._r(0.5, False),
               "context_r_ctx_only": self._r(0.5, False), "semantic_only": self._r(0.5, False),
               "resonance_combined": self._r(0.5, False)}
        v = PD.decide_csr(res, {}, n=170)
        assert v["decision"] == "HIDDEN_ONLY_SIGNAL"

    def test_insufficient(self):
        v = PD.decide_csr(self._base(), {}, n=10)
        assert v["decision"] == "INSUFFICIENT_DATA"

    def test_continue_requires_complement_or_strong(self):
        for d in ("CSR_REDUNDANT", "RESONANCE_ONLY_SIGNAL", "HIDDEN_ONLY_SIGNAL",
                  "STATE_BHAVA_ONLY_SIGNAL", "NO_SIGNAL"):
            assert not PD.csr_continues(d)


# ---------------------------------------------------------------------------
# Tier 2 — numpy
# ---------------------------------------------------------------------------

try:
    import numpy as np  # noqa: F401
    _HAS_NP = True
except Exception:
    _HAS_NP = False

npmark = pytest.mark.skipif(not _HAS_NP, reason="numpy required")


@npmark
class TestConstructionAndPCA:
    def test_missing_feature_drops_sets(self):
        # if CSR keys absent, csr_static is not 'available'; legacy sets still are
        arrays = {"bhava": np.zeros((5, 12)), "bhava_entropy": np.zeros(5),
                  "hidden_pooled": np.zeros((5, 8))}
        avail = PF.available_sets_arrays(arrays)
        assert "bhava_only" in avail and "hidden_only" in avail
        assert "csr_static" not in avail and "phoneme_bhava_only" not in avail

    def test_csr_sets_available_when_keys_present(self):
        n = 6
        arrays = {"context_r_ctx": np.zeros((n, 16)), "semantic": np.zeros((n, 4096)),
                  "resonance_combined": np.zeros((n, 12)), "hidden_pooled": np.zeros((n, 4096)),
                  "state_bhava": np.zeros((n, 12)), "state_bhava_entropy": np.zeros(n)}
        avail = PF.available_sets_arrays(arrays)
        for s in ("csr_static", "context_r_ctx_only", "semantic_only", "resonance_combined",
                  "hidden_plus_csr", "hidden_plus_state_bhava_plus_csr"):
            assert s in avail

    def test_per_group_pca_keeps_resonance_over_hidden(self):
        from cg_ablation import probe_train as PT
        rng = np.random.RandomState(0)
        n = 120
        y = (rng.rand(n) > 0.5).astype(int)
        resonance = (y[:, None] * 2 - 1) * 1.2 + rng.randn(n, 12) * 0.6  # signal
        hidden = rng.randn(n, 4096)                                      # noise
        full = PT.evaluate_groups({"hidden_pooled": hidden, "resonance_combined": resonance}, y,
                                  reduce_groups=PF.HIDDEN_KEYS, pca_dim=24, n_boot=200)
        assert full["auroc"] > 0.7   # resonance not swamped by 4096-d hidden noise

    def test_semantic_high_dim_is_reduced_not_below_chance(self):
        from cg_ablation import probe_train as PT
        rng = np.random.RandomState(1)
        n = 100
        y = np.zeros(n, int); y[rng.choice(n, 40, replace=False)] = 1
        semantic = rng.randn(n, 4096)   # noise -> fair PCA'd baseline ~chance
        r = PT.evaluate_groups({"semantic": semantic}, y, reduce_groups=PF.HIDDEN_KEYS,
                               pca_dim=24, n_boot=200)
        assert abs(r["auroc"] - 0.5) < 0.2 and not r["beats_chance"]
