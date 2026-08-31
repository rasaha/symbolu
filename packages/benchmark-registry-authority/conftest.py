"""Make this package and the frozen BR-1 layer importable for the in-tree tests.

``ugence_benchmark_registry_authority`` resolves from this package's src layout,
and ``ugence_benchmark_registry`` from the sibling BR-1 package's — which is the
one and only runtime dependency, so nothing else is put on the path. If a second
Ugence package ever became importable this way, the dependency-boundary test
would still fail: it asserts on declared metadata and on the import graph, not
on what happens to be reachable.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"
BR1_SRC = HERE.parent / "benchmark-registry" / "src"
for path in (str(SRC), str(BR1_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)
