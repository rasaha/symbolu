"""Regression: Gemma-2 must load with eager attention, and ONLY Gemma-2 does — the
deployment-layer fix must not touch any other family's loading path, and must not alter
the frozen client bytes / frozen fingerprint.

This is a runtime/deployment defect fix (Gemma-2 needs attn_implementation='eager' or
every generation raises). It changes no prompts, tasks, budgets, or scoring, and it
lives entirely in the non-frozen runner (run_benchmark.py), so the frozen fingerprint is
byte-identical to the Qwen2.5-7B primary run for every model, Gemma included.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_RUNPOD = pathlib.Path(__file__).resolve().parents[1] / "runpod"
if str(_RUNPOD) not in sys.path:
    sys.path.insert(0, str(_RUNPOD))

import runpod_common as RC          # noqa: E402
import run_benchmark as RB          # noqa: E402


def test_only_gemma2_needs_eager():
    assert RB._needs_eager_attention("google/gemma-2-9b-it") is True
    assert RB._needs_eager_attention("google/gemma-2-27b-it") is True
    assert RB._needs_eager_attention("GOOGLE/GEMMA-2-9B-IT") is True   # case-insensitive
    # every other family in the cross-model set loads unchanged
    assert RB._needs_eager_attention("Qwen/Qwen2.5-7B-Instruct") is False
    assert RB._needs_eager_attention("Qwen/Qwen2.5-14B-Instruct") is False
    assert RB._needs_eager_attention("meta-llama/Llama-3.1-8B-Instruct") is False
    assert RB._needs_eager_attention("mistralai/Mistral-7B-Instruct-v0.3") is False
    assert RB._needs_eager_attention("google/gemma-7b-it") is False    # gemma-1, not gemma-2
    assert RB._needs_eager_attention("") is False
    assert RB._needs_eager_attention(None) is False


def test_gemma_fix_does_not_change_frozen_fingerprint():
    # The Gemma deployment fix lives in run_benchmark.py (not a frozen file). The frozen
    # benchmark surface — including the model-execution adapter llm_client.py — is unchanged.
    assert RC.frozen_fingerprint()["fingerprint"] == \
        "sha256:ac4e069262ec663de0983c5461c64ad57bb8d62db326e6a6f1701f0628381eac"
    assert "llm_client.py" in RC._FROZEN_FILES   # still part of the frozen fingerprint


def test_gemma_patch_injects_eager_and_restores(monkeypatch):
    """build_client wraps from_pretrained only transiently: eager is injected while the
    Gemma client loads, and the original from_pretrained is restored afterwards so a
    later non-Gemma load is clean. Simulated without real weights."""
    import types
    transformers = pytest.importorskip("transformers")

    seen = {}

    def _probe_from_pretrained(*a, **k):
        return k.get("attn_implementation", "default")

    monkeypatch.setattr(transformers.AutoModelForCausalLM, "from_pretrained",
                        _probe_from_pretrained)

    class _FakeClient:
        is_real = True

        def __init__(self, *a, **k):
            # what attn_implementation is in force at load time?
            seen["attn"] = transformers.AutoModelForCausalLM.from_pretrained("x")

    fake_mod = types.SimpleNamespace(TransformersLLMClient=_FakeClient,
                                     MockReaderClient=_FakeClient)
    monkeypatch.setitem(sys.modules, "actiongate_context_ablation.llm_client", fake_mod)

    cfg = {"allow_mock": False, "model_id": "google/gemma-2-9b-it", "model_dir": "/nonexistent",
           "max_new_tokens": 8, "dtype": "bf16", "device": "cpu"}
    RB.build_client(cfg)
    assert seen["attn"] == "eager"            # eager injected during Gemma load
    # original restored afterwards (probe returns default when not wrapped)
    assert transformers.AutoModelForCausalLM.from_pretrained("x") == "default"
