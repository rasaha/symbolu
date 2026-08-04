#!/usr/bin/env python
"""Resolve base-image digests from the Docker Registry v2 manifest API (P3E §3).

Reads base-images.json, resolves each entry's multi-arch INDEX digest and the exact
linux/amd64 child-manifest digest, and writes a machine-readable resolution report.
Distinguishes: resolved / registry_inaccessible / auth_failure / rate_limited /
dns_or_network_failure. Manifests only — no blob download.

    python resolve_base_images.py <base-images.json> <out.json>

Exit 0 when every entry resolves; 1 otherwise (so a resolver CI job fails loudly).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

AUTH = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"
MANIFEST = "https://registry-1.docker.io/v2/{repo}/manifests/{ref}"
INDEX_ACCEPT = (
    "application/vnd.oci.image.index.v1+json,"
    "application/vnd.docker.distribution.manifest.list.v2+json,"
    "application/vnd.oci.image.manifest.v1+json,"
    "application/vnd.docker.distribution.manifest.v2+json"
)


def _get(url: str, headers: dict, head: bool = False):
    req = urllib.request.Request(url, headers=headers, method="HEAD" if head else "GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        # resp.headers is a case-insensitive HTTPMessage — do NOT dict() it
        return resp.status, resp.headers, (b"" if head else resp.read())


def _token(repo: str) -> str | None:
    try:
        _, _, body = _get(AUTH.format(repo=repo), {})
        return json.loads(body)["token"]
    except Exception:  # noqa: BLE001
        return None


def resolve_one(entry: dict) -> dict:
    repo, tag = entry["repository"], entry["tag"]
    out = {"repository": repo, "tag": tag, "status": "unknown", "manifest_digest": None,
           "amd64_manifest_digest": None, "platform": entry.get("platform", "linux/amd64")}
    token = _token(repo)
    if not token:
        out["status"] = "auth_failure"
        return out
    hdr = {"Authorization": f"Bearer {token}", "Accept": INDEX_ACCEPT}
    try:
        status, headers, _ = _get(MANIFEST.format(repo=repo, ref=tag), hdr, head=True)
        out["manifest_digest"] = headers.get("Docker-Content-Digest")
        _, _, body = _get(MANIFEST.format(repo=repo, ref=tag), hdr)
        index = json.loads(body)
        for m in index.get("manifests", []):
            p = m.get("platform", {})
            if p.get("architecture") == "amd64" and p.get("os") == "linux" and "variant" not in p:
                out["amd64_manifest_digest"] = m["digest"]
        out["status"] = "resolved" if out["manifest_digest"] else "registry_inaccessible"
    except urllib.error.HTTPError as exc:
        out["status"] = "rate_limited" if exc.code == 429 else ("auth_failure" if exc.code in (401, 403) else "registry_inaccessible")
    except urllib.error.URLError:
        out["status"] = "dns_or_network_failure"
    except Exception:  # noqa: BLE001
        out["status"] = "registry_inaccessible"
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: resolve_base_images.py <base-images.json> <out.json>", file=sys.stderr)
        return 2
    pins = json.load(open(argv[1], encoding="utf-8"))
    results = [resolve_one(e) for e in pins["base_images"]]
    report = {"schema": "base-image-resolution.v1", "results": results,
              "all_resolved": all(r["status"] == "resolved" for r in results)}
    with open(argv[2], "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    for r in results:
        print(f"{r['status']:>22}  {r['repository']}:{r['tag']}  index={r['manifest_digest']}  amd64={r['amd64_manifest_digest']}")
    return 0 if report["all_resolved"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
