"""AI Hiring application — composes the hiring domain and the DGM kernel.

The application wires the domain-neutral governance kernel
(``decision_governance``) with the hiring domain (``domains.hiring``) into an
end-to-end, in-memory platform. The canonical composition root lives in
:mod:`applications.ai_hiring.platform` and imports the kernel directly (no
``ai_hiring.*`` compatibility shims). The legacy ``ai_hiring`` package re-exports
these entry points for backward compatibility.

Dependency direction: ``applications.ai_hiring`` → {``domains.hiring``,
``decision_governance``}. The reverse never holds.
"""

from __future__ import annotations

from applications.ai_hiring.platform import HiringPlatform, build_in_memory_platform

__all__ = ["HiringPlatform", "build_in_memory_platform"]
