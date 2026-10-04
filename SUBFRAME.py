import math
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
from System.Collections.Generic import List

STRETCH = True
ARM_W = 1.5 / 12.0
ARM_D = 3.5 / 12.0

tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
def one(v): return v if not hasattr(v, '__iter__') else list(v)[0]

# ---------- geometry ----------
TAU = 2 * math.pi
def V(p): return (p.X, p.Y, p.Z)
def add(*vs): return tuple(sum(c) for c in zip(*vs))
def mul(a, s): return tuple(c * s for c in a)
def sub(a, b): return tuple(p - q for p, q in zip(a, b))
def dot(a, b): return sum(p * q for p, q in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def unit(a):
    l = dot(a, a) ** 0.5
    return mul(a, 1.0 / l) if l > 1e-12 else None

def circ(c):
    p1, p2, p3 = V(c.PointAtStart), V(c.PointAt(c.Domain.Mid)), V(c.PointAtEnd)
    a_, b_ = sub(p2, p1), sub(p3, p1)
    n_ = cross(a_, b_)
    cen = add(p1, mul(add(mul(cross(n_, a_), dot(b_, b_)), mul(cross(b_, n_), dot(a_, a_))), 0.5 / dot(n_, n_)))
    X = unit(sub(p1, cen)); Z = unit(n_)
    return cen, dot(sub(p1, cen), sub(p1, cen)) ** 0.5, X, cross(Z, X), Z, (p1, p2, p3)

def span(pts, cen, X, Y):
    s, m, e = [math.atan2(dot(sub(p, cen), Y), dot(sub(p, cen), X)) % TAU for p in pts]
    if (m - s) % TAU <= (e - s) % TAU: return s, (e - s) % TAU
    return e, (s - e) % TAU

def ring_info(ringcrv, skincrv):
    cen, R, X, Y, Z, rp = circ(ringcrv)
    r0, rs = span(rp, cen, X, Y)
    scen, sR, _, _, _, sp = circ(skincrv)
    s0, ss = span(sp, cen, X, Y)
    lo, hi = 0.0, rs
    best = None
    for k in (-1, 0, 1):
        a0 = max(0.0, (s0 - r0) % TAU + k * TAU)
        a1 = min(rs, (s0 - r0) % TAU + k * TAU + ss)
        if a1 - a0 > 1e-9 and (best is None or a1 - a0 > best[1] - best[0]): best = (a0, a1)
    if best: lo, hi = best
    return dict(cen=cen, R=R, X=X, Y=Y, Z=Z, r0=r0, rs=rs, lo=lo, hi=hi, scen=scen, sR=sR)

def u_of(p, F):
    u = (math.atan2(dot(sub(p, F['cen']), F['Y']), dot(sub(p, F['cen']), F['X'])) - F['r0']) % TAU
    if u > F['rs'] + (TAU - F['rs']) / 2: u -= TAU
    return u

def rail_positions(F_list, boards_u, N, w):
    kb, best = None, 1.5
    for U in boards_u:
        gaps = [U[i + 1] - U[i] for i in range(len(U) - 1)]
        if not gaps: continue
        med = sorted(gaps)[len(gaps) // 2]
        for i, g in enumerate(gaps):
            if med > 1e-12 and g / med > best: kb, best = i, g / med
    rows = []
    for F, U in zip(F_list, boards_u):
        ins = (w / 2.0) / F['R']
        lo, hi = F['lo'] + ins, F['hi'] - ins
        if kb is None:
            rows.append(('even', lo, hi)); continue
        e1 = min(max(U[kb], lo), hi)
        e2 = min(max(U[kb + 1], e1), hi)
        rows.append(('eye', lo, e1, e2, hi))
    if kb is None:
        return [[lo + (hi - lo) * j / max(N - 1, 1) for j in range(N)] for _, lo, hi in rows], None
    rest = max(N - 2, 0)
    s1 = sum(r[2] - r[1] for r in rows); s2 = sum(r[4] - r[3] for r in rows)
    n1 = int(round(rest * s1 / (s1 + s2))) if s1 + s2 > 0 else rest // 2
    n2 = rest - n1
    out = []
    for _, lo, e1, e2, hi in rows:
        below = [lo + (e1 - lo) * j / n1 for j in range(n1)] if n1 else []
        above = [e2 + (hi - e2) * j / n2 for j in range(1, n2 + 1)] if n2 else []
        out.append(below + [e1, e2] + above)
    return out, kb

def frame_at(F, u):
    th = F['r0'] + u
    d = add(mul(F['X'], math.cos(th)), mul(F['Y'], math.sin(th)))
    return add(F['cen'], mul(d, F['R'])), d, cross(F['Z'], d), F['Z']

def hit(q, dvec, o, n_):
    s = dot(sub(o, q), n_) / dot(dvec, n_)
    return add(q, mul(dvec, s))

def plank_corners(fa, fb, W, T):
    (oa, _, ta, za), (ob, _, tb, zb) = fa, fb
    xp = unit(sub(ob, oa))
    if xp is None: return None
    if dot(ta, tb) < 0: tb = mul(tb, -1)
    s = add(ta, tb)
    yp = unit(sub(s, mul(xp, dot(s, xp)))); n_ = cross(xp, yp)
    A, B = {}, {}
    for sy in (-1, 1):
        for sz in (-1, 1):
            q = add(oa, mul(yp, sy * W / 2.0), mul(n_, sz * T / 2.0))
            A[sy, sz] = hit(q, xp, oa, za); B[sy, sz] = hit(q, xp, ob, zb)
    return [(A[-1,1], B[-1,1], B[1,1], A[1,1]), (A[-1,-1], A[1,-1], B[1,-1], B[-1,-1]),
            (A[-1,-1], B[-1,-1], B[-1,1], A[-1,1]), (A[1,-1], A[1,1], B[1,1], B[1,-1]),
            (A[-1,-1], A[-1,1], A[1,1], A[1,-1]), (B[-1,-1], B[1,-1], B[1,1], B[-1,1])]

def arm_frame(F, u, H):
    p, d, tg, Z = frame_at(F, u)
    if F['sR'] < F['R']: d = mul(d, -1)
    base = add(p, mul(d, H / 2.0))
    w_ = sub(base, F['scen'])
    bq = dot(w_, d); cq = dot(w_, w_) - F['sR'] ** 2
    disc = bq * bq - cq
    if disc < 0: return None
    L = -bq + disc ** 0.5
    if L <= 1e-6: return None
    return base, d, cross(Z, d), Z, L

# ---------- inputs ----------
if not hasattr(boards, 'Branches'):
    raise Exception("right-click 'boards' and set it to Tree Access")
rings = [rs.coercecurve(c) for c in ring]
skins = [rs.coercecurve(c) for c in skin]
pts = [[V(rs.coerce3dpoint(p)) for p in br] for br in boards.Branches]
N, W, H = int(round(float(one(n)))), float(one(w)), float(one(h))
try: arm_brep = rs.coercebrep(one(arm)) if arm else None
except NameError: arm_brep = None
arm_len = arm_brep.GetBoundingBox(True).Max.Z if arm_brep else 0
count = min(len(rings), len(skins), len(pts))

F = [ring_info(rings[k], skins[k]) for k in range(count)]
BU = [[u_of(p, F[k]) for p in pts[k]] for k in range(count)]
U, kb = rail_positions(F, BU, N, W)

def P3(t): return rg.Point3d(*t)

# ---------- rails: flat mitred segments, continuous end to end ----------
rails = []
for j in range(len(U[0])):
    fr = [frame_at(F[k], U[k][j]) for k in range(count)]
    for k in range(count - 1):
        quads = plank_corners(fr[k], fr[k + 1], W, H)
        if not quads: continue
        faces = List[rg.Brep]()
        for q in quads:
            f = rg.Brep.CreateFromCornerPoints(P3(q[0]), P3(q[1]), P3(q[2]), P3(q[3]), tol)
            if f: faces.Add(f)
        joined = rg.Brep.JoinBreps(faces, tol)
        if joined:
            b = joined[0]
            if b.SolidOrientation == rg.BrepSolidOrientation.Inward: b.Flip()
            rails.append(b)

# ---------- arms: one on every rail at every rib ----------
arms = []
for k in range(count):
    for u in U[k]:
        r_ = arm_frame(F[k], u, H)
        if not r_: continue
        base, d, tg, Z, L = r_
        up = rg.Plane(P3(base), rg.Vector3d(*tg), rg.Vector3d(*Z))
        if arm_brep:
            g = arm_brep.DuplicateBrep()
            if STRETCH and arm_len > 1e-9:
                g.Transform(rg.Transform.Scale(rg.Plane.WorldXY, 1, 1, L / arm_len))
            g.Transform(rg.Transform.PlaneToPlane(rg.Plane.WorldXY, up))
            arms.append(g)
        else:
            arms.append(rg.Box(up, rg.Interval(-ARM_W / 2, ARM_W / 2),
                               rg.Interval(-ARM_D / 2, ARM_D / 2), rg.Interval(0, L)).ToBrep())
