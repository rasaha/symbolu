#!/usr/bin/env python
"""Genuine image-layer secret scan (P3E §5).

`docker save`s the image, extracts the outer archive, parses its manifest, then
extracts and scans the CONTENT of every referenced layer tar (not just the outer
listing). Also scans the image config (env, labels, history). Writes machine-readable
evidence and exits nonzero on any finding.

    python scan_image_layers.py <image> <out.json>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile

# path patterns that must never appear in a runtime layer
BANNED_PATHS = re.compile(
    r"(^|/)(\.git(/|$)|\.env($|\.)|\.npmrc$|\.pypirc$|\.aws/credentials$|"
    r"id_rsa$|id_ed25519$|.*\.pem$|.*\.key$|node_modules/|__pycache__/.*\.pyc$)"
)
# content patterns (private keys, tokens) scanned in small text-ish files
BANNED_CONTENT = re.compile(
    rb"BEGIN [A-Z ]*PRIVATE KEY|aws_secret_access_key|ghp_[A-Za-z0-9]{20,}|"
    rb"AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,}",
    re.IGNORECASE,
)
ALLOW_PATH = re.compile(r"(^|/)(opt/venv/.*/site-packages/.*\.(pem|key)$)")  # bundled CA stores etc.


def _scan_layer(layer_path: str, findings: list) -> None:
    with tarfile.open(layer_path, "r:*") as tf:
        for member in tf:
            if not member.isfile():
                continue
            name = member.name
            if BANNED_PATHS.search(name) and not ALLOW_PATH.search(name):
                findings.append({"layer": os.path.basename(layer_path), "path": name, "kind": "banned_path"})
            if member.size and member.size <= 262144:  # scan small files for embedded secrets
                try:
                    data = tf.extractfile(member).read()
                except Exception:  # noqa: BLE001
                    continue
                if BANNED_CONTENT.search(data):
                    findings.append({"layer": os.path.basename(layer_path), "path": name, "kind": "secret_content"})


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: scan_image_layers.py <image> <out.json>", file=sys.stderr)
        return 2
    image, out = argv[1], argv[2]
    findings: list = []
    with tempfile.TemporaryDirectory() as tmp:
        tar = os.path.join(tmp, "img.tar")
        subprocess.check_call(["docker", "save", image, "-o", tar])
        with tarfile.open(tar) as tf:
            tf.extractall(tmp)  # noqa: S202 - trusted, locally built image
        manifest = json.load(open(os.path.join(tmp, "manifest.json")))
        layers = manifest[0]["Layers"]
        config_file = manifest[0]["Config"]
        for layer in layers:
            _scan_layer(os.path.join(tmp, layer), findings)
        # config: env / labels / history
        cfg = json.load(open(os.path.join(tmp, config_file)))
        blob = json.dumps(cfg).encode()
        if BANNED_CONTENT.search(blob) or re.search(rb"PASSWORD=|_TOKEN=|SECRET=", blob):
            findings.append({"layer": "config", "path": config_file, "kind": "secret_in_config"})

    report = {"schema": "image-layer-secret-scan.v1", "image": image, "layers_scanned": len(layers),
              "findings": findings, "result": "PASS" if not findings else "FAIL"}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    print(f"layers scanned: {len(layers)} · findings: {len(findings)} · {report['result']}")
    for f in findings:
        print("  FINDING", f, file=sys.stderr)
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
