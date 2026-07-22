# Implementation B — Architecture

- **Language:** JavaScript on Node.js v22 (stdlib only: `fs`, `path`, `crypto`, `TextDecoder`, `String.prototype.normalize`).
- **Style:** functional pipeline of pure modules — deliberately different from Implementation A's Python class-based design.

## Pipeline (ValidationRecord + CandidateArtifact → AssuranceRecord)
1. `loadResources(pkg)` — one immutable object of frozen tables (confusables, invisibles, POS classes, irregular lemmas, ENG-CORE).
2. Descriptor/integrity envelope check → `INPUT_INTEGRITY_FAILURE`.
3. Modality dispatch (`text` / `json`; else `UNSUPPORTED_MODALITY`).
4. **Strict JSON**: an independent raw-byte scanner (`strictJson`) — BOM check, fatal UTF-8 decode, brace-depth scan, number-grammar regexes, a hand-written surrogate-escape check, and a **stack-based duplicate-key scanner over the raw string** (does not trust `JSON.parse`, which erases duplicate keys), then field/string limits.
5. **Text**: reject-codepoint scan → integrity failure; BASE-MD unsupported/malformed scan → processing failure; suspicious-Unicode flag → assertion-level `unresolved`; else segment → correspond.
6. **Correspondence** as staged pure functions: explicit → exact (NFC set-equality) → structured (S/P/O) → lexical (integer-pair rational Jaccard vs 0.35/0.85, no floats).
7. Structural **fidelity** (status/uncertainty/provenance/citation/counter-evidence).
8. `assemble` reducer → findings, §8.1 outcome, evaluation-summary, projection Π + hash.
9. `trace` produces non-redacted and redacted (pointer+hash) traces.

## Determinism
Canonical serialization is a locally implemented stable stringifier (sorted keys); Jaccard uses integer cross-multiplication (`n·td ≥ tn·d`) so threshold decisions never touch binary floats.
