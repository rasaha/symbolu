"""Tiny deterministic JSON writer (no system clock, sorted keys)."""
import json, os
def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, default=str); fh.write("\n")
