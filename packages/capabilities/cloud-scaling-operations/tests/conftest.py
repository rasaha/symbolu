"""Make the operations + advisory src and the tests dir importable for standalone runs.

Two properties this must hold, both learned the hard way by other packages' sweeps
(guard-coverage ADR §7.1 and §9.d — a conftest that locates the repository by counting
directory levels, or that stops setting paths because *an* installation is importable,
measures the wrong code the moment the tree is copied):

* **This package's own ``src`` is inserted first, unconditionally.** The gate-removal
  sweep runs this suite from a disposable copy outside the repository; an editable
  install of the *repository's* source must never shadow the copy under test, or every
  mutant would import unmutated code and the sweep would measure nothing.
* **The advisory controller is located through the checkout, not by ``..`` hops.** In a
  copied tree ``../../cloud-scaling-controller`` resolves to nothing; ``UGENCE_REPO_ROOT``
  is how the sweep tells a copy where the real checkout is, and the marker walk covers an
  ordinary in-repo run.
"""

from __future__ import annotations

import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent

for _p in (str(_HERE / ".." / "src"), str(_HERE)):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _repo_root() -> "pathlib.Path | None":
    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    for candidate in (_HERE, *_HERE.parents):
        if (candidate / "packages" / "capabilities" / "cloud-scaling-controller").is_dir():
            return candidate
    return None


_REPO = _repo_root()
if _REPO is not None:
    _ADV_SRC = str(_REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "src")
    if os.path.isdir(_ADV_SRC) and _ADV_SRC not in sys.path:
        # After this package's own paths: the copy under test always wins.
        sys.path.insert(2, _ADV_SRC)
