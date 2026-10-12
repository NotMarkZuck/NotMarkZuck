"""
TriFacade  -  identical-module triangulated facade for Rhino 8 / Grasshopper
=============================================================================

Paste this whole file into a Grasshopper "Python 3 Script" component
(Rhino 8: Params > Util ... or double-click canvas and type "Python 3").
It also runs in the legacy "GhPython" (IronPython) component.

See SETUP_GUIDE.md for the inputs/outputs to create and how to wire them.
Every input is optional except Srf: any input you do not create (or leave
unconnected) falls back to the default shown below.

WHY THIS APPROACH (short version)
---------------------------------
A sheet of identical equilateral triangles is "intrinsically flat": at every
interior node six 60-degree corners add up to exactly 360 degrees. If you keep
every edge the same length, no node may ever change that angle sum, so the
sheet can only FOLD along straight lines - it can never form a local dome or
bump (discrete version of Gauss's Theorema Egregium). A constraint solver
(Kangaroo) asked for both "all edges equal" and "local bump" will therefore
always return a compromise with many slightly different panels.

This script gives you two exact, fabrication-safe alternatives:

  Mode 0  TERRACE  (default)  - local bumps / dents, EXACTLY 2 panel types
      Nodes move along the surface normal in fixed steps of height h.
      Neighbouring nodes are never more than one step apart. Under that rule
      every triangle is either
          Type A : equilateral  L, L, L          (all three nodes on one level)
          Type B : isosceles    L, S, S          (nodes on two adjacent levels)
      where S = sqrt(L^2 + h^2).  Only 2 strut lengths (L and S) exist.

  Mode 1  FOLD  - pleated bands, EXACTLY 1 panel type
      The sheet folds along lattice lines like rigid origami. Every panel stays
      the identical equilateral triangle and every strut stays length L;
      only hinge angles change. Depth is organised in bands (pleats) rather
      than isolated bumps, and the facade gets slightly shorter in the fold
      direction (allowed by the brief: boundary may shift).

Both modes keep every panel perfectly planar (a triangle always is).
"""

import math

SQ3_2 = math.sqrt(3.0) / 2.0
# axial neighbours on a triangular lattice
NEIGH = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


# =============================================================================
# CORE GEOMETRY  (plain python, no Rhino needed - unit tested separately)
# All coordinates are in the local lattice frame: x along rows, y across rows,
# z along the facade normal.
# =============================================================================

def lattice_xy(key, L):
    i, j = key
    return ((i + 0.5 * j) * L, j * L * SQ3_2)


def build_lattice(bbox, L, inside, trim=1):
    """Return the list of kept triangles (tuples of 3 lattice keys).

    trim 0 = keep triangles with all corners inside the boundary
    trim 1 = keep triangles whose centre is inside   (best overall fit)
    trim 2 = keep triangles with any corner inside   (full coverage)
    """
    xmin, ymin, xmax, ymax = bbox
    H = L * SQ3_2
    cache = {}

    def ins(k):
        if k not in cache:
            x, y = lattice_xy(k, L)
            cache[k] = inside(x, y)
        return cache[k]

    tris = []
    for j in range(int(math.floor(ymin / H)) - 1, int(math.ceil(ymax / H)) + 1):
        i0 = int(math.floor(xmin / L - 0.5 * j)) - 2
        i1 = int(math.ceil(xmax / L - 0.5 * j)) + 2
        for i in range(i0, i1):
            up = ((i, j), (i + 1, j), (i, j + 1))
            down = ((i + 1, j), (i + 1, j + 1), (i, j + 1))
            for t in (up, down):
                if trim == 0:
                    keep = all(ins(k) for k in t)
                elif trim == 2:
                    keep = any(ins(k) for k in t)
                else:
                    pts = [lattice_xy(k, L) for k in t]
                    keep = inside(sum(p[0] for p in pts) / 3.0,
                                  sum(p[1] for p in pts) / 3.0)
                if keep:
                    tris.append(t)
    return tris


def topology(tris):
    """Vertices, edges (with use count), adjacency and boundary vertices."""
    edge_count = {}
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            e = (a, b) if a < b else (b, a)
            edge_count[e] = edge_count.get(e, 0) + 1
    keys = sorted(set(k for t in tris for k in t))
    adj = dict((k, []) for k in keys)
    boundary = set()
    for (a, b), c in edge_count.items():
        adj[a].append(b)
        adj[b].append(a)
        if c == 1:
            boundary.add(a)
            boundary.add(b)
    return keys, sorted(edge_count), adj, boundary


def smoothstep(s):
    s = max(0.0, min(1.0, s))
    return s * s * (3.0 - 2.0 * s)


def influence(keys, L, sources, radius):
    """Signed influence (-1..1) per vertex. sources = [(dist_fn, weight)].
    The strongest source (by absolute value) wins, so push and pull regions
    can live side by side."""
    f = {}
    for k in keys:
        x, y = lattice_xy(k, L)
        best = 0.0
        for dist, w in sources:
            d = dist(x, y)
            if d < radius:
                v = w * smoothstep(1.0 - d / radius)
                if abs(v) > abs(best):
                    best = v
        f[k] = best
    return f


def nearest_key(keys, L, x, y):
    return min(keys, key=lambda k: (lattice_xy(k, L)[0] - x) ** 2 +
                                   (lattice_xy(k, L)[1] - y) ** 2)


def _envelope(vals, adj, up):
    """Make vals 1-Lipschitz on the graph.
    up=True  : smallest function >= vals  (keeps peaks, widens slopes)
    up=False : largest  function <= vals  (keeps footprint, clips peaks)"""
    vals = dict(vals)
    queue = list(vals)
    while queue:
        k = queue.pop()
        for n in adj[k]:
            if up and vals[k] - 1 > vals[n]:
                vals[n] = vals[k] - 1
                queue.append(n)
            elif not up and vals[k] + 1 < vals[n]:
                vals[n] = vals[k] + 1
                queue.append(n)
    return vals


def solve_terrace(keys, edges, adj, target, pinned, spread=True):
    """The 'relaxation' step for TERRACE mode.
    target: dict key -> integer level wanted. Returns integer levels such that
    every pair of neighbours differs by at most one level (=> 2 panel types),
    pinned vertices stay at level 0."""
    pos = dict((k, max(0, target[k])) for k in keys)
    neg = dict((k, max(0, -target[k])) for k in keys)
    pos = _envelope(pos, adj, spread)
    neg = _envelope(neg, adj, spread)
    g = dict((k, pos[k] - neg[k]) for k in keys)
    for k in pinned:
        g[k] = 0
    # resolve remaining conflicts (pinned edges, push next to pull)
    changed = True
    while changed:
        changed = False
        for a, b in edges:
            if abs(g[a] - g[b]) > 1:
                cand = [k for k in (a, b) if k not in pinned]
                k = max(cand, key=lambda c: abs(g[c]))
                g[k] += -1 if g[k] > 0 else 1
                changed = True
    return g


def terrace_positions(keys, L, levels, h):
    return dict((k, lattice_xy(k, L) + (levels[k] * h,)) for k in keys)


def fold_positions(keys, L, f, depth, steps):
    """FOLD mode. Strips between lattice rows are hinged; pairs of strips
    fold up/down (a pleat) so every edge keeps length L exactly.
    Returns (positions, per-row fold angle list)."""
    H = L * SQ3_2
    rows = sorted(set(k[1] for k in keys))
    j0, j1 = rows[0], rows[-1]
    # strongest influence per row
    rowf = dict((j, 0.0) for j in range(j0, j1 + 1))
    for k in keys:
        if abs(f[k]) > abs(rowf[k[1]]):
            rowf[k[1]] = f[k]
    max_ang = math.asin(min(1.0, abs(depth) / H))
    sign_d = 1.0 if depth >= 0 else -1.0
    Y = {j0: j0 * H}
    Z = {j0: 0.0}
    angles = []
    for j in range(j0, j1):
        p = (j - j0) // 2                      # pleat index
        lo = j0 + 2 * p
        span = [rowf.get(r, 0.0) for r in range(lo, min(lo + 2, j1) + 1)]
        v = max(span, key=abs)
        mag = abs(v)
        if steps and steps > 0:
            mag = round(mag * steps) / float(steps)   # standardise hinge angles
        a = max_ang * mag
        if lo + 1 > j1:                        # odd last strip cannot close a pleat
            a = 0.0
        a *= sign_d * (1.0 if v >= 0 else -1.0)
        if (j - j0) % 2 == 1:
            a = -a
        angles.append(a)
        Y[j + 1] = Y[j] + H * math.cos(a)
        Z[j + 1] = Z[j] + H * math.sin(a)
    # keep the facade centred (shrink split evenly top/bottom)
    shift = sum(Y[k[1]] - k[1] * H for k in keys) / float(len(keys))
    pos = {}
    for k in keys:
        x, _ = lattice_xy(k, L)
        pos[k] = (x, Y[k[1]] - shift, Z[k[1]])
    return pos, angles


def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _letters(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def classify(items, sig_fn, by_count=False):
    """Group items by signature. Types are ordered by signature (so the
    equilateral panel / shortest strut is type A / 1), or by frequency."""
    sigs = [sig_fn(it) for it in items]
    counts = {}
    for s in sigs:
        counts[s] = counts.get(s, 0) + 1
    if by_count:
        order = sorted(counts, key=lambda s: (-counts[s], s))
    else:
        order = sorted(counts)
    index = dict((s, i) for i, s in enumerate(order))
    return [index[s] for s in sigs], order, counts


def analyse(tris, edges, adj, pos, L):
    """Panel types, strut types, joint types + text report lines."""
    q = lambda v: round(v / L, 5)
    def tri_sig(t):
        return tuple(sorted(q(_dist(pos[t[a]], pos[t[(a + 1) % 3]])) for a in range(3)))
    def joint_sig(k):
        p = pos[k]
        return tuple(sorted((q(pos[n][0] - p[0]), q(pos[n][1] - p[1]),
                             q(pos[n][2] - p[2])) for n in adj[k]))
    p_ids, p_order, p_counts = classify(tris, tri_sig)
    s_ids, s_order, s_counts = classify(edges, lambda e: q(_dist(pos[e[0]], pos[e[1]])))
    keys = sorted(adj)
    j_ids, j_order, _ = classify(keys, joint_sig, by_count=True)

    ref, worst = {}, 0.0                 # true (unrounded) length check
    for n, (a, b) in enumerate(edges):
        d = _dist(pos[a], pos[b])
        ref.setdefault(s_ids[n], d)
        worst = max(worst, abs(d - ref[s_ids[n]]))
    rep = ["PANEL TYPES: %d" % len(p_order)]
    for n, s in enumerate(p_order):
        rep.append("  Type %s : %4d panels   edges = %s" % (
            _letters(n), p_counts[s], ", ".join("%.4f" % (v * L) for v in s)))
    rep.append("STRUT TYPES: %d" % len(s_order))
    for n, s in enumerate(s_order):
        rep.append("  Strut %d : %4d members  length = %.4f" % (n + 1, s_counts[s], s * L))
    rep.append("JOINTS: %d  (%d distinct node configurations)" % (len(keys), len(j_order)))
    zs = [pos[k][2] for k in keys]
    rep.append("DEPTH: min %.4f   max %.4f" % (min(zs), max(zs)))
    rep.append("Longest panel edge: %.4f" % (max(max(s) for s in p_order) * L))
    rep.append("Largest edge-length error vs. its type: %.2e" % worst)
    return p_ids, s_ids, j_ids, rep


def generate(bbox, inside, L, mode=0, trim=1, sources=(), node_targets=(),
             radius=None, depth=None, levels=2, spread=True, pin_edge=True):
    """Full pipeline in the local frame. node_targets = [(x, y, weight)]."""
    if radius is None:
        radius = 3.0 * L
    if depth is None:
        depth = 0.25 * L
    levels = max(1, int(levels))
    tris = build_lattice(bbox, L, inside, trim)
    if not tris:
        raise ValueError("No triangles fit - make the edge length smaller "
                         "or use Trim = 2.")
    keys, edges, adj, boundary = topology(tris)
    f = influence(keys, L, sources, radius)
    for x, y, w in node_targets:                 # user-picked vertices
        f[nearest_key(keys, L, x, y)] = max(-1.0, min(1.0, w))
    info = {}
    if mode == 1:
        pos, angles = fold_positions(keys, L, f, depth, levels)
        info["levels"] = dict((k, 0) for k in keys)
        info["fold_angles_deg"] = [math.degrees(a) for a in angles]
    else:
        h = depth / float(levels)
        target = dict((k, int(round(f[k] * levels))) for k in keys)
        pinned = boundary if pin_edge else set()
        lv = solve_terrace(keys, edges, adj, target, pinned, spread)
        pos = terrace_positions(keys, L, lv, h)
        info["levels"] = lv
        info["step"] = h
    p_ids, s_ids, j_ids, rep = analyse(tris, edges, adj, pos, L)
    if mode == 1:
        rep.insert(0, "MODE: FOLD (pleated, identical equilateral panels)")
    else:
        rep.insert(0, "MODE: TERRACE (step h = %.4f, %d levels)" % (info["step"], levels))
    return dict(tris=tris, keys=keys, edges=edges, adj=adj, boundary=boundary,
                pos=pos, panel_type=p_ids, strut_type=s_ids, joint_type=j_ids,
                report=rep, **info)


# =============================================================================
# GRASSHOPPER WRAPPER  (only runs inside Rhino)
# =============================================================================

try:
    import Rhino
    import Rhino.Geometry as rg
    import System.Drawing as sd
    _IN_RHINO = True
except ImportError:
    _IN_RHINO = False

PALETTE = [(200, 200, 200), (230, 140, 50), (70, 140, 210), (120, 190, 90),
           (200, 80, 120), (150, 110, 200)]


def _in(name, default):
    v = globals().get(name)
    if v is None or (isinstance(v, (list, tuple)) and len(v) == 0):
        return default
    return v


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [x for x in v if x is not None]
    try:
        return [x for x in v if x is not None]  # .NET lists
    except TypeError:
        return [v]


def _weights(w, n):
    w = [float(x) for x in _as_list(w)]
    if not w:
        return [1.0] * n
    return [w[min(i, len(w) - 1)] for i in range(n)]


def _run():
    doc = Rhino.RhinoDoc.ActiveDoc
    tol = doc.ModelAbsoluteTolerance if doc else 0.001

    # ---- 1. input surface --------------------------------------------------
    srf = _in("Srf", None)
    if srf is None:
        raise ValueError("Connect a planar surface to Srf.")
    if isinstance(srf, rg.Surface):
        srf = srf.ToBrep()
    face = srf.Faces[0]
    ok, pl = face.TryGetPlane(tol * 10)
    if not ok:
        raise ValueError("Srf must be planar.")
    if face.OrientationIsReversed:
        pl = rg.Plane(pl.Origin, pl.XAxis, -pl.YAxis)
    # outer boundary first, then any holes (window openings)
    loops = [face.OuterLoop.To3dCurve()]
    loops += [lp.To3dCurve() for lp in face.Loops
              if lp.LoopType == rg.BrepLoopType.Inner]

    # ---- 2. module size ----------------------------------------------------
    ft = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Feet, doc.ModelUnitSystem) if doc else 1.0
    L = float(_in("Size", 12.0 * ft))
    if L <= 0:
        raise ValueError("Size must be greater than zero.")
    H = L * SQ3_2

    # lattice frame: anchored at the lower-left of the surface, then
    # rotated / slid by the user to get the best fit
    XY = rg.Plane.WorldXY

    def flatten(xf):
        """Boundary loops mapped into a frame, plus their 2D bounds."""
        crvs, b = [], [1e100, 1e100, -1e100, -1e100]
        for c in loops:
            d = c.DuplicateCurve()
            d.Transform(xf)
            d = rg.Curve.ProjectToPlane(d, XY)
            box = d.GetBoundingBox(True)
            b = [min(b[0], box.Min.X), min(b[1], box.Min.Y),
                 max(b[2], box.Max.X), max(b[3], box.Max.Y)]
            crvs.append(d)
        return crvs, b

    _, b0 = flatten(rg.Transform.PlaneToPlane(pl, XY))
    origin = pl.PointAt(b0[0] + float(_in("ShiftU", 0.0)) * L,
                        b0[1] + float(_in("ShiftV", 0.0)) * H)
    ang = math.radians(float(_in("Angle", 0.0)))
    xa = pl.XAxis * math.cos(ang) + pl.YAxis * math.sin(ang)
    ya = pl.YAxis * math.cos(ang) - pl.XAxis * math.sin(ang)
    lpl = rg.Plane(origin, xa, ya)
    to_l = rg.Transform.PlaneToPlane(lpl, XY)
    local_loops, bb = flatten(to_l)
    louter, holes = local_loops[0], local_loops[1:]
    OUT = rg.PointContainment.Outside

    def inside(x, y):
        p = rg.Point3d(x, y, 0)
        if louter.Contains(p, XY, tol) == OUT:
            return False
        for hcrv in holes:
            if hcrv.Contains(p, XY, tol) == rg.PointContainment.Inside:
                return False
        return True

    # ---- 3. deformation controls ------------------------------------------
    def local_pt(p):
        return to_l * rg.Point3d(p)

    sources = []
    pts = _as_list(_in("Pts", []))
    for p, w in zip(pts, _weights(_in("PtW", []), len(pts))):
        q = local_pt(p)
        sources.append((lambda x, y, q=q: math.hypot(x - q.X, y - q.Y), w))
    crvs = _as_list(_in("Crvs", []))
    for c, w in zip(crvs, _weights(_in("CrvW", []), len(crvs))):
        d = c.DuplicateCurve()
        d.Transform(to_l)
        d = rg.Curve.ProjectToPlane(d, XY)

        def cdist(x, y, d=d):
            p = rg.Point3d(x, y, 0)
            res = d.ClosestPoint(p)
            t = res[1] if isinstance(res, tuple) else res
            return p.DistanceTo(d.PointAt(t))
        sources.append((cdist, w))
    nodes = _as_list(_in("Nodes", []))
    node_targets = []
    for p, w in zip(nodes, _weights(_in("NodeW", []), len(nodes))):
        q = local_pt(p)
        node_targets.append((q.X, q.Y, w))

    res = generate(tuple(bb), inside, L,
                   mode=int(_in("Mode", 0)), trim=int(_in("Trim", 1)),
                   sources=sources, node_targets=node_targets,
                   radius=float(_in("Radius", 3.0 * L)),
                   depth=float(_in("Depth", 0.25 * L)),
                   levels=int(_in("Levels", 2)),
                   spread=bool(_in("Spread", True)),
                   pin_edge=bool(_in("PinEdge", True)))

    # ---- 4. back to world geometry ----------------------------------------
    keys = res["keys"]
    idx = dict((k, n) for n, k in enumerate(keys))
    W = dict((k, lpl.PointAt(*res["pos"][k])) for k in keys)

    mesh = rg.Mesh()
    for k in keys:
        mesh.Vertices.Add(W[k])
    for t in res["tris"]:
        mesh.Faces.AddFace(idx[t[0]], idx[t[1]], idx[t[2]])
    mesh.Normals.ComputeNormals()
    mesh.Compact()

    panels, colors = [], []
    for t, ty in zip(res["tris"], res["panel_type"]):
        panels.append(rg.Brep.CreateFromCornerPoints(W[t[0]], W[t[1]], W[t[2]], tol))
        c = PALETTE[ty % len(PALETTE)]
        colors.append(sd.Color.FromArgb(c[0], c[1], c[2]))
    struts = [rg.Line(W[a], W[b]) for a, b in res["edges"]]
    joints = [W[k] for k in keys]
    jlevel = [res["levels"][k] for k in keys]

    out = dict(Mesh=mesh, Panels=panels, PanelType=res["panel_type"],
               Colors=colors, Struts=struts, StrutType=res["strut_type"],
               Joints=joints, JointType=res["joint_type"], JointLevel=jlevel,
               Frame=lpl, Report="\n".join(res["report"]))

    # ---- 5. bake ------------------------------------------------------------
    if bool(_in("Bake", False)) and doc:
        _bake(doc, out)
        out["Report"] += "\nBAKED to layer 'TriFacade'."
    return out


def _layer(doc, path, color):
    idx = doc.Layers.FindByFullPath(path, -1)
    if idx >= 0:
        return idx
    parent = None
    if "::" in path:
        parent = doc.Layers[_layer(doc, path.rsplit("::", 1)[0], sd.Color.Black)]
    lay = Rhino.DocObjects.Layer()
    lay.Name = path.rsplit("::", 1)[-1]
    lay.Color = color
    if parent is not None:
        lay.ParentLayerId = parent.Id
    return doc.Layers.Add(lay)


def _bake(doc, out):
    for brep, ty, col in zip(out["Panels"], out["PanelType"], out["Colors"]):
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = _layer(doc, "TriFacade::Panels Type " + _letters(ty), col)
        a.SetUserString("PanelType", _letters(ty))
        doc.Objects.AddBrep(brep, a)
    for ln, ty in zip(out["Struts"], out["StrutType"]):
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = _layer(doc, "TriFacade::Struts %d" % (ty + 1), sd.Color.DimGray)
        a.SetUserString("StrutType", str(ty + 1))
        doc.Objects.AddLine(ln, a)
    for p, ty in zip(out["Joints"], out["JointType"]):
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = _layer(doc, "TriFacade::Joints", sd.Color.Red)
        a.SetUserString("JointType", str(ty + 1))
        doc.Objects.AddPoint(p, a)
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = _layer(doc, "TriFacade::Mesh", sd.Color.Gray)
    doc.Objects.AddMesh(out["Mesh"], a)
    doc.Views.Redraw()


if _IN_RHINO and "ghenv" in globals():
    try:
        _o = _run()
        Mesh = _o["Mesh"]; Panels = _o["Panels"]; PanelType = _o["PanelType"]
        Colors = _o["Colors"]; Struts = _o["Struts"]; StrutType = _o["StrutType"]
        Joints = _o["Joints"]; JointType = _o["JointType"]
        JointLevel = _o["JointLevel"]; Frame = _o["Frame"]; Report = _o["Report"]
    except Exception as e:
        import Grasshopper
        Report = "ERROR: %s" % e
        ghenv.Component.AddRuntimeMessage(
            Grasshopper.Kernel.GH_RuntimeMessageLevel.Error, str(e))
