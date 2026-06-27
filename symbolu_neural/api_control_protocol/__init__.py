"""Symbol-U as an API-level structured control protocol — EXPERIMENTAL / ISOLATED.

Investigates whether Symbol-U is better used as an external structured control
packet sent to an LLM via the API than as an internal neural module. Measurement
harness only: no weights changed, no model trained, no decoder built.

The decisive arm (a real LLM interpreting the packet) needs an API key and is not
runnable in this sandbox; see API_CONTROL_PROTOCOL_REPORT.md. Does not modify or
depend on the older detector files or clean_softmax.
"""
