# Normative Inputs actually consumed by Implementation B

Read at runtime from `tap-e7-base-companion-1.1.1/`:
- `resources/normalization/unicode-confusables.tsv`, `.../invisible-codepoints.tsv`
- `resources/language/pos-cues.tsv`, `.../eng-core.txt`
- `resources/normalization/lemmatization-irregular.tsv`
- `manifest/resource-manifest.json`, `manifest/release-manifest.json`, `manifest/corpus-manifest.json`
- `corpus/*.json` (projected to the input envelope only)

Thresholds (T_accept=0.85, T_reject=0.35), correspondence staging, §8.1 precedence, taxonomy, and
polarity are transcribed from the TAP-E7 spec / BASE profile. The runtime config fingerprint is
recomputed from the manifests (not hard-coded) and gated before evaluation.

NOT consumed as authority: Implementation A source/reports/outputs, expected/ or derivations/ (blind),
audit adjudications, or any expected-result generator.
