import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs

# lays the boards and the skin out flat on the XY plane (to the side of the bridge)
# and measures the area of every piece
tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
def many(v):
    try: return list(v) if hasattr(v, '__iter__') else ([] if v is None else [v])
    except NameError: return []
def num(v, d):
    try: return float(many(v)[0])
    except: return d

boards_in = [rs.coercebrep(b) for b in many(boards) if b is not None]
def as_brep(g):
    # accepts the skin as a surface/polysurface, or as a mesh
    b_ = rs.coercebrep(g)
    if b_: return b_
    return rs.coercemesh(g)
skins_in = [as_brep(s) for s in many(skin) if s is not None]
SPACE = num(space, 1.0)          # gap between pieces on the sheet (ft)
ROW = num(row, 120.0)            # start a new row after this many feet
try: o_ = rs.coerce3dpoint(many(origin)[0])
except: o_ = None
bb_all = rg.BoundingBox.Empty
for b in boards_in + skins_in:
    if b: bb_all.Union(b.GetBoundingBox(True))
ORIGIN = o_ if o_ else (rg.Point3d(bb_all.Min.X, bb_all.Min.Y - bb_all.Diagonal.Y - 20.0, 0)
                        if bb_all.IsValid else rg.Point3d.Origin)

def area(g):
    m = rg.AreaMassProperties.Compute(g)
    return m.Area if m else 0.0

# shelf packing: pieces go left to right along a row, then the next row starts below
cursor = [ORIGIN.X, ORIGIN.Y, 0.0]       # x, y, height of the current row
def place(g):
    bb = g.GetBoundingBox(True)
    w, h = bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y
    if cursor[0] > ORIGIN.X and cursor[0] + w > ORIGIN.X + ROW:
        cursor[0] = ORIGIN.X; cursor[1] -= cursor[2] + SPACE; cursor[2] = 0.0
    g.Transform(rg.Transform.Translation(cursor[0] - bb.Min.X, cursor[1] - bb.Max.Y, -bb.Min.Z))
    cursor[0] += w + SPACE; cursor[2] = max(cursor[2], h)
    return g

def label(g, txt):
    return rg.TextDot(txt, g.GetBoundingBox(True).Center)

# ---------- boards ----------
# with the ring curves plugged into 'rings', the boards are unrolled IN PLACE: the bridge is opened out
# like a sleeve, so every board sits where it really is - across the page = along the bridge,
# up the page = around the ring (measured from the middle of each ring's arc). sizes and the 3" gaps
# come out true to within a fraction of an inch. without 'rings' they are laid out in rows instead.
import math
flat_boards, board_areas, labels = [], [], []
try: ring_crvs = [rs.coercecurve(c) for c in many(rings) if c is not None]
except NameError: ring_crvs = []
ring_crvs = [c for c in ring_crvs if c]

def V3(p): return rg.Vector3d(p.X, p.Y, p.Z)
R_ = []
for c in ring_crvs:
    ok, arc = c.TryGetArc(0.01)
    if not ok: continue
    cen, rad = arc.Center, arc.Radius
    mid = c.PointAt(c.Domain.Mid)
    R_.append((cen, rad, mid))
R_.sort(key=lambda r: r[0].X)

def unwrap(P):
    # world point -> (along the bridge, around the ring) for the opened-out map
    if len(R_) < 2: return None
    k = 0
    while k < len(R_) - 2 and P.X > R_[k + 1][0].X: k += 1
    (c0, r0, m0), (c1, r1, m1) = R_[k], R_[k + 1]
    D = c1 - c0
    seg = D.Length; D.Unitize()
    f = ((P - c0) * D) / seg if seg > 1e-9 else 0.0
    C = c0 + (c1 - c0) * f
    rad = r0 + (r1 - r0) * f
    ref = (m0 - c0) * (1 - f) + (m1 - c1) * f           # middle of the arc, blended between the two rings
    ref = ref - D * (ref * D); ref.Unitize()
    side = rg.Vector3d.CrossProduct(D, ref)
    r = P - C
    r = r - D * (r * D)
    th = math.atan2(r * side, r * ref)
    along = sum((R_[i + 1][0] - R_[i][0]).Length for i in range(k)) + seg * f
    return rg.Point3d(ORIGIN.X + along, ORIGIN.Y + th * rad, 0)

for i, b in enumerate(boards_in):
    if not b: continue
    face = max(b.Faces, key=lambda f_: area(f_.DuplicateFace(False)))
    fb = face.DuplicateFace(False)
    a_ = area(fb)
    if R_ and len(R_) > 1:
        loop = rg.Curve.JoinCurves(fb.DuplicateEdgeCurves(True), tol)
        if not loop: continue
        crv_ = loop[0]
        okp, poly = crv_.TryGetPolyline()
        pts_ = list(poly)[:-1] if okp else [crv_.PointAt(t_) for t_ in crv_.DivideByCount(24, True)]
        flat_pts = [unwrap(p) for p in pts_]
        if any(p is None for p in flat_pts): continue
        flat_pts.append(flat_pts[0])
        pb = rg.Brep.CreatePlanarBreps(rg.PolylineCurve(flat_pts), tol)
        if not pb: continue
        fb = pb[0]
    else:
        ok, pl = face.TryGetPlane(tol)
        if not ok: continue
        edges = sorted(fb.Edges, key=lambda e: e.GetLength(), reverse=True)
        x = edges[0].PointAtEnd - edges[0].PointAtStart          # lay the plank along X
        src = rg.Plane(fb.GetBoundingBox(True).Center, x, rg.Vector3d.CrossProduct(pl.Normal, x))
        fb.Transform(rg.Transform.PlaneToPlane(src, rg.Plane.WorldXY))
        place(fb)
    flat_boards.append(fb); board_areas.append(a_)
    labels.append(label(fb, "B%d  %.2f sf" % (i + 1, a_)))

if flat_boards:      # start the skin on a fresh row, below the boards
    bbb = rg.BoundingBox.Empty
    for fb in flat_boards: bbb.Union(fb.GetBoundingBox(True))
    cursor[0] = ORIGIN.X; cursor[1] = min(cursor[1] - cursor[2], bbb.Min.Y) - 3 * SPACE; cursor[2] = 0.0

# ---------- skin: laid flat as ONE piece ----------
# the skin pieces are joined into one surface first. a skin that only bends one way unrolls exactly;
# one that bends two ways can't be flattened without a little stretch, so it is "squished" flat in one
# piece (like Rhino's Squish command). the label always shows the TRUE area of the skin.
def unroll(b_):
    try:
        u_ = rg.Unroller(b_)
        u_.AbsoluteTolerance = max(tol, 0.01)
        u_.RelativeTolerance = 0.05
        res = u_.PerformUnroll()
        out_ = list(res[0]) if isinstance(res, tuple) else list(res)
        out_ = [p for p in out_ if p]
        if len(out_) > 1:                      # came apart - only accept it if it rejoins into one piece
            j_ = rg.Brep.JoinBreps(out_, tol)
            out_ = list(j_) if j_ and len(j_) == 1 else []
        return out_
    except Exception:
        return []

def to_mesh(g):
    if isinstance(g, rg.Mesh): return g
    mp = rg.MeshingParameters.Default
    mp.MaximumEdgeLength = 0.5
    ms = rg.Mesh.CreateFromBrep(g, mp)
    if not ms: return None
    m = rg.Mesh()
    for mm in ms: m.Append(mm)
    m.Weld(3.14159)
    return m

def squish(g):
    try:
        m = to_mesh(g)
        if m is None: return []
        res = rg.Squisher().SquishMesh(rg.SquishParameters(), m)
        return [res] if res else []
    except Exception:
        return []

def unfold_mesh(g):
    # fallback that always works: mesh the piece and fold its triangles out flat one by one,
    # keeping every triangle's true size (so the flat area is exactly the real area)
    import math
    from collections import deque
    if isinstance(g, rg.Mesh): ms = [g]
    else: ms = list(rg.Mesh.CreateFromBrep(g, rg.MeshingParameters.Default) or [])
    if not ms: return []
    m = rg.Mesh()
    for mm in ms: m.Append(mm)
    m.Faces.ConvertQuadsToTriangles()
    key, P3 = {}, []
    def vid(i):
        v = m.Vertices[i]
        k = (round(v.X, 5), round(v.Y, 5), round(v.Z, 5))
        if k not in key: key[k] = len(P3); P3.append((v.X, v.Y, v.Z))
        return key[k]
    T = []
    for i in range(m.Faces.Count):
        f = m.Faces[i]
        t_ = (vid(f.A), vid(f.B), vid(f.C))
        if len(set(t_)) == 3: T.append(t_)
    E = {}
    for fi, t_ in enumerate(T):
        for e in ((t_[0], t_[1]), (t_[1], t_[2]), (t_[2], t_[0])):
            E.setdefault(frozenset(e), []).append(fi)
    def dist(i, j): return sum((P3[i][k] - P3[j][k]) ** 2 for k in range(3)) ** 0.5
    def third(A, B, ra, rb, ref=None):
        dx, dy = B[0] - A[0], B[1] - A[1]
        d = (dx * dx + dy * dy) ** 0.5 or 1e-12
        a_ = (ra * ra - rb * rb + d * d) / (2 * d)
        h_ = max(ra * ra - a_ * a_, 0.0) ** 0.5
        bx, by = A[0] + a_ * dx / d, A[1] + a_ * dy / d
        c1, c2 = (bx - h_ * dy / d, by + h_ * dx / d), (bx + h_ * dy / d, by - h_ * dx / d)
        if ref is None: return c1
        side = lambda p: dx * (p[1] - A[1]) - dy * (p[0] - A[0])
        return c1 if side(c1) * side(ref) < 0 else c2
    placed = [None] * len(T)
    out_ = []
    for st0 in range(len(T)):
        if placed[st0] is not None: continue
        a0, b0, c0 = T[st0]
        A, B = (0.0, 0.0), (dist(a0, b0), 0.0)
        placed[st0] = {a0: A, b0: B, c0: third(A, B, dist(a0, c0), dist(b0, c0))}
        flat = rg.Mesh(); q = deque([st0])
        while q:
            fi = q.popleft(); co = placed[fi]; t_ = T[fi]
            n0 = flat.Vertices.Count
            for v in t_: flat.Vertices.Add(co[v][0], co[v][1], 0.0)
            flat.Faces.AddFace(n0, n0 + 1, n0 + 2)
            for e in ((t_[0], t_[1]), (t_[1], t_[2]), (t_[2], t_[0])):
                for nf in E[frozenset(e)]:
                    if placed[nf] is not None: continue
                    u_, v_ = e
                    w_ = [x for x in T[nf] if x not in e][0]
                    opp = [x for x in t_ if x not in e][0]
                    placed[nf] = {u_: co[u_], v_: co[v_],
                                  w_: third(co[u_], co[v_], dist(u_, w_), dist(v_, w_), co[opp])}
                    q.append(nf)
        flat.Normals.ComputeNormals()
        out_.append(flat)
    return out_

flat_skin, skin_areas, how = [], [], []
breps_ = [g for g in skins_in if isinstance(g, rg.Brep)]
meshes_ = [g for g in skins_in if isinstance(g, rg.Mesh)]
joined_ = list(rg.Brep.JoinBreps(breps_, tol) or breps_) if breps_ else []
if meshes_:
    mj = rg.Mesh()
    for mm in meshes_: mj.Append(mm)
    joined_.append(mj)
for s in joined_:
    true_area = area(s)
    flat = unroll(s) if isinstance(s, rg.Brep) else []
    method = "unrolled exactly"
    if not flat:
        flat = squish(s); method = "squished (slight stretch)"
    if not flat:
        parts = unfold_mesh(to_mesh(s)) or []
        flat = [max(parts, key=area)] if parts else []; method = "unfolded"
    if not flat: continue
    p = flat[0]
    place(p)
    flat_skin.append(p); skin_areas.append(true_area); how.append(method)
    labels.append(label(p, "SKIN %d  %.1f sf" % (len(flat_skin), true_area)))

print("boards: %d pieces, %.1f sq ft total" % (len(board_areas), sum(board_areas)))
for i, (a_, h_) in enumerate(zip(skin_areas, how)):
    print("skin %d: %.1f sq ft (true area) - %s" % (i + 1, a_, h_))
print("skin total: %.1f sq ft | skin pieces received: %d, joined into %d" % (sum(skin_areas), len(skins_in), len(joined_)))
