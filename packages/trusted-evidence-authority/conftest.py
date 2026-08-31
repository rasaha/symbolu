"""Make this package importable for its own tests.

``ugence_trusted_evidence_authority`` resolves from this package's src layout.
No installed wheel and no sibling package are required to run the in-tree tests
— this package is a zero-dependency leaf, so nothing else is put on the path.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
