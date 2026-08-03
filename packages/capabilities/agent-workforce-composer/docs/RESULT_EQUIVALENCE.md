# v1/v2 Result Equivalence (P2.1)

`compare_adaptations` and `compare_workforce_plans` classify how a
`v1 + full overlay` adaptation relates to a `v2 + reduced overlay` adaptation:
`BYTE_IDENTICAL`, `SEMANTICALLY_EQUIVALENT`, `INTENTIONALLY_DIFFERENT`,
`INCOMPATIBLE`.

For the four Governance Studio P3A scenarios (committed conformance fixtures under
`conformance/governance_studio_v2/`):
- node dispositions: **BYTE_IDENTICAL**;
- adaptation and plan outcome: **SEMANTICALLY_EQUIVALENT** (assignments, eligibility
  fills, fallbacks, permissions, non-agent nodes identical; raw fingerprints differ
  because v2 carries richer provenance and a different source contract);
- zero intentional differences, zero incompatibilities.

Fingerprint strategy: v1 fingerprints are unchanged; v2 adaptation fingerprints are
versioned and include v2 semantic inputs; a semantic-equivalence fingerprint compares
the planning projection and is equal for equivalent v1/v2 inputs. Byte identity is
never claimed where only semantic equivalence holds.
