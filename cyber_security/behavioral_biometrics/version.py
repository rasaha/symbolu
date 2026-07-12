"""Frozen component versions.

Every artifact (session, feature vector, split, verdict) carries the versions that
produced it, so a later re-analysis can tell whether two records are comparable.
Bump these when the wire format or numeric semantics change.
"""

from __future__ import annotations

SCHEMA_VERSION = "bbio-schema/1.0.0"
COLLECTOR_VERSION = "bbio-collector/1.0.0"
EXTRACTOR_VERSION = "bbio-extractor/1.0.0"
ANALYSIS_VERSION = "bbio-analysis/1.0.0"

# Sentinel that MUST accompany any data produced by the synthetic generators.
SYNTHETIC_MARKER = "SYNTHETIC_TEST_ONLY"
REAL_MARKER = "REAL"

# data_origin — a stricter provenance label used by the real collector app. Only
# REAL_PARTICIPANT data can ever produce a positive identity/coupling verdict.
ORIGIN_REAL = "REAL_PARTICIPANT"
ORIGIN_SYNTHETIC = "SYNTHETIC_TEST_ONLY"
ORIGIN_MOCK = "MOCK_TEST_ONLY"
ORIGIN_DEMO = "DEMO_ONLY"
DATA_ORIGINS = (ORIGIN_REAL, ORIGIN_SYNTHETIC, ORIGIN_MOCK, ORIGIN_DEMO)

COLLECTOR_APP_VERSION = "bbio-collector-app/1.0.0"
STUDY_VERSION = "bbio-study/1.0.0"
