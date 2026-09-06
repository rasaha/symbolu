"""The PA/PWC-X1 composition root.

Policy Authority authenticates; the compiler binds; this package derives the
reference that connects them. It issues nothing, revokes nothing, approves nothing,
and holds no key material.
"""

from __future__ import annotations

from .errors import AuthoritativeCompilationError, RefusalCode
from .models import AuthoritativeCompilationDraft
from .service import AuthoritativePolicyCompilationService, PolicyPackBuilder
from .version import __version__
from .version_info import version_info

__all__ = [
    "__version__",
    "AuthoritativePolicyCompilationService",
    "PolicyPackBuilder",
    "AuthoritativeCompilationDraft",
    "AuthoritativeCompilationError",
    "RefusalCode",
    "version_info",
]
