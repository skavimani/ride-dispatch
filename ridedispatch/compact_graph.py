"""Compact, integer-indexed copy of the road network for fast searches (Phase 3).

Phase 2 stored the graph as a dict of dicts keyed by intersection name and
built a new `dist` dict and `done` set for every search. This module freezes
the graph into compressed sparse row (CSR) arrays: node i's roads are
targets[offsets[i]:offsets[i+1]] with matching weights. Nodes are numbered
0..V-1, so per-search state lives in flat lists that are never cleared:
a "stamp" number marks which entries belong to the current search, giving
an O(1) reset instead of O(V).

Two search optimizations sit on top:

* First-hit stop.  The dispatcher only needs the candidate driver who can
  reach the rider soonest. Dijkstra settles nodes in order of travel time,
  so the first candidate settled is the answer and the search stops there,
  instead of waiting for the farthest (or an unreachable) candidate.
* A* (Hart, Nilsson & Raphael, 1968).  h(v) = straight-line distance from v
  to the nearest candidate x the fewest seconds per km on any road. This
  never over-estimates, and the minimum of consistent heuristics is
  consistent, so the first target popped is still the true nearest.
"""

import heapq
import math
from array import array

from .exceptions import UnknownNodeError


class CompactGraph:
    def __init__(self, network):
        ids = list(network._pos)
        index = {node: i for i, node in enumerate(ids)}
        self.ids = ids
        self.index = index
        self.version = getattr(network, "version", None)
        n = len(ids)
        self.xs = array("d", (network._pos[v][0] for v in ids))
        self.ys = array("d", (network._pos[v][1] for v in ids))
        self.fwd = self._csr(network._out, ids, index)
        self.rev = self._csr(network._in, ids, index)
        # A* scale: fewest seconds needed per straight-line km on any road
        spk = math.inf
        for u, nbrs in network._out.items():
            ux, uy = network._pos[u]
            for v, w in nbrs.items():
                vx, vy = network._pos[v]
                km = math.hypot(vx - ux, vy - uy)
                if km > 0:
                    spk = min(spk, w / km)
        self.sec_per_km = 0.0 if math.isinf(spk) else spk
        # per-search scratch space, reused across searches (stamp trick)
        self._dist = [math.inf] * n
        self._seen = [0] * n        # == stamp -> dist entry is valid
        self._done = [0] * n        # == stamp -> node settled
        self._stamp = 0
        self.last_settled = 0       # nodes settled by the last search

    @staticmethod
    def _csr(adj, ids, index):
        offsets = array("l", [0])
        targets = array("l")
        weights = array("d")
        for node in ids:
            for nbr, w in adj[node].items():
                targets.append(index[nbr])
                weights.append(w)
            offsets.append(len(targets))
        return offsets, targets, weights

    def __len__(self):
        return len(self.ids)

    def node_index(self, node):
        try:
            return self.index[node]
        except KeyError:
            raise UnknownNodeError(f"unknown intersection: {node!r}") from None

    # ---- searches -------------------------------------------------------
    def nearest_target(self, source, targets, reverse=True, method="dijkstra"):
        """Search from `source` until the first node in `targets` is settled.

        reverse=True gives the time to drive from each target TO source.
        Returns (target_node, seconds). If no target is reachable returns
        (None, inf) and the settled set of the exhausted search can be read
        with settled_time() until the next search.
        """
        src = self.node_index(source)
        goal = {self.node_index(t) for t in targets}
        found, d = self._search(src, goal, reverse, method, first_hit=True)
        if found is None:
            return None, math.inf
        return self.ids[found], d

    def travel_times(self, source, targets, reverse=True, method="dijkstra"):
        """Exact times for every target (inf if unreachable); stops when all settled."""
        src = self.node_index(source)
        goal = {self.node_index(t) for t in targets}
        self._search(src, set(goal), reverse, method, first_hit=False)
        out = {}
        for t in targets:
            i = self.index[t]
            out[t] = self._dist[i] if self._done[i] == self._stamp else math.inf
        return out

    def settled_time(self, node):
        """Travel time of `node` if the last search settled it, else None."""
        i = self.index.get(node)
        if i is None or self._done[i] != self._stamp:
            return None
        return self._dist[i]

    def _search(self, src, goal, reverse, method, first_hit):
        offsets, targets, weights = self.rev if reverse else self.fwd
        self._stamp += 1
        stamp = self._stamp
        dist, seen, done = self._dist, self._seen, self._done
        use_astar = method == "astar" and self.sec_per_km > 0 and goal
        if method not in ("dijkstra", "astar"):
            raise ValueError("method must be 'dijkstra' or 'astar'")
        if use_astar:
            xs, ys, spk = self.xs, self.ys, self.sec_per_km
            gx = [xs[g] for g in goal]
            gy = [ys[g] for g in goal]
            pts = list(zip(gx, gy))

            def h(v):
                x, y = xs[v], ys[v]
                return spk * min(math.hypot(px - x, py - y) for px, py in pts)
        dist[src] = 0.0
        seen[src] = stamp
        heap = [(h(src) if use_astar else 0.0, 0.0, src)]
        settled = 0
        remaining = len(goal)
        while heap:
            _, d, u = heapq.heappop(heap)
            if done[u] == stamp:
                continue                    # stale heap entry
            done[u] = stamp
            settled += 1
            if u in goal:
                if first_hit:
                    self.last_settled = settled
                    return u, d
                remaining -= 1
                if remaining == 0:
                    break
            for j in range(offsets[u], offsets[u + 1]):
                v = targets[j]
                nd = d + weights[j]
                if seen[v] != stamp or nd < dist[v]:
                    dist[v] = nd
                    seen[v] = stamp
                    heapq.heappush(heap, (nd + h(v) if use_astar else nd, nd, v))
        self.last_settled = settled
        return None, math.inf
