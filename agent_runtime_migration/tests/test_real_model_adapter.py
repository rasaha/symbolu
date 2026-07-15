"""Phase 3: real-model adapter CONTRACT tests.

These prove the live HTTP adapter satisfies the LanguageModel contract and that a
real model's malformed output fails closed BEFORE execution. They run against a
LOCAL fake HTTP server — they are contract-compliance evidence, NOT live-model
evidence (no real model runs). No credentials are used (a dummy test key).
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agent_runtime_migration.contracts import Goal, RiskClass
from agent_runtime_migration.model import (
    LiveHTTPModel, LiveModelConfig, build_live_model_from_env,
)
from agent_runtime_migration.model.parsing import ModelParseError, parse_plan_payload
from agent_runtime_migration.planning import ModelPlanner
from agent_runtime_migration.tools import ToolRegistry

_PLAN = json.dumps({"actions": [{"tool": "search", "description": "find", "arguments": {"q": "x"}}]})


def _make_server(body_text: str):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def do_POST(self):
            n = int(self.headers.get("content-length", 0))
            self.rfile.read(n)
            resp = json.dumps({"choices": [{"message": {"content": body_text}}]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(resp)

    srv = HTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _live(base):
    os.environ["_TEST_KEY"] = "dummy-not-a-real-secret"
    cfg = LiveModelConfig(provider="openai", model_id="test-model", base_url=base, timeout_s=5)
    return LiveHTTPModel(cfg, api_key_env="_TEST_KEY")


def test_adapter_satisfies_contract_over_http():
    srv, base = _make_server(_PLAN)
    try:
        model = _live(base)
        out = model.generate("Objective: search")
        assert json.loads(out)["actions"][0]["tool"] == "search"
        # flows through the frozen parser into a typed plan
        reg = ToolRegistry(); reg.register("search", lambda a: "DOC", RiskClass.LOCAL_READ_ONLY,
                                           fast_path_permitted=True)
        plan = ModelPlanner(model, reg).plan(Goal(goal_id="g", objective="search"))
        assert plan.steps[0].tool_name == "search"
    finally:
        srv.shutdown()


def test_malformed_real_output_fails_closed():
    srv, base = _make_server("not valid json at all")
    try:
        model = _live(base)
        reg = ToolRegistry(); reg.register("search", lambda a: "DOC", RiskClass.LOCAL_READ_ONLY,
                                           fast_path_permitted=True)
        with pytest.raises(ModelParseError):
            ModelPlanner(model, reg).plan(Goal(goal_id="g", objective="x"))
    finally:
        srv.shutdown()


def test_adapter_does_not_log_credentials():
    srv, base = _make_server(_PLAN)
    try:
        model = _live(base)
        model.generate("x")
        # the adapter logs only prompt LENGTHS, never content/credentials
        assert model.prompt_log and all(isinstance(x, int) for x in model.prompt_log)
    finally:
        srv.shutdown()


def test_no_model_configured_returns_none():
    # In THIS environment no provider/credentials are set -> None (runner reports BLOCKED).
    for var in ("RUNTIME_MODEL_PROVIDER", "RUNTIME_MODEL_ID"):
        os.environ.pop(var, None)
    assert build_live_model_from_env() is None


def test_missing_credentials_returns_none():
    os.environ["RUNTIME_MODEL_PROVIDER"] = "openai"
    os.environ["RUNTIME_MODEL_ID"] = "gpt-x"
    os.environ.pop("OPENAI_API_KEY", None)
    try:
        assert build_live_model_from_env() is None   # no key -> not available
    finally:
        os.environ.pop("RUNTIME_MODEL_PROVIDER", None)
        os.environ.pop("RUNTIME_MODEL_ID", None)
