from governance_studio_deployment.passwords import hash_password, verify_password, is_valid_hash_format


def test_hash_verify_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong", h)


def test_hash_is_salted_and_self_describing():
    a = hash_password("same")
    b = hash_password("same")
    assert a != b  # random salt
    assert a.startswith("scrypt$")
    assert is_valid_hash_format(a)


def test_invalid_formats_rejected():
    assert not is_valid_hash_format("")
    assert not is_valid_hash_format("plaintext")
    assert not is_valid_hash_format("scrypt$notanumber$8$1$x$y")
    assert not verify_password("x", "garbage")


def test_empty_password_rejected():
    import pytest
    with pytest.raises(ValueError):
        hash_password("")
