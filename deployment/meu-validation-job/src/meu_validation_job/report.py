"""The run's redacted report: identifiers, digests, timestamps, accounting, outcomes.

Written through the validation distribution's secret-shape scanner, so a report that
somehow carried a key, a prompt or a response never reaches disk: the writer raises
instead. That is deliberately a failure rather than a redaction, because a report that
silently drops a field is a report nobody can reason about.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence

from ugence_model_egress_unit import COMMISSIONING_LIMITS, COMMISSIONING_STATUS, LIVE_VENDOR_EGRESS
from ugence_model_egress_unit import __version__ as unit_version
from ugence_model_egress_custody_gcp import __version__ as custody_version
from ugence_model_egress_validation import __version__ as harness_version
from ugence_model_egress_validation.secret_shapes import assert_clean

from .gates import GateReport
from .version import REPORT_SCHEMA, __version__ as job_version

__all__ = ["NOTHING_COMPOSED", "build_report", "write_report"]


#: What a run that composed nothing looks like. A refused live run reports exactly this,
#: and ``tests/test_gate_order.py`` holds it to that: no Google client was built, no
#: custody adapter exists and no transport of any kind — real or fake — was constructed.
NOTHING_COMPOSED: Dict[str, Any] = {
    "google_secret_manager_client": False,
    "custody_adapter": False,
    "transport": "none",
}


def build_report(*, config, gates: GateReport, mode: str, outcome: str, started_at: datetime,
                 finished_at: datetime, offline_report: Optional[Mapping[str, Any]] = None,
                 components: Optional[Mapping[str, Any]] = None,
                 notes: Sequence[str] = ()) -> Dict[str, Any]:
    limits = COMMISSIONING_LIMITS
    report: Dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "generated_at": finished_at.isoformat(),
        "started_at": started_at.isoformat(),
        "mode": mode,
        "outcome": outcome,
        "versions": {
            "meu-validation-job": job_version,
            "ugence-model-egress-unit": unit_version,
            "ugence-model-egress-custody-gcp": custody_version,
            "ugence-model-egress-validation": harness_version,
        },
        "commissioning_status": COMMISSIONING_STATUS,
        "posture": {
            "instance_reference": config.instance_reference,
            "workload_identity_principal": config.workload_identity_principal,
            "environment": config.environment,
            "endpoint": config.endpoint,
        },
        "gates": gates.as_record(),
        "blocked_gates": list(gates.blocked),
        "credential_materialized": False,
        "secret_version_accessed": None,
        "components_composed": dict(components if components is not None else NOTHING_COMPOSED),
        "genuine_calls": {"authorized": None, "consumed": 0},
        "accounting": {"input_tokens": 0, "output_tokens": 0, "usd_cents": 0},
        "ceilings": {
            "max_genuine_calls": limits.max_genuine_calls,
            "budget_usd_cents": limits.budget_usd_cents,
            "max_input_tokens": limits.max_input_tokens,
            "max_output_tokens": limits.max_output_tokens,
            "concurrency": limits.concurrency,
            "max_retries": limits.max_retries,
            "store": limits.store, "tools": limits.tools,
            "streaming": limits.streaming, "background": limits.background,
        },
        "live_vendor_egress": LIVE_VENDOR_EGRESS,
        "network_opened": False,
        "credential_present": False,
        "live_pass_claimed": False,
        "notes": list(notes),
    }
    if offline_report is not None:
        report["offline_harness"] = {
            "summary": offline_report.get("summary"),
            "rows": [{k: row.get(k) for k in ("row", "scenario", "required", "status",
                                              "result_in_record", "infrastructure_dependent")}
                     for row in offline_report.get("rows", [])],
            "infrastructure_dependent_rows_not_executed":
                offline_report.get("infrastructure_dependent_rows_not_executed"),
            "drift": offline_report.get("drift", []),
        }
    return report


def write_report(report: Mapping[str, Any], path: pathlib.Path, *,
                 known_markers: Sequence[str] = ()) -> pathlib.Path:
    """Scan, then write. A report carrying a secret shape raises rather than lands."""

    assert_clean(report, known_markers=known_markers, what="the validation job report")
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
