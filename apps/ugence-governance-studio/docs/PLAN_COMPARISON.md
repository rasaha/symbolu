# Plan Comparison (P3D)

Uses `POST /plans/compare`. Compares two deterministically-produced plans from the
same scenario contract (baseline vs an identical control, or baseline vs a
provider-forbidden variant). Displays the API diff: assignment / constraint /
permission / fallback / policy-digest changes, snapshot-changed and the diff
fingerprint. Identical plans are shown as such. No browser-side semantic diff is
implemented — the API supplies the diff.
