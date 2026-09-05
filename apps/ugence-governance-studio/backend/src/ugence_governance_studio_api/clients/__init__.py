"""Outbound clients. Read/shadow only, and restricted at the client level."""
from .console import ConsoleClient, ConsoleUnavailable, CONSOLE_ALLOWED_ROUTES

__all__ = ["ConsoleClient", "ConsoleUnavailable", "CONSOLE_ALLOWED_ROUTES"]
