"""Correction C (v0.1.2) — fingerprint documentation/contract accuracy.

Proves behaviourally that ``outcome_fingerprint`` does NOT bind token counts while
``run_fingerprint`` does, and that the generated invariance-contract artifact states
the same field inventory.
"""

from __future__ import annotations

import json
import pathlib

import ugence_context_minimization
from ugence_context_minimization.api import Context, ContextUnit, minimize_context

from support import KeywordOracle

PROJECT_ROOT = pathlib.Path(ugence_context_minimization.__file__).resolve().parents[2]
ARTIFACTS = PROJECT_ROOT / "artifacts"


def _ctx(token_count):
    return Context(id="c", correlation_id="k", units=(
        ContextUnit(id="crit", text="deploy anchor", source_type="state_fact", token_count=token_count),
        ContextUnit(id="f", text="weekly filler", source_type="log_event", token_count=token_count),
    ))


def test_outcome_fingerprint_excludes_token_counts():
    a = minimize_context(_ctx(1), oracle=KeywordOracle(), target_reduction=0.0, evaluation_time=1.0)
    b = minimize_context(_ctx(99), oracle=KeywordOracle(), target_reduction=0.0, evaluation_time=1.0)
    # same outcome (same ids/mode/status) despite different token counts
    assert a.surviving_ids == b.surviving_ids
    assert a.outcome_fingerprint == b.outcome_fingerprint


def test_run_fingerprint_includes_token_counts():
    a = minimize_context(_ctx(1), oracle=KeywordOracle(), target_reduction=0.0, evaluation_time=1.0)
    b = minimize_context(_ctx(99), oracle=KeywordOracle(), target_reduction=0.0, evaluation_time=1.0)
    assert a.run_fingerprint != b.run_fingerprint


def test_artifact_outcome_excludes_run_includes_token_counts():
    contract = json.loads((ARTIFACTS / "invariance_contract.json").read_text())
    fp = contract["fingerprints"]
    outcome_excludes = set(fp["outcome_fingerprint"]["excludes"])
    run_binds = set(fp["run_fingerprint"]["binds"])
    assert {"original_tokens", "resulting_tokens"} <= outcome_excludes
    assert "unit_resolved_token_count" in run_binds


def test_artifact_outcome_binds_are_the_documented_set():
    contract = json.loads((ARTIFACTS / "invariance_contract.json").read_text())
    binds = set(contract["fingerprints"]["outcome_fingerprint"]["binds"])
    assert binds == {
        "context_id", "mode", "surviving_ids", "removed_structural",
        "removed_extractive", "restored_ids", "protected_ids",
        "equivalence_status", "fell_back", "policy_version",
        "oracle_id", "oracle_contract_version",
    }
