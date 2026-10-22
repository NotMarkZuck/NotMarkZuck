import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
from System.Collections.Generic import List

tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance

# quick outline of the window from the two gene pools - same maths as the BOARDS script,
# but only draws lines, so it updates instantly while you drag the genes
def many(v):
    try: return list(v) if hasattr(v, '__iter__') else ([] if v is None else [v])
    except NameError: return []
def nums(v):
    try: return [float(x) for x in many(v)]
    except NameError: return []

crvs = [rs.coercecurve(c) for c in many(crv) if c is not None]
LOC, OPN = nums(wloc), nums(wopen)
try: GAP = float(many(g)[0])
except: GAP = 0.25
try: DIN = float(many(din)[0])      # how far the window cutter reaches in towards the centre (ft)
except: DIN = 1.0
try: DOUT = float(many(dout)[0])    # how far the window cutter reaches out past the boards (ft)
except: DOUT = 3.0

def spread(vals, n):
    m = len(vals)
    if m == 0: return []
    if m == 1: return [vals[0]] * n
    out_ = []
    for k in range(n):
        x_ = k * (m - 1) / float(max(n - 1, 1))
        i = min(int(x_), m - 2); f = x_ - i
        p0, p1, p2, p3 = vals[max(i - 1, 0)], vals[i], vals[i + 1], vals[min(i + 2, m - 1)]
        out_.append(0.5 * (2 * p1 + (p2 - p0) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
                           + (3 * p1 - p0 - 3 * p2 + p3) * f ** 3))
    return out_

def at_len(c, s):
    res = c.LengthParameter(min(max(s, 0.0), c.GetLength()))
    return c.PointAt(res[1] if isinstance(res, tuple) else res)

def radial(c, s):
    # the point on the ring plus the points DIN inside and DOUT outside it, straight out from the ring's centre
    res = c.LengthParameter(min(max(s, 0.0), c.GetLength()))
    tt = res[1] if isinstance(res, tuple) else res
    p = c.PointAt(tt)
    k = c.CurvatureAt(tt)
    out_ = -k
    out_.Unitize()
    return p - out_ * DIN, p + out_ * DOUT

LOCk, OPNk = spread(LOC, len(crvs)), spread(OPN, len(crvs))
lower, upper, centre = [], [], []
runs, cur = [], []                                   # rings with a window, grouped into unbroken stretches
for k, c in enumerate(crvs):
    L = c.GetLength()
    sc = min(max(LOCk[k], 0.0), 1.0) * L
    centre.append(at_len(c, sc))
    op = max(OPNk[k] / 12.0, 0.0) if OPNk else 0.0
    if op <= GAP + 1e-6:                             # no window on this ring
        if cur: runs.append(cur); cur = []
        continue
    lower.append(at_len(c, sc - op / 2.0))           # faces of the two boards framing the window
    upper.append(at_len(c, sc + op / 2.0))
    (li, lo_), (ui, uo) = radial(c, sc - op / 2.0), radial(c, sc + op / 2.0)
    cur.append((li, lo_, uo, ui))
if cur: runs.append(cur)

outline = rg.PolylineCurve(lower + upper[::-1] + lower[:1]) if len(lower) > 1 else None
centreline = rg.PolylineCurve(centre) if len(centre) > 1 else None

# ---------- window cutter: a closed solid through the window, from inside the boards out past the skin ----------
def solid(run):
    if len(run) < 2: return None
    quads = [run[0], run[-1][::-1]]
    for m in range(len(run) - 1):
        a_, b_ = run[m], run[m + 1]
        for i in range(4):
            j = (i + 1) % 4
            quads.append((a_[i], b_[i], b_[j], a_[j]))
    faces = List[rg.Brep]()
    for qd in quads:
        f = rg.Brep.CreateFromCornerPoints(qd[0], qd[1], qd[2], qd[3], tol)
        if f: faces.Add(f)
    joined = rg.Brep.JoinBreps(faces, tol)
    if not joined: return None
    b = joined[0]
    if b.SolidOrientation == rg.BrepSolidOrientation.Inward: b.Flip()
    return b
cutter = [b for b in (solid(r) for r in runs) if b]
print("rings with a window: %d of %d | cutters: %d (closed: %s)" % (
    len(lower), len(crvs), len(cutter), [b.IsSolid for b in cutter]))
