"""Tests for Track B — offline real-trace replay.

Covers the adapters (parse real Azure fixture slices + schema fixtures for the
PENDING_DATA sources), the TraceSeries contract, the EfficiencyObserver, the
TraceReplayHarness, and the ReplayPrometheusClient driving the EXISTING
Stage-2/3 pipeline.

All inputs are the small committed fixtures under data/cloud_traces/fixtures/ —
no network, no full traces.
"""

import os

import pytest

from cloud_controller.replay.adapters import (
    AdapterStatus,
    AzureLLMInferenceAdapter,
    AzureVMNoiseAdapter,
    AlibabaMicroservicesAdapter,
    GoogleBorgAdapter,
    TraceSeries,
)
from cloud_controller.replay.efficiency_observer import EfficiencyObserver
from cloud_controller.replay.harness import TraceReplayHarness
from cloud_controller.replay.replay_source import ReplayPrometheusClient
from cloud_controller.observability.efficiency_estimator import EfficiencyState

FIX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cloud_traces", "fixtures",
)

CONV = os.path.join(FIX, "azure_llm_conv_sample.csv")
CODE = os.path.join(FIX, "azure_llm_code_sample.csv")
VMN = os.path.join(FIX, "azure_vm_noise_sample.csv")
ALIBABA = os.path.join(FIX, "alibaba_msresource_SCHEMA_FIXTURE.csv")
GOOGLE = os.path.join(FIX, "google_borg_task_usage_SCHEMA_FIXTURE.csv")

_METRIC_KEYS = {"cpu", "memory", "latency_p99", "error_rate", "queue_depth"}


# ----------------------- Adapters -----------------------

class TestAzureLLMAdapter:
    def test_parses_real_fixture(self):
        s = AzureLLMInferenceAdapter().load(CONV, cycle_seconds=15.0)
        assert s.status is AdapterStatus.EXECUTED
        assert s.n_cycles > 0
        assert s.meta["n_requests"] == 800  # the committed slice
        assert s.license == "CC-BY-4.0"

    def test_demand_in_unit_interval(self):
        s = AzureLLMInferenceAdapter().load(CONV)
        assert all(0.0 <= d <= 1.0 for d in s.demand)
        assert max(s.demand) > 0.0  # some real load

    def test_count_vs_tokens_metric(self):
        s_tok = AzureLLMInferenceAdapter().load(CONV, load_metric="tokens")
        s_cnt = AzureLLMInferenceAdapter().load(CONV, load_metric="count")
        # Both valid demand series; token-weighting generally differs from counts.
        assert len(s_tok.demand) == len(s_cnt.demand)
        assert s_tok.demand != s_cnt.demand

    def test_metrics_series_has_canonical_keys(self):
        s = AzureLLMInferenceAdapter().load(CONV)
        ms = s.to_metrics_series()
        assert len(ms) == s.n_cycles
        assert _METRIC_KEYS.issubset(set(ms[0].keys()))

    def test_max_rows_caps_parse(self):
        s = AzureLLMInferenceAdapter().load(CONV, max_rows=100)
        assert s.meta["n_requests"] == 100

    def test_missing_file_raises(self):
        with pytest.raises((FileNotFoundError, OSError)):
            AzureLLMInferenceAdapter().load(os.path.join(FIX, "nope.csv"))


class TestAzureVMNoiseAdapter:
    def test_parses_real_fixture(self):
        s = AzureVMNoiseAdapter().load(VMN)
        assert s.status is AdapterStatus.EXECUTED
        assert s.n_cycles > 0
        assert all(0.0 <= d <= 1.0 for d in s.demand)

    def test_invert_flips_orientation(self):
        a = AzureVMNoiseAdapter().load(VMN, invert=False)
        b = AzureVMNoiseAdapter().load(VMN, invert=True)
        # Inversion changes the series (unless degenerate constant).
        assert a.demand != b.demand


class TestPendingDataAdapters:
    def test_alibaba_schema_fixture_parses(self):
        s = AlibabaMicroservicesAdapter().load(ALIBABA, cycle_seconds=15.0)
        assert s.status is AdapterStatus.PENDING_DATA
        assert s.n_cycles > 0
        assert all(0.0 <= d <= 1.0 for d in s.demand)
        assert "PENDING_DATA" in s.meta["note"]

    def test_google_schema_fixture_parses(self):
        s = GoogleBorgAdapter().load(GOOGLE, cycle_seconds=15.0)
        assert s.status is AdapterStatus.PENDING_DATA
        assert s.n_cycles > 0
        assert all(0.0 <= d <= 1.0 for d in s.demand)


class TestTraceSeries:
    def test_demand_clamped(self):
        s = TraceSeries(
            name="t", source="x", license="y", status=AdapterStatus.EXECUTED,
            cycle_seconds=15.0, demand=[-0.5, 0.3, 2.0],
        )
        assert s.demand == [0.0, 0.3, 1.0]

    def test_supplied_metrics_passthrough(self):
        m = [{"cpu": 0.5, "memory": 0.5, "latency_p99": 0.5, "error_rate": 0.0, "queue_depth": 0.5}]
        s = TraceSeries("t", "x", "y", AdapterStatus.EXECUTED, 15.0, [0.5], metrics=m)
        assert s.to_metrics_series() is m


# ----------------------- EfficiencyObserver -----------------------

class TestEfficiencyObserver:
    def test_guard_dormant_below_threshold(self):
        """Guard never blocks below high_replica_threshold (read-only safety)."""
        obs = EfficiencyObserver(futility_window=5, high_replica_threshold=20)
        metrics = {"cpu": 0.9, "memory": 0.7, "latency_p99": 0.8, "error_rate": 0.2, "queue_depth": 0.8}
        for _ in range(50):
            o = obs.observe(metrics, replicas=10, raw_delta=2, optimal_replicas=5)
            assert o.guarded_delta == o.raw_delta  # never capped at 10 < 20 replicas
        assert obs.blocked_events == 0

    def test_guard_can_block_in_futile_regime(self):
        """A growing fleet with demand-bound metrics is the real futile regime:
        cpu-per-replica collapses vs the low-replica baseline (over-provisioning
        waste → NOT_HELPING), and once replicas pass 20 with a sustained streak
        the guard caps the scale-out. Mirrors the EdgeCaseHarness loop order."""
        obs = EfficiencyObserver(futility_window=5, high_replica_threshold=20)
        # Latency/error stay high regardless of replicas (demand-bound) so scaling
        # never improves them; cpu absolute stays high so per-replica util falls.
        metrics = {"cpu": 0.95, "memory": 0.7, "latency_p99": 0.9, "error_rate": 0.3, "queue_depth": 0.9}
        replicas = 5
        blocked_any = False
        for _ in range(60):
            o = obs.observe(metrics, replicas=replicas, raw_delta=2, optimal_replicas=5)
            if o.blocked:
                blocked_any = True
                assert o.guarded_delta == 0
            # Apply the (possibly capped) delta, as Track B / the harness does.
            replicas = max(1, replicas + o.guarded_delta)
        assert blocked_any
        assert obs.blocked_events > 0

    def test_negative_delta_passes_through(self):
        """The guard never touches scale-in."""
        obs = EfficiencyObserver(high_replica_threshold=20)
        metrics = {"cpu": 0.1, "memory": 0.2, "latency_p99": 0.1, "error_rate": 0.0, "queue_depth": 0.1}
        for _ in range(30):
            o = obs.observe(metrics, replicas=30, raw_delta=-2, optimal_replicas=5)
            assert o.guarded_delta == -2


# ----------------------- Harness -----------------------

class TestReplayHarness:
    def test_runs_and_scores(self):
        s = AzureLLMInferenceAdapter().load(CONV)
        res = TraceReplayHarness(base_replicas=5).run(s)
        assert res.guard_on is not None and res.guard_off is not None
        assert res.n_cycles == s.n_cycles
        assert res.guard_on.score.total_cycles == s.n_cycles
        assert res.status == "executed"

    def test_guard_on_never_more_blocked_than_scale_outs(self):
        s = AzureLLMInferenceAdapter().load(CONV)
        res = TraceReplayHarness(base_replicas=5).run(s)
        assert 0 <= res.blocked_scale_outs <= max(1, res.total_scale_outs)

    def test_deterministic(self):
        s = AzureLLMInferenceAdapter().load(CONV)
        r1 = TraceReplayHarness(base_replicas=5).run(s)
        r2 = TraceReplayHarness(base_replicas=5).run(s)
        assert r1.guard_on.replica_cycles == r2.guard_on.replica_cycles
        assert r1.blocked_scale_outs == r2.blocked_scale_outs

    def test_cost_saved_usd_basis(self):
        s = AzureLLMInferenceAdapter().load(CONV)
        res = TraceReplayHarness(base_replicas=5).run(s)
        usd = res.cost_saved_usd(0.03, 15.0)
        # $ saved is replica-cycles-saved * (15/60) min * $0.03; sign follows savings.
        expected = res.replica_cycles_saved * (15.0 / 60.0) * 0.03
        assert abs(usd - expected) < 1e-9


# ----------------------- ReplayPrometheusClient drives the real pipeline -----------------------

class TestReplayPrometheusClient:
    def test_duck_types_prometheus_client(self):
        s = AzureLLMInferenceAdapter().load(CONV)
        c = ReplayPrometheusClient(s, base_replicas=5)
        m = c.query_metrics()
        assert _METRIC_KEYS.issubset(set(m.keys()))
        k = c.query_k8s_state()
        assert {"current_replicas", "desired_replicas", "pod_restarts"}.issubset(set(k.keys()))
        assert c.health_check() is True

    def test_drives_existing_signal_pipeline(self):
        """A real SignalPipeline ingests replayed trace data end-to-end."""
        from cloud_controller.signals.pipeline import SignalPipeline, PipelineConfig
        s = AzureLLMInferenceAdapter().load(CONV)
        pipeline = SignalPipeline(PipelineConfig())
        pipeline.prometheus = ReplayPrometheusClient(s, base_replicas=5)
        cycles = 0
        for _ in range(min(20, s.n_cycles)):
            res = pipeline.poll_once()
            if res is not None:
                cycles += 1
                assert res.action is not None
        assert cycles > 0

    def test_drives_existing_shadow_runner(self):
        """The full Stage-3 ShadowRunner (pipeline+HPA+divergence) runs on a trace."""
        from cloud_controller.shadow.runner import ShadowRunner, ShadowConfig
        s = AzureLLMInferenceAdapter().load(CONV)
        runner = ShadowRunner(ShadowConfig())
        replay = ReplayPrometheusClient(s, base_replicas=5)
        runner.pipeline.prometheus = replay
        runner.hpa_watcher.prometheus = replay
        steps = 0
        for _ in range(min(15, s.n_cycles)):
            r = runner.step()
            if r is not None:
                steps += 1
        assert steps > 0
        # The divergence tracker accumulated decisions from real trace data.
        assert len(runner.divergence_tracker.records) > 0
