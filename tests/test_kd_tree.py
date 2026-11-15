import random
import unittest

from ridedispatch import KDTree


def brute(points, q, k):
    d = sorted((((x - q[0]) ** 2 + (y - q[1]) ** 2) ** 0.5, key) for key, (x, y) in points.items())
    return d[:k]


class TestKDTree(unittest.TestCase):
    def setUp(self):
        rng = random.Random(42)
        self.points = {f"d{i}": (rng.uniform(0, 50), rng.uniform(0, 50)) for i in range(500)}

    def test_matches_brute_force(self):
        tree = KDTree(self.points.items())
        rng = random.Random(7)
        for _ in range(100):
            q = (rng.uniform(0, 50), rng.uniform(0, 50))
            k = rng.randint(1, 10)
            got = [round(d, 9) for d, _ in tree.nearest(q, k)]
            want = [round(d, 9) for d, _ in brute(self.points, q, k)]
            self.assertEqual(got, want)

    def test_insert_one_by_one_matches_brute_force(self):
        tree = KDTree()
        for key, p in self.points.items():
            tree.insert(key, p)
        got = [round(d, 9) for d, _ in tree.nearest((25, 25), 8)]
        want = [round(d, 9) for d, _ in brute(self.points, (25, 25), 8)]
        self.assertEqual(got, want)

    def test_remove_and_update(self):
        tree = KDTree(self.points.items())
        nearest_key = tree.nearest((10, 10), 1)[0][1]
        self.assertTrue(tree.remove(nearest_key))
        self.assertFalse(tree.remove(nearest_key))        # already gone
        self.assertNotIn(nearest_key, [k for _, k in tree.nearest((10, 10), 20)])
        tree.update("d1", (10.0, 10.0))
        self.assertEqual(tree.nearest((10, 10), 1), [(0.0, "d1")])
        self.assertEqual(len(tree), 499)

    def test_rebuild_after_many_deletes(self):
        tree = KDTree(self.points.items())
        keys = list(self.points)
        for key in keys[:300]:
            tree.remove(key)
        self.assertGreaterEqual(tree.rebuilds, 1)
        left = {k: self.points[k] for k in keys[300:]}
        got = [round(d, 9) for d, _ in tree.nearest((5, 5), 5)]
        want = [round(d, 9) for d, _ in brute(left, (5, 5), 5)]
        self.assertEqual(got, want)

    def test_empty_k_and_duplicates(self):
        tree = KDTree()
        self.assertEqual(tree.nearest((0, 0), 3), [])
        tree.insert("a", (1, 1))
        tree.insert("b", (1, 1))                           # same spot is fine
        self.assertEqual(len(tree.nearest((1, 1), 10)), 2) # k > size
        self.assertEqual(tree.nearest((1, 1), 0), [])
        with self.assertRaises(ValueError):
            tree.insert("a", (2, 2))                       # same key is not
        with self.assertRaises(KeyError):
            tree.update("zzz", (0, 0))

    def test_bad_points(self):
        tree = KDTree()
        with self.assertRaises(TypeError):
            tree.insert("a", (1,))
        with self.assertRaises(TypeError):
            tree.insert("a", ("x", 1))
        with self.assertRaises(ValueError):
            tree.insert("a", (float("nan"), 1))

    def test_deep_unbalanced_tree_no_recursion_error(self):
        tree = KDTree()
        for i in range(3000):                  # sorted inserts -> a long chain
            tree.insert(i, (i, i))
        self.assertEqual(tree.nearest((2999, 2999), 1)[0][1], 2999)


if __name__ == "__main__":
    unittest.main()
