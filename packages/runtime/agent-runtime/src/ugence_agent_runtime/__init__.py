"""Ugence Agent Runtime — domain-neutral coordination of agent/workflow execution.

The Agent Runtime coordinates execution: task and workflow lifecycle, provider and
tool invocation, retry/timeout/cancellation, checkpoints, and durable recovery. It
asks an external, neutral governance boundary whether a consequential transition may
proceed, and obeys the answer — it never creates governance authority, authors
policy, authorizes actions, or mints execution clearance.

Importing this package is side-effect free: it opens no connections, loads no
credentials, starts no threads or schedulers, and runs no recovery. See
``docs/AGENT_RUNTIME_SECURITY.md``.

Public API: see ``ugence_agent_runtime.api`` (re-exported here).
"""
from __future__ import annotations

from .api import *  # noqa: F401,F403
from .api import __all__ as _api_all
from .version import VERSION, __version__

__all__ = list(_api_all) + ["__version__", "VERSION"]
