# Independence Declaration — TAP-E7-BASE Implementation A

Implementation A was authored clean-room from the published normative resources of the
v1.1.0 package. It consumes only `(ValidationRecord, CandidateArtifact, descriptor envelope)`
and produces an `AssuranceRecord`. Dispatch never reads fixture id, group, purpose,
phenomenon, or authoritative flag — those fields are stripped by the blind loader before the
verifier is invoked.

## Prohibited reuse (inspected and NOT imported)
The following v1.1.0 tooling exists in `tap-e7-base-companion-1.1.0-tooling/` and is prohibited
from reuse. Implementation A imports none of it:
- `build_11.py` — corpus builder / expected-result generation.
- `audit_bytes_11.py` — byte-reproducibility auditor.
- `audit_deriv_11.py` — normative-derivation auditor.
- `validate_pkg_11.py` — packaging validator.
- `primitives.py` — the builder/auditor shared canonicalization layer.
- `gen_reports_11.py` — report generator.
- `derivations/*.json` — never read as executable logic (and never read at all during blind execution).
- `expected/*.json` — never read during blind execution (filesystem-guarded).

## What Implementation A re-implemented independently
Strict-JSON validation, content tokenization, lemmatization, Jaccard (exact rational),
Unicode confusable/invisible dispositions, correspondence staging, structural fidelity,
§8.1 outcome aggregation, evaluation-summary counting, projection Π, trace/redaction.
Each was written fresh in `src/verifier.py`; none was copied from the builder/auditors.

## Permitted shared inputs (read-only, data not code)
Normative resource files, grammar, schemas, fixture inputs, and package manifests — read from
the package at `docs/.../tap-e7-base-companion-1.1.0/`. Generic utilities (UTF-8 read, JSON,
SHA-256, canonical ordering) are implemented locally in `src/verifier.py` and unit-tested.

## Blind boundary (enforced, not asserted)
`tools/run_blind_conformance.py` wraps `open()` and raises `PermissionError` if the verifier
attempts to read `expected/` or `derivations/` during evaluation. Proof of zero such reads is
recorded in `results/blind-proof.json` (`blind_boundary_intact: true`).

## Not a second implementation
Implementation A, the corpus builder, the auditors, and the packaging validator are NOT four
independent implementations. Stable promotion still requires a genuinely separate
Implementation B (clean-room handoff in `reports/implementation-b-handoff.md`).
