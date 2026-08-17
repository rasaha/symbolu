"""Put the package src and the tests directory on the path for the test suite."""

import pathlib
import sys

TESTS = pathlib.Path(__file__).resolve().parent
SRC = TESTS.parent / "src"
for path in (str(SRC), str(TESTS)):
    if path not in sys.path:
        sys.path.insert(0, path)
