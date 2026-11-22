import itertools
import math
import random
import unittest

from ridedispatch.hungarian import assign


def brute_best(cost):
    """(pairs matched, total cost) of the best assignment, by brute force."""
    n, m = len(cost), len(cost[0])
    best = (-1, math.inf)
    if n <= m:
        for cols in itertools.permutations(range(m), n):
            pairs = [(i, j) for i, j in enumerate(cols) if not math.isinf(cost[i][j])]
            cand = (len(pairs), sum(cost[i][j] for i, j in pairs))
            if cand[0] > best[0] or (cand[0] == best[0] and cand[1] < best[1] - 1e-9):
                best = cand
    else:
        t = [[cost[i][j] for i in range(n)] for j in range(m)]
        return brute_best(t)
    return best


def score(cost, choice):
    pairs = [(i, j) for i, j in enumerate(choice) if j is not None]
    return len(pairs), sum(cost[i][j] for i, j in pairs)


class TestHungarian(unittest.TestCase):
    def test_matches_brute_force(self):
        rng = random.Random(3)
        for _ in range(300):
            n, m = rng.randint(1, 6), rng.randint(1, 6)
            cost = [[math.inf if rng.random() < 0.2 else rng.uniform(0, 900)
                     for _ in range(m)] for _ in range(n)]
            choice = assign(cost)
            used = [j for j in choice if j is not None]
            self.assertEqual(len(used), len(set(used)))        # no driver twice
            got, want = score(cost, choice), brute_best(cost)
            self.assertEqual(got[0], want[0])
            self.assertAlmostEqual(got[1], want[1], places=6)

    def test_beats_greedy_example(self):
        # greedy row-by-row takes (0,0)=1 then (1,1)=100 -> 101; optimum is 2 + 3 = 5
        cost = [[1, 2], [3, 100]]
        self.assertEqual(assign(cost), [1, 0])

    def test_edge_cases(self):
        self.assertEqual(assign([]), [])
        self.assertEqual(assign([[], []]), [None, None])
        self.assertEqual(assign([[math.inf]]), [None])
        with self.assertRaises(ValueError):
            assign([[1, 2], [3]])
        with self.assertRaises(ValueError):
            assign([[float("nan")]])


if __name__ == "__main__":
    unittest.main()
