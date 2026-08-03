"""Deterministic OpenAPI generation (§6, §24).

Generates a host-free, timestamp-free OpenAPI document with stable operation and
model names. The same input always yields byte-identical output, so the committed
``contracts/openapi.json`` can be drift-verified in CI.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from .app import create_app
from .settings import ApiSettings


def generate_openapi() -> Dict[str, Any]:
    # Docs enabled so the schema is produced; no host servers are emitted.
    app = create_app(ApiSettings(environment="openapi", enable_docs=True,
                                 build_commit=None, build_id=None))
    schema = app.openapi()
    # Strip anything host/environment specific for a stable contract.
    schema.pop("servers", None)
    return schema


def canonical_openapi_bytes() -> bytes:
    schema = generate_openapi()
    text = json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")
