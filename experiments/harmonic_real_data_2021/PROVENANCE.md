# Data provenance — Azure Functions Invocation Trace 2021

Recorded before any experiment implementation.

- **Dataset:** Azure Functions Invocation Trace 2021 (two weeks starting
  2021-01-31), `Azure/AzurePublicDataset`.
- **Authoritative documentation:**
  https://github.com/Azure/AzurePublicDataset/blob/master/AzureFunctionsInvocationTrace2021.md
  (fetched 2026-08-30 via raw.githubusercontent.com).
- **Storage location:** unlike the 2019 dataset (a release asset), this trace
  is a file committed in the repository at
  `data/AzureFunctionsInvocationTraceForTwoWeeksJan2021.rar`. Retrieval URL
  used (HTTP 200):
  https://raw.githubusercontent.com/Azure/AzurePublicDataset/master/data/AzureFunctionsInvocationTraceForTwoWeeksJan2021.rar
  (the `github.com/.../raw/...` redirect form returns 403 from this
  environment).
- **Archive:** `AzureFunctionsInvocationTraceForTwoWeeksJan2021.rar` (RAR 5),
  **18,444,269 bytes**, SHA-256
  `8bb5d1c82e89e467062b6582996232df24edfebadbaf3287a8c985ca178ba92d`,
  downloaded 2026-08-30. Extraction note for reproducers: `unar` and `p7zip`
  16.02 fail on this RAR5 stream (decoder limitations); the reference
  RARLAB `unrar` verifies the archive **All OK** and extracts it cleanly.
- **Extracted file:** `AzureFunctionsInvocationTraceForTwoWeeksJan2021.txt`,
  **305,388,316 bytes**, SHA-256
  `d56368ef194baa8d418304bd2f87cca67668ced0d117bd89ad4ef3cf836457d2`.
  CSV with header `app,func,end_timestamp,duration`: per-invocation records
  (encrypted app id; function id unique within app; invocation end time and
  duration in seconds). **1,980,951 rows** spanning end-timestamps
  0.1 → 1,209,599.7 s — exactly 14.00 days. Population is small: ~119 unique
  apps, ~424 unique (app, func) pairs.
- **License:** CC-BY (Creative Commons Attribution), per the dataset page and
  repository LICENSE.
- **Attribution:** Yanqi Zhang, Íñigo Goiri, Gohar Irfan Chaudhry, Rodrigo
  Fonseca, Sameh Elnikety, Christina Delimitrou, Ricardo Bianchini. "Faster
  and Cheaper Serverless Computing on Harvested Resources." SOSP 2021.
  Dataset © Microsoft, used under CC-BY.
- **Storage discipline:** archive and extracted file live outside Git (the
  session scratchpad); the repository carries only provenance, code, the
  frozen cohort list, and results. Reproduction re-downloads and verifies the
  digests above.
