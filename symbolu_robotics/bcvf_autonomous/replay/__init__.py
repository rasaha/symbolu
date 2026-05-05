"""Replay / record-and-replay framework.

Public surface (provisional, see ``API_STABILITY.md`` §2.2 +
``REPLAY_FRAMEWORK_DESIGN.md`` §9):

* :class:`ReplayBundle` — recall-investigator's recording
  artifact (config + recorded output + metadata).
* :func:`build_replay_bundle` — factory wrapping in-memory
  components into a bundle.
* :func:`save_replay_bundle` / :func:`load_replay_bundle` —
  canonical-JSON round-trip.
* :func:`replay_bundle` — bit-identity verification path.
* :func:`compare_replay` — pure comparator (caller supplies the
  reconstructed record).
* :class:`ReplayResult` — typed verdict with field-level +
  tick-level divergence localisation.
* :class:`ReplayBundleError` / :class:`ReplayBundleVersionError`
  — exception hierarchy.
* :data:`BUNDLE_VERSION` — schema version of the bundle format.

See ``REPLAY_FRAMEWORK_DESIGN.md`` for the full design.
"""

from .bundle import (
    BUNDLE_VERSION,
    ReplayBundle,
    build_replay_bundle,
)
from .errors import ReplayBundleError, ReplayBundleVersionError
from .io import (
    load_replay_bundle,
    render_replay_bundle_text,
    save_replay_bundle,
)
from .reconstructor import (
    ReplayResult,
    compare_replay,
    replay_bundle,
)


__all__ = [
    # Bundle
    "BUNDLE_VERSION",
    "ReplayBundle",
    "build_replay_bundle",
    # I/O
    "load_replay_bundle",
    "render_replay_bundle_text",
    "save_replay_bundle",
    # Reconstructor
    "ReplayResult",
    "compare_replay",
    "replay_bundle",
    # Errors
    "ReplayBundleError",
    "ReplayBundleVersionError",
]
