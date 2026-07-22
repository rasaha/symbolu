# Implementation Scope

## Implemented (drives the mandatory corpus)
Package/config loading and fingerprint gate; descriptor/integrity validation; modality dispatch;
strict raw-JSON validation (duplicate-key/BOM/UTF-8/surrogate/number/depth/field/string limits, with
recipe + base64 reconstruction); content tokenization with the published function-word classes;
lemmatization (irregular table + suffix rules + identity fallback); explicit-mapping validation;
staged correspondence (explicit → exact → structured → lexical) with exact-rational Jaccard against
`T_reject=0.35` / `T_accept=0.85`; structural fidelity (status upgrade, uncertainty suppression,
provenance/citation mismatch, misleading-contradiction omission); Unicode confusable/invisible
dispositions (reject / strip-and-flag / normalize); bounded sentence segmentation and
assertion/non-assertion classification (interrogative, imperative/instruction, heading, code-fence,
zero-assertion); deterministic outcome aggregation (§8.1); evaluation-summary counting;
AssuranceTrace + redacted trace (pointer+hash); normalized projection Π + hash; deterministic replay.

## Bounded / heuristic (documented)
- Imperative/instruction detection uses a small closed lead-word set plus "shares no record entity"
  — sufficient for the mandatory security fixtures; the published resources do not fully pin
  imperative detection (noted as a spec gap, not a silent assumption).
- BASE-MD handling is a conformance subset: it detects unsupported/malformed constructs (raw HTML,
  comments, malformed reference definitions) and strips headings/code fences; it does not implement
  the full inline/block grammar (not required by the mandatory corpus).

## Deliberately NOT implemented (out of scope per the task and/or engine-level)
- Artifact generation, repair, or wording recommendations; completeness evaluation; operational disposition.
- The 4 informative categories (MEANING_DISTORTION, CERTAINTY_OVERSTATEMENT, SCOPE_EXPANSION,
  QUALIFICATION_OMISSION) — engine-level semantic comparison not derivable from published resources;
  the verifier abstains and reports them on the informative (non-gate) track.
- Deep coreference, full typed-scope comparison, and attribution/endorsement semantics beyond what the
  mandatory corpus exercises.

No online model, embedding model, LLM correspondence, or external entity knowledge is used anywhere.
