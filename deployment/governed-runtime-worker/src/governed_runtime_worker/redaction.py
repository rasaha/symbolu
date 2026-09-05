"""The worker holds exactly two secrets, the application and system database DSNs
(ADR §4). Nothing that renders configuration, prints a startup line or formats an
error may carry them. This module is the one place a DSN is turned into text."""

from __future__ import annotations

from typing import Iterable
from urllib.parse import urlsplit

__all__ = ["REDACTED", "redact_dsn", "Scrubber"]

REDACTED = "<redacted>"


def redact_dsn(url: str) -> str:
    """The scheme, host, port and database of a DSN, never its user or password.

    A value that does not parse is rendered as ``<redacted>`` outright rather than
    risk echoing whatever it was.
    """

    if not isinstance(url, str) or not url:
        return REDACTED
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return REDACTED
    if not parts.scheme or not host:
        return REDACTED
    return f"{parts.scheme}://{REDACTED}@{host}{port}{parts.path or ''}"


class Scrubber:
    """Replaces every occurrence of a secret, and of its password alone, in text.

    Applied to every line the worker writes to a terminal or a log handler, so a
    library that echoes a connection string in an exception cannot leak it through
    this process's output.
    """

    def __init__(self, secrets: Iterable[str]) -> None:
        needles: set[str] = set()
        for secret in secrets:
            if not isinstance(secret, str) or not secret:
                continue
            needles.add(secret)
            try:
                password = urlsplit(secret).password
            except ValueError:
                password = None
            if password:
                needles.add(password)
        # Longest first, so a full DSN is replaced before its password fragment.
        self._needles = sorted(needles, key=len, reverse=True)

    def scrub(self, text: str) -> str:
        for needle in self._needles:
            text = text.replace(needle, REDACTED)
        return text
