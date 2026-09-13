"""Make the shared fixtures importable as a plain module.

Named ``_change_effect_policy_fixtures`` rather than ``_fixtures`` so a combined
multi-package pytest run cannot shadow ``change-effect-records``'s fixtures of that
name — both packages put their ``tests`` directory on ``sys.path``, and the first one
there would otherwise answer for both.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
