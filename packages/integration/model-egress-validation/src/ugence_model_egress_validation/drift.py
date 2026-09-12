"""Drift checks (LP-7 ruling 11): the records beside the unit agree with the code.

Pure over two parsed records; :func:`load_records` reads the two JSON files beside the
installed unit. A drift is a sentence naming the record field and the code constant.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List, Mapping, Optional

import ugence_model_egress_unit as meu
from ugence_model_egress_provider_openai import DESIGNATED_MODEL, OpenAIResponsesProvider

from .rows import ROWS

__all__ = ["RecordsNotLocated", "records_directory", "load_records", "check_drift"]


_RECORDS_SUBPATH = pathlib.Path("packages") / "integration" / "model-egress-unit"
_RECORD_FILES = ("MEU_LIVE_PROVIDER_DESIGNATION.json", "MEU_LIVE_VALIDATION.json")
_DESIGNATION_SCHEMA = "model-egress-unit.live-provider-designation.v1"


class RecordsNotLocated(FileNotFoundError):
    """No record root, or more than one: the caller passes ``--records`` explicitly."""


def _holds_records(directory: pathlib.Path) -> bool:
    return all((directory / name).is_file() for name in _RECORD_FILES)


def _checkout_root(start: pathlib.Path) -> Optional[pathlib.Path]:
    """The nearest ancestor of ``start`` (inclusive) that is a git checkout root. The walk
    stops there: a parent, sibling or unrelated checkout is never a candidate."""

    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _unit_source_records() -> Optional[pathlib.Path]:
    """The records beside the unit when the unit is imported from a source checkout
    (``<root>/src/ugence_model_egress_unit``); ``None`` when it is installed."""

    here = pathlib.Path(meu.__file__).resolve().parent
    if here.parent.name == "src" and _holds_records(here.parents[1]):
        return here.parents[1]
    return None


def _working_directory_records() -> Optional[pathlib.Path]:
    root = _checkout_root(pathlib.Path.cwd().resolve())
    if root is None:
        return None
    candidate = root / _RECORDS_SUBPATH
    return candidate if _holds_records(candidate) else None


def records_directory() -> pathlib.Path:
    """The directory holding the two records, located by exactly one rule or refused.

    Candidates are (a) the records beside the unit when the unit is imported from a source
    checkout, and (b) the records of the git checkout that contains the working directory.
    When both exist they must be the same directory; when they differ, or when neither
    exists, this fails closed with :class:`RecordsNotLocated` and the caller passes
    ``--records``. A parent, sibling or unrelated checkout is never consulted.
    """

    found = {p.resolve() for p in (_unit_source_records(), _working_directory_records()) if p is not None}
    if not found:
        raise RecordsNotLocated(
            "the live-provider records were not located: the unit is not imported from a source checkout and the "
            "working directory is not inside a checkout holding packages/integration/model-egress-unit; pass --records <dir>")
    if len(found) > 1:
        raise RecordsNotLocated(
            "ambiguous record roots (the unit's source checkout and the working directory's checkout differ); "
            "pass --records <dir> to name the intended one: " + ", ".join(sorted(str(p) for p in found)))
    return found.pop()


def load_records(directory: pathlib.Path = None) -> Dict[str, Any]:
    """Read-only: the two records parsed, after checking they are the intended records
    (the designation record's ``schema`` is the live-provider designation schema)."""

    directory = pathlib.Path(directory).resolve() if directory is not None else records_directory()
    if not _holds_records(directory):
        raise RecordsNotLocated(f"{directory} does not hold both records")
    designation = json.loads((directory / "MEU_LIVE_PROVIDER_DESIGNATION.json").read_text(encoding="utf-8"))
    validation = json.loads((directory / "MEU_LIVE_VALIDATION.json").read_text(encoding="utf-8"))
    if designation.get("schema") != _DESIGNATION_SCHEMA:
        raise RecordsNotLocated(f"{directory} holds a designation record of schema {designation.get('schema')!r}, "
                                f"not {_DESIGNATION_SCHEMA!r}")
    if "validation_matrix" not in validation or "meu_live_status" not in validation:
        raise RecordsNotLocated(f"{directory} holds a validation record without a matrix or status")
    return {"designation": designation, "validation": validation}


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

    authorization = validation.get("live_synthetic_validation_authorization")
    if authorization != meu.LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION_DIGEST:
        drift.append(f"MEU_LIVE_VALIDATION.live_synthetic_validation_authorization {authorization!r} is not the unit's "
                     f"mirror LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION_DIGEST {meu.LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION_DIGEST!r}")
    if authorization != meu.NOT_GIVEN and not (isinstance(authorization, str) and len(authorization) == 64
                                               and set(authorization) <= set("0123456789abcdef")):
        drift.append("live_synthetic_validation_authorization is neither NOT_GIVEN nor a 64-hex digest of a typed authorization; "
                     "a string, flag or name is never an authorization (ADR §0.6)")
    if not isinstance(validation.get("revoked_authorization_digests"), list):
        drift.append("the validation record carries no revoked_authorization_digests list")
    expected_owner = designation.get("custody", {}).get("custody_owner")
    if not validation.get("authorizing_owner") or validation.get("authorizing_owner") != expected_owner:
        drift.append("the validation record's authorizing_owner is absent or is not the designated custody owner")
    if authorization == meu.NOT_GIVEN and validation.get("meu_live_status") in meu.GENUINE_CALL_ADMITTING_STATUSES:
        drift.append("the status admits a genuine call while no authorization is pinned; a genuine call needs both (ADR §0.6)")
    row12 = next((r for r in validation.get("validation_matrix", []) if r.get("row") == 12), {})
    if any("MET" in str(p).split(";")[0].split("(")[0] for p in row12.get("prerequisites", [])):
        drift.append("row 12 lists MET among its prerequisites; MET is the outcome, never a prerequisite (ADR §0.5)")
    if not row12.get("prerequisites"):
        drift.append("row 12 carries no prerequisites (ADR §0.5)")
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
    obligations = step8.get("obligations", {})
    if len(obligations) != 17 or step8.get("obligation_count") != 17:
        drift.append("the designation record does not carry exactly seventeen step-8 obligations (LP-7 ruling 12)")
    undesignated = [k for k, v in obligations.items() if isinstance(v, str) and v.startswith("UNDESIGNATED")]
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
