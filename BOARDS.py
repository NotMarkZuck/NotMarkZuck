import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
from System.Collections.Generic import List
import ghpythonlib.treehelpers as th

tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
def many(v):
    try: return list(v) if hasattr(v, '__iter__') else ([] if v is None else [v])
    except NameError: return []
def num(v, d):
    try: return float(many(v)[0])
    except: return d
def nums(v):
    try: return [float(x) for x in many(v)]
    except NameError: return []

crvs = [rs.coercecurve(c) for c in many(crv) if c is not None]
try: U1, G1 = nums(u), nums(gap)
except NameError: U1, G1 = [], []
try: LOC, OPN = nums(wloc), nums(wopen)   # gene pools: window location (0-1 along the arc) and opening (inches)
except NameError: LOC, OPN = [], []
try: U2, G2 = nums(u2), nums(gap2)
except NameError: U2, G2 = [], []
W = num(w, 0.5)            # board width (ft)  6"
GAP = num(g, 0.25)         # gap between boards (ft)  3"
T = num(t, 0.5 / 12.0)     # board thickness (ft)
P = W + GAP                # one board + one gap

try: cutters = [rs.coercebrep(c_) for c_ in many(cut) if c_ is not None]
except NameError: cutters = []
cut_boxes = [(c_, c_.GetBoundingBox(True)) for c_ in cutters if c_]
def inside(pt):
    return any(bb.Contains(pt) and c_.IsPointInside(pt, tol, False) for c_, bb in cut_boxes)

def at(lst, k, d=0.0):
    return lst[min(k, len(lst) - 1)] if lst else d

def spread(vals, n):
    # gene values spaced evenly from the first ring to the last, smooth curve in between
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
LOCk = spread(LOC, len(crvs))
OPNk = spread(OPN, len(crvs)) if OPN else [0.0] * len(LOCk)

# ---------- layout: every board 6" wide, every gap 3", measured along each ring ----------
# rows are counted outwards from the two edges of the window: row -1 is always the board just
# below the window, row 0 the board just above it, and so on. so the boards framing the window
# run as continuous lines from ring to ring, and any difference in board count between rings
# shows up only at the far ends of the arcs. where there is no window the two edge rows simply
# meet with a normal 3" gap.
rows = []
for k, c in enumerate(crvs):
    L = c.GetLength()
    if LOCk:
        # window from the gene pools: centre at LOC along the arc, OPN inches clear between the framing boards
        sc_ = min(max(LOCk[k], 0.0), 1.0) * L
        half = max(OPNk[k] / 12.0 - GAP, 0.0) / 2.0
        e1, e2 = max(sc_ - half, 0.0), min(sc_ + half, L)
    else:
        uu, yy = at(U1, k, 0.5), max(at(G1, k), 0.0)
        e1, e2 = uu * (1 - yy) * L, (uu + (1 - uu) * yy) * L
    others = []
    if U2:
        u2_, y2_ = at(U2, k), max(at(G2, k), 0.0)
        if y2_ > 1e-9: others.append((u2_ * (1 - y2_) * L, (u2_ + (1 - u2_) * y2_) * L))
    d = {}
    # above the window: rows 0, 1, 2 ...
    sc, j = e2 + GAP / 2.0 + W / 2.0, 0
    while sc + W / 2.0 <= L + tol:
        for a_, b_ in others:   # hop over a second window if there is one
            if sc - W / 2.0 < b_ and sc + W / 2.0 > a_: sc = b_ + GAP / 2.0 + W / 2.0
        if sc + W / 2.0 > L + tol: break
        d[j] = sc
        sc += P; j += 1
    # below the window: rows -1, -2, -3 ...
    sc, j = e1 - GAP / 2.0 - W / 2.0, -1
    while sc - W / 2.0 >= -tol:
        for a_, b_ in others:
            if sc - W / 2.0 < b_ and sc + W / 2.0 > a_: sc = a_ - GAP / 2.0 - W / 2.0
        if sc - W / 2.0 < -tol: break
        d[j] = sc
        sc -= P; j -= 1
    rows.append(d)

def frame(c, s):
    res = c.LengthParameter(s)
    tt = res[1] if isinstance(res, tuple) else res
    p = c.PointAt(tt)
    x = c.TangentAt(tt)
    ok = c.TryGetPlane()
    z = ok[1].ZAxis if isinstance(ok, tuple) and ok[0] else rg.Vector3d.CrossProduct(x, c.CurvatureAt(tt))
    z.Unitize()
    kv = c.CurvatureAt(tt)          # points towards the centre of the ring
    return p, x, z, kv

def V(p): return (p.X, p.Y, p.Z)
def add(*vs): return tuple(sum(c_) for c_ in zip(*vs))
def mul(a_, s_): return tuple(c_ * s_ for c_ in a_)
def sub(a_, b_): return tuple(p_ - q_ for p_, q_ in zip(a_, b_))
def dot(a_, b_): return sum(p_ * q_ for p_, q_ in zip(a_, b_))
def unit(a_):
    l_ = dot(a_, a_) ** 0.5
    return mul(a_, 1.0 / l_) if l_ > 1e-12 else None
def cross(a_, b_): return (a_[1]*b_[2]-a_[2]*b_[1], a_[2]*b_[0]-a_[0]*b_[2], a_[0]*b_[1]-a_[1]*b_[0])
def hit(q, dd, o, n):
    s_ = dot(sub(o, q), n) / dot(dd, n)
    return rg.Point3d(*add(q, mul(dd, s_)))

F = [{j: frame(crvs[k], s) for j, s in rows[k].items()} for k in range(len(crvs))]

# ---------- planks: flat, mitred to each ring, one per row per bay ----------
a = []
bays = []                           # per bay: the planks in order along the arc (for the straps)
h, tk = W / 2.0, T / 2.0
for k in range(len(crvs) - 1):
    bays.append([])
    for j in sorted(set(F[k]) & set(F[k + 1])):
        (pa, xa, za, ka), (pb, xb, zb, kb) = F[k][j], F[k + 1][j]
        oa, ob = V(pa), V(pb)
        xp = unit(sub(ob, oa))
        if xp is None: continue
        ta, tb = V(xa), V(xb)
        if dot(ta, tb) < 0: tb = mul(tb, -1)
        s_ = add(ta, tb)
        yp = unit(sub(s_, mul(xp, dot(s_, xp))))
        if yp is None: continue
        n = cross(xp, yp)
        A, B = {}, {}
        for sy in (-1, 1):
            for sz in (-1, 1):
                q = add(oa, mul(yp, sy * h), mul(n, sz * tk))
                A[sy, sz] = hit(q, xp, oa, V(za))
                B[sy, sz] = hit(q, xp, ob, V(zb))
        if cut_boxes and all(inside(c_) for c_ in list(A.values()) + list(B.values())): continue
        n_out = n if dot(n, add(V(ka), V(kb))) < 0 else mul(n, -1)   # face of the board towards the skin
        zb_ = V(zb) if dot(V(za), V(zb)) > 0 else mul(V(zb), -1)
        bays[-1].append((mul(add(oa, ob), 0.5), xp, yp, n_out, add(V(za), zb_)))
        quads = [(A[-1,1], B[-1,1], B[1,1], A[1,1]), (A[-1,-1], A[1,-1], B[1,-1], B[-1,-1]),
                 (A[-1,-1], B[-1,-1], B[-1,1], A[-1,1]), (A[1,-1], A[1,1], B[1,1], B[1,-1]),
                 (A[-1,-1], A[-1,1], A[1,1], A[1,-1]), (B[-1,-1], B[1,-1], B[1,1], B[-1,1])]
        faces = List[rg.Brep]()
        for qd in quads:
            f = rg.Brep.CreateFromCornerPoints(qd[0], qd[1], qd[2], qd[3], tol)
            if f: faces.Add(f)
        joined = rg.Brep.JoinBreps(faces, tol)
        if joined:
            b = joined[0]
            if b.SolidOrientation == rg.BrepSolidOrientation.Inward: b.Flip()
            a.append(b)

# ---------- straps: one metal strap across the middle of each bay, on the outside face of the boards ----------
# it runs flat on each board and straight across each 3" gap, so it is a faceted arc that sits tight
# on the boards. it starts at the edge of the first board, ends at the edge of the last, and breaks at windows.
try: SW = float(many(sw)[0]) / 12.0      # strap width (inches)
except: SW = 2.0 / 12.0
try: STH = float(many(sth)[0]) / 12.0    # strap thickness (inches)
except: STH = 0.25 / 12.0

def strap(run, O, N):
    # every corner of the strap sits exactly where a board's outside edge crosses one of two
    # flat planes (the strap's two sides), so the strap is a straight, flat band across the boards
    if len(run) < 2: return None
    def on_plane(q, x, off):
        o_ = add(O, mul(N, off))
        dn = dot(x, N)
        return add(q, mul(x, dot(sub(o_, q), N) / dn)) if abs(dn) > 1e-9 else q
    P_ = [rg.Point3d(*on_plane(q, x, -SW / 2.0)) for q, x, n in run]          # inner, one side
    Q_ = [rg.Point3d(*on_plane(q, x, SW / 2.0)) for q, x, n in run]           # inner, other side
    Po = [rg.Point3d(*add(on_plane(q, x, -SW / 2.0), mul(n, STH))) for q, x, n in run]
    Qo = [rg.Point3d(*add(on_plane(q, x, SW / 2.0), mul(n, STH))) for q, x, n in run]
    quads = [(P_[0], Po[0], Qo[0], Q_[0]), (P_[-1], Q_[-1], Qo[-1], Po[-1])]
    for m in range(len(run) - 1):
        quads += [(P_[m], Q_[m], Q_[m + 1], P_[m + 1]), (Po[m], Po[m + 1], Qo[m + 1], Qo[m]),
                  (P_[m], P_[m + 1], Po[m + 1], Po[m]), (Q_[m], Qo[m], Qo[m + 1], Q_[m + 1])]
    faces = List[rg.Brep]()
    for qd in quads:
        f = rg.Brep.CreateFromCornerPoints(qd[0], qd[1], qd[2], qd[3], tol)
        if f: faces.Add(f)
    joined = rg.Brep.JoinBreps(faces, tol)
    if not joined: return None
    b = joined[0]
    if b.SolidOrientation == rg.BrepSolidOrientation.Inward: b.Flip()
    return b

straps = []
if SW > 0 and STH > 0:
    for bay in bays:
        if not bay: continue
        # one flat plane halfway between the two rings: the strap's centre line lies in it
        O = mul(add(*[m_ for m_, _, _, _, _ in bay]), 1.0 / len(bay))
        N = unit(add(*[z_ for _, _, _, _, z_ in bay]))
        if N is None: continue
        run = []
        for mid, xp, yp, n, z_ in bay:
            face = add(mid, mul(n, tk))
            e_lo, e_hi = add(face, mul(yp, -h)), add(face, mul(yp, h))
            if run:
                dd = sub(e_lo, run[-1][0])
                if dot(dd, dd) ** 0.5 > GAP * 1.5 + 1e-6:     # bigger than a normal gap = window or missing boards
                    b = strap(run, O, N)
                    if b: straps.append(b)
                    run = []
            run += [(e_lo, xp, n), (e_hi, xp, n)]
        b = strap(run, O, N)
        if b: straps.append(b)

# board centre points, one branch per ring (feeds the SUBFRAME script's 'boards' input)
pts = th.list_to_tree([[F[k][j][0] for j in sorted(F[k])] for k in range(len(crvs))])
print("rings: %d | boards per ring: %d to %d | planks: %d | straps: %d" % (
    len(crvs), min(len(r) for r in rows) if rows else 0, max(len(r) for r in rows) if rows else 0, len(a), len(straps)))
