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

# ---------- skin rebuilt from flat panels (needs 'rings') ----------
# the skin is redrawn as narrow strips running along the bridge, each strip made of flat triangles
# (straight edges only). a strip like that can be laid flat EXACTLY - no stretch, no overlap - and
# each flat strip is put back where it sits on the opened-out bridge, so the whole skin keeps its
# shape on the page, like the gores of a globe map. thin wedge gaps between strips show where the
# real skin curves two ways. the real skin is not changed - this is a separate copy.
def tri_area2(p, q, r):
    u = (q[0] - p[0], q[1] - p[1], q[2] - p[2]); v = (r[0] - p[0], r[1] - p[1], r[2] - p[2])
    c = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return 0.5 * (c[0] * c[0] + c[1] * c[1] + c[2] * c[2]) ** 0.5

def build_strips(n_st, n_col, hit, thetas):
    # hit(i, th) -> ((x, y, z), map_xy) or None. returns strips: [(nodes, mapc, tris)]
    cache = {}
    def node(i, j):
        if (i, j) not in cache: cache[(i, j)] = hit(i, thetas[j])
        return cache[(i, j)]
    edge_cache = {}
    def corner(i, j, jo):
        # the corner itself if it is on the skin, else the skin's edge between it and its partner jo
        h = node(i, j)
        if h: return ((i, j), h)
        if not node(i, jo): return None
        key = (i, j, jo)
        if key not in edge_cache:
            t_in, t_out = thetas[jo], thetas[j]
            best = node(i, jo)
            for _ in range(14):
                tm = 0.5 * (t_in + t_out)
                hm = hit(i, tm)
                if hm: t_in, best = tm, hm
                else: t_out = tm
            edge_cache[key] = best
        return ((i, j, 'e', jo), edge_cache[key])
    strips_ = []
    for j in range(n_col - 1):
        run = []
        for i in range(n_st - 1):
            cs = [corner(i, j, j + 1), corner(i, j + 1, j), corner(i + 1, j + 1, j), corner(i + 1, j, j + 1)]
            if any(c is None for c in cs):
                if run: strips_.append(run); run = []
                continue
            run.append(cs)
        if run: strips_.append(run)
    out_ = []
    for run in strips_:
        nodes, mapc, tris = {}, {}, []
        for a_, b_, c_, d_ in run:
            for k_, (P, M) in (a_, b_, c_, d_):
                nodes[k_] = P; mapc[k_] = M
            for t_ in ((a_[0], b_[0], c_[0]), (a_[0], c_[0], d_[0])):
                if tri_area2(nodes[t_[0]], nodes[t_[1]], nodes[t_[2]]) > 1e-9: tris.append(t_)
        if tris: out_.append((nodes, mapc, tris))
    return out_

def unfold_chain(nodes, mapc, tris):
    # lays a strip of triangles flat one after another (exact), then turns/moves it onto its map spot
    def d3(a_, b_): return sum((nodes[a_][k] - nodes[b_][k]) ** 2 for k in range(3)) ** 0.5
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
    m = len(tris) // 2
    a0, b0, c0 = tris[m]
    F = {a0: (0.0, 0.0), b0: (d3(a0, b0), 0.0)}
    F[c0] = third(F[a0], F[b0], d3(a0, c0), d3(b0, c0))
    def walk(order, prev):
        for t_ in order:
            new = [v for v in t_ if v not in F]
            if len(new) != 1: prev = t_; continue
            w_ = new[0]; u_, v_ = [v for v in t_ if v != w_]
            opp = [v for v in prev if v not in (u_, v_)]
            ref = F[opp[0]] if opp and opp[0] in F else None
            F[w_] = third(F[u_], F[v_], d3(u_, w_), d3(v_, w_), ref)
            prev = t_
    walk(tris[m + 1:], tris[m])
    walk(tris[:m][::-1], tris[m])
    # match the map: mirror if needed, then rotate and move onto the map position of the middle triangle
    def cross2(p, q, r): return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if cross2(F[a0], F[b0], F[c0]) * cross2(mapc[a0], mapc[b0], mapc[c0]) < 0:
        F = {k_: (x, -y) for k_, (x, y) in F.items()}
    ang = (math.atan2(mapc[b0][1] - mapc[a0][1], mapc[b0][0] - mapc[a0][0])
           - math.atan2(F[b0][1] - F[a0][1], F[b0][0] - F[a0][0]))
    ca, sa = math.cos(ang), math.sin(ang)
    ox, oy = F[a0]; mx, my = mapc[a0]
    return {k_: (mx + ca * (x - ox) - sa * (y - oy), my + sa * (x - ox) + ca * (y - oy)) for k_, (x, y) in F.items()}

try: STRIP = float(many(strip)[0])          # strip width around the ring (ft)
except: STRIP = 2.0
try: SUB = max(int(round(float(many(sub)[0]))), 1)   # points per bay along the bridge
except: SUB = 3

panels3d, panel_area = None, 0.0
flat_skin, skin_areas, how = [], [], []
if len(R_) > 1 and skins_in:
    msk = rg.Mesh()
    for g_ in skins_in:
        if isinstance(g_, rg.Mesh): msk.Append(g_)
        else:
            mp_ = rg.MeshingParameters.Default; mp_.MaximumEdgeLength = 1.0
            for mm in (rg.Mesh.CreateFromBrep(g_, mp_) or []): msk.Append(mm)
    true_area = sum(area(g_) for g_ in skins_in)
    # stations along the bridge: every ring, plus SUB-1 in between
    ST = []
    along0 = 0.0
    for k in range(len(R_) - 1):
        (c0, r0, m0), (c1, r1, m1) = R_[k], R_[k + 1]
        D = c1 - c0; seg = D.Length; D.Unitize()
        for q in range(SUB + (1 if k == len(R_) - 2 else 0)):
            f = q / float(SUB)
            C = c0 + (c1 - c0) * f
            ref = (m0 - c0) * (1 - f) + (m1 - c1) * f
            ref = ref - D * (ref * D); ref.Unitize()
            ST.append((C, ref, rg.Vector3d.CrossProduct(D, ref), along0 + seg * f))
        along0 += seg
    rmax = max(r for _, r, _ in R_) + 2.0
    n_col = max(int(math.ceil(2 * math.pi * rmax / STRIP)), 8) + 1
    thetas = [-math.pi + 2 * math.pi * j / (n_col - 1) for j in range(n_col)]
    def hit(i, th):
        C, ref, side, along = ST[i]
        dvec = ref * math.cos(th) + side * math.sin(th)
        t_ = rg.Intersect.Intersection.MeshRay(msk, rg.Ray3d(C, dvec))
        if t_ is None or t_ < 0: return None
        P = C + dvec * t_
        r = P.DistanceTo(C)
        return ((P.X, P.Y, P.Z), (ORIGIN.X + along, ORIGIN.Y + th * r))
    strips3 = build_strips(len(ST), n_col, hit, thetas)
    panels3d = rg.Mesh()
    flats = []
    for nodes, mapc, tris in strips3:
        n0 = panels3d.Vertices.Count; idx = {}
        for k_, P in nodes.items():
            idx[k_] = panels3d.Vertices.Count; panels3d.Vertices.Add(P[0], P[1], P[2])
        for t_ in tris:
            panels3d.Faces.AddFace(idx[t_[0]], idx[t_[1]], idx[t_[2]])
            panel_area += tri_area2(nodes[t_[0]], nodes[t_[1]], nodes[t_[2]])
        F2 = unfold_chain(nodes, mapc, tris)
        fm = rg.Mesh(); fi = {}
        for k_, (x, y) in F2.items():
            fi[k_] = fm.Vertices.Count; fm.Vertices.Add(x, y, 0.0)
        for t_ in tris: fm.Faces.AddFace(fi[t_[0]], fi[t_[1]], fi[t_[2]])
        fm.Normals.ComputeNormals()
        flats.append(fm)
    panels3d.Normals.ComputeNormals()
    if flats:
        # slide the whole skin map down so it sits below the boards (lined up along the bridge with them)
        gb = rg.BoundingBox.Empty
        for fm in flats: gb.Union(fm.GetBoundingBox(True))
        top = (cursor[1] if flat_boards else ORIGIN.Y)
        mv = rg.Transform.Translation(0, top - gb.Max.Y, 0)
        for fm in flats: fm.Transform(mv)
        flat_skin = flats
        skin_areas = [true_area]
        how = ["%d flat strips of straight-edged panels, unrolled exactly (panel area %.1f sf)" % (len(flats), panel_area)]
        gb = rg.BoundingBox.Empty
        for fm in flats: gb.Union(fm.GetBoundingBox(True))
        labels.append(rg.TextDot("SKIN  %.1f sf (panels %.1f sf)" % (true_area, panel_area), gb.Center))

if not flat_skin:
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
print("skin pieces received: %d" % len(skins_in))
