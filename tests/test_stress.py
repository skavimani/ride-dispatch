"""Scaled-down stress tests (the full-size runs are in benchmarks/stress.py)."""

import math
import random
import time
import unittest

from ridedispatch import KDTree, RequestQueue, RideRequest
from ridedispatch.citygen import grid_city, random_nodes
from ridedispatch.fast_dispatcher import FastDispatcher
from ridedispatch.grid_index import GridIndex


class TestStress(unittest.TestCase):
    def test_gps_storm_keeps_indexes_correct(self):
        rng = random.Random(11)
        pts = {i: (rng.uniform(0, 30), rng.uniform(0, 30)) for i in range(2000)}
        kd, grid = KDTree(pts.items()), GridIndex(1.0, pts.items())
        for _ in range(20000):
            i = rng.randrange(2000)
            x, y = pts[i]
            pts[i] = (min(30, max(0, x + rng.uniform(-0.3, 0.3))),
                      min(30, max(0, y + rng.uniform(-0.3, 0.3))))
            kd.update(i, pts[i])
            grid.update(i, pts[i])
        self.assertGreater(kd.rebuilds, 0)
        for _ in range(30):
            q = (rng.uniform(0, 30), rng.uniform(0, 30))
            want = sorted(math.dist(p, q) for p in pts.values())[:5]
            for idx in (kd, grid):
                got = [d for d, _ in idx.nearest(q, 5)]
                for a, b in zip(got, want):
                    self.assertAlmostEqual(a, b, places=9)

    def test_all_drivers_on_one_spot(self):
        g = GridIndex(1.0)
        kd = KDTree()
        for i in range(3000):
            g.insert(i, (5.0, 5.0))
            kd.insert(i, (5.0, 5.0))
        self.assertEqual(len(g.nearest((5, 5), 10)), 10)
        self.assertEqual(len(kd.nearest((5, 5), 10)), 10)

    def test_mass_cancellation_keeps_heap_small(self):
        q = RequestQueue()
        for i in range(20000):
            q.push(RideRequest(f"R{i}", 0, i))
        for i in range(20000):
            if i % 100:
                q.cancel(f"R{i}")
        self.assertEqual(len(q), 200)
        self.assertLess(q.heap_size(), 3 * 200 + 20)
        self.assertEqual(q.pop().request_id, "R0")

    def test_many_unreachable_requests_do_not_slow_the_round(self):
        net = grid_city(30)
        net.add_intersection("island", -9, -9)
        d = FastDispatcher(net, candidates=5)
        for i, n in enumerate(random_nodes(net, 300, seed=1)):
            d.add_driver(i, n)
        for i in range(500):
            d.submit_request(f"X{i}", "island")
        for i, n in enumerate(random_nodes(net, 250, seed=2)):
            d.submit_request(f"R{i}", n)
        start = time.perf_counter()
        self.assertEqual(len(d.dispatch_all()), 250)
        self.assertLess(time.perf_counter() - start, 5.0)
        self.assertEqual(len(d.queue), 500)

    def test_drivers_outnumber_nothing(self):
        d = FastDispatcher(grid_city(10))
        for i in range(50):
            d.submit_request(f"R{i}", i)
        self.assertEqual(d.dispatch_all(), [])
        self.assertEqual(d.dispatch_batch(), [])
        self.assertEqual(len(d.queue), 50)


if __name__ == "__main__":
    unittest.main()
