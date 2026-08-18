import sys, hashlib, json
root = sys.argv[1]
P = root + "/packages/trusted-evidence-authority"
sys.path.insert(0, P+"/src"); sys.path.insert(0, P+"/tests")
from ugence_trusted_evidence_authority.contracts.canonical import canonical_digest
import _builders as B1
import ugence_trusted_evidence_authority.api as api
from ugence_trusted_evidence_authority.contracts.reasons import TrustedEvidenceRefusalReason as R
print("  EvidenceSchemaRef        ", canonical_digest(api.EvidenceSchemaRef(schema_id="ugence.evidence.model-benchmark", schema_version="1")))
print("  CanonicalEvidenceIdentity", B1.identity().canonical_digest())
print("  api symbol count         ", len(api.__all__))
print("  refusal members          ", len(list(R)))
print("  TEV-1 first19 sha256     ", hashlib.sha256("|".join(m.name for m in list(R)[:19]).encode()).hexdigest())
