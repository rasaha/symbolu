# Data provenance — Azure Functions 2019 public trace

Recorded before any experiment implementation, per the owner's ratification.

- **Dataset:** Microsoft Azure Functions Trace 2019 (anonymized), from
  `Azure/AzurePublicDataset`.
- **Authoritative documentation:**
  https://github.com/Azure/AzurePublicDataset/blob/master/AzureFunctionsDataset2019.md
  (fetched 2026-08-29 via raw.githubusercontent.com; names the release asset
  below as the download).
- **Release tag:** `dataset-functions-2019` on `Azure/AzurePublicDataset`.
- **Asset URL (authoritative download):**
  https://github.com/Azure/AzurePublicDataset/releases/download/dataset-functions-2019/azurefunctions_dataset2019_azurefunctions-dataset2019.tar.xz
  (redirects to release-assets.githubusercontent.com; HTTP 200).
- **Archive:** `azurefunctions_dataset2019_azurefunctions-dataset2019.tar.xz`,
  **142,968,140 bytes**, SHA-256
  `aff8b3ca7240a41a109e4ee598e0a96e45fcb92e7b8395ac19cb3748cd260d89`,
  downloaded 2026-08-29.
- **Selected files (the only files this experiment uses):** the 14 per-minute
  anonymized invocation-count files
  `invocations_per_function_md.anon.d01.csv` … `d14.csv`
  (columns `HashOwner,HashApp,HashFunction,Trigger,1..1440`; one row per
  function per day; value = invocations in that minute). Per-file byte sizes:
  `DATA_SIZES.txt`; per-file SHA-256 digests: `DATA_DIGESTS.txt`.
- **License:** CC-BY (Creative Commons Attribution), per the dataset page and
  https://github.com/Azure/AzurePublicDataset/blob/master/LICENSE.
- **Attribution:** Mohammad Shahrad, Rodrigo Fonseca, Íñigo Goiri, Gohar
  Chaudhry, Paul Batum, Jason Cooke, Eduardo Laureano, Colby Tresness, Mark
  Russinovich, Ricardo Bianchini. "Serverless in the Wild: Characterizing and
  Optimizing the Serverless Workload at a Large Cloud Provider." USENIX ATC
  2020. Dataset © Microsoft, used under CC-BY.
- **Storage discipline:** the archive and extracted CSVs live outside Git (the
  session scratchpad). The repository carries only this provenance record, the
  digests/sizes, code, the frozen function list, and results — never the
  dataset (owner ratification). Reproduction re-downloads the asset and
  verifies the digests above.
