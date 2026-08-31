# Implementation Scope — Implementation B

## Implemented (drives the mandatory corpus)
Package/config load + independent fingerprint gate; descriptor/integrity; modality dispatch; strict
raw-JSON scanner (BOM, UTF-8, duplicate keys at any depth from raw bytes, surrogate escapes, number
grammar, depth/field/string limits, recipe + base64 reconstruction); content tokenization with the
published function-word classes; lemmatization (irregular table + suffix rules + identity); explicit
mapping validation; staged correspondence (explicit→exact→structured→lexical, integer-pair rational
Jaccard vs 0.35/0.85); structural fidelity (status/uncertainty/provenance/citation/counter-evidence);
Unicode confusable/invisible dispositions (reject / strip-and-flag / normalize) with NFC; bounded
segmentation + assertion identification (interrogative, imperative, heading, code-fence, zero-assertion);
§8.1 aggregation; evaluation-summary counts; non-redacted + redacted trace (pointer+hash); projection
Π + hash; deterministic replay.

## Bounded / not implemented (honest)
- Imperative detection uses a closed lead-word set (resources do not fully pin it); BASE-MD is the
  conformance subset the mandatory corpus needs.
- The 4 informative categories (MEANING_DISTORTION, CERTAINTY_OVERSTATEMENT, SCOPE_EXPANSION,
  QUALIFICATION_OMISSION) are engine-level and not implemented — B abstains, non-gate.
- No artifact generation/repair, completeness evaluation, operational disposition, external fact
  checking, LLM, embedding model, or network.
