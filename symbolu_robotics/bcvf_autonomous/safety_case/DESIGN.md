# BCVF Autonomous — SOTIF / ISO 26262 Traceability Template

## §1 Why this exists

The brief's Q3 line item — *"SOTIF / ISO 26262 traceability
template"* — is now mostly mapping work, not new code. Every
artifact a clause-by-clause walk-through needs already lives in the
repo:

* The seven characterization families are the **HA inputs**
  (SOTIF clause 6).
* `FAMILY_MAGNITUDES` + the 1320-cell primary grid are the
  **triggering-condition table** (SOTIF clause 7).
* The per-step `TrustShapedEpisodeRecord` is the **post-incident
  trace** (SOTIF clause 10 + ISO 26262 Part 6 §11).
* The V2 Schmitt-trigger + the V2 chatter-immunity sweep are the
  **functional-insufficiency mitigation argument** (SOTIF clause 8).
* The fleet harness (`FleetSummary`, `find_near_vetoes`) is the
  **field-monitoring evidence pack** (SOTIF clause 10).

Pulling this from Q3 to Q2 unlocks BD conversations that would
otherwise wait until "after the safety case is ready" — the safety
case is what a deployment partner authors against their own
operational design domain, but the **artifacts that ground each
clause** are what we ship today.

## §2 What this template IS

* A regulator-facing index from BCVF artifacts to ISO 21448
  (SOTIF) clauses 5–10 and ISO 26262 Part 6 §7–11.
* A Python data model (`safety_case.traceability`) with a
  `TraceabilityMatrix` builder + a deterministic markdown renderer.
* A pinned snapshot — `SOTIF_TRACEABILITY.md` in this directory —
  emitted by `render_markdown(build_traceability_matrix())`. The
  snapshot is byte-identical to the renderer's output; if a future
  refactor moves an artifact, the doc-render test fails until
  someone re-runs the snapshot generator.
* A reverse index — for any single artifact, the list of clauses
  it grounds.

## §3 What this template IS NOT

* Not a deployment-ready safety case. The deployment partner
  authors the safety case against their operational design domain.
  This template lets them start that authoring on day one with the
  technical evidence pre-mapped instead of waiting for a separate
  workstream.
* Not an exhaustive standards survey. SOTIF clauses 4 / 11 / 12
  and ISO 26262 Parts 1–5 / 7–12 are out of scope per §6.
* Not a substitute for a regulator workshop. The Q3 brief item
  remains "template + workshop"; this commit lands the template
  half ahead of schedule.

## §4 Maintenance contract

The traceability matrix is the **single source of truth**. The
markdown snapshot ships in the repo for human readers, but it is
machine-generated and machine-checked:

1. To add or move an artifact: edit the relevant
   `EvidenceArtifact` constant in `traceability.py`. Run
   `python -c "from symbolu_robotics.bcvf_autonomous.safety_case
   import build_traceability_matrix, render_markdown; print(
   render_markdown(build_traceability_matrix()))" >
   safety_case/SOTIF_TRACEABILITY.md` to refresh the snapshot.
2. The doc-render test (`tests/test_safety_case.py`) compares the
   on-disk snapshot to the renderer's output and fails if they
   diverge.
3. The artifact-resolution test imports every `module_path` and
   looks up every `symbol`; a renamed module / removed symbol
   fails the test rather than silently invalidating a clause's
   evidence.
4. The clause-coverage test asserts every clause carries at least
   one evidence artifact and every artifact is referenced by at
   least one clause — neither orphaned clauses nor orphaned
   artifacts can sneak in.

## §5 Standards covered

| Standard | Clauses mapped |
|---|---|
| ISO 21448 (SOTIF) | 5, 6, 7, 8, 9, 10 |
| ISO 26262 Part 6 (Software) | §7, §8, §9, §9.4.4, §10, §11 |

Twelve clauses total, indexing nineteen unique BCVF artifacts.

## §6 Out-of-scope clauses

* SOTIF clause 4 (definitions), clause 11 (release-to-the-market
  criteria), clause 12 (process-related considerations) —
  governance items owned by the deployment partner.
* ISO 26262 Part 6 §5 (general topics), §6 (initiation) — process-
  layer items established by the deployment partner's QM
  organisation.
* ISO 26262 Parts 1–5, 7–12 — system / hardware / production
  lifecycle outside the software-arbitration boundary BCVF
  occupies.
