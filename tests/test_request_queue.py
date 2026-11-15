import unittest

from ridedispatch import RequestQueue, RideRequest, UnknownRequestError, DuplicateRequestError


class TestRequestQueue(unittest.TestCase):
    def test_priority_then_fifo(self):
        q = RequestQueue()
        q.push(RideRequest("late-standard", "A", 5, 1))
        q.push(RideRequest("early-standard", "A", 1, 1))
        q.push(RideRequest("urgent", "A", 9, 0))
        self.assertEqual([q.pop().request_id for _ in range(3)],
                         ["urgent", "early-standard", "late-standard"])

    def test_same_time_ties_use_insertion_order(self):
        q = RequestQueue()
        for rid in ["x", "y", "z"]:
            q.push(RideRequest(rid, "A", 0))
        self.assertEqual([q.pop().request_id for _ in range(3)], ["x", "y", "z"])

    def test_cancel_is_skipped(self):
        q = RequestQueue()
        q.push(RideRequest("r1", "A", 1, 0))
        q.push(RideRequest("r2", "A", 2))
        req = q.cancel("r1")
        self.assertEqual(req.status, "cancelled")
        self.assertEqual(len(q), 1)
        self.assertEqual(q.peek().request_id, "r2")
        self.assertEqual(q.pop().request_id, "r2")
        with self.assertRaises(IndexError):
            q.pop()

    def test_purge_keeps_heap_small(self):
        q = RequestQueue()
        for i in range(1000):
            q.push(RideRequest(f"r{i}", "A", i))
        for i in range(990):
            q.cancel(f"r{i}")
        self.assertGreaterEqual(q.purges, 1)
        self.assertLess(q.heap_size(), 60)
        self.assertEqual(q.pop().request_id, "r990")

    def test_errors(self):
        q = RequestQueue()
        self.assertIsNone(q.peek())
        with self.assertRaises(UnknownRequestError):
            q.cancel("nope")
        q.push(RideRequest("r", "A", 0))
        with self.assertRaises(DuplicateRequestError):
            q.push(RideRequest("r", "A", 1))
        with self.assertRaises(ValueError):
            q.push(RideRequest("bad", "A", 0, priority=-1))
        with self.assertRaises(TypeError):
            q.push("not a request")


if __name__ == "__main__":
    unittest.main()
