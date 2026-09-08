#!/usr/bin/env python3
"""Extract + plot the site linework inside the study box, with IDs, so the
road / sidewalk / bridge elements can be identified."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, ezdxf, topo, json

CX, CY, HALF = 2565620.0, 399138.0, 100.0
X0, X1, Y0, Y1 = CX-HALF, CX+HALF, CY-HALF, CY+HALF
PAD = 25

WANT = {
    "C-EP-BOC-E":  ("back of curb",      "#0969da", 2.2),
    "C-EP-GTR-E":  ("gutter/flowline",   "#54aeff", 1.4),
    "C-EP-EDC-E":  ("edge of conc/pave", "#8250df", 1.3),
    "C-EP-EOB-E":  ("edge of bit",       "#a475f9", 1.3),
    "C-EA-WW-E":   ("walkway",           "#cf222e", 1.6),
    "C-EA-STP-E":  ("steps",             "#bc4c00", 1.8),
    "C-EF-RET-E":  ("retaining/bridge",  "#000000", 2.4),
    "C-EF-RAIL-E": ("railing",           "#57606a", 1.2),
    "C-EA-BCR-E":  ("building",          "#6e7781", 2.4),
    "C-EP-CLC-E":  ("centerline",        "#2da44e", 1.0),
}

def clip_ok(pl):
    xs=[p[0] for p in pl]; ys=[p[1] for p in pl]
    return not (max(xs)<X0-PAD or min(xs)>X1+PAD or max(ys)<Y0-PAD or min(ys)>Y1+PAD)

doc = ezdxf.readfile(topo.EXST)
out = []
for e in doc.modelspace():
    lay = e.dxf.layer.split("$")[-1]
    if lay not in WANT: continue
    pl = topo.entity_polyline(e)
    if not pl or len(pl) < 2 or not clip_ok(pl): continue
    out.append({"layer": lay, "type": e.dxftype(), "pts": [[round(x,3), round(y,3)] for x,y in pl]})

# merge collinear-ish fragments per layer into chains for readability
print(f"{len(out)} entities captured")
by = {}
for o in out: by.setdefault(o["layer"], []).append(o)
for lay in sorted(by):
    print(f"  {lay:<14} {WANT[lay][0]:<20} n={len(by[lay])}")

json.dump(out, open("site_lines.json","w"))

fig, ax = plt.subplots(figsize=(16,16))
d = np.load("terrain.npz")
cs = ax.contour(d["gx"], d["gy"], d["Z"], levels=np.arange(672,690,1),
                colors="#cbb", linewidths=0.7, zorder=0)
ax.clabel(cs, fmt="%d", fontsize=6)

seen=set()
for i,o in enumerate(out):
    lay=o["layer"]; nm,c,lw = WANT[lay]
    P=np.array(o["pts"])
    ax.plot(P[:,0],P[:,1],color=c,lw=lw,zorder=3,label=nm if lay not in seen else None)
    seen.add(lay)
    mid=P[len(P)//2]
    ax.annotate(str(i), mid, fontsize=6, color=c, zorder=8,
                bbox=dict(fc="white",ec="none",alpha=0.6,pad=0.4))

ax.add_patch(plt.Rectangle((X0,Y0),2*HALF,2*HALF,fill=False,ec="red",lw=2,ls="--",zorder=10))
ax.set_xlim(X0-PAD,X1+PAD); ax.set_ylim(Y0-PAD,Y1+PAD); ax.set_aspect("equal")
ax.legend(loc="upper left",fontsize=8); ax.grid(alpha=0.2)
ax.set_title("Site linework in study box (numbers = entity index)")
plt.tight_layout(); plt.savefig("site_lines.png",dpi=110)
print("saved site_lines.png")
