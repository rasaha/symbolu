"""Phase 6K.17 — CPU tests for the chunked-prefill guard.

Pinned acceptance criteria:

  1. Default (caller passes nothing / None): the resolver returns False —
     EXPLICITLY. vLLM V0 treats None as "auto" and AUTO-ENABLES chunked
     prefill at max_model_len > 32768; chunk 2+ of a chunked prompt then
     arrives as a prefill-with-context and the backend refuses it on the
     prefix-aware branch (hit live: A100-80G, mml=36096). "Leave unset"
     must NOT be the outcome.

  2. Explicit False is honored (returns False).

  3. Explicit True RAISES RuntimeError by default — chunk 2+ would run
     the prefix-prefill read path on non-APC metadata (unvalidated math).

  4. INT4_PROTECTED_ALLOW_CHUNKED_PREFILL=1 bypasses the refusal and
     returns True (dev-only escape hatch, loud warning).

  5. Factory wiring: the int4_protected branch routes through the
     resolver and pins kwargs["enable_chunked_prefill"]; the stock branch
     (kv_cache_dtype="auto") must NOT inject a value the caller didn't ask
     for (verified statically — the factory requires vllm at call time,
     unavailable in CPU CI).

All tests are CPU-only; kv_policy.int4_protected guards its vllm/torch
imports so the module imports cleanly without either.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break

from kv_policy import int4_protected as ip


class TestResolveChunkedPrefill(unittest.TestCase):
    """The resolver is the load-bearing surface — the factory calls
    ip._resolve_chunked_prefill(...) for every int4_protected LLM."""

    def setUp(self):
        os.environ.pop(ip._ALLOW_CHUNKED_ENV, None)

    def tearDown(self):
        os.environ.pop(ip._ALLOW_CHUNKED_ENV, None)

    def test_default_none_pins_false(self):
        self.assertIs(ip._resolve_chunked_prefill(None), False)

    def test_explicit_false_honored(self):
        self.assertIs(ip._resolve_chunked_prefill(False), False)

    def test_true_refused_by_default(self):
        with self.assertRaises(RuntimeError) as cm:
            ip._resolve_chunked_prefill(True)
        msg = str(cm.exception)
        self.assertIn("chunked prefill", msg)
        self.assertIn("32768", msg)  # names the auto-enable trap
        self.assertIn(ip._ALLOW_CHUNKED_ENV, msg)

    def test_env_override_allows_true(self):
        os.environ[ip._ALLOW_CHUNKED_ENV] = "1"
        self.assertIs(ip._resolve_chunked_prefill(True), True)

    def test_env_override_zero_still_refuses(self):
        os.environ[ip._ALLOW_CHUNKED_ENV] = "0"
        with self.assertRaises(RuntimeError):
            ip._resolve_chunked_prefill(True)

    def test_env_override_does_not_change_default(self):
        os.environ[ip._ALLOW_CHUNKED_ENV] = "1"
        self.assertIs(ip._resolve_chunked_prefill(None), False)


class TestFactoryWiring(unittest.TestCase):
    """Static checks of the factory body (the factory itself needs a GPU
    + vllm to execute; CPU CI verifies the wiring is present and gated)."""

    def _factory_source(self):
        import inspect
        return inspect.getsource(ip.Int4ProtectedLLM)

    def test_factory_routes_through_resolver(self):
        src = self._factory_source()
        self.assertIn("_resolve_chunked_prefill", src)
        self.assertIn('kwargs.pop("enable_chunked_prefill"', src)

    def test_factory_gates_on_int4_dtype(self):
        # The pinned value must apply ONLY to the int4_protected branch; a
        # stock ("auto") run keeps vLLM's own policy unless the caller asked.
        src = self._factory_source()
        i_pop = src.index('kwargs.pop("enable_chunked_prefill"')
        i_gate = src.index('if kv_cache_dtype == "int4_protected":', i_pop)
        i_set = src.index('kwargs["enable_chunked_prefill"] = _resolve_chunked_prefill', i_gate)
        self.assertGreater(i_set, i_gate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
