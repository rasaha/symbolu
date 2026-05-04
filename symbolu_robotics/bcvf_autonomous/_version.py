"""Single source of truth for the package version.

The version is exported from :mod:`symbolu_robotics.bcvf_autonomous` as
``__version__`` (string) and ``VERSION_INFO`` (tuple). The two are
kept in sync by a test pin so a future contributor cannot bump one
without the other.

Semver discipline (see ``API_STABILITY.md``):

* **Major** — backwards-incompatible changes to ``STABLE_API`` after
  a deprecation cycle. ``0.x → 1.0`` is the call-out moment when the
  API stability commitment becomes a backwards-compatibility one.
* **Minor** — additive changes to ``STABLE_API`` / ``PROVISIONAL_API``,
  removal of ``PROVISIONAL_API`` symbols (with a release-note line),
  or behavioural changes that don't break a stable signature.
* **Patch** — bug fixes, doc edits, internal refactors.

Pre-1.0 (current state) the contract is "breaking changes get a
release-note line and a deprecation warning, but minor bumps may
introduce them." Post-1.0 stable removal requires a full deprecation
cycle.
"""

from __future__ import annotations

from typing import Tuple


__version__: str = "0.4.0"
VERSION_INFO: Tuple[int, int, int] = (0, 4, 0)
