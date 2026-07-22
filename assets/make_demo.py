#!/usr/bin/env python3
"""Generate assets/demo.svg: a self-contained animated terminal demo for exform.

No external dependencies. Uses SMIL <animate> so it plays on GitHub (which
serves README images via camo and preserves SMIL animation). Regenerate with:
    python assets/make_demo.py
"""
import os
from html import escape

BG = "#1b1e24"
FG = "#d7dae0"
GREEN = "#7ec699"
BLUE = "#6cb6ff"
YELLOW = "#e2c08d"
GREY = "#7d8590"
PROMPT = "#8ddb8c"

FONT = "ui-monospace, 'SF Mono', 'Cascadia Code', Menlo, Consolas, monospace"
FS = 15
LH = 22
PAD_X = 18
PAD_Y = 46
W = 780
CHARW = FS * 0.60
TOTAL = 9.0

# (delay seconds, [(text, color), ...])
lines = [
    (0.2, [("$ ", PROMPT), ("printf 'John Smith\\nGrace Hopper\\nAlan Turing\\n' | \\", FG)]),
    (0.5, [("    exform -e ", FG), ("'John Smith => Smith, J.'", YELLOW), (" \\", FG)]),
    (0.9, [("           -e ", FG), ("'Grace Hopper => Hopper, G.'", YELLOW)]),
    (2.6, [("Smith, J.", GREEN)]),
    (2.9, [("Hopper, G.", GREEN)]),
    (3.2, [("Turing, A.", GREEN), ("      \u2190 line it never saw", GREY)]),
    (5.0, [("$ ", PROMPT), ("... --dry-run", FG)]),
    (6.0, [("program: ", GREY), ("field(ws,1) + ', ' + line.first + '.'", BLUE)]),
]

n = len(lines)
H = PAD_Y + LH * n + 14


def loop_anim(delay):
    fade = 0.25
    return (
        f'<animate attributeName="opacity" '
        f'values="0;0;1;1;0" '
        f'keyTimes="0;{delay/TOTAL:.3f};{(delay+fade)/TOTAL:.3f};0.965;1" '
        f'dur="{TOTAL:.1f}s" repeatCount="indefinite"/>'
    )


parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
    f'viewBox="0 0 {W} {H}" font-family="{FONT}" font-size="{FS}">',
    f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="{BG}"/>',
    '<circle cx="20" cy="20" r="6" fill="#ff5f56"/>',
    '<circle cx="40" cy="20" r="6" fill="#ffbd2e"/>',
    '<circle cx="60" cy="20" r="6" fill="#27c93f"/>',
    f'<text x="{W//2}" y="25" fill="{GREY}" text-anchor="middle" '
    f'font-size="13">exform \u2014 reshape text by example</text>',
]

for i, (delay, spans) in enumerate(lines):
    y = PAD_Y + i * LH + FS
    tspans = []
    cx = PAD_X
    for text, color in spans:
        tspans.append(
            f'<tspan x="{cx:.0f}" fill="{color}" xml:space="preserve">'
            f'{escape(text)}</tspan>'
        )
        cx += len(text) * CHARW
    # default opacity=1 so renderers that ignore SMIL show a readable static
    # frame (whole session visible) rather than a blank box.
    parts.append(
        f'<text y="{y}" opacity="1">' + "".join(tspans) + loop_anim(delay) + '</text>'
    )

# blinking cursor after the last line
cy = PAD_Y + (n - 1) * LH + FS
parts.append(
    f'<rect x="{PAD_X + 92}" y="{cy - FS + 3}" width="9" height="{FS}" '
    f'fill="{FG}" opacity="0">'
    f'<animate attributeName="opacity" values="0;0;1;0;1;0;1;0" '
    f'keyTimes="0;0.66;0.72;0.78;0.84;0.90;0.96;1" '
    f'dur="{TOTAL:.1f}s" repeatCount="indefinite"/></rect>'
)

parts.append('</svg>')
svg = "\n".join(parts) + "\n"

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.svg")
with open(out, "w") as f:
    f.write(svg)
print("wrote", out, len(svg), "bytes")
