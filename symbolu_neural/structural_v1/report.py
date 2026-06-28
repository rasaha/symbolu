"""Deterministic structural report (Stage A).

Output is labeled 'structure, not validated meaning' and makes NO claim about
meaning, Sanskrit/varna privilege, or LLM usefulness.
"""
from __future__ import annotations

from . import STRUCTURE_LABEL
from .gate import StageAResult


def render_report(result: StageAResult) -> str:
    lines = []
    lines.append("# STRUCTURAL_V1 — Stage A Structural Report")
    lines.append("")
    lines.append(f"> **{STRUCTURE_LABEL}.** This report establishes structural signal")
    lines.append("> only. It does NOT validate meaning, Sanskrit/varna privilege, or LLM")
    lines.append("> usefulness. Operators are provisional (feature-derived, not estimated).")
    lines.append("")
    lines.append(f"## Verdict: **{result.verdict}**")
    lines.append("")
    lines.append("Stage A PASS = G1 AND G2 AND G3 AND G4.")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append("| gate | result | key numbers |")
    lines.append("|---|---|---|")
    for g in result.gates:
        nums = ", ".join(f"{k}={v:.4f}" for k, v in g.detail.items())
        lines.append(f"| {g.name} | {'PASS' if g.passed else 'FAIL'} | {nums} |")
    lines.append("")
    lines.append("### Gate notes")
    for g in result.gates:
        lines.append(f"- **{g.name}** — {g.note}")
    lines.append("")
    lines.append("## Diagnostics")
    lines.append("")
    for k, v in result.diagnostics.items():
        lines.append(f"- {k}: {v:.4f}")
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    if result.warnings:
        for w in result.warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Interpretation (bounded)")
    lines.append("")
    lines.append(_interpretation(result))
    lines.append("")
    return "\n".join(lines)


def _interpretation(result: StageAResult) -> str:
    v = result.verdict
    if v == "PASS":
        return (
            "A structural signal exists on the provisional, feature-derived operators: "
            "the operator product produces order-dependent structure that beats the bag, "
            "random-orthogonal, and relabel nulls, and the order-effect pattern is "
            "partially factorizable along the pre-registered feature axes. This is an "
            "expressiveness/consistency result about the framework plus a feature-derived "
            "initialization and the structure of the feature chart. It does NOT show the "
            "operators are real, that the order-structure carries meaning, that varna is "
            "privileged over IPA or a random partition, or that any of this is useful to an "
            "LLM. Those require human order-effect data and comparative analyses that are "
            "out of Stage A's scope. " + STRUCTURE_LABEL + "."
        )
    if v == "FAIL":
        failed = [g.name for g in result.gates if not g.passed]
        return (
            f"No qualifying structural signal: gate(s) {', '.join(failed)} failed. "
            "The feature-grounded operator product did not produce inventory-specific, "
            "factorizable order-structure beyond the nulls. This is a structural-null "
            "result; it says nothing for or against meaning, varna privilege, or LLM "
            "usefulness, none of which Stage A tests. " + STRUCTURE_LABEL + "."
        )
    return (
        "Stage A is inconclusive (underpowered or unstable scores); thresholds are not "
        "applied. No structural claim is made. This says nothing about meaning, varna "
        "privilege, or LLM usefulness. " + STRUCTURE_LABEL + "."
    )
