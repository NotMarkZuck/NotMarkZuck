#!/usr/bin/env python3
"""Report what geometry falls inside a candidate study box."""
import sys, collections, math
import ezdxf

CX, CY, HALF = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
X0, X1 = CX - HALF, CX + HALF
Y0, Y1 = CY - HALF, CY + HALF

def pts_of(e):
    """Yield (x,y,z) sample points for an entity."""
    t = e.dxftype()
    try:
        if t == "LINE":
            yield (e.dxf.start.x, e.dxf.start.y, e.dxf.start.z)
            yield (e.dxf.end.x, e.dxf.end.y, e.dxf.end.z)
        elif t == "LWPOLYLINE":
            z = float(e.dxf.elevation or 0.0)
            for p in e.get_points("xy"):
                yield (p[0], p[1], z)
        elif t == "POLYLINE":
            for v in e.vertices:
                L = v.dxf.location
                yield (L.x, L.y, L.z)
        elif t == "ARC":
            c = e.dxf.center; r = e.dxf.radius
            a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
            if a1 < a0: a1 += 2 * math.pi
            n = max(2, int((a1 - a0) / 0.2) + 1)
            for i in range(n + 1):
                a = a0 + (a1 - a0) * i / n
                yield (c.x + r * math.cos(a), c.y + r * math.sin(a), c.z)
        elif t == "CIRCLE":
            c = e.dxf.center
            yield (c.x, c.y, c.z)
        elif t in ("TEXT", "MTEXT", "INSERT", "POINT"):
            for a in ("insert", "location"):
                if e.dxf.hasattr(a):
                    p = e.dxf.get(a); yield (p.x, p.y, p.z); return
    except Exception:
        return

def inside(p):
    return X0 <= p[0] <= X1 and Y0 <= p[1] <= Y1

doc = ezdxf.readfile(sys.argv[1])
msp = doc.modelspace()
hit = collections.defaultdict(lambda: collections.Counter())
zs = collections.defaultdict(list)
for e in msp:
    ps = list(pts_of(e))
    if not ps:
        continue
    if any(inside(p) for p in ps):
        lay = e.dxf.layer.split("$")[-1]
        hit[lay][e.dxftype()] += 1
        for p in ps:
            if inside(p) and p[2] != 0:
                zs[lay].append(p[2])

print(f"BOX  X {X0:.1f}..{X1:.1f}   Y {Y0:.1f}..{Y1:.1f}   ({2*HALF:.0f} x {2*HALF:.0f} ft)")
print("-" * 76)
for lay in sorted(hit, key=lambda L: -sum(hit[L].values())):
    ty = ", ".join(f"{k}:{v}" for k, v in hit[lay].most_common())
    zr = ""
    if zs[lay]:
        zr = f"  Z {min(zs[lay]):.1f}..{max(zs[lay]):.1f}"
    print(f"{sum(hit[lay].values()):>5}  {lay:<28}{zr:<22} {ty}")
