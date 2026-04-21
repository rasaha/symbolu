"""§2.8.3–§2.8.4: CostOrder enum + BCVFLLMConfig defaults."""

from __future__ import annotations

from symbolu_bcvf_llm.core import BCVFLLMConfig, CostOrder


def test_cost_order_enum_values():
    assert CostOrder.ZEROTH.value == 0
    assert CostOrder.FIRST.value == 1
    assert CostOrder.SECOND.value == 2


def test_bcvflllm_config_defaults():
    cfg = BCVFLLMConfig()
    assert cfg.gate_threshold == 0.1
    assert cfg.gate_beta == 200.0
    assert cfg.huber_delta == 0.5
    assert cfg.use_anchor_pairing is False
    assert cfg.anchor_index == 0
    assert cfg.step_l == 1.0
    assert cfg.cost_order == CostOrder.SECOND


def test_bcvflllm_config_weight_vector_none_by_default():
    assert BCVFLLMConfig().weight_vector is None
