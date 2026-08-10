# TAP-CANON/1 — Canonicalization (normative)

This document fixes the byte-exact canonicalization used everywhere the package produces a
hash (`config_fingerprint`, `resource_root`, `schema_root`, `corpus_root`, `package_root`,
`projection_pi_sha256`, every per-file digest, and `sha256sums.txt`). It **describes existing
v1.1.1 behavior only**; nothing here is new behavior.

## 1. Canonical JSON
For any JSON value `V`, `canonical_json(V)` is the string produced by serializing `V` with:
- **Key ordering:** object member keys sorted ascending by Unicode code point (equivalently,
  Python `json.dumps(..., sort_keys=True)`; JavaScript `Object.keys().sort()`), applied recursively.
- **Separators:** `","` between elements/members and `":"` between key and value, with **no
  whitespace** anywhere (Python `separators=(",", ":")`).
- **Non-ASCII:** emitted literally as UTF-8 (Python `ensure_ascii=False`); no `\uXXXX` escaping
  of characters that are valid unescaped in a JSON string.
- **String escaping:** only the JSON-required escapes — `\"`, `\\`, and the C0 control escapes
  (`\b \f \n \r \t` and `\u00XX` for other controls). No other escaping.
- **Numbers:** serialized in the shortest round-tripping form of the parsed value; integers have
  no decimal point; `-0` and `0` both serialize as `0`; exponent inputs are serialized as their
  numeric value (e.g. `5e-1` → `0.5`). (All package hash inputs use integer/enum fields only, so
  number formatting never affects a published root.)
- **Booleans / null:** `true`, `false`, `null`.

## 2. Hash input construction
For a JSON value `V`:
```
hash_input(V) = utf8_bytes( canonical_json(V) + "\n" )     # exactly one trailing LF (U+000A)
digest(V)     = "sha-256:" + lowercase_hex( SHA-256( hash_input(V) ) )
```
The trailing newline is **mandatory** and part of every root/fingerprint/Π hash.

## 3. Encoding and Unicode
- All files and all hash inputs are **UTF-8**. No BOM is emitted.
- **Line endings** are **LF (U+000A)** only; files are hashed as stored, with no line-ending
  normalization.
- **Unicode NFC** is applied during *content processing* (tokenization / correspondence input),
  never re-applied during canonical JSON serialization — object string values are hashed exactly
  as stored. This keeps input-normalization (NFC) and output-canonicalization (JSON) as distinct,
  non-interchangeable operations.

## 4. Per-file digest
Every per-file `sha256` in the manifests is `"sha-256:" + lowercase_hex(SHA-256(raw_file_bytes))`
over the file's exact bytes (no normalization). Empty files hash to the SHA-256 of the empty byte
string. This is the value referenced by all root computations.

## 5. Reference values (reproduce these to self-check)
Computed over the v1.2.0 package, these are byte-identical to v1.1.1:
```
config_fingerprint sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734
resource_root      sha-256:a6ab878888a5cc98e660fc18b9d8da603cdf999c9989b2a5b1b40acfdc10d175
schema_root        sha-256:d1f1a95c70e75b1f58453fef43022a99ef349fde4f834e4286cbff629783bcc8
corpus_root        sha-256:f8c83c91c9d5db15e8608ed414784c5c83d0783838ddd48c527c97637130b614
```
