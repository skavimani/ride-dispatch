"""Benchmark 2: road-time (ETA) search per ride request, and graph memory.

Cities of 2,500 to ~100,000 intersections, at a busy density (one free
driver per 25 intersections) and a sparse, late-night density (one per
400), 1,000 requests (60% at 20 hot spots). Every method gets the
same 5 straight-line candidates per request and must return the candidate
with the smallest road time:

  phase2      RoadNetwork.travel_times_from (dict graph, waits for all 5)
  csr_all     CompactGraph, still waits for all 5 (isolates the CSR effect)
  csr_first   CompactGraph + first-hit stop (Dijkstra)
  astar       CompactGraph + first-hit stop + A*
  cached      RouteCache (memoized, resumable first-hit Dijkstra)

Run:  python3 -m benchmarks.bench_routing
"""

import math
import time

from ridedispatch.citygen import grid_city, random_nodes, hotspot_nodes
from ridedispatch.compact_graph import CompactGraph
from ridedispatch.grid_index import GridIndex
from ridedispatch.route_cache import RouteCache

from .common import save, memory_of

SIDES = (50, 100, 200, 316)
REQUESTS = 1000


def main():
    out = {}
    for per in (25, 400):
        out[per] = bench(per)
    save("routing", out)


def bench(per):
    out = {}
    for side in SIDES:
        net = grid_city(side)
        V = len(net)
        t = time.perf_counter()
        g = CompactGraph(net)
        freeze_s = time.perf_counter() - t
        drivers = random_nodes(net, V // per, seed=side)
        idx = GridIndex(1.0, ((i, net.position(n)) for i, n in enumerate(drivers)))
        pickups = hotspot_nodes(net, REQUESTS, seed=side)
        jobs = []
        for p in pickups:
            near = idx.nearest(net.position(p), 5)
            jobs.append((p, {drivers[i] for _, i in near}))
        res = {"V": V, "E": net.edge_count(), "drivers": len(drivers), "freeze_s": freeze_s}
        answers = {}

        def timed(name, fn, settled):
            t0 = time.perf_counter()
            ans, work = [], 0
            for p, nodes in jobs:
                ans.append(fn(p, nodes))
                work += settled()
            res[name] = {"ms": (time.perf_counter() - t0) / REQUESTS * 1e3,
                         "settled": work / REQUESTS}
            answers[name] = ans

        timed("phase2", lambda p, n: min(net.travel_times_from(p, targets=n, reverse=True).values()),
              lambda: 0)
        timed("csr_all", lambda p, n: min(g.travel_times(p, n).values()), lambda: g.last_settled)
        res["phase2"]["settled"] = res["csr_all"]["settled"]   # same algorithm, same work
        timed("csr_first", lambda p, n: g.nearest_target(p, n)[1], lambda: g.last_settled)
        timed("astar", lambda p, n: g.nearest_target(p, n, method="astar")[1], lambda: g.last_settled)
        cache = RouteCache(g, max_entries=256)
        timed("cached", lambda p, n: cache.nearest_target(p, n)[1], lambda: cache.last_settled)
        res["cached"]["hit_rate"] = cache.hits / (cache.hits + cache.misses)
        res["cached"]["nodes_held"] = cache.nodes_held()
        # all methods must agree with the Phase 2 answer
        ref = answers["phase2"]
        res["all_agree"] = all(
            all(abs(a - b) < 1e-6 or (math.isinf(a) and math.isinf(b)) for a, b in zip(ref, answers[m]))
            for m in answers)
        res["mem_dict_mb"] = memory_of(lambda: grid_city(side)) / 1e6
        res["mem_csr_mb"] = memory_of(lambda: CompactGraph(net)) / 1e6
        out[side] = res
        print(per, side, V, {k: (round(v["ms"], 3), round(v["settled"])) if isinstance(v, dict) else v
                        for k, v in res.items()})
    return out


if __name__ == "__main__":
    main()
