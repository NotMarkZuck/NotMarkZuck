import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs

tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
def many(v): return list(v) if hasattr(v, '__iter__') else [v]

skins = [rs.coercebrep(s) for s in many(skin) if s is not None]
cuts = [rs.coercebrep(c) for c in many(cutters) if c is not None]
skins = [s for s in skins if s]
cuts = [c for c in cuts if c]
for c in cuts:
    if c.IsSolid and c.SolidOrientation == rg.BrepSolidOrientation.Inward: c.Flip()

def inside(pt):
    for c in cuts:
        if c.IsSolid:
            if c.IsPointInside(pt, tol, False): return True
        elif c.GetBoundingBox(True).Contains(pt):
            return True
    return False

kept, removed = [], []
for s in skins:
    pieces = [s]
    # split the skin along every cutter
    for c in cuts:
        nxt = []
        for p in pieces:
            sp = p.Split(c, tol)
            nxt.extend(list(sp) if sp and len(sp) > 0 else [p])
        pieces = nxt
    # drop every piece that sits inside a cutter
    for p in pieces:
        amp = rg.AreaMassProperties.Compute(p)
        if amp is None:
            kept.append(p); continue
        pt = p.ClosestPoint(amp.Centroid)
        (removed if inside(pt) else kept).append(p)

skin_cut = kept
print("skin pieces in: %d | cutters: %d (closed: %s)" % (len(skins), len(cuts), [c.IsSolid for c in cuts]))
print("kept: %d | removed: %d" % (len(kept), len(removed)))
