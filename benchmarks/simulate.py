"""Benchmark 3: time-stepped dispatch simulation, Phase 2 vs Phase 3.

Every 10 simulated seconds:
  1. GPS: each free driver moves to a neighbouring intersection with p = 0.5;
  2. new ride requests arrive (Poisson; 60% at 20 hot spots, 10% urgent);
  3. the dispatcher matches waiting requests (greedy, or a Hungarian batch);
  4. trips finish (pickup time + 5-20 min ride) and drivers become free.

Configurations
  phase2   Dispatcher: k-d tree + dict-graph Dijkstra waiting for all k
  grid+A*  FastDispatcher(index="grid", router="astar"), greedy
  cached   FastDispatcher(index="grid", router="cached"), greedy
  batch    FastDispatcher(index="grid", router="astar") + dispatch_batch()

Run:  python3 -m benchmarks.simulate
"""

import math
import random
import time

from ridedispatch import Dispatcher
from ridedispatch.citygen import grid_city
from ridedispatch.fast_dispatcher import FastDispatcher
from ridedispatch.request_queue import URGENT, STANDARD

from .common import save

TICK = 10.0
CONFIGS = {
    "phase2": lambda net: Dispatcher(net, candidates=5),
    "grid+A*": lambda net: FastDispatcher(net, candidates=5, index="grid", router="astar"),
    "cached": lambda net: FastDispatcher(net, candidates=5, index="grid", router="cached"),
    "batch": lambda net: FastDispatcher(net, candidates=5, index="grid", router="astar"),
}


def poisson(rng, lam):
    # Knuth's method; fine for the small per-tick rates used here
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def run(name, net, n_drivers, minutes, req_per_min, seed=1):
    d = CONFIGS[name](net)
    nodes = list(net._pos)
    out_nbrs = {u: list(v) for u, v in net._out.items()}
    rng_place = random.Random(seed)
    for i in range(n_drivers):
        d.add_driver(f"D{i}", rng_place.choice(nodes))
    hot = random.Random(seed + 1).sample(nodes, 20)
    rng_gps, rng_req, rng_trip = (random.Random(seed + s) for s in (2, 3, 4))
    finishing = []                       # (time, driver_id, dropoff)
    t_gps = t_dispatch = 0.0
    n_updates = 0
    etas, waits, submitted, rid = [], [], 0, 0
    ticks = int(minutes * 60 / TICK)
    lam = req_per_min * TICK / 60.0
    for step in range(ticks):
        now = step * TICK
        # 4) finished trips (done first so freed drivers can be matched)
        still = []
        for f in finishing:
            if f[0] <= now:
                d.complete_trip(f[1], f[2])
            else:
                still.append(f)
        finishing = still
        # 1) GPS updates of free drivers
        moves = []
        for drv in d.drivers:
            if drv.status == "free" and rng_gps.random() < 0.5:
                nb = out_nbrs[drv.node]
                if nb:
                    moves.append((drv.driver_id, rng_gps.choice(nb)))
        t0 = time.perf_counter()
        for did, node in moves:
            d.move_driver(did, node)
        t_gps += time.perf_counter() - t0
        n_updates += len(moves)
        # 2) new requests
        for _ in range(poisson(rng_req, lam)):
            node = rng_req.choice(hot) if rng_req.random() < 0.6 else rng_req.choice(nodes)
            pr = URGENT if rng_req.random() < 0.1 else STANDARD
            d.submit_request(f"R{rid}", node, priority=pr, request_time=now)
            rid += 1
            submitted += 1
        # 3) matching
        t0 = time.perf_counter()
        if name == "batch":
            matches = []
            while len(d.queue) and len(d.locator):
                got = d.dispatch_batch(max_batch=100)
                if not got:
                    break
                matches += got
        else:
            matches = d.dispatch_all()
        t_dispatch += time.perf_counter() - t0
        for m in matches:
            etas.append(m.eta_seconds)
            waits.append(now - m.request.request_time)
            ride = rng_trip.uniform(300, 1200)
            finishing.append((now + m.eta_seconds + ride, m.driver_id, rng_trip.choice(nodes)))
    etas.sort()
    matched = len(etas)
    return {
        "submitted": submitted, "matched": matched, "left_waiting": len(d.queue),
        "dispatch_ms_per_match": t_dispatch / max(1, matched) * 1e3,
        "dispatch_s": t_dispatch, "gps_us_per_update": t_gps / max(1, n_updates) * 1e6,
        "gps_updates": n_updates, "mean_eta_s": sum(etas) / max(1, matched),
        "p95_eta_s": etas[int(0.95 * (matched - 1))] if etas else 0.0,
        "mean_queue_wait_s": sum(waits) / max(1, len(waits)),
        "nodes_settled": getattr(d, "nodes_settled", None),
        "cache_hit_rate": (d.cache.hits / max(1, d.cache.hits + d.cache.misses))
        if name == "cached" else None,
    }


def main():
    out = {"scale": {}, "detail": {}}
    # (a) progressively larger cities: 1 driver per 20 intersections
    for side in (50, 100, 200, 316):
        net = grid_city(side)
        V = len(net)
        drivers = V // 20
        rpm = drivers * 0.06                 # demand ~ 75% of fleet capacity
        out["scale"][side] = {"V": V, "drivers": drivers, "req_per_min": rpm}
        for name in ("phase2", "grid+A*"):
            r = run(name, net, drivers, 10, rpm)
            out["scale"][side][name] = r
            print("scale", side, name, {k: round(v, 3) if isinstance(v, float) else v
                                       for k, v in r.items()})
    # (b) 40,000-intersection city, 30 minutes, normal demand and rush hour
    net = grid_city(200)
    for label, rpm in (("normal", 80), ("rush", 160)):   # ~70% and ~140% of capacity
        out["detail"][label] = {}
        for name in CONFIGS:
            r = run(name, net, 2000, 30, rpm)
            out["detail"][label][name] = r
            print(label, name, {k: round(v, 3) if isinstance(v, float) else v
                                for k, v in r.items()})
    save("simulation", out)


if __name__ == "__main__":
    main()
