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

# ---------- boards: each plank is flat, so its biggest face is laid straight down on the plane ----------
flat_boards, board_areas, labels = [], [], []
for i, b in enumerate(boards_in):
    if not b: continue
    face = max(b.Faces, key=lambda f_: area(f_.DuplicateFace(False)))
    fb = face.DuplicateFace(False)
    ok, pl = face.TryGetPlane(tol)
    if not ok: continue
    edges = sorted(fb.Edges, key=lambda e: e.GetLength(), reverse=True)
    x = edges[0].PointAtEnd - edges[0].PointAtStart          # lay the plank along X
    src = rg.Plane(fb.GetBoundingBox(True).Center, x, rg.Vector3d.CrossProduct(pl.Normal, x))
    fb.Transform(rg.Transform.PlaneToPlane(src, rg.Plane.WorldXY))
    place(fb)
    a_ = area(fb)
    flat_boards.append(fb); board_areas.append(a_)
    labels.append(label(fb, "B%d  %.2f sf" % (i + 1, a_)))

if flat_boards:      # start the skin on a fresh row
    cursor[0] = ORIGIN.X; cursor[1] -= cursor[2] + 3 * SPACE; cursor[2] = 0.0

# ---------- skin: unrolled flat ----------
# a skin lofted through all the rings bends two ways, so it can't unroll in one go. if that fails,
# it is cut into one strip per bay (between two rings) - each strip is close to flat-bendable,
# so it unrolls with only a tiny stretch, and the areas still add up to the real skin area.
def unroll(b_):
    try:
        u_ = rg.Unroller(b_)
        u_.AbsoluteTolerance = max(tol, 0.01)
        u_.RelativeTolerance = 0.05
        res = u_.PerformUnroll()
        out_ = list(res[0]) if isinstance(res, tuple) else list(res)
        return [p for p in out_ if p]
    except Exception:
        return []

def strips(b_):
    out_ = []
    for f in b_.Faces:
        srf = f.UnderlyingSurface()
        d, sv = max(((d_, list(srf.GetSpanVector(d_))) for d_ in (0, 1)), key=lambda x_: len(x_[1]))
        cuts = [srf.IsoCurve(1 - d, t_) for t_ in sv[1:-1]]
        cuts = [c_ for c_ in cuts if c_]
        sp = f.Split(cuts, tol) if cuts else None
        if sp and sp.Faces.Count > 1:
            out_ += [sp.Faces[i].DuplicateFace(False) for i in range(sp.Faces.Count)]
        else:
            out_.append(f.DuplicateFace(False))
    return out_

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

flat_skin, skin_areas, failed, failed_area = [], [], 0, 0.0
for i, s in enumerate(skins_in):
    if not s: continue
    pieces = unroll(s) if isinstance(s, rg.Brep) else []
    if not pieces:
        parts = strips(s) if isinstance(s, rg.Brep) else [s]
        for st_ in parts:
            got = unroll(st_) if isinstance(st_, rg.Brep) else []
            if not got: got = unfold_mesh(st_)
            if got: pieces += got
            else:
                failed += 1; failed_area += area(st_)
    for p in pieces:
        place(p)
        a_ = area(p)
        flat_skin.append(p); skin_areas.append(a_)
        labels.append(label(p, "S%d  %.2f sf" % (len(flat_skin), a_)))

print("boards: %d pieces, %.1f sq ft total" % (len(board_areas), sum(board_areas)))
print("skin:   %d flat pieces, %.1f sq ft total%s" % (len(skin_areas), sum(skin_areas) + failed_area,
      ("  (%d strip(s), %.1f sq ft, could not be laid flat but are counted)" % (failed, failed_area)) if failed else ""))
print("skin pieces received: %d" % len(skins_in))
