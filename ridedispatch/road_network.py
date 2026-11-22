"""Road network: weighted directed graph stored as adjacency lists.

Intersections are nodes with (x, y) coordinates in kilometres; road segments
are edges weighted by travel time in seconds. Phase 2 change: roads may be
one-way, so the graph keeps a forward and a reverse adjacency list.
"""

import heapq
import math

from .exceptions import UnknownNodeError


class RoadNetwork:
    """Directed, weighted graph with Dijkstra shortest travel times."""

    def __init__(self):
        self._pos = {}        # node -> (x, y)
        self._out = {}        # node -> {neighbour: seconds}  (forward roads)
        self._in = {}         # node -> {neighbour: seconds}  (reverse roads)
        self.version = 0      # Phase 3: bumped on every change so cached
                              # compact copies know when to refresh

    # ---- building the graph -------------------------------------------
    def add_intersection(self, node, x, y):
        """Add (or move) an intersection at coordinates (x, y)."""
        if not all(isinstance(v, (int, float)) for v in (x, y)):
            raise TypeError("coordinates must be numbers")
        self._pos[node] = (float(x), float(y))
        self.version += 1
        self._out.setdefault(node, {})
        self._in.setdefault(node, {})

    def add_road(self, u, v, seconds, two_way=True):
        """Add a road u -> v taking `seconds` (and v -> u if two_way)."""
        self._check(u)
        self._check(v)
        if not isinstance(seconds, (int, float)) or math.isnan(seconds):
            raise TypeError("travel time must be a number")
        if seconds < 0:
            raise ValueError("travel time cannot be negative (Dijkstra needs >= 0)")
        if u == v:
            raise ValueError("a road must join two different intersections")
        self._set_edge(u, v, seconds)
        if two_way:
            self._set_edge(v, u, seconds)

    def _set_edge(self, u, v, seconds):
        # keep the faster road if the same segment is added twice
        if seconds < self._out[u].get(v, math.inf):
            self._out[u][v] = seconds
            self._in[v][u] = seconds
            self.version += 1

    # ---- queries ------------------------------------------------------
    def position(self, node):
        """Return the (x, y) coordinates of an intersection."""
        self._check(node)
        return self._pos[node]

    def __contains__(self, node):
        return node in self._pos

    def __len__(self):
        return len(self._pos)

    def edge_count(self):
        return sum(len(n) for n in self._out.values())

    def travel_times_from(self, source, targets=None, reverse=False):
        """Dijkstra's algorithm from `source`.

        reverse=False: seconds to drive source -> every node.
        reverse=True : seconds to drive every node -> source (search runs on
                       the reversed graph, so one-way streets are respected).
        If `targets` is given the search stops once all of them are settled
        (early exit). Unreachable targets get math.inf.
        """
        self._check(source)
        adj = self._in if reverse else self._out
        remaining = None
        if targets is not None:
            remaining = set(targets)
            for t in remaining:
                self._check(t)
        dist = {source: 0.0}
        done = set()
        heap = [(0.0, source)]
        while heap:
            d, node = heapq.heappop(heap)
            if node in done:
                continue                      # stale heap entry
            done.add(node)
            if remaining is not None:
                remaining.discard(node)
                if not remaining:
                    break                     # every target settled
            for nxt, w in adj[node].items():
                nd = d + w
                if nd < dist.get(nxt, math.inf):
                    dist[nxt] = nd
                    heapq.heappush(heap, (nd, nxt))
        if targets is None:
            return dist
        return {t: (dist[t] if t in done else math.inf) for t in targets}

    def _check(self, node):
        if node not in self._pos:
            raise UnknownNodeError(f"unknown intersection: {node!r}")
