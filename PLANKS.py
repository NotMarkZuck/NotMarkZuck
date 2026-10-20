import Rhino
import Rhino.Geometry as rg
from System.Collections.Generic import List
import rhinoscriptsyntax as rs

tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
P = list(x)
def num(v): return float(v) if not hasattr(v, '__iter__') else float(list(v)[0])
h, t = num(y) / 2.0, num(z) / 2.0

try: cutters = [rs.coercebrep(c_) for c_ in (cut if hasattr(cut, '__iter__') else [cut]) if c_ is not None]
except NameError: cutters = []
cut_boxes = [(c_, c_.GetBoundingBox(True)) for c_ in cutters]
def inside(pt):
    return any(bb.Contains(pt) and c_.IsPointInside(pt, tol, False) for c_, bb in cut_boxes)

def v(p): return (p.X, p.Y, p.Z)
def add(*vs): return tuple(sum(c) for c in zip(*vs))
def mul(a, s): return tuple(c * s for c in a)
def sub(a, b): return tuple(p - q for p, q in zip(a, b))
def dot(a, b): return sum(p * q for p, q in zip(a, b))
def unit(a):
    l = dot(a, a) ** 0.5
    return mul(a, 1.0 / l) if l > 1e-12 else None
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def hit(q, d, o, n):
    s = dot(sub(o, q), n) / dot(d, n)
    return rg.Point3d(*add(q, mul(d, s)))

a = []
for pa, pb in zip(P[:-1], P[1:]):
    oa, ob = v(pa.Origin), v(pb.Origin)
    xp = unit(sub(ob, oa))
    if xp is None: continue
    ta, tb = v(pa.XAxis), v(pb.XAxis)
    if dot(ta, tb) < 0: tb = mul(tb, -1)
    s = add(ta, tb)
    yp = unit(sub(s, mul(xp, dot(s, xp))))
    n = cross(xp, yp)
    A, B = {}, {}
    for sy in (-1, 1):
        for sz in (-1, 1):
            q = add(oa, mul(yp, sy * h), mul(n, sz * t))
            A[sy, sz] = hit(q, xp, oa, v(pa.ZAxis))
            B[sy, sz] = hit(q, xp, ob, v(pb.ZAxis))
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