# Known limitations

- TAP evaluates **supplied evidence**; it does **not** establish objective truth.
- TAP does **not** authorize or execute actions, and does **not** replace a final
  business decision.
- TAP does **not** implicitly fetch unrestricted enterprise data.
- Fail-safe infrastructure handling produces **INDETERMINATE**, not approval.
- The reference engine is **deterministic**; deterministic reference behavior is
  **not** equivalent to legal, factual, or domain correctness.
- Remote operation requires **independently secured transport and authentication**.
- **Packaging verification is not production certification.**
  `version_info().production_certified` is `False`.
