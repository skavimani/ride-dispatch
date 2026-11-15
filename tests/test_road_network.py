import math
import unittest

from ridedispatch import RoadNetwork, UnknownNodeError


def triangle():
    net = RoadNetwork()
    for n, x, y in [("A", 0, 0), ("B", 1, 0), ("C", 2, 0)]:
        net.add_intersection(n, x, y)
    net.add_road("A", "B", 60)
    net.add_road("B", "C", 60)
    net.add_road("A", "C", 500)
    return net


class TestRoadNetwork(unittest.TestCase):
    def test_shortest_path_prefers_cheaper_route(self):
        self.assertEqual(triangle().travel_times_from("A")["C"], 120)

    def test_unreachable_node_is_infinite(self):
        net = triangle()
        net.add_intersection("Z", 9, 9)
        self.assertEqual(net.travel_times_from("A", targets=["Z"])["Z"], math.inf)

    def test_one_way_road_respected_in_both_directions(self):
        net = RoadNetwork()
        net.add_intersection("A", 0, 0)
        net.add_intersection("B", 1, 0)
        net.add_road("A", "B", 30, two_way=False)
        self.assertEqual(net.travel_times_from("A", targets=["B"])["B"], 30)
        self.assertEqual(net.travel_times_from("B", targets=["A"])["A"], math.inf)
        # reverse search from B: who can drive TO B?  A can.
        self.assertEqual(net.travel_times_from("B", targets=["A"], reverse=True)["A"], 30)

    def test_early_exit_matches_full_search(self):
        net = triangle()
        full = net.travel_times_from("A")
        part = net.travel_times_from("A", targets=["B"])
        self.assertEqual(part["B"], full["B"])

    def test_duplicate_road_keeps_faster_time(self):
        net = triangle()
        net.add_road("A", "C", 10)
        self.assertEqual(net.travel_times_from("A")["C"], 10)

    def test_bad_inputs(self):
        net = triangle()
        with self.assertRaises(ValueError):
            net.add_road("A", "B", -1)
        with self.assertRaises(ValueError):
            net.add_road("A", "A", 5)
        with self.assertRaises(TypeError):
            net.add_road("A", "B", "fast")
        with self.assertRaises(UnknownNodeError):
            net.add_road("A", "Q", 5)
        with self.assertRaises(UnknownNodeError):
            net.travel_times_from("Q")
        with self.assertRaises(TypeError):
            net.add_intersection("X", "a", 0)


if __name__ == "__main__":
    unittest.main()
