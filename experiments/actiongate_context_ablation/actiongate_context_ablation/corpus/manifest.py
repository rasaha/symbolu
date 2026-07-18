"""Build the corpus manifest (provenance + coverage + content hashes)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from . import registry


def build_manifest(items=None) -> dict:
    items = items if items is not None else registry.load_all()
    rows = [it.manifest_row() for it in items]
    rows.sort(key=lambda r: r["item_id"])
    coverage = {
        "n_items": len(rows),
        "by_partition": dict(Counter(r["partition"] for r in rows)),
        "by_split": dict(Counter(r["split"] for r in rows)),
        "by_domain": dict(Counter(r["domain"] for r in rows)),
        "by_action_type": dict(Counter(r["action_type"] for r in rows)),
        "by_structure_family": dict(Counter(r["structure_family"] for r in rows)),
        "n_domains": len({r["domain"] for r in rows}),
        "n_action_types": len({r["action_type"] for r in rows}),
        "total_units": sum(r["n_units"] for r in rows),
        "total_tokens": sum(r["n_tokens"] for r in rows),
    }
    blob = json.dumps(rows, sort_keys=True).encode("utf-8")
    manifest_hash = "sha256:" + hashlib.sha256(blob).hexdigest()
    return {
        "manifest_version": "1",
        "note": ("PUBLIC = repository-derived; AUTHORED = independently authored. "
                 "Neither is confidential customer operational data."),
        "coverage": coverage,
        "manifest_hash": manifest_hash,
        "items": rows,
    }


def write_manifest(path, items=None) -> str:
    m = build_manifest(items)
    with open(path, "w") as f:
        json.dump(m, f, indent=2, sort_keys=True)
    return m["manifest_hash"]
