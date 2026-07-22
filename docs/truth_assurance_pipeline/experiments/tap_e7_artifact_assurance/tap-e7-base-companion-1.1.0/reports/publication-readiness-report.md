# TAP-E7-BASE Companion Package v1.1.0 — Publication-Readiness Report

## Quality gate (§26) — every item confirmed against reproduced evidence

| Gate condition | Status |
| --- | --- |
| No mandatory fixture is label-only | PASS (byte auditor: 0 label-only mandatory) |
| Each expected result tied to actual input bytes | PASS (derivation auditor: 86/86) |
| Jaccard threshold fixtures contain mathematically correct token sets | PASS (7/20…18/20) |
| Malformed JSON encoded as raw bytes / recipe | PASS (JS01–JS22) |
| Depth and size fixtures genuinely cross their limits | PASS (depth 65, fields 100001, string 1048577) |
| Unicode attacks contain the claimed code points | PASS (U+03BF/0441/200B/200C/202E/202B/00A0/00E9/0301) |
| Explicit-map defects exist in the mapping structures | PASS (EM01–EM05) |
| Determinism pairs use distinct relevant representations | PASS (distinct bytes, equal canonical/NFC) |
| Privacy fixtures contain real redacted/non-redacted traces | PASS (PR01–PR06) |
| Redacted traces contain no prohibited raw content | PASS (redaction scan: 0 leaks) |
| Security fixtures contain actual attacks | PASS (embedded payloads) |
| Fixture derivations present | PASS (one per fixture) |
| All mandatory requirements mapped | PASS (84/84) |
| All roots reproduce | PASS (5/5 recomputed) |
| Runtime fingerprint excludes corpus membership | PASS |
| Original v1.0.0 intact | PASS (separate committed directory, untouched) |
| No frozen runtime semantic changed | PASS (0 RUNTIME_RESOURCE_CHANGE; config_fingerprint identical) |
| No normative placeholder remains | PASS (0) |

## Final counts
- Total files: 90 fixtures + 90 expected + 86 derivations + resources/grammar/schemas
  (reused from v1.0.0 except the extended fixture schema) + 3 manifests + 5 hash artifacts + reports.
- Changed vs v1.0.0: 562 files (all new corpus/expected/derivation, manifests, hashes, 1 schema).
- Fixtures 90 (mandatory 86, informative 4); corrected/replaced: the entire corpus was rebuilt
  from real bytes (the v1.0.0 label-only fixtures are superseded, not patched in place).
- Expected results: 90.  Derivation records: 86 (mandatory) + carried for informative.
- Mandatory requirements: 84 — all passing byte reproducibility and bounded semantic derivation.
- JSON parser branch fixtures: 22.  Unicode security fixtures: 9 (+3 in SEC).  Determinism
  pairs: 10.  Privacy fixture pairs: 6.  Jaccard boundary fixtures: 6.
- Finding-category coverage: 14/14.  Outcome distribution: ASSURED 40, INDETERMINATE 38, NOT_ASSURED 12.
- Hash verification: all manifest/fixture/expected/derivation digests + 5 roots reproduce.
- Placeholder scan: 0.

## Full 64-char hashes
```
resource_root      a6ab878888a5cc98e660fc18b9d8da603cdf999c9989b2a5b1b40acfdc10d175
schema_root        d1f1a95c70e75b1f58453fef43022a99ef349fde4f834e4286cbff629783bcc8
corpus_root        642e7ecbbdb03508a12589961741a13ed1ccf9398b784889c2c4b57cde7ee5b1
config_fingerprint d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734
package_root       bff7685055fb99e9bec1ebfe3cec150f56540cd16421d36f40962ade9975f5ff
```

## Conclusion
- **Publication verdict: 2** — publication-complete subject to the explicitly listed
  non-semantic residuals (no second implementation yet; four engine-dependent taxonomy
  categories carried as informative). The mandatory conformance corpus is now a valid oracle:
  every mandatory fixture is byte-reproducible and its expected result is independently
  re-derivable from the bytes under the frozen rules.
- **Maturity: Stable promotion not yet supported** — two independent conforming TAP-E7
  implementations must still pass this corpus. A builder + auditors are not two implementations.
