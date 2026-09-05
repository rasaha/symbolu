"""Assert the base-image pins match the ratified supply decision (P3F).

BLOCKING pre-build gate. This checks the pins against the *owner-ratified record*
in ``docs/audits/ugence_governance_studio_p3e/BASE_IMAGE_MIRROR_DECISION.json``;
``mirror-digest-conformance`` (``verify_mirror_digest.py``) then checks that the
owner-approved mirror serves exactly that digest.

Together the two close the substitution hole: this step establishes
base-images.json == Dockerfile == ratification record, and the mirror step
establishes mirror == ratification record. A re-pin therefore cannot land with
green CI without editing the ratification record, which requires owner
re-ratification. Upstream mutable-tag movement is observed separately and
never enters either check.

Checks, all failing closed:
  * every base-images.json entry is a ratified image, at the ratified index and
    amd64 child digests;
  * every ratified image is actually pinned in base-images.json;
  * every Dockerfile FROM is digest-pinned, names a ratified image, and pins the
    ratified digest;
  * the Dockerfile stages per image match the ratified stage list;
  * the platform declared by the record, by base-images.json (top level and per
    entry) and by any ``--platform`` on a Dockerfile FROM all agree.

Deterministic and network-independent: it opens no socket, so an upstream
registry being unreachable, or a mutable tag having moved, cannot change its
answer (owner ruling SEPARATE_PIN_CONFORMANCE_FROM_TAG_DRIFT, 2026-09-05).

Exits 0 on conformance, 1 on any mismatch. Reads only; changes nothing.
"""
from __future__ import annotations

import json
import re
import sys

RECORD = "docs/audits/ugence_governance_studio_p3e/BASE_IMAGE_MIRROR_DECISION.json"
PINS = "deployment/governance-studio/base-images.json"
DOCKERFILE = "deployment/governance-studio/Dockerfile"

_FROM = re.compile(
    r"^FROM\s+(?:--platform=(\S+)\s+)?(\S+?):(\S+?)@(sha256:[0-9a-f]{64})(?:\s+AS\s+(\S+))?\s*$",
    re.MULTILINE,
)


def _short(ref: str) -> str:
    """docker.io/library/node:22-bookworm-slim -> node:22-bookworm-slim."""
    if ref.startswith("docker.io/"):
        ref = ref.split("/", 1)[1]
    if ref.startswith("library/"):
        ref = ref[len("library/") :]
    return ref


def main(record: str = RECORD, pins_path: str = PINS, dockerfile: str = DOCKERFILE) -> int:
    record_doc = json.load(open(record))
    ratified = {
        _short(i["upstream_ref"]): i
        for i in record_doc["authoritative_digests"]["images"]
    }
    platform = record_doc["authoritative_digests"].get("platform")
    fail: list[str] = []
    if not platform:
        fail.append("ratification record declares no platform")

    pins = json.load(open(pins_path))
    if pins.get("platform") != platform:
        fail.append(f'base-images.json platform {pins.get("platform")!r} != ratified {platform!r}')
    seen = set()
    for e in pins["base_images"]:
        if e.get("platform") != platform:
            fail.append(
                f'{_short(e["repository"])}:{e["tag"]} (role {e["role"]}): platform '
                f'{e.get("platform")!r} != ratified {platform!r}'
            )
        ref = f'{_short(e["repository"])}:{e["tag"]}'
        r = ratified.get(ref)
        if r is None:
            fail.append(
                f'base-images.json pins {e["registry"]}/{e["repository"]}:{e["tag"]} '
                f'(role {e["role"]}), which the ratification record does not authorize'
            )
            continue
        seen.add(ref)
        for field in ("manifest_digest", "amd64_manifest_digest"):
            if e.get(field) != r[field]:
                fail.append(
                    f'{ref} (role {e["role"]}): base-images.json {field} '
                    f'{e.get(field)} != ratified {r[field]}'
                )

    for ref in ratified:
        if ref not in seen:
            fail.append(f"ratified image {ref} is not pinned in base-images.json")

    text = open(dockerfile).read()
    for line in text.splitlines():
        if line.startswith("FROM ") and "@sha256:" not in line:
            fail.append(f"Dockerfile has an unpinned FROM: {line.strip()}")

    stages: dict[str, list[str]] = {}
    froms = _FROM.findall(text)
    for from_platform, name, tag, digest, stage in froms:
        ref = f"{name}:{tag}"
        if from_platform and from_platform != platform:
            fail.append(
                f"Dockerfile stage '{stage}' declares --platform={from_platform} "
                f"!= ratified {platform}"
            )
        r = ratified.get(ref)
        if r is None:
            fail.append(
                f"Dockerfile builds FROM {ref}, which the ratification record "
                "does not authorize"
            )
            continue
        if digest != r["manifest_digest"]:
            fail.append(
                f"Dockerfile stage '{stage}' pins {ref}@{digest} "
                f'!= ratified {r["manifest_digest"]}'
            )
        stages.setdefault(ref, []).append(stage)

    for ref, r in ratified.items():
        got, want = sorted(stages.get(ref, [])), sorted(r["dockerfile_stages"])
        if got != want:
            fail.append(f"{ref}: Dockerfile stages {got} != ratified dockerfile_stages {want}")

    if fail:
        print("BLOCKING: base-image pins do not match the ratified supply decision.", file=sys.stderr)
        for f in fail:
            print("  FAIL " + f, file=sys.stderr)
        print(
            f"\nA re-pin is a change to the ratified decision. Edit {record} and obtain\n"
            "owner re-ratification; do not silently re-pin base-images.json or the\n"
            "Dockerfile to a different digest, and do not substitute a base image.",
            file=sys.stderr,
        )
        return 1

    print(
        f"base-image pins conform to the ratified supply decision "
        f"({len(ratified)} image(s), {len(froms)} FROM stage(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
