"""Make the shared authority test fixtures importable as a plain module.

The module is named ``_authority_fixtures`` rather than ``_fixtures`` so a
combined multi-package pytest run cannot shadow another package's fixtures.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
