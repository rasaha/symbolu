"""
test_cg_checkpoint.py — --cg-state-dict load + verify (torch-free).

Covers the verification core (unwrap / verify / fail-closed) and the load_cg_adapter
orchestration via injected factories — no torch, no model. The real wrapper construction
is torch-gated (one skip-if-torch-present check). NO success claim.
"""

from __future__ import annotations

import importlib.util
import logging

import numpy as np
import pytest

from experiments.signal_gov.cg_checkpoint import (
    CGCheckpointError,
    companion_aux_path,
    load_cg_adapter,
    prepare_cg_state_dict,
    unwrap_state_dict,
    verify_cg_state_dict,
)


# ----- fake state dicts (numpy tensors; no torch) -----

def _trained_sd():
    return {
        "backbone.model.layers.0.self_attn.q_proj.weight": np.ones((4, 4)),
        "state_projector.net.0.weight": np.ones((8, 8)),
        "intent_projector.proj.weight": np.ones((4, 4)),
        "phase_adapter.0.weight": np.ones((16, 8)),          # input linear
        "phase_adapter.2.weight": np.full((4096, 16), 0.05), # output linear (trained -> nonzero)
    }


def _vanilla_sd():
    return {"model.embed_tokens.weight": np.ones((10, 4)),
            "backbone.norm.weight": np.ones(4)}


def _untrained_sd():
    d = _trained_sd()
    d["phase_adapter.2.weight"] = np.zeros((4096, 16))       # zero-init -> untrained
    return d


class _FakeWrapper:
    def __init__(self):
        self.loaded = []
        self.evaled = False

    def load_state_dict(self, sd, strict=True):
        self.loaded.append((sd, strict))
        return ([], [])

    def eval(self):
        self.evaled = True
        return self


class _FakeAdapter:
    def __init__(self, wrapper):
        self.wrapper = wrapper
        self.IS_STUB = False


# ----- unwrap -----

@pytest.mark.parametrize("key", ["model_state_dict", "model", "state_dict"])
def test_unwrap_wrapped(key):
    inner = _trained_sd()
    assert unwrap_state_dict({key: inner, "step": 5}) is inner


def test_unwrap_raw():
    raw = _trained_sd()
    assert unwrap_state_dict(raw) is raw


def test_unwrap_bad_type():
    with pytest.raises(CGCheckpointError):
        unwrap_state_dict(["not", "a", "dict"])


# ----- verify -----

def test_verify_trained():
    v = verify_cg_state_dict(_trained_sd())
    assert v.has_cg_keys and v.is_trained
    assert v.phase_output_key == "phase_adapter.2.weight"
    assert v.phase_output_norm > 0


def test_verify_vanilla():
    v = verify_cg_state_dict(_vanilla_sd())
    assert not v.has_cg_keys and not v.is_trained


def test_verify_untrained_zero_phase():
    v = verify_cg_state_dict(_untrained_sd())
    assert v.has_cg_keys and not v.is_trained
    assert v.phase_output_norm == pytest.approx(0.0)


# ----- companion aux path -----

def test_companion_aux_path():
    assert str(companion_aux_path("checkpoints_unified/best_model.pt")) == \
        "checkpoints_unified/best_model.pt".replace("best_model.pt", "best_aux.pt")
    assert companion_aux_path("a/checkpoint_model.pt").name == "checkpoint_aux.pt"
    assert companion_aux_path("a/final.pt") is None


# ----- prepare (fail-closed gate) -----

def test_prepare_passes_trained():
    sd, v = prepare_cg_state_dict({"model_state_dict": _trained_sd()})
    assert v.is_trained and "state_projector.net.0.weight" in sd


def test_prepare_fails_vanilla():
    with pytest.raises(CGCheckpointError, match="vanilla"):
        prepare_cg_state_dict(_vanilla_sd())


def test_prepare_fails_untrained():
    with pytest.raises(CGCheckpointError, match="UNTRAINED"):
        prepare_cg_state_dict(_untrained_sd())


def test_prepare_allow_untrained_bypasses(caplog):
    with caplog.at_level(logging.WARNING):
        sd, v = prepare_cg_state_dict(_vanilla_sd(), allow_untrained=True)
    assert not v.is_trained
    assert "allow-untrained-cg-head" in caplog.text


# ----- load_cg_adapter orchestration (injected factories; no torch) -----

def test_load_cg_adapter_trained_path():
    w = _FakeWrapper()
    captured = {}

    def wf(base, q, dm):
        captured["wf_args"] = (base, q, dm)
        return w

    adapter = load_cg_adapter(
        base_model="mistralai/Mistral-7B-v0.3", state_dict_path="ckpt/best_model.pt",
        state_dict_loader=lambda p: {"model_state_dict": _trained_sd()},
        wrapper_factory=wf, adapter_factory=_FakeAdapter)
    assert isinstance(adapter, _FakeAdapter)
    assert adapter.wrapper is w
    assert w.evaled and w.loaded           # state-dict loaded into wrapper
    assert captured["wf_args"] == ("mistralai/Mistral-7B-v0.3", None, "auto")


def test_load_cg_adapter_vanilla_fails_before_building_wrapper():
    called = {"wf": False}

    def wf(*a):
        called["wf"] = True
        return _FakeWrapper()

    with pytest.raises(CGCheckpointError):
        load_cg_adapter(base_model="b", state_dict_path="x.pt",
                        state_dict_loader=lambda p: _vanilla_sd(),
                        wrapper_factory=wf, adapter_factory=_FakeAdapter)
    assert called["wf"] is False           # never constructs the model on a vanilla ckpt


def test_load_cg_adapter_untrained_fails():
    with pytest.raises(CGCheckpointError, match="UNTRAINED"):
        load_cg_adapter(base_model="b", state_dict_path="x.pt",
                        state_dict_loader=lambda p: _untrained_sd(),
                        wrapper_factory=lambda *a: _FakeWrapper(),
                        adapter_factory=_FakeAdapter)


def test_load_cg_adapter_allow_untrained_bypasses():
    adapter = load_cg_adapter(base_model="b", state_dict_path="x.pt", allow_untrained=True,
                              state_dict_loader=lambda p: _vanilla_sd(),
                              wrapper_factory=lambda *a: _FakeWrapper(),
                              adapter_factory=_FakeAdapter)
    assert isinstance(adapter, _FakeAdapter)


@pytest.mark.skipif(importlib.util.find_spec("torch") is not None,
                    reason="torch present: skip the default-loader no-torch check")
def test_load_cg_adapter_default_loader_requires_torch():
    with pytest.raises(ImportError, match="torch"):
        load_cg_adapter(base_model="b", state_dict_path="/no/such/best_model.pt")
