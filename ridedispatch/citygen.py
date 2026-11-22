"""Synthetic cities and workloads for Phase 3 scaling tests.

grid_city(side) builds a side x side street grid (side**2 intersections):
* blocks of `block_km`, with each intersection nudged a little at random,
* every 5th street is a faster arterial (50 km/h vs. about 30 km/h),
* every 4th east-west street is one-way, alternating east/west like
  Manhattan, so the graph stays strongly connected.
Travel time on a road = length / speed. Everything is seeded, so the same
arguments always give the same city.
"""

import math
import random

from .road_network import RoadNetwork


def grid_city(side, block_km=0.2, seed=0, one_way_every=4):
    if side < 2:
        raise ValueError("side must be at least 2")
    rng = random.Random(seed)
    net = RoadNetwork()
    for r in range(side):
        for c in range(side):
            x = c * block_km + rng.uniform(-0.15, 0.15) * block_km
            y = r * block_km + rng.uniform(-0.15, 0.15) * block_km
            net.add_intersection(r * side + c, x, y)

    def seconds(u, v, arterial):
        (ux, uy), (vx, vy) = net.position(u), net.position(v)
        kmh = 50.0 if arterial else rng.uniform(24.0, 36.0)
        return math.hypot(vx - ux, vy - uy) / kmh * 3600.0

    for r in range(side):
        one_way = one_way_every and r % one_way_every == one_way_every // 2
        eastbound = (r // one_way_every) % 2 == 0 if one_way else None
        for c in range(side):
            u = r * side + c
            if c + 1 < side:                       # east-west street
                v = u + 1
                s = seconds(u, v, r % 5 == 0)
                if one_way:
                    a, b = (u, v) if eastbound else (v, u)
                    net.add_road(a, b, s, two_way=False)
                else:
                    net.add_road(u, v, s)
            if r + 1 < side:                       # north-south street
                v = u + side
                net.add_road(u, v, seconds(u, v, c % 5 == 0))
    return net


def random_nodes(net, n, seed=1):
    rng = random.Random(seed)
    nodes = list(net._pos)
    return [rng.choice(nodes) for _ in range(n)]


def hotspot_nodes(net, n, hotspots=20, hot_share=0.6, seed=2):
    """Request pickups: `hot_share` of them at a few busy intersections."""
    rng = random.Random(seed)
    nodes = list(net._pos)
    hot = rng.sample(nodes, min(hotspots, len(nodes)))
    return [rng.choice(hot) if rng.random() < hot_share else rng.choice(nodes)
            for _ in range(n)]
