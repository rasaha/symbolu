#!/usr/bin/env python3
"""Render the Ugence collateral markdown into a print-ready PDF.

Converts the generic one-pager and the package IP index into a single styled
HTML document and prints it with headless Chromium. No external Python
dependencies: the markdown subset used by the collateral (headings, tables,
lists, emphasis, code spans, links, rules) is handled here directly.

Usage: python3 scripts/render_collateral_pdf.py [-o OUTPUT.pdf]
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLLATERAL = REPO / "docs" / "collateral"
SOURCES = [
    COLLATERAL / "UGENCE_PLATFORM_ONE_PAGER.md",
    COLLATERAL / "UGENCE_PACKAGE_IP_INDEX.md",
]
CHROME_CANDIDATES = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
]

CSS = """
@page { size: A4 portrait; margin: 12mm 11mm 12mm 11mm; }
* { box-sizing: border-box; }
body {
  font-family: "DejaVu Serif", Georgia, serif;
  font-size: 7.2pt; line-height: 1.28; color: #1f2937;
  margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.doc + .doc { page-break-before: always; }
h1 {
  font-size: 15pt; color: #132a7e; margin: 0 0 2pt 0; letter-spacing: -0.2pt;
}
h1 + .kicker {
  font-size: 8pt; color: #6b7280; font-style: italic;
  margin: 0 0 10pt 0; padding-bottom: 7pt; border-bottom: 1.4pt solid #132a7e;
}
h2 {
  break-after: avoid; page-break-after: avoid;
  font-size: 9.2pt; color: #13337e; margin: 7pt 0 2.5pt 0;
  padding-bottom: 2pt; border-bottom: 0.6pt solid #d6dae6;
}
h3 { font-size: 9pt; color: #13337e; margin: 7pt 0 2.5pt 0; }
p { margin: 0 0 4pt 0; }
ul, ol { margin: 0 0 6pt 0; padding-left: 14pt; }
li { margin: 0 0 2pt 0; }
strong { color: #0b1f4a; }
code {
  font-family: "DejaVu Sans Mono", Consolas, monospace; font-size: 7.4pt;
  background: #eef1f7; padding: 0.5pt 2pt; border-radius: 2pt; color: #12306e;
}
hr { border: 0; border-top: 0.6pt solid #d6dae6; margin: 9pt 0; }
table { width: 100%; border-collapse: collapse; margin: 0 0 6pt 0; font-size: 7.1pt; }
th {
  text-align: left; background: #132a7e; color: #ffffff;
  padding: 2.8pt 4pt; font-size: 7.6pt; letter-spacing: 0.2pt;
}
tr { break-inside: avoid; page-break-inside: avoid; }
thead { display: table-header-group; }
td { padding: 2.6pt 4pt; vertical-align: top; border-bottom: 0.5pt solid #e3e6ee; }
tr:nth-child(even) td { background: #f6f7fb; }
td:first-child { width: 30%; white-space: nowrap; }
.footer {
  margin-top: 10pt; background: #1e4a7e; color: #ffffff; font-size: 6.6pt;
  padding: 3pt 6pt; letter-spacing: 0.6pt; break-inside: avoid;
}
"""

def inline(text: str) -> str:
    """Escape a markdown line, then re-apply the inline constructs we support.

    Code spans are lifted out first so that emphasis inside them — and
    backticks inside emphasis — both survive intact.
    """
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links -> their text
    spans: list[str] = []

    def stash(m: re.Match[str]) -> str:
        spans.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def render(md: str) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i, list_tag, para = 0, None, []

    def flush_para() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            flush_para(); close_list(); i += 1; continue
        if stripped.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|- :"):
            flush_para(); close_list()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        if stripped.startswith("#"):
            flush_para(); close_list()
            level = len(stripped) - len(stripped.lstrip("#"))
            out.append(f"<h{level}>{inline(stripped[level:].strip())}</h{level}>")
            i += 1; continue
        if stripped in {"---", "***"}:
            flush_para(); close_list(); out.append("<hr>"); i += 1; continue
        bullet = re.match(r"[-*]\s+(.*)", stripped)
        number = re.match(r"\d+\.\s+(.*)", stripped)
        if bullet or number:
            flush_para()
            want = "ul" if bullet else "ol"
            if list_tag != want:
                close_list(); out.append(f"<{want}>"); list_tag = want
            item = [(bullet or number).group(1)]
            i += 1
            while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"\s*([-*]|\d+\.)\s", lines[i]):
                item.append(lines[i].strip()); i += 1
            out.append(f"<li>{inline(' '.join(item))}</li>")
            continue
        close_list()
        para.append(stripped)
        i += 1
    flush_para(); close_list()

    body = "\n".join(out)
    # the italic line right under the title is the document kicker
    return re.sub(r"(</h1>\s*)<p><em>(.*?)</em></p>", r'\1<p class="kicker">\2</p>', body, count=1, flags=re.S)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default=str(COLLATERAL / "UGENCE_PLATFORM_OVERVIEW.pdf"))
    args = ap.parse_args()

    chrome = next((c for c in CHROME_CANDIDATES if Path(c).exists()), shutil.which("chromium"))
    if not chrome:
        print("no chromium binary found", file=sys.stderr)
        return 1

    footer = ("<div class='footer'>UGENCE LABS · PLATFORM OVERVIEW · "
              "PRE-REVENUE, PRE-EXTERNAL-DEPLOYMENT</div>")
    docs = "\n".join(f'<div class="doc">{render(p.read_text())}{footer}</div>' for p in SOURCES)
    page = (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Ugence Labs — Platform Overview</title><style>{CSS}</style></head>"
        f"<body>{docs}</body></html>"
    )

    out = Path(args.output).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "collateral.html"
        src.write_text(page)
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
             f"--print-to-pdf={out}", src.as_uri()],
            check=True, capture_output=True, timeout=180,
        )
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
