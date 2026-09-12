"""The redacted report generator (LP-7 ruling 11).

A report carries statuses, observations that are refusal names and counts, digests, and
versions. It carries no prompt text, no response text and no credential: the generator
refuses to produce one that does (the harness's synthetic prompt and leased marker are
registered as known markers, and every string is scanned for credential shapes). It
never claims a live pass and never edits ``MEU_LIVE_VALIDATION.json``.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict

from ugence_model_egress_provider_openai import FAKE_RESPONSE_MARKER

from .harness import OfflineRun
from ugence_model_egress_unit import STEP8_OBLIGATION_COUNT, step8_field_counts

from .rows import ROWS, STATUS_VOCABULARY
from .secret_shapes import assert_clean
from .version import REPORT_SCHEMA

__all__ = ["build_report", "render", "write_report"]


def build_report(run: OfflineRun) -> Dict[str, Any]:
    rows = []
    for o in run.outcomes:
        assert o.status in STATUS_VOCABULARY, o.status
        row_def = next(r for r in ROWS if r.row == o.row)
        rows.append({"row": o.row, "scenario": o.scenario, "required": o.required, "status": o.status,
                     "observed": o.observed, "digests": list(o.digests), "reason": o.reason,
                     "infrastructure_dependent": o.infrastructure_dependent,
                     "result_in_record": None,
                     "external_evidence_required": row_def.external_evidence_required})
    counts = {s: sum(r["status"] == s for r in rows) for s in STATUS_VOCABULARY}
    report = {
        "schema": REPORT_SCHEMA,
        "generated_at": run.generated_at.isoformat(),
        "versions": {"ugence-model-egress-unit": run.unit_version,
                     "ugence-model-egress-provider-openai": run.adapter_version,
                     "ugence-model-egress-validation": run.harness_version},
        "commissioning_status": run.commissioning_status,
        "effect_on_MEU_LIVE_VALIDATION": "none; this report is offline evidence and marks no row of the record",
        "live_pass_claimed": False,
        "network_opened": False,
        "credential_present": False,
        "infrastructure_dependent_rows_not_executed": [r["row"] for r in rows if r["infrastructure_dependent"]],
        "audit_query_window": None,
        "step8": {"statement": step8_field_counts()["statement"], "obligations": STEP8_OBLIGATION_COUNT,
                  "checked_fields": step8_field_counts()["checked_fields"], "supplied_here": 0},
        "content_policy": "statuses, refusal names, counts, digests and versions only; no prompt text, no response text, no credential",
        "summary": counts,
        "rows": rows,
    }
    text = render(report)
    if FAKE_RESPONSE_MARKER in text:
        raise ValueError("a report never carries response text, not even the fake marker")
    assert_clean(report, known_markers=run.known_markers, what="the report")
    for marker in run.known_markers:
        if marker in text:
            raise ValueError("a report never carries the prompt or the leased marker")
    return report


def render(report: Dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_report(report: Dict[str, Any], path: pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(report), encoding="utf-8")
    return path
