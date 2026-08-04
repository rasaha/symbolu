# Synthetic Data Boundary (P3E)

Only the four pinned scenarios load: `procurement`, `customer_support`,
`cybersecurity_success`, `cybersecurity_no_feasible_team`. The committed manifest fixes
their fixture hashes and an aggregate bundle hash with classification
`SYNTHETIC_DEMONSTRATION_ONLY`. Startup fails closed (`SYNTHETIC_DATA_BOUNDARY_FAILED`)
on any missing/extra/tampered fixture, wrong classification, or a `UGS_API_SCENARIO_ROOT`
override. No filesystem path, URL, upload, environment variable, or remote fetch can add
or redirect scenarios. This is a demonstration boundary — never load production, customer,
or enterprise data into this deployment.
