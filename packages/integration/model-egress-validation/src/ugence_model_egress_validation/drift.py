"""Drift checks (LP-7 ruling 11): the records beside the unit agree with the code.

Pure over two parsed records; :func:`load_records` reads the two JSON files beside the
installed unit. A drift is a sentence naming the record field and the code constant.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List, Mapping

import ugence_model_egress_unit as meu
from ugence_model_egress_provider_openai import DESIGNATED_MODEL, OpenAIResponsesProvider

from .rows import ROWS

__all__ = ["records_directory", "load_records", "check_drift"]


_RECORDS_SUBPATH = pathlib.Path("packages") / "integration" / "model-egress-unit"


def records_directory() -> pathlib.Path:
    """The directory holding ``MEU_LIVE_PROVIDER_DESIGNATION.json`` and
    ``MEU_LIVE_VALIDATION.json``.

    In a source checkout that is the unit's package root beside its ``src``. When the
    unit is installed into site-packages (CI installs all three distributions), the
    records are not beside it, so the checkout is located by walking up from the
    working directory to the repository that contains ``packages/integration/model-egress-unit``.
    """

    here = pathlib.Path(meu.__file__).resolve().parent
    candidates = [here.parents[1], here.parent, here]
    cwd = pathlib.Path.cwd().resolve()
    candidates.extend(parent / _RECORDS_SUBPATH for parent in (cwd, *cwd.parents))
    for candidate in candidates:
        if (candidate / "MEU_LIVE_VALIDATION.json").exists() and (candidate / "MEU_LIVE_PROVIDER_DESIGNATION.json").exists():
            return candidate
    raise FileNotFoundError(
        "the live-provider records were not found beside the unit or in a checkout above the working "
        "directory; pass --records <dir> or run from the repository")


def load_records(directory: pathlib.Path = None) -> Dict[str, Any]:
    directory = pathlib.Path(directory) if directory is not None else records_directory()
    return {
        "designation": json.loads((directory / "MEU_LIVE_PROVIDER_DESIGNATION.json").read_text(encoding="utf-8")),
        "validation": json.loads((directory / "MEU_LIVE_VALIDATION.json").read_text(encoding="utf-8")),
    }


def check_drift(designation: Mapping[str, Any], validation: Mapping[str, Any]) -> List[str]:
    drift: List[str] = []
    L = meu.COMMISSIONING_LIMITS
    limits = designation.get("limits", {})
    for record_key, code_value in (("max_input_tokens_per_request", L.max_input_tokens),
                                   ("max_output_tokens_per_request", L.max_output_tokens),
                                   ("max_genuine_validation_calls", L.max_genuine_calls),
                                   ("concurrency", L.concurrency)):
        if limits.get(record_key) != code_value:
            drift.append(f"limits.{record_key} is {limits.get(record_key)!r} in the record but {code_value!r} in COMMISSIONING_LIMITS")
    if limits.get("total_commissioning_budget_usd", -1) * 100 != L.budget_usd_cents:
        drift.append("limits.total_commissioning_budget_usd disagrees with COMMISSIONING_LIMITS.budget_usd_cents")
    if limits.get("streaming") is not False or L.streaming is not False:
        drift.append("limits.streaming must be false in the record and the code")

    vendor = designation.get("vendor", {})
    if vendor.get("api_host") != meu.OPENAI_RESPONSES.host:
        drift.append(f"vendor.api_host {vendor.get('api_host')!r} is not OPENAI_RESPONSES.host {meu.OPENAI_RESPONSES.host!r}")
    if not str(vendor.get("endpoint", "")).startswith(meu.OPENAI_RESPONSES.path):
        drift.append("vendor.endpoint does not begin with OPENAI_RESPONSES.path")
    model = str(vendor.get("model", "")).split(" ")[0]
    if model != DESIGNATED_MODEL or not meu.is_pinned_snapshot(model):
        drift.append(f"vendor.model {model!r} is not the adapter's DESIGNATED_MODEL {DESIGNATED_MODEL!r}")
    if OpenAIResponsesProvider.designated_model != DESIGNATED_MODEL:
        drift.append("the adapter class and its version module disagree on the designated model")

    status = validation.get("meu_live_status")
    if status != meu.COMMISSIONING_STATUS:
        drift.append(f"MEU_LIVE_VALIDATION.meu_live_status {status!r} is not COMMISSIONING_STATUS {meu.COMMISSIONING_STATUS!r}")
    if status not in validation.get("status_vocabulary", []):
        drift.append("meu_live_status is outside the record's own vocabulary")

    matrix = validation.get("validation_matrix", [])
    expected = [(r.row, r.required) for r in ROWS]
    actual = [(r.get("row"), r.get("required")) for r in matrix]
    if actual != expected:
        drift.append("the validation matrix rows or their required outcomes differ from the harness's row table")
    step8 = designation.get("step8_required_values", {})
    undesignated = [k for k, v in step8.items() if isinstance(v, str) and v.startswith("UNDESIGNATED")]
    if undesignated and status != "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS":
        drift.append(f"{len(undesignated)} step-8 values are UNDESIGNATED but the status is {status!r}")
    if status == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS":
        if any(r.get("result") is not None for r in matrix):
            drift.append("a matrix row carries a result while the provider is blocked")
        evidence = validation.get("evidence", {})
        if evidence.get("runs") or evidence.get("accepting_owner") or evidence.get("ci_run_or_signed_report"):
            drift.append("the validation record carries evidence while the provider is blocked")
    if meu.LIVE_VENDOR_EGRESS is not False:
        drift.append("LIVE_VENDOR_EGRESS is not False")
    return drift
