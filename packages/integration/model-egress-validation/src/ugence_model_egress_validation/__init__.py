"""Ugence Model Egress Validation — the offline step-7 artifacts (LP-7 ruling 11).

The eighteen-row harness over injected fake components, the negative-test matrix, the
redacted report generator, the drift checks and secret-shape scanning. **Opens no network
connection, holds no credential, marks no infrastructure-dependent row as passed, and
never edits ``MEU_LIVE_VALIDATION.json``.** ``live`` exists only to refuse until every
step-8 designation is supplied and independently checked.
"""

from __future__ import annotations

from .drift import check_drift, load_records, records_directory
from .harness import SYNTHETIC_PROMPT, OfflineRun, RowOutcome, run_offline
from .report import build_report, render, write_report
from .rows import OFFLINE_ROWS, ROWS, STATUS_VOCABULARY, Row
from .secret_shapes import Finding, assert_clean, scan
from .version import ENFORCEMENT_ENABLED, LIVE_VENDOR_EGRESS, MATURITY, REPORT_SCHEMA, __version__

__all__ = [
    "__version__", "MATURITY", "ENFORCEMENT_ENABLED", "LIVE_VENDOR_EGRESS", "REPORT_SCHEMA",
    "Row", "ROWS", "OFFLINE_ROWS", "STATUS_VOCABULARY",
    "SYNTHETIC_PROMPT", "RowOutcome", "OfflineRun", "run_offline",
    "build_report", "render", "write_report",
    "records_directory", "load_records", "check_drift",
    "Finding", "scan", "assert_clean",
]
