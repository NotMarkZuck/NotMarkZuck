#!/usr/bin/env python3
"""Survey a DXF: units, extents, layers, entity mix, text labels."""
import sys, collections
import ezdxf

UNITS = {0:"unitless",1:"inches",2:"feet",3:"miles",4:"mm",5:"cm",6:"m",
         7:"km",8:"microinch",9:"mil",10:"yards",11:"angstrom",12:"nm",
         13:"micron",14:"dm",15:"dam",16:"hm",17:"Gm",18:"AU",19:"ly",20:"pc"}

def zrange(e):
    """Return (minz, maxz) of an entity's vertices, or None."""
    zs = []
    try:
        dxft = e.dxftype()
        if dxft == "LWPOLYLINE":
            el = float(e.dxf.elevation or 0.0)
            zs = [el]
        elif dxft == "POLYLINE":
            zs = [v.dxf.location.z for v in e.vertices]
        elif dxft == "LINE":
            zs = [e.dxf.start.z, e.dxf.end.z]
        elif dxft in ("POINT", "TEXT", "MTEXT", "INSERT", "CIRCLE", "ARC"):
            p = e.dxf.get("insert", None) or e.dxf.get("location", None) or e.dxf.get("center", None)
            if p is not None:
                zs = [p.z]
        elif dxft == "3DFACE":
            zs = [e.dxf.vtx0.z, e.dxf.vtx1.z, e.dxf.vtx2.z, e.dxf.vtx3.z]
        elif dxft == "SPLINE":
            zs = [p[2] for p in e.control_points]
    except Exception:
        return None
    if not zs:
        return None
    return (min(zs), max(zs))


def main(path):
    print("=" * 78)
    print("FILE:", path.split("/")[-1])
    print("=" * 78)
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    ins = doc.header.get("$INSUNITS", 0)
    print(f"DXF version : {doc.dxfversion}")
    print(f"$INSUNITS   : {ins} ({UNITS.get(ins,'?')})")
    for k in ("$EXTMIN", "$EXTMAX", "$LIMMIN", "$LIMMAX"):
        if k in doc.header:
            print(f"{k:12}: {doc.header[k]}")

    # Layer stats
    stats = collections.defaultdict(lambda: {"n": 0, "types": collections.Counter(),
                                             "zmin": float("inf"), "zmax": float("-inf"),
                                             "xmin": float("inf"), "xmax": float("-inf"),
                                             "ymin": float("inf"), "ymax": float("-inf")})
    texts = []
    for e in msp:
        lay = e.dxf.layer
        s = stats[lay]
        s["n"] += 1
        s["types"][e.dxftype()] += 1
        zr = zrange(e)
        if zr:
            s["zmin"] = min(s["zmin"], zr[0])
            s["zmax"] = max(s["zmax"], zr[1])
        try:
            bb = e.bbox() if hasattr(e, "bbox") else None
        except Exception:
            bb = None
        if e.dxftype() in ("TEXT", "MTEXT"):
            try:
                t = e.dxf.text if e.dxftype() == "TEXT" else e.text
                p = e.dxf.get("insert", None) or e.dxf.get("location", None)
                texts.append((lay, str(t).strip()[:70], (round(p.x,1), round(p.y,1), round(p.z,2)) if p else None))
            except Exception:
                pass

    print(f"\nENTITIES total: {sum(s['n'] for s in stats.values())}   LAYERS: {len(stats)}")
    print("-" * 78)
    print(f"{'LAYER':<40} {'N':>6}  {'Z-RANGE':<22} TYPES")
    print("-" * 78)
    for lay in sorted(stats, key=lambda L: -stats[L]["n"]):
        s = stats[lay]
        if s["zmin"] == float("inf"):
            zs = "-"
        else:
            zs = f"{s['zmin']:.2f} .. {s['zmax']:.2f}"
        ty = ", ".join(f"{k}:{v}" for k, v in s["types"].most_common(4))
        print(f"{lay[:40]:<40} {s['n']:>6}  {zs:<22} {ty}")

    print(f"\nTEXT LABELS: {len(texts)}")
    seen = set()
    for lay, t, p in texts:
        key = t.upper()
        if not t or key in seen:
            continue
        seen.add(key)
        if len(seen) <= 120:
            print(f"   [{lay[:22]:<22}] {t!r} @ {p}")
    print()

if __name__ == "__main__":
    for p in sys.argv[1:]:
        try:
            main(p)
        except Exception as ex:
            print(f"!! FAILED {p}: {type(ex).__name__}: {ex}\n")
