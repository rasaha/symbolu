"""Data model + matrix builder for the SOTIF / ISO 26262 traceability map.

Three pieces:

* :class:`Standard` — enum of the standards we map (SOTIF, ISO 26262 Part 6).
* :class:`Clause` — one clause-or-subclause we explicitly cover, with the
  short auditor-facing requirement statement and the BCVF evidence
  artifacts that ground it.
* :class:`EvidenceArtifact` — one importable BCVF surface: a module path
  plus an optional symbol name. The artifact's importability is
  pinned by ``test_safety_case`` so a future refactor that moves
  the symbol fails the suite loudly rather than silently invalidating
  the safety-case mapping.

The matrix is built top-down from :func:`iso_21448_clauses` and
:func:`iso_26262_part6_clauses`; each clause carries its own evidence
list, so the reverse index ("which clauses does this artifact serve?")
is computed from the same source — no duplicated bookkeeping.
"""

from __future__ import annotations

import importlib
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Standard(Enum):
    """Safety standards covered by the traceability matrix."""

    SOTIF_21448 = "ISO 21448 (SOTIF)"
    ISO_26262_PART_6 = "ISO 26262 Part 6 (Software)"


@dataclass(frozen=True)
class EvidenceArtifact:
    """One BCVF surface that grounds a clause.

    ``module_path`` must be importable; ``symbol`` (if given) must be
    an attribute of the imported module. ``test_safety_case`` exercises
    both invariants so a renamed module / removed symbol surfaces as
    a test failure rather than a silent traceability gap.
    """

    module_path: str
    symbol: Optional[str] = None
    description: str = ""

    @property
    def reference(self) -> str:
        if self.symbol:
            return f"{self.module_path}::{self.symbol}"
        return self.module_path

    def resolve(self) -> object:
        """Import the module (and look up the symbol if specified)."""
        module = importlib.import_module(self.module_path)
        if self.symbol is None:
            return module
        if not hasattr(module, self.symbol):
            raise AttributeError(
                f"module {self.module_path!r} has no attribute {self.symbol!r} "
                "— traceability matrix is stale"
            )
        return getattr(module, self.symbol)


@dataclass(frozen=True)
class Clause:
    """One clause / subclause covered by the matrix."""

    standard: Standard
    clause_id: str           # e.g. "6", "7.4.4", "Part 6 §9.4.4"
    title: str               # short auditor-facing label
    requirement: str         # one-sentence summary of what the clause asks
    evidence: Tuple[EvidenceArtifact, ...]
    notes: str = ""          # caveats / scope limits


@dataclass(frozen=True)
class TraceabilityEntry:
    """One row of the rendered matrix (one clause)."""

    clause: Clause


@dataclass
class TraceabilityMatrix:
    """Full traceability matrix grouped by standard."""

    entries_by_standard: Dict[Standard, List[TraceabilityEntry]] = field(
        default_factory=dict
    )

    def all_clauses(self) -> List[Clause]:
        return [
            entry.clause
            for entries in self.entries_by_standard.values()
            for entry in entries
        ]

    def all_artifacts(self) -> List[EvidenceArtifact]:
        seen: Dict[str, EvidenceArtifact] = {}
        for clause in self.all_clauses():
            for art in clause.evidence:
                seen.setdefault(art.reference, art)
        return list(seen.values())

    def reverse_index(self) -> Dict[str, List[Clause]]:
        """Map artifact reference → clauses it serves."""
        out: Dict[str, List[Clause]] = defaultdict(list)
        for clause in self.all_clauses():
            for art in clause.evidence:
                out[art.reference].append(clause)
        return dict(out)


# --------------------------------------------------------------------------- #
# Evidence-artifact constants — single source of truth for module paths
# --------------------------------------------------------------------------- #
# Centralising these makes the matrix lighter to read AND lets the test
# suite walk a flat list when verifying importability. If a future
# refactor moves an artifact, exactly one constant changes.

_BCVF_KERNEL = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.core",
    symbol="compute_bcvf_cost",
    description="BCVF cost kernel (SE(2) body-frame disagreement, "
                "second-order, gate × pseudo-Huber)",
)
_BCVF_CONFIG = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.core",
    symbol="BCVFConfig",
    description="Kernel configuration dataclass — gate threshold, β, "
                "Huber δ, lever arm, cost order",
)
_MANIFOLD = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.manifold",
    symbol="body_frame_error_trajectory",
    description="SE(2) body-frame error primitive — the kernel's "
                "signal definition",
)
_TRACES = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.characterization.traces",
    symbol="generate_trace",
    description="Seven-family synthetic SE(2) trace generator — the "
                "named hazards (baseline, constant_bias, linear_drift, "
                "accelerating, noise_floor, outlier, sensor_dropout)",
)
_FAMILY_MAGNITUDES = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.characterization.sweep",
    symbol="FAMILY_MAGNITUDES",
    description="Per-family magnitude grids — the discrete triggering-"
                "condition table the sweep scans",
)
_ACCEPTANCE_TABLE = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.characterization.sweep",
    symbol="_evaluate_thresholds",
    description="Per-family acceptance thresholds — pass / fail rule "
                "table the sweep enforces (DESIGN.md §4)",
)
_PRIMARY_GRID = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.characterization.sweep",
    symbol="run_primary_grid",
    description="22 configs × 60 seeds = 1320-cell certification grid; "
                "drives the per-config Wilson-CI floor",
)
_SUMMARIZE_GRID = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.characterization.sweep",
    symbol="summarize_grid",
    description="Aggregator emitting per-config Wilson 95% CI low/high, "
                "min_ci_lower_bound, cells_below_certification_floor",
)
_WILSON_CI = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.characterization.stats",
    symbol="wilson_ci",
    description="Wilson score CI primitive (closed-form, no scipy) — "
                "the stated statistical bound's machinery",
)
_BASELINES = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.baselines",
    symbol="run_shootout",
    description="Apples-to-apples baseline shootout — BCVF vs EKF "
                "(Mahalanobis-rejection) vs Majority-Vote vs Anchor "
                "across the seven families",
)
_PILOT = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.pilot",
    symbol="run_pilot",
    description="§6.2 paired A0 vs A3 pilot runner — sign test + "
                "Wilson CI + FleetSummary + Lemma-1 negative-control gate",
)
_TRUST_DIAG = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.trust_diagnostics",
    symbol="TrustShapedEpisodeRecord",
    description="Per-step trust diagnostic record — every tick's "
                "weights, BCVF cost, V2 state, near-veto incidence; "
                "the post-incident trace a recall investigator opens",
)
_FLEET = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.analysis",
    symbol="FleetSummary",
    description="Fleet-scale aggregator over episode records — argmax-"
                "flips per step, near-vetoes, V2 state distribution, "
                "per-predictor exclusion incidence; the field-monitoring "
                "evidence pack",
)
_NEAR_VETO = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.analysis.near_veto",
    symbol="find_near_vetoes",
    description="Near-veto detector — flags ticks where a predictor "
                "approached but did not cross the exclusion threshold; "
                "the SOTIF triggering-condition near-miss surface",
)
_CONSUMER_V2 = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.trust",
    symbol="ConsumerV2Config",
    description="Schmitt-trigger consumer V2 — engage / disengage "
                "thresholds + dwell-time hysteresis (chatter-immunity "
                "argument)",
)
_V2_SWEEP = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.v2_chatter_sweep",
    symbol="run_v2_promotion_decision",
    description="Paired V1-vs-V2 promotion-gate sweep — Wilson CI on "
                "chatter rate + exact one-sided McNemar on rescue "
                "preservation; documents the chatter-immunity claim",
)
_CHARACTERIZATION_DESIGN = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.characterization",
    symbol="run_primary_grid",
    description="Characterization DESIGN.md §4 (per-family thresholds) "
                "+ §6.1 (Wilson CI floor) — the readable safety contract",
)
_RUNNER = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.runner",
    symbol="Runner",
    description="Closed-loop scenario runner — module integration test "
                "harness exercising kernel + planner + trust + V2",
)
_BICYCLE = EvidenceArtifact(
    module_path="symbolu_robotics.bcvf_autonomous.predictors.base",
    symbol="BicycleConfig",
    description="Vehicle dynamics + predictor interface — the system "
                "boundary the kernel arbitrates over",
)


# --------------------------------------------------------------------------- #
# ISO 21448 (SOTIF) clauses 5–10
# --------------------------------------------------------------------------- #


def iso_21448_clauses() -> List[Clause]:
    """SOTIF clauses 5 through 10 grounded in BCVF artifacts.

    Coverage scope:

    * Clauses 5 / 6 / 7 are the audit-priority items the brief calls
      out (HA inputs, triggering-condition table, system specification).
    * Clause 8 covers Lemma-1 functional insufficiencies + the V2
      mitigation.
    * Clauses 9 / 10 cover V&V + field monitoring (the artifact pack
      a buyer looks for once the spec is signed off).

    Clauses outside 5–10 (e.g. 4 — definitions; 11 — release-to-the-
    market criteria) are intentionally not enumerated here: the
    Q3-pulled-to-Q2 work is the regulator-facing mapping for the
    technical artifacts we ship today, not the full safety-case
    document a deployment partner authors.
    """
    s = Standard.SOTIF_21448
    return [
        Clause(
            standard=s,
            clause_id="5",
            title="Functional and system specification",
            requirement=(
                "Define the function under analysis, its operational "
                "design domain, and the boundary at which inputs / "
                "outputs are exchanged with the rest of the system."
            ),
            evidence=(
                _BCVF_KERNEL, _BCVF_CONFIG, _MANIFOLD, _BICYCLE,
            ),
            notes=(
                "BCVF is specified as an arbitration function over M "
                "predictor SE(2) trajectories on a fixed horizon H. "
                "Inputs: ``(M, H, 3)`` predictor tensor. Outputs: "
                "``(H, 3)`` consensus + ``(M,)`` per-predictor "
                "attribution. The kernel is dimensionally explicit "
                "(weight matrix in m / rad), deterministic, and "
                "fp64-stable — see DESIGN.md §1 + §2."
            ),
        ),
        Clause(
            standard=s,
            clause_id="6",
            title="Hazard identification and risk evaluation (HARA)",
            requirement=(
                "Enumerate the named classes of inputs whose mishandling "
                "could lead to hazardous behaviour, and assess the "
                "associated risk."
            ),
            evidence=(_TRACES, _CHARACTERIZATION_DESIGN),
            notes=(
                "The seven characterization families ARE the named "
                "hazard inputs at the predictor-arbitration interface: "
                "``baseline``, ``constant_bias``, ``linear_drift``, "
                "``accelerating``, ``noise_floor``, ``outlier``, "
                "``sensor_dropout``. Each has an explicit polarity "
                "(must-be-quiet vs must-fire) and a formal generator "
                "in ``characterization/traces.py`` so a HARA reviewer "
                "can re-execute and inspect every input class."
            ),
        ),
        Clause(
            standard=s,
            clause_id="7",
            title="Identification and evaluation of triggering conditions",
            requirement=(
                "Identify discrete triggering conditions for each "
                "named hazard and evaluate the system response across "
                "the magnitude range of interest."
            ),
            evidence=(_FAMILY_MAGNITUDES, _PRIMARY_GRID, _NEAR_VETO),
            notes=(
                "``FAMILY_MAGNITUDES`` is the discrete triggering-"
                "condition table — e.g. ``accelerating`` is evaluated "
                "at ``accel_mag ∈ {0.1, 0.3, 0.5, 1.0}``. The primary "
                "grid evaluates every (family, magnitude) cell at 60 "
                "seeds and emits a per-cell pass / fail verdict with "
                "Wilson 95% CI lower bound. ``find_near_vetoes`` is "
                "the runtime triggering-condition near-miss surface "
                "for fielded data."
            ),
        ),
        Clause(
            standard=s,
            clause_id="8",
            title="Identification of functional insufficiencies + mitigations",
            requirement=(
                "Identify functional insufficiencies of the intended "
                "function (cases where it does not respond as required) "
                "and document mitigations."
            ),
            evidence=(_CONSUMER_V2, _V2_SWEEP),
            notes=(
                "Insufficiency #1 — Lemma 1 invariance (intentional): "
                "the SECOND-order kernel does not fire on constant "
                "offset or linear drift. Documented as a desired "
                "specification property; the ablation grid confirms "
                "the invariance is exact (ZEROTH / FIRST orders fire, "
                "SECOND does not). Insufficiency #2 — per-tick chatter "
                "on borderline disagreements where V1 softmin can flip "
                "argmax across consecutive ticks. Mitigation: V2 "
                "Schmitt-trigger consumer (``ConsumerV2Config``) with "
                "engage / disengage thresholds + dwell-time hysteresis. "
                "The v0.6 V2 promotion-decision sweep documents the "
                "non-promotion finding and the Q2 recalibration scope."
            ),
        ),
        Clause(
            standard=s,
            clause_id="9",
            title="Verification and validation of SOTIF",
            requirement=(
                "Verify and validate that the function's response to "
                "named hazards meets the stated acceptance criteria, "
                "with quantified statistical confidence."
            ),
            evidence=(
                _PRIMARY_GRID, _SUMMARIZE_GRID, _WILSON_CI,
                _BASELINES, _PILOT, _ACCEPTANCE_TABLE,
            ),
            notes=(
                "V&V is layered: (i) deterministic threshold gates "
                "per family (``_evaluate_thresholds``); (ii) per-config "
                "Wilson 95% CI lower bound floor of 0.90 across the "
                "1320-cell grid (``CERTIFICATION_FLOOR``); (iii) "
                "apples-to-apples baseline shootout against EKF / "
                "Majority / Anchor; (iv) §6.2 paired A0 vs A3 pilot "
                "with one-sided sign test + Wilson CI on win rate. "
                "Three sabotage tests in the suite confirm V&V would "
                "fail on a broken kernel rather than silently passing."
            ),
        ),
        Clause(
            standard=s,
            clause_id="10",
            title="Methodology — operational design and field monitoring",
            requirement=(
                "Define the methodology for monitoring the system in "
                "the field and feeding observed triggering conditions "
                "back into hazard analysis."
            ),
            evidence=(_TRUST_DIAG, _FLEET, _NEAR_VETO),
            notes=(
                "Per-tick ``TrustShapedEpisodeRecord`` is the structured "
                "post-incident trace a recall investigator opens. "
                "``FleetSummary`` aggregates across episodes — argmax-"
                "flips, near-vetoes, V2 state distribution, per-"
                "predictor exclusion incidence — exactly the surface a "
                "fleet-scale safety-monitoring tool consumes. Dataset "
                "ingest is strict (no silent zero-fill on incomplete "
                "payloads) so a corrupt episode surfaces as ``ValueError`` "
                "at load time rather than as a quiet metric drift."
            ),
        ),
    ]


# --------------------------------------------------------------------------- #
# ISO 26262 Part 6 — Software safety lifecycle (selected clauses)
# --------------------------------------------------------------------------- #


def iso_26262_part6_clauses() -> List[Clause]:
    """ISO 26262 Part 6 selected clauses — the software-side mapping.

    We enumerate the clauses where BCVF artifacts are the natural
    evidence: §7 (software safety requirements), §8 (architectural
    design), §9 (unit design + verification), §10 (integration +
    verification), §11 (verification of software safety requirements).
    Earlier clauses (§5 general topics, §6 initiation) are governance-
    layer items the deployment partner owns.
    """
    s = Standard.ISO_26262_PART_6
    return [
        Clause(
            standard=s,
            clause_id="Part 6 §7",
            title="Specification of software safety requirements",
            requirement=(
                "Derive software safety requirements from the system-"
                "level safety concept and document the verification "
                "criteria for each."
            ),
            evidence=(_ACCEPTANCE_TABLE, _CHARACTERIZATION_DESIGN),
            notes=(
                "Per-family acceptance tables in "
                "``_evaluate_thresholds`` are the software-level "
                "safety requirements, with explicit numeric thresholds "
                "per family + the alignment criterion. Each requirement "
                "carries a ``failure_reasons`` label so an auditor can "
                "trace a failed cell back to the specific gate that "
                "fired."
            ),
        ),
        Clause(
            standard=s,
            clause_id="Part 6 §8",
            title="Software architectural design",
            requirement=(
                "Specify the software architecture, including module "
                "decomposition, interfaces between modules, and "
                "dependencies between modules."
            ),
            evidence=(_BCVF_KERNEL, _RUNNER, _CONSUMER_V2),
            notes=(
                "Modules: kernel (``core.py``), trust shaping "
                "(``trust.py``), planner (``mppi_planner.py``), "
                "diagnostics (``trust_diagnostics.py``), runner "
                "(``runner.py``), analysis (``analysis/``). Interfaces "
                "are typed dataclasses (``BCVFConfig``, ``RunConfig``, "
                "``ConsumerV2Config``); each module ships a DESIGN.md."
            ),
        ),
        Clause(
            standard=s,
            clause_id="Part 6 §9",
            title="Software unit design and implementation",
            requirement=(
                "Implement each software unit per the architectural "
                "design and the unit-level safety requirements."
            ),
            evidence=(_BCVF_KERNEL, _CONSUMER_V2, _TRUST_DIAG),
            notes=(
                "Units are ASIL-style isolated: kernel has zero "
                "external dependencies beyond NumPy, V2 hysteresis is "
                "a pure state machine, diagnostics are a pure "
                "recorder. Determinism: every unit is fp64-stable + "
                "RNG-deterministic (seed-in / output-out)."
            ),
        ),
        Clause(
            standard=s,
            clause_id="Part 6 §9.4.4",
            title="Software unit verification methods",
            requirement=(
                "Verify each software unit against its design + safety "
                "requirements using methods appropriate for the ASIL "
                "(boundary values, equivalence classes, error guessing, "
                "structural coverage)."
            ),
            evidence=(
                _PRIMARY_GRID, _SUMMARIZE_GRID, _WILSON_CI,
                _ACCEPTANCE_TABLE,
            ),
            notes=(
                "Boundary values: every family magnitude is evaluated "
                "at four points spanning the threshold-edge (e.g. "
                "``accel_mag ∈ {0.1, 0.3, 0.5, 1.0}``). Equivalence "
                "classes: the seven families are the equivalence-class "
                "partition of input shapes. Structural coverage: 1320 "
                "cells × per-(family, magnitude) Wilson 95% CI lower "
                "bound floor 0.90 — every unit-level acceptance "
                "criterion is exercised at N=60 with a stated "
                "statistical bound (see ``CERTIFICATION_FLOOR``)."
            ),
        ),
        Clause(
            standard=s,
            clause_id="Part 6 §10",
            title="Software integration and integration verification",
            requirement=(
                "Integrate software units per the architectural "
                "design and verify the integrated software behaves "
                "as specified."
            ),
            evidence=(_RUNNER, _PILOT, _BASELINES),
            notes=(
                "End-to-end integration: ``Runner`` exercises kernel + "
                "trust + V2 + planner across canonical scenarios "
                "(S1 nominal, S3 map-error-accel, etc.). ``run_pilot`` "
                "wires the same trust pipeline to a dataset adapter "
                "for paired A0 vs A3 evaluation. ``run_shootout`` "
                "integrates BCVF with three baseline arbitrators "
                "(EKF, Majority, Anchor) over the seven families."
            ),
        ),
        Clause(
            standard=s,
            clause_id="Part 6 §11",
            title="Verification of software safety requirements",
            requirement=(
                "Demonstrate the integrated software meets every "
                "software safety requirement, with traceable evidence."
            ),
            evidence=(
                _SUMMARIZE_GRID, _PILOT, _FLEET, _TRUST_DIAG,
            ),
            notes=(
                "Requirement-by-requirement traceability: each "
                "per-family threshold maps to a passing test in "
                "``test_characterization.py``; each pilot-level "
                "acceptance gate (Lemma-1 negative control, "
                "responsive-class win rate, attribution accuracy) "
                "maps to a passing test in ``test_pilot.py``; each "
                "fleet-level metric is round-trip-tested via "
                "``analysis.io`` strict serialisation."
            ),
        ),
    ]


# --------------------------------------------------------------------------- #
# Matrix builder + renderer
# --------------------------------------------------------------------------- #


def build_traceability_matrix() -> TraceabilityMatrix:
    matrix = TraceabilityMatrix()
    matrix.entries_by_standard[Standard.SOTIF_21448] = [
        TraceabilityEntry(clause=c) for c in iso_21448_clauses()
    ]
    matrix.entries_by_standard[Standard.ISO_26262_PART_6] = [
        TraceabilityEntry(clause=c) for c in iso_26262_part6_clauses()
    ]
    return matrix


def render_markdown(matrix: TraceabilityMatrix) -> str:
    """Render the matrix as the ``SOTIF_TRACEABILITY.md`` shipped on disk.

    The output is deterministic — same matrix in, same string out — so
    a test can pin the on-disk doc to ``render_markdown(...)`` and a
    drift between the doc and the matrix shows up as a test failure
    rather than a silent inconsistency.
    """
    lines: List[str] = []
    lines.append("# SOTIF (ISO 21448) + ISO 26262 Part 6 — BCVF traceability")
    lines.append("")
    lines.append(
        "Generated from "
        "``symbolu_robotics.bcvf_autonomous.safety_case.build_traceability_matrix``."
    )
    lines.append(
        "Do not hand-edit this file — update the matrix in "
        "``traceability.py`` and the doc-render test will refresh "
        "this snapshot."
    )
    lines.append("")
    lines.append(
        "**Scope.** This is the regulator-facing index from BCVF "
        "artifacts to the standard clauses they ground. It is *not* "
        "a deployment-ready safety case — that document is authored "
        "by the deployment partner against their specific operational "
        "design domain. The matrix exists so a buyer's safety team "
        "can begin a clause-by-clause walk-through on day one of a "
        "diligence engagement, instead of waiting for a separate "
        "safety-case workstream."
    )
    lines.append("")
    lines.append("## Index")
    lines.append("")
    for std in matrix.entries_by_standard:
        lines.append(f"* {std.value}")
        for entry in matrix.entries_by_standard[std]:
            lines.append(
                f"  * Clause **{entry.clause.clause_id}** — "
                f"{entry.clause.title}"
            )
    lines.append("")

    for std, entries in matrix.entries_by_standard.items():
        lines.append(f"## {std.value}")
        lines.append("")
        for entry in entries:
            c = entry.clause
            lines.append(f"### Clause {c.clause_id} — {c.title}")
            lines.append("")
            lines.append(f"**Requirement.** {c.requirement}")
            lines.append("")
            lines.append("**Evidence artifacts.**")
            for art in c.evidence:
                lines.append(f"* `{art.reference}` — {art.description}")
            lines.append("")
            if c.notes:
                lines.append(f"**Notes.** {c.notes}")
                lines.append("")

    lines.append("## Reverse index — artifact → clauses served")
    lines.append("")
    lines.append("| Artifact | Clauses |")
    lines.append("|---|---|")
    reverse = matrix.reverse_index()
    for ref in sorted(reverse.keys()):
        clause_ids = ", ".join(c.clause_id for c in reverse[ref])
        lines.append(f"| `{ref}` | {clause_ids} |")
    lines.append("")
    lines.append("## Out-of-scope clauses (intentionally not enumerated)")
    lines.append("")
    lines.append(
        "* SOTIF clauses 4 (definitions), 11 (release-to-the-market "
        "criteria), 12 (process-related considerations) — governance "
        "items owned by the deployment partner."
    )
    lines.append(
        "* ISO 26262 Part 6 §5 (general topics) and §6 (initiation) — "
        "process-layer items established by the deployment partner's "
        "QM organisation."
    )
    lines.append(
        "* ISO 26262 Parts 1–5, 7–12 — system / hardware / production "
        "lifecycle outside the software-arbitration boundary BCVF "
        "occupies."
    )
    return "\n".join(lines) + "\n"
