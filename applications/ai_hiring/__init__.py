"""AI Hiring application — composes the hiring domain and the DGM kernel.

The application wires kernel governance services with hiring-domain adapters
(evidence ingestion, rubrics, ATS-style actions) into an end-to-end workflow.
The concrete wiring currently lives in the historical ``ai_hiring`` package
(retained for import stability); this module re-exposes its composition entry
points so callers can depend on ``applications.ai_hiring``.
"""

from __future__ import annotations

from ai_hiring import HiringPlatform, build_in_memory_platform

__all__ = ["HiringPlatform", "build_in_memory_platform"]
