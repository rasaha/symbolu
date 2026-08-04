"""Registry: metadata only, secret rejection, integrity, fingerprint, empty registry."""

from __future__ import annotations

import pytest

from ugence_llm_steering_controller import CandidateRegistry, RegistryError, validate_registry
from ugence_llm_steering_controller.registry import _FORBIDDEN_KEY_PATTERNS


@pytest.mark.parametrize("secret_key", ["api_key", "API_KEY", "openai_api_key", "secret",
                                        "bearer_token", "client_secret", "aws_secret_access_key",
                                        "authorization", "private_key", "session_token"])
def test_secret_like_keys_rejected(secret_key):
    payload = {
        "providers": [{"provider_id": "p", secret_key: "x"}],
        "models": [{"model_id": "m", "provider_id": "p"}],
    }
    with pytest.raises(RegistryError):
        CandidateRegistry.from_dict(payload)


def test_nested_secret_rejected():
    payload = {
        "providers": [{"provider_id": "p", "meta": {"nested": {"access_key": "k"}}}],
        "models": [{"model_id": "m", "provider_id": "p"}],
    }
    ok, problems = validate_registry(payload)
    assert not ok and problems


def test_duplicate_model_id_rejected():
    payload = {
        "providers": [{"provider_id": "p"}],
        "models": [{"model_id": "m", "provider_id": "p"}, {"model_id": "m", "provider_id": "p"}],
    }
    with pytest.raises(RegistryError):
        CandidateRegistry.from_dict(payload)


def test_model_unknown_provider_rejected():
    payload = {"providers": [{"provider_id": "p"}],
               "models": [{"model_id": "m", "provider_id": "nope"}]}
    with pytest.raises(RegistryError):
        CandidateRegistry.from_dict(payload)


def test_empty_registry_is_valid_but_yields_no_candidate():
    reg = CandidateRegistry.from_dict({"providers": [], "models": []})
    assert len(reg) == 0
    ok, problems = validate_registry({"providers": [], "models": []})
    assert ok and not problems


def test_fingerprint_is_stable_and_content_addressed():
    a = CandidateRegistry.from_dict({"providers": [{"provider_id": "p"}],
                                     "models": [{"model_id": "m", "provider_id": "p"}]})
    b = CandidateRegistry.from_dict({"models": [{"model_id": "m", "provider_id": "p"}],
                                     "providers": [{"provider_id": "p"}]})
    assert a.fingerprint() == b.fingerprint()  # key order independent
    c = CandidateRegistry.from_dict({"providers": [{"provider_id": "p"}],
                                     "models": [{"model_id": "m2", "provider_id": "p"}]})
    assert a.fingerprint() != c.fingerprint()


def test_models_and_providers_sorted():
    reg = CandidateRegistry.from_dict({
        "providers": [{"provider_id": "z"}, {"provider_id": "a"}],
        "models": [{"model_id": "y", "provider_id": "a"}, {"model_id": "b", "provider_id": "z"}],
    })
    assert [p.provider_id for p in reg.providers] == ["a", "z"]
    assert [m.model_id for m in reg.models] == ["b", "y"]


def test_forbidden_key_patterns_cover_common_secrets():
    joined = " ".join(_FORBIDDEN_KEY_PATTERNS)
    for token in ("api_key", "secret", "token", "credential", "private_key", "cert"):
        assert token in joined
