# Determinism

Determinism is the central guarantee of this tooling: identical approved input
plus an identical compiler version yields an identical logical result. This
document explains the mechanisms that make that true.

## Canonical JSON

All digest-bearing and reproducible artifacts are serialized as **canonical
JSON** (`serialization/`) with **sorted keys**. Canonical serialization removes
key-ordering and formatting variability, so two logically identical structures
produce byte-identical JSON and therefore identical digests.

## Content addressing

Workflow IR node ids are **content-addressed**: a node id is the SHA-256 over its
`kind`, `capability`, and the sorted ids of its input objects (see
`WORKFLOW_IR.md`). Edges carry a deterministic `order`. Audit events form a
canonical SHA-256 digest chain (see `AUDIT_SCHEMA.md`). Identity is derived from
content, never from wall-clock time or insertion order.

## The compiled package

A compiled package (`compiler/release.py`) is a fixed set of canonical JSON
files:

- `manifest.json`
- `policy_pack.json`
- `workflow_ir.json`
- `capability_manifest.json`
- `assurance_manifest.json`
- `coverage_matrix.json`
- `audit_schema.json`
- `approval_record.json`
- `validation_report.json`
- `structural_digest.json`

## Logical digest exclusions

The **logical** package digest deliberately **excludes volatile inputs**:

- release timestamps, and
- lifecycle status.

Because these are excluded, the logical digest reflects only the substance of the
compiled result. Identical approved input compiled by the same compiler version
produces an identical logical digest — a property that is verified. Release
timestamps are recorded separately, as metadata, so provenance of *when* a
release happened is retained without contaminating *what* was released.

## Reproducibility

Reproducibility extends to distribution: the built wheel is bit-for-bit
reproducible and the sdist is content-reproducible (see `INSTALL.md` and
`SECURITY_AND_FAILURE_MODEL.md`). Combined with canonical serialization and
content addressing, this gives an end-to-end reproducible chain from approved
policy pack to installable artifact.

Determinism is not incidental — validation rejects `NON_DETERMINISTIC_VALUE`
findings (see `VALIDATION_MODEL.md`) precisely to keep this guarantee intact.
