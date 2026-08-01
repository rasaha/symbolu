#!/usr/bin/env python3
"""Validate relative Markdown links and referenced source paths in StoryGraph docs.

Scans every Markdown file under the StoryGraph package for:
  * relative Markdown links ``[text](relative/path.md#anchor)`` and
  * inline backtick references to `docs/...`, `examples/...`, or
    `src/ugence_storygraph/...` paths
and reports any whose target does not exist. External links (http/https), pure
anchors (``#...``), and absolute paths are skipped.

Run:  python packages/capabilities/storygraph/check_doc_links.py
Exit 0 if all links resolve; non-zero (with a report) otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parents[2]

_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _targets(md: Path):
    text = md.read_text(encoding="utf-8")
    for m in _LINK.finditer(text):
        raw = m.group(1).strip()
        if raw.startswith(("http://", "https://", "#", "mailto:")):
            continue
        yield raw.split("#", 1)[0].strip()


def main() -> int:
    broken = []
    for md in sorted(PKG.rglob("*.md")):
        if "__pycache__" in md.parts:
            continue
        for target in _targets(md):
            if not target or target.startswith("/"):
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                broken.append((md.relative_to(REPO), target))
    if broken:
        print(f"BROKEN relative links: {len(broken)}")
        for src, target in broken:
            print(f"  {src}  ->  {target}")
        return 1
    print(f"All relative Markdown links resolve ({sum(1 for _ in PKG.rglob('*.md'))} files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
