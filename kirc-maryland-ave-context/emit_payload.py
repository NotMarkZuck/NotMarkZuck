#!/usr/bin/env python3
"""Emit compact literal payloads for the SketchUp build_model calls."""
import numpy as np, json, ezdxf, topo
from scipy.spatial import cKDTree
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

CX, CY, HALF = 2565620.0, 399138.0, 100.0
X0, X1, Y0, Y1 = CX-HALF, CX+HALF, CY-HALF, CY+HALF

# ---------- campus-wide merged surface (for draping outlines anywhere) ----------
de = ezdxf.readfile(topo.EXST)
dk = ezdxf.readfile(topo.KIRC)

def densify(pts, step=4.0):
    out = []
    for i in range(len(pts)-1):
        (x0,y0),(x1,y1) = pts[i], pts[i+1]
        d = ((x1-x0)**2+(y1-y0)**2)**0.5
        n = max(1, int(d/step))
        for k in range(n):
            t = k/n; out.append((x0+(x1-x0)*t, y0+(y1-y0)*t))
    out.append(pts[-1]); return out

E = np.array([(x,y,z) for z,pl in topo.exst_contours(de, layers=("C-EG-1-E",))
              for (x,y) in densify(pl)])
labs = topo.numeric_labels(dk, "TOPO-TEXT")
polys = [topo.entity_polyline(e) for e in dk.modelspace() if "TOPO-CONT" in e.dxf.layer]
polys = [p for p in polys if p and len(p) >= 2]
lc = topo.label_chains(topo.build_chains(polys), labs)
K = [(x,y,z) for z,c in lc for (x,y) in densify(c)]
K += [(x,y,v) for v,x,y,k in topo.spot_elevations(dk) if k in ("SPOT","TC","BC","BS")]
K = np.array(K)
keep = cKDTree(K[:,:2]).query(E[:,:2])[0] > 22.0
W = np.vstack([K, E[keep]])
wlin = LinearNDInterpolator(W[:,:2], W[:,2]); wnear = NearestNDInterpolator(W[:,:2], W[:,2])
def wsurf(x,y):
    x=np.asarray(x,float); y=np.asarray(y,float)
    z=wlin(x,y); return np.where(np.isnan(z), wnear(x,y), z)
print(f"campus merged surface: {len(W)} pts (KIRC {len(K)}, EXST kept {keep.sum()})")

D = json.load(open("model_data.json"))
ZMIN = D["meta"]["ZMIN"]; N = D["meta"]["N"]; STEP = D["meta"]["STEP"]

# ---------- terrain: integer hundredths of a foot above datum ----------
Z = np.array(D["terrain"])
Zi = np.round((Z - ZMIN)*100).astype(int)
flat = ",".join(str(v) for v in Zi.ravel())
CH = 3
chunks = []
per = len(flat)//CH
i = 0
while i < len(flat):
    j = min(len(flat), i+per)
    if j < len(flat):
        j = flat.find(",", j)
        j = len(flat) if j < 0 else j
    chunks.append(flat[i:j]); i = j+1
print(f"terrain {N}x{N}, {len(flat)} chars in {len(chunks)} chunks "
      f"({', '.join(str(len(c)) for c in chunks)})")
for k,c in enumerate(chunks):
    open(f"payload_terrain_{k}.txt","w").write(c)

# ---------- ribbons -> compact "x,y,z;..." in feet, 2dp ----------
def enc_ribbon(rows):
    return ";".join(f"{a[0]-CX:.2f},{a[1]-CY:.2f},{a[2]-ZMIN:.2f},"
                    f"{b[0]-CX:.2f},{b[1]-CY:.2f},{b[2]-ZMIN:.2f}"
                    for a,b in rows)
rib = {k: enc_ribbon(D[k]) for k in ("road","curb_w","curb_e","walk_w","walk_e")}
for k,v in rib.items():
    open(f"payload_{k}.txt","w").write(v); print(f"  {k:<8} {len(v)} chars, {len(D[k])} stations")

# ---------- bridge ----------
b = D["bridge"]
bs = ";".join(f"{x-CX:.2f},{ys-CY:.2f},{yn-CY:.2f}"
              for x,ys,yn in zip(b["xs"],b["y_s"],b["y_n"]))
open("payload_bridge.txt","w").write(bs)
print(f"  bridge   {len(bs)} chars, deck_z={b['deck_z']-ZMIN:.2f} ft above datum")

# ---------- building outlines, draped on campus surface ----------
blds = []
for e in de.modelspace():
    lay = e.dxf.layer.split("$")[-1]
    if lay not in ("C-BLDG-MAIN-HATCH-N","C-BLDG-E","C-EA-BCR-E"): continue
    pl = topo.entity_polyline(e)
    if not pl or len(pl) < 2: continue
    P = np.array(pl)
    # KIRC footprint always kept (user asked for it); others only near the box
    R = 900.0 if lay == "C-BLDG-MAIN-HATCH-N" else 150.0
    if (P[:,0].max()<CX-R or P[:,0].min()>CX+R or
        P[:,1].max()<CY-R or P[:,1].min()>CY+R): continue
    blds.append((lay, P))
# chain the loose C-EA-BCR-E lines
loose = [[tuple(p) for p in P] for lay,P in blds if lay=="C-EA-BCR-E"]
named = [(lay,P) for lay,P in blds if lay!="C-EA-BCR-E"]
for c in topo.build_chains(loose):
    P = np.array(c)
    if np.hypot(*np.diff(P,axis=0).T).sum() >= 12:
        named.append(("C-EA-BCR-E", P))
print(f"building outlines: {len(named)}")
parts = []
for lay,P in named:
    Q = np.array(densify([tuple(p) for p in P], step=8.0))
    z = wsurf(Q[:,0], Q[:,1])
    tag = {"C-BLDG-MAIN-HATCH-N":"KIRC","C-BLDG-E":"EXBLDG","C-EA-BCR-E":"BLDG"}[lay]
    parts.append(tag+":"+",".join(f"{qx-CX:.1f},{qy-CY:.1f},{qz-ZMIN:.1f}"
                                  for (qx,qy),qz in zip(Q[:,:2],z)))
    print(f"  {tag:<7} {len(Q):>4} pts  x[{P[:,0].min()-CX:+.0f},{P[:,0].max()-CX:+.0f}] "
          f"y[{P[:,1].min()-CY:+.0f},{P[:,1].max()-CY:+.0f}] z {z.min():.1f}..{z.max():.1f}")
s = ";".join(parts); open("payload_buildings.txt","w").write(s)
print(f"  buildings payload {len(s)} chars")
