"""LP-1 and LP-3: the one destination a provider adapter may reach, checked as a string.

This module opens nothing. It exists so the adapter that will live in another
distribution imports its permission from here and cannot widen it: a URL is permitted
only if its scheme, host and path are exactly the designated ones, with no userinfo,
no non-default port, no query and no fragment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .records import RefusalReason

__all__ = ["DesignatedDestination", "OPENAI_RESPONSES", "DestinationRefused", "check_destination"]


class DestinationRefused(ValueError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"{RefusalReason.DESTINATION_NOT_PERMITTED.value}: {detail}")
        self.reason = RefusalReason.DESTINATION_NOT_PERMITTED


@dataclass(frozen=True)
class DesignatedDestination:
    host: str
    path: str
    scheme: str = "https"

    def __post_init__(self) -> None:
        if self.scheme != "https":
            raise ValueError("a designated destination is https")
        if not self.host or "/" in self.host or ":" in self.host or "@" in self.host:
            raise ValueError("host must be a bare host name")
        if not self.path.startswith("/") or "?" in self.path or "#" in self.path:
            raise ValueError("path must be absolute and carry no query or fragment")

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host}{self.path}"

    def check(self, url: str) -> Optional[str]:
        """Why ``url`` is not this destination, or ``None`` when it is exactly it."""

        if not isinstance(url, str):
            return "not a string"
        scheme, sep, rest = url.partition("://")
        if not sep or scheme.lower() != self.scheme:
            return "scheme is not https"
        authority, slash, path = rest.partition("/")
        path = "/" + path if slash else ""
        if "@" in authority:
            return "userinfo is not permitted"
        host, colon, port = authority.partition(":")
        if colon and port != "443":
            return "a non-default port is not permitted"
        if host.lower() != self.host or not host:
            return "host is not the designated host"
        if "?" in path or "#" in path:
            return "a query or fragment is not permitted"
        if path != self.path:
            return "path is not the designated endpoint"
        return None


#: LP-3 (owner, 2026-09-11): the only provider destination in the commissioning scope.
OPENAI_RESPONSES = DesignatedDestination(host="api.openai.com", path="/v1/responses")


def check_destination(url: str, designated: DesignatedDestination = OPENAI_RESPONSES) -> str:
    """The URL, unchanged, or :class:`DestinationRefused`. Never widens."""

    why = designated.check(url)
    if why is not None:
        raise DestinationRefused(why)
    return url
