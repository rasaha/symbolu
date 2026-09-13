"""Every error this package raises, with the provider's words removed.

A Google API error carries a message, and that message is written by a service that
has just been handed a principal, a resource and sometimes a payload. None of it is
allowed into an exception, a log line, a record or a report here. What survives a
Google exception is its **type name and nothing else**, and even that is checked for a
credential shape before it is used.
"""

from __future__ import annotations

from ugence_model_egress_unit import looks_like_a_credential

__all__ = ["SANITIZED_UNKNOWN", "sanitize_exception_type"]

#: What an exception whose own type name is unusable becomes.
SANITIZED_UNKNOWN = "UnknownSecretManagerError"


def sanitize_exception_type(exc: BaseException) -> str:
    """The exception's type name, or :data:`SANITIZED_UNKNOWN`. Never its message.

    The type name is taken from the class, not from ``str(exc)``, so an exception whose
    *message* embeds a credential cannot leak through here. A class whose own name is
    absurd (credential-shaped, over-long, or not printable) is replaced outright.
    """

    name = type(exc).__name__
    if (not name or len(name) > 64 or not name.isidentifier()
            or looks_like_a_credential(name)):
        return SANITIZED_UNKNOWN
    return name
