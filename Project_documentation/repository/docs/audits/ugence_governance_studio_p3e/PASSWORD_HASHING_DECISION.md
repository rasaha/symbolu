# Password Hashing Decision (P3E completion §5)

**Decision: Argon2id** (preferred path), via the pinned `argon2-cffi`.

The earlier pass fell back to stdlib `scrypt` believing no Argon2 wheel was installable
offline. That was wrong: PyPI is allowlisted by the egress proxy and `argon2-cffi`
installs reproducibly. The deployment now uses Argon2id.

| Property | Value |
|----------|-------|
| Library | `argon2-cffi` (added to deployment dependencies + SBOM + audit) |
| Algorithm | Argon2id |
| Record format | `$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>` (standard encoded) |
| Parameters | time_cost 3 · memory 64 MiB · parallelism 4 · hash 32B · salt 16B |
| Salt | library-managed (random per hash) |
| Verification | library constant-time verify |
| Max accepted (stored hash) | memory ≤ 256 MiB · time ≤ 10 · parallelism ≤ 8 |
| Excessive cost | **rejected before the KDF runs** (DoS-safe) |
| Malformed / unsupported | fail closed |
| Legacy scrypt | verified for migration only; never generated |
| CLI | `generate_password_hash` never prints the password; hash passed only via secret |

Covered by `tests/test_passwords.py` (Argon2id encoding, roundtrip, salted, malformed
rejection, **excessive-cost rejection before KDF**, legacy-scrypt migration verify).

## Migration boundary (honest)

This deployment holds **no persistent credential store** — the password hash is provided
read-only via a secret and verified per request, so the process cannot rewrite it.
`needs_rehash(encoded)` is therefore an **advisory** signal (surfaced to the operator, e.g.
in logs/readiness) returning `True` for a legacy scrypt record or an Argon2id record below
current parameters, so the operator regenerates the hash with `generate_password_hash` and
restarts. It performs **no automatic in-place migration**, and it is consulted only after a
**successful** verification — a failed verification never triggers migration. Tests:
`test_current_argon2id_hash_does_not_need_rehash`,
`test_legacy_scrypt_record_reports_needs_rehash_after_success`,
`test_failed_verification_never_triggers_migration`.
