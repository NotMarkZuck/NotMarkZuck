"""Checks the TriFacade geometry core without Rhino:  python3 test_trifacade.py"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import TriFacade as tf  # noqa: E402

L = 12.0
W, Ht = 96.0, 60.0                       # 96' x 60' facade
BBOX = (0.0, 0.0, W, Ht)


def rect(x, y):
    return 0 <= x <= W and 0 <= y <= Ht


def with_window(x, y):                   # facade with a 20' x 12' opening
    return rect(x, y) and not (60 <= x <= 80 and 20 <= y <= 32)


def pt(px, py):
    return lambda x, y: math.hypot(x - px, y - py)


def edge_lengths_exact(res):
    """Every strut must equal L or sqrt(L^2+h^2) (terrace) / L (fold)."""
    pos = res["pos"]
    allowed = [L]
    if "step" in res:
        allowed.append(math.hypot(L, res["step"]))
    for a, b in res["edges"]:
        d = tf._dist(pos[a], pos[b])
        assert min(abs(d - v) for v in allowed) < 1e-9, d


def lipschitz(res):
    lv = res["levels"]
    return all(abs(lv[a] - lv[b]) <= 1 for a, b in res["edges"])


def test_flat():
    res = tf.generate(BBOX, rect, L)
    assert len(set(res["panel_type"])) == 1
    edge_lengths_exact(res)


def test_terrace_push_pull_curve():
    line = lambda x, y: abs(y - 45.0) if 10 <= x <= 90 else 1e9   # control "curve"
    srcs = [(pt(30, 30), 1.0), (pt(70, 25), -1.0), (line, 0.6)]
    for spread in (True, False):
        res = tf.generate(BBOX, rect, L, sources=srcs, radius=30, depth=8,
                          levels=3, spread=spread)
        assert lipschitz(res)
        assert len(set(res["panel_type"])) <= 2, res["report"]
        edge_lengths_exact(res)
        assert all(res["levels"][k] == 0 for k in res["boundary"])
        print("\n".join(res["report"]), "\n")


def test_nodes_and_hole():
    res = tf.generate(BBOX, with_window, L, node_targets=[(30, 30, 1.0)],
                      depth=6, levels=2, trim=0)
    assert max(res["levels"].values()) == 2
    assert lipschitz(res) and len(set(res["panel_type"])) <= 2
    for t in res["tris"]:
        for k in t:
            assert with_window(*tf.lattice_xy(k, L))


def test_random_fields():
    random.seed(1)
    for _ in range(30):
        srcs = [(pt(random.uniform(0, W), random.uniform(0, Ht)),
                 random.choice([-1, 1]) * random.uniform(.3, 1)) for _ in range(4)]
        res = tf.generate(BBOX, rect, L, sources=srcs, radius=random.uniform(10, 50),
                          levels=random.randint(1, 4), pin_edge=random.random() < .5,
                          spread=random.random() < .5)
        assert lipschitz(res) and len(set(res["panel_type"])) <= 2
        edge_lengths_exact(res)


def test_fold():
    res = tf.generate(BBOX, rect, L, mode=1, sources=[(pt(48, 30), 1.0)],
                      radius=30, depth=6, levels=3)
    assert len(set(res["panel_type"])) == 1, res["report"]
    edge_lengths_exact(res)
    assert max(p[2] for p in res["pos"].values()) > 3
    print("\n".join(res["report"]))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
