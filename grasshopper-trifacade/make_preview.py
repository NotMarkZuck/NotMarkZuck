"""Draws preview.svg (terrace + fold examples) from the TriFacade core, no Rhino needed."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import TriFacade as tf  # noqa: E402

L, W, HT = 12.0, 120.0, 72.0
rect = lambda x, y: 0 <= x <= W and 0 <= y <= HT
pt = lambda px, py: (lambda x, y: math.hypot(x - px, y - py))
COLS = ["#cfcfcf", "#e68c32", "#468cd2"]


YAW, PITCH = math.radians(-40), math.radians(18)
LIGHT = (0.45, 0.55, 0.70)


def rot(p):
    x, y, z = p                      # facade in x/y, depth z towards viewer
    x, z = x * math.cos(YAW) - z * math.sin(YAW), x * math.sin(YAW) + z * math.cos(YAW)
    y, z = y * math.cos(PITCH) - z * math.sin(PITCH), y * math.sin(PITCH) + z * math.cos(PITCH)
    return x, y, z


def project(p, ox, oy, s=4.4):
    x, y, _ = rot(p)
    return ox + s * x, oy - s * y


def shade(hexcol, tri):
    a, b, c = tri
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    m = math.sqrt(sum(q * q for q in n)) or 1
    k = 0.45 + 0.55 * abs(sum(n[i] * LIGHT[i] for i in range(3)) / m)
    rgb = [int(hexcol[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(min(255, int(q * k)) for q in rgb)


def draw(res, ox, oy, title):
    out = ['<text x="%d" y="%d" font-size="18" font-family="sans-serif">%s</text>'
           % (ox, oy - 435, title)]
    tris = sorted(zip(res["tris"], res["panel_type"]),
                  key=lambda t: sum(rot(res["pos"][k])[2] for k in t[0]))
    for t, ty in tris:
        pts = " ".join("%.1f,%.1f" % project(res["pos"][k], ox, oy) for k in t)
        out.append('<polygon points="%s" fill="%s" stroke="#333" stroke-width="0.8"/>'
                   % (pts, shade(COLS[ty % 3], [res["pos"][k] for k in t])))
    for n, line in enumerate(res["report"][:4]):
        out.append('<text x="%d" y="%d" font-size="12" font-family="monospace">%s</text>'
                   % (ox, oy + 30 + 15 * n, line.replace("&", "&amp;")))
    return out


terrace = tf.generate((0, 0, W, HT), rect, L,
                      sources=[(pt(40, 36), 1.0), (pt(90, 30), -1.0)],
                      node_targets=[(96, 60, 1.0)], radius=36, depth=9, levels=3)
fold = tf.generate((0, 0, W, HT), rect, L, mode=1,
                   sources=[(pt(60, 36), 1.0)], radius=40, depth=7, levels=3)
svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="580" '
       'style="background:#fff">']
svg += draw(terrace, 60, 470, "Mode 0  TERRACE  - bump, dent, single raised node (2 panel types)")
svg += draw(fold, 700, 470, "Mode 1  FOLD  - pleats, all panels identical (1 panel type)")
svg.append("</svg>")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview.svg"), "w").write("\n".join(svg))
print("wrote preview.svg")
