"""Exceptions raised by the replay framework.

Two layers:

* :class:`ReplayBundleError` — base class. A buyer's recall-
  investigation script can ``except ReplayBundleError`` to
  catch every replay-specific failure without catching unrelated
  ``ValueError`` / ``KeyError`` slips.
* :class:`ReplayBundleVersionError` — subclass raised when a
  bundle's ``bundle_version`` field doesn't match the loader's
  supported schema. Lets a downstream caller distinguish
  "bundle is structurally invalid" (base class) from "bundle
  is from a future schema this loader doesn't understand"
  (version subclass).

The base class is the one a downstream caller catches; the
subclass is the one the test suite asserts on.
"""

from __future__ import annotations


class ReplayBundleError(Exception):
    """Base class for replay-bundle errors.

    Raised on:

    * Missing required fields at bundle load time.
    * ``recorded_record`` payload that fails
      :func:`episode_record_from_dict` validation.
    * Type mismatches (non-dict input, non-string version, etc.).
    """


class ReplayBundleVersionError(ReplayBundleError):
    """Raised when a bundle's ``bundle_version`` doesn't match the
    loader's supported schema. A future schema bump fails loud
    rather than silently producing a wrong replay.
    """
