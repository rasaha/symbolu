"""Legacy import compatibility: the ``cloud_controller`` and ``symbolu.cloud_controller``
namespaces resolve to the SAME objects as the canonical package, and produce identical
behavior. These namespaces are a monorepo-only compatibility surface; when they are not
importable (e.g. a pure wheel install), the tests skip.
"""

from __future__ import annotations

import pytest

import ugence_cloud_scaling_controller as canon


def _try_import(name):
    try:
        __import__(name)
        import importlib
        return importlib.import_module(name)
    except ImportError:
        pytest.skip(f"legacy namespace {name!r} not importable (wheel-only environment)")


def test_legacy_cloud_controller_object_identity():
    _try_import("cloud_controller")
    from cloud_controller.controller import Controller as Legacy
    assert Legacy is canon.controller.Controller
    from cloud_controller.config import InfraControllerConfig as LegacyCfg
    assert LegacyCfg is canon.config.InfraControllerConfig


def test_symbolu_cloud_controller_object_identity():
    _try_import("symbolu.cloud_controller")
    from symbolu.cloud_controller.controller import Controller as SymLegacy
    assert SymLegacy is canon.controller.Controller


def test_deep_submodule_identity_across_namespaces():
    _try_import("cloud_controller")
    _try_import("symbolu.cloud_controller")
    from cloud_controller.core.coherence import CoherenceModel as A
    from symbolu.cloud_controller.core.coherence import CoherenceModel as B
    from ugence_cloud_scaling_controller.core.coherence import CoherenceModel as C
    assert A is B is C


def test_replay_subpackage_reachable_via_legacy():
    _try_import("cloud_controller")
    import cloud_controller.replay.harness as legacy_harness
    import ugence_cloud_scaling_controller.replay.harness as canon_harness
    assert legacy_harness is canon_harness


def test_behavioral_parity_through_legacy_import():
    _try_import("cloud_controller")
    from cloud_controller.controller import Controller as Legacy
    from ugence_cloud_scaling_controller.controller import Controller as Canon

    steps = [{"cpu": 0.9, "memory": 0.85, "latency_p99": 0.8}] * 15

    def run(cls):
        c = cls()
        out = []
        for m in steps:
            r = c.step(metrics=dict(m), current_replicas=5, phase="peak")
            out.append((r.recommendation, r.replica_delta, round(r.action_score, 10),
                        round(r.pressure, 10)))
        return out

    # Same class object => identical behavior; assert explicitly anyway.
    assert run(Legacy) == run(Canon)
