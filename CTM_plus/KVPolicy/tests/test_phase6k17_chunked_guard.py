"""Phase 6K.17 guard -> Phase 6K.18 supported opt-in — CPU tests for the
chunked-prefill resolver.

Pinned acceptance criteria (6K.18 revision; the DEFAULT-OFF pins are
LOAD-BEARING and unchanged from 6K.17 — vLLM V0 treats None as "auto"
and AUTO-ENABLES chunked prefill at max_model_len > 32768, hit live on
A100-80G at mml=36096):

  1. Default (caller passes nothing / None): the resolver returns False —
     EXPLICITLY. "Leave unset" must NOT be the outcome. UNCHANGED.

  2. Explicit False is honored (returns False). UNCHANGED.

  3. Explicit True is SUPPORTED (Phase 6K.18 D3): returns True — the
     factory then arms the 6B.2 rid-stash hook + chunked_active and
     forces eager. (Pre-6K.18 this raised; the chunk-2+ context rebuild
     now handles non-block-aligned ctx via the staged-K-tail splice.)

  4. INT4_PROTECTED_ALLOW_CHUNKED_PREFILL no longer changes the resolver
     outcome (True is supported with or without it) and MUST NOT flip
     the default (None stays False with the env set). The env survives
     only as the backend-side raw bypass for non-factory construction.

  5. Factory wiring: the int4_protected branch routes through the
     resolver and pins kwargs["enable_chunked_prefill"]; the stock branch
     (kv_cache_dtype="auto") must NOT inject a value the caller didn't ask
     for; chunked True arms set_chunked_active + the eager coupling
     (verified statically — the factory requires vllm at call time,
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

    def test_true_supported_6k18(self):
        # Phase 6K.18 D3: explicit opt-in is supported (no env needed).
        self.assertIs(ip._resolve_chunked_prefill(True), True)

    def test_env_override_allows_true(self):
        # Env set is harmless — same outcome as without it.
        os.environ[ip._ALLOW_CHUNKED_ENV] = "1"
        self.assertIs(ip._resolve_chunked_prefill(True), True)

    def test_env_zero_does_not_block_supported_true(self):
        # The env is the RAW BYPASS knob (backend-side), not a kill
        # switch for the supported factory path.
        os.environ[ip._ALLOW_CHUNKED_ENV] = "0"
        self.assertIs(ip._resolve_chunked_prefill(True), True)

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
        i_set = src.index('kwargs["enable_chunked_prefill"] = _chunked_resolved', i_gate)
        self.assertGreater(i_set, i_gate)

    def test_factory_arms_chunked_contract(self):
        # 6K.18 D2: chunked True must arm set_chunked_active (post-init)
        # and couple eager exactly like APC.
        src = self._factory_source()
        self.assertIn("set_chunked_active", src)
        self.assertIn("_chunked_resolved = _resolve_chunked_prefill", src)
        self.assertIn("INT4_PROTECTED_CHUNKED_ALLOW_GRAPHS", src)
        # Hook-install condition includes the chunked flag (the rid stash
        # is the only legal identity for chunk 2+).
        self.assertIn("_apc_on or _chunked_on", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
