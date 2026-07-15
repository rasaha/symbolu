"""Backward-compatibility (deliverable 16): V0.1 and V0.2 preserved by V0.3.

Frozen fingerprints unchanged; V0.2 base digests unchanged; V0.3 dispatches the
Kubernetes profiles to the frozen V0.2 code (identical digest).
"""
from __future__ import annotations

import hashlib

from cer_v0_3 import envelope as e3
from cer_v0_3.conformance import cross_domain

# frozen fingerprints (CER_V0_2_BASELINE_FREEZE.md)
FROZEN = {
    "cer_v0_1/conformance/vectors.json": "3ec7f36d741f6302",
    "cer_v0_2/conformance/vectors.json": "3dc9f372c47121bd",
    "cer_v0_2/envelope.py": "c04bd2560c0fd6aa",
    "cer_v0_2/profiles/scale.py": "05e7e26c6ab6fea0",
    "cer_v0_2/profiles/rollout.py": "306266320c2d7b49",
    "cyber_security/action_gate_reference/action_gate_ref/projection.py": "ce458712e7643a27",
    "cyber_security/action_gate_reference/action_gate_ref/policy.py": "a2f7c5b51f5fa907",
    "cyber_security/action_gate_reference/action_gate_ref/schema.py": "0307acdb4e05d6ed",
    "symbolu_robotics/autonomous_control_plane/cloud/composition.py": "b810e2f0c3bc0e28",
    "symbolu_robotics/autonomous_control_plane/cloud/outcomes.py": "21fd7283100eff66",
}

V2_SCALE = "07f7a6aaf20a55a8f03fc31f232420774c7361264cabf66b3a2ac74ffd3f7b51"
V2_ROLLOUT = "72ddae264f4bb757fdeb137bbea0d44dfb36bf60161571447a82be0695c770e3"


def test_frozen_fingerprints_unchanged():
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for rel, exp in FROZEN.items():
        h = hashlib.sha256(open(os.path.join(root, rel), "rb").read()).hexdigest()[:16]
        assert h == exp, f"{rel} changed: {h} != {exp}"


def test_v3_dispatches_k8s_to_frozen_v2():
    # V0.3 envelope produces the same scale digest as frozen V0.2
    scale = cross_domain._v2_scale_cer()
    assert e3.action_digest(scale) == V2_SCALE


def test_regression_digests_unchanged():
    r = cross_domain.run()
    assert r["regression_scale_unchanged"] is True
    assert r["regression_rollout_unchanged"] is True
