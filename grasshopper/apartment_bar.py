"""
Apartment Bar Generator  (Grasshopper Python script component)

Takes a line drawn in Rhino and treats it as the centerline of a
double-loaded corridor. Apartment boxes are placed on both sides of the
corridor, an end unit caps each end of the line, and the whole thing is
stacked for the chosen number of floors.

All dimensions are in feet (set your Rhino file units to Feet).

INPUTS (right-click each input on the component to set its name / type):
    Line          - Curve. The line you drew in Rhino (the corridor centerline).
    Floors        - int. Number of floors (connect a Number Slider).
    UnitWidth     - float. Target width of a typical unit along the corridor. Default 25.
    UnitDepth     - float. Depth of a unit from corridor to exterior wall. Default 30.
    EndUnitLength - float. How far each end unit runs along the line. Default 30.
    FloorHeight   - float. Floor-to-floor height. Default 10.
    CorridorWidth - float. Corridor width. Default 5.

OUTPUTS:
    Units     - Boxes for the typical units on both sides of the corridor.
    EndUnits  - Boxes for the end units that cap each end.
    Corridor  - Boxes for the corridor on each floor.
    Info      - A short text summary (unit counts, sizes).
"""

import math
import Rhino.Geometry as rg


def default(value, fallback):
    return fallback if value is None else value


def make_box(plane, x0, x1, y0, y1, z0, z1):
    return rg.Box(plane, rg.Interval(x0, x1), rg.Interval(y0, y1),
                  rg.Interval(z0, z1)).ToBrep()


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
    # Accept either a Rhino curve or a plain line
    if hasattr(Line, "PointAtStart"):
        start, end = Line.PointAtStart, Line.PointAtEnd
    else:
        start, end = Line.From, Line.To

    # Flatten to the start point's elevation so the building sits level
    end = rg.Point3d(end.X, end.Y, start.Z)
    direction = end - start
    length = direction.Length

    if length > 0:
        direction.Unitize()
        side = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, direction)
        # Local frame: X runs along the line, Y runs across it, Z is up
        plane = rg.Plane(start, direction, side)

        half = corr_w / 2.0
        full_half = half + unit_d          # half of the total building width

        # Space between the two end units holds the typical units
        middle = length - 2.0 * end_len
        if middle < 0:
            # Line is too short for two full end units: split it between them
            end_len = length / 2.0
            middle = 0.0

        count = int(math.floor(middle / unit_w + 1e-9)) if middle > 0 else 0
        if middle > 0 and count == 0:
            count = 1
        actual_w = middle / count if count else 0.0

        for f in range(floors):
            z0 = f * floor_h
            z1 = z0 + floor_h

            # End units span the full building width at each end
            EndUnits.append(make_box(plane, 0, end_len, -full_half, full_half, z0, z1))
            EndUnits.append(make_box(plane, length - end_len, length,
                                     -full_half, full_half, z0, z1))

            # Corridor between the end units
            if middle > 0:
                Corridor.append(make_box(plane, end_len, length - end_len,
                                         -half, half, z0, z1))

            # Typical units on both sides
            for i in range(count):
                x0 = end_len + i * actual_w
                x1 = x0 + actual_w
                Units.append(make_box(plane, x0, x1, half, full_half, z0, z1))
                Units.append(make_box(plane, x0, x1, -full_half, -half, z0, z1))

        Info = "\n".join([
            "Floors: %d" % floors,
            "Typical units per side per floor: %d" % count,
            "Typical unit size: %.1f' x %.1f' (%.0f sf)" % (actual_w, unit_d, actual_w * unit_d),
            "End unit size: %.1f' x %.1f' (%.0f sf)" % (end_len, 2 * full_half,
                                                        end_len * 2 * full_half),
            "Total units: %d" % (floors * (2 * count + 2)),
            "Building height: %.1f'" % (floors * floor_h),
        ])
