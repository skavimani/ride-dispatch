import math
import random
import unittest

from ridedispatch import RoadNetwork, UnknownNodeError
from ridedispatch.citygen import grid_city
from ridedispatch.compact_graph import CompactGraph
from ridedispatch.route_cache import RouteCache


def random_network(n=150, roads=450, seed=0):
    rng = random.Random(seed)
    net = RoadNetwork()
    for i in range(n):
        net.add_intersection(i, rng.uniform(0, 10), rng.uniform(0, 10))
    for _ in range(roads):
        u, v = rng.sample(range(n), 2)
        km = math.dist(net.position(u), net.position(v))
        net.add_road(u, v, km * rng.uniform(80, 200), two_way=rng.random() < 0.6)
    return net


class TestCompactGraph(unittest.TestCase):
    def test_same_times_as_phase2_dijkstra(self):
        for seed in range(5):
            net = random_network(seed=seed)
            g = CompactGraph(net)
            rng = random.Random(seed)
            for _ in range(40):
                s = rng.randrange(150)
                ts = rng.sample(range(150), 6)
                for rev in (True, False):
                    want = net.travel_times_from(s, targets=ts, reverse=rev)
                    for method in ("dijkstra", "astar"):
                        got = g.travel_times(s, ts, reverse=rev, method=method)
                        for t in ts:
                            self.assertAlmostEqual(got[t], want[t], places=6)

    def test_first_hit_is_the_nearest_for_dijkstra_and_astar(self):
        net = grid_city(30, seed=4)
        g = CompactGraph(net)
        rng = random.Random(4)
        for _ in range(100):
            s = rng.randrange(900)
            ts = rng.sample(range(900), 5)
            best = min(net.travel_times_from(s, targets=ts, reverse=True).values())
            for method in ("dijkstra", "astar"):
                node, t = g.nearest_target(s, ts, method=method)
                self.assertAlmostEqual(t, best, places=6)

    def test_astar_settles_fewer_nodes(self):
        g = CompactGraph(grid_city(60, seed=1))
        g.nearest_target(0, [3599], method="dijkstra")
        dij = g.last_settled
        g.nearest_target(0, [3599], method="astar")
        self.assertLess(g.last_settled, dij)

    def test_unreachable_and_exhausted_search(self):
        net = random_network(seed=2)
        net.add_intersection("island", 50, 50)
        g = CompactGraph(net)
        self.assertEqual(g.nearest_target(0, ["island"]), (None, math.inf))
        self.assertIsNone(g.settled_time("island"))
        self.assertEqual(g.settled_time(0), 0.0)       # source is settled
        self.assertEqual(g.travel_times(0, ["island"])["island"], math.inf)

    def test_bad_inputs(self):
        g = CompactGraph(random_network())
        with self.assertRaises(UnknownNodeError):
            g.nearest_target("nope", [1])
        with self.assertRaises(UnknownNodeError):
            g.travel_times(1, ["nope"])
        with self.assertRaises(ValueError):
            g.nearest_target(0, [1], method="bfs")

    def test_stamp_reset_between_searches(self):
        g = CompactGraph(grid_city(20))
        for _ in range(3):                             # same answer each time
            self.assertAlmostEqual(g.nearest_target(0, [399])[1],
                                   g.travel_times(0, [399])[399])


class TestRouteCache(unittest.TestCase):
    def test_cached_answers_equal_fresh_search(self):
        net = grid_city(30, seed=2)
        g = CompactGraph(net)
        cache = RouteCache(g, max_entries=8)
        rng = random.Random(2)
        hot = [5, 77, 450]
        for _ in range(300):
            s = rng.choice(hot)
            ts = rng.sample(range(900), 5)
            want = min(net.travel_times_from(s, targets=ts, reverse=True).values())
            self.assertAlmostEqual(cache.nearest_target(s, ts)[1], want, places=6)
        self.assertGreater(cache.hits, 0)

    def test_limits_are_respected(self):
        g = CompactGraph(grid_city(30))
        cache = RouteCache(g, max_entries=3, max_nodes=400)
        for s in range(0, 900, 37):
            cache.nearest_target(s, [899])
            self.assertLessEqual(len(cache), 3)
        self.assertGreater(cache.evictions, 0)
        self.assertLessEqual(cache.nodes_held(), 400 + 900)   # one entry may exceed
        with self.assertRaises(ValueError):
            RouteCache(g, max_entries=0)

    def test_unreachable_target(self):
        net = random_network()
        net.add_intersection("island", 99, 99)
        cache = RouteCache(CompactGraph(net))
        self.assertEqual(cache.nearest_target(0, ["island"]), (None, math.inf))
        self.assertTrue(cache.exhausted(0))
        self.assertEqual(cache.nearest_target(0, ["island"]), (None, math.inf))


if __name__ == "__main__":
    unittest.main()
