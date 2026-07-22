# Final Strict JSON Profile

- **file:** `schemas/strict-json-profile.json` = `sha-256:bf796f7d5aadd5686534ca412f560865b0dccb7b765626fe73747a1e9b472798`

```json
{
  "duplicate_keys": "detected on token stream BEFORE object construction; any duplicate -> INPUT_INTEGRITY_FAILURE",
  "encoding": "UTF-8 only; BOM rejected -> INPUT_INTEGRITY_FAILURE",
  "limit_exceed": "PROCESSING_FAILURE",
  "limits": {
    "max_depth": 64,
    "max_fields": 100000,
    "max_string": 1048576
  },
  "numbers": "RFC8259; NaN/Infinity/leading-zero/leading-plus rejected; canonical decimal; -0 == 0",
  "ordering": "members sorted by JSON Pointer (tap-canon/1)",
  "pointer_escape": "RFC6901",
  "resource_id": "BASE-JSON",
  "surrogates": "valid UTF-16 escape pairs only; lone surrogate -> INPUT_INTEGRITY_FAILURE",
  "version": "1.0"
}
```

The profile fixes the deterministic acceptance boundary for JSON artifacts: duplicate keys,
depth over the fixed bound, field-count and string-length bounds, and non-UTF-8 input each map
to a specific `EVALUATION_LIMITATION` category (`INPUT_INTEGRITY_FAILURE` /
`PROCESSING_FAILURE`), exercised by corpus fixtures A05, A06, A07, C02, C03, F07, J07–J10,
S10, S11, S14.
