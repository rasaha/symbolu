"""The reviewer roster EXACTLY as supplied in the activation request.

Every field was provided as an unfilled template placeholder. It is recorded here verbatim (placeholders
intact) so the eligibility gate evaluates the real input rather than an assumed-complete roster. Nothing is
filled in on the reviewers' behalf.
"""

PROVIDED_ROSTER = {
    "R1": {
        "pseudonymous_id": "[R1_ID]",
        "role": "[TECHNICAL REVIEWER / POLICY-RISK REVIEWER / DOMAIN REVIEWER]",
        "expertise": "[BRIEF DESCRIPTION]",
        "real_reviewer": "YES",                 # asserted, but unbacked by a filled pseudonymous ID
        "confidentiality_ack": "[YES/NO]",
        "coi_declaration": "[YES/NO]",
        "access_scope": "[SCOPE]",
    },
    "R2": {
        "pseudonymous_id": "[R2_ID]",
        "role": "[TECHNICAL REVIEWER / POLICY-RISK REVIEWER / DOMAIN REVIEWER]",
        "expertise": "[BRIEF DESCRIPTION]",
        "real_reviewer": "YES",
        "confidentiality_ack": "[YES/NO]",
        "coi_declaration": "[YES/NO]",
        "access_scope": "[SCOPE]",
    },
    "A1": {
        "pseudonymous_id": "[A1_ID OR NONE]",
        "role": "INDEPENDENT ADJUDICATOR",
        "real_reviewer": "[YES/NOT APPLICABLE]",
        "independence_declaration": "[YES/NO/NOT APPLICABLE]",
        "access_scope": "[SCOPE OR NOT APPLICABLE]",
    },
}
