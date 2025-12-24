"""
EXPERIMENT SANDBOX — NON-AUTHORITATIVE
=======================================

EXPERIMENT_ONLY = True

WARNING: This module and all submodules are EXPERIMENTAL.
This file MUST NOT be used as ontology source of truth.

HARD CONSTRAINTS:
    - Files in docs/experiments/ are NOT production code
    - They MUST NOT be imported by the production pipeline
    - They MUST NOT be reachable from Phase-4B, Phase-4C, or Phase-14
    - Any ontology data in experiments is NON-AUTHORITATIVE

AUTHORITATIVE SOURCE:
    - Ontology data: docs/data/*.json (via Phase-4A only)
    - Ontology executor: symbolu.ontology.phase4a

Do NOT use experimental code for:
    - Production varna lookups
    - Layer interaction resolution
    - Ontology validation
"""

# EXPERIMENT_ONLY marker — enforced by import guards
EXPERIMENT_ONLY = True

# This package contains experimental phase engine implementations.
# NOT for production use.
