"""Put the package src, the BR-1 src and the tests directory on the path."""

import pathlib
import sys

TESTS = pathlib.Path(__file__).resolve().parent
PKG = TESTS.parent
SRC = PKG / "src"
BR1_SRC = PKG.parent / "benchmark-registry" / "src"
for path in (str(SRC), str(BR1_SRC), str(TESTS)):
    if path not in sys.path:
        sys.path.insert(0, path)
