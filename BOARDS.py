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
U1, G1 = nums(u), nums(gap)
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

# ---------- layout: every board 6" wide, every gap 3", measured along each ring ----------
# boards sit on a fixed grid that starts at the middle of the window, so the same board
# row lands at the same distance from the window on every ring (rows line up ring to ring).
# the window removes whole boards; boards that don't fit at the ends of a ring are dropped.
rows = []
for k, c in enumerate(crvs):
    L = c.GetLength()
    wins = []
    for UU, GG in ((U1, G1), (U2, G2)):
        if not UU: continue
        uu, yy = at(UU, k), at(GG, k)
        if yy > 1e-9: wins.append((uu * (1 - yy) * L, (uu + (1 - uu) * yy) * L))
    uu, yy = at(U1, k, 0.5), at(G1, k)
    s0 = (uu * (1 - yy) + uu + (1 - uu) * yy) * 0.5 * L
    d = {}
    for j in range(-int(s0 / P) - 2, int((L - s0) / P) + 2):
        sc = s0 + P / 2.0 + j * P
        lo, hi = sc - W / 2.0, sc + W / 2.0
        if lo < -tol or hi > L + tol: continue
        if any(lo < b_ and hi > a_ for a_, b_ in wins): continue
        d[j] = sc
    rows.append(d)

def frame(c, s):
    res = c.LengthParameter(s)
    tt = res[1] if isinstance(res, tuple) else res
    p = c.PointAt(tt)
    x = c.TangentAt(tt)
    ok = c.TryGetPlane()
    z = ok[1].ZAxis if isinstance(ok, tuple) and ok[0] else rg.Vector3d.CrossProduct(x, c.CurvatureAt(tt))
    z.Unitize()
    return p, x, z

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
h, tk = W / 2.0, T / 2.0
for k in range(len(crvs) - 1):
    for j in sorted(set(F[k]) & set(F[k + 1])):
        (pa, xa, za), (pb, xb, zb) = F[k][j], F[k + 1][j]
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

# board centre points, one branch per ring (feeds the SUBFRAME script's 'boards' input)
pts = th.list_to_tree([[F[k][j][0] for j in sorted(F[k])] for k in range(len(crvs))])
print("rings: %d | boards per ring: %d to %d | planks: %d" % (
    len(crvs), min(len(r) for r in rows) if rows else 0, max(len(r) for r in rows) if rows else 0, len(a)))
