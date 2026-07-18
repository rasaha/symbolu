"""Machinery tests for the API control-protocol pilot.

Run: python symbolu_neural/api_control_protocol/tests/test_api.py
"""
from __future__ import annotations

import json

from symbolu_neural.api_control_protocol.packets import ARMS, build, approx_tokens
from symbolu_neural.api_control_protocol.ontology import AXES, SYMBOLU_STATE
from symbolu_neural.api_control_protocol import pilot
from symbolu_neural.api_control_protocol.evaluator import tone_adherence, hit


def test_all_arms_build_for_all_axes():
    for arm in ARMS:
        for axis in AXES:
            msg = build(arm, axis)
            assert isinstance(msg, str)
    assert build("none", "calm") == ""


def test_json_arms_are_valid_json():
    for arm in ["symbolu_json", "hybrid", "sentiment_json", "random_json", "shuffled_symbolu"]:
        msg = build(arm, "calm")
        block = msg[msg.index("{"): msg.rindex("}") + 1]
        obj = json.loads(block)
        assert isinstance(obj, dict)


def test_shuffled_differs_from_real_state():
    real = SYMBOLU_STATE["calm"]
    msg = build("shuffled_symbolu", "calm")
    block = msg[msg.index("{"): msg.rindex("}") + 1]
    obj = json.loads(block)["symbolu_state"]
    # at least one ontology field corrupted vs the real calm state
    assert any(obj[k] != real[k] for k in real)


def test_json_costs_more_tokens_than_nl():
    nl = approx_tokens(build("nl_instruction", "calm"))
    hy = approx_tokens(build("hybrid", "calm"))
    assert hy > nl  # JSON verbosity is a real cost


def test_adherence_metric_bounds():
    assert tone_adherence("a calm gentle grounded reply", "calm") > 0
    assert hit("a calm gentle grounded reply", "calm") == 1
    assert hit("a calm gentle grounded reply", "heavy") == 0


def test_pilot_runs_mock_end_to_end():
    r = pilot.run(backend="mock")
    assert r["is_real"] is False
    for arm in ARMS:
        assert "hit_rate" in r["arms"][arm]
        assert r["arms"][arm]["ctrl_tokens"] >= 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
