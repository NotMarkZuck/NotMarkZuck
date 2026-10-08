"""GS Gallery — opening "listening" spread (placeholder version).

Layout follows mood image 2 (collage + hand drawing + timeline), restyled in
the portfolio system: white page, greyscale, one red accent, everything built
from points. Every grey dot-field is a PLACEHOLDER for a real photo / drawing.

Run:  python3 make_gs_listening.py  ->  gs_listening.svg / .pdf / .png
"""
import math
import random
from pathlib import Path

W, H = 1584, 612                    # one spread, 22 x 8.5 in
GUTTER = W / 2
BG, INK, GREY, LIGHT, ACCENT = "#ffffff", "#0b0b0b", "#8a8a8a", "#d9d9d6", "#e8262b"
SANS = "Inter, 'Helvetica Neue', Arial, sans-serif"
MONO = "'IBM Plex Mono', 'DejaVu Sans Mono', 'Courier New', monospace"
rng = random.Random(3)
out = []


def text(x, y, s, size=8, fill=INK, family=MONO, weight="400", anchor="start", spacing=0.6):
    out.append(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
               f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
               f'letter-spacing="{spacing}" xml:space="preserve">{s}</text>')


def halftone(x, y, w, h, label, seed, step=5.0, dark=0.7, frame=True):
    """A dot-field stand-in for a photo: dot size follows a smooth random 'image'."""
    r = random.Random(seed)
    waves = [(r.uniform(0.004, 0.02), r.uniform(0.004, 0.02), r.uniform(0, 6.3)) for _ in range(4)]
    out.append(f'<g class="placeholder" id="ph-{seed}">')
    yy = y + step / 2
    while yy < y + h:
        xx = x + step / 2
        while xx < x + w:
            v = sum(math.sin(xx * a + yy * b + p) for a, b, p in waves) / 4      # -1..1
            v = (v + 1) / 2 * dark + r.uniform(-0.05, 0.05)
            rad = max(0, v) * step * 0.55
            if rad > 0.25:
                out.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="{rad:.2f}" fill="{INK}"/>')
            xx += step
        yy += step
    if frame:
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{LIGHT}" stroke-width="0.5"/>')
    out.append('</g>')
    # label chip
    out.append(f'<rect x="{x + 6}" y="{y + 6}" width="{len(label) * 4.3 + 10}" height="12" fill="{BG}"/>')
    text(x + 11, y + 15, label, 6.2, ACCENT)


def site_map(x, y, w, h):
    """Abstract street grid + lake as dots, site in red. Placeholder for a real map."""
    out.append('<g id="site-map">')
    out.append(f'<clipPath id="mapclip"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>')
    out.append(f'<g clip-path="url(#mapclip)">')
    # lake: fine grey dots on the right third
    for i in range(900):
        px, py = x + w * rng.uniform(0.68, 1.0), y + h * rng.uniform(0, 1)
        if px > x + w * (0.70 + 0.08 * math.sin((py - y) / 40)):
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="0.6" fill="{GREY}" opacity="0.6"/>')
    # streets: two rotated grids
    for ang, sp in ((0, 26), (90, 22), (28, 60)):
        for k in range(-20, 40):
            a = math.radians(ang)
            cx0, cy0 = x + k * sp * math.sin(a) * (1 if ang else 0) + (k * sp if ang == 90 else 0), y
            if ang == 0:
                out.append(f'<line x1="{x}" y1="{y + k * sp}" x2="{x + w * 0.72}" y2="{y + k * sp}" stroke="{LIGHT}" stroke-width="0.6"/>')
            elif ang == 90:
                out.append(f'<line x1="{x + k * sp}" y1="{y}" x2="{x + k * sp}" y2="{y + h}" stroke="{LIGHT}" stroke-width="0.6"/>')
            else:
                out.append(f'<line x1="{x + k * sp}" y1="{y + h}" x2="{x + k * sp + h * math.tan(a)}" y2="{y}" stroke="{LIGHT}" stroke-width="1.2"/>')
    # site
    sx, sy = x + w * 0.52, y + h * 0.42
    out.append(f'<polygon points="{sx},{sy} {sx + 34},{sy - 6} {sx + 40},{sy + 26} {sx + 4},{sy + 30}" fill="{ACCENT}"/>')
    out.append('</g>')
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{LIGHT}" stroke-width="0.5"/>')
    out.append('</g>')
    out.append(f'<rect x="{x + 6}" y="{y + 6}" width="132" height="12" fill="{BG}"/>')
    text(x + 11, y + 15, "PLACEHOLDER — SITE MAP", 6.2, ACCENT)
    text(sx + 46, sy + 14, "SITE", 7, ACCENT, weight="700")
    text(x + w * 0.80, y + h * 0.5, "LAKE MICHIGAN", 6, GREY)


def terrain_bands(x0, x1, y0):
    """Soft layered bands behind the hand drawing (the pink 'mountains' in the reference)."""
    for i, (col, op) in enumerate(((LIGHT, 0.55), (LIGHT, 0.35), ("#f3d3d4", 0.6))):
        pts = []
        for k in range(0, 61):
            xx = x0 + (x1 - x0) * k / 60
            yy = y0 + i * 34 + 18 * math.sin(k / 6 + i * 1.7) + 10 * math.sin(k / 2.3 + i)
            pts.append(f"{xx:.1f},{yy:.1f}")
        back = []
        for k in range(60, -1, -1):
            xx = x0 + (x1 - x0) * k / 60
            yy = y0 + i * 34 + 46 + 14 * math.sin(k / 5 + i * 2.1)
            back.append(f"{xx:.1f},{yy:.1f}")
        pts += back
        out.append(f'<polygon points="{" ".join(pts)}" fill="{col}" opacity="{op}"/>')


def main():
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    out.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

    # ---- running header / footer ------------------------------------------------
    text(40, 34, "03  GS GALLERY", 8, INK, weight="700", spacing=1.5)
    text(W - 40, 34, "PRECAST EXHIBITION GALLERY · MILWAUKEE, WI · INDIVIDUAL · FALL 20XX · INSTRUCTOR [NAME]",
         6.5, GREY, anchor="end", spacing=0.8)
    text(40, H - 22, "03", 8, GREY)
    text(W - 40, H - 22, "04", 8, GREY, anchor="end")

    # ---- LEFT PAGE: what the site sounds / looks like -------------------------------
    site_map(40, 60, 300, 230)
    halftone(40, 300, 170, 150, "PHOTO — SITE, STREET LEVEL", 11)
    halftone(220, 300, 120, 150, "PHOTO — DETAIL", 12, step=4)

    # chapter label + idea statement (the one paragraph a reviewer reads)
    text(372, 84, "01 / LISTENING", 8, ACCENT, weight="700", spacing=1.5)
    out.append(f'<text x="372" y="122" font-family="{SANS}" font-size="30" font-weight="700" fill="{INK}" letter-spacing="-0.5">'
               f'<tspan x="372">What did the</tspan><tspan x="372" dy="34">site already say?</tspan></text>')
    idea = ["[Idea statement, max 60 words. Placeholder: Before drawing a",
            "plan I spent [n] hours on the site recording sound, movement",
            "and light. The paths people already walked became the gallery's",
            "single folding line; the quiet corners became its courtyards.]"]
    for i, line in enumerate(idea):
        text(372, 190 + i * 13, line, 7.6, INK, spacing=0.2)

    # four listening notes (the 'objectives' boxes in the reference)
    notes = [("01", "SOUND", "decibel walk, 6 points"), ("02", "MOVEMENT", "desire lines, 1 day"),
             ("03", "LIGHT", "shadow study, 4 hours"), ("04", "PEOPLE", "[n] short interviews")]
    bx, by, bw, bh = 372, 268, 92, 120
    for i, (n, t, sub) in enumerate(notes):
        x = bx + i * (bw + 8)
        out.append(f'<rect x="{x}" y="{by}" width="{bw}" height="{bh}" fill="none" stroke="{GREY}" stroke-width="0.6" stroke-dasharray="2 2"/>')
        text(x + 7, by + 15, n, 9, ACCENT, weight="700")
        text(x + 7, by + 28, t, 7.5, INK, weight="700", spacing=1)
        text(x + 7, by + 39, sub, 5.8, GREY)
        halftone(x + 7, by + 48, bw - 14, bh - 56, "SKETCH", 20 + i, step=3.2, dark=0.45, frame=False)
    # small data strip: foot traffic by hour (economics voice) — placeholder numbers
    text(372, 412, "FOOT TRAFFIC PAST THE SITE, PEOPLE / HOUR  (PLACEHOLDER DATA)", 6, GREY, spacing=0.6)
    counts = [3, 2, 2, 4, 9, 18, 26, 22, 19, 24, 31, 28, 17, 12, 8, 5]
    for i, c in enumerate(counts):
        x = 372 + i * 24
        for k in range(c // 2):
            out.append(f'<circle cx="{x + 4}" cy="{470 - k * 3.2:.1f}" r="1.2" fill="{ACCENT if c == max(counts) else INK}"/>')
        text(x + 4, 482, f"{6 + i:02d}", 5.5, GREY, anchor="middle", spacing=0)

    # ---- RIGHT PAGE: the hand drawing over the terrain bands ------------------------
    terrain_bands(GUTTER + 20, W - 40, 150)
    hx, hy, hw, hh = GUTTER + 70, 70, 500, 370
    out.append(f'<rect x="{hx}" y="{hy}" width="{hw}" height="{hh}" fill="{BG}" opacity="0.55"/>')
    halftone(hx, hy, hw, hh, "NEW HAND DRAWING — ink on paper, scan at 600 dpi, background removed", 31, step=6, dark=0.35, frame=False)
    out.append(f'<rect x="{hx}" y="{hy}" width="{hw}" height="{hh}" fill="none" stroke="{ACCENT}" stroke-width="0.8" stroke-dasharray="4 3"/>')
    out.append(f'<rect x="{hx + 60}" y="{hy + hh / 2 - 24}" width="{hw - 120}" height="44" fill="{BG}"/>')
    text(hx + hw / 2, hy + hh / 2 - 6, "Draw: how the site's paths fold into the gallery.", 11, INK, SANS, "700", "middle", 0)
    text(hx + hw / 2, hy + hh / 2 + 12, "Existing walking routes  →  one continuous line  →  rooms + courtyards",
         7.5, GREY, anchor="middle", spacing=0.3)
    # callouts with arrows, like the reference's dashed red arrows
    for (x1, y1, x2, y2, lab) in ((hx + hw + 10, hy + 60, hx + hw - 40, hy + 100, "entry from the art museum side"),
                                  (hx + hw + 10, hy + 250, hx + hw - 60, hy + 230, "courtyard where people already pause")):
        out.append(f'<path d="M{x1},{y1} Q{(x1 + x2) / 2 + 20},{y1 - 20} {x2},{y2}" fill="none" stroke="{ACCENT}" stroke-width="0.9" stroke-dasharray="3 2"/>')
        out.append(f'<circle cx="{x2}" cy="{y2}" r="2.2" fill="{ACCENT}"/>')
        text(x1 + 4, y1 + 3, lab, 6.5, INK, spacing=0.2)

    # ---- timeline across the bottom of the spread ------------------------------------
    ty = H - 70
    text(40, ty - 26, "SITE HISTORY  (PLACEHOLDER YEARS)", 6.5, GREY, spacing=0.8)
    for k in range(int((W - 80) / 6)):
        out.append(f'<circle cx="{40 + k * 6}" cy="{ty}" r="0.9" fill="{GREY}"/>')
    events = ["18XX", "19XX", "19XX", "19XX", "20XX", "20XX", "NOW"]
    for i, ev in enumerate(events):
        x = 80 + i * ((W - 160) / (len(events) - 1))
        last = ev == "NOW"
        out.append(f'<circle cx="{x:.1f}" cy="{ty}" r="13" fill="{ACCENT if last else INK}"/>')
        text(x, ty + 3, ev, 6.5, BG, weight="700", anchor="middle", spacing=0.2)
        text(x, ty + 26, "[event]" if not last else "the gallery", 6, GREY, anchor="middle", spacing=0.2)

    out.append('</svg>')

    here = Path(__file__).parent
    svg = "\n".join(out)
    (here / "gs_listening.svg").write_text(svg)
    try:
        import cairosvg
        cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(here / "gs_listening.pdf"))
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(here / "gs_listening.png"), scale=2)
    except ImportError:
        print("cairosvg not installed: wrote gs_listening.svg only")
    print("done")


if __name__ == "__main__":
    main()
