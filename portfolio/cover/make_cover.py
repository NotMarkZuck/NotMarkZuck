"""Portfolio cover (placeholder version).

The point field is a stand-in for a Vizzit Gaussian-splat scan of a physical
model. When the real scan exists, delete the <g id="placeholder-splat"> group in
Illustrator and drop the scan image in its place.

Run:  python3 make_cover.py   ->  cover.svg / cover.pdf / cover.png
"""
import math
import random
from pathlib import Path

W, H = 792, 612                     # 11 x 8.5 in, landscape, same as the old cover
BG, INK, GREY, ACCENT = "#f1f0ed", "#0b0b0b", "#8a8a8a", "#e8262b"
SANS = "Inter, 'Helvetica Neue', Arial, sans-serif"
MONO = "'IBM Plex Mono', 'DejaVu Sans Mono', 'Courier New', monospace"

# ----------------------------------------------------------------------------
# Text — swap SCHOOL per application (MIT asks for name + program on the file)
# ----------------------------------------------------------------------------
NAME_BIG = "LUKOS"
SCHOOL = "[SCHOOL NAME]"
SCAN_STATS = [                       # placeholder numbers: replace with the real scan's
    "// scan.vizzit  — physical model, 1:200",
    "source    phone video, 00:42",
    "points    1,204,330 gaussians",
    "scale     1:1 measured",
    "status    PLACEHOLDER",
]


def splat_field(rng):
    """Concentric arcs of points sweeping out from the name, densest near the core."""
    cx, cy = 150, H / 2
    dots = []
    for i in range(70):
        t = i / 69
        r = 70 + 300 * t ** 0.9
        squash = 1.0 - 0.25 * t                      # arcs flatten as they grow
        n = int(260 * (1 - t) + 60)
        for _ in range(n):
            a = rng.uniform(-88, 88)
            a += rng.gauss(0, 2.5)
            rad = math.radians(a)
            jitter = rng.gauss(0, 3 + 6 * t)
            x = cx + (r + jitter) * math.cos(rad)
            y = cy + (r + jitter) * math.sin(rad) * squash
            if not (0 < x < W - 230 and 30 < y < H - 30):
                continue
            # colour: ink core, accent band, grey haze
            band = abs(a) / 88
            if t < 0.35:
                col = INK
            elif t < 0.6 and band < 0.75 and rng.random() < 0.55:
                col = ACCENT
            else:
                col = GREY
            size = max(0.25, rng.gauss(0.9 - 0.5 * t, 0.25))
            alpha = max(0.08, min(1, rng.gauss(0.85 - 0.6 * t, 0.15)))
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.2f}" fill="{col}" '
                        f'opacity="{alpha:.2f}"/>')
        # a few long "strands" per arc, like the fibres in the reference
        if i % 3 == 0:
            a0, a1 = rng.uniform(-80, -20), rng.uniform(20, 80)
            steps = 40
            pts = []
            for k in range(steps + 1):
                aa = math.radians(a0 + (a1 - a0) * k / steps)
                pts.append(f"{cx + r * math.cos(aa):.1f},{cy + r * math.sin(aa) * squash:.1f}")
            dots.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{GREY}" '
                        f'stroke-width="0.25" opacity="0.5"/>')
    return dots


def main():
    rng = random.Random(7)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="{BG}"/>']

    out += ['<g id="placeholder-splat">', *splat_field(rng), '</g>']

    # Huge vertical surname down the left edge (reads bottom-to-top)
    out.append(f'<text id="surname" transform="translate(146 {H - 34}) rotate(-90)" '
               f'font-family="{SANS}" font-size="168" font-weight="700" fill="{INK}" '
               f'letter-spacing="-2">{NAME_BIG}</text>')

    # Right column
    x = W - 200
    out.append(f'<g id="right-column" font-family="{MONO}">')
    lines = [("JEREMI LUKOS", INK, 10, "700"), ("", INK, 10, "400"),
             ("LISTENING TO PLACES,", INK, 10, "400"), ("ONE POINT AT A TIME.", ACCENT, 10, "400")]
    y = 60
    for txt, col, size, weight in lines:
        if txt:
            out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{col}" letter-spacing="1">{txt}</text>')
        y += 15
    out.append(f'<line x1="{x}" y1="{y + 4}" x2="{x + 22}" y2="{y + 4}" stroke="{ACCENT}" stroke-width="1"/>')

    y = 250
    for txt in ("PORTFOLIO", "M.ARCH APPLICATION 2027", SCHOOL):
        out.append(f'<text x="{x}" y="{y}" font-size="8.5" fill="{ACCENT if txt == SCHOOL else INK}" letter-spacing="1">{txt}</text>')
        y += 14

    y = 430
    for txt in ("ARCHITECTURE", "ECONOMICS", "MAKING", "VIZZIT.HOMES"):
        out.append(f'<polygon points="{x},{y - 7} {x + 5},{y - 3.5} {x},{y}" fill="{ACCENT}"/>')
        out.append(f'<text x="{x + 10}" y="{y}" font-size="8.5" fill="{INK}" letter-spacing="1">{txt}</text>')
        y += 14
    out.append(f'<line x1="{x}" y1="{y + 2}" x2="{x + 22}" y2="{y + 2}" stroke="{ACCENT}" stroke-width="1"/>')

    # scan stats block, bottom right, like the code block in the reference
    y = H - 100
    for i, txt in enumerate(SCAN_STATS, start=1):
        out.append(f'<text x="{x - 16}" y="{y}" font-size="6" fill="{ACCENT}">{i:02d}</text>')
        out.append(f'<text x="{x}" y="{y}" font-size="6" fill="{GREY}" xml:space="preserve">{txt}</text>')
        y += 10
    out.append('</g>')
    out.append('</svg>')

    here = Path(__file__).parent
    svg = "\n".join(out)
    (here / "cover.svg").write_text(svg)
    try:
        import cairosvg
        cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(here / "cover.pdf"))
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(here / "cover.png"), scale=2)
    except ImportError:
        print("cairosvg not installed: wrote cover.svg only")
    print("done")


if __name__ == "__main__":
    main()
