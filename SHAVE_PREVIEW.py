import Rhino.Geometry as rg
import rhinoscriptsyntax as rs

# quick preview of the shave: joins the start points and the end points of the shave arcs,
# so it updates instantly while you drag the shave gene pools
def many(v):
    try: return list(v) if hasattr(v, '__iter__') else ([] if v is None else [v])
    except NameError: return []

arcs = [rs.coercecurve(c) for c in many(crv) if c is not None]
arcs = [c for c in arcs if c]
starts = [c.PointAtStart for c in arcs]
ends = [c.PointAtEnd for c in arcs]
edge1 = rg.PolylineCurve(starts) if len(starts) > 1 else None
edge2 = rg.PolylineCurve(ends) if len(ends) > 1 else None
print("shave arcs: %d" % len(arcs))
