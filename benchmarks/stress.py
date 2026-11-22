"""Benchmark 4: stress tests under extreme or unexpected input.

  gps_storm      100,000 drivers, 1,000,000 GPS updates (k-d tree vs grid)
  cancel_flood   1,000,000 requests, 99% cancelled (heap must stay small)
  same_spot      20,000 drivers all on one intersection (both indexes' worst case)
  unreachable    50 pickups on a cut-off 400-intersection district
  surge          3,000 requests at one stadium exit at the same moment

Run:  python3 -m benchmarks.stress
"""

import math
import random
import time

from ridedispatch import Dispatcher, KDTree, RequestQueue, RideRequest
from ridedispatch.citygen import grid_city, random_nodes
from ridedispatch.fast_dispatcher import FastDispatcher
from ridedispatch.grid_index import GridIndex

from .common import save


def gps_storm():
    rng = random.Random(1)
    n, updates = 100_000, 1_000_000
    pts = {i: (rng.uniform(0, 40), rng.uniform(0, 40)) for i in range(n)}
    moves = []
    for _ in range(updates):
        i = rng.randrange(n)
        x, y = pts[i]
        pts[i] = (min(40, max(0, x + rng.uniform(-0.2, 0.2))),
                  min(40, max(0, y + rng.uniform(-0.2, 0.2))))
        moves.append((i, pts[i]))
    qs = [(rng.uniform(0, 40), rng.uniform(0, 40)) for _ in range(200)]
    want = [sorted(math.dist(p, q) for p in pts.values())[:5] for q in qs[:20]]
    out = {}
    for name, idx in (("kdtree", KDTree(pts.items())), ("grid", GridIndex(0.25, pts.items()))):
        t = time.perf_counter()
        for i, p in moves:
            idx.update(i, p)
        upd = time.perf_counter() - t
        t = time.perf_counter()
        got = [idx.nearest(q, 5) for q in qs]
        qry = (time.perf_counter() - t) / len(qs)
        ok = all(abs(a - b) < 1e-9 for g, w in zip(got, want) for (a, _), b in zip(g, w))
        out[name] = {"updates_s": upd, "us_per_update": upd / updates * 1e6,
                     "query_us_after": qry * 1e6, "rebuilds": idx.rebuilds, "correct": ok}
    return out


def cancel_flood():
    q = RequestQueue()
    n = 1_000_000
    t = time.perf_counter()
    for i in range(n):
        q.push(RideRequest(i, 0, float(i)))
        if i % 100:
            q.cancel(i)
    el = time.perf_counter() - t
    return {"requests": n, "live": len(q), "heap_entries": q.heap_size(),
            "purges": q.purges, "us_per_op": el / (2 * n) * 1e6,
            "first_pop": q.pop().request_id}


def same_spot():
    n = 20_000
    out = {}
    for name in ("kdtree_bulk", "kdtree_insert", "grid"):
        items = [(i, (5.0, 5.0)) for i in range(n)]
        t = time.perf_counter()
        if name == "kdtree_bulk":
            idx = KDTree(items)
        elif name == "grid":
            idx = GridIndex(1.0, items)
        else:
            idx = KDTree()
            for i, p in items[:5000]:        # O(n^2) inserts: cap at 5,000
                idx.insert(i, p)
        build = time.perf_counter() - t
        t = time.perf_counter()
        for _ in range(200):
            idx.nearest((5.0, 5.0), 5)
        out[name] = {"drivers": len(idx), "build_s": build,
                     "query_ms": (time.perf_counter() - t) / 200 * 1e3}
    return out


def unreachable():
    net = grid_city(100)                      # 10,000 intersections
    side = 20                                  # cut-off district, no drivers
    for r in range(side):
        for c in range(side):
            net.add_intersection(("cut", r, c), 30 + c * 0.2, 30 + r * 0.2)
    for r in range(side):
        for c in range(side):
            if c + 1 < side:
                net.add_road(("cut", r, c), ("cut", r, c + 1), 20)
            if r + 1 < side:
                net.add_road(("cut", r, c), ("cut", r + 1, c), 20)
    rng = random.Random(3)
    drivers = random_nodes(net, 500, seed=4)
    drivers = [d for d in drivers if not isinstance(d, tuple)]
    normal = random_nodes(net, 100, seed=5)
    normal = [n for n in normal if not isinstance(n, tuple)]
    out = {}
    for name, make in (("phase2", lambda: Dispatcher(net, candidates=5)),
                       ("phase3", lambda: FastDispatcher(net, candidates=5, router="astar"))):
        d = make()
        for i, n in enumerate(drivers):
            d.add_driver(i, n)
        for i in range(50):                    # cut-off requests arrive first
            d.submit_request(f"X{i}", ("cut", rng.randrange(side), rng.randrange(side)),
                             request_time=i)
        for i, n in enumerate(normal):
            d.submit_request(f"R{i}", n, request_time=100 + i)
        t = time.perf_counter()
        m = d.dispatch_all()
        out[name] = {"matched": len(m), "still_waiting": len(d.queue),
                     "seconds": time.perf_counter() - t}
    return out


def surge():
    net = grid_city(200)
    drivers = random_nodes(net, 2000, seed=6)
    stadium = 200 * 100 + 100
    out = {}
    for name, make in (("phase2", lambda: Dispatcher(net, candidates=5)),
                       ("grid+A*", lambda: FastDispatcher(net, router="astar")),
                       ("cached", lambda: FastDispatcher(net, router="cached"))):
        d = make()
        for i, n in enumerate(drivers):
            d.add_driver(i, n)
        for i in range(3000):
            d.submit_request(f"S{i}", stadium, request_time=0)
        t = time.perf_counter()
        m = d.dispatch_all()
        el = time.perf_counter() - t
        out[name] = {"matched": len(m), "seconds": el, "ms_per_match": el / len(m) * 1e3,
                     "mean_eta_s": sum(x.eta_seconds for x in m) / len(m)}
        if name == "cached":
            out[name]["hit_rate"] = d.cache.hits / (d.cache.hits + d.cache.misses)
    return out


def main():
    out = {}
    for name, fn in (("gps_storm", gps_storm), ("cancel_flood", cancel_flood),
                     ("same_spot", same_spot), ("unreachable", unreachable), ("surge", surge)):
        out[name] = fn()
        print(name, out[name])
    save("stress", out)


if __name__ == "__main__":
    main()
