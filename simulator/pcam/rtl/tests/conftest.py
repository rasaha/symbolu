"""
Pytest config for the PCAM RTL cosim tests.

The cocotb test module ``cosim_freq_sketch.py`` imports ``cocotb``
unconditionally (it has to — cocotb's ``@cocotb.test()`` decorators
only work at module load under a real simulator invocation). We must
tell pytest NOT to collect that file, otherwise pytest tries to
import it and raises a collection error on environments without
cocotb installed.

The pytest-collectable entry point is ``test_freq_sketch_cosim.py``,
which is a thin wrapper that subprocess-invokes ``make cosim`` and
skips gracefully when the tooling is unavailable.
"""

collect_ignore = ["cosim_freq_sketch.py"]
