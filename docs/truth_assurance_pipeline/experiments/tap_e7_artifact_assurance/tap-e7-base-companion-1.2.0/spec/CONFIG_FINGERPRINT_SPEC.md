# Runtime Config Fingerprint — Specification (normative)

Binds the previously-inferred construction of `roots.config_fingerprint`. An independent
implementer must be able to reproduce the published value from **this document + the package
manifests alone**, with no reference to any implementation. Uses TAP-CANON/1 (see CANONICALIZATION.md).

## 1. Purpose
The fingerprint identifies the exact set of **runtime, outcome-affecting configuration** an
implementation binds before evaluating any artifact. It is a gate: an implementation must recompute
it and refuse to run if it differs from `manifest/release-manifest.json → roots.config_fingerprint`.

## 2. Participating files (and only these)
The fingerprint is computed over the entries of `manifest/resource-manifest.json` whose
`outcome_affecting` field is `true`. In v1.2.0 that is exactly **39** files:
- all `resources/**` files,
- both `grammar/**` files,
- `schemas/strict-json-profile.json` (the one schema that constrains runtime JSON acceptance).

## 3. Files that never participate
- `corpus/**` — corpus membership is content, not runtime configuration.
- `expected/**`, `derivations/**` — oracle data, not runtime configuration.
- `reports/**`, `spec/**` — documentation.
- `manifest/**`, `hashes/**` — derived indices.
- `schemas/*.schema.json` (the 5 structural schemas) — they validate fixture shape, not runtime outcome; `outcome_affecting=false`.
- any implementation directory (`tap-e7-base-implementation-*`) — outside the package.

## 4. Canonical inputs
- **Paths:** exactly as stored in `resource-manifest.json` — forward-slash, package-relative, no leading `./`.
- **Per-file `sha256`:** exactly as stored in `resource-manifest.json` (each is SHA-256 over the file's raw bytes; empty files → SHA-256 of the empty string; no line-ending normalization).
- **Ordering:** the participating entries in **ascending path order** (the resource-manifest is stored sorted; filter to `outcome_affecting=true` preserving that order).
- **Duplicate paths:** none permitted; the manifest paths are unique.

## 5. Fingerprint object and hash
```
FP = {
  "target_spec":       release-manifest.target_specification,   // "tap-e7-assurance/1.0.0"
  "target_profile":    release-manifest.target_profile,          // "tap-e7-base/1.0"
  "canonicalization":  release-manifest.canonicalization,        // "tap-canon/1"
  "thresholds":        { "T_accept": 0.85, "T_reject": 0.35 },
  "runtime_resources": [ { "path": <p>, "sha256": <h> } for each participating entry, in path order ]
}
config_fingerprint = digest(FP)          // = "sha-256:" + hex(SHA-256( canonical_json(FP) + "\n" ))
```
`canonical_json` and `digest` are defined in CANONICALIZATION.md. Note the object is hashed via
canonical JSON (keys sorted), so the literal key order above is immaterial; the value order of
`runtime_resources` **is** significant and is path-ascending.

## 6. Reference
Over v1.2.0 (byte-identical to v1.1.1):
`config_fingerprint = sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734`.
Adding `spec/` documentation does not change this value because `spec/` files are not in
`resource-manifest.json` and are not `outcome_affecting`.
