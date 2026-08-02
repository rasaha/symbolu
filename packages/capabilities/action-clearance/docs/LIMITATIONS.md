# Limitations (read before drawing conclusions)

- **Action Clearance is not ActionGate.** It evaluates the immediate executability
  of an *existing* authorization; it never authorizes.
- **Action Clearance never creates authorization** and never broadens one.
- **CLEAR is not execution.** A CLEAR result does not itself permit execution; the
  downstream boundary must validate a current receipt and acquire a reservation.
- **The package performs no external calls** — no GitHub/identity/incident/
  change-management/database/Kubernetes/robotics client, no network, no credentials.
- **The package stores nothing** and **reserves nothing** (no `reserve_once`).
- **The package implements no GitHub support** (or any domain adapter). Tests use
  neutral fixtures only.
- **The package does not replace company policy or human authority.** `ESCALATE`
  defers to a human/specialist; the package encodes deterministic policy, not
  judgement.
- **Enforcement remains blocked** on durable receipt storage and atomic one-time
  reservation, which are out of scope for this phase.
