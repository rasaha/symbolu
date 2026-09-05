// AUTO-GENERATED from apps/ugence-governance-studio/contracts/openapi_v2.json
// DO NOT EDIT BY HAND. Regenerate with: npm run generate:api-v2
// source_openapi_sha256: dd63180dc91ba7842dc1dc2b6efb3dbc155ea3bd47200f40de7bac85d373f39a
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
}
