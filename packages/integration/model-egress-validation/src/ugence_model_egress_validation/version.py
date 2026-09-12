"""Single source of truth for this distribution's version and posture."""

from __future__ import annotations

__version__ = "0.2.1"

MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"
ENFORCEMENT_ENABLED = False

#: No network path exists here and none is configurable; the test suite runs with
#: socket connections patched to raise, and the boundary tests refuse the imports.
LIVE_VENDOR_EGRESS = False

#: The report schema this distribution writes.
REPORT_SCHEMA = "model-egress-validation.offline-report.v1"
