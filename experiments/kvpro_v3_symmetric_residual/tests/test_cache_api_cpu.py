"""CPU test: the transformers-cache accessor handles the API variants (layers / key_cache / subscript)."""
from __future__ import annotations

import os
import sys
import unittest

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
import fakequant_model as FQ          # noqa: E402


class _Layer:
    def __init__(self, k, v):
        self.keys, self.values = k, v


class _PkvLayers:                      # transformers 5.x
    def __init__(self, ks, vs):
        self.layers = [_Layer(k, v) for k, v in zip(ks, vs)]


class _PkvKeyCache:                     # older transformers
    def __init__(self, ks, vs):
        self.key_cache, self.value_cache = list(ks), list(vs)


class _PkvSubscript:                    # legacy tuple-of-tuples
    def __init__(self, ks, vs):
        self._d = list(zip(ks, vs))

    def __getitem__(self, i):
        return self._d[i]

    def __len__(self):
        return len(self._d)


class TestCacheAccessor(unittest.TestCase):
    def _pair(self, n=3):
        ks = [torch.randn(1, 2, 5, 8) for _ in range(n)]
        vs = [torch.randn(1, 2, 5, 8) for _ in range(n)]
        return ks, vs

    def test_layers_api(self):
        ks, vs = self._pair()
        pkv = _PkvLayers(ks, vs)
        k, v = FQ.layer_kv(pkv, 1)
        self.assertTrue(torch.equal(k, ks[1]) and torch.equal(v, vs[1]))
        self.assertEqual(FQ.num_cache_layers(pkv), 3)

    def test_key_cache_api(self):
        ks, vs = self._pair()
        pkv = _PkvKeyCache(ks, vs)
        k, v = FQ.layer_kv(pkv, 2)
        self.assertTrue(torch.equal(k, ks[2]) and torch.equal(v, vs[2]))
        self.assertEqual(FQ.num_cache_layers(pkv), 3)

    def test_subscript_api(self):
        ks, vs = self._pair()
        pkv = _PkvSubscript(ks, vs)
        k, v = FQ.layer_kv(pkv, 0)
        self.assertTrue(torch.equal(k, ks[0]) and torch.equal(v, vs[0]))
        self.assertEqual(FQ.num_cache_layers(pkv), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
