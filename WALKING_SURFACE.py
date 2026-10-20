import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs

tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
def one(v): return v if not hasattr(v, '__iter__') else list(v)[0]

prof = rs.coercecurve(one(profile))
woods = []
for b_ in (wood if hasattr(wood, '__iter__') else [wood]):
    b_ = rs.coercebrep(b_) if b_ is not None else None
    if b_: woods.append((b_, b_.GetBoundingBox(True)))
try: STEP = float(one(step))
except: STEP = 0.5
try: REACH = float(one(reach))
except: REACH = 20.0

# stations along the profile: evenly spaced, plus every corner (ramp/landing change)
dom = prof.Domain
L = prof.GetLength()
n = max(int(L / STEP), 1)
ts = list(prof.DivideByCount(n, True))
t = dom.Min
while True:
    res = prof.GetNextDiscontinuity(rg.Continuity.C1_continuous, t, dom.Max)
    ok, tk = (res if isinstance(res, tuple) else (False, None))
    if not ok or tk is None or tk <= t: break
    ts.append(tk); t = tk
ts = sorted(set(round(x, 9) for x in ts))

Z = rg.Vector3d(0, 0, 1)
def hits(p, c):
    a, b = p - c * REACH, p + c * REACH
    lc = rg.LineCurve(a, b)
    lb = lc.GetBoundingBox(True)
    out = []
    for br, bb in woods:
        if (bb.Max.X < lb.Min.X - tol or bb.Min.X > lb.Max.X + tol or
            bb.Max.Y < lb.Min.Y - tol or bb.Min.Y > lb.Max.Y + tol or
            bb.Max.Z < lb.Min.Z - tol or bb.Min.Z > lb.Max.Z + tol): continue
        res = rg.Intersect.Intersection.CurveBrep(lc, br, tol)
        if not isinstance(res, tuple) or not res[0]: continue
        for q in (res[2] or []): out.append((q - p) * c)
        for oc in (res[1] or []):
            out.append((oc.PointAtStart - p) * c); out.append((oc.PointAtEnd - p) * c)
    left = [s for s in out if s < -tol]
    right = [s for s in out if s > tol]
    return (max(left) if left else None), (min(right) if right else None)

# at every station: walk sideways from the profile line until the first wood member on each side
st = []
for t in ts:
    p = prof.PointAt(t)
    tg = prof.TangentAt(t)
    h = rg.Vector3d(tg.X, tg.Y, 0)
    if not h.Unitize(): continue
    c = rg.Vector3d.CrossProduct(Z, h)
    c.Unitize()
    sl, sr = hits(p, c)
    st.append([p, c, sl, sr])

# only keep the stretch of profile that actually sits inside the bridge
idx = [i for i, s in enumerate(st) if s[2] is not None or s[3] is not None]
st = st[idx[0]: idx[-1] + 1] if idx else []

# where there is no wood member, run straight between the last and next touching points
pos = [0.0]
for i in range(1, len(st)):
    a, b = st[i - 1][0], st[i][0]
    pos.append(pos[-1] + ((a.X - b.X) ** 2 + (a.Y - b.Y) ** 2) ** 0.5)
for side in (2, 3):
    known = [i for i, s in enumerate(st) if s[side] is not None]
    if not known: continue
    for i, s in enumerate(st):
        if s[side] is not None: continue
        lo = [k for k in known if k < i]
        hi = [k for k in known if k > i]
        if lo and hi:
            a, b = lo[-1], hi[0]
            f = (pos[i] - pos[a]) / (pos[b] - pos[a]) if pos[b] > pos[a] else 0.0
            s[side] = st[a][side] + (st[b][side] - st[a][side]) * f
        else:
            s[side] = st[lo[-1] if lo else hi[0]][side]

# build the walking surface: flat across, following the profile along
left_pts = [p + c * sl for p, c, sl, sr in st]
right_pts = [p + c * sr for p, c, sl, sr in st]
faces = []
for i in range(len(st) - 1):
    f = rg.Brep.CreateFromCornerPoints(left_pts[i], right_pts[i], right_pts[i + 1], left_pts[i + 1], tol)
    if f: faces.append(f)
surface = None
if faces:
    joined = rg.Brep.JoinBreps(faces, tol)
    if joined:
        surface = joined[0]
        surface.MergeCoplanarFaces(tol)
left = rg.PolylineCurve(left_pts) if len(left_pts) > 1 else None
right = rg.PolylineCurve(right_pts) if len(right_pts) > 1 else None

# ---------- thickness: 6" (or the 'thick' input, in feet), extruded straight down ----------
try: T = float(one(thick))
except: T = 0.5
down = rg.Vector3d(0, 0, -T)
lb = [p + down for p in left_pts]
rb = [p + down for p in right_pts]
sides = []
for i in range(len(st) - 1):
    for q in ((left_pts[i], right_pts[i], right_pts[i + 1], left_pts[i + 1]),
              (lb[i], lb[i + 1], rb[i + 1], rb[i]),
              (left_pts[i], left_pts[i + 1], lb[i + 1], lb[i]),
              (right_pts[i], rb[i], rb[i + 1], right_pts[i + 1])):
        f = rg.Brep.CreateFromCornerPoints(q[0], q[1], q[2], q[3], tol)
        if f: sides.append(f)
if len(st) > 1:
    for q in ((left_pts[0], lb[0], rb[0], right_pts[0]), (left_pts[-1], right_pts[-1], rb[-1], lb[-1])):
        f = rg.Brep.CreateFromCornerPoints(q[0], q[1], q[2], q[3], tol)
        if f: sides.append(f)
joined = rg.Brep.JoinBreps(sides, tol) if sides else None
if joined:
    surface = joined[0]
    surface.MergeCoplanarFaces(tol)
    if surface.SolidOrientation == rg.BrepSolidOrientation.Inward: surface.Flip()
