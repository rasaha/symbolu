"""Distribution version.

0.1.0 is the FIRST implementation of the durable-execution boundary. The engine
behind it (DBOS) is a **candidate**, not a ratified engine — see the README and
`docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md` §8.
"""

__version__ = "0.1.0"

#: Engine ratification state. Flipped to "RATIFIED" only when every ADR §8 matrix row
#: has passing evidence in CI. Read by :func:`ugence_durable_execution.engine_status`
#: and asserted by the test suite, so the claim cannot drift away from the evidence.
DBOS_ENGINE_STATUS = "CANDIDATE"
