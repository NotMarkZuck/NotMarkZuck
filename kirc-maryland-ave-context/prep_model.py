#!/usr/bin/env python3
"""Prepare all SketchUp model geometry: terrain grid + road/curb/walk ribbons
+ building outlines + bridge. Emits model_data.json."""
import numpy as np, json, ezdxf, topo
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator, RegularGridInterpolator

CX, CY, HALF = 2565620.0, 399138.0, 100.0
X0, X1, Y0, Y1 = CX-HALF, CX+HALF, CY-HALF, CY+HALF

d = np.load("terrain.npz")
M = d["M"]
lin = LinearNDInterpolator(M[:, :2], M[:, 2])
near = NearestNDInterpolator(M[:, :2], M[:, 2])

def surf(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    z = lin(x, y)
    return np.where(np.isnan(z), near(x, y), z)

# ---------- terrain grid ----------
STEP = 3.125
N = int(round(200.0/STEP)) + 1
gx = np.linspace(X0, X1, N); gy = np.linspace(Y0, Y1, N)
GXm, GYm = np.meshgrid(gx, gy)
Z = surf(GXm, GYm)
inbox = (M[:,0]>=X0)&(M[:,0]<=X1)&(M[:,1]>=Y0)&(M[:,1]<=Y1)
Mi = M[inbox]
rgi = RegularGridInterpolator((gy, gx), Z, bounds_error=False, fill_value=None)
r = Mi[:,2] - rgi(np.column_stack([Mi[:,1], Mi[:,0]]))
print(f"terrain {N}x{N} @ {STEP} ft = {(N-1)*(N-1)*2} tris")
print(f"  fit vs {len(Mi)} control pts: RMS {np.sqrt((r**2).mean()):.3f} ft, "
      f"{100*(np.abs(r)<0.25).mean():.0f}% within 0.25 ft")
ZMIN, ZMAX = float(Z.min()), float(Z.max())
print(f"  z {ZMIN:.2f}..{ZMAX:.2f}  (datum = low point {ZMIN:.2f} ft)")

# ---------- robust road-edge extraction ----------
S = json.load(open("site_lines.json"))

def crossings(idx, y):
    P = np.array(S[idx]["pts"]); out = []
    for a, b in zip(P[:-1], P[1:]):
        if (a[1]-y)*(b[1]-y) <= 0 and a[1] != b[1]:
            t = (y-a[1])/(b[1]-a[1]); out.append(a[0] + t*(b[0]-a[0]))
    return out

def fit_edge(idx, xref, tol=12.0):
    """Fit x = a*y + b to the local run of a polyline near xref."""
    ys_s, xs_s = [], []
    for y in np.linspace(Y0-10, Y1+10, 90):
        c = [x for x in crossings(idx, y) if abs(x-xref) < tol]
        if len(c) == 1:
            ys_s.append(y); xs_s.append(c[0])
    if len(ys_s) < 4:
        return None, 0, 0.0
    A = np.polyfit(ys_s, xs_s, 1)
    resid = np.array(xs_s) - np.polyval(A, ys_s)
    return A, len(ys_s), float(np.abs(resid).max())

EDGE = {   # name: (entity index, reference x at y=399138)
    "walk_w_back":  (55, 2565595.03),
    "walk_w_front": (42, 2565601.07),
    "boc_w":        (52, 2565612.23),
    "eop_w":        (53, 2565614.83),
    "eop_e":        (67, 2565650.95),
    "boc_e":        (66, 2565653.55),
    "walk_e_back":  (70, 2565672.89),
}
ys = np.linspace(Y0, Y1, 81)
edges, fits = {}, {}
for k, (idx, xref) in EDGE.items():
    A, n, mx = fit_edge(idx, xref)
    if A is None:
        print(f"  !! {k}: no local run found, using constant x={xref}")
        edges[k] = np.full_like(ys, xref)
    else:
        edges[k] = np.polyval(A, ys)
        fits[k] = (n, mx)
        print(f"  {k:<13} x {edges[k][0]:.2f}->{edges[k][-1]:.2f}  "
              f"(fit on {n} pts, max dev {mx:.3f} ft)")

CURB = 0.5      # curb reveal (ft)
PAVE = 0.02     # lift paving off terrain to avoid z-fighting
WALK = 0.25     # concrete walk sits slightly proud of grade

def ribbon(xa, xb, za_off=0.0, zb_off=0.0):
    za = surf(xa, ys) + za_off
    zb = surf(xb, ys) + zb_off
    return [[[float(xa[i]), float(ys[i]), float(za[i])],
             [float(xb[i]), float(ys[i]), float(zb[i])]] for i in range(len(ys))]

out = {
    "meta": {"CX": CX, "CY": CY, "HALF": HALF, "STEP": STEP, "N": N,
             "ZMIN": ZMIN, "ZMAX": ZMAX, "CURB": CURB},
    "terrain": [[round(float(v), 3) for v in row] for row in Z],
    # roadway spans back-of-curb to back-of-curb (includes the gutter pans)
    "road":     ribbon(edges["boc_w"], edges["boc_e"], PAVE, PAVE),
    # curb faces: vertical, 0.5 ft, at the back-of-curb lines
    "curb_w":   ribbon(edges["boc_w"], edges["boc_w"]-0.5, PAVE, CURB),
    "curb_e":   ribbon(edges["boc_e"], edges["boc_e"]+0.5, PAVE, CURB),
    "walk_w":   ribbon(edges["walk_w_back"], edges["walk_w_front"], WALK, WALK),
    "walk_e":   ribbon(edges["boc_e"]+0.5, edges["walk_e_back"], CURB, WALK),
}
print(f"  roadway width {float(np.mean(edges['boc_e']-edges['boc_w'])):.2f} ft "
      f"(pavement {float(np.mean(edges['eop_e']-edges['eop_w'])):.2f} ft)")
print(f"  west walk {float(np.mean(edges['walk_w_front']-edges['walk_w_back'])):.2f} ft, "
      f"east paved {float(np.mean(edges['walk_e_back']-edges['boc_e'])):.2f} ft")

# ---------- footbridge (approximate) ----------
b_s, b_n = np.array(S[50]["pts"]), np.array(S[49]["pts"])
def y_at_x(P, xs):
    o = np.argsort(P[:,0]); return np.interp(xs, P[o,0], P[o,1])
bxs = np.linspace(X0, X1, 41)
road_z = float(np.median(surf(np.linspace(2565615, 2565651, 9), np.full(9, CY))))
DECK = road_z + 14.0 + 2.0
print(f"\nbridge: road crown {road_z:.2f} -> deck top {DECK:.2f} ft "
      f"(14' clearance + 2' structure); deck y "
      f"{y_at_x(b_s,[CX])[0]:.2f}..{y_at_x(b_n,[CX])[0]:.2f}")
out["bridge"] = {"xs": [float(v) for v in bxs],
                 "y_s": [float(v) for v in y_at_x(b_s, bxs)],
                 "y_n": [float(v) for v in y_at_x(b_n, bxs)],
                 "deck_z": DECK, "thick": 2.0, "parapet": 3.5}

# ---------- building outlines (draped edges) ----------
bl = [[tuple(p) for p in o["pts"]] for o in S if o["layer"] == "C-EA-BCR-E"]
chains = topo.build_chains(bl)
blds = []
for c in chains:
    P = np.array(c)
    if len(P) < 2: continue
    L = float(np.hypot(*np.diff(P, axis=0).T).sum())
    if L < 8: continue
    if not ((P[:,0] >= X0-10) & (P[:,0] <= X1+10) &
            (P[:,1] >= Y0-10) & (P[:,1] <= Y1+10)).any(): continue
    blds.append({"pts": [[float(a), float(b)] for a, b in P], "len": L})
print(f"building outline chains kept: {len(blds)} "
      f"(total {sum(b['len'] for b in blds):.0f} ft of outline)")
out["buildings"] = blds

# ---------- steps ----------
out["steps"] = [[[float(a), float(b)] for a, b in o["pts"]]
                for o in S if o["layer"] == "C-EA-STP-E"]

json.dump(out, open("model_data.json", "w"))
print("\nsaved model_data.json")
