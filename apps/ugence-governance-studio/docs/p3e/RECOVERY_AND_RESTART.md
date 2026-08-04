# Recovery and Restart (P3E)

The service is stateless. A restart re-runs the fail-closed startup integrity gate and
reloads the pinned synthetic bundle; scenario planning is deterministic, so plan/replay
fingerprints are identical across restarts. Recovery = redeploy the same image with the
same `.env` and TLS material. There is no database, no persisted decision store, and no
user state to restore. Roll back by redeploying the previous image digest.
