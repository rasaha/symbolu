"""Make the canonical ``ugence_storygraph`` package importable for source-tree
(non-installed) test runs by putting ``src/`` on ``sys.path``.

When the package is installed as a wheel this file is not shipped and is
unnecessary — the package is already importable. It exists only so that
``pytest packages/capabilities/storygraph`` works directly from a checkout.
"""

import pathlib
import sys

SRC = pathlib.Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
