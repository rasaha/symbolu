"""The reference signer is for tests; production refuses it structurally.

Also: no production signer, key loading, key generation, network, filesystem,
environment-variable, credential or discovery code exists anywhere under src/.
"""

from __future__ import annotations

import ast
import pathlib
import pickle

import pytest

import ugence_risk_authority_effect_attestation as ea
from _fixtures import ATTESTED_AT, PROVIDER, TENANT, observation, provider_signer

SRC = pathlib.Path(ea.__file__).resolve().parent


def test_the_reference_signer_is_marked_at_class_level_and_immutable():
    assert ea.ReferenceEd25519EffectAttestationSigner.is_reference_signer is True
    signer = provider_signer()
    with pytest.raises(AttributeError):
        signer.is_reference_signer = False  # type: ignore[misc]
    with pytest.raises(AttributeError):
        signer._signing_key = None  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        pickle.dumps(signer)


def test_production_minting_refuses_the_reference_signer_and_every_subclass_of_it():
    with pytest.raises(ea.EffectAttestationSigningBoundaryError):
        ea.mint_effect_attestation(observation(), signer=provider_signer(), tenant_id=TENANT,
                                   attested_at=ATTESTED_AT, production_mode=True)

    class Disguised(ea.ReferenceEd25519EffectAttestationSigner):
        is_reference_signer = False

    with pytest.raises(ea.EffectAttestationSigningBoundaryError):
        ea.mint_effect_attestation(
            observation(),
            signer=Disguised(b"\x09" * 32, attester_identity="p", attester_key_id="k", attester_role=PROVIDER),
            tenant_id=TENANT, attested_at=ATTESTED_AT, production_mode=True,
        )


def test_a_signer_that_has_not_declared_itself_non_reference_is_refused_in_production():
    class Silent:
        attester_identity = "p"
        attester_key_id = "k"
        attester_role = PROVIDER

        def sign_effect_attestation(self, signed_bytes):
            return "ab" * 64

    with pytest.raises(ea.EffectAttestationSigningBoundaryError):
        ea.mint_effect_attestation(observation(), signer=Silent(), tenant_id=TENANT,
                                   attested_at=ATTESTED_AT, production_mode=True)


def test_a_non_signer_is_refused_in_every_mode():
    for bad in (None, object(), "signer"):
        with pytest.raises(ea.EffectAttestationSigningBoundaryError):
            ea.mint_effect_attestation(observation(), signer=bad, tenant_id=TENANT,  # type: ignore[arg-type]
                                       attested_at=ATTESTED_AT)


def test_minting_refuses_a_naive_instant_and_an_observation_it_cannot_canonicalize():
    from datetime import datetime

    from ugence_governance_contracts import ExecutionBusinessOutcome, ExecutionObservation

    with pytest.raises(ea.EffectAttestationContractError):
        ea.mint_effect_attestation(observation(), signer=provider_signer(), tenant_id=TENANT,
                                   attested_at=datetime(2026, 9, 6, 12, 0))
    non_string = ExecutionObservation(business_outcome=ExecutionBusinessOutcome.SUCCEEDED,
                                      observed_parameters={"amount": 12.5})  # type: ignore[dict-item]
    with pytest.raises(ea.EffectAttestationContractError):
        ea.mint_effect_attestation(non_string, signer=provider_signer(), tenant_id=TENANT,
                                   attested_at=ATTESTED_AT)


def test_no_key_loading_generation_network_filesystem_env_or_discovery_code_exists():
    banned_modules = {"os", "pathlib", "socket", "ssl", "http", "urllib", "secrets", "random",
                      "subprocess", "shutil", "tempfile", "glob", "importlib", "pkgutil",
                      "cryptography", "nacl", "requests", "httpx", "boto3", "kubernetes"}
    banned_calls = {"generate", "generate_private_key", "getenv", "environ", "open", "urlopen",
                    "connect", "listen", "walk", "listdir", "load_pem_private_key",
                    "from_private_bytes", "token_bytes", "urandom"}
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {a.name.split(".")[0] for a in node.names} & banned_modules, path.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                assert node.module.split(".")[0] not in banned_modules, (path.name, node.module)
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                assert name not in banned_calls, (path.name, name)
            elif isinstance(node, ast.Attribute) and node.attr == "environ":
                raise AssertionError(f"{path.name}: reads the environment")


def test_no_clock_is_read_anywhere():
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic", "perf_counter"), (
                    path.name, name)
                if name == "astimezone":
                    assert node.args, f"{path.name}: zero-argument astimezone infers the local zone"


def test_the_only_signer_class_under_src_is_the_reference_one():
    signers = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and "Signer" in node.name and "Port" not in node.name:
                signers.append(node.name)
    assert signers == ["ReferenceEd25519EffectAttestationSigner"]
