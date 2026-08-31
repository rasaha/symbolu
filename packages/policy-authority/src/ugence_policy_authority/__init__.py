"""Ugence Policy Authority — the shared, platform-wide policy authority.

**Internal platform infrastructure.** Not a customer-facing module, not a
product, and not a UVI engine. There is exactly **one** Policy Authority in
Ugence; this is it.

It owns one technical job: **issuing, signing, registering, resolving,
verifying and revoking policy versions** — for any policy family that registers
an adapter. **UVI policy schemas are its first adapter**, a consumer of the
boundary rather than the owner of it.

What it does **not** do:

* it does not author policy content;
* it does not decide whether policy content is good;
* it does not approve anything — organizational approval is produced *outside*
  the authority, and the authority merely **verifies** it through a boundary
  the composition root configures and trusts;
* it never approves its own policy, and never acts as both approving and
  issuing authority for the same policy;
* it never authorizes a runtime action — that is Risk Authority / ActionGate;
* it evaluates no readiness, calculates no value, resolves no benchmark, and
  performs no forecasting or attribution.

The reference registry is **in-memory, reference-grade and process-local**, not
production persistence. Structured successor references (supersession) and
benchmark-value governance are deferred to separate milestones.

Import the curated surface from :mod:`ugence_policy_authority.api`. See
``README.md`` for the exact trust guarantees and their limits.
"""

from __future__ import annotations

__version__ = "0.2.0"

from .api import *  # noqa: F401,F403,E402
from .api import __all__ as _api_all  # noqa: E402

__all__ = list(_api_all)
