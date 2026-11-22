"""Memoized, resumable reverse-Dijkstra searches (Phase 3 caching).

Ride requests cluster at hot spots (stations, airports, venues), so the
same pickup intersection is searched again and again. The road graph does
not change between requests, so a Dijkstra search from a pickup can be
paused and kept: everything it settled already has its exact travel time.

For the next request at the same pickup the cache first looks among the
settled nodes. Dijkstra settles nodes in increasing time, so if any
candidate is already settled, the smallest settled candidate is the true
nearest and no graph work is needed (a cache hit). Otherwise the paused
search resumes from where it stopped.

Memory is bounded two ways: at most `max_entries` pickups are kept, and
the total settled nodes across all entries stays under `max_nodes`; the
least recently used entry is evicted first (an LRU policy).
"""

import heapq
import math
from collections import OrderedDict


class _Search:
    __slots__ = ("dist", "heap", "settled")

    def __init__(self, src):
        self.dist = {src: 0.0}     # best known time (settled or frontier)
        self.heap = [(0.0, src)]
        self.settled = {}          # node index -> exact seconds


class RouteCache:
    def __init__(self, graph, max_entries=256, max_nodes=2_000_000):
        if max_entries < 1 or max_nodes < 1:
            raise ValueError("cache limits must be positive")
        self.graph = graph
        self.max_entries = max_entries
        self.max_nodes = max_nodes
        self._lru = OrderedDict()   # source index -> _Search
        self._nodes = 0             # settled nodes held in all entries
        self.hits = self.misses = self.evictions = 0
        self.last_settled = 0       # new nodes settled by the last query

    def __len__(self):
        return len(self._lru)

    def nodes_held(self):
        return self._nodes

    def nearest_target(self, source, targets):
        """Like CompactGraph.nearest_target(reverse=True), but memoized."""
        g = self.graph
        src = g.node_index(source)
        goal = {g.node_index(t) for t in targets}
        s = self._lru.get(src)
        if s is None:
            s = _Search(src)
            self._lru[src] = s
        else:
            self._lru.move_to_end(src)
        # 1) answer from what is already settled?
        best, best_d = None, math.inf
        for t in goal:
            d = s.settled.get(t)
            if d is not None and d < best_d:
                best, best_d = t, d
        self.last_settled = 0
        if best is not None:
            self.hits += 1
            return g.ids[best], best_d
        self.misses += 1
        # 2) resume the paused search until a candidate is settled
        offsets, tgts, wts = g.rev
        dist, heap, settled = s.dist, s.heap, s.settled
        found = None
        new = 0
        while heap:
            d, u = heapq.heappop(heap)
            if u in settled:
                continue
            settled[u] = d
            new += 1
            for j in range(offsets[u], offsets[u + 1]):
                v = tgts[j]
                nd = d + wts[j]
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
            if u in goal:
                found = u
                break
        self.last_settled = new
        self._nodes += new
        self._evict(keep=src)
        if found is None:
            return None, math.inf
        return g.ids[found], settled[found]

    def settled_time(self, source, node):
        """Exact time from node to source if the cached search settled it."""
        s = self._lru.get(self.graph.index.get(source))
        i = self.graph.index.get(node)
        if s is None or i is None:
            return None
        return s.settled.get(i)

    def exhausted(self, source):
        s = self._lru.get(self.graph.index.get(source))
        return s is not None and not s.heap

    def _evict(self, keep):
        while (len(self._lru) > self.max_entries or self._nodes > self.max_nodes) \
                and len(self._lru) > 1:
            src, s = next(iter(self._lru.items()))
            if src == keep:
                self._lru.move_to_end(src)
                continue
            del self._lru[src]
            self._nodes -= len(s.settled)
            self.evictions += 1

    def clear(self):
        self._lru.clear()
        self._nodes = 0
