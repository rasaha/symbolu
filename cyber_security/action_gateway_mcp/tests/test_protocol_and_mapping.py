"""Protocol parsing, canonical mapping, registry coverage, response mapping."""

from __future__ import annotations

import pytest

from action_gateway_mcp import protocol, registry
from action_gateway_mcp.errors import ArgumentError, ProtocolError, UnknownToolError


def test_parse_valid_call():
    p = protocol.parse_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": "kubernetes.get", "arguments": {"a": "b"}}})
    assert p["name"] == "kubernetes.get" and p["arguments"] == {"a": "b"}


def test_parse_rejects_bad_shapes():
    for bad in [{}, {"jsonrpc": "1.0"}, {"jsonrpc": "2.0", "method": "x"},
                {"jsonrpc": "2.0", "method": "tools/call", "params": {}}]:
        with pytest.raises(ProtocolError):
            protocol.parse_request(bad)


def test_registry_covers_all_exposed_tools():
    expected = {"filesystem.write", "filesystem.delete", "terraform.plan", "terraform.apply",
                "kubernetes.get", "kubernetes.apply", "kubernetes.delete", "iam.inspect",
                "iam.grant", "monitoring.disable"}
    assert set(registry.EXPOSED_TOOLS) == expected
    assert set(registry.metadata().keys()) == expected


def test_every_mutating_tool_maps_to_frozen_operation():
    frozen_ops = {"IAM_GRANT_ADMIN", "DEPLOY", "DB_DELETE", "NET_EXPOSE", "SECRET_READ",
                  "MONITORING_DISABLE", "DB_MUTATION", "KEY_ROTATE",
                  "CLOUD_SPEND_INCREASE", "EXTERNAL_COMMS"}
    for name, spec in registry.REGISTRY.items():
        if spec.read_only:
            assert spec.operation is None and spec.gateway_tool is None
        else:
            assert spec.operation in frozen_ops
            assert spec.gateway_tool and spec.gateway_verb
            assert spec.target_builder is not None


def test_unknown_tool_fails_closed():
    with pytest.raises(UnknownToolError):
        registry.get_spec("shell.exec")


def test_argument_validation_fail_closed():
    spec = registry.get_spec("filesystem.write")
    with pytest.raises(ArgumentError):
        registry.validate_arguments(spec, {"path": "x"})  # missing content
    with pytest.raises(ArgumentError):
        registry.validate_arguments(spec, {"path": "x", "content": "y", "extra": "z"})
    with pytest.raises(ArgumentError):
        registry.validate_arguments(spec, {"path": 1, "content": "y"})  # wrong type


def test_numeric_args_must_be_typed_strings():
    spec = registry.get_spec("filesystem.write")
    with pytest.raises(ArgumentError):
        registry.validate_arguments(spec, {"path": "x", "content": "y", "affected_count": 5})
    registry.validate_arguments(spec, {"path": "x", "content": "y", "affected_count": "5"})


def test_target_builder_fail_closed_on_missing_pieces():
    spec = registry.get_spec("kubernetes.delete")
    with pytest.raises(KeyError):
        spec.target_builder({"namespace": "p"})  # missing kind/name


def test_response_mapping_never_carries_token():
    for outcome in (protocol.ALLOW, protocol.DENY, protocol.ESCALATE_TO_HUMAN,
                    protocol.SIMULATE_AND_RETRY, protocol.REQUEST_MORE_EVIDENCE,
                    protocol.ALLOW_WITH_CONSTRAINTS):
        r = protocol.decision_response(
            outcome=outcome, request_id="r1", action_hash="h", dispositive_rules=["R1"],
            applied_constraints=None, reason="")
        assert r["execution_token"] is None
        assert r["executable"] == (outcome in protocol.EXECUTABLE)
