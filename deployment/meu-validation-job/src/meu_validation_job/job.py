"""One run of the validation job.

Offline (the default) exercises the eighteen-row harness over fake components, evaluates
every gate, writes a redacted report and exits zero **without reading a real secret**.
Live fails closed: no live Responses transport exists in any installed distribution and
``LIVE_VENDOR_EGRESS`` is False, so there is nothing to dispatch with. The refusal names
that first, so nobody reads it as "authorize it and it will run".
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence

from ugence_model_egress_unit import CI_ENVIRONMENT_MARKERS
from ugence_model_egress_validation.harness import run_offline
from ugence_model_egress_validation.report import build_report as build_offline_report

from .composition import CompositionRefused, build_custody_adapter
from .config import JobConfig, JobConfigRefused
from .gates import GateReport, evaluate_gates
from .report import build_report, write_report
from .version import EXIT_NONCONFORMANT, EXIT_OK, EXIT_REFUSED, GENUINE_DISPATCH_IMPLEMENTED

__all__ = ["JobResult", "ci_marker_variables", "load_records", "run"]

OFFLINE_CONFORMANT = "OFFLINE_CONFORMANT"
BLOCKED = "BLOCKED"
REFUSED = "REFUSED"


@dataclass(frozen=True)
class JobResult:
    exit_code: int
    outcome: str
    report: Dict[str, Any]
    report_path: Optional[pathlib.Path]
    messages: Sequence[str]


def ci_marker_variables(environ: Mapping[str, str]) -> Dict[str, str]:
    """Exactly the CI marker names, read from ``environ`` and nothing else.

    This is the job's only environment read. It cannot reach a key, a DSN or any other
    variable, and ``tests/test_boundaries.py`` holds the source to that.
    """

    return {marker: str(environ.get(marker, "")) for marker in CI_ENVIRONMENT_MARKERS}


def load_records(config: JobConfig) -> tuple:
    """The designation record, the validation record and, when named, the authorization."""

    def read(path: str, what: str) -> Dict[str, Any]:
        try:
            document = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise JobConfigRefused(f"{what}: {path} does not exist") from None
        except json.JSONDecodeError as exc:
            raise JobConfigRefused(f"{what}: {path} is not valid JSON (line {exc.lineno})") from None
        if not isinstance(document, dict):
            raise JobConfigRefused(f"{what}: {path} is not a JSON object")
        return document

    designation = read(config.designation_record_path, "designation_record_path")
    validation = read(config.validation_record_path, "validation_record_path")
    authorization = read(config.authorization_record_path, "authorization_record_path") \
        if str(config.authorization_record_path).strip() else None
    return designation, validation, authorization


def run(config: JobConfig, *, now: Optional[datetime] = None, environ: Mapping[str, str],
        client=None) -> JobResult:
    """Evaluate, report, exit. ``client`` is injected by tests; the deployed job passes
    none and the composition root builds the real one, which only a run that has cleared
    the credential gates can reach."""

    started_at = now or datetime.now(timezone.utc)
    designation, validation, authorization = load_records(config)
    variables = ci_marker_variables(environ)
    gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                           authorization_record=authorization, variables=variables, now=started_at)

    if config.mode == "live":
        return _refuse_live(config, gates, started_at)
    return _offline(config, gates, started_at)


def _refuse_live(config: JobConfig, gates: GateReport, started_at: datetime) -> JobResult:
    messages = [
        "live mode refused: no live Responses transport exists in any installed distribution and "
        "LIVE_VENDOR_EGRESS is False, so this job has nothing to dispatch with. Implementing that "
        "transport is the next slice and is not what an authorization unblocks.",
    ]
    messages += [f"also outstanding: {gate}" for gate in gates.blocked if gate != "LIVE_TRANSPORT"]
    finished_at = datetime.now(timezone.utc) if started_at is None else started_at
    report = build_report(config=config, gates=gates, mode="live", outcome=REFUSED,
                          started_at=started_at, finished_at=finished_at, notes=messages)
    path = write_report(report, pathlib.Path(config.report_path))
    return JobResult(EXIT_REFUSED, REFUSED, report, path, messages)


def _offline(config: JobConfig, gates: GateReport, started_at: datetime) -> JobResult:
    """The default. Fake components throughout; no custody adapter is composed at all.

    The offline path does not build a custody adapter even with a fake client, because
    "offline" should mean the credential path was never entered, not that it was entered
    with a double. The harness has its own marker custody for the rows that need one.
    """

    run_result = run_offline(now=started_at)
    offline_report = build_offline_report(run_result)
    nonconformant = [row["row"] for row in offline_report["rows"] if row["status"] == "OFFLINE_NONCONFORMANT"]
    outcome = OFFLINE_CONFORMANT if not nonconformant else BLOCKED
    messages = [
        f"offline harness: {offline_report['summary']}",
        f"infrastructure-dependent rows not executed: "
        f"{offline_report['infrastructure_dependent_rows_not_executed']}",
        "no credential was materialized and no secret version was accessed: the offline path never "
        "composes a custody adapter.",
    ]
    messages += [f"gate outstanding: {gate}" for gate in gates.blocked]
    if nonconformant:
        messages.append(f"non-conformant offline rows: {nonconformant}")
    report = build_report(config=config, gates=gates, mode="offline", outcome=outcome,
                          started_at=started_at, finished_at=started_at,
                          offline_report=offline_report, notes=messages)
    path = write_report(report, pathlib.Path(config.report_path),
                        known_markers=tuple(run_result.known_markers))
    return JobResult(EXIT_OK if not nonconformant else EXIT_NONCONFORMANT,
                     outcome, report, path, messages)
