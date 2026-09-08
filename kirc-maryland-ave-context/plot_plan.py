#!/usr/bin/env python3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ezdxf, topo

CX, CY, H = 2565620.0, 399138.0, 100.0
PAD = 80

de = ezdxf.readfile(topo.EXST)
dk = ezdxf.readfile(topo.KIRC)

fig, ax = plt.subplots(figsize=(13, 13))

def draw(doc, laynames, color, lw, label, ls="-", zo=2):
    first = True
    for e in doc.modelspace():
        lay = e.dxf.layer.split("$")[-1]
        if lay not in laynames:
            continue
        pl = topo.entity_polyline(e)
        if not pl or len(pl) < 2:
            continue
        xs = [p[0] for p in pl]; ys = [p[1] for p in pl]
        if max(xs) < CX-H-PAD or min(xs) > CX+H+PAD or max(ys) < CY-H-PAD or min(ys) > CY+H+PAD:
            continue
        ax.plot(xs, ys, color=color, lw=lw, ls=ls, zorder=zo,
                label=label if first else None)
        first = False

# existing contours
firstc = True
for z, pl in topo.exst_contours(de, layers=("C-EG-1-E",)):
    xs = [p[0] for p in pl]; ys = [p[1] for p in pl]
    if max(xs) < CX-H-PAD or min(xs) > CX+H+PAD or max(ys) < CY-H-PAD or min(ys) > CY+H+PAD:
        continue
    ax.plot(xs, ys, color="#c8b89a", lw=0.8, zorder=1,
            label="EXST contour (1ft)" if firstc else None)
    firstc = False

# KIRC design contours
labs = topo.numeric_labels(dk, "TOPO-TEXT")
polys = [topo.entity_polyline(e) for e in dk.modelspace() if "TOPO-CONT" in e.dxf.layer]
polys = [p for p in polys if p and len(p) >= 2]
lc = topo.label_chains(topo.build_chains(polys), labs)
firstk = True
for z, c in lc:
    xs = [p[0] for p in c]; ys = [p[1] for p in c]
    if max(xs) < CX-H-PAD or min(xs) > CX+H+PAD or max(ys) < CY-H-PAD or min(ys) > CY+H+PAD:
        continue
    ax.plot(xs, ys, color="#1a7f37", lw=1.4, zorder=3,
            label="KIRC as-built contour" if firstk else None)
    firstk = False
    ax.annotate(f"{int(z)}", (xs[len(xs)//2], ys[len(ys)//2]), fontsize=6,
                color="#1a7f37", zorder=6)

draw(de, {"C-EP-BOC-E"}, "#0969da", 2.0, "back of curb")
draw(de, {"C-EP-EDC-E"}, "#8250df", 1.3, "edge of pavement/conc")
draw(de, {"C-EP-GTR-E"}, "#0969da", 1.0, "gutter", ls="--")
draw(de, {"C-EA-WW-E"}, "#cf222e", 1.4, "walkway")
draw(de, {"C-EA-STP-E"}, "#bc4c00", 1.6, "steps")
draw(de, {"C-EF-RET-E"}, "#000000", 2.2, "retaining wall / footbridge")
draw(de, {"C-EF-RAIL-E"}, "#57606a", 1.0, "railing")
draw(de, {"C-EA-BCR-E"}, "#6e7781", 2.2, "building outline")
draw(dk, {"L-SITE-WALK"}, "#d1242f", 1.0, "KIRC walk", ls=":")
draw(dk, {"L-SITE-WALL"}, "#7d4e00", 1.2, "KIRC wall", ls=":")

# KIRC spot elevations
sp = topo.spot_elevations(dk)
sx = [s[1] for s in sp if CX-H-PAD < s[1] < CX+H+PAD and CY-H-PAD < s[2] < CY+H+PAD]
sy = [s[2] for s in sp if CX-H-PAD < s[1] < CX+H+PAD and CY-H-PAD < s[2] < CY+H+PAD]
ax.scatter(sx, sy, s=14, c="#1a7f37", marker="+", zorder=7, label="KIRC spot elev")

# street labels
for e in de.modelspace():
    if e.dxftype() in ("TEXT", "MTEXT"):
        t = topo.text_of(e)
        if any(k in t.upper() for k in ("MARYLAND", "KENWOOD", "FOOTBRIDGE")):
            p = topo.pos_of(e)
            if p and CX-H-PAD < p[0] < CX+H+PAD and CY-H-PAD < p[1] < CY+H+PAD:
                ax.annotate(t[:28], p, fontsize=9, color="darkred", weight="bold", zorder=9)

# study box
ax.add_patch(plt.Rectangle((CX-H, CY-H), 2*H, 2*H, fill=False, ec="red",
                           lw=2.5, ls="--", zorder=10, label="200' x 200' study box"))
ax.plot([CX], [CY], "r*", ms=16, zorder=11)

ax.set_aspect("equal")
ax.set_xlim(CX-H-PAD, CX+H+PAD); ax.set_ylim(CY-H-PAD, CY+H+PAD)
ax.set_title("UWM KIRC / N Maryland Ave footbridge — study area\n"
             "grey=old survey contours, green=KIRC as-built grading", fontsize=12)
ax.legend(loc="upper left", fontsize=7, ncol=2)
ax.grid(alpha=0.25)
plt.tight_layout()
plt.savefig("study_area.png", dpi=115)
print("saved study_area.png")
