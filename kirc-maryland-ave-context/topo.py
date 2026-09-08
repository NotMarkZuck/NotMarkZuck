#!/usr/bin/env python3
"""Topo extraction helpers: contours, chains, label association."""
import math, re, collections
import ezdxf

EXST = "dxf/CAMPUS_KIRC_CAD_EXST_CONDITIONS_RVT_IMPORT.dxf"
KIRC = "dxf/CAMPUS_KIRC_CAD_BGND_RVT_IMPORT.dxf"

# ---------- generic geometry ----------

def arc_pts(e, step=0.15):
    c = e.dxf.center; r = e.dxf.radius
    a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
    if a1 <= a0:
        a1 += 2 * math.pi
    n = max(2, int((a1 - a0) / step) + 1)
    return [(c.x + r * math.cos(a0 + (a1 - a0) * i / n),
             c.y + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def entity_polyline(e):
    """Return list of (x,y) for a linear entity, else None."""
    t = e.dxftype()
    if t == "LINE":
        return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    if t == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        if e.closed and len(pts) > 2:
            pts = pts + [pts[0]]
        return pts
    if t == "POLYLINE":
        pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if e.is_closed and len(pts) > 2:
            pts = pts + [pts[0]]
        return pts
    if t == "ARC":
        return arc_pts(e)
    return None


def clean_text(t):
    return re.sub(r"\\[A-Za-z][^;]*;|[{}]", " ", str(t)).strip()


def text_of(e):
    try:
        return clean_text(e.dxf.text if e.dxftype() == "TEXT" else e.text)
    except Exception:
        return ""


def pos_of(e):
    for a in ("insert", "location", "center"):
        if e.dxf.hasattr(a):
            p = e.dxf.get(a)
            return (p.x, p.y)
    return None


# ---------- existing-conditions 3D contours ----------

def exst_contours(doc, layers=("C-EG-1-E", "C-EG-5-E")):
    """3D contour polylines: [(elev, [(x,y),...]), ...]"""
    out = []
    for e in doc.modelspace():
        lay = e.dxf.layer.split("$")[-1]
        if lay not in layers:
            continue
        if e.dxftype() != "LWPOLYLINE":
            continue
        z = float(e.dxf.elevation or 0.0)
        if z <= 0:
            continue
        pts = entity_polyline(e)
        if pts and len(pts) >= 2:
            out.append((z, pts))
    return out


# ---------- chain building (for 2D contours needing labels) ----------

def build_chains(polys, tol=0.05):
    """Join 2D polylines end-to-end into chains."""
    key = lambda p: (round(p[0] / tol), round(p[1] / tol))
    ends = collections.defaultdict(list)   # node -> [(idx, which_end)]
    for i, p in enumerate(polys):
        ends[key(p[0])].append((i, 0))
        ends[key(p[-1])].append((i, 1))

    used = [False] * len(polys)
    chains = []
    for i in range(len(polys)):
        if used[i]:
            continue
        used[i] = True
        chain = list(polys[i])
        # extend forward then backward
        for direction in (1, 0):
            while True:
                tip = chain[-1] if direction else chain[0]
                cand = [(j, w) for (j, w) in ends[key(tip)] if not used[j]]
                if len(cand) != 1:
                    break
                j, w = cand[0]
                used[j] = True
                seg = list(polys[j])
                if w == 1:
                    seg.reverse()
                seg = seg[1:]
                if direction:
                    chain.extend(seg)
                else:
                    chain = list(reversed(seg)) + chain
        chains.append(chain)
    return chains


def label_chains(chains, labels, max_dist=40.0):
    """Assign each chain the elevation of the nearest numeric label.
    labels: [(elev, x, y), ...]  Returns [(elev, chain), ...]"""
    out = []
    for ch in chains:
        # sample the chain sparsely for distance tests
        samp = ch[:: max(1, len(ch) // 40)] + [ch[0], ch[-1]]
        best, bestd = None, 1e18
        for (ev, lx, ly) in labels:
            d = min((lx - x) ** 2 + (ly - y) ** 2 for (x, y) in samp)
            if d < bestd:
                bestd, best = d, ev
        if best is not None and bestd <= max_dist ** 2:
            out.append((best, ch))
    return out


def numeric_labels(doc, layer_sub, lo=600, hi=750):
    """Whole-number contour labels: [(elev,x,y)]"""
    out = []
    for e in doc.modelspace():
        if e.dxftype() not in ("TEXT", "MTEXT"):
            continue
        if layer_sub not in e.dxf.layer:
            continue
        t = text_of(e)
        m = re.fullmatch(r"(\d{3}(?:\.\d+)?)", t)
        if not m:
            continue
        v = float(m.group(1))
        if not (lo <= v <= hi):
            continue
        p = pos_of(e)
        if p:
            out.append((v, p[0], p[1]))
    return out


def spot_elevations(doc, layer_sub="TOPO-SPOT", lo=600, hi=750):
    """Spot elevations incl. TW/BW/TC/BC prefixes -> [(elev,x,y,kind)]"""
    out = []
    pat = re.compile(r"\b(TW|BW|TC|BC|TS|BS|TR|FL|RIM|INV|FFE|G)?\s*(\d{3}\.\d+)")
    for e in doc.modelspace():
        if e.dxftype() not in ("TEXT", "MTEXT"):
            continue
        if layer_sub not in e.dxf.layer:
            continue
        t = text_of(e)
        p = pos_of(e)
        if not p:
            continue
        for m in pat.finditer(t):
            v = float(m.group(2))
            if lo <= v <= hi:
                out.append((v, p[0], p[1], m.group(1) or "SPOT"))
    return out
