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
