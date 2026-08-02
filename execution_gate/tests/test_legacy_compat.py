"""Legacy compatibility surface tests.

Prove that the ``execution_gate`` namespace is a logic-free compatibility surface over
the canonical ``ugence_model_selection`` package: every product-core submodule and its
public symbols resolve to the SAME objects (identity preserved), so existing
``import execution_gate...`` consumers keep working with identical behavior.
"""
from __future__ import annotations

import importlib

import ugence_model_selection as canon


CORE_SUBMODULES = ("reason_codes", "states", "model", "gate", "policy", "registry")


def test_core_submodules_are_the_same_object():
    for name in CORE_SUBMODULES:
        legacy = importlib.import_module(f"execution_gate.{name}")
        canonical = importlib.import_module(f"ugence_model_selection.{name}")
        assert legacy is canonical, f"execution_gate.{name} is not the canonical module object"


def test_public_types_have_identity():
    from execution_gate.gate import ExecutionGate as LEG_Gate
    from ugence_model_selection.gate import ExecutionGate as CAN_Gate
    assert LEG_Gate is CAN_Gate

    from execution_gate.states import EligibilityDecision as LEG_Dec, EligibilityState as LEG_State
    from ugence_model_selection.states import EligibilityDecision as CAN_Dec, EligibilityState as CAN_State
    assert LEG_Dec is CAN_Dec and LEG_State is CAN_State

    from execution_gate.model import Candidate as LEG_Cand
    from ugence_model_selection.model import Candidate as CAN_Cand
    assert LEG_Cand is CAN_Cand

    from execution_gate.policy import select as LEG_select, Selection as LEG_Sel
    from ugence_model_selection.policy import select as CAN_select, Selection as CAN_Sel
    assert LEG_select is CAN_select and LEG_Sel is CAN_Sel

    from execution_gate.reason_codes import ReasonCode as LEG_RC
    from ugence_model_selection.reason_codes import ReasonCode as CAN_RC
    assert LEG_RC is CAN_RC


def test_deep_import_names_reexported_through_gate():
    # governed_inference_pilot deep-imports these FROM execution_gate.gate.
    from execution_gate.gate import (
        ExecutionGate, Candidate, Request, Signal, Evidence, EvidenceSource, EligibilityState,
    )
    from ugence_model_selection.gate import Candidate as CAN_Cand
    assert Candidate is CAN_Cand


def test_version_matches_canonical():
    import execution_gate
    assert execution_gate.__version__ == canon.__version__
