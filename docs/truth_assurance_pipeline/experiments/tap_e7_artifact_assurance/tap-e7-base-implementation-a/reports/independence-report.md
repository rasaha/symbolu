# Independence Report

## Authoring independence
`src/verifier.py` was written from the normative resources, importing none of the v1.1.0
builder/auditor/validator tooling (enumerated in `DEPENDENCY_BOUNDARY.md`). It re-implements
strict-JSON validation, tokenization, lemmatization, Jaccard, Unicode dispositions, correspondence
staging, fidelity, §8.1 aggregation, evaluation-summary counting, and projection Π from scratch.

## Blind execution (enforced)
`tools/run_blind_conformance.py` installs a guarded `open()` that raises on any read of `expected/`
or `derivations/` while the verifier runs. `results/blind-proof.json` records
`blind_boundary_intact: true` with an empty list of expected/derivation reads. The blind loader
passes the verifier only `{modality, validation_record, artifact, profile_ref, release_ref}` — every
expected/metadata field (expected, phenomenon, purpose, group, authoritative, derivation_ref) is
stripped first.

## Identity-independence (negative tests, §28)
Security tests confirm the result is a pure function of input bytes + resources: re-evaluating the
same submission yields an identical projection hash regardless of any fixture-identity metadata
(which the verifier never receives). A deliberately false expected result would be caught by
`compare_expected.py`, which recomputes the verdict independently rather than trusting stored values.

## Not a second implementation
Per §34, Implementation A plus the builder/auditors/validator do **not** constitute multiple
independent implementations. A clean-room Implementation B is specified in
`implementation-b-handoff.md` and is out of scope for this task.
