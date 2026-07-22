# Confidence Adapter Binding (adapter-scoped)

- **adapter file:** `resources/confidence/confidence-adapter.json` = `sha-256:848e28ab8d8980463b346e0b8e2a08628aba787cd5fb3eeb18120cbd1fa47b9a`
- **mapping table:** `resources/confidence/confidence-mapping-table.tsv` = `sha-256:3247f010c47b9d0ca5d2500304c88d9e0724dc7708089894218f9a008c375861`

**Binding status: EXPLICITLY ADAPTER-SCOPED (not a claimed exact upstream binding).**
TAP-E6 does not publish a fully enumerated confidence encoding, so this package binds
confidence through a named, versioned adapter with a frozen band order `NONE < LOW < MEDIUM
< HIGH` and total input coverage: categorical tokens, scalar ∈ [0,1] with fixed cut points,
intervals, and vector-with-overall forms all map to a band, and every malformed/out-of-range/
missing form maps to `INPUT_INTEGRITY_FAILURE`. Corpus group **H (23 fixtures, H01–H23)**
exercises each mapping and each rejection path.

```json
{
  "binding": "adapter-only (E6 confidence encoding not fully published)",
  "forms": {
    "categorical": "table",
    "interval": "map lower bound; record mapping_loss if hi higher",
    "scalar": "intervals",
    "vector": "consume E6 overall min-floored value; never read dimensions"
  },
  "missing": "INPUT_INTEGRITY_FAILURE",
  "order": [
    "NONE",
    "LOW",
    "MEDIUM",
    "HIGH"
  ],
  "overstatement": "expressed>validated -> CERTAINTY_OVERSTATEMENT",
  "resource_id": "BASE-CONF-ADAPTER",
  "unrecognized": "INPUT_INTEGRITY_FAILURE",
  "upstream_clarification_required": [
    "E6 categorical band enumeration+order",
    "or scalar range semantics",
    "and overall-confidence field name/location"
  ],
  "version": "1.0"
}
```

**Minimal upstream clarification required to lift the adapter scope to an exact binding:**
either (a) an enumerated categorical band set with defined order, or (b) scalar semantics
*and* the canonical location of the overall-confidence field in the E6 `ValidationRecord`.
Until E6 publishes one of these, the binding remains adapter-scoped by design; no fixture
outcome depends on an unpublished E6 detail (every H fixture's expectation follows from the
adapter table alone).
