# DilChat internal-pilot participant disclosure (owner-approved, DILCHAT-D-PL-4)

Show this to every participant **before** participation. It is owner-approved
text: do not paraphrase it, and do not soften the two claims it deliberately
makes — that this is not a production service, and that reports are read but not
adjudicated.

The pilot is **invitation-only**. No open registration, public download link,
public App Store or Play Store listing, or uncontrolled invitation forwarding is
authorized. Distribution uses a non-public channel (iOS: TestFlight or approved
private distribution; Android: EAS internal testing or private build
distribution), and participant access must be revocable.

---

## DilChat Internal Pilot

DilChat is currently an internal pilot and is not a publicly released production
service.

The pilot is intended to evaluate account creation, pairing, private messaging,
safety controls, reliability, and the overall user experience.

Messages and account information are processed by the DilChat pilot systems
according to the pilot's privacy and security controls.

You may block another participant or submit a safety report. Submitted safety
reports may be reviewed by the named DilChat safety reviewer. The current pilot
does not yet operate a full moderation or adjudication process, so submitting a
report does not imply that an automated or formal enforcement action will occur.

Push notifications are not enabled in the initial pilot. Message availability
remains based on the DilChat application and its authoritative server state.

Participation is invitation-only and may be suspended or ended while the pilot is
being evaluated.

---

## Conditional paragraph — only if Expo Push is enabled in a later round

**Do not include this while `DILCHAT_PUSH_TRANSPORT=null`** (the ratified setting
for the first pilot, D-PL-2). Add it only when push is actually enabled:

> DilChat notifications contain no message body or sender name. Notification
> delivery requires device-token and notification-timing information to pass
> through Expo and the underlying Apple or Google notification infrastructure.

Enabling push is a subsequent pilot-round decision under the already-ratified
DEC-3C-1 privacy boundary; it is not authorized by D-PL-4.
