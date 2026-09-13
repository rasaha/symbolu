"""One run of the validation job.

Offline (the default) exercises the eighteen-row harness over fake components, evaluates
every gate, writes a redacted report and exits zero **without reading a real secret**.
Live fails closed, and it is refused by the **earliest** outstanding governance gate
rather than by the missing transport. In the present repository state that is the
seventeen undesignated Step-8 obligations, four gates before a transport is consulted.
Naming the transport first would invite the reading "authorize it and it will run",
which is false: the designations, their independent verification, the owner's separate
authorization and the egress flag are each outstanding before it.
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
from .report import NOTHING_COMPOSED, build_report, write_report
from .version import EXIT_NONCONFORMANT, EXIT_OK, EXIT_REFUSED

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
        if not gates.may_dispatch_a_genuine_call:
            return _refuse_live(config, gates, started_at)
        # Unreachable in this slice: LIVE_TRANSPORT cannot pass while
        # GENUINE_DISPATCH_IMPLEMENTED is False. Guarded rather than assumed, so a future
        # slice that flips that flag without building the dispatch path fails loudly.
        raise CompositionRefused(  # pragma: no cover
            "every gate passed but no genuine dispatch path is implemented in this distribution")
    return _offline(config, gates, started_at)


def _refuse_live(config: JobConfig, gates: GateReport, started_at: datetime) -> JobResult:
    """Refuse a live run, leading with the EARLIEST outstanding gate.

    The order matters more than it looks. Leading with the missing transport invites the
    reading "authorize it and it will run", which is false: in the present repository
    state the designations are undesignated, nobody has verified them, no authorization
    exists and live vendor egress is disabled, and each of those is outstanding before
    the transport is. Nothing is composed on this path at all — no Google client, no
    custody adapter, no transport — because :attr:`GateReport.may_compose_components` is
    false while any of gates 1 to 6 is blocked.
    """

    first = gates.first_blocked
    messages = [f"live mode refused at {first}: {gates.reason(first)}"]
    messages += [f"also outstanding, in order: {gate} — {gates.reason(gate)}"
                 for gate in gates.blocked if gate != first]
    messages.append("no Google client, custody adapter or transport was composed, and no Secret Manager "
                    "materialization was attempted: composition begins only after every gate before "
                    "LIVE_TRANSPORT has passed.")
    report = build_report(config=config, gates=gates, mode="live", outcome=REFUSED,
                          started_at=started_at, finished_at=started_at,
                          components=NOTHING_COMPOSED, notes=messages)
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
                          offline_report=offline_report,
                          # The harness's own injected doubles, and nothing else: no
                          # Google client was built and no custody adapter was composed.
                          components={**NOTHING_COMPOSED, "transport": "fake"},
                          notes=messages)
    path = write_report(report, pathlib.Path(config.report_path),
                        known_markers=tuple(run_result.known_markers))
    return JobResult(EXIT_OK if not nonconformant else EXIT_NONCONFORMANT,
                     outcome, report, path, messages)
