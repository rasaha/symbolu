"""Put the legacy ``composite_threat_detector`` shim location on sys.path so the
compatibility contract tests can exercise the legacy import path alongside the
canonical ``ugence_storygraph`` package.
"""

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[5]
LEGACY_ROOT = REPO / "cyber_security" / "composite_threat_detector"
if LEGACY_ROOT.is_dir() and str(LEGACY_ROOT) not in sys.path:
    sys.path.insert(0, str(LEGACY_ROOT))
