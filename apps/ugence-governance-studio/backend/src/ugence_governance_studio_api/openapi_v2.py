"""Deterministic OpenAPI generation for the v2 contract (GAS-4).

Byte-for-byte the same discipline as ``openapi.py``: host-free, timestamp-free, stable
operation ids, sorted keys. Generated from ``create_v2_app`` — never from the combined
application — so the v1 document and this one can never perturb each other.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from .app_v2 import create_v2_app
from .settings import ApiSettings


def generate_v2_openapi() -> Dict[str, Any]:
    app = create_v2_app(
        ApiSettings(environment="openapi", enable_docs=True, build_commit=None, build_id=None)
    )
    schema = app.openapi()
    schema.pop("servers", None)
    return schema


def canonical_v2_openapi_bytes() -> bytes:
    schema = generate_v2_openapi()
    text = json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")
