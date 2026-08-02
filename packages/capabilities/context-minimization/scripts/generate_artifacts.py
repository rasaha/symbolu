#!/usr/bin/env python3
"""Derive the package's machine-readable artifacts FROM the implementation.

Writes (under packages/.../context-minimization/artifacts/):
    public_api.json               — the curated api.__all__ surface + versions
    reason_codes.json             — the curated reason-code vocabulary
    minimization_result_schema.json — the MinimizationResult field schema
    invariance_contract.json      — the neutral oracle / equivalence contract
    acceptance_scenarios.json     — enumerated fail-closed / success scenarios

Run:  python packages/capabilities/context-minimization/scripts/generate_artifacts.py
This is idempotent; commit the outputs. ``tests/packaging/test_public_api.py`` and
``test_reason_codes.py`` assert these stay in sync with the code.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ugence_context_minimization import api, reasons  # noqa: E402
from ugence_context_minimization.models import MinimizationResult  # noqa: E402

ART = ROOT / "artifacts"


def _type_name(t: object) -> str:
    return getattr(t, "__name__", str(t))


def public_api() -> dict:
    return {
        "distribution": "ugence-context-minimization",
        "namespace": "ugence_context_minimization",
        "version": api.__version__,
        "contract_version": api.CONTRACT_VERSION,
        "module": "ugence_context_minimization.api",
        "exports": sorted(api.__all__),
    }


def reason_codes() -> dict:
    return {
        "contract_version": api.CONTRACT_VERSION,
        "codes": list(reasons.ALL_REASON_CODES),
    }


def result_schema() -> dict:
    fields = []
    for f in dataclasses.fields(MinimizationResult):
        fields.append({"name": f.name, "type": _type_name(f.type)})
    return {
        "contract_version": api.CONTRACT_VERSION,
        "type": "MinimizationResult",
        "fields": fields,
        "computed_properties": ["achieved_reduction", "equivalence_verified"],
    }


def invariance_contract() -> dict:
    return {
        "contract_version": api.CONTRACT_VERSION,
        "oracle_protocol": "InvarianceOracle",
        "method": "evaluate(context, *, evaluation_time=None) -> OracleEvaluation",
        "equivalence_rule": (
            "Two contexts are equivalent iff their OracleEvaluation.equivalence_key "
            "values are equal. The minimizer treats the key as OPAQUE and never "
            "interprets it. Invariance is defined ENTIRELY by the supplied oracle; "
            "the package creates no authority."
        ),
        "oracle_evaluation_fields": [
            "equivalence_key", "oracle_id", "contract_version", "evaluation_ref",
            "correlation_id", "valid_until", "reason_codes", "metadata",
        ],
        "fail_closed_conditions": [
            "missing oracle (oracle mode) -> OracleRequiredError (raised)",
            "oracle raises -> full fallback (ORACLE_RAISED)",
            "malformed / empty-key result -> full fallback (ORACLE_RESULT_MALFORMED)",
            "oracle_id / contract_version drift between calls -> full fallback (ORACLE_CONTRACT_MISMATCH)",
            "evaluation_time > valid_until -> full fallback (ORACLE_EVALUATION_EXPIRED)",
            "correlation_id mismatch -> full fallback (CORRELATION_MISMATCH)",
            "changed key -> restore necessary spans; else full fallback",
            "unresolved joint effect -> full fallback (JOINT_EFFECT_FALLBACK)",
            "protection provider fails -> protect everything (PROTECTION_PROVIDER_FAILED)",
        ],
        "guarantees_boundary": {
            "is": ["extractive omission", "equivalence relative to supplied oracle",
                   "structurally lossless dedup (structural mode)"],
            "is_not": ["authorization", "context admission", "rewrite/paraphrase/summarize",
                       "retrieval", "model reasoning", "live-enterprise validation"],
        },
    }


def acceptance_scenarios() -> dict:
    return {
        "contract_version": api.CONTRACT_VERSION,
        "scenarios": [
            {"id": "structural_exact_duplicate", "mode": "STRUCTURAL",
             "expect": "unprotected exact duplicate removed, representative kept"},
            {"id": "structural_protected_duplicate", "mode": "STRUCTURAL",
             "expect": "protected duplicate retained"},
            {"id": "oracle_invariant_removal", "mode": "ORACLE_VERIFIED",
             "expect": "VERIFIED, filler removed"},
            {"id": "oracle_restore", "mode": "ORACLE_VERIFIED",
             "expect": "RESTORED, necessary span recovered"},
            {"id": "oracle_joint_fallback", "mode": "ORACLE_VERIFIED",
             "expect": "FALLBACK (JOINT_EFFECT_FALLBACK)"},
            {"id": "oracle_exception", "mode": "ORACLE_VERIFIED",
             "expect": "FALLBACK (ORACLE_RAISED)"},
            {"id": "oracle_expired", "mode": "ORACLE_VERIFIED",
             "expect": "FALLBACK (ORACLE_EVALUATION_EXPIRED)"},
            {"id": "oracle_correlation_mismatch", "mode": "ORACLE_VERIFIED",
             "expect": "FALLBACK (CORRELATION_MISMATCH)"},
            {"id": "protection_uncertain_retained", "mode": "ORACLE_VERIFIED",
             "expect": "uncertain unit retained"},
            {"id": "budget_unreachable", "mode": "ORACLE_VERIFIED",
             "expect": "safest achievable + BUDGET_UNREACHABLE_WITHOUT_PROTECTED"},
        ],
    }


def main() -> int:
    ART.mkdir(exist_ok=True)
    outputs = {
        "public_api.json": public_api(),
        "reason_codes.json": reason_codes(),
        "minimization_result_schema.json": result_schema(),
        "invariance_contract.json": invariance_contract(),
        "acceptance_scenarios.json": acceptance_scenarios(),
    }
    for name, data in outputs.items():
        (ART / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print(f"wrote artifacts/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
