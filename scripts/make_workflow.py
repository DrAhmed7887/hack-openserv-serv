#!/usr/bin/env python3
"""Writes docs/workflow.svg (16:9) and docs/workflow_4x5.svg (LinkedIn 4:5) from one list of steps.

Every step names the module that does it; tests/test_workflow_diagram.py checks each one exists, so the picture
cannot drift from the code. Run: python3 scripts/make_workflow.py   (PNG renders are made from these SVGs.)
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, LINE, BG, CARD = "#1b2430", "#566273", "#c9d1db", "#f6f7f9", "#ffffff"
ACCENT, WARN, BAD, OK = "#1f5f8b", "#8a5a00", "#9b2c2c", "#1d6b43"
FONT = "Inter, -apple-system, 'Segoe UI', Roboto, sans-serif"
MONO = "ui-monospace, Menlo, monospace"

# (title, module, what it checks). The module path is checked against the repo by a test.
STEPS = [
    ("Catalog + case", "data/catalog.json", "synthetic only"),
    ("1 · Inputs", "src/contract_audit/inputs.py", "schema, bounds, text"),
    ("2 · Capability", "src/contract_audit/catalog.py", "quote, hash, negation"),
    ("3 · Calls", "src/contract_audit/calls.py", "tool, study, arg values"),
    ("4 · Receipts", "src/contract_audit/receipts.py", "executor, sha256, status"),
    ("5 · Coverage", "src/contract_audit/coverage.py", "4 dispositions"),
    ("6 · Report", "src/contract_audit/reconcile.py", "claims need receipts"),
    ("Audit JSON", "src/contract_audit/audit.py", "full support or gaps"),
]
SERV_MODULE = "src/contract_audit/serv.py"
TITLE = "How the audit decides"
SUBTITLE = "Example: synthetic case c07. The report reads as finished; 1 of 6 required assessments is fully supported."
RULE = "Full support only when the mapping is confirmed, the call is valid and its receipt checks out."
SERV_LINES = ["Uncertain only → SERV Reasoning (serv.py → OpenServ inference API, strict JSON) → advice:",
              "a verdict and a verbatim quote that names the study type. A person confirms; it never changes the result."]
SERV_LINES_TALL = ["Uncertain only → SERV Reasoning", "(serv.py → OpenServ API, strict JSON)",
                   "→ verdict + verbatim quote that", "names the study type.",
                   "A person confirms. It never", "changes the result."]


def text(x, y, s, size, weight=400, fill=INK, family=FONT, anchor="start", halo=False):
    ring = f' stroke="{BG}" stroke-width="12" stroke-linejoin="round" paint-order="stroke"' if halo else ""
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{ring}>{escape(s)}</text>')


def box(x, y, w, h, step, size):
    title, module, what = step
    stroke = ACCENT if title == "Audit JSON" else LINE
    return "".join([
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{CARD}" stroke="{stroke}" stroke-width="2"/>',
        text(x + 20, y + size + 18, title, size + 2, 700),
        text(x + 20, y + 2 * size + 30, Path(module).name, size - 2, 400, ACCENT, MONO),
        text(x + 20, y + 3 * size + 40, what, size, 400, MUTED),
    ])


def arrow(x1, y1, x2, y2, color=MUTED, dashed=False, marker="a"):
    dash = ' stroke-dasharray="10 8"' if dashed else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="3"{dash} '
            f'marker-end="url(#{marker})"/>')


def defs():
    return ("<defs>"
            f'<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>'
            f'<marker id="w" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{WARN}"/></marker></defs>')


def wide():
    W, H, bw, bh, gap, size = 1600, 900, 335, 150, 48, 24
    xs = [60 + i * (bw + gap) for i in range(4)]
    rows = [205, 425]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', defs(),
           f'<rect width="{W}" height="{H}" fill="{BG}"/>',
           text(60, 92, TITLE, 44, 700), text(60, 140, SUBTITLE, 25, 400, MUTED)]
    for i, step in enumerate(STEPS):
        r, c = divmod(i, 4)
        out.append(box(xs[c], rows[r], bw, bh, step, size))
        if c < 3:
            out.append(arrow(xs[c] + bw + 6, rows[r] + bh / 2, xs[c + 1] - 6, rows[r] + bh / 2))
    out.append(f'<path d="M{xs[3] + bw / 2},{rows[0] + bh + 4} V{rows[0] + bh + 36} H{xs[0] + bw / 2} '
               f'V{rows[1] - 8}" fill="none" stroke="{MUTED}" stroke-width="3" marker-end="url(#a)"/>')
    sy = 668
    out.append(f'<rect x="60" y="{sy}" width="{W - 120}" height="150" rx="14" fill="#fbf5ea" stroke="{WARN}" '
               f'stroke-width="2" stroke-dasharray="10 8"/>')
    out.append(text(84, sy + 44, SERV_LINES[0], 25, 600, WARN))
    out.append(text(84, sy + 84, SERV_LINES[1], 25, 400, INK))
    out.append(text(84, sy + 124, "Human: the engineer acts on each gap. Physician/operator sign-off on obligations: pending.",
                    24, 400, MUTED))
    out.append(arrow(xs[1] + bw / 2, rows[1] + bh + 4, xs[1] + bw / 2, sy - 6, WARN, True, "w"))
    out.append(arrow(xs[3] + bw / 2, sy - 6, xs[3] + bw / 2, rows[1] + bh + 6, WARN, True, "w"))
    out.append(text(xs[3] + bw / 2 + 14, sy - 16, "advice only", 24, 600, WARN))
    out.append(text(60, 628, RULE, 25, 600, OK, halo=True))
    out.append(text(W - 60, H - 30, "Synthetic data and a fictional catalog. No images, no patients.", 22, 400, MUTED,
                    anchor="end"))
    out.append("</svg>")
    return "\n".join(out)


def tall():
    W, H, bw, bh, size = 1080, 1350, 480, 170, 28
    xs = [40, 560]
    ys = [250, 450, 650, 850]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', defs(),
           f'<rect width="{W}" height="{H}" fill="{BG}"/>',
           text(40, 96, TITLE, 52, 700),
           text(40, 150, "The report reads as finished.", 30, 400, MUTED),
           text(40, 192, "1 of 6 assessments is fully supported.", 30, 600, BAD)]
    for i, step in enumerate(STEPS):
        r, c = divmod(i, 2)
        out.append(box(xs[c], ys[r], bw, bh, step, size))
        if c == 0:
            out.append(arrow(xs[0] + bw + 4, ys[r] + bh / 2, xs[1] - 6, ys[r] + bh / 2))
        elif r < 3:
            out.append(f'<path d="M{xs[1] + bw / 2},{ys[r] + bh + 2} V{ys[r] + bh + 15} H{xs[0] + bw / 2} '
                       f'V{ys[r + 1] - 6}" fill="none" stroke="{MUTED}" stroke-width="3" marker-end="url(#a)"/>')
    sy = 1048
    out.append(f'<rect x="40" y="{sy}" width="{W - 80}" height="262" rx="14" fill="#fbf5ea" stroke="{WARN}" '
               f'stroke-width="2" stroke-dasharray="10 8"/>')
    for j, line in enumerate(SERV_LINES_TALL[:4]):
        out.append(text(64, sy + 44 + j * 40, line, 28, 600 if j == 0 else 400, WARN if j == 0 else INK))
    out.append(text(64, sy + 44 + 4 * 40, " ".join(SERV_LINES_TALL[4:]), 28, 600, INK))
    out.append(text(64, sy + 44 + 5 * 40 + 4, "Synthetic data. Rules signed 11 Nov.", 28, 400, MUTED))
    out.append("</svg>")
    return "\n".join(out)


def main():
    (ROOT / "docs" / "workflow.svg").write_text(wide() + "\n", encoding="utf-8")
    (ROOT / "docs" / "workflow_4x5.svg").write_text(tall() + "\n", encoding="utf-8")
    print("wrote docs/workflow.svg and docs/workflow_4x5.svg")


if __name__ == "__main__":
    main()
