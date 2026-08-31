"""Make the package ``src`` and the ``tests`` directory importable.

Allows the package-local suite to run standalone (``pytest packages/.../tests``) or
from an installed wheel, without an editable install.

The local ``src`` goes on ``sys.path`` **first, unconditionally** (guard-coverage ADR
§7.1/§9.d). This file used to prefer an installed distribution and fall back to the
source tree only on ImportError, which is the defect the Cloud Scaling Operations
adoption had to fix in its own conftest: the guard sweep runs this suite from a
disposable copy *outside* the repository, and in any environment where the controller
happens to be importable — an editable install, a wheel in the job's virtualenv, a
`PYTHONPATH` inherited from a neighbouring step — the copy's tests would import the
**unmutated** package. Every mutant would then be scored against code the mutation never
touched, and the whole sweep would report guards as killed or surviving on evidence that
has nothing to do with them.

Preferring the local tree is not merely safer for the sweep, it is what a package-local
suite should do in any case: `packages/.../tests` is meant to test the source beside it,
not whatever else is installed.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))

# The source beside this suite wins over any installed distribution, always.
if _SRC in sys.path:
    sys.path.remove(_SRC)
sys.path.insert(0, _SRC)

sys.path.insert(0, _HERE)  # so tests can 'import support'
