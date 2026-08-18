"""Private key material cannot reach anything that leaves this process.

The rule, from the milestone brief and ADR DD-10: private signing material
enters only through a narrow signer/key-provider boundary, and never appears in
a ``repr``, in canonical JSON, in an envelope field, in a log line, in an
exception, in a probe, fixture, wheel, sdist or manifest, and is never
retrievable from a verification result.

The strongest guarantee here is structural rather than conventional: the
canonical encoder **rejects ``bytes`` outright**, and no public contract
declares a bytes-typed field, so there is no path by which a seed could reach a
canonical byte sequence or a digest even by mistake.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib

import pytest
from _authority_builders import (
    NON_PRODUCTION_ATTACKER_SEED,
    NON_PRODUCTION_AUTHORITY_SEED,
    NON_PRODUCTION_PRODUCER_SEED,
    NON_PRODUCTION_RFC8032_TEST1_SEED,
    authority_anchor,
    determination,
    envelope,
    issuer,
    producer_anchor,
    reverifier,
    signer,
    submission,
)
from _builders import AS_OF
from ugence_trusted_evidence_authority.api import (
    TrustedEvidenceCanonicalizationError,
    TrustedEvidenceSigningKey,
    TrustedEvidenceVerificationKey,
    audit_record_for_determination,
    audit_record_for_receipt_verification,
    canonical_bytes,
)

import ugence_trusted_evidence_authority as pkg
import ugence_trusted_evidence_authority.api as api

PKG_ROOT = pathlib.Path(pkg.__file__).resolve().parent
SEED = NON_PRODUCTION_AUTHORITY_SEED
SEED_HEX = SEED.hex()


def _every_public_artifact():
    signed = envelope()
    result = determination()
    verification = reverifier().verify(signed, evaluated_at=AS_OF)
    return {
        "envelope": signed,
        "payload": signed.payload,
        "submission": submission(),
        "producer_anchor": producer_anchor(),
        "authority_anchor": authority_anchor(),
        "determination": result,
        "verification": verification,
        "audit_verification": audit_record_for_determination(
            result, tenant_id="tenant-1", envelope=signed
        ),
        "audit_reverification": audit_record_for_receipt_verification(
            verification, signed, tenant_id="tenant-1"
        ),
    }


# --------------------------------------------------------------------------- #
# The seed does not appear anywhere
# --------------------------------------------------------------------------- #

def test_the_signing_key_repr_is_redacted_in_both_directions():
    key = TrustedEvidenceSigningKey(SEED)
    assert repr(key) == "TrustedEvidenceSigningKey(<redacted>)"
    assert str(key) == "TrustedEvidenceSigningKey(<redacted>)"
    assert SEED_HEX not in repr(key)
    assert SEED_HEX not in str(key)
    assert "%r" % (key,) == "TrustedEvidenceSigningKey(<redacted>)"
    assert "{}".format(key) == "TrustedEvidenceSigningKey(<redacted>)"
    assert f"{key}" == "TrustedEvidenceSigningKey(<redacted>)"


def test_the_signer_and_issuer_reprs_carry_coordinates_only():
    for obj in (signer(), issuer()):
        rendered = repr(obj)
        assert SEED_HEX not in rendered
        assert "seed" not in rendered.lower()
        assert "redacted" in rendered or "authority=" in rendered


@pytest.mark.parametrize("name", sorted(_every_public_artifact()))
def test_no_public_artifact_renders_or_canonicalizes_the_seed(name):
    artifact = _every_public_artifact()[name]
    assert SEED_HEX not in repr(artifact), name
    assert SEED_HEX not in str(artifact), name
    if hasattr(artifact, "canonical_bytes"):
        assert SEED_HEX not in artifact.canonical_bytes().decode("utf-8"), name
    if dataclasses.is_dataclass(artifact):
        rendered = json.dumps(dataclasses.asdict(artifact), default=str)
        assert SEED_HEX not in rendered, name


def test_a_seed_is_not_retrievable_from_any_verification_result():
    signed = envelope()
    verification = reverifier().verify(signed, evaluated_at=AS_OF)
    for obj in (signed, verification, determination()):
        for attribute in ("seed", "signing_key", "private_key", "secret",
                          "key_material", "_signing_key"):
            assert not hasattr(obj, attribute), (type(obj).__name__, attribute)


def test_an_exception_from_the_signer_never_carries_the_seed():
    with pytest.raises(Exception) as excinfo:
        signer().sign_receipt(b"not a signing input")
    assert SEED_HEX not in str(excinfo.value)
    assert SEED_HEX not in repr(excinfo.value)
    assert SEED_HEX not in repr(excinfo.traceback[-1])


def test_the_signing_key_is_not_canonicalizable_at_all():
    """The encoder rejects bytes, so a seed cannot reach a digest by mistake."""

    with pytest.raises(TrustedEvidenceCanonicalizationError):
        canonical_bytes(TrustedEvidenceSigningKey(SEED))


def test_no_public_contract_declares_a_bytes_typed_field():
    """The structural guarantee behind every assertion above."""

    from ugence_trusted_evidence_authority.api import ReceiptSigningInput

    exempt = {
        TrustedEvidenceSigningKey,       # the boundary itself
        TrustedEvidenceVerificationKey,  # public material only
        ReceiptSigningInput,             # a transient, never-serialized frame
    }
    for name in api.__all__:
        obj = getattr(api, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        if obj in exempt:
            continue
        for field in dataclasses.fields(obj):
            assert "bytes" not in str(field.type).lower(), (name, field.name)


def test_the_public_half_does_not_disclose_the_private_half():
    key = TrustedEvidenceSigningKey(SEED)
    public = key.verification_key
    assert public.public_key_bytes != SEED
    assert SEED not in public.public_key_bytes
    assert not hasattr(public, "seed")
    assert not hasattr(public, "signing_key")


def test_the_signing_key_offers_no_seed_accessor():
    key = TrustedEvidenceSigningKey(SEED)
    for absent in ("to_bytes", "export", "serialize", "hex", "as_bytes",
                   "private_bytes", "reveal"):
        assert not hasattr(key, absent), absent


# --------------------------------------------------------------------------- #
# No ambient key loading (DD-10)
# --------------------------------------------------------------------------- #

def test_no_module_loads_a_key_from_the_environment_filesystem_or_network():
    """TEV-2 adds none of these; ``os``/``pathlib``/``socket`` are banned."""

    banned = {"os", "pathlib", "socket", "urllib", "http", "requests",
              "subprocess", "shutil", "tempfile", "secrets", "random"}
    for path in sorted(PKG_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots = {node.module.split(".")[0]}
            assert not (roots & banned), (path.name, sorted(roots & banned))


def test_no_key_generation_or_persistence_entry_point_is_exported():
    for name in api.__all__:
        lowered = name.lower().replace("_", "")
        for banned in ("generatekey", "keygen", "loadkey", "savekey", "storekey",
                       "keystore", "keyvault", "kms", "hsm", "keyprovider",
                       "issuecredential", "credential"):
            assert banned not in lowered, name


def test_no_source_file_contains_a_hard_coded_key_like_literal():
    """A 64-char lowercase hex literal in package source would be key-shaped.

    Digest domains, profile identifiers and version strings are all well under
    that length, so a match here is a genuine finding rather than a false
    positive. Test vectors live under ``tests/`` and in the probe harness, both
    outside the shipped package.
    """

    import re

    pattern = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
    for path in sorted(PKG_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not pattern.search(text), path.name


# --------------------------------------------------------------------------- #
# Test key material is unmistakably non-production
# --------------------------------------------------------------------------- #

def test_every_test_seed_constant_is_named_non_production():
    import _authority_builders as builders

    seeds = [
        name
        for name, value in vars(builders).items()
        if isinstance(value, bytes) and len(value) == 32
    ]
    assert seeds, "no test seeds found — the convention check would be vacuous"
    for name in seeds:
        assert name.startswith("NON_PRODUCTION_"), name


def test_the_test_seeds_are_trivially_patterned_or_published_rfc_vectors():
    """Unmistakably fake: byte ranges, or the RFC's own published test key."""

    assert NON_PRODUCTION_PRODUCER_SEED == bytes(range(0, 32))
    assert NON_PRODUCTION_AUTHORITY_SEED == bytes(range(32, 64))
    assert NON_PRODUCTION_ATTACKER_SEED == bytes(range(64, 96))
    assert NON_PRODUCTION_RFC8032_TEST1_SEED == bytes.fromhex(
        "9d61b19deffd5a60ba844af492ec2cc4"
        "4449c5697b326919703bac031cae7f60"
    )


def test_the_probe_harness_labels_its_keys_the_same_way():
    probe_source = PKG_ROOT.parents[1] / "adversarial_probes.py"
    tree = ast.parse(probe_source.read_text(encoding="utf-8"))
    seeds = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and "SEED" in target.id:
                    seeds.append(target.id)
    assert seeds
    for name in seeds:
        assert name.startswith("NON_PRODUCTION_"), name


def test_no_test_key_material_ships_inside_the_package():
    """Seeds live under ``tests/`` and in the probe harness, never in ``src/``."""

    for path in sorted(PKG_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in ("NON_PRODUCTION_", "SEED = ", "seed = bytes(",
                       "9d61b19deffd5a60"):
            assert marker not in text, (path.name, marker)
