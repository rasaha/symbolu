// AUTO-GENERATED from apps/ugence-governance-studio/contracts/openapi_v2.json
// DO NOT EDIT BY HAND. Regenerate with: npm run generate:api-v2
// source_openapi_sha256: c6785b267dafe9e2593b58744890606727b26d450ffd1a32f9b544f95a2d0f3e
// api_contract_version: governance_studio.api.v2

export interface paths {
    "/api/v2/authority/decisions/{decision_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Decision
         * @description One recorded Decision Authority decision.
         */
        get: operations["v2_authority_read_decision"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/authority/policies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Policies
         * @description Issued policy records for the identities this deployment was configured with.
         */
        get: operations["v2_authority_list_policies"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/authority/policies/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Policy
         * @description One issued record, with its revocations and supersessions.
         */
        get: operations["v2_authority_read_policy"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/constitution/preflight": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preflight Constitution
         * @description Dry-run every pre-signing check.
         *
         *     This is the ONLY activation entry point the studio reaches (SD-2). Issuance and
         *     activation are authority acts and are permanently outside the allowlist.
         */
        post: operations["v2_constitution_preflight"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/constitution/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Validate Constitution
         * @description Structural validation of a constitution document. Mutation-free.
         */
        post: operations["v2_constitution_validate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/data-use/declarations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Data Use Declarations
         * @description The declarations in force for this deployment's tenant at ``as_of``.
         *
         *     ``as_of`` is an ISO-8601 instant with a timezone; absent, the request's own instant
         *     is used and reported back. A declaration outside its window is absent from the
         *     answer, never flagged.
         */
        get: operations["v2_data_use_list"];
        put?: never;
        /**
         * Declare Data Use
         * @description Record one typed data-use declaration for this deployment's tenant.
         *
         *     Every field is validated by data-use-admission's own refusal reasons; a superseding
         *     declaration is admitted only by ``supersession_refusals``. ``data_ref`` is an opaque
         *     handle and the record carries no data. A refusal is typed, never a 500.
         */
        post: operations["v2_data_use_declare"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/exports/{receipt_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Export
         * @description The export artifact for one clearance receipt this deployment holds.
         *
         *     The tenant is the deployment's, never the caller's. An id the deployment does
         *     not hold is refused typed, never answered as an empty success: "no such
         *     clearance" and "no clearances" must not look alike to an external runtime. The
         *     artifact is content-addressed, and the answer says in four separate ways what
         *     recomputing that fingerprint does not establish.
         */
        get: operations["v2_export_read"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/observe/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Audit Ids
         * @description Known correlation ids, as the console reports them.
         */
        get: operations["v2_observe_audit_ids"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/observe/audit/{correlation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Audit Chain
         * @description One reconstructed decision chain, rendered exactly as returned.
         *
         *     The studio does not re-derive, re-order or re-hash it: the console's audit store is
         *     the record, and a studio-side reconstruction would be a second unverified account.
         */
        get: operations["v2_observe_audit_chain"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/observe/deployment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Deployment Status
         * @description The deployment's own startup attestation: seam states, checks and pins
         *     (ADR_UGENCE_MODULE_ADMINISTRATION_SCOPING.md MA-2 as amended, MS-1 to MS-5).
         *
         *     What is returned is what the deployment's fail-closed integrity gate computed
         *     before the port bound, handed to the studio once at composition (MS-2). Nothing is
         *     probed at request time, no file is read, and a configured seam is not a reachable
         *     engine; the answer says so in its own ceiling field. The console's module registry
         *     is not here, by ruling (MS-1).
         */
        get: operations["v2_observe_deployment"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/observe/ledger/{correlation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ledger Chain
         * @description The worker's own tenant's audit-ledger rows for one correlation id, as the
         *     worker read them, with the worker's chain verification (FD-11.3, FD-11.4).
         *
         *     The studio names no tenant and re-derives, re-orders and re-hashes nothing: what
         *     is returned is the worker's answer, including its typed refusal when the chain
         *     does not verify.
         */
        get: operations["v2_observe_ledger_chain"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/policy/compile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Compile Policy
         * @description Compile a reviewed pack into a release.
         *
         *     ``approval`` is required by the request model and ``require_approval`` is left at
         *     the compiler's default of True. The studio has no path that compiles without one.
         */
        post: operations["v2_policy_compile"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/policy/synthesize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Synthesize Policy
         * @description Preview the Workflow IR the canvas would produce. No approval; no release.
         */
        post: operations["v2_policy_synthesize"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/policy/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Validate Policy
         * @description Validate a policy pack. No approval required; produces no release.
         */
        post: operations["v2_policy_validate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/publish/shadow": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Publish Shadow
         * @description Hand a compiled release package to the console's SHADOW governed loop.
         *
         *     There is no non-shadow variant. The console also exposes action-authorization and
         *     clearance routes; the studio's console client cannot reach them (SD-2).
         */
        post: operations["v2_publish_shadow"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/registry/registrations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Registrations
         * @description The registrations in force for this deployment's tenant at ``as_of``.
         *
         *     ``as_of`` is an ISO-8601 instant with a timezone; absent, the request's own instant
         *     is used and reported back. A registration outside its window is absent from the
         *     answer, never flagged.
         */
        get: operations["v2_registry_list"];
        put?: never;
        /**
         * Register System
         * @description Record one typed system registration for this deployment's tenant.
         *
         *     Every field is validated by ai-system-registry's own refusal reasons; the
         *     classification label is recorded uninterpreted; a superseding registration is
         *     admitted only by the package's supersession rule. A refusal is typed, never a 500.
         */
        post: operations["v2_registry_register"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/review/approvals/{approval_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Approval
         * @description One approval record and its hash-linked event chain.
         */
        get: operations["v2_review_read_approval"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/review/decisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Decision
         * @description Relay a human's decision to the review service, verbatim.
         *
         *     The body is forwarded as received. The studio adds no identity, computes no
         *     eligibility and reads nothing but the review service's typed answer, which it
         *     returns whether the decision was recorded, replayed or refused.
         */
        post: operations["v2_review_submit_decision"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/review/queue": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Queue
         * @description Parked ESCALATE instances awaiting a human decision, as the review service lists them.
         *
         *     A HOLD is never presented as awaiting a human (HR-5); the studio counts any it
         *     filtered so the guard is visible.
         */
        get: operations["v2_review_list_queue"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/review/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Shadow Run
         * @description Relay a start of the worker's own shadow run (front-door seam 6, FD-10).
         *
         *     Nothing of the studio's crosses: the body is the operator's correlation id or
         *     nothing, the client pins the mode word ``shadow``, and the worker's own definition
         *     digest binds the run (FD-10.3). The worker's answer, whether it started, replayed or
         *     refused, is returned as the worker said it; a missing review-service URL or an
         *     older worker without the route is a typed gap.
         */
        post: operations["v2_review_start_shadow_run"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/review/runs/{instance_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Run
         * @description One instance: checkpoint view, engine status and its open approvals.
         *
         *     Fingerprints and ``valid_until`` values are history — what was evaluated and when
         *     that evaluation lapsed — never a live permission.
         */
        get: operations["v2_review_read_run"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/review/runs/{instance_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Run Events
         * @description The full runtime event log for one instance, including signal rows.
         */
        get: operations["v2_review_read_run_events"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/simulate/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Run Simulation
         * @description Drive a workflow a bounded number of quanta and report every outcome.
         *
         *     ``execution_mode`` accepts only the non-mutating modes; ``LIVE`` is refused with a
         *     typed 422 rather than being silently downgraded, so a caller that asked for live
         *     execution learns that the studio does not do that.
         */
        post: operations["v2_simulate_run"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/vendor/declarations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Vendor Declarations
         * @description The vendor declarations in force for this deployment's tenant at ``as_of``.
         *
         *     ``as_of`` is an ISO-8601 instant with a timezone; absent, the request's own instant
         *     is used and reported back. A declaration outside its window is absent from the
         *     answer, never flagged. The answer is never ordered by posture: nothing ranks one.
         */
        get: operations["v2_vendor_list"];
        put?: never;
        /**
         * Declare Vendor Dependency
         * @description Record one typed vendor-dependency declaration for this deployment's tenant.
         *
         *     Every field is validated by vendor-dependency's own refusal reasons; a superseding
         *     declaration is admitted only by ``supersession_refusals``. ``vendor_ref`` is an
         *     opaque handle and the record carries no way to reach the vendor. A refusal is
         *     typed, never a 500.
         */
        post: operations["v2_vendor_declare"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ConstitutionPreflightRequest
         * @description Dry-run every pre-signing check.
         *
         *     ``preflight_issuance`` is documented as mutation-free, which is exactly why it is
         *     the only activation entry point the studio may reach (SD-2): it reports what
         *     issuance *would* find without performing it.
         */
        ConstitutionPreflightRequest: {
            /** Approval Reference */
            approval_reference?: string | null;
            /** Constitution */
            constitution: {
                [key: string]: unknown;
            };
            /** Expected Reference Tenant Id */
            expected_reference_tenant_id?: string | null;
            /** Record Id */
            record_id: string;
        };
        /**
         * ConstitutionValidateRequest
         * @description Structural validation of a constitution document. Mutation-free.
         */
        ConstitutionValidateRequest: {
            /** Constitution */
            constitution: {
                [key: string]: unknown;
            };
        };
        /**
         * DataUseDeclareRequest
         * @description Declare one data use for this deployment's tenant (typed intake only, FD-4).
         *
         *     No ``declaration_id`` (derived by the package, never chosen) and no ``tenant_id``
         *     (the deployment's). ``data_ref`` is an opaque, non-secret reference — never the
         *     data, and there is no field that could carry it. ``classification_label``,
         *     ``purpose_label`` and ``residency_label`` are recorded uninterpreted (DE-2, DE-3),
         *     and ``declared_by`` is an opaque handle recorded as presented and unproven
         *     (FD-12.3). Nothing here restricts egress: FD-12.5 invents no restriction for the
         *     absent egress package.
         */
        DataUseDeclareRequest: {
            binding: components["schemas"]["DeclarationBindingInput"];
            /** Classification Label */
            classification_label: string;
            /**
             * Correlation Id
             * @default
             */
            correlation_id: string;
            /** Data Ref */
            data_ref: string;
            /**
             * Declared By
             * @default
             */
            declared_by: string;
            /**
             * Notes
             * @default
             */
            notes: string;
            /** Purpose Label */
            purpose_label: string;
            /**
             * Residency Label
             * @default
             */
            residency_label: string;
            /**
             * Supersedes
             * @default
             */
            supersedes: string;
            validity: components["schemas"]["DeclarationValidityInput"];
        };
        /**
         * DeclarationBindingInput
         * @description The exact system and configuration a declaration is about, as typed fields.
         *
         *     No ``tenant_id``: the tenant is the deployment's and is never caller-supplied.
         *     The two required digests are lowercase sha-256 hex the declarer asserts; the
         *     studio computes none of them.
         */
        DeclarationBindingInput: {
            /** Binding Id */
            binding_id: string;
            /** Configuration Digest */
            configuration_digest: string;
            /** Configuration Id */
            configuration_id: string;
            /** Context Digest */
            context_digest: string;
            /** Context Id */
            context_id: string;
            /**
             * Deployment Environment Ref
             * @default
             */
            deployment_environment_ref: string;
            /** Subject Id */
            subject_id: string;
            /** System Id */
            system_id: string;
            /** System Version */
            system_version: string;
        };
        /**
         * DeclarationValidityInput
         * @description The declaration window, as ISO-8601 instants with a timezone.
         */
        DeclarationValidityInput: {
            /** Expires At */
            expires_at?: string | null;
            /** Issued At */
            issued_at: string;
            /** Stale After */
            stale_after?: string | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * PolicyCompileRequest
         * @description Compile a reviewed pack.
         *
         *     ``approval`` is required and is never defaulted: the compiler's
         *     ``require_approval`` defaults to True and the studio never overrides it.
         */
        PolicyCompileRequest: {
            /** Approval */
            approval: {
                [key: string]: unknown;
            };
            /** Pack */
            pack: {
                [key: string]: unknown;
            };
        };
        /**
         * PolicyPackRequest
         * @description A policy pack as authored on the canvas, carried as a JSON object.
         */
        PolicyPackRequest: {
            /** Pack */
            pack: {
                [key: string]: unknown;
            };
        };
        /**
         * PublishShadowRequest
         * @description Hand a compiled release package to the console's SHADOW governed loop.
         *
         *     There is no non-shadow variant of this request, by construction.
         */
        PublishShadowRequest: {
            /** Compiled Package */
            compiled_package: {
                [key: string]: unknown;
            };
            /** Scenario Id */
            scenario_id?: string | null;
        };
        /**
         * RegistryBindingInput
         * @description The exact system and configuration a registration is about, as typed fields.
         *
         *     No ``tenant_id``: the tenant is the deployment's and is never caller-supplied.
         *     The two required digests are lowercase sha-256 hex the administrator asserts; the
         *     studio computes none of them.
         */
        RegistryBindingInput: {
            /** Binding Id */
            binding_id: string;
            /**
             * Canonical Subject Context Ref
             * @default
             */
            canonical_subject_context_ref: string;
            /** Configuration Digest */
            configuration_digest: string;
            /** Configuration Id */
            configuration_id: string;
            /** Context Digest */
            context_digest: string;
            /** Context Id */
            context_id: string;
            /**
             * Deployment Environment Ref
             * @default
             */
            deployment_environment_ref: string;
            /** Subject Id */
            subject_id: string;
            /** System Id */
            system_id: string;
            /**
             * System Manifest Digest
             * @default
             */
            system_manifest_digest: string;
            /**
             * System Manifest Ref
             * @default
             */
            system_manifest_ref: string;
            /** System Version */
            system_version: string;
        };
        /**
         * RegistryRegisterRequest
         * @description Register one system for this deployment's tenant (typed intake only, FD-4).
         *
         *     No ``registration_id`` (derived by the package, never chosen), no ``tenant_id``
         *     (the deployment's), no ``registered_by`` (the deployment's name and version). The
         *     ``owner_ref`` is an opaque handle recorded as presented and unproven (FD-9.3); the
         *     ``classification_label`` is recorded uninterpreted (registry ADR D-2).
         */
        RegistryRegisterRequest: {
            binding: components["schemas"]["RegistryBindingInput"];
            /** Classification Label */
            classification_label: string;
            /**
             * Notes
             * @default
             */
            notes: string;
            /** Owner Ref */
            owner_ref: string;
            /**
             * Supersedes
             * @default
             */
            supersedes: string;
            validity: components["schemas"]["RegistryValidityInput"];
        };
        /**
         * RegistryValidityInput
         * @description The registration window, as ISO-8601 instants with a timezone.
         */
        RegistryValidityInput: {
            /** Expires At */
            expires_at?: string | null;
            /** Issued At */
            issued_at: string;
            /** Stale After */
            stale_after?: string | null;
        };
        /**
         * ReviewDecisionRequest
         * @description A human's decision on a parked proposal, relayed verbatim (HR-1).
         *
         *     ``decision`` is the human's word — GRANT or REJECT — and the studio forwards it as
         *     typed. ``presented_approver`` is the approver reference the review service listed
         *     as eligible; the studio holds no identity of its own and proves none, which is why
         *     the review service labels every decision ``PRESENTED_UNPROVEN``. ``justification``
         *     is required: a decision without one is not relayed.
         */
        ReviewDecisionRequest: {
            /** Approval Id */
            approval_id: string;
            /**
             * Decision
             * @enum {string}
             */
            decision: "GRANT" | "REJECT";
            /** Justification */
            justification: string;
            /** Presented Approver */
            presented_approver: {
                [key: string]: unknown;
            };
        };
        /**
         * ReviewStartShadowRunRequest
         * @description Ask the governed runtime worker to start its own shadow run (front-door seam 6,
         *     FD-10.2), relayed as typed (FD-10.1).
         *
         *     The one field is the operator's correlation id, a typed token, or nothing. No
         *     workflow, task, provider, mode or definition digest can be carried here, by
         *     construction (FD-10.3): the worker holds the definition and its own digest binds
         *     the run, and the mode word the studio sends is pinned to ``shadow`` in the client.
         */
        ReviewStartShadowRunRequest: {
            /** Correlation Id */
            correlation_id?: string | null;
        };
        /**
         * SimulateRunRequest
         * @description Run a workflow against fixtures, recording every governance decision.
         *
         *     ``execution_mode`` is constrained to the non-mutating modes. LIVE is not a member
         *     of the accepted set and cannot be requested.
         */
        SimulateRunRequest: {
            /** Correlation Id */
            correlation_id?: string | null;
            /**
             * Execution Mode
             * @default DRY_RUN
             */
            execution_mode: string;
            /**
             * Max Quanta
             * @default 16
             */
            max_quanta: number;
            /** Workflow */
            workflow: {
                [key: string]: unknown;
            };
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /**
         * VendorBindingInput
         * @description The exact system and configuration a vendor declaration is about.
         *
         *     No ``tenant_id``: the tenant is the deployment's and is never caller-supplied.
         *     The two required digests are lowercase sha-256 hex the declarer asserts; the
         *     studio computes none of them.
         */
        VendorBindingInput: {
            /** Binding Id */
            binding_id: string;
            /** Configuration Digest */
            configuration_digest: string;
            /** Configuration Id */
            configuration_id: string;
            /** Context Digest */
            context_digest: string;
            /** Context Id */
            context_id: string;
            /**
             * Deployment Environment Ref
             * @default
             */
            deployment_environment_ref: string;
            /** Subject Id */
            subject_id: string;
            /** System Id */
            system_id: string;
            /** System Version */
            system_version: string;
        };
        /**
         * VendorDeclareRequest
         * @description Declare one vendor dependency for this deployment's tenant (typed intake, FD-4).
         *
         *     No ``declaration_id`` (derived by the package, never chosen) and no ``tenant_id``
         *     (the deployment's). ``vendor_ref`` is an opaque, non-secret reference — never an
         *     address, endpoint or credential, and there is no field that could carry one.
         *     ``risk_posture_label`` is recorded uninterpreted (VR-3, FD-13.4): nothing orders,
         *     compares, ranks or scores it, and there is no field for an approval, onboarding
         *     status, tier or certification because no package computes one. ``policy_ref`` is
         *     recorded and never resolved (VR-4), and ``declared_by`` is an opaque handle
         *     recorded as presented and unproven (FD-12.3, carried forward by FD-13.2).
         */
        VendorDeclareRequest: {
            binding: components["schemas"]["VendorBindingInput"];
            /**
             * Correlation Id
             * @default
             */
            correlation_id: string;
            /**
             * Declared By
             * @default
             */
            declared_by: string;
            /**
             * Notes
             * @default
             */
            notes: string;
            /** Policy Ref */
            policy_ref: string;
            /** Risk Posture Label */
            risk_posture_label: string;
            /**
             * Supersedes
             * @default
             */
            supersedes: string;
            validity: components["schemas"]["VendorValidityInput"];
            /** Vendor Ref */
            vendor_ref: string;
        };
        /**
         * VendorValidityInput
         * @description The declaration window, as ISO-8601 instants with a timezone.
         */
        VendorValidityInput: {
            /** Expires At */
            expires_at?: string | null;
            /** Issued At */
            issued_at: string;
            /** Stale After */
            stale_after?: string | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    v2_authority_read_decision: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                decision_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_authority_list_policies: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    v2_authority_read_policy: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_constitution_preflight: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConstitutionPreflightRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_constitution_validate: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConstitutionValidateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_data_use_list: {
        parameters: {
            query?: {
                as_of?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_data_use_declare: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataUseDeclareRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_export_read: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_observe_audit_ids: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    v2_observe_audit_chain: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                correlation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_observe_deployment: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    v2_observe_ledger_chain: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                correlation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_policy_compile: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PolicyCompileRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_policy_synthesize: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PolicyPackRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_policy_validate: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PolicyPackRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_publish_shadow: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishShadowRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_registry_list: {
        parameters: {
            query?: {
                as_of?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_registry_register: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegistryRegisterRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_review_read_approval: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_review_submit_decision: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewDecisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_review_list_queue: {
        parameters: {
            query?: {
                required_role?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_review_start_shadow_run: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewStartShadowRunRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_review_read_run: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                instance_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_review_read_run_events: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                instance_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_simulate_run: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulateRunRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_vendor_list: {
        parameters: {
            query?: {
                as_of?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v2_vendor_declare: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VendorDeclareRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
