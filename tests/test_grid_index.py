import math
import random
import unittest

from ridedispatch.grid_index import GridIndex


def brute(points, q, k):
    return sorted((math.dist(p, q), key) for key, p in points.items())[:k]


class TestGridIndex(unittest.TestCase):
    def assert_same(self, got, want):
        self.assertEqual(len(got), len(want))
        for (dg, _), (dw, _) in zip(got, want):
            self.assertAlmostEqual(dg, dw, places=9)

    def test_matches_brute_force(self):
        rng = random.Random(7)
        pts = {f"d{i}": (rng.uniform(0, 20), rng.uniform(0, 20)) for i in range(500)}
        g = GridIndex(cell_km=1.0, items=pts.items())
        for _ in range(100):
            q = (rng.uniform(-2, 22), rng.uniform(-2, 22))
            for k in (1, 5, 20):
                self.assert_same(g.nearest(q, k), brute(pts, q, k))

    def test_matches_brute_force_after_many_updates(self):
        rng = random.Random(8)
        pts = {f"d{i}": (rng.uniform(0, 10), rng.uniform(0, 10)) for i in range(300)}
        g = GridIndex(cell_km=0.5, items=pts.items())
        for _ in range(3000):                         # GPS updates
            key = rng.choice(list(pts))
            pts[key] = (rng.uniform(0, 10), rng.uniform(0, 10))
            g.update(key, pts[key])
        for key in list(pts)[:100]:                   # drivers taken
            g.remove(key)
            del pts[key]
        for _ in range(50):
            q = (rng.uniform(0, 10), rng.uniform(0, 10))
            self.assert_same(g.nearest(q, 7), brute(pts, q, 7))

    def test_far_away_query_and_k_larger_than_size(self):
        g = GridIndex(0.1, items=[("a", (0, 0)), ("b", (1, 1))])
        self.assertEqual([k for _, k in g.nearest((500, 500), k=10)], ["b", "a"])

    def test_edge_cases(self):
        g = GridIndex(1.0)
        self.assertEqual(g.nearest((0, 0), 3), [])
        g.insert("a", (0, 0))
        self.assertEqual(g.nearest((0, 0), 0), [])
        with self.assertRaises(ValueError):
            g.insert("a", (1, 1))                     # duplicate
        with self.assertRaises(KeyError):
            g.update("zz", (1, 1))
        self.assertFalse(g.remove("zz"))
        with self.assertRaises(ValueError):
            g.insert("n", (float("nan"), 0))
        with self.assertRaises(TypeError):
            g.insert("t", "oops")
        for bad in (0, -1, float("inf"), "1"):
            with self.assertRaises(ValueError):
                GridIndex(bad)

    def test_empty_cells_are_freed(self):
        g = GridIndex(1.0)
        for i in range(100):
            g.insert(i, (i, i))
        self.assertEqual(g.occupied_cells(), 100)
        for i in range(100):
            g.update(i, (0.5, 0.5))                   # all into one cell
        self.assertEqual(g.occupied_cells(), 1)
        for i in range(100):
            g.remove(i)
        self.assertEqual((len(g), g.occupied_cells()), (0, 0))

    def test_negative_coordinates(self):
        g = GridIndex(1.0, items=[("a", (-3.5, -0.2)), ("b", (2, 2))])
        self.assertEqual(g.nearest((-3, 0), 1)[0][1], "a")


if __name__ == "__main__":
    unittest.main()
