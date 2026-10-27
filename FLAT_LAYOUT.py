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
skins_in = [rs.coercebrep(s) for s in many(skin) if s is not None]
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

# ---------- skin: unrolled flat (it is lofted with straight sections, so it unrolls exactly) ----------
flat_skin, skin_areas, failed = [], [], 0
for i, s in enumerate(skins_in):
    if not s: continue
    pieces = []
    try:
        u_ = rg.Unroller(s)
        res = u_.PerformUnroll()
        pieces = list(res[0]) if isinstance(res, tuple) else list(res)
    except Exception:
        pieces = []
    if not pieces:
        failed += 1
        continue
    for p in pieces:
        place(p)
        a_ = area(p)
        flat_skin.append(p); skin_areas.append(a_)
        labels.append(label(p, "S%d  %.2f sf" % (len(flat_skin), a_)))

print("boards: %d pieces, %.1f sq ft total" % (len(board_areas), sum(board_areas)))
print("skin:   %d pieces, %.1f sq ft total%s" % (len(skin_areas), sum(skin_areas),
      ("  (%d piece(s) could not be unrolled)" % failed) if failed else ""))
