"""Radial table of contents for the portfolio.

Edit PROJECTS below, then run:  python3 make_toc.py
Outputs toc.svg (editable text, opens in Illustrator / InDesign),
toc.pdf and toc.png (preview).
"""
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# DATA — replace placeholders with real projects.
# (title, year, hours, featured_page)  featured_page=None -> small grey entry
# Hours drive the length of each bar in the central burst.
# ---------------------------------------------------------------------------
FEATURED = {
    # title: (subtitle shown in the readable list, year, hours, page)
    "GS GALLERY":       ("Precast exhibition gallery · individual", 2024, 320, 3),
    "MOUNTAIN LIBRARY": ("Warehouse to public library · team", 2024, 400, 8),
    "THE LOOP":         ("Bike shelter, Great Plains trail · individual", 2023, 180, 12),
    "VIZZIT.HOMES":     ("Founder · phone video to Gaussian splat", 2025, 600, 15),
    "SKETCHBOOK":       ("Hand drawings · personal", 2025, 150, 17),
}

PLACEHOLDER_YEARS = [2021] * 4 + [2022] * 6 + [2023] * 7 + [2024] * 7 + [2025] * 6 + [2026] * 4
PLACEHOLDER_HOURS = [40, 90, 25, 60, 120, 35, 75, 50, 140, 30, 65, 110, 45, 85, 20,
                     130, 55, 95, 70, 40, 150, 60, 35, 100, 80, 45, 125, 30, 70, 90,
                     55, 115, 40, 65]


def build_projects():
    items = []
    for i, (yr, hrs) in enumerate(zip(PLACEHOLDER_YEARS, PLACEHOLDER_HOURS), start=1):
        items.append({"title": f"PLACEHOLDER PROJECT {i:02d}", "year": yr,
                      "hours": hrs, "page": None})
    for title, (sub, yr, hrs, page) in FEATURED.items():
        items.append({"title": title, "sub": sub, "year": yr, "hours": hrs, "page": page})
    # group by year; inside a year, spread featured projects among the grey ones
    items.sort(key=lambda p: (p["year"], sum(map(ord, p["title"])) % 7))
    return items


# ---------------------------------------------------------------------------
# LAYOUT — one landscape spread, 22 x 8.5 in (matches the current portfolio)
# ---------------------------------------------------------------------------
W, H = 1584, 612
CX, CY = 1090, 596            # centre of the fan (on the right-hand page)
A_START, A_END = 172, 8       # degrees, left -> right across the top
R_DOT_INNER = 50
R_BURST0, R_BURST_MAX = 62, 222
R_RING = 238                  # dotted ring between burst and text
R_TEXT = 252                  # where every title starts
YEAR_GAP = 3.5                # degrees of empty space between years

BG, FG, GREY, DIM, ACCENT = "#0b0b0b", "#ffffff", "#6e6e6e", "#3a3a3a", "#e8262b"
SANS = "Inter, 'Helvetica Neue', Arial, sans-serif"
MONO = "'IBM Plex Mono', 'DejaVu Sans Mono', 'Courier New', monospace"


def polar(r, deg):
    a = math.radians(deg)
    return CX + r * math.cos(a), CY - r * math.sin(a)


def radial_text(r, deg, text, size, fill, family, weight="400", spacing=0.6):
    """Text running outward from radius r; flipped on the left so it is never upside down."""
    x, y = polar(r, deg)
    if deg > 90:
        rot, anchor = 180 - deg, "end"
    else:
        rot, anchor = -deg, "start"
    return (f'<text x="{x:.2f}" y="{y:.2f}" transform="rotate({rot:.2f} {x:.2f} {y:.2f})" '
            f'font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'letter-spacing="{spacing}" text-anchor="{anchor}" dominant-baseline="middle">{text}</text>')


def main():
    projects = build_projects()
    years = sorted({p["year"] for p in projects})

    # featured projects get a double-width slot so their bigger type has room
    slots = [2 if p["page"] else 1 for p in projects]
    usable = (A_START - A_END) - YEAR_GAP * (len(years) - 1)
    step = usable / sum(slots)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="{BG}"/>']

    burst, ring, text, year_marks = [], [], [], []
    max_hours = max(p["hours"] for p in projects)
    angle = A_START
    prev_year = projects[0]["year"]
    year_start = angle
    for p, s in zip(projects, slots):
        if p["year"] != prev_year:
            year_marks.append((prev_year, year_start, angle))
            angle -= YEAR_GAP
            year_start = angle
            prev_year = p["year"]
        mid = angle - step * s / 2
        angle -= step * s

        featured = p["page"] is not None
        r1 = R_BURST0 + (R_BURST_MAX - R_BURST0) * p["hours"] / max_hours
        x0, y0 = polar(R_BURST0, mid)
        x1, y1 = polar(r1, mid)
        burst.append(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
                     f'stroke="{ACCENT if featured else FG}" stroke-width="{2.4 if featured else 0.9}" '
                     f'stroke-linecap="round" opacity="{1 if featured else 0.75}"/>')
        # fine texture lines beside each bar, like the reference burst
        for off, k in ((-step * 0.28, 0.82), (step * 0.28, 0.64)):
            xa, ya = polar(R_BURST0, mid + off)
            xb, yb = polar(R_BURST0 + (r1 - R_BURST0) * k, mid + off)
            burst.append(f'<line x1="{xa:.2f}" y1="{ya:.2f}" x2="{xb:.2f}" y2="{yb:.2f}" '
                         f'stroke="{GREY}" stroke-width="0.4"/>')

        if featured:
            text.append(radial_text(R_TEXT, mid, f'{p["title"]}', 17, FG, SANS, "700", 1.2))
            # page number further out, in accent
            text.append(radial_text(R_TEXT + 14 + len(p["title"]) * 12.6, mid,
                                    f'{p["page"]:02d}', 17, ACCENT, MONO, "700", 0))
        else:
            text.append(radial_text(R_TEXT, mid, p["title"], 8.4, GREY, MONO, "400", 0.5))
    year_marks.append((prev_year, year_start, angle))

    # dotted rings
    for r, n, rad, fill in ((R_DOT_INNER, 90, 0.8, GREY), (R_RING, 260, 1.0, GREY)):
        for i in range(n):
            x, y = polar(r, A_START + 4 - (A_START - A_END + 8) * i / (n - 1))
            ring.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{rad}" fill="{fill}"/>')

    # year labels on the ring + a bright dot marking each year's start
    for yr, a0, a1 in year_marks:
        xs, ys = polar(R_RING, a0 + 1.2)
        ring.append(f'<circle cx="{xs:.2f}" cy="{ys:.2f}" r="2.6" fill="{FG}"/>')
        text.append(radial_text(R_RING - 26, (a0 + a1) / 2, str(yr), 8.5, FG, MONO, "700", 1))

    out += ['<g id="burst">', *burst, '</g>', '<g id="rings">', *ring, '</g>',
            '<g id="titles">', *text, '</g>']

    # ---- left page: readable contents list + key -------------------------
    L = []
    L.append(f'<text x="48" y="64" font-family="{MONO}" font-size="9" fill="{GREY}" letter-spacing="2">JEREMI LUKOS — M.ARCH PORTFOLIO</text>')
    L.append(f'<text x="48" y="118" font-family="{SANS}" font-size="44" font-weight="700" fill="{FG}" letter-spacing="1">CONTENTS</text>')
    L.append(f'<text x="48" y="146" font-family="{MONO}" font-size="9" fill="{GREY}" letter-spacing="1">EVERY PROJECT, 2021–2026. FIVE ARE IN THIS BOOK.</text>')
    y = 200
    for title, (sub, yr, hrs, page) in sorted(FEATURED.items(), key=lambda kv: kv[1][3]):
        L.append(f'<text x="48" y="{y}" font-family="{MONO}" font-size="18" font-weight="700" fill="{ACCENT}">{page:02d}</text>')
        L.append(f'<text x="96" y="{y}" font-family="{SANS}" font-size="18" font-weight="700" fill="{FG}" letter-spacing="1">{title}</text>')
        L.append(f'<text x="96" y="{y + 17}" font-family="{MONO}" font-size="8" fill="{GREY}" letter-spacing="0.5">{sub.upper()} · {yr}</text>')
        y += 52
    ky = 488
    L.append(f'<line x1="48" y1="{ky - 18}" x2="400" y2="{ky - 18}" stroke="{DIM}" stroke-width="0.6"/>')
    L.append(f'<text x="48" y="{ky}" font-family="{MONO}" font-size="7.5" fill="{GREY}" letter-spacing="0.6">READING THE CHART</text>')
    keys = [
        (FG, "WHITE TITLE — project in this portfolio"),
        (GREY, "GREY TITLE — every other project, studio, job, competition"),
        (ACCENT, "BAR LENGTH — hours invested in the project"),
        (FG, "SECTORS — one per year, oldest on the left"),
    ]
    for i, (c, label) in enumerate(keys):
        yy = ky + 18 + i * 15
        L.append(f'<circle cx="52" cy="{yy - 3}" r="2.6" fill="{c}"/>')
        L.append(f'<text x="64" y="{yy}" font-family="{MONO}" font-size="7.5" fill="{GREY}" letter-spacing="0.4">{label}</text>')
    L.append(f'<text x="{W - 48}" y="{H - 24}" font-family="{MONO}" font-size="8" fill="{DIM}" text-anchor="end">02</text>')
    out += ['<g id="contents-list">', *L, '</g>', '</svg>']

    here = Path(__file__).parent
    svg = "\n".join(out)
    (here / "toc.svg").write_text(svg)
    try:
        import cairosvg
        cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(here / "toc.pdf"))
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(here / "toc.png"), scale=2)
    except ImportError:
        print("cairosvg not installed: wrote toc.svg only")
    print("done")


if __name__ == "__main__":
    main()
