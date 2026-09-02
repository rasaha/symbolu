"""§4 capture boundary: a separate-process provider gateway that captures every model call,
recomputes telemetry from its own records and attests it on the digested execution record.
The provider SDK lives in the caller's factory module, never here."""
