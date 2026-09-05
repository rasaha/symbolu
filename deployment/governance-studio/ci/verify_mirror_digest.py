#!/usr/bin/env python
"""Mirror-digest conformance (owner ruling SEPARATE_PIN_CONFORMANCE_FROM_TAG_DRIFT, rule 5).

Container builds must pull the ratified digest from an owner-approved, reachable OCI
mirror. This step asks the mirror for each ratified image BY DIGEST and proves the
manifest it serves is content-addressed to that digest: the ``Docker-Content-Digest``
header must equal it, a sha256 over the body must equal it, and the index must list
the ratified linux/amd64 child. Any other answer is a blocking mismatch.

It never talks to docker.io. When the mirror coordinates are not configured it emits
ONE stable, typed outcome — ``RESOURCE_BLOCKER_MIRROR_UNCONFIGURED`` — naming exactly
what the owner must supply, and stops. There is no Docker Hub fallback, no
re-pinning and no substitution: the ratified digest is the only reference this
script will ever pull.

Typed outcomes (``outcome`` in the JSON report and on stdout):

    MIRROR_DIGEST_CONFORMS            every image verified by digest; build may pull
    MIRROR_DIGEST_MISMATCH            the mirror served something else: halt
    MIRROR_UNREACHABLE                configured, but no usable answer: halt
    RESOURCE_BLOCKER_MIRROR_UNCONFIGURED  host, prefix or secret name missing: halt

Exit codes: 0 conforms; 1 mismatch or unreachable; 3 resource blocker.

Credential handling: the credential VALUE is read from the environment variable
whose name the ratification record supplies (``mirror.secret_name``) and is used only
as a bearer/basic header. It is never printed; every line this script emits is
passed through a redactor that replaces the value, should it ever appear, with
``[REDACTED]``.

    python verify_mirror_digest.py <record.json> <pins.json> <out.json> [--print-build-args]
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

OUTCOME_CONFORMS = "MIRROR_DIGEST_CONFORMS"
OUTCOME_MISMATCH = "MIRROR_DIGEST_MISMATCH"
OUTCOME_UNREACHABLE = "MIRROR_UNREACHABLE"
OUTCOME_BLOCKER = "RESOURCE_BLOCKER_MIRROR_UNCONFIGURED"

EXIT_CONFORMS, EXIT_MISMATCH, EXIT_BLOCKER = 0, 1, 3

INDEX_ACCEPT = (
    "application/vnd.oci.image.index.v1+json,"
    "application/vnd.docker.distribution.manifest.list.v2+json,"
    "application/vnd.oci.image.manifest.v1+json,"
    "application/vnd.docker.distribution.manifest.v2+json"
)

#: The upstream registry is never a source for this script, under any condition.
_FORBIDDEN_HOSTS = ("docker.io", "registry-1.docker.io", "auth.docker.io", "index.docker.io")

Fetcher = Callable[[str, dict], tuple[int, dict, bytes]]


class Redactor:
    """Every emitted line passes through here; a secret value never reaches a log."""

    def __init__(self, secrets: list[str]) -> None:
        self._secrets = [s for s in secrets if s]

    def __call__(self, text: str) -> str:
        for s in self._secrets:
            if s in text:
                text = text.replace(s, "[REDACTED]")
            b64 = base64.b64encode(s.encode()).decode()
            if b64 in text:
                text = text.replace(b64, "[REDACTED]")
        return text


def _default_fetch(url: str, headers: dict) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, dict(resp.headers.items()), resp.read()


def mirror_coordinates(record: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    m = record.get("mirror") or {}
    host = m.get("registry_host") or None
    prefix = m.get("repository_prefix") or None
    secret_name = m.get("secret_name") or (m.get("credential_mechanism") or {}).get("secret_name") or None
    return host, prefix, secret_name


def resource_blocker(host: Optional[str], prefix: Optional[str], secret_name: Optional[str]) -> dict:
    """The one stable typed outcome for an unconfigured mirror."""

    missing = [name for name, value in (("registry_host", host), ("repository_prefix", prefix),
                                        ("secret_name", secret_name)) if not value]
    return {
        "outcome": OUTCOME_BLOCKER,
        "blocker_kind": "RESOURCE",
        "missing": missing,
        "required_from_owner": {
            "registry_host": "the DNS name of the owner-approved OCI mirror reachable from CI",
            "repository_prefix": "the path prefix under which the mirror serves docker.io/library images",
            "secret_name": "the GitHub Actions secret NAME holding the mirror pull credential; the value is never recorded",
        },
        "where_to_record": "docs/audits/ugence_governance_studio_p3e/BASE_IMAGE_MIRROR_DECISION.json mirror.registry_host, mirror.repository_prefix, mirror.secret_name",
        "fallback": "none: docker.io is never consulted by this step",
        "gates": "NOT_EXECUTED",
    }


def _mirror_ref(host: str, prefix: str, repository: str) -> str:
    return f"{host.rstrip('/')}/{prefix.strip('/')}/{repository}"


def verify_one(entry: dict, ratified: dict, *, host: str, prefix: str, auth_header: Optional[str],
               fetch: Fetcher) -> dict:
    repo = entry["repository"]
    ref = _mirror_ref(host, prefix, repo)
    want = ratified["manifest_digest"]
    want_amd64 = ratified["amd64_manifest_digest"]
    out = {"repository": repo, "tag": entry["tag"], "mirror_ref": f"{ref}@{want}",
           "ratified_digest": want, "served_digest": None, "body_digest": None,
           "amd64_child_present": None, "status": None}
    if any(host == h or host.endswith("." + h) for h in _FORBIDDEN_HOSTS):
        out["status"] = "refused_upstream_host"
        return out
    url = f"https://{ref.split('/', 1)[0]}/v2/{ref.split('/', 1)[1]}/manifests/{want}"
    headers = {"Accept": INDEX_ACCEPT}
    if auth_header:
        headers["Authorization"] = auth_header
    try:
        status, resp_headers, body = fetch(url, headers)
    except urllib.error.HTTPError as exc:
        out["status"] = f"http_{exc.code}"
        return out
    except Exception as exc:  # noqa: BLE001 - URLError, timeout, DNS
        out["status"] = f"unreachable_{type(exc).__name__}"
        return out
    if status != 200:
        out["status"] = f"http_{status}"
        return out
    served = {k.lower(): v for k, v in resp_headers.items()}.get("docker-content-digest")
    body_digest = "sha256:" + hashlib.sha256(body).hexdigest()
    out["served_digest"], out["body_digest"] = served, body_digest
    try:
        index = json.loads(body)
        children = [m.get("digest") for m in index.get("manifests", [])]
    except ValueError:
        children = []
    out["amd64_child_present"] = want_amd64 in children
    if served == want and body_digest == want and out["amd64_child_present"]:
        out["status"] = "conforms"
    else:
        out["status"] = "mismatch"
    return out


def verify(record: dict, pins: dict, *, environ: dict, fetch: Fetcher = _default_fetch) -> tuple[dict, int]:
    host, prefix, secret_name = mirror_coordinates(record)
    if not (host and prefix and secret_name):
        return resource_blocker(host, prefix, secret_name), EXIT_BLOCKER
    credential = environ.get(secret_name)
    if not credential:
        blocker = resource_blocker(host, prefix, None)
        blocker["missing"] = [f"environment variable {secret_name} (the secret named by the record) is unset in this job"]
        return blocker, EXIT_BLOCKER
    auth_header = credential if credential.lower().startswith(("bearer ", "basic ")) else f"Bearer {credential}"
    ratified = {i["upstream_ref"].split("/", 1)[1]: i for i in record["authoritative_digests"]["images"]}
    results = []
    for e in pins["base_images"]:
        r = ratified.get(e["repository"] + ":" + e["tag"]) or ratified.get(f'{e["repository"]}:{e["tag"]}')
        if r is None:
            results.append({"repository": e["repository"], "tag": e["tag"], "status": "not_ratified"})
            continue
        results.append(verify_one(e, r, host=host, prefix=prefix, auth_header=auth_header, fetch=fetch))
    statuses = {r["status"] for r in results}
    if statuses == {"conforms"}:
        outcome, code = OUTCOME_CONFORMS, EXIT_CONFORMS
    elif statuses & {"mismatch", "not_ratified", "refused_upstream_host"}:
        outcome, code = OUTCOME_MISMATCH, EXIT_MISMATCH
    else:
        outcome, code = OUTCOME_UNREACHABLE, EXIT_MISMATCH
    return {"outcome": outcome, "mirror": {"registry_host": host, "repository_prefix": prefix,
                                           "secret_name": secret_name},
            "results": results, "gates": "NOT_EXECUTED" if code else "PULL_AUTHORIZED"}, code


def build_contexts(record: dict, pins: dict) -> list[str]:
    """``--build-context`` overrides that make the unchanged Dockerfile FROMs resolve
    through the mirror, still by the ratified digest. Nothing is re-pinned."""

    host, prefix, _ = mirror_coordinates(record)
    ratified = {i["upstream_ref"].split("/", 1)[1]: i for i in record["authoritative_digests"]["images"]}
    out, seen = [], set()
    for e in pins["base_images"]:
        key = f'{e["repository"]}:{e["tag"]}'
        r = ratified[key]
        short = key.split("library/", 1)[-1]
        target = f'{_mirror_ref(host, prefix, e["repository"])}@{r["manifest_digest"]}'
        arg = f"--build-context={short}@{r['manifest_digest']}=docker-image://{target}"
        if arg not in seen:
            seen.add(arg)
            out.append(arg)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print("usage: verify_mirror_digest.py <record.json> <pins.json> <out.json> [--print-build-args]",
              file=sys.stderr)
        return 2
    record = json.load(open(argv[1], encoding="utf-8"))
    pins = json.load(open(argv[2], encoding="utf-8"))
    _, _, secret_name = mirror_coordinates(record)
    redact = Redactor([os.environ.get(secret_name, "")] if secret_name else [])
    report, code = verify(record, pins, environ=os.environ)
    with open(argv[3], "w", encoding="utf-8") as fh:
        fh.write(redact(json.dumps(report, indent=2)) + "\n")
    print(redact(json.dumps(report, indent=2)))
    if code == EXIT_CONFORMS and "--print-build-args" in argv:
        print(redact(" ".join(build_contexts(record, pins))))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
