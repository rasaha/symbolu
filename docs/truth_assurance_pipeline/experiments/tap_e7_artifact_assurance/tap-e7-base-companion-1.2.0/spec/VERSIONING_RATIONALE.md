# Versioning Rationale — why v1.2.0

## Classification: B — Normative clarification (binding previously-inferred behavior)
The additions are not pure prose about unrelated matters, and they are not error fixes to existing
documents. They **bind, as normative text, behavior that v1.1.1 only made inferable**: the exact
config-fingerprint serialization and the projection-Π field set. Both were independently
reverse-engineered by Implementations A and B and by the independent review — all three matched, so
the behavior was already determinate, but it was not *published* as binding.

## Why MINOR (1.2.0), not PATCH (1.1.2) and not MAJOR
- **Not MAJOR:** no runtime semantic changes. Thresholds, taxonomy, precedence, correspondence
  stages, Unicode/JSON behavior, grammar, fixtures, expected outputs, derivations, runtime
  resources, the config-fingerprint *value*, Π *semantics*, and both corpora are byte-identical to
  v1.1.1. `resource_root`, `schema_root`, `corpus_root`, and `config_fingerprint` are unchanged.
- **Not PATCH:** the release adds **new normative surface** (four normative specifications + one
  normative schema + an interoperability profile). A PATCH conventionally fixes defects in existing
  normative text without adding new binding requirements. Adding new binding documents is a MINOR,
  backward-compatible feature addition.
- **Therefore MINOR → v1.2.0.** `package_root` changes solely because documentation files were added
  to the sealed file set; this is the expected and only hash change.

## Backward compatibility
Any implementation that conformed to v1.1.1 conforms to v1.2.0 unchanged: v1.2.0 forbids nothing
that v1.1.1 permitted and requires no new runtime behavior. The new documents only make the existing
requirements reproducible without inference.
