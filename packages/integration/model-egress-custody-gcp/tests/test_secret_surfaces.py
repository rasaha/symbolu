"""Every routine surface the accessed payload and the issued lease could escape through.

The companion of the unit's ``test_credential_lease_surfaces.py``, for the two objects
this distribution produces: the answer from Secret Manager and the lease built from it.
Both are plain classes with ``__slots__`` and neither is a dataclass, so there is no
``__dict__`` to hand out and no ``fields()`` to walk.

The boundary, stated accurately: same-process inspection still reaches a slot, and no
Python object can prevent that. Everything a serializer, logger, debugger repr,
exception renderer or copy routine touches unprompted is asserted closed.
"""

from __future__ import annotations

import copy
import dataclasses
import io
import json
import logging
import pickle
import traceback

import pytest

from ugence_model_egress_custody_gcp import AccessedSecretVersion
from ugence_model_egress_unit import CustodyRefused

from _fixtures import FAKE_PAYLOAD, NOW, RESOURCE, FakeClient, config, designation, request
from synthetic_shapes import KINDS, synthetic_credential_shape

from test_adapter import build

PAYLOAD_BYTES = FAKE_PAYLOAD.encode("utf-8")


def accessed() -> AccessedSecretVersion:
    return AccessedSecretVersion(name=RESOURCE, payload=PAYLOAD_BYTES)


def _captures(subject) -> dict:
    def attempt(name, call):
        try:
            return name, call()
        except Exception as exc:  # noqa: BLE001 - a refusal is a valid answer
            return name, f"<raised {type(exc).__name__}: {exc}>"

    surfaces = [
        ("repr", lambda: repr(subject)), ("str", lambda: str(subject)),
        ("format", lambda: format(subject)), ("f-string", lambda: f"{subject}"),
        ("f-string-repr", lambda: f"{subject!r}"), ("percent-s", lambda: "%s" % (subject,)),
        ("vars", lambda: vars(subject)), ("dict", lambda: subject.__dict__),
        ("asdict", lambda: dataclasses.asdict(subject)),
        ("astuple", lambda: dataclasses.astuple(subject)),
        ("fields", lambda: dataclasses.fields(subject)),
        ("json", lambda: json.dumps(subject)),
        ("json-default-str", lambda: json.dumps(subject, default=str)),
        ("json-default-repr", lambda: json.dumps(subject, default=repr)),
        ("json-default-vars", lambda: json.dumps(subject, default=vars)),
        ("pickle", lambda: pickle.dumps(subject)),
        ("copy", lambda: copy.copy(subject)), ("deepcopy", lambda: copy.deepcopy(subject)),
        ("reduce", lambda: subject.__reduce__()), ("reduce_ex", lambda: subject.__reduce_ex__(2)),
        ("getstate", lambda: subject.__getstate__()),
        ("dir-values", lambda: {n: getattr(subject, n, None) for n in dir(subject)
                                if not n.startswith("_") and n != "payload"}),
    ]
    return dict(attempt(name, call) for name, call in surfaces)


# --- the accessed answer -------------------------------------------------------------

def test_the_accessed_version_has_no_instance_dict_and_is_not_a_dataclass():
    answer = accessed()
    assert not hasattr(answer, "__dict__")
    with pytest.raises(TypeError):
        vars(answer)
    assert not dataclasses.is_dataclass(answer)
    assert "_held" in AccessedSecretVersion.__slots__


@pytest.mark.parametrize("surface", sorted(_captures(accessed())))
def test_no_routine_surface_of_the_accessed_version_yields_the_payload(surface):
    captured = _captures(accessed())[surface]
    assert FAKE_PAYLOAD not in repr(captured) and FAKE_PAYLOAD not in str(captured), surface


def test_the_accessed_version_is_immutable_and_compares_by_version_only():
    answer = accessed()
    with pytest.raises(AttributeError, match="immutable"):
        answer.name = "other"
    with pytest.raises(AttributeError, match="immutable"):
        del answer.name
    assert answer == AccessedSecretVersion(name=RESOURCE, payload=b"completely different")
    assert answer != AccessedSecretVersion(name=RESOURCE + "9", payload=PAYLOAD_BYTES)
    assert answer.payload == PAYLOAD_BYTES, "and the adapter can still read it"


# --- the lease this distribution issues ------------------------------------------------

@pytest.mark.parametrize("surface", sorted(_captures(
    build().materialize(request(), now=NOW))))
def test_no_routine_surface_of_an_issued_lease_yields_the_credential(surface):
    lease = build().materialize(request(), now=NOW)
    captured = _captures(lease)[surface]
    assert FAKE_PAYLOAD not in repr(captured) and FAKE_PAYLOAD not in str(captured), surface


def test_an_issued_lease_has_no_dict_and_still_hands_the_credential_to_one_consumer():
    lease = build().materialize(request(), now=NOW)
    assert not hasattr(lease, "__dict__")
    with pytest.raises(TypeError):
        vars(lease)
    assert lease.use(lambda s: s, now=NOW) == FAKE_PAYLOAD
    assert FAKE_PAYLOAD not in json.dumps(lease.as_record())


# --- exception chains and logging ---------------------------------------------------------

@pytest.mark.parametrize("kind", KINDS)
def test_no_link_of_a_refusal_chain_carries_credential_shaped_provider_text(kind):
    leaked = synthetic_credential_shape(kind)

    class PermissionDenied(RuntimeError):
        pass

    adapter = build(client=FakeClient(raises=PermissionDenied(f"denied: {leaked} on {RESOURCE}")))
    with pytest.raises(CustodyRefused) as info:
        adapter.materialize(request(), now=NOW)
    assert info.value.__context__ is None and info.value.__cause__ is None
    chain, exc = [], info.value
    while exc is not None and exc not in chain:
        chain.append(exc)
        exc = exc.__context__ or exc.__cause__
    rendered = "".join(traceback.format_exception(type(info.value), info.value, info.value.__traceback__))
    assert leaked not in rendered
    for link in chain:
        assert leaked not in str(link) and leaked not in repr(link)
        assert leaked not in repr(getattr(link, "args", ()))


def test_logging_an_issued_lease_or_an_accessed_version_renders_no_secret():
    lease = build().materialize(request(), now=NOW)
    answer = accessed()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    log = logging.getLogger("custody-surfaces")
    log.handlers = [handler]
    log.setLevel(logging.DEBUG)
    log.propagate = False
    log.info("lease %s answer %r", lease, answer)
    log.info("structured", extra={"lease": lease, "answer": answer})
    try:
        adapter = build(client=FakeClient(raises=RuntimeError(FAKE_PAYLOAD)))
        adapter.materialize(request(), now=NOW)
    except CustodyRefused:
        log.exception("materialization refused")
    assert FAKE_PAYLOAD not in stream.getvalue()
