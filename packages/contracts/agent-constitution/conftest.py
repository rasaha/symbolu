"""Make ``ugence_agent_constitution`` importable from the src layout for this
package's own tests, without requiring an editable install.

Only the package's own ``src`` directory is added. The repository root is
deliberately NOT added: this package is a leaf and its tests must not be able to
import a sibling Ugence package by accident.
"""

import pathlib
import sys

SRC = str((pathlib.Path(__file__).resolve().parent / "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
