import unittest

from ridedispatch import Dispatcher, RoadNetwork, DispatchError, UnknownNodeError, FREE, ASSIGNED
from ridedispatch.request_queue import URGENT


def small_city():
    """Phase 1 test city: 5 intersections, 6 two-way roads."""
    net = RoadNetwork()
    for n, x, y in [("A", 0, 0), ("B", 1, 0), ("C", 2, 0), ("D", 0, 1), ("E", 2, 1)]:
        net.add_intersection(n, x, y)
    for u, v, s in [("A", "B", 60), ("B", "C", 120), ("A", "D", 240),
                    ("B", "D", 300), ("C", "E", 90), ("D", "E", 400)]:
        net.add_road(u, v, s)
    return net


class TestDispatcher(unittest.TestCase):
    def setUp(self):
        self.d = Dispatcher(small_city(), candidates=2)
        self.d.add_driver("Driver-1", "D")
        self.d.add_driver("Driver-2", "C")
        self.d.add_driver("Driver-3", "E")

    def assert_invariant(self):
        """A driver is in the k-d tree exactly when its status is FREE."""
        for drv in self.d.drivers:
            self.assertEqual(drv.driver_id in self.d.locator, drv.status == FREE)

    def test_picks_lowest_road_eta_not_straight_line(self):
        self.d.submit_request("R1", "A")
        self.d.submit_request("R2", "B", priority=URGENT)
        m = self.d.dispatch_next()
        self.assertEqual((m.request.request_id, m.driver_id, m.eta_seconds), ("R2", "Driver-2", 120))
        self.assertEqual(self.d.drivers.get("Driver-2").status, ASSIGNED)
        self.assert_invariant()

    def test_full_trip_lifecycle(self):
        self.d.submit_request("R1", "B")
        m = self.d.dispatch_next()
        self.d.complete_trip(m.driver_id, "A")
        drv = self.d.drivers.get(m.driver_id)
        self.assertEqual((drv.status, drv.node, drv.trips_completed), (FREE, "A", 1))
        self.assert_invariant()
        with self.assertRaises(DispatchError):
            self.d.complete_trip(m.driver_id, "A")       # not on a trip now

    def test_cancelled_request_never_matched(self):
        self.d.submit_request("R1", "A")
        self.d.cancel_request("R1")
        self.assertIsNone(self.d.dispatch_next())
        self.assertEqual(len(self.d.locator), 3)

    def test_move_and_offline(self):
        self.d.move_driver("Driver-1", "A")
        self.d.go_offline("Driver-2")
        self.d.go_offline("Driver-3")
        self.d.submit_request("R1", "B")
        self.assertEqual(self.d.dispatch_next().driver_id, "Driver-1")
        self.d.go_online("Driver-3")
        self.assert_invariant()

    def test_no_free_drivers_request_waits(self):
        for drv in ["Driver-1", "Driver-2", "Driver-3"]:
            self.d.go_offline(drv)
        self.d.submit_request("R1", "A")
        self.assertIsNone(self.d.dispatch_next())
        self.assertEqual(len(self.d.queue), 1)

    def test_unreachable_request_does_not_block_queue(self):
        self.d.network.add_intersection("Island", 5, 5)
        self.d.submit_request("R-island", "Island", priority=URGENT)
        self.d.submit_request("R-normal", "A")
        m = self.d.dispatch_next()
        self.assertEqual(m.request.request_id, "R-normal")
        self.assertIn("R-island", self.d.queue)            # kept, not lost

    def test_widens_search_when_candidates_unreachable(self):
        net = small_city()
        net.add_intersection("F", 0.1, 0.1)                # close but cut off
        d = Dispatcher(net, candidates=1)
        d.add_driver("cut-off", "F")
        d.add_driver("far", "E")
        d.submit_request("R1", "A")
        m = d.dispatch_next()
        self.assertEqual(m.driver_id, "far")
        self.assertGreater(m.candidates_checked, 1)

    def test_one_way_street_changes_choice(self):
        net = RoadNetwork()
        for n, x in [("W", 0), ("P", 1), ("E1", 2), ("E2", 3)]:
            net.add_intersection(n, x, 0)
        net.add_road("P", "W", 60, two_way=False)          # westbound only
        net.add_road("E1", "P", 60, two_way=False)
        net.add_road("E2", "E1", 60, two_way=False)
        d = Dispatcher(net, candidates=3)
        d.add_driver("west", "W")                          # 1 km, cannot reach P
        d.add_driver("east", "E2")                         # 2 km, 120 s
        d.submit_request("R", "P")
        m = d.dispatch_next()
        self.assertEqual((m.driver_id, m.eta_seconds), ("east", 120))

    def test_bad_inputs(self):
        with self.assertRaises(UnknownNodeError):
            self.d.submit_request("R", "nowhere")
        with self.assertRaises(UnknownNodeError):
            self.d.add_driver("new", "nowhere")
        with self.assertRaises(ValueError):
            Dispatcher(small_city(), candidates=0)
        self.d.submit_request("R", "A")
        self.d.dispatch_next()
        busy = [x.driver_id for x in self.d.drivers if x.status == ASSIGNED][0]
        with self.assertRaises(DispatchError):
            self.d.go_offline(busy)

    def test_dispatch_all_matches_until_drivers_run_out(self):
        for i, node in enumerate("ABCDE"):
            self.d.submit_request(f"R{i}", node)
        matches = self.d.dispatch_all()
        self.assertEqual(len(matches), 3)
        self.assertEqual(len(self.d.queue), 2)
        self.assertEqual(len({m.driver_id for m in matches}), 3)   # no double-booking
        self.assert_invariant()


if __name__ == "__main__":
    unittest.main()
