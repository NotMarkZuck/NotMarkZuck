#!/usr/bin/env python3
"""Merge KIRC as-built grading over the older campus survey, build a gridded
terrain surface for the 200x200 ft study box at the N Maryland Ave footbridge."""
import numpy as np, ezdxf, topo
from scipy.spatial import cKDTree
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

CX, CY, HALF = 2565620.0, 399138.0, 100.0
PAD = 60.0                 # gather data beyond box so edges interpolate cleanly
GRID = 2.5                 # ft between terrain grid points
KIRC_RADIUS = 22.0         # KIRC data governs within this distance of a KIRC point

X0, X1 = CX - HALF, CX + HALF
Y0, Y1 = CY - HALF, CY + HALF
GX0, GX1 = X0 - PAD, X1 + PAD
GY0, GY1 = Y0 - PAD, Y1 + PAD


def in_gather(x, y):
    return GX0 <= x <= GX1 and GY0 <= y <= GY1


def densify(pts, step=3.0):
    """Insert points along segments so contours constrain the TIN properly."""
    out = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        d = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        n = max(1, int(d / step))
        for k in range(n):
            t = k / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    out.append(pts[-1])
    return out


def main():
    # ---------- existing survey contours ----------
    de = ezdxf.readfile(topo.EXST)
    exst = []
    for z, pl in topo.exst_contours(de, layers=("C-EG-1-E",)):
        for (x, y) in densify(pl):
            if in_gather(x, y):
                exst.append((x, y, z))
    E = np.array(exst)
    print(f"EXST points in gather area : {len(E)}   z {E[:,2].min():.1f}..{E[:,2].max():.1f}")

    # ---------- KIRC as-built grading ----------
    dk = ezdxf.readfile(topo.KIRC)
    labs = topo.numeric_labels(dk, "TOPO-TEXT")
    polys = [topo.entity_polyline(e) for e in dk.modelspace() if "TOPO-CONT" in e.dxf.layer]
    polys = [p for p in polys if p and len(p) >= 2]
    lc = topo.label_chains(topo.build_chains(polys), labs)

    kirc = []
    for z, c in lc:
        for (x, y) in densify(c):
            if in_gather(x, y):
                kirc.append((x, y, z))
    # ground-level spot elevations only (TW/TS are tops of walls/steps, above grade)
    nspot = 0
    for v, x, y, kind in topo.spot_elevations(dk):
        if kind in ("SPOT", "TC", "BC", "BS") and in_gather(x, y):
            kirc.append((x, y, v)); nspot += 1
    K = np.array(kirc)
    print(f"KIRC points in gather area : {len(K)} (incl {nspot} spot elevs)"
          f"   z {K[:,2].min():.1f}..{K[:,2].max():.1f}")

    # ---------- merge: KIRC wins where it has data ----------
    ktree = cKDTree(K[:, :2])
    d_e, _ = ktree.query(E[:, :2])
    keep = d_e > KIRC_RADIUS
    M = np.vstack([K, E[keep]])
    print(f"EXST points dropped inside KIRC footprint : {(~keep).sum()} of {len(E)}")
    print(f"MERGED control points : {len(M)}")

    # ---------- grid the surface ----------
    nx = int(round(2 * HALF / GRID)) + 1
    gx = np.linspace(X0, X1, nx)
    gy = np.linspace(Y0, Y1, nx)
    GXm, GYm = np.meshgrid(gx, gy)
    lin = LinearNDInterpolator(M[:, :2], M[:, 2])
    Z = lin(GXm, GYm)
    holes = np.isnan(Z)
    if holes.any():
        near = NearestNDInterpolator(M[:, :2], M[:, 2])
        Z[holes] = near(GXm[holes], GYm[holes])
        print(f"filled {holes.sum()} grid holes by nearest-neighbour")
    print(f"GRID {nx}x{nx} @ {GRID} ft   z {Z.min():.2f}..{Z.max():.2f}  (relief {Z.max()-Z.min():.2f} ft)")

    np.savez("terrain.npz", gx=gx, gy=gy, Z=Z, M=M, K=K, E=E,
             CX=CX, CY=CY, HALF=HALF, GRID=GRID)
    print("saved terrain.npz")


if __name__ == "__main__":
    main()
