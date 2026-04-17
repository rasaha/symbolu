"""P3 tests: TCU modes, new ISA / kernel templates presence."""

from pathlib import Path

import pytest

from cohera import TCU, TCUMode


# ----- TCU modes -----

def test_tcu_default_mode_is_frame_ema():
    tcu = TCU()
    assert tcu.mode == TCUMode.FRAME_EMA


def test_tcu_set_mode_kv_cache():
    tcu = TCU()
    tcu.set_mode(TCUMode.KV_CACHE)
    assert tcu.mode == TCUMode.KV_CACHE


def test_tcu_reset_sequence_no_op_under_frame_ema():
    tcu = TCU()
    # Should not raise; no-op in FRAME_EMA mode
    tcu.reset_sequence(stream=None)


def test_tcu_reset_sequence_under_kv_cache():
    tcu = TCU(mode=TCUMode.KV_CACHE)
    tcu.reset_sequence(stream=object())
    assert tcu.mode == TCUMode.KV_CACHE


def test_tcu_get_context_passes_stream_without_error():
    tcu = TCU(mode=TCUMode.KV_CACHE)
    assert tcu.get_context(head=0, stream=object()) is None


def test_tcu_mode_enum_values():
    assert int(TCUMode.FRAME_EMA) == 0
    assert int(TCUMode.KV_CACHE) == 1


# ----- Kernel templates present -----

KERNEL_DIR = Path(__file__).resolve().parent.parent / "examples" / "kernels"


@pytest.mark.parametrize("name", [
    "phase_attention.ckl",
    "mistral_phase_attention.ckl",
    "sovereign_state_projection.ckl",
    "phase_adapter_gate.ckl",
    "ontology_projection.ckl",
])
def test_kernel_template_exists(name: str):
    assert (KERNEL_DIR / name).is_file()


def test_mistral_kernel_declares_rope_and_gqa():
    src = (KERNEL_DIR / "mistral_phase_attention.ckl").read_text()
    assert "apply_rope" in src
    assert "gqa_broadcast" in src
    assert "mistral_phase_attention_fused" in src


def test_sovereign_kernel_declares_component_normalization():
    src = (KERNEL_DIR / "sovereign_state_projection.ckl").read_text()
    # All five component sections and both Kosha modes must be present
    for token in (
        "BHAVA_DIM", "KOSHA_DIM", "VRITTI_DIM", "GUNA_DIM", "RESERVED_DIM",
        "KOSHA_MODE_SIGMOID", "KOSHA_MODE_SOFTMAX",
        "softmax_window", "sigmoidf", "tanhf",
    ):
        assert token in src, f"missing token in sovereign kernel: {token}"


def test_phase_adapter_kernel_declares_gated_residual():
    src = (KERNEL_DIR / "phase_adapter_gate.ckl").read_text()
    assert "CO_GATED_RESIDUAL" in src or "gate_logit" in src
    assert "sigmoidf" in src
    assert "gelu" in src


# ----- ISA reference lists the new opcodes -----

ISA_REF = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "docs" / "hardware" / "COHERA_ISA_REFERENCE.md"
)


@pytest.mark.parametrize("mnemonic", ["PH_ROPE", "ON_PROJECT_SOVEREIGN", "CO_GATED_RESIDUAL"])
def test_isa_reference_contains_new_opcodes(mnemonic: str):
    if not ISA_REF.exists():
        pytest.skip("ISA reference not present in this checkout")
    text = ISA_REF.read_text()
    assert mnemonic in text
