# TAP-E7 — Artifact Assurance (companion package)

The seventh TAP layer verifies the **fidelity of a candidate artifact to the frozen
`ValidationRecord` produced by TAP-E6 — Claim Validation**. It is *verify-only*
(non-generative) and emits one of three outcomes under a total-order precedence:

- **NOT_ASSURED** — any positive violation, else
- **INDETERMINATE** — any evaluation limitation, else
- **ASSURED**.

This directory holds the **publication-complete conformance companion** for the
`tap-e7-base` profile. It contains no assurance engine — only the normative resources,
grammar, JSON profile, schemas, and a fully concrete conformance corpus with genuinely
computed SHA-256 digests, roots, and a runtime config fingerprint.

## Contents

| Path | Contents |
|---|---|
| [`tap-e7-base-companion-1.0.0/`](tap-e7-base-companion-1.0.0/) | the versioned companion package |
| `…/manifest/` | release / resource / corpus manifests (every file hashed) |
| `…/resources/` | 34 language/normalization/semantics/citation/confidence rulesets |
| `…/grammar/` | self-contained BASE-MD PEG grammar + block semantics |
| `…/schemas/` | 5 JSON schemas + the strict JSON profile |
| `…/corpus/`, `…/expected/` | 142 concrete fixtures + 142 expected results |
| `…/hashes/` | resource/corpus/config/package roots + `sha256sums.txt` |
| `…/reports/` | the 7 publication documents + archived validator stdout |

## Verified roots (recomputed by an independent validator)

```
resource_root      sha-256:9dc04e9b582e86e7f9ed8b649ef3a905e785afb0254c47fb249dded272e4f826
schema_root        sha-256:68f57fd7e7408dfba472a9c3603f1d127e7450d8af9b0a3c73e46cc793062a01
corpus_root        sha-256:58f71d2f22bfd5295a11b3bbbe5e36901a11945b00c201265b688f074a62b73c
config_fingerprint sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734
package_root       sha-256:f9a520305324c0de5052869ebf641067e3698f5f407807f0d4cabe235a463cb3
```

`corpus_root` is **excluded** from `config_fingerprint` (corpus membership is not runtime
configuration).

## Status

**Publication-complete (Option 1).** All 142 fixture outcomes re-derive from the frozen §8.1
precedence; every polarity, count invariant, projection hash, manifest digest, and root was
independently recomputed and matched; the schema graph is acyclic; the grammar is
self-contained; the placeholder scan is clean. The confidence binding is **adapter-scoped**
by necessity (E6 has not published an exact confidence encoding). See
[`…/reports/07-final-publication-validation-report.md`](tap-e7-base-companion-1.0.0/reports/07-final-publication-validation-report.md).
