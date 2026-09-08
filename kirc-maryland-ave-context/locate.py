#!/usr/bin/env python3
"""Locate street-name text and list all layers in a DXF."""
import sys, re, collections
import ezdxf

KEYS = re.compile(r"MARYLAND|KENWOOD|HARTFORD|BRIDGE|NEWPORT|EDGEWOOD|DOWNER|IRC|KIRC", re.I)

def txt_of(e):
    try:
        return (e.dxf.text if e.dxftype() == "TEXT" else e.text)
    except Exception:
        return ""

def pos_of(e):
    for a in ("insert", "location", "center"):
        if e.dxf.hasattr(a):
            p = e.dxf.get(a)
            return (p.x, p.y, p.z)
    return None

path = sys.argv[1]
doc = ezdxf.readfile(path)
msp = doc.modelspace()

print("### STREET / BRIDGE LABELS ###")
hits = []
for e in msp:
    if e.dxftype() in ("TEXT", "MTEXT"):
        t = re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", str(txt_of(e))).strip()
        if t and KEYS.search(t):
            hits.append((t[:60], pos_of(e), e.dxf.layer))
for t, p, lay in sorted(hits, key=lambda h: h[0]):
    if p:
        print(f"  {t!r:<40} @ ({p[0]:.1f}, {p[1]:.1f})  [{lay[-28:]}]")
    else:
        print(f"  {t!r:<40} @ ?  [{lay[-28:]}]")

print("\n### ALL LAYERS (name -> count) ###")
cnt = collections.Counter(e.dxf.layer for e in msp)
for lay in sorted(cnt):
    short = lay.split("$")[-1] if "$" in lay else lay
    print(f"  {cnt[lay]:>5}  {short:<34} | {lay}")

print("\n### BLOCK (INSERT) NAMES ###")
bc = collections.Counter()
for e in msp:
    if e.dxftype() == "INSERT":
        bc[e.dxf.name] += 1
for n, c in bc.most_common(40):
    print(f"  {c:>4}  {n}")
