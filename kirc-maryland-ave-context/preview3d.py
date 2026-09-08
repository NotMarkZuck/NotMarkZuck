#!/usr/bin/env python3
"""3D preview of exactly what was built into the SketchUp model."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, json
from matplotlib.colors import LightSource

d = np.load("terrain.npz")
D = json.load(open("model_data.json"))
CX, CY = D["meta"]["CX"], D["meta"]["CY"]
ZMIN = D["meta"]["ZMIN"]
Z = np.array(D["terrain"])
N = D["meta"]["N"]; STEP = D["meta"]["STEP"]

gx = np.linspace(-100, 100, N)
gy = np.linspace(-100, 100, N)
GX, GY = np.meshgrid(gx, gy)
ZR = Z - ZMIN          # ft above datum

fig = plt.figure(figsize=(19, 9.5))

# ---------------- left: 3D view ----------------
ax = fig.add_subplot(1, 2, 1, projection="3d")
ls = LightSource(azdeg=315, altdeg=45)
cols = ls.shade(ZR, cmap=plt.get_cmap("summer"), vert_exag=4, blend_mode="soft")
ax.plot_surface(GX, GY, ZR, facecolors=cols, rstride=1, cstride=1,
                linewidth=0, antialiased=False, shade=False)

def rib_xyz(key):
    R = D[key]
    A = np.array([[r[0][0]-CX, r[0][1]-CY, r[0][2]-ZMIN] for r in R])
    B = np.array([[r[1][0]-CX, r[1][1]-CY, r[1][2]-ZMIN] for r in R])
    return A, B

for key, c, lw in (("road", "#1a1a1a", 1.6), ("walk_w", "#8a5a2b", 1.4),
                   ("walk_e", "#8a5a2b", 1.4)):
    A, B = rib_xyz(key)
    for P, lab in ((A, None), (B, None)):
        ax.plot(P[:,0], P[:,1], P[:,2]+0.15, color=c, lw=lw, zorder=8)

# bridge
b = D["bridge"]
bx = np.array(b["xs"]) - CX
ys_ = -2.30 + 0.024*bx
yn_ =  9.71 + 0.024*bx
dz = b["deck_z"] - ZMIN
for yy in (ys_, yn_):
    ax.plot(bx, yy, np.full_like(bx, dz), color="#b03a2e", lw=2.5, zorder=12)
ax.plot([bx[0],bx[0]],[ys_[0],yn_[0]],[dz,dz], color="#b03a2e", lw=2.5)
ax.plot([bx[-1],bx[-1]],[ys_[-1],yn_[-1]],[dz,dz], color="#b03a2e", lw=2.5)

ax.set_xlabel("East (ft)"); ax.set_ylabel("North (ft)"); ax.set_zlabel("Height above low point (ft)")
ax.set_xlim(-100,100); ax.set_ylim(-100,100); ax.set_zlim(0,22)
ax.set_box_aspect((1,1,0.30))
ax.view_init(elev=32, azim=-58)
ax.set_title("3D terrain as built into SketchUp\n(red = footbridge deck, black = roadway edges)", fontsize=11)

# ---------------- right: plan with everything ----------------
ax2 = fig.add_subplot(1, 2, 2)
im = ax2.contourf(gx, gy, ZR, levels=np.arange(0, 12.5, 0.25), cmap="terrain")
cs = ax2.contour(gx, gy, ZR, levels=np.arange(0, 12, 1), colors="k", linewidths=0.6)
ax2.clabel(cs, fmt=lambda v: f"{v+ZMIN:.0f}", fontsize=7)

A, B = rib_xyz("road")
ax2.fill(np.concatenate([A[:,0], B[::-1,0]]), np.concatenate([A[:,1], B[::-1,1]]),
         color="#3a3a3a", alpha=0.85, zorder=4, label="roadway (N Maryland Ave)")
for key, c, lab in (("walk_w", "#d8cfc0", "sidewalk west"),
                    ("walk_e", "#d8cfc0", "sidewalk east / paved")):
    A, B = rib_xyz(key)
    ax2.fill(np.concatenate([A[:,0], B[::-1,0]]), np.concatenate([A[:,1], B[::-1,1]]),
             color=c, alpha=0.95, zorder=5, label=lab)
ax2.fill(np.concatenate([bx, bx[::-1]]), np.concatenate([ys_, yn_[::-1]]),
         color="#b03a2e", alpha=0.55, zorder=6, label="footbridge deck (+14' over road)")

ax2.set_aspect("equal"); ax2.set_xlim(-100,100); ax2.set_ylim(-100,100)
ax2.set_xlabel("East (ft) from study-box centre"); ax2.set_ylabel("North (ft)")
ax2.set_title("Plan — 200' x 200' study box\n(labels = true survey elevation, ft)", fontsize=11)
ax2.legend(loc="lower left", fontsize=8)
plt.colorbar(im, ax=ax2, shrink=0.75, label="ft above site low point (674.93)")

plt.tight_layout(); plt.savefig("model_preview.png", dpi=100)
print("saved model_preview.png")
print(f"terrain relief {ZR.min():.2f} .. {ZR.max():.2f} ft  (true {ZMIN:.2f} .. {ZMIN+ZR.max():.2f})")
