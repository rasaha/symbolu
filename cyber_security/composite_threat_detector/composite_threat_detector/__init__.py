"""COMPATIBILITY-ONLY legacy import path for the StoryGraph capability.

Canonical package: ``ugence_storygraph`` (``packages/capabilities/storygraph``).

This module contains **no business logic**. It re-exports the canonical public
API and installs a redirect so that every pre-migration import of the form
``composite_threat_detector`` or ``composite_threat_detector.<submodule>``
resolves to the **same** canonical module object (identity preserved). It exists
only for the compatibility period so existing in-repo imports keep working.

    # legacy (still works) ............ from composite_threat_detector import StoryGraph
    # canonical (preferred) ........... from ugence_storygraph import StoryGraph
    # canonical small API ............. from ugence_storygraph.api import StoryGraph

New code MUST import ``ugence_storygraph`` (or ``ugence_storygraph.api``).

Compatibility metadata:
    __compatibility__            True
    __canonical_package__        "ugence_storygraph"
    __removal_review_version__   "3.0.0"   (review/remove no earlier than this)

Side effects: exactly one, and only when the canonical package is not already
importable — a source-checkout bootstrap that puts
``packages/capabilities/storygraph/src`` on ``sys.path``. No other runtime effect.
"""

from __future__ import annotations

import importlib
import sys
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

_CANON = "ugence_storygraph"
_LEGACY = __name__  # "composite_threat_detector"


def _ensure_canonical_importable():
    try:
        return importlib.import_module(_CANON)
    except ModuleNotFoundError:
        import pathlib

        here = pathlib.Path(__file__).resolve()
        for parent in here.parents:
            cand = parent / "packages" / "capabilities" / "storygraph" / "src"
            if (cand / _CANON / "__init__.py").exists():
                if str(cand) not in sys.path:
                    sys.path.insert(0, str(cand))
                return importlib.import_module(_CANON)
        raise


_canon = _ensure_canonical_importable()


class _RedirectLoader(Loader):
    """Loader that returns the already-imported canonical module unchanged."""

    def __init__(self, canon_name: str) -> None:
        self._canon_name = canon_name

    def create_module(self, spec):  # noqa: D401
        return importlib.import_module(self._canon_name)

    def exec_module(self, module):  # already executed as the canonical module
        return None


class _RedirectFinder(MetaPathFinder):
    """Map ``composite_threat_detector.<sub>`` to ``ugence_storygraph.<sub>``."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(_LEGACY + "."):
            canon_name = _CANON + fullname[len(_LEGACY):]
            try:
                importlib.import_module(canon_name)
            except ModuleNotFoundError:
                return None
            return ModuleSpec(fullname, _RedirectLoader(canon_name))
        return None


if not any(isinstance(f, _RedirectFinder) for f in sys.meta_path):
    sys.meta_path.append(_RedirectFinder())

# Re-export the canonical public surface — the SAME objects (identity preserved).
from ugence_storygraph import *  # noqa: E402,F401,F403
from ugence_storygraph import __all__, __version__  # noqa: E402,F401

__compatibility__ = True
__canonical_package__ = _CANON
__removal_review_version__ = "3.0.0"
