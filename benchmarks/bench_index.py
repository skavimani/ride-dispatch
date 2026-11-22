"""Benchmark 1: k-d tree (Phase 2) vs uniform grid (Phase 3) driver index.

For 1k, 10k and 100k drivers spread over a 40 km x 40 km city:
build time, GPS-update cost (at least 3 updates per driver), and k-nearest (k = 5) query cost.
Run from the repository root:  python3 -m benchmarks.bench_index
"""

import random
import time

from ridedispatch import KDTree
from ridedispatch.grid_index import GridIndex

from .common import save, memory_of

CITY_KM = 40.0
QUERIES = 5_000


def run(n, make):
    UPDATES = max(50_000, 3 * n)     # every driver moves ~3 times or more
    rng = random.Random(n)
    pts = {i: (rng.uniform(0, CITY_KM), rng.uniform(0, CITY_KM)) for i in range(n)}
    t = time.perf_counter()
    idx = make(pts.items())
    build = time.perf_counter() - t
    moves = []
    for _ in range(UPDATES):
        i = rng.randrange(n)
        x, y = pts[i]
        pts[i] = (min(CITY_KM, max(0.0, x + rng.uniform(-0.2, 0.2))),
                  min(CITY_KM, max(0.0, y + rng.uniform(-0.2, 0.2))))
        moves.append((i, pts[i]))
    t = time.perf_counter()
    for i, p in moves:
        idx.update(i, p)
    upd = (time.perf_counter() - t) / UPDATES
    qs = [(rng.uniform(0, CITY_KM), rng.uniform(0, CITY_KM)) for _ in range(QUERIES)]
    t = time.perf_counter()
    for q in qs:
        idx.nearest(q, 5)
    qry = (time.perf_counter() - t) / QUERIES
    mem = memory_of(lambda: make(list(pts.items())))
    return {"build_s": build, "update_us": upd * 1e6, "query_us": qry * 1e6,
            "memory_mb": mem / 1e6, "rebuilds": getattr(idx, "rebuilds", 0)}


def main():
    out = {}
    for n in (1_000, 10_000, 100_000):
        # about 1-2 drivers per cell on average
        cell = max(0.25, (CITY_KM * CITY_KM / n) ** 0.5 * 1.5)
        out[n] = {
            "kdtree": run(n, lambda items: KDTree(items)),
            "grid": run(n, lambda items, c=cell: GridIndex(c, items)),
            "cell_km": cell,
        }
        print(n, {k: {m: round(v, 2) for m, v in r.items()} if isinstance(r, dict) else r
                  for k, r in out[n].items()})
    save("index", out)


if __name__ == "__main__":
    main()
