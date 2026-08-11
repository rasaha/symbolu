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
from ugence_context_minimization import token_accounting as ta  # noqa: E402

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
            "malformed result / non-string key / empty oracle identity -> full fallback (ORACLE_RESULT_MALFORMED)",
            "oracle_id / contract_version drift between calls -> full fallback (ORACLE_CONTRACT_MISMATCH)",
            "evaluation_time >= valid_until (INCLUSIVE) -> full fallback (ORACLE_EVALUATION_EXPIRED)",
            "valid_until supplied but no evaluation_time -> full fallback (ORACLE_EVALUATION_TIME_REQUIRED)",
            "context has correlation but evaluation omits it -> full fallback (ORACLE_CORRELATION_MISSING)",
            "context correlation != evaluation correlation -> full fallback (ORACLE_CORRELATION_MISMATCH)",
            "changed key -> restore necessary spans; else full fallback",
            "unresolved joint effect -> full fallback (JOINT_EFFECT_FALLBACK)",
            "protection provider fails -> protect everything (PROTECTION_PROVIDER_FAILED)",
        ],
        "correlation_binding": (
            "When the context carries a non-empty correlation_id, every usable oracle "
            "evaluation (baseline, reduced, per-unit restoration, final restored) MUST "
            "carry the identical id. Missing and mismatched are distinct, non-collapsed "
            "reason codes."
        ),
        "expiry_semantics": (
            "Expiry is INCLUSIVE at the exact valid_until instant. A validity horizon "
            "with no evaluation_time fails closed; the core never reads a wall clock — "
            "the caller controls evaluation_time for deterministic replay."
        ),
        "fingerprints": {
            "outcome_fingerprint": {
                "summary": "digest of the selected outcome only (byte-identical to the v0.1.0 field)",
                "domain": "ugence-context-minimization/result/1",
                "binds": [
                    "context_id", "mode", "surviving_ids", "removed_structural",
                    "removed_extractive", "restored_ids", "protected_ids",
                    "equivalence_status", "fell_back", "policy_version",
                    "oracle_id", "oracle_contract_version",
                ],
                "excludes": [
                    "original_tokens", "resulting_tokens", "unit_text_or_content_digest",
                    "requested_reduction", "requested_token_budget", "evaluation_time",
                    "reason_codes", "policy_fingerprint", "oracle_evaluation_ref",
                    "oracle_valid_until", "correlation_id", "equivalence_key",
                ],
            },
            "run_fingerprint": {
                "summary": "complete run identity: request + policy + oracle + outcome",
                "domain": "ugence-context-minimization/run/2",
                "binds": [
                    "context_contract_version", "context_id", "correlation_id",
                    "unit_id", "unit_source_type", "unit_content_digest",
                    "unit_resolved_token_count", "unit_protected", "unit_redundancy_set",
                    "requested_reduction", "requested_token_budget", "mode",
                    "evaluation_time", "policy_version", "policy_fingerprint",
                    "token_counter_identity", "oracle_id", "oracle_contract_version",
                    "oracle_evaluation_ref", "oracle_valid_until", "oracle_correlation_id",
                    "surviving_ids", "removed_structural", "removed_extractive",
                    "restored_ids", "protected_ids", "original_tokens", "resulting_tokens",
                    "equivalence_status", "fell_back", "reason_codes",
                ],
                "excludes": ["credentials", "secrets", "equivalence_key", "raw_metadata_objects"],
            },
            "fingerprint": "DEPRECATED alias of outcome_fingerprint",
        },
        "timestamp_contract": (
            "evaluation_time (caller) and valid_until (oracle) must be finite real "
            "numbers, not bool/NaN/inf/str. Malformed caller evaluation_time raises "
            "InvalidRequestError before the oracle is called; malformed oracle "
            "valid_until fails closed with ORACLE_RESULT_MALFORMED."
        ),
        "token_count_contract": (
            "Caller ContextUnit.token_count and injected TokenCounter.count() results "
            "must be non-negative ints (never bool/float/NaN/inf/str); malformed values "
            "raise InvalidUnitError."
        ),
        "metadata_contract": (
            "Metadata keys must be str; values must be JSON scalars (str / finite number "
            "/ bool / None). Non-scalar values raise InvalidUnitError."
        ),
        "guarantees_boundary": {
            "is": ["extractive omission", "equivalence relative to supplied oracle",
                   "structurally lossless dedup (structural mode)"],
            "is_not": ["authorization", "context admission", "rewrite/paraphrase/summarize",
                       "retrieval", "model reasoning", "live-enterprise validation"],
        },
    }


def _fields(dc: object) -> list:
    return [{"name": f.name, "type": _type_name(f.type)} for f in dataclasses.fields(dc)]


def token_accounting_schema() -> dict:
    """Machine-readable schema for the CM-TA1 token-accounting contracts.

    Three DISTINCT measurements, never collapsed: context reduction (A), the
    complete-request estimate (B), and provider-reported usage (C).
    """
    return {
        "contract_version": api.CONTRACT_VERSION,
        "module": "ugence_context_minimization.token_accounting",
        "principle": (
            "Context Minimization measures how much context was safely removed (A). "
            "The request estimate measures the complete serialized request (B) via an "
            "INJECTED counter — the core implements no provider tokenizer. Provider "
            "usage measures what the API reported consuming (C); it is authoritative for "
            "the response being reconciled, never overwrites the estimate, and is NOT an "
            "invoice. Unknown usage is None, never zero."
        ),
        "enums": {
            "TokenCountBasis": [b.value for b in ta.TokenCountBasis],
            "AttemptStatus": [s.value for s in ta.AttemptStatus],
            "UsageAvailability": [u.value for u in ta.UsageAvailability],
        },
        "models": {
            "RequestTokenEstimate": {
                "measurement": "B",
                "fields": _fields(ta.RequestTokenEstimate),
                "note": "estimated_input_tokens is distinct from MinimizationResult.resulting_tokens",
            },
            "ProviderTokenUsage": {
                "measurement": "C",
                "fields": _fields(ta.ProviderTokenUsage),
                "optional_int_fields_unknown_is_null": [
                    "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                    "output_tokens", "reasoning_tokens", "total_tokens",
                ],
                "derived_total": "input+output ONLY (cached/cache_write/reasoning excluded to avoid double-count); reported total_tokens preserved separately",
            },
            "ApiCallTokenRecord": {
                "fields": _fields(ta.ApiCallTokenRecord),
                "computed_properties": ["is_retry", "reduction_pct", "record_fingerprint"],
                "fingerprint_domain": "ugence-context-minimization/api-call/1",
                "excludes": ["prompt_text", "credentials", "secrets", "provider_response_payload"],
            },
            "LogicalRequestTokenSummary": {
                "fields": _fields(ta.LogicalRequestTokenSummary),
                "computed_properties": ["summary_fingerprint"],
                "fingerprint_domain": "ugence-context-minimization/logical-request/1",
                "note": "context savings counted once per logical request; unknown usage keeps complete=False",
                "total_provenance": {
                    "provider_reported_total_tokens": "sum of ONLY explicit provider-reported totals; never a derived value",
                    "attempts_reporting_total": "count of known attempts that carried an explicit provider total",
                    "derived_total_tokens": "sum of derived input+output; cached/cache_write/reasoning excluded (never re-added)",
                    "settlement_token_units": "documented settlement selection per attempt (reported total if present, else derived); meaningful only when complete",
                    "rule": "a field named 'provider ... total' contains ONLY provider-reported values; provider-reported and derived totals are never blended into one field",
                },
            },
        },
        "protocols": ["RequestTokenCounter", "TokenAccountingSink"],
        "apis": [
            "prepare_api_call_measurement",
            "reconcile_api_call_measurement",
            "aggregate_logical_request_usage",
        ],
        "fail_closed_conditions": [
            "negative / bool / float / NaN / inf / str token count -> InvalidUnitError/InvalidRequestError",
            "usage AVAILABLE without any known field -> InvalidRequestError",
            "usage AVAILABLE while provider not invoked -> InvalidRequestError",
            "provider_usage supplied while availability is UNAVAILABLE -> InvalidRequestError",
            "context_tokens_eliminated != before-after, or after>before -> InvalidRequestError",
            "attempt_number < 1 -> InvalidRequestError",
            "duplicate attempt_id with conflicting content -> InvalidRequestError (idempotent replay must be byte-identical)",
            "aggregation over divergent minimization run fingerprints -> InvalidRequestError",
        ],
        "boundary": {
            "is": ["neutral accounting of already-measured facts", "deterministic fingerprints"],
            "is_not": [
                "provider tokenizer", "model SDK", "network/database/filesystem persistence",
                "pricing authority", "invoice reconciliation", "wall-clock or random id generation",
            ],
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
            {"id": "oracle_expired_inclusive", "mode": "ORACLE_VERIFIED",
             "expect": "FALLBACK at evaluation_time == valid_until (ORACLE_EVALUATION_EXPIRED)"},
            {"id": "oracle_missing_evaluation_time", "mode": "ORACLE_VERIFIED",
             "expect": "FALLBACK (ORACLE_EVALUATION_TIME_REQUIRED)"},
            {"id": "oracle_correlation_missing", "mode": "ORACLE_VERIFIED",
             "expect": "FALLBACK (ORACLE_CORRELATION_MISSING)"},
            {"id": "oracle_correlation_mismatch", "mode": "ORACLE_VERIFIED",
             "expect": "FALLBACK (ORACLE_CORRELATION_MISMATCH)"},
            {"id": "protection_uncertain_retained", "mode": "ORACLE_VERIFIED",
             "expect": "uncertain unit retained"},
            {"id": "budget_unreachable", "mode": "ORACLE_VERIFIED",
             "expect": "safest achievable + BUDGET_UNREACHABLE_WITHOUT_PROTECTED"},
            {"id": "request_reduction_preserved", "mode": "ORACLE_VERIFIED",
             "expect": "requested_reduction echoes the caller's target on every path"},
            {"id": "two_fingerprints", "mode": "ANY",
             "expect": "run_fingerprint and outcome_fingerprint are distinct; fingerprint aliases outcome"},
            # -- CM-TA1 token accounting -----------------------------------------
            {"id": "ta_prepare_copies_context_counts", "mode": "ACCOUNTING",
             "expect": "prepare copies MinimizationResult before/after/eliminated verbatim; run_fingerprint preserved"},
            {"id": "ta_default_counter_approximate", "mode": "ACCOUNTING",
             "expect": "default request counter -> DEFAULT_APPROXIMATE, is_approximate True"},
            {"id": "ta_injected_counter_exact", "mode": "ACCOUNTING",
             "expect": "injected full-coverage counter -> INJECTED_COUNTER, is_approximate False"},
            {"id": "ta_estimate_distinct_from_context", "mode": "ACCOUNTING",
             "expect": "full-request estimate (B) is a different number than minimized context (A)"},
            {"id": "ta_worked_example", "mode": "ACCOUNTING",
             "expect": "before 8214 / after 2310 / eliminated 5904; provider input 2337 / cached 1500 / output 428"},
            {"id": "ta_failed_attempt_known_usage", "mode": "ACCOUNTING",
             "expect": "FAILED attempt with usage keeps AVAILABLE usage (failed calls can consume tokens)"},
            {"id": "ta_failed_attempt_unknown_usage", "mode": "ACCOUNTING",
             "expect": "FAILED/EXCEPTION with no usage -> UNAVAILABLE_*, provider_usage None (unknown != zero)"},
            {"id": "ta_no_provider_call_no_record", "mode": "ACCOUNTING",
             "expect": "governance HOLD/BLOCK/ESCALATE never invokes provider -> no ApiCallTokenRecord"},
            {"id": "ta_cached_reasoning_not_double_counted", "mode": "ACCOUNTING",
             "expect": "derived_total = input+output only; cached/cache_write/reasoning excluded and still visible"},
            {"id": "ta_unknown_fields_null", "mode": "ACCOUNTING",
             "expect": "unknown usage fields serialize as null, not zero"},
            {"id": "ta_malformed_counts_rejected", "mode": "ACCOUNTING",
             "expect": "negative/bool/float/NaN/inf/str token counts rejected fail-closed"},
            {"id": "ta_duplicate_attempt_conflict_rejected", "mode": "ACCOUNTING",
             "expect": "duplicate attempt_id with conflicting content rejected; identical replay idempotent"},
            {"id": "ta_three_attempts_three_records", "mode": "ACCOUNTING",
             "expect": "three attempts under one logical request remain three records"},
            {"id": "ta_summary_marks_gaps", "mode": "ACCOUNTING",
             "expect": "any unknown-usage attempt -> summary.complete False; savings counted once"},
            {"id": "ta_deterministic_fingerprints", "mode": "ACCOUNTING",
             "expect": "record + summary fingerprints deterministic; counter id/version and usage changes shift the record fp"},
        ],
    }


def main() -> int:
    ART.mkdir(exist_ok=True)
    outputs = {
        "public_api.json": public_api(),
        "reason_codes.json": reason_codes(),
        "minimization_result_schema.json": result_schema(),
        "invariance_contract.json": invariance_contract(),
        "token_accounting_schema.json": token_accounting_schema(),
        "acceptance_scenarios.json": acceptance_scenarios(),
    }
    for name, data in outputs.items():
        (ART / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print(f"wrote artifacts/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
