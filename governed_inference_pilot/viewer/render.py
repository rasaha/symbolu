"""Local static operator trace viewer (Phase 22). Renders a trace to a self-contained HTML string.
NOT a production dashboard: no auth, no deployment, no live data. Deterministic."""
from __future__ import annotations

from typing import Any
from ..audit import AuditTrace


def render_html(trace: AuditTrace, internal: bool = False) -> str:
    v = trace.view(internal=internal)
    rows = ""
    for e in v["events"]:
        rows += (f"<tr><td>{e['seq']}</td><td>{e['stage']}</td><td>{e['component_version']}</td>"
                 f"<td>{e['disposition']}</td><td>{e['shadow_outcome']}</td>"
                 f"<td>{', '.join(e['reason_codes'])}</td><td>{e['latency_units']}</td>"
                 f"<td>{e.get('error','')}</td></tr>")
    return f"""<section class="gip-trace">
<h2>Trace {v['trace_id']}</h2>
<p>Final: <strong>{v['final_shadow_disposition']}</strong> ·
   Human review: {v['human_review_state']} ·
   Replay signature: <code>{v['replay_signature'][:16]}</code></p>
<table border="1"><thead><tr><th>#</th><th>stage</th><th>version</th><th>disposition</th>
<th>shadow</th><th>reasons</th><th>latency</th><th>error</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="note">Shadow-only view. No governed action was performed. {'Internal' if internal else 'Redacted'} view.</p>
</section>"""
