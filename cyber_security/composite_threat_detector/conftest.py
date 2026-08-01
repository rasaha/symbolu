"""COMPATIBILITY-ONLY. Put this directory on sys.path so the legacy
``composite_threat_detector`` redirect shim (see ./composite_threat_detector/)
is importable for root-level / legacy invocations during the compatibility
period. The canonical package is ``ugence_storygraph`` under
``packages/capabilities/storygraph``; new tests live there.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
