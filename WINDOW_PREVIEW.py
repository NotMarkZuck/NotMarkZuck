import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs

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

LOCk, OPNk = spread(LOC, len(crvs)), spread(OPN, len(crvs))
lower, upper, centre = [], [], []
for k, c in enumerate(crvs):
    L = c.GetLength()
    sc = min(max(LOCk[k], 0.0), 1.0) * L
    centre.append(at_len(c, sc))
    op = max(OPNk[k] / 12.0, 0.0) if OPNk else 0.0
    if op <= GAP + 1e-6: continue                    # no window on this ring
    lower.append(at_len(c, sc - op / 2.0))           # faces of the two boards framing the window
    upper.append(at_len(c, sc + op / 2.0))

outline = rg.PolylineCurve(lower + upper[::-1] + lower[:1]) if len(lower) > 1 else None
centreline = rg.PolylineCurve(centre) if len(centre) > 1 else None
print("rings with a window: %d of %d" % (len(lower), len(crvs)))
