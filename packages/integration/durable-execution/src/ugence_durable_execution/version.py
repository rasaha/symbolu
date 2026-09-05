"""Distribution version.

0.1.0 is the FIRST implementation of the durable-execution boundary. The engine
behind it (DBOS) is **ratified as the initial engine** by owner ruling OD-3 on the
CI-verified ADR §8 matrix — see the README and
`docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md` §8A and §9. Ratified
is not pilot-validated and not production-certified.
"""

__version__ = "0.1.0"

#: Engine ratification state. Flipped to "RATIFIED" by owner ruling OD-3 (ADR §9,
#: 2026-09-05) on the evidence of every ADR §8 matrix row passing in CI
#: (durable-execution-ci job 101257085510 on fe6f1591). Read by
#: :func:`ugence_durable_execution.engine_status` and asserted by the test suite
#: together with the ADR record, so the claim cannot drift away from the evidence.
DBOS_ENGINE_STATUS = "RATIFIED"
