"""Ugence AI Control Plane — Unified Console API.

A dedicated backend service that consolidates the governance functionality of the
Ugence platform's Specialized-AI-Systems and AI-Control-Plane layers behind one
stable HTTP surface, so a single web console can drive the *governed loop*:

    Agent Gateway  -> Truth & Evidence -> Policy & Action Control -> Operational
    (what enters)     (is it supported)   (may THIS action run + is it safe now)

It deliberately excludes the two AI-Infrastructure modules (KVPro, Cloud Scaling
Controller) — those are frozen and never govern.

This service is intentionally separate from ``symbolu.service.api_server`` (the
Symbol-U research pipeline). It imports the platform module libraries in-process
through their *frozen public API surfaces only* and never through internal
modules, so it stays inside the versioning guarantees recorded in
``platform/PLATFORM_FREEZE_V1.json``.

Packaged under ruling CP-1..CP-5 (``ADR_UGENCE_CONSOLE_PACKAGING_SCOPING.md`` §8) as
the distribution ``ugence-console-api`` at ``packages/integration/console-api``. Three
things that ruling fixed and this package must keep true:

* **Five routes, not eleven** (CP-3). The loop still evaluates all four capabilities in
  order; it exposes none of them individually. See ``app.SERVED_ROUTES``.
* **The audit ceiling is on every answer** (CP-4). See ``models.AUDIT_CEILING``.
* **A missing governance dependency fails at install** (CP-5), never at runtime while
  the service keeps answering.

The import namespace is unchanged by the move (CP-2): every boundary test in the tree
that forbids ``ugence_console_api`` still forbids the same name.
"""

from __future__ import annotations

#: 0.2.0 — first packaged release: the move to ``packages/integration/console-api``,
#: the five-route surface, the declared ceiling and the declared dependencies.
__version__ = "0.2.0"
