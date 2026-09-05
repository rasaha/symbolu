"""Second-pass helper: read the rendered PDF, find the page of every TOC entry, write toc_pages.json.

Usage: python docs/tooling/capability_pipeline/paginate.py <pdf>
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "docs", "UGENCE_ENTERPRISE_AI_GOVERNANCE_CAPABILITY_PIPELINE.md")
pdf = sys.argv[1]
n = int(re.search(r"Pages:\s+(\d+)", subprocess.check_output(["pdfinfo", pdf]).decode()).group(1))
pages = []
for i in range(1, n + 1):
    txt = subprocess.check_output(["pdftotext", "-f", str(i), "-l", str(i), "-layout", pdf, "-"]).decode("utf-8", "replace")
    pages.append(re.sub(r"\s+", " ", txt))
entries = []
for ln in open(SRC, encoding="utf-8").read().split("\n"):
    m = re.match(r"^(#{1,2})\s+(.*)$", ln)
    if m and not ln.startswith("# Ugence Enterprise"):
        entries.append(m.group(2).strip())
# the contents page itself lists every heading; skip pages that contain "Contents" heading block
skip = {i for i, t in enumerate(pages) if "Contents" in t and entries[0] in t and entries[-1] in t}
result = {}
cursor = 0
for e in entries:
    key = re.sub(r"\s+", " ", e)
    found = None
    for i in range(cursor, n):
        if i in skip:
            continue
        if key in pages[i]:
            found = i
            break
    if found is None:  # fall back: search from start, ignoring the TOC page
        for i in range(n):
            if i not in skip and key in pages[i]:
                found = i
                break
    if found is not None:
        result[e] = found + 1
        cursor = found
json.dump(result, open(os.path.join(HERE, "toc_pages.json"), "w"), indent=1, ensure_ascii=False)
missing = [e for e in entries if e not in result]
print("entries", len(entries), "resolved", len(result), "missing", missing)
