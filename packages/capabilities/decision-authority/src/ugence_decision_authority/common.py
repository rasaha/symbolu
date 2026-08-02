"""Framework-agnostic helpers shared across the Decision Governance kernel.

Deliberately dependency-free (stdlib only) so the domain layer never couples to
a web or ORM framework. ID generation and the clock are exposed as plain
functions and can be injected into services for deterministic tests.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

IdFactory = Callable[[str], str]
Clock = Callable[[], datetime]


def new_id(prefix: str) -> str:
    """Return a collision-resistant identifier with a human-readable prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 over a payload.

    Uses sorted keys and a stable separator so the same logical payload always
    produces the same digest, independent of dict ordering. Non-JSON-native
    values (datetimes, enums) are stringified via ``default=str``.
    """
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
