#!/usr/bin/env python
"""Ratified-pin conformance for the governed-runtime-worker image (ADR step 4).

BLOCKING, network-independent, first among the worker's container steps. The worker
introduces no base image and no digest of its own: it builds only FROM the
python:3.11-slim-bookworm digest the owner ratified for the studio image in
``docs/audits/ugence_governance_studio_p3e/BASE_IMAGE_MIRROR_DECISION.json``. This
script asserts, offline:

  * every image ``base-images.json`` pins is one the ratification record authorizes,
    with the record's exact index and amd64 digests and platform;
  * the worker pins the python image only (a node image, or any other, is a change to
    the ratified decision and is refused here);
  * every Dockerfile FROM is digest-pinned to a pinned image and declares no other
    platform, and the python stage list is exactly the ratified ``backend`` and
    ``runtime`` roles.

It shares the P3E verifier's FROM grammar and the record; it differs only in accepting
a subset of the ratified images, which the studio verifier (rightly, for the studio)
does not. Exit 0 conforms; 1 blocking mismatch.

    python verify_ratified_pins.py [record.json] [pins.json] [Dockerfile]
"""
from __future__ import annotations

import json
import re
import sys

RECORD = "docs/audits/ugence_governance_studio_p3e/BASE_IMAGE_MIRROR_DECISION.json"
PINS = "deployment/governed-runtime-worker/base-images.json"
DOCKERFILE = "deployment/governed-runtime-worker/Dockerfile"

#: The one image the worker may build from, and the stage roles it may use.
PERMITTED = {"library/python:3.11-slim-bookworm": ["backend", "runtime"]}

_FROM = re.compile(
    r"^FROM\s+(?:--platform=(\S+)\s+)?(\S+?):(\S+?)@(sha256:[0-9a-f]{64})(?:\s+AS\s+(\S+))?\s*$",
    re.MULTILINE,
)


def _short(ref: str) -> str:
    """``docker.io/library/python`` and the Dockerfile's bare ``python`` are one image."""
    ref = ref.split("@", 1)[0]
    if ref.startswith("docker.io/"):
        ref = ref[len("docker.io/"):]
    if "/" not in ref:
        ref = "library/" + ref
    return ref


def main(record: str = RECORD, pins_path: str = PINS, dockerfile: str = DOCKERFILE) -> int:
    record_doc = json.load(open(record))
    ratified = {_short(i["upstream_ref"]): i for i in record_doc["authoritative_digests"]["images"]}
    platform = record_doc["authoritative_digests"].get("platform")
    fail: list[str] = []
    if not platform:
        fail.append("ratification record declares no platform")

    pins = json.load(open(pins_path))
    if pins.get("platform") != platform:
        fail.append(f'base-images.json platform {pins.get("platform")!r} != ratified {platform!r}')
    pinned: dict[str, dict] = {}
    for e in pins["base_images"]:
        ref = f'{e["repository"]}:{e["tag"]}'
        if e.get("registry") != "docker.io":
            fail.append(f"{ref} (role {e['role']}): registry {e.get('registry')!r} is not the ratified upstream")
        if e.get("platform") != platform:
            fail.append(f"{ref} (role {e['role']}): platform {e.get('platform')!r} != ratified {platform!r}")
        r = ratified.get(ref)
        if r is None:
            fail.append(f"base-images.json pins {ref} (role {e['role']}), which the ratification record does not authorize")
            continue
        if ref not in PERMITTED:
            fail.append(f"base-images.json pins {ref} (role {e['role']}); the worker may build only from {sorted(PERMITTED)}")
            continue
        for field in ("manifest_digest", "amd64_manifest_digest"):
            if e.get(field) != r[field]:
                fail.append(f"{ref} (role {e['role']}): base-images.json {field} {e.get(field)} != ratified {r[field]}")
        pinned[ref] = r
    for ref in PERMITTED:
        if ref not in pinned:
            fail.append(f"the worker image {ref} is not pinned in base-images.json")

    text = open(dockerfile).read()
    for line in text.splitlines():
        if line.startswith("FROM ") and "@sha256:" not in line:
            fail.append(f"Dockerfile has an unpinned FROM: {line.strip()}")
    stages: dict[str, list[str]] = {}
    froms = _FROM.findall(text)
    for from_platform, name, tag, digest, stage in froms:
        ref = f"{_short(name)}:{tag}"
        if from_platform and from_platform != platform:
            fail.append(f"Dockerfile stage '{stage}' declares --platform={from_platform} != ratified {platform}")
        r = pinned.get(ref)
        if r is None:
            fail.append(f"Dockerfile builds FROM {ref}, which is not a pinned, ratified worker base image")
            continue
        if digest != r["manifest_digest"]:
            fail.append(f"Dockerfile stage '{stage}' pins {ref}@{digest} != ratified {r['manifest_digest']}")
        stages.setdefault(ref, []).append(stage)
    for ref, want in PERMITTED.items():
        got = sorted(stages.get(ref, []))
        if got != sorted(want):
            fail.append(f"{ref}: Dockerfile stages {got} != permitted worker stages {sorted(want)}")

    if fail:
        print("BLOCKING: the worker's base-image pins do not match the ratified supply decision.", file=sys.stderr)
        for f in fail:
            print("  FAIL " + f, file=sys.stderr)
        print(f"\nA re-pin is a change to the ratified decision recorded in {record}; the worker\n"
              "may not introduce a digest or an image of its own.", file=sys.stderr)
        return 1
    print(f"worker base-image pins conform to the ratified supply decision "
          f"({len(pinned)} image(s), {len(froms)} FROM stage(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
