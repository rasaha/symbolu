#!/usr/bin/env python
"""Advisory observation of upstream mutable-tag drift (ruling
SEPARATE_PIN_CONFORMANCE_FROM_TAG_DRIFT, rule 3).

For each ratified image, resolve what the mutable tag currently points at on the
upstream registry and report it beside the ratified digest. This is information for
the owner's controlled refresh decision and nothing more: it never fails, never
edits a tracked file, never approves a candidate and never changes what is built.
An unreachable registry is itself reported, as an observation, not an error.

    python observe_tag_drift.py <record.json> <pins.json> <out.json>

Exit code is always 0 by design; the report's ``observations`` carry the facts.
"""
from __future__ import annotations

import json
import sys
from typing import Callable

RESOLVER = None  # injected by the caller or resolved lazily from resolve_base_images


def _default_resolver() -> Callable[[dict], dict]:
    import importlib.util
    import os

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resolve_base_images.py")
    spec = importlib.util.spec_from_file_location("resolve_base_images", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.resolve_one


def observe(record: dict, pins: dict, *, resolver: Callable[[dict], dict]) -> dict:
    ratified = {i["upstream_ref"].split("/", 1)[1]: i for i in record["authoritative_digests"]["images"]}
    observations = []
    for e in pins["base_images"]:
        key = f'{e["repository"]}:{e["tag"]}'
        r = ratified.get(key, {})
        try:
            live = resolver(e)
        except Exception as exc:  # noqa: BLE001 - an observation, never a failure
            live = {"status": f"resolver_error_{type(exc).__name__}", "manifest_digest": None}
        ratified_digest = r.get("manifest_digest")
        current = live.get("manifest_digest")
        if live.get("status") != "resolved" or current is None:
            drift = "UNOBSERVABLE"
        elif current == ratified_digest:
            drift = "NONE"
        else:
            drift = "TAG_MOVED"
        observations.append({
            "upstream_ref": f'{e["registry"]}/{e["repository"]}:{e["tag"]}',
            "role": e.get("role"),
            "ratified_digest": ratified_digest,
            "current_tag_digest": current,
            "registry_status": live.get("status"),
            "drift": drift,
            "meaning": {
                "NONE": "the mutable tag still names the ratified digest",
                "TAG_MOVED": "the mutable tag names a newer image; the ratified digest is unaffected and stays authoritative (rule 3); a change is only ever made through a controlled refresh (rule 1)",
                "UNOBSERVABLE": "the upstream registry gave no usable answer; the ratified pin is unaffected (rule 3)",
            }[drift],
        })
    return {
        "schema": "base-image-tag-drift.v1",
        "advisory": True,
        "required_status": False,
        "modifies_tracked_files": False,
        "observations": observations,
        "summary": {d: sum(1 for o in observations if o["drift"] == d)
                    for d in ("NONE", "TAG_MOVED", "UNOBSERVABLE")},
    }


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: observe_tag_drift.py <record.json> <pins.json> <out.json>", file=sys.stderr)
        return 0
    record = json.load(open(argv[1], encoding="utf-8"))
    pins = json.load(open(argv[2], encoding="utf-8"))
    report = observe(record, pins, resolver=RESOLVER or _default_resolver())
    with open(argv[3], "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    for o in report["observations"]:
        print(f"{o['drift']:>12}  {o['upstream_ref']}  ratified={o['ratified_digest']}  "
              f"current={o['current_tag_digest']}  ({o['registry_status']})")
    print("advisory only: no required status, no tracked file modified, no digest approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
