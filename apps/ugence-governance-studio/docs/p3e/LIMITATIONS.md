# Limitations (P3E)

P3E **is** single-tenant, synthetic-data-only, HTTPS-only, authenticated demonstration
hosting. P3E **does not**: grant permissions; provision credentials; authorize business
actions; execute agents; call external models/tools; integrate production systems; ingest
real/customer/enterprise data; provide multitenancy, SSO/SCIM/RBAC product features, a
persistent user or decision database, billing, analytics, or telemetry export. It is not
an enterprise identity implementation and not a public-Internet SaaS deployment. The OCI
image build/run and container vulnerability scan are CI-gated; in a daemon-less
environment they are reported NOT_EXECUTED, not passed.
