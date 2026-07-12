"""Cross-domain authorization artifacts (all Ed25519).

The broker's trust rests ONLY on these asymmetric artifacts — never on the
frozen HMAC token, which stays confined to the gateway domain (see
IMPLEMENTATION_FINDINGS). Property guarantees:
  * the agent holds no private key -> cannot produce any valid artifact;
  * the gateway holds only its own key -> cannot forge an approval or policy sig;
  * the broker holds no signing key -> cannot forge a gateway authz, approval, or
    policy signature; it only verifies.
"""

from __future__ import annotations

from . import crypto


def build_approval(approver_purpose, approver_sk, *, action_hash, policy_hash,
                   issued_at, expiry, nonce):
    body = {"action_hash": action_hash, "policy_hash": policy_hash,
            "approver_id": approver_purpose, "issued_at": issued_at,
            "expiry": expiry, "nonce": nonce}
    return {**body, "signature": crypto.sign(approver_sk, body)}


def verify_approval(keyring, approval, *, action_hash, policy_hash, now) -> bool:
    body = {k: approval[k] for k in ("action_hash", "policy_hash", "approver_id",
                                     "issued_at", "expiry", "nonce")}
    if approval["action_hash"] != action_hash or approval["policy_hash"] != policy_hash:
        return False
    if now >= approval["expiry"]:
        return False
    return keyring.verify(approval["approver_id"], body, approval["signature"])


def approvals_digest(approvals) -> str:
    return crypto.digest_hex([a["signature"] for a in approvals])


def build_exec_authz(gateway_sk, intent: dict, approvals: list) -> dict:
    signed_body = {"intent": intent, "approvals_digest": approvals_digest(approvals)}
    return {"intent": intent, "approvals": approvals,
            "approvals_digest": signed_body["approvals_digest"],
            "signature": crypto.sign(gateway_sk, signed_body)}


def verify_exec_authz(keyring, authz: dict, *, now, expected_gateway_identity) -> tuple:
    """Return (ok, reason). Verifies the gateway Ed25519 signature + binding."""
    intent = authz.get("intent")
    if not isinstance(intent, dict):
        return False, "E_AUTHZ_MALFORMED"
    if intent.get("gateway_identity") != expected_gateway_identity:
        return False, "E_AUTHZ_IDENTITY"
    if now >= intent.get("expiry", ""):
        return False, "E_AUTHZ_EXPIRED"
    if authz.get("approvals_digest") != approvals_digest(authz.get("approvals", [])):
        return False, "E_AUTHZ_APPROVALS_TAMPERED"
    body = {"intent": intent, "approvals_digest": authz["approvals_digest"]}
    if not keyring.verify("gateway", body, authz.get("signature", "")):
        return False, "E_AUTHZ_BAD_GATEWAY_SIGNATURE"
    return True, "OK"


# --- Ed25519-signed policy bundle (cross-domain policy provenance) ---

def sign_policy_bundle(policy_root_sk, bundle: dict, policy_hash: str) -> dict:
    body = {"policy_hash": policy_hash}
    return {"policy_hash": policy_hash, "signature": crypto.sign(policy_root_sk, body)}


def verify_policy_signature(keyring, policy_hash: str, policy_sig: dict) -> bool:
    if policy_sig.get("policy_hash") != policy_hash:
        return False
    return keyring.verify("policy_root", {"policy_hash": policy_hash},
                          policy_sig.get("signature", ""))
