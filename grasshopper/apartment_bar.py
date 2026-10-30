"""
Apartment Bar Generator  (Grasshopper Python script component)

Takes a line or curve drawn in Rhino and treats it as the centerline of a
double-loaded corridor. Apartment blocks are placed on both sides of the
corridor, an end unit caps each end, and the whole thing is stacked for
the chosen number of floors.

The curve can be a straight line, a polyline with corners (L, U, Z shapes),
a smooth curve, or a closed shape (a closed shape gets no end units).

All dimensions are in feet (set your Rhino file units to Feet).

INPUTS (right-click each input on the component to set its name / type):
    Line          - Curve. The line or curve you drew in Rhino (the corridor centerline).
    Floors        - int. Number of floors (connect a Number Slider).
    UnitWidth     - float. Target width of a typical unit along the corridor. Default 25.
    UnitDepth     - float. Depth of a unit from corridor to exterior wall. Default 30.
    EndUnitLength - float. How far each end unit runs along the line. Default 30.
    FloorHeight   - float. Floor-to-floor height. Default 10.
    CorridorWidth - float. Corridor width. Default 5.

OUTPUTS:
    Units     - Blocks for the typical units on both sides of the corridor.
    EndUnits  - Blocks for the end units that cap each end.
    Corridor  - Blocks for the corridor on each floor.
    Info      - A short text summary (unit counts, sizes).
"""

import math
import Rhino
import Rhino.Geometry as rg


def default(value, fallback):
    return fallback if value is None else value


def tolerance():
    doc = Rhino.RhinoDoc.ActiveDoc
    return doc.ModelAbsoluteTolerance if doc else 0.01


def to_polyline(curve, max_edge):
    """Turn any curve into a list of corner points (straight segments)."""
    ok, poly = curve.TryGetPolyline()
    if not ok:
        # Smooth curve: approximate it with short straight pieces
        pc = curve.ToPolyline(0, 0, 0.1, 0, 0, 0.5, 0, max_edge, True)
        ok, poly = pc.TryGetPolyline()
    poly.DeleteShortSegments(tolerance())
    poly.MergeColinearSegments(0.01, False)
    return poly


def segments(points, closed):
    """
    Describe each straight segment of the centerline: start/end point,
    direction, sideways normal, and the angled (mitered) offset direction
    at each end so neighbouring segments meet cleanly at corners.
    """
    pts = list(points)
    if closed and pts[0].DistanceTo(pts[-1]) < tolerance():
        pts = pts[:-1]
    count = len(pts) if closed else len(pts) - 1
    segs = []
    for i in range(count):
        p0, p1 = pts[i], pts[(i + 1) % len(pts)]
        d = p1 - p0
        length = d.Length
        d.Unitize()
        n = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, d)
        segs.append({"p0": p0, "p1": p1, "d": d, "n": n, "len": length})

    def miter(n_a, n_b):
        m = n_a + n_b
        if not m.Unitize():
            return rg.Vector3d(n_b)
        c = m * n_b
        if c < 0.2:            # very sharp corner: limit the spike
            c = 0.2
        return m / c

    for i, s in enumerate(segs):
        prev = segs[i - 1] if (closed or i > 0) else None
        nxt = segs[(i + 1) % len(segs)] if (closed or i < len(segs) - 1) else None
        s["m0"] = miter(prev["n"], s["n"]) if prev else rg.Vector3d(s["n"])
        s["m1"] = miter(s["n"], nxt["n"]) if nxt else rg.Vector3d(s["n"])
    return segs


def point(seg, x, s, where):
    """Point on segment at distance x along it, offset s sideways."""
    if where == "start":
        return seg["p0"] + seg["m0"] * s
    if where == "end":
        return seg["p1"] + seg["m1"] * s
    return seg["p0"] + seg["d"] * x + seg["n"] * s


def block(pts, z0, height):
    """Extrude a flat 4-sided footprint into a closed solid."""
    lifted = [rg.Point3d(p.X, p.Y, z0) for p in pts]
    lifted.append(lifted[0])
    outline = rg.PolylineCurve(lifted)
    srf = rg.Surface.CreateExtrusion(outline, rg.Vector3d(0, 0, height))
    brep = srf.ToBrep()
    capped = brep.CapPlanarHoles(tolerance())
    return capped if capped else brep


def band(seg, s_a, s_b):
    """Footprint covering a whole segment between sideways offsets s_a and s_b."""
    return [point(seg, 0, s_a, "start"), point(seg, 0, s_a, "end"),
            point(seg, 0, s_b, "end"), point(seg, 0, s_b, "start")]


def unit_footprints(seg, s_a, s_b, target_w):
    """Split one side of a segment into evenly sized unit footprints."""
    s_mid = (s_a + s_b) / 2.0
    x_start = (seg["m0"] * s_mid) * seg["d"]
    x_end = seg["len"] + (seg["m1"] * s_mid) * seg["d"]
    run = x_end - x_start
    if run <= 0:
        return [], 0.0
    count = max(1, int(math.floor(run / target_w + 1e-9)))
    w = run / count
    cuts = [("start", 0)] + [("mid", x_start + k * w) for k in range(1, count)] + [("end", 0)]
    feet = []
    for k in range(count):
        (wa, xa), (wb, xb) = cuts[k], cuts[k + 1]
        feet.append([point(seg, xa, s_a, wa), point(seg, xb, s_a, wb),
                     point(seg, xb, s_b, wb), point(seg, xa, s_b, wa)])
    return feet, w


Units = []
EndUnits = []
Corridor = []
Info = "Connect a line drawn in Rhino to the Line input."

floors = int(default(Floors, 1))
unit_w = float(default(UnitWidth, 25.0))
unit_d = float(default(UnitDepth, 30.0))
end_len = float(default(EndUnitLength, 30.0))
floor_h = float(default(FloorHeight, 10.0))
corr_w = float(default(CorridorWidth, 5.0))

if Line is not None and floors > 0:
    curve = Line.ToNurbsCurve() if hasattr(Line, "ToNurbsCurve") else rg.LineCurve(Line)

    # Flatten onto the start point's elevation so the building sits level
    base_z = curve.PointAtStart.Z
    curve = rg.Curve.ProjectToPlane(curve, rg.Plane(rg.Point3d(0, 0, base_z), rg.Vector3d.ZAxis))

    total = curve.GetLength()
    closed = curve.IsClosed
    half = corr_w / 2.0
    full_half = half + unit_d          # half of the total building width

    # Split the centerline into: end piece / middle / end piece
    end_pieces = []
    middle = curve
    if not closed:
        if 2 * end_len > total:
            end_len = total / 2.0
        ok_a, t_a = curve.LengthParameter(end_len)
        ok_b, t_b = curve.LengthParameter(total - end_len)
        dom = curve.Domain
        end_pieces = [curve.Trim(dom.Min, t_a), curve.Trim(t_b, dom.Max)]
        end_pieces = [c for c in end_pieces if c]
        middle = curve.Trim(t_a, t_b) if t_b - t_a > 1e-9 else None

    unit_widths = []
    units_per_floor = 0

    middle_segs = []
    if middle:
        poly = to_polyline(middle, unit_w)
        middle_segs = segments(poly, closed)

    end_segs = []
    for piece in end_pieces:
        end_segs.extend(segments(to_polyline(piece, unit_w), False))

    for f in range(floors):
        z0 = f * floor_h

        for seg in end_segs:
            EndUnits.append(block(band(seg, -full_half, full_half), z0, floor_h))

        for seg in middle_segs:
            Corridor.append(block(band(seg, -half, half), z0, floor_h))
            for s_a, s_b in ((half, full_half), (-half, -full_half)):
                feet, w = unit_footprints(seg, s_a, s_b, unit_w)
                for foot in feet:
                    Units.append(block(foot, z0, floor_h))
                if f == 0:
                    units_per_floor += len(feet)
                    if w:
                        unit_widths.append(w)

    end_count = len(end_pieces)
    lines = [
        "Floors: %d" % floors,
        "Typical units per floor: %d" % units_per_floor,
        "End units per floor: %d" % end_count,
        "Total units: %d" % (floors * (units_per_floor + end_count)),
        "Unit depth: %.1f'" % unit_d,
        "Building height: %.1f'" % (floors * floor_h),
    ]
    if unit_widths:
        lines.insert(3, "Typical unit width: %.1f' to %.1f' (measured at mid-depth)"
                     % (min(unit_widths), max(unit_widths)))
    Info = "\n".join(lines)
