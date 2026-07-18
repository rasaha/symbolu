# ACP Canonical Identity (Phase 0)

Specification of the deterministic identity used for world states, action
candidates, decisions, and control authorizations
(`autonomous_control_plane/identity.py`). This is a narrowly-scoped,
standard-library implementation — **not** a copy of the ActionGate reference
hasher; it implements only what ACP needs and documents its rules explicitly.

---

## 1. Identity function

```
identity(value, *, domain, version=1) -> sha256 hex
  payload = "acp\x1f{domain}\x1fv{version}\x1f" + canonical_json(value)
  return sha256(payload.utf-8).hexdigest()
```

- **`canonical_json`** = `json.dumps(canonicalize(value), sort_keys=True,
  separators=(",",":"), ensure_ascii=True, allow_nan=False)`.
- **Domain separation** — the `domain` label + schema `version` are hashed into a
  prefix delimited by the unit-separator byte `0x1f`, so an action hash can never
  collide with a world-state hash even for an identical payload. Domains in use:
  `world_state`, `predictor_evidence`, `action_candidate`,
  `control_authorization`.

## 2. Canonicalization rules (`canonicalize`)

| type | rule |
|---|---|
| `None`, `bool` | as-is (bool handled before int) |
| `int` | as-is |
| `float` | **reject non-finite** (`NaN`/`±Inf` → `NonFiniteValueError`); normalize `-0.0`→`0.0` |
| `str` | as-is |
| `bytes` | `{"__bytes__": hex}` |
| `Enum` | `{"__enum__": "TypeName.MEMBER"}` |
| dataclass | dict of fields, **excluding** fields tagged `metadata={"identity": False}` |
| `Mapping` | keys **sorted** (order-independent); keys must be `str` |
| `Sequence` (list/tuple) | **order preserved** (order is significant) |
| anything else | `IdentityError` (total: never guesses) |

## 3. Included vs excluded fields

- **Included:** every dataclass field by default.
- **Excluded:** fields explicitly tagged `field(metadata={"identity": False})` —
  currently `CanonicalWorldState.label` and `CanonicalActionCandidate.provenance`
  (free-text/provenance that must not change identity). Nothing is excluded
  implicitly.

## 4. Float handling

- Non-finite values fail loudly at the earliest point: envelope construction
  (`normalize_float` in `__post_init__`) and again in `canonicalize`.
- `-0.0` is normalized to `0.0` so numerically-equal values share an identity.
- Floats are serialized by Python's shortest-round-trip `repr` via `json`; no
  fixed-precision rounding is applied to the identity itself (callers that want
  tolerance must quantize before hashing).

## 5. Array / mapping ordering

- **Sequences preserve order** — a trajectory reference list `[a, b]` ≠ `[b, a]`.
- **Mappings sort keys** — dict insertion order does not change identity
  (`test_dict_insertion_order_irrelevant`).

## 6. Versioning

The `version` argument is part of the hashed prefix. Bumping a schema's version
deliberately invalidates all prior identities for that domain — the intended
mechanism for a breaking envelope-schema change.

## 7. Tests proving the contract (`test_acp_phase0.py`)

| requirement | test |
|---|---|
| identical input → identical identity | `test_identical_input_same_identity` |
| changed trajectory → different identity | `test_changed_trajectory_changes_identity` |
| changed margin/state → different identity | `test_changed_margin_changes_identity`, `test_state_version_change_on_env` |
| map/state-version change invalidates prior authorization | `test_stale_world_state_rejected`, `test_stale_constraint_set_rejected` |
| dict insertion order does not change identity | `test_dict_insertion_order_irrelevant` |
| identity-excluded field does not change identity | `test_identity_excluded_field_does_not_change_identity` |
| domain separation | `test_domain_separation` |
| `-0.0` normalized | `test_negative_zero_normalized` |
| NaN/Inf fail loudly | `TestNonFiniteRejection` (3 tests) |

## 8. Explicit non-claims

- **Not cryptographic.** SHA-256 content identity is for determinism, dedup, and
  drift detection — **not** tamper-proofing. `ControlAuthorization.grant_id` is a
  reference identity, not a signature; production key custody is out of Phase 0.
- **Not float-tolerant.** Two nearly-equal floats hash differently by design;
  quantize upstream if tolerance is required.
