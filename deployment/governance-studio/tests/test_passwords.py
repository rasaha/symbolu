import pytest

from governance_studio_deployment.passwords import (
    hash_password,
    verify_password,
    needs_rehash,
    is_valid_hash_format,
    MAX_ARGON2_MEMORY_COST,
)


def test_hash_is_argon2id_encoded():
    h = hash_password("correct horse battery staple")
    assert h.startswith("$argon2id$")
    assert is_valid_hash_format(h)


def test_hash_verify_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong", h)


def test_hash_is_salted():
    assert hash_password("same") != hash_password("same")  # library-managed random salt


def test_invalid_formats_rejected():
    assert not is_valid_hash_format("")
    assert not is_valid_hash_format("plaintext")
    assert not is_valid_hash_format("$argon2id$garbage")
    assert not verify_password("x", "garbage")
    assert not verify_password("x", "$argon2id$v=19$m=nope,t=3,p=4$c2FsdA$aGFzaA")


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        hash_password("")


def test_excessive_cost_parameters_rejected_before_kdf():
    # a stored hash claiming absurd memory cost must be refused BEFORE the KDF runs
    huge = MAX_ARGON2_MEMORY_COST * 100
    malicious = f"$argon2id$v=19$m={huge},t=3,p=4$c2FsdHNhbHRzYWx0$aGFzaGhhc2hoYXNo"
    assert not is_valid_hash_format(malicious)
    assert not verify_password("anything", malicious)


def test_current_argon2id_hash_does_not_need_rehash():
    h = hash_password("fresh")
    assert verify_password("fresh", h)
    assert needs_rehash(h) is False  # current parameters → no rehash needed


def test_legacy_scrypt_record_reports_needs_rehash_after_success():
    import base64
    import hashlib
    salt = b"0123456789abcdef"
    n, r, p = 2 ** 14, 8, 1
    dk = hashlib.scrypt(b"legacy", salt=salt, n=n, r=r, p=p, dklen=32, maxmem=128 * r * n * 2)
    encoded = f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    # successful legacy verification → rehash-required signal (operator migrates out-of-band)
    assert verify_password("legacy", encoded) is True
    assert needs_rehash(encoded) is True


def test_failed_verification_never_triggers_migration():
    import base64
    import hashlib
    salt = b"0123456789abcdef"
    n, r, p = 2 ** 14, 8, 1
    dk = hashlib.scrypt(b"legacy", salt=salt, n=n, r=r, p=p, dklen=32, maxmem=128 * r * n * 2)
    encoded = f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    # a wrong password must fail; migration is only ever considered on success
    assert verify_password("wrong", encoded) is False


def test_legacy_scrypt_hash_still_verifies():
    # migration: a legacy scrypt record is still accepted by verify (not generated anymore)
    import base64
    import hashlib
    salt = b"0123456789abcdef"
    n, r, p = 2 ** 14, 8, 1
    dk = hashlib.scrypt(b"legacy-pass", salt=salt, n=n, r=r, p=p, dklen=32, maxmem=128 * r * n * 2)
    encoded = f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    assert is_valid_hash_format(encoded)
    assert verify_password("legacy-pass", encoded)
    assert not verify_password("wrong", encoded)
