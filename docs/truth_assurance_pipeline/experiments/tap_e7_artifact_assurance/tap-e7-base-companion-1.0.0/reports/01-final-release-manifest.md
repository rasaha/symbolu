# TAP-E7-BASE Companion Package v1.0.0 — Final Release Manifest

- **release_id:** `tap-e7-base-companion/1.0.0`
- **target_specification:** `tap-e7-assurance/1.0.0`
- **target_profile:** `tap-e7-base/1.0`
- **canonicalization:** `tap-canon/1`
- **state:** `complete-package-1.0.0`
- **manifest file:** `manifest/release-manifest.json` = `sha-256:4c68592ae6faf536e48cc73e978afc2eb994592c29cfe7a2706452d4427c33ff`

## Package roots (independently recomputed, byte-for-byte)

| root | sha-256 |
| --- | --- |
| resource_root | sha-256:9dc04e9b582e86e7f9ed8b649ef3a905e785afb0254c47fb249dded272e4f826 |
| schema_root | sha-256:68f57fd7e7408dfba472a9c3603f1d127e7450d8af9b0a3c73e46cc793062a01 |
| corpus_root | sha-256:58f71d2f22bfd5295a11b3bbbe5e36901a11945b00c201265b688f074a62b73c |
| config_fingerprint | sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734 |
| package_root | sha-256:f9a520305324c0de5052869ebf641067e3698f5f407807f0d4cabe235a463cb3 |


> `config_fingerprint_note`: corpus_root EXCLUDED from runtime config_fingerprint (corpus membership is not runtime configuration)

## Inventory (counts)

| item | count |
| --- | --- |
| ENG-CORE tokens | 127 |
| abbreviations | 42 |
| confusable rows | 18 |
| invisible codepoints | 16 |
| conformance fixtures | 142 |
| normative resource files | 44 |
| JSON schemas (of the above) | 6 |
| total files in package | 336 |


The `manifest/release-manifest.json` object enumerates every normative file with
its `sha256`, `normative`, and `outcome_affecting` flags. `manifest/release-manifest.json`,
`hashes/package-root.txt`, and `hashes/sha256sums.txt` are derived-last artifacts and are
therefore not self-listed (a manifest cannot contain its own digest); every other file is listed.
