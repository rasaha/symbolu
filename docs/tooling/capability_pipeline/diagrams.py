"""Vector figures for the Capability Pipeline document.

Each function returns (svg_text, width_px, height_px). Figures replace the
mermaid blocks in the markdown source; the layout is hand-drawn so the
document renders identically in Word and PDF without a mermaid runtime.
"""

FONT = "Helvetica,Arial,sans-serif"
INK = "#1E2340"
MUTED = "#6B7280"
ARROW = "#4B5563"

# fill, stroke, text
C_VIOLET = ("#ECEAFB", "#5145C7", "#2A2170")
C_BLUE = ("#E4EFF7", "#2B6CB0", "#173A5A")
C_GREEN = ("#E9F7EF", "#2E7D5B", "#14532D")
C_AMBER = ("#FBF1DD", "#B7791F", "#6B4A12")
C_GREY = ("#EEF1F4", "#6B7280", "#374151")
C_RED = ("#FBEBE9", "#C0392B", "#7A2016")
C_TEAL = ("#E1F0F7", "#1C7FA8", "#0E4C63")


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(text, maxchars):
    out = []
    for para in str(text).split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            if line and len(line) + 1 + len(w) > maxchars:
                out.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        out.append(line)
    return out


class SVG:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = []

    def rect(self, x, y, w, h, cat, r=6, sw=1.4, dash=None):
        fill, stroke, _ = cat
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" ry="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'
        )

    def text(self, x, y, lines, fill, fs, weight="400", anchor="middle", dy=None):
        dy = dy or fs * 1.25
        s = "".join(
            f'<tspan x="{x}" y="{y + i * dy}">{esc(ln)}</tspan>' for i, ln in enumerate(lines)
        )
        self.parts.append(
            f'<text text-anchor="{anchor}" font-family="{FONT}" font-size="{fs}" '
            f'font-weight="{weight}" fill="{fill}">{s}</text>'
        )

    def box(self, x, y, w, h, title, sub, cat, tfs=12.5, sfs=10, maxchars=None):
        self.rect(x, y, w, h, cat)
        _, _, tc = cat
        maxchars = maxchars or int(w / (0.53 * sfs))
        sub_lines = wrap(sub, maxchars) if sub else []
        block_h = tfs * 1.25 + len(sub_lines) * sfs * 1.25
        y0 = y + (h - block_h) / 2 + tfs
        self.text(x + w / 2, y0, [title], tc, tfs, "700")
        if sub_lines:
            self.text(x + w / 2, y0 + tfs * 1.25 + 1, sub_lines, INK, sfs)

    def line(self, pts, dash=None, arrow=True, color=ARROW, sw=1.4):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        m = ' marker-end="url(#arr)"' if arrow else ""
        path = "M " + " L ".join(f"{x} {y}" for x, y in pts)
        self.parts.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{sw}"{d}{m}/>'
        )

    def label(self, x, y, text, fs=9.5, fill=MUTED, anchor="middle", bg=True):
        if bg:
            w = 0.55 * fs * len(text) + 6
            self.parts.append(
                f'<rect x="{x - w / 2 if anchor == "middle" else x - 3}" y="{y - fs}" '
                f'width="{w}" height="{fs + 4}" fill="white"/>'
            )
        self.text(x, y, [text], fill, fs, "400", anchor)

    def render(self):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">'
            '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{ARROW}"/></marker></defs>'
            f'<rect width="{self.w}" height="{self.h}" fill="white"/>'
            + "".join(self.parts)
            + "</svg>"
        )


STAGES = ["Define", "Propose", "Verify", "Decide", "Authorize", "Clear", "Execute", "Assure", "Measure"]
STAGE_CATS = [C_VIOLET, C_BLUE, C_TEAL, C_VIOLET, C_GREEN, C_AMBER, C_BLUE, C_TEAL, C_GREEN]


def _nine_stage(subs, feedback_label):
    """Nine stages in a 3x3 wrap layout with a dashed feedback edge from Measure to Define."""
    W = 660
    bw, bh, gx, gy = 190, 64, 45, 40
    x0, y0 = 20, 22
    s = SVG(W, y0 + 3 * bh + 2 * gy + 44)
    pos = []
    for i in range(9):
        r, c = divmod(i, 3)
        x = x0 + c * (bw + gx)
        y = y0 + r * (bh + gy)
        pos.append((x, y))
        s.box(x, y, bw, bh, STAGES[i], subs[i], STAGE_CATS[i], tfs=12.5, sfs=9.6)
    for i in range(8):
        x, y = pos[i]
        nx, ny = pos[i + 1]
        if (i + 1) % 3 != 0:
            s.line([(x + bw, y + bh / 2), (nx, ny + bh / 2)])
        else:
            midy = y + bh + gy / 2
            s.line([(x + bw / 2, y + bh), (x + bw / 2, midy), (nx + bw / 2, midy), (nx + bw / 2, ny)])
    # feedback: from Measure (bottom right) back up to Define (top left) along the outer edge
    mx, my = pos[8]
    dx, dy = pos[0]
    yb = my + bh + 22
    s.line(
        [(mx + bw / 2, my + bh), (mx + bw / 2, yb), (dx + bw / 2 - 60, yb), (dx + bw / 2 - 60, dy + bh / 2), (dx, dy + bh / 2)],
        dash="5,4",
        color=MUTED,
    )
    s.label((mx + dx + bw) / 2, yb - 4, feedback_label)
    return s.render(), s.w, s.h


def fig_sequence():
    subs = [
        "Rules and identity",
        "Advice and plans",
        "Claims and evidence",
        "Business and risk",
        "Exact action",
        "Current conditions",
        "Controlled runtime",
        "Trajectory and effect",
        "Readiness and value",
    ]
    return _nine_stage(subs, "feedback")


def fig_scenario():
    subs = [
        "Signed policies and role bounds",
        "120 → 180 replicas",
        "Metrics, producer and policy",
        "Accept bounded business risk",
        "Exact service and target",
        "Freeze, incident and expiry",
        "Runtime plus Kubernetes",
        "Trajectory and real effect",
        "Readiness, cost and value",
    ]
    return _nine_stage(subs, "policy feedback")


def fig_minimum_path():
    rows = [
        ("Policy Authority + Capacity Policy", "Define bounded scaling rules", C_VIOLET),
        ("Scaling Controller + Agentic Proposer", "Prepare exact recommendation", C_BLUE),
        ("TAP + Trusted Evidence + Authenticity", "Verify claims, producer and policy", C_TEAL),
        ("Decision Authority + Risk Authority", "Approve and mint bounded authority", C_VIOLET),
        ("ActionGate + Action Clearance", "Authorize exact action and recheck now", C_GREEN),
        ("Agent Runtime + Scaling Operations", "Execute controlled mutation", C_BLUE),
        ("Status + Runtime + Execution Assurance", "Revoke, observe and reconcile effect", C_TEAL),
    ]
    bw, bh, gy = 400, 58, 26
    W = 480
    s = SVG(W, 20 + len(rows) * bh + (len(rows) - 1) * gy + 20)
    x = (W - bw) / 2
    for i, (t, sub, cat) in enumerate(rows):
        y = 20 + i * (bh + gy)
        s.box(x, y, bw, bh, t, sub, cat, tfs=12.5, sfs=10)
        if i < len(rows) - 1:
            s.line([(x + bw / 2, y + bh), (x + bw / 2, y + bh + gy)])
    return s.render(), s.w, s.h


def fig_pipeline():
    """Five development bands stacked vertically, with the research lane and frozen state at the side."""
    W, H = 680, 640
    s = SVG(W, H)
    bx, bw = 20, 430
    bands = [
        ("1 · Define contracts", [("Contract-only", 3, C_VIOLET)]),
        (
            "2 · Build the kernel",
            [
                ("Core implemented", 19, C_BLUE),
                ("Phase in progress", 6, C_BLUE),
                ("Last phase done", 3, C_BLUE),
                ("Experimental kernel", 2, C_AMBER),
            ],
        ),
        ("3 · Harden for deployment", [("Reference-grade", 4, C_TEAL), ("CI-verified, pilot pending", 2, C_TEAL)]),
        ("4 · Client pilot", [("Pilot-ready", 0, C_GREY), ("Pilot-validated", 0, C_GREY)]),
        ("5 · Production", [("Production-certified", 0, C_GREY)]),
    ]
    bh, gy = 92, 30
    y = 22
    band_pos = []
    for title, chips in bands:
        s.rect(bx, y, bw, bh, ("#FAFBFE", "#C9CFE3", INK), r=8, sw=1.2)
        s.text(bx + 12, y + 18, [title], INK, 11.5, "700", anchor="start")
        # chips in one or two rows
        cw, ch, cg = 196, 26, 10
        per_row = 2
        for i, (name, n, cat) in enumerate(chips):
            r, c = divmod(i, per_row)
            cx = bx + 12 + c * (cw + cg)
            cy = y + 30 + r * (ch + 6)
            s.rect(cx, cy, cw, ch, cat, r=13, sw=1.2)
            s.text(cx + cw / 2, cy + 17, [f"{name} · {n}"], cat[2], 10, "600")
        band_pos.append((bx, y, bw, bh))
        y += bh + gy
    for i in range(len(bands) - 1):
        _, by, _, bh_ = band_pos[i]
        s.line([(bx + bw / 2, by + bh_), (bx + bw / 2, by + bh_ + gy)])
    # policy feedback from production back to define (left edge)
    _, y5, _, h5 = band_pos[4]
    _, y1, _, h1 = band_pos[0]
    s.line([(bx, y5 + h5 / 2), (bx - 12, y5 + h5 / 2), (bx - 12, y1 + h1 / 2), (bx, y1 + h1 / 2)], dash="5,4", color=MUTED)
    s.parts.append(
        f'<text transform="translate({bx - 16},{(y1 + y5) / 2 + 60}) rotate(-90)" text-anchor="middle" '
        f'font-family="{FONT}" font-size="9.5" fill="{MUTED}">policy feedback</text>'
    )
    # research lane (right)
    rx, rw = bx + bw + 40, 170
    _, y2, _, h2 = band_pos[1]
    ry, rh = y1, h1 + gy + h2
    s.rect(rx, ry, rw, rh, ("#FFFDF5", "#B7791F", C_AMBER[2]), r=8, sw=1.2, dash="6,4")
    s.text(rx + rw / 2, ry + 20, ["Research track", "(parallel lane)"], C_AMBER[2], 11, "700")
    s.rect(rx + 12, ry + 58, rw - 24, 26, C_AMBER, r=13)
    s.text(rx + rw / 2, ry + 75, ["Research-only · 4"], C_AMBER[2], 10, "600")
    s.text(rx + rw / 2, ry + 112, wrap("Feeds evidence into contract and policy revision; never enters the pilot band.", 26), MUTED, 9)
    s.line([(rx, ry + 71), (bx + bw, y1 + h1 / 2)], dash="5,4", color=MUTED)
    s.label((rx + bx + bw) / 2 + 4, (ry + 71 + y1 + h1 / 2) / 2 - 6, "evidence only", fs=9)
    # frozen state (right, beside band 3)
    _, y3, _, h3 = band_pos[2]
    fy = y3 - 6
    s.rect(rx, fy, rw, 54, C_GREEN, r=27, sw=1.2)
    s.text(rx + rw / 2, fy + 23, ["Frozen API · 2"], C_GREEN[2], 11, "700")
    s.text(rx + rw / 2, fy + 40, ["side state from band 2 onward"], MUTED, 8.6)
    s.line([(bx + bw, y2 + h2 - 18), (rx, fy + 27)], dash="5,4", color=MUTED)
    s.label((rx + bx + bw) / 2 + 4, (y2 + h2 - 18 + fy + 27) / 2 - 6, "API freeze", fs=9)
    # note
    s.text(bx, H - 14, ["All 45 capabilities sit in bands 1–3. Bands 4 and 5 are empty by each package's own declaration."], MUTED, 9.5, anchor="start")
    return s.render(), s.w, s.h


ALL = {
    "sequence": fig_sequence,
    "chain": None,  # the text chain in Section 14 is rendered as a monospace block, not a figure
    "scenario": fig_scenario,
    "minimum_path": fig_minimum_path,
    "pipeline": fig_pipeline,
}
