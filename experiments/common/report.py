"""Markdown report builder — replaces hand-assembled result files.

Standard structure: STATUS/caveat header, sections, tables, decision, and an
auto reproducibility-metadata block. Reports are generated from execution, not
hand-written.
"""
from __future__ import annotations

import json


class ReportBuilder:
    def __init__(self, title: str, status_caveat: str):
        self._lines: list[str] = [f"# {title}", "", f"> {status_caveat}", ""]

    def section(self, title: str) -> "ReportBuilder":
        self._lines += [f"## {title}", ""]
        return self

    def para(self, text: str) -> "ReportBuilder":
        self._lines += [text, ""]
        return self

    def bullets(self, items) -> "ReportBuilder":
        self._lines += [f"- {it}" for it in items]
        self._lines.append("")
        return self

    def table(self, headers, rows) -> "ReportBuilder":
        self._lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        self._lines.append("|" + "---|" * len(headers))
        for r in rows:
            self._lines.append("| " + " | ".join(str(c) for c in r) + " |")
        self._lines.append("")
        return self

    def decision(self, verdict: str) -> "ReportBuilder":
        self._lines += [f"> **DECISION: {verdict}**", ""]
        return self

    def repro_block(self, metadata: dict) -> "ReportBuilder":
        self.section("Reproducibility metadata")
        flat = {k: v for k, v in metadata.items() if k not in ("config", "output_sha256")}
        self.table(["field", "value"], [(k, v) for k, v in flat.items()])
        if metadata.get("config"):
            self._lines += ["Config:", "```json",
                            json.dumps(metadata["config"], indent=2, default=str), "```", ""]
        if metadata.get("output_sha256"):
            self.table(["output", "sha256"],
                       [(k, v) for k, v in metadata["output_sha256"].items()])
        return self

    def footer(self, text: str = "structure, not validated meaning.") -> "ReportBuilder":
        self._lines += [f"> {text}"]
        return self

    def build(self) -> str:
        return "\n".join(self._lines).rstrip() + "\n"

    def write(self, path) -> str:
        md = self.build()
        with open(path, "w") as f:
            f.write(md)
        return md
