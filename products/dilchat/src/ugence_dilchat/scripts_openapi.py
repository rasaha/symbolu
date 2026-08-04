"""Generate the OpenAPI document for the running app (no DB connection needed).

Usage:
    dilchat-openapi [output_path]
Prints to stdout if no path is given.
"""

from __future__ import annotations

import json
import sys

from .app import create_app


def build_openapi() -> dict:
    app = create_app()
    return app.openapi()


def main() -> None:
    doc = build_openapi()
    # Safety guard: this phase must never expose a Guna Milan route.
    for path in doc.get("paths", {}):
        if "guna" in path.lower():
            raise SystemExit(f"Refusing to emit OpenAPI: forbidden guna route present: {path}")
    output = json.dumps(doc, indent=2, sort_keys=True)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            fh.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
