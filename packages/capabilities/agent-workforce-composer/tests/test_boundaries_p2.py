"""P2 boundary tests (§31 Boundaries; P2-I17,I20)."""
from __future__ import annotations

import ast
import pathlib
import sys

import ugence_agent_workforce_composer  # noqa: F401
import ugence_agent_workforce_composer.api as api

_SRC = pathlib.Path(ugence_agent_workforce_composer.__file__).resolve().parent

_FORBIDDEN_ROOTS = {
    "agentic", "agent_runtime_v2", "agent_runtime_migration",
    "ugence_model_selection", "execution_gate", "ai_hiring",
    "ugence_procurement", "ugence_actiongate_provider", "ugence_action_clearance",
    "ugence_storygraph", "control_plane", "cloud_controller",
    "ugence_policy_workflow_compiler",
    "requests", "httpx", "urllib3", "socket", "aiohttp", "openai", "anthropic",
    "torch", "boto3",
}


def test_no_forbidden_imports_including_p2_modules():
    offenders = []
    for path in _SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = []
            if isinstance(node, ast.Import):
                roots = [n.name.split(".")[0] for n in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            for root in roots:
                if root in _FORBIDDEN_ROOTS:
                    offenders.append(f"{path.name}: imports {root}")
    assert not offenders, offenders


def test_no_execution_scheduling_or_grant_symbols():
    text = "\n".join(p.read_text(encoding="utf-8") for p in _SRC.rglob("*.py"))
    for banned in ("subprocess.", "socket.socket", "asyncio.run", "os.system",
                   ".dispatch(", "invoke_model(", "schedule_workflow("):
        assert banned not in text


def test_importing_api_loads_no_prohibited_modules():
    import subprocess
    code = (
        "import ugence_agent_workforce_composer.api, sys;"
        "banned=['agentic','ugence_model_selection','ugence_policy_workflow_compiler',"
        "'ai_hiring','ugence_procurement','ugence_actiongate_provider','ugence_action_clearance'];"
        "hit=[b for b in banned if b in sys.modules];"
        "print('HIT:'+','.join(hit)); sys.exit(1 if hit else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            env={"PYTHONPATH": str(_SRC.parent)})
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_wall_clock_in_p2_core():
    for name in ("ranking", "composition", "permissions", "fallback", "plan", "scoring",
                 "dependency", "failure_domains"):
        src = (_SRC / f"{name}.py").read_text(encoding="utf-8")
        for banned in ("time.time(", "datetime.now(", "datetime.utcnow(", "random."):
            assert banned not in src, (name, banned)
