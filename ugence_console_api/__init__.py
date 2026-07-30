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
"""

from __future__ import annotations

__version__ = "0.1.0"
