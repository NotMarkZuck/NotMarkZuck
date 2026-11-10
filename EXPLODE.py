#! python3
# Exploded axon: pushes the boards, slats, straps and skin straight outward from the bridge's
# centre line (the line through the centres of the rings). Rings are not moved.
# Works on COPIES - the originals are kept (and hidden) so nothing is lost.
import rhinoscriptsyntax as rs
import Rhino.Geometry as rg

# layer name, default distance it moves outward (ft) - from the inside layer to the outside one
LAYERS = [("boards new", 2.0), ("slats new", 2.0), ("straps new", 4.0), ("skin new", 6.0)]
BREAK_UP = ("skin new",)          # layers whose objects are split into their separate strips first


def find_layer(name):
    # finds the layer even if it sits inside a parent layer or the capitals differ
    for full in rs.LayerNames() or []:
        if full.split("::")[-1].strip().lower() == name.lower():
            return full
    return None


def get_layer(name, colour):
    return name if rs.IsLayer(name) else rs.AddLayer(name, colour)


def ring_centre(obj_id):
    g = rs.coercegeometry(obj_id)
    crv = g if isinstance(g, rg.Curve) else None
    if crv is None:
        b = rs.coercebrep(obj_id)
        if b:
            edges = list(b.DuplicateEdgeCurves(True))
            if edges:
                crv = max(edges, key=lambda c: c.GetLength())     # the long curved edge of the ring
    if crv is None:
        return None
    res = crv.TryGetArc(0.01)
    if isinstance(res, tuple) and res[0]:
        return res[1].Center
    c = rg.Circle(crv.PointAtStart, crv.PointAt(crv.Domain.Mid), crv.PointAtEnd)
    return c.Center if c.IsValid else None


def main():
    rings = rs.GetObjects("Select the rings (ring curves or ring solids) - they set the centre line",
                          rs.filter.curve | rs.filter.polysurface | rs.filter.surface | rs.filter.extrusion)
    if not rings:
        return
    centres = [c for c in (ring_centre(r) for r in rings) if c]
    if len(centres) < 2:
        print("Could not find at least 2 ring centres.")
        return
    # order the centres along the bridge
    a_, b_ = max(((p, q) for p in centres for q in centres), key=lambda pq: pq[0].DistanceTo(pq[1]))
    along = b_ - a_
    centres.sort(key=lambda p: (p - a_) * along)
    axis = rg.PolylineCurve(centres)

    dist = {}
    for name, d in LAYERS:
        v = rs.GetReal("How far to move '%s' outward (ft)" % name, d, 0.0)
        if v is None:
            return
        dist[name] = v

    rs.EnableRedraw(False)
    try:
        ax_layer = get_layer("explode centre line", (255, 0, 0))
        rs.ObjectLayer(rs.AddPolyline(centres), ax_layer)
        report = []
        for name, _ in LAYERS:
            d = dist[name]
            src = find_layer(name)
            objs = rs.ObjectsByLayer(src) if src else None
            if not objs:
                report.append("%s: layer not found or empty" % name)
                continue
            new_layer = get_layer(src.split("::")[-1] + " EXPLODED", rs.LayerColor(src))
            copies = rs.CopyObjects(objs) or []
            rs.ObjectLayer(copies, new_layer)
            if name in BREAK_UP:
                pieces = []
                for cid in copies:
                    if rs.IsPolysurface(cid):
                        pieces += rs.ExplodePolysurfaces(cid, True) or [cid]
                    elif rs.IsMesh(cid):
                        pieces += rs.ExplodeMeshes(cid, True) or [cid]
                    else:
                        pieces.append(cid)
                copies = pieces
                rs.ObjectLayer(copies, new_layer)
            moved = 0
            for cid in copies:
                bb = rs.BoundingBox(cid)
                if not bb:
                    continue
                cen = rg.Point3d(sum(p.X for p in bb) / 8.0, sum(p.Y for p in bb) / 8.0, sum(p.Z for p in bb) / 8.0)
                res = axis.ClosestPoint(cen)
                t = res[1] if isinstance(res, tuple) else res
                on_axis = axis.PointAt(t)
                tan = axis.TangentAt(t)
                out = cen - on_axis
                out = out - tan * (out * tan)          # straight out, square to the centre line
                if not out.Unitize():
                    continue
                rs.MoveObject(cid, out * d)
                moved += 1
            rs.LayerVisible(src, False)
            report.append("%s: %d pieces moved %.2f ft outward" % (name, moved, d))
    finally:
        rs.EnableRedraw(True)
    print("\n".join(report))
    print("Originals are kept on their layers (now hidden). The exploded copies are on the '... EXPLODED' layers.")


main()
