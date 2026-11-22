import unittest

from ridedispatch import Dispatcher, RoadNetwork, DispatchError, FREE
from ridedispatch.citygen import grid_city, random_nodes, hotspot_nodes
from ridedispatch.fast_dispatcher import FastDispatcher
from ridedispatch.request_queue import URGENT

from tests.test_dispatcher import small_city

CONFIGS = [(i, r) for i in ("grid", "kdtree") for r in ("dijkstra", "astar", "cached")]


def fill(d, drivers, requests):
    for i, n in enumerate(drivers):
        d.add_driver(f"D{i}", n)
    for i, n in enumerate(requests):
        d.submit_request(f"R{i}", n, request_time=i)


class TestFastDispatcher(unittest.TestCase):
    def assert_invariant(self, d):
        for drv in d.drivers:
            self.assertEqual(drv.driver_id in d.locator, drv.status == FREE)

    def test_same_matches_as_phase2_for_every_config(self):
        net = grid_city(40, seed=9)
        drivers, requests = random_nodes(net, 150, seed=9), hotspot_nodes(net, 120, seed=9)
        base = Dispatcher(net, candidates=5)
        fill(base, drivers, requests)
        want = [(m.request.request_id, m.driver_id, round(m.eta_seconds, 6))
                for m in base.dispatch_all()]
        for index, router in CONFIGS:
            with self.subTest(index=index, router=router):
                d = FastDispatcher(net, candidates=5, index=index, router=router, cell_km=0.5)
                fill(d, drivers, requests)
                got = [(m.request.request_id, m.driver_id, round(m.eta_seconds, 6))
                       for m in d.dispatch_all()]
                self.assertEqual(got, want)
                self.assert_invariant(d)

    def test_phase2_scenarios_still_hold(self):
        for index, router in CONFIGS:
            d = FastDispatcher(small_city(), candidates=2, index=index, router=router)
            for name, node in [("Driver-1", "D"), ("Driver-2", "C"), ("Driver-3", "E")]:
                d.add_driver(name, node)
            d.submit_request("R1", "A")
            d.submit_request("R2", "B", priority=URGENT)
            m = d.dispatch_next()
            self.assertEqual((m.request.request_id, m.driver_id, m.eta_seconds),
                             ("R2", "Driver-2", 120))

    def test_unreachable_candidates_fall_back_to_reachable_driver(self):
        net = small_city()
        net.add_intersection("F", 0.1, 0.1)                 # close but cut off
        d = FastDispatcher(net, candidates=1, router="astar")
        d.add_driver("cut-off", "F")
        d.add_driver("far", "E")
        d.submit_request("R1", "A")
        self.assertEqual(d.dispatch_next().driver_id, "far")

    def test_unreachable_requests_set_aside_once_per_round(self):
        net = grid_city(20)
        net.add_intersection("island", -5, -5)
        d = FastDispatcher(net, candidates=3)
        for i in range(10):
            d.add_driver(f"D{i}", i * 30)
        for i in range(20):
            d.submit_request(f"X{i}", "island", priority=URGENT)
        for i in range(10):
            d.submit_request(f"R{i}", 200 + i)
        matches = d.dispatch_all()
        self.assertEqual(len(matches), 10)
        self.assertEqual(len(d.queue), 20)                  # islands kept, not lost

    def test_network_change_refreshes_compact_graph(self):
        net = small_city()
        d = FastDispatcher(net, candidates=3)
        d.add_driver("x", "E")
        d.submit_request("R1", "A")
        g1 = d.graph
        net.add_intersection("G", 3, 3)
        net.add_road("G", "A", 10)
        self.assertIsNot(d.graph, g1)
        d.add_driver("y", "G")
        self.assertEqual(d.dispatch_next().driver_id, "y")

    def test_batch_never_worse_than_greedy_and_no_double_booking(self):
        net = grid_city(40, seed=3)
        drivers, requests = random_nodes(net, 120, seed=4), random_nodes(net, 80, seed=5)
        greedy = FastDispatcher(net, candidates=6)
        batch = FastDispatcher(net, candidates=6)
        fill(greedy, drivers, requests)
        fill(batch, drivers, requests)
        g = greedy.dispatch_all()
        b = batch.dispatch_batch(max_batch=80)
        self.assertEqual(len({m.driver_id for m in b}), len(b))
        self.assertEqual(len(b), 80)
        self.assertLessEqual(sum(m.eta_seconds for m in b),
                             sum(m.eta_seconds for m in g) + 1e-6)
        self.assert_invariant(batch)

    def test_batch_prefers_urgent_when_drivers_are_scarce(self):
        d = FastDispatcher(small_city(), candidates=3)
        d.add_driver("only", "C")
        d.submit_request("std", "B", request_time=0)
        d.submit_request("urg", "E", priority=URGENT, request_time=5)
        m = d.dispatch_batch()
        self.assertEqual([x.request.request_id for x in m], ["urg"])
        self.assertIn("std", d.queue)

    def test_batch_edge_cases(self):
        d = FastDispatcher(small_city())
        self.assertEqual(d.dispatch_batch(), [])
        d.submit_request("R", "A")
        self.assertEqual(d.dispatch_batch(), [])            # no drivers
        self.assertIn("R", d.queue)
        with self.assertRaises(ValueError):
            d.dispatch_batch(max_batch=0)

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            FastDispatcher(small_city(), index="quadtree")
        with self.assertRaises(ValueError):
            FastDispatcher(small_city(), router="bfs")
        d = FastDispatcher(small_city())
        d.add_driver("a", "A")
        d.submit_request("R", "B")
        d.dispatch_next()
        with self.assertRaises(DispatchError):
            d.go_offline("a")


if __name__ == "__main__":
    unittest.main()
