"""
Tests for GL-Cache group-level learned eviction.

Validates:
1. GBStumpEnsemble training and prediction
2. GLCacheLearner lifecycle (record, refault, flush, train, score)
3. Feature extraction
4. Integration with CTMPlusController
5. Benchmark comparison: CTM+ with Hedge vs CTM+ with GL-Cache

Run: python -m pytest tests/test_glcache.py -v
"""

import math
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "simulator"))

import pytest

from ctm_plus.controllers.glcache import (
    GBStumpEnsemble,
    GLCacheLearner,
    GLCacheConfig,
    DecisionStump,
    fit_stump,
    extract_features,
    frequency_group,
    NUM_FEATURES,
)
from ctm_plus.core.config import (
    SimulatorConfig,
    CTMPlusConfig,
    GLCacheConfig as GLCacheConfigFrozen,
)
from ctm_plus.core.state import OpType
from ctm_plus.simulator import Simulator
from ctm_plus.traces.loader import TraceEvent


# ============================================================================
# Decision Stump
# ============================================================================

class TestDecisionStump:
    def test_basic_prediction(self):
        stump = DecisionStump(feature_idx=0, threshold=0.5, left_val=1.0, right_val=-1.0)
        assert stump.predict([0.3, 0.0]) == 1.0
        assert stump.predict([0.7, 0.0]) == -1.0
        assert stump.predict([0.5, 0.0]) == 1.0  # <= threshold

    def test_fit_stump(self):
        X = [[0.1], [0.2], [0.8], [0.9]]
        residuals = [1.0, 1.0, -1.0, -1.0]
        stump = fit_stump(X, residuals, num_features=1)
        # Should split around 0.5
        assert stump.left_val > 0  # Low values → positive residual
        assert stump.right_val < 0  # High values → negative residual


# ============================================================================
# GBStumpEnsemble
# ============================================================================

class TestGBStumpEnsemble:
    def test_untrained_returns_zero(self):
        model = GBStumpEnsemble()
        assert model.predict_score([0.5] * 12) == 0.0
        assert not model.trained

    def test_training_basic(self):
        model = GBStumpEnsemble(num_rounds=5, num_features=3)
        rng = random.Random(42)
        X = [[rng.random() for _ in range(3)] for _ in range(50)]
        y = [1.0 if x[0] > 0.5 else 0.0 for x in X]  # Feature 0 is signal
        model.fit(X, y)
        assert model.trained
        assert len(model.stumps) == 5

    def test_learns_signal(self):
        """Model should learn to score high-feature-0 objects higher."""
        model = GBStumpEnsemble(num_rounds=10, num_features=4)
        rng = random.Random(42)
        X = [[rng.random() for _ in range(4)] for _ in range(200)]
        y = [1.0 if x[0] > 0.7 else 0.0 for x in X]
        model.fit(X, y)

        # High feature 0 should score higher (more likely refaulted = keep)
        high_score = model.predict_score([0.9, 0.5, 0.5, 0.5])
        low_score = model.predict_score([0.1, 0.5, 0.5, 0.5])
        assert high_score > low_score

    def test_batch_predict(self):
        model = GBStumpEnsemble(num_rounds=3, num_features=2)
        X = [[0.1, 0.2], [0.3, 0.4], [0.8, 0.9]]
        y = [0.0, 0.0, 1.0]
        model.fit(X, y)
        scores = model.predict_batch_scores(X)
        assert len(scores) == 3

    def test_too_few_samples(self):
        model = GBStumpEnsemble()
        model.fit([[0.5] * 12], [1.0])  # Only 1 sample
        assert not model.trained  # Should not train with < 4 samples

    def test_all_zeros(self):
        """Model handles all-zero outcomes without crashing."""
        model = GBStumpEnsemble(num_rounds=3, num_features=2)
        X = [[0.5, 0.5]] * 20
        y = [0.0] * 20  # All good evictions
        model.fit(X, y)
        assert model.trained


# ============================================================================
# GLCacheLearner
# ============================================================================

class TestGLCacheLearner:
    def _make_learner(self, **kwargs):
        defaults = dict(train_interval=30, min_train_samples=10, refault_window=100)
        defaults.update(kwargs)
        return GLCacheLearner(GLCacheConfig(**defaults))

    def test_basic_lifecycle(self):
        learner = self._make_learner(refault_window=40)  # keep=10
        rng = random.Random(42)

        # Record evictions
        for i in range(50):
            feats = [rng.random() for _ in range(NUM_FEATURES)]
            learner.record_eviction(i, feats, frequency_group(rng.randint(1, 30)))

        assert learner.total_evictions == 50
        assert len(learner._pending) == 50

        # Mark some as refaults
        for i in range(0, 20):
            learner.record_refault(i)

        assert learner.total_refaults == 20
        assert len(learner._pending) == 30

        # Flush old (keep=10, flush 20 of 30 pending)
        learner.flush_old_pending(1000)
        assert len(learner._pending) <= 10

        # Now we have 20 refaults + 20 flushed = 40 completed
        # _since_last_train = 40 >= train_interval=30
        trained = learner.maybe_train()
        assert trained
        assert learner.is_trained

    def test_scoring_after_training(self):
        learner = self._make_learner()
        rng = random.Random(42)

        for i in range(60):
            feats = [rng.random() for _ in range(NUM_FEATURES)]
            learner.record_eviction(i, feats, i % 4)

        for i in range(20):
            learner.record_refault(i)

        learner.flush_old_pending(1000)
        learner.maybe_train()

        s = learner.score([0.5] * NUM_FEATURES, 0)
        assert isinstance(s, float)

    def test_fallback_weights(self):
        learner = self._make_learner()
        assert not learner.is_trained
        weights = learner.get_weights()
        assert len(weights) == 5
        assert abs(sum(weights) - 1.0) < 0.01

    def test_reset(self):
        learner = self._make_learner()
        for i in range(10):
            learner.record_eviction(i, [0.5] * NUM_FEATURES, 0)
        learner.reset()
        assert learner.total_evictions == 0
        assert len(learner._pending) == 0
        assert not learner.is_trained

    def test_stats(self):
        learner = self._make_learner()
        stats = learner.get_stats()
        assert "total_evictions" in stats
        assert "refault_rate" in stats
        assert "global_model_trained" in stats
        assert "group_counts" in stats


# ============================================================================
# Feature extraction
# ============================================================================

class TestFeatureExtraction:
    def test_frequency_groups(self):
        assert frequency_group(0) == 0
        assert frequency_group(1) == 0
        assert frequency_group(3) == 1
        assert frequency_group(10) == 2
        assert frequency_group(50) == 3

    def test_extract_features_shape(self):
        class MockPage:
            last_access_time = 100
            access_count = 5
            write_count = 1
            coherence = 0.7
            amplitude = 0.5
            heat = 0.1
            drift = 0.05
            size_bytes = 4096
            created_time = 50

        feats = extract_features(
            MockPage(), current_time=200, max_time=200, min_time=50,
            tier0_capacity=100, reuse_score=0.3, neighbor_hotness=0.4,
            irr_normalized=0.2,
        )
        assert len(feats) == NUM_FEATURES
        # All features should be finite
        assert all(math.isfinite(f) for f in feats)


# ============================================================================
# CTMPlusController integration
# ============================================================================

class TestCTMPlusIntegration:
    def test_glcache_enabled(self):
        config = SimulatorConfig(tier0_size=100, tier1_size=10000)
        ctm_cfg = CTMPlusConfig(glcache=GLCacheConfigFrozen(enabled=True))
        from ctm_plus.controllers.ctm_plus import CTMPlusController
        ctrl = CTMPlusController(config, ctm_cfg)
        assert ctrl._glcache is not None

    def test_glcache_disabled_by_default(self):
        config = SimulatorConfig(tier0_size=100, tier1_size=10000)
        ctm_cfg = CTMPlusConfig()
        from ctm_plus.controllers.ctm_plus import CTMPlusController
        ctrl = CTMPlusController(config, ctm_cfg)
        assert ctrl._glcache is None

    def test_glcache_simulation_runs(self):
        """Full simulation with GL-Cache enabled completes without errors."""
        config = SimulatorConfig(tier0_size=100, tier1_size=10000)
        ctm_cfg = CTMPlusConfig(
            glcache=GLCacheConfigFrozen(enabled=True, train_interval=50, min_train_samples=20)
        )
        from ctm_plus.controllers.ctm_plus import CTMPlusController
        ctrl = CTMPlusController(config, ctm_cfg)

        trace = [
            TraceEvent(timestamp=i, page_id=i % 500, op_type=OpType.READ)
            for i in range(3000)
        ]

        sim = Simulator(config=config)
        result = sim.run(trace, ctrl, trace_name="glcache_test", verbose=False)

        assert result.metrics.total_accesses == 3000
        stats = ctrl.get_stats()
        assert stats["glcache_enabled"]
        assert stats["glcache_stats"]["total_evictions"] > 0
        assert stats["glcache_stats"]["train_count"] > 0

    def test_glcache_vs_hedge_comparison(self):
        """Run both Hedge and GL-Cache on same trace, verify both complete."""
        config = SimulatorConfig(tier0_size=50, tier1_size=5000)

        # Hedge (default)
        hedge_cfg = CTMPlusConfig()
        # GL-Cache
        gl_cfg = CTMPlusConfig(
            glcache=GLCacheConfigFrozen(enabled=True, train_interval=50, min_train_samples=20)
        )

        from ctm_plus.controllers.ctm_plus import CTMPlusController

        trace = [
            TraceEvent(timestamp=i, page_id=i % 200, op_type=OpType.READ)
            for i in range(5000)
        ]

        sim = Simulator(config=config)

        hedge_ctrl = CTMPlusController(config, hedge_cfg)
        gl_ctrl = CTMPlusController(config, gl_cfg)

        hedge_result = sim.run(trace, hedge_ctrl, trace_name="hedge", verbose=False)
        gl_result = sim.run(trace, gl_ctrl, trace_name="glcache", verbose=False)

        print(f"\n  Hedge hit rate:   {hedge_result.metrics.hit_rate:.2%}")
        print(f"  GL-Cache hit rate: {gl_result.metrics.hit_rate:.2%}")
        print(f"  GL-Cache trains:   {gl_ctrl.get_stats()['glcache_stats']['train_count']}")

        # Both should complete and produce valid metrics
        assert hedge_result.metrics.total_accesses == 5000
        assert gl_result.metrics.total_accesses == 5000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
