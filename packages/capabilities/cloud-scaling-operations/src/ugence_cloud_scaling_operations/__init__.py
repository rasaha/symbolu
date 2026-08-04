"""Ugence Cloud Scaling Operations — controlled-execution capability (canonical package).

Execution-capable (NOT advisory-only): in LIVE mode with credentials and an external
authorization it can mutate infrastructure. Dry-run is the default mode. Depends on the
advisory package ``ugence_cloud_scaling_controller``; the advisory package never depends
on this one. The authority boundary and controlled executors are added in subsequent
commits.
"""

from .version import __version__

__all__ = ["__version__"]
