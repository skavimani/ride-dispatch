"""Waiting ride requests: binary min-heap + hash table (Williams, 1964).

Heap entries are keyed (priority, request_time, seq): lower priority number
is more urgent; ties go to the earlier request (FIFO). Cancellation removes
the request from the dict in O(1); its heap entry is skipped when it surfaces
(lazy deletion). Phase 2: stale entries are purged when they outnumber live
ones, so memory stays O(live requests).
"""

import heapq
import itertools
from dataclasses import dataclass

from .exceptions import UnknownRequestError, DuplicateRequestError

URGENT = 0
STANDARD = 1


@dataclass
class RideRequest:
    request_id: str
    pickup_node: object
    request_time: float
    priority: int = STANDARD
    status: str = "waiting"      # waiting | assigned | cancelled


class RequestQueue:
    def __init__(self):
        self._heap = []
        self._live = {}                  # request_id -> (entry, RideRequest)
        self._seq = itertools.count()
        self.purges = 0

    def __len__(self):
        return len(self._live)

    def __contains__(self, request_id):
        return request_id in self._live

    def push(self, req):
        """Add a waiting request in O(log n)."""
        if not isinstance(req, RideRequest):
            raise TypeError("push() expects a RideRequest")
        if req.request_id in self._live:
            raise DuplicateRequestError(f"request already waiting: {req.request_id!r}")
        if not isinstance(req.priority, int) or req.priority < 0:
            raise ValueError("priority must be a non-negative integer")
        entry = [req.priority, req.request_time, next(self._seq), req.request_id]
        self._live[req.request_id] = (entry, req)
        req.status = "waiting"
        heapq.heappush(self._heap, entry)

    def cancel(self, request_id):
        """Cancel a waiting request in O(1) (lazy deletion)."""
        try:
            entry, req = self._live.pop(request_id)
        except KeyError:
            raise UnknownRequestError(f"no waiting request {request_id!r}") from None
        entry[-1] = None                 # mark heap entry as stale
        req.status = "cancelled"
        if len(self._heap) > 2 * len(self._live) + 16:
            self._purge()
        return req

    def peek(self):
        """Most urgent waiting request without removing it (None if empty)."""
        self._drop_stale_top()
        return self._live[self._heap[0][-1]][1] if self._heap else None

    def pop(self):
        """Remove and return the most urgent request. IndexError if empty."""
        self._drop_stale_top()
        if not self._heap:
            raise IndexError("pop from an empty request queue")
        entry = heapq.heappop(self._heap)
        _, req = self._live.pop(entry[-1])
        return req

    def _drop_stale_top(self):
        while self._heap and self._heap[0][-1] is None:
            heapq.heappop(self._heap)

    def _purge(self):
        self._heap = [e for e in self._heap if e[-1] is not None]
        heapq.heapify(self._heap)
        self.purges += 1

    def heap_size(self):
        """Entries physically in the heap (live + not-yet-purged stale)."""
        return len(self._heap)
