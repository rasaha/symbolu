"""
Tests for Appendix F Stage 0 — Generation Tracer & Baseline Statistics.

Validates:
- GenerationTracer per-token recording (F.2.3)
- BindingCacheTracerMixin intent/salience tracking (F.2.7)
- CTMPlusTracerMixin layer access + tier simulation (F.2.8)
- MistralCGGenerationTracer composed recording (F.2.9)
- BaselineStatisticsAnalyzer full F.2.5 metrics computation
- Export/import round-trip
- Zero modification guarantee (tracer is observation-only)
"""

import json
import math
import os
import tempfile

import pytest
import torch
import torch.nn.functional as F

from symbolu.inference.generation_tracer import (
    GenerationTracer,
    BindingCacheTracerMixin,
    CTMPlusTracerMixin,
    MistralCGGenerationTracer,
    BaselineStatisticsAnalyzer,
)


# =============================================================================
# Fixtures
# =============================================================================

class _MockModel:
    """Minimal mock model for tracer init."""
    num_heads = 4
    embed_dim = 64
    mistral_hidden_dim = 64


@pytest.fixture
def mock_model():
    return _MockModel()


@pytest.fixture
def basic_tracer(mock_model):
    return GenerationTracer(model=mock_model)


@pytest.fixture
def mistral_tracer(mock_model):
    return MistralCGGenerationTracer(
        model=mock_model,
        binding_cache_top_k=8,
        ctm_num_layers=4,
        ctm_gpu_budget=2,
    )


def _fake_logits(vocab_size=100):
    """Return random logits tensor [vocab_size]."""
    return torch.randn(vocab_size)


def _fake_hidden(dim=64):
    """Return random hidden state tensor [dim]."""
    return torch.randn(dim)


def _fake_hidden_seq(seq_len=10, dim=64):
    """Return random hidden state tensor [seq_len, dim]."""
    return torch.randn(seq_len, dim)


# =============================================================================
# GenerationTracer (F.2.3)
# =============================================================================

class TestGenerationTracer:

    def test_record_token_basic(self, basic_tracer):
        logits = _fake_logits()
        hidden = _fake_hidden()
        basic_tracer.record_token(token_id=42, logits=logits, hidden_state=hidden)

        assert len(basic_tracer.trace) == 1
        entry = basic_tracer.trace[0]
        assert entry["token_id"] == 42
        assert "logit_entropy" in entry
        assert "token_prob" in entry
        assert "hidden_norm" in entry
        assert entry["logit_entropy"] >= 0
        assert entry["token_prob"] >= 0
        assert entry["hidden_norm"] >= 0

    def test_record_multiple_tokens(self, basic_tracer):
        for i in range(10):
            basic_tracer.record_token(
                token_id=i, logits=_fake_logits(), hidden_state=_fake_hidden()
            )
        assert len(basic_tracer.trace) == 10

    def test_record_with_onto_state(self, basic_tracer):
        basic_tracer.record_token(
            token_id=5,
            logits=_fake_logits(),
            hidden_state=_fake_hidden(),
            onto_state={"coherence": 0.85},
        )
        assert basic_tracer.trace[0]["bhava_coherence"] == 0.85

    def test_clear(self, basic_tracer):
        basic_tracer.record_token(token_id=0, logits=_fake_logits(), hidden_state=_fake_hidden())
        assert len(basic_tracer.trace) == 1
        basic_tracer.clear()
        assert len(basic_tracer.trace) == 0

    def test_export_and_load(self, basic_tracer):
        for i in range(5):
            basic_tracer.record_token(
                token_id=i, logits=_fake_logits(), hidden_state=_fake_hidden()
            )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            basic_tracer.export(path)
            with open(path, 'r') as f:
                loaded = json.load(f)
            assert len(loaded) == 5
            assert all("token_id" in e for e in loaded)
            assert all("logit_entropy" in e for e in loaded)
        finally:
            os.unlink(path)

    def test_summary_empty(self, basic_tracer):
        assert basic_tracer.summary() == {}

    def test_summary_returns_all_core_stats(self, basic_tracer):
        for i in range(20):
            basic_tracer.record_token(
                token_id=i % 10, logits=_fake_logits(), hidden_state=_fake_hidden()
            )
        stats = basic_tracer.summary()
        assert "mean_logit_entropy" in stats
        assert "num_tokens" in stats
        assert stats["num_tokens"] == 20
        # Repetition rate should be present for n-grams
        assert "token_repetition_rate_2gram" in stats
        assert "token_repetition_rate_3gram" in stats


# =============================================================================
# BindingCacheTracerMixin (F.2.7)
# =============================================================================

class TestBindingCacheTracerMixin:

    def test_init_and_record(self):
        mixin = BindingCacheTracerMixin()
        mixin.init_binding_cache_tracer(num_heads=4, head_dim=16, top_k=8)

        intent = torch.randn(4)
        hidden = _fake_hidden_seq(seq_len=20, dim=64)
        entry = mixin.record_binding_cache(
            token_id=10, hidden_state=hidden,
            intent_phase=intent, input_ids=torch.zeros(20, dtype=torch.long),
        )

        assert "intent_phase" in entry
        assert "intent_drift" in entry
        assert entry["intent_drift"] == 0.0  # First token, no previous
        assert "salience_entropy" in entry
        assert "salience_top_k_ratio" in entry
        assert "binding_cache_hit_rate" in entry

    def test_intent_drift_nonzero_after_two(self):
        mixin = BindingCacheTracerMixin()
        mixin.init_binding_cache_tracer(num_heads=4, head_dim=16, top_k=8)

        intent1 = torch.zeros(4)
        intent2 = torch.ones(4)
        hidden = _fake_hidden_seq()

        mixin.record_binding_cache(0, hidden, intent1, torch.zeros(10, dtype=torch.long))
        entry2 = mixin.record_binding_cache(1, hidden, intent2, torch.zeros(10, dtype=torch.long))

        assert entry2["intent_drift"] > 0

    def test_cache_hit_rate_short_seq(self):
        mixin = BindingCacheTracerMixin()
        mixin.init_binding_cache_tracer(num_heads=4, head_dim=16, top_k=64)

        hidden = _fake_hidden_seq(seq_len=10, dim=64)
        entry = mixin.record_binding_cache(
            0, hidden, torch.randn(4), torch.zeros(10, dtype=torch.long)
        )
        # Sequence (10) < top_k (64), so hit rate should be 1.0
        assert entry["binding_cache_hit_rate"] == 1.0


# =============================================================================
# CTMPlusTracerMixin (F.2.8)
# =============================================================================

class TestCTMPlusTracerMixin:

    def test_init_and_record(self):
        mixin = CTMPlusTracerMixin()
        mixin.init_ctm_plus_tracer(num_layers=8, gpu_budget=4)

        for i in range(8):
            mixin.record_layer_access(i)

        entry = mixin.record_ctm_metrics()

        assert "ctm_layer_access" in entry
        assert len(entry["ctm_layer_access"]) == 8
        assert "ctm_phase_coherence" in entry
        assert "ctm_workload_mode" in entry
        assert "ctm_simulated_gpu_layers" in entry
        assert entry["ctm_simulated_gpu_layers"] == 4
        assert entry["ctm_simulated_cpu_layers"] == 4

    def test_workload_temporal(self):
        """Uniform access should classify as temporal."""
        mixin = CTMPlusTracerMixin()
        mixin.init_ctm_plus_tracer(num_layers=4, gpu_budget=2)
        for i in range(4):
            mixin.record_layer_access(i)
        entry = mixin.record_ctm_metrics()
        assert entry["ctm_workload_mode"] == "temporal"

    def test_workload_scan(self):
        """Heavily skewed access should classify as scan."""
        mixin = CTMPlusTracerMixin()
        mixin.init_ctm_plus_tracer(num_layers=4, gpu_budget=2)
        for _ in range(100):
            mixin.record_layer_access(0)
        for i in range(1, 4):
            mixin.record_layer_access(i)
        entry = mixin.record_ctm_metrics()
        assert entry["ctm_workload_mode"] == "scan"

    def test_reset_access_counts(self):
        mixin = CTMPlusTracerMixin()
        mixin.init_ctm_plus_tracer(num_layers=4, gpu_budget=2)
        mixin.record_layer_access(0)
        mixin.reset_access_counts()
        assert all(c == 0 for c in mixin._access_counts)

    def test_out_of_range_layer_access(self):
        mixin = CTMPlusTracerMixin()
        mixin.init_ctm_plus_tracer(num_layers=4, gpu_budget=2)
        mixin.record_layer_access(-1)
        mixin.record_layer_access(100)
        assert all(c == 0 for c in mixin._access_counts)


# =============================================================================
# MistralCGGenerationTracer (F.2.9)
# =============================================================================

class TestMistralCGGenerationTracer:

    def test_record_with_all_metrics(self, mistral_tracer):
        # Record layer accesses
        for i in range(4):
            mistral_tracer.record_layer_access(i)

        intent = torch.randn(4)
        logits = _fake_logits()
        hidden = _fake_hidden_seq(seq_len=20, dim=64)

        mistral_tracer.record_token(
            token_id=7,
            logits=logits,
            hidden_state=hidden,
            intent_phase=intent,
            input_ids=torch.zeros(20, dtype=torch.long),
        )

        assert len(mistral_tracer.trace) == 1
        entry = mistral_tracer.trace[0]

        # Core fields
        assert entry["token_id"] == 7
        assert "logit_entropy" in entry
        assert "hidden_norm" in entry

        # Binding Cache fields
        assert "intent_phase" in entry
        assert "salience_entropy" in entry

        # CTM+ fields
        assert "ctm_layer_access" in entry
        assert "ctm_workload_mode" in entry

    def test_summary_includes_all_sections(self, mistral_tracer):
        for step in range(10):
            for i in range(4):
                mistral_tracer.record_layer_access(i)
            mistral_tracer.record_token(
                token_id=step,
                logits=_fake_logits(),
                hidden_state=_fake_hidden_seq(),
                intent_phase=torch.randn(4),
                input_ids=torch.zeros(10, dtype=torch.long),
            )

        stats = mistral_tracer.summary()
        # Core
        assert "mean_logit_entropy" in stats
        assert "num_tokens" in stats
        # Binding Cache
        assert "mean_intent_drift" in stats
        assert "mean_cache_hit_rate" in stats
        # CTM+
        assert "mean_ctm_phase_coherence" in stats
        assert "ctm_dominant_workload" in stats
        assert "ctm_mode_stability" in stats

    def test_export_roundtrip(self, mistral_tracer):
        mistral_tracer.record_token(
            token_id=0, logits=_fake_logits(),
            hidden_state=_fake_hidden_seq(),
            intent_phase=torch.randn(4),
            input_ids=torch.zeros(10, dtype=torch.long),
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            mistral_tracer.export(path)
            stats = BaselineStatisticsAnalyzer.from_file(path)
            assert "mean_logit_entropy" in stats
        finally:
            os.unlink(path)


# =============================================================================
# BaselineStatisticsAnalyzer (F.2.5)
# =============================================================================

class TestBaselineStatisticsAnalyzer:

    def _make_trace(self, n=50):
        """Build a synthetic trace with all fields."""
        trace = []
        for i in range(n):
            entry = {
                "token_id": i % 20,  # Some repetition
                "logit_entropy": 5.0 + torch.randn(1).item(),
                "token_prob": 0.05 + 0.01 * torch.randn(1).item(),
                "hidden_norm": 10.0 + torch.randn(1).item(),
                "bhava_coherence": 0.5 + 0.2 * torch.randn(1).item(),
                "csr_score": 0.3 + 0.1 * torch.randn(1).item(),
                "vritti_vector": F.softmax(torch.randn(5), dim=-1).tolist(),
                "kosha_alpha": F.softmax(torch.randn(6), dim=-1).tolist(),
                "bliss": max(0.01, min(1.0, 0.7 + 0.2 * torch.randn(1).item())),
                "intent_drift": max(0, 0.1 + 0.05 * torch.randn(1).item()),
                "salience_entropy": 3.0 + torch.randn(1).item(),
                "salience_top_k_ratio": 0.4 + 0.1 * torch.randn(1).item(),
                "binding_cache_hit_rate": 0.9,
                "ctm_phase_coherence": 3.5 + 0.5 * torch.randn(1).item(),
                "ctm_workload_mode": "temporal",
                "ctm_layer_access": [i % 4 + 1 for _ in range(8)],
                "ctm_adaptive_p": 0.5,
                "ctm_simulated_gpu_layers": 4,
                "ctm_simulated_cpu_layers": 4,
                "ctm_prefetch_hits": 0,
            }
            trace.append(entry)
        return trace

    def test_compute_empty(self):
        assert BaselineStatisticsAnalyzer.compute([]) == {}

    def test_compute_all_metrics(self):
        trace = self._make_trace(n=120)
        stats = BaselineStatisticsAnalyzer.compute(trace)

        # Core F.2.5
        assert "mean_logit_entropy" in stats
        assert "std_logit_entropy" in stats
        assert "num_tokens" in stats
        assert stats["num_tokens"] == 120

        # Repetition
        assert "token_repetition_rate_2gram" in stats
        assert "token_repetition_rate_3gram" in stats
        assert "token_repetition_rate_4gram" in stats

        # Drift proxy (n > 100)
        assert "long_form_drift_proxy" in stats
        assert stats["long_form_drift_proxy"] is not None

        # Bliss
        assert "bliss_mean" in stats
        assert "bliss_histogram" in stats

        # CSR
        assert "csr_score_mean" in stats
        assert "csr_score_std" in stats

        # Vritti
        assert "vritti_entropy_mean" in stats
        assert stats["vritti_entropy_mean"] > 0

        # Kosha
        assert "kosha_alpha_entropy_mean" in stats
        assert stats["kosha_alpha_entropy_mean"] > 0

        # Binding Cache
        assert "mean_intent_drift" in stats
        assert "mean_cache_hit_rate" in stats

        # CTM+
        assert "mean_ctm_phase_coherence" in stats
        assert "ctm_optimal_gpu_budget_95pct" in stats
        assert "ctm_mode_stability" in stats

    def test_report_format(self):
        trace = self._make_trace(n=30)
        stats = BaselineStatisticsAnalyzer.compute(trace)
        report = BaselineStatisticsAnalyzer.report(stats)
        assert "Stage 0 Baseline Statistics Report" in report
        assert "Mean logit entropy" in report

    def test_from_file(self):
        trace = self._make_trace(n=10)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            json.dump(trace, f)
            path = f.name
        try:
            stats = BaselineStatisticsAnalyzer.from_file(path)
            assert "mean_logit_entropy" in stats
            assert stats["num_tokens"] == 10
        finally:
            os.unlink(path)

    def test_ngram_repetition_detection(self):
        # All same tokens → high repetition
        trace = [{"token_id": 5, "logit_entropy": 6.0, "token_prob": 0.1,
                  "hidden_norm": 10.0} for _ in range(50)]
        stats = BaselineStatisticsAnalyzer.compute(trace)
        # With all-same tokens, 2-gram repetition should be very high
        assert stats["token_repetition_rate_2gram"] > 0.9

    def test_no_repetition_unique_tokens(self):
        trace = [{"token_id": i, "logit_entropy": 6.0, "token_prob": 0.1,
                  "hidden_norm": 10.0} for i in range(50)]
        stats = BaselineStatisticsAnalyzer.compute(trace)
        assert stats["token_repetition_rate_2gram"] == 0.0


# =============================================================================
# Zero-modification guarantee
# =============================================================================

class TestZeroModificationGuarantee:
    """Verify that the tracer does not alter generation output."""

    def test_tracer_does_not_modify_logits(self, mock_model):
        tracer = GenerationTracer(model=mock_model)
        logits = torch.randn(100)
        logits_copy = logits.clone()
        hidden = torch.randn(64)

        tracer.record_token(token_id=0, logits=logits, hidden_state=hidden)

        # Logits must be unchanged
        assert torch.equal(logits, logits_copy)

    def test_tracer_does_not_modify_hidden(self, mock_model):
        tracer = GenerationTracer(model=mock_model)
        logits = torch.randn(100)
        hidden = torch.randn(64)
        hidden_copy = hidden.clone()

        tracer.record_token(token_id=0, logits=logits, hidden_state=hidden)

        # Hidden state must be unchanged
        assert torch.equal(hidden, hidden_copy)

    def test_mistral_tracer_does_not_modify_inputs(self, mock_model):
        tracer = MistralCGGenerationTracer(
            model=mock_model, binding_cache_top_k=8,
            ctm_num_layers=4, ctm_gpu_budget=2,
        )
        logits = torch.randn(100)
        hidden = torch.randn(10, 64)
        intent = torch.randn(4)
        input_ids = torch.arange(10)

        logits_copy = logits.clone()
        hidden_copy = hidden.clone()
        intent_copy = intent.clone()
        ids_copy = input_ids.clone()

        tracer.record_token(
            token_id=0, logits=logits, hidden_state=hidden,
            intent_phase=intent, input_ids=input_ids,
        )

        assert torch.equal(logits, logits_copy)
        assert torch.equal(hidden, hidden_copy)
        assert torch.equal(intent, intent_copy)
        assert torch.equal(input_ids, ids_copy)
