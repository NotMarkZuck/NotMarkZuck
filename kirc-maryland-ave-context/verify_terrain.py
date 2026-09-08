#!/usr/bin/env python3
"""Validate the merged terrain grid against the source contour data."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, ezdxf, topo
from matplotlib.colors import LightSource
from scipy.interpolate import RegularGridInterpolator

d = np.load("terrain.npz")
gx, gy, Z, M, K, E = d["gx"], d["gy"], d["Z"], d["M"], d["K"], d["E"]
CX, CY, HALF = float(d["CX"]), float(d["CY"]), float(d["HALF"])
X0, X1, Y0, Y1 = CX-HALF, CX+HALF, CY-HALF, CY+HALF

fig, axes = plt.subplots(1, 2, figsize=(20, 10))

# ---- panel 1: hillshade + regenerated contours vs source contours ----
ax = axes[0]
ls = LightSource(azdeg=315, altdeg=45)
hs = ls.hillshade(Z, vert_exag=3.0, dx=2.5, dy=2.5)
ax.imshow(hs, cmap="gray", extent=[X0, X1, Y0, Y1], origin="lower", alpha=0.75)
im = ax.contourf(gx, gy, Z, levels=np.arange(674, 688.5, 0.5), cmap="terrain", alpha=0.45)
cs = ax.contour(gx, gy, Z, levels=np.arange(674, 688, 1), colors="k", linewidths=0.8)
ax.clabel(cs, fmt="%d", fontsize=7)

de = ezdxf.readfile(topo.EXST)
f = True
for z, pl in topo.exst_contours(de, layers=("C-EG-1-E",)):
    xs=[p[0] for p in pl]; ys=[p[1] for p in pl]
    if max(xs)<X0 or min(xs)>X1 or max(ys)<Y0 or min(ys)>Y1: continue
    ax.plot(xs, ys, color="red", lw=1.6, ls=(0,(4,3)), zorder=5,
            label="source EXST contour" if f else None); f=False
dk = ezdxf.readfile(topo.KIRC)
labs = topo.numeric_labels(dk, "TOPO-TEXT")
polys=[topo.entity_polyline(e) for e in dk.modelspace() if "TOPO-CONT" in e.dxf.layer]
polys=[p for p in polys if p and len(p)>=2]
lc = topo.label_chains(topo.build_chains(polys), labs)
f=True
for z,c in lc:
    xs=[p[0] for p in c]; ys=[p[1] for p in c]
    if max(xs)<X0 or min(xs)>X1 or max(ys)<Y0 or min(ys)>Y1: continue
    ax.plot(xs, ys, color="blue", lw=1.6, ls=(0,(4,3)), zorder=5,
            label="source KIRC contour" if f else None); f=False
ax.set_xlim(X0,X1); ax.set_ylim(Y0,Y1); ax.set_aspect("equal")
ax.set_title("Merged terrain (black = regenerated contours)\nvs source contours (red=EXST, blue=KIRC as-built)")
ax.legend(loc="lower left", fontsize=8)
plt.colorbar(im, ax=ax, shrink=0.7, label="elevation (ft)")

# ---- panel 2: which source governs where + residuals ----
ax = axes[1]
ax.imshow(hs, cmap="gray", extent=[X0,X1,Y0,Y1], origin="lower", alpha=0.6)
inbox = lambda P: (P[:,0]>=X0)&(P[:,0]<=X1)&(P[:,1]>=Y0)&(P[:,1]<=Y1)
Ki, Ei = K[inbox(K)], E[inbox(E)]
ax.scatter(Ki[:,0], Ki[:,1], s=5, c="blue", label=f"KIRC as-built pts ({len(Ki)})", zorder=4)
ax.scatter(Ei[:,0], Ei[:,1], s=5, c="red", label=f"EXST survey pts ({len(Ei)})", zorder=3, alpha=0.5)
Mi = M[inbox(M)]
rgi = RegularGridInterpolator((gy, gx), Z, bounds_error=False, fill_value=None)
res = Mi[:,2] - rgi(np.column_stack([Mi[:,1], Mi[:,0]]))
sc = ax.scatter(Mi[:,0], Mi[:,1], s=26, c=res, cmap="coolwarm", vmin=-0.5, vmax=0.5,
                edgecolors="k", linewidths=0.2, zorder=6)
plt.colorbar(sc, ax=ax, shrink=0.7, label="control pt - surface (ft)")
ax.set_xlim(X0,X1); ax.set_ylim(Y0,Y1); ax.set_aspect("equal")
ax.set_title("Data sources used, and surface fit residuals")
ax.legend(loc="lower left", fontsize=8)

plt.tight_layout(); plt.savefig("verify_terrain.png", dpi=100)
print("RESIDUALS of surface vs control points inside box:")
print(f"  n={len(res)}  mean {res.mean():+.3f}  max|r| {np.abs(res).max():.3f} ft"
      f"  |r|<0.25ft: {100*(np.abs(res)<0.25).mean():.1f}%")
print("saved verify_terrain.png")
