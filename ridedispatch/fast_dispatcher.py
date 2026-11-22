"""Phase 3 optimized dispatcher.

Same public interface and the same invariant as the Phase 2 Dispatcher
(a driver is in the locator exactly when the registry marks it FREE), with
these changes:

1. Locator: uniform GridIndex by default (O(1) GPS updates) or the k-d tree.
2. Router: CompactGraph (CSR arrays, O(1)-reset scratch space) with a
   first-hit stop, using Dijkstra, A*, or the memoized RouteCache.
3. No repeated doubling of k when nobody is reachable: when a search runs
   out of roads, every node that can reach the pickup has been settled, so
   any free driver on one of those nodes is checked directly, once.
4. dispatch_all() sets unreachable requests aside for the whole round
   instead of re-trying them after every match.
5. dispatch_batch(): match a batch of requests at once with the Hungarian
   method to minimise the total pickup time (Xu et al., 2018).
"""

import math

from .compact_graph import CompactGraph
from .dispatcher import Dispatcher, Match
from .driver_registry import ASSIGNED, FREE
from .grid_index import GridIndex
from .hungarian import assign
from .kd_tree import KDTree
from .request_queue import URGENT
from .route_cache import RouteCache

ROUTERS = ("dijkstra", "astar", "cached")
URGENT_BONUS = 3600.0   # seconds; makes urgent rows win when drivers are scarce


class FastDispatcher(Dispatcher):
    def __init__(self, network, candidates=5, index="grid", router="dijkstra",
                 cell_km=1.0, cache_entries=256, cache_nodes=2_000_000):
        super().__init__(network, candidates)
        if index == "grid":
            self.locator = GridIndex(cell_km)
        elif index == "kdtree":
            self.locator = KDTree()
        else:
            raise ValueError("index must be 'grid' or 'kdtree'")
        if router not in ROUTERS:
            raise ValueError(f"router must be one of {ROUTERS}")
        self.router = router
        self.cache_entries = cache_entries
        self.cache_nodes = cache_nodes
        self._graph = None
        self._cache = None
        self.nodes_settled = 0          # total search work, for benchmarks

    # ---- compact graph kept in step with the road network ----------------
    @property
    def graph(self):
        if self._graph is None or self._graph.version != self.network.version:
            self._graph = CompactGraph(self.network)
            self._cache = RouteCache(self._graph, self.cache_entries, self.cache_nodes)
        return self._graph

    @property
    def cache(self):
        self.graph          # refresh if the network changed
        return self._cache

    def _nearest_by_road(self, pickup, nodes):
        """(best_node, seconds) among `nodes`, or (None, inf)."""
        g = self.graph
        if self.router == "cached":
            res = self._cache.nearest_target(pickup, nodes)
            self.nodes_settled += self._cache.last_settled
        else:
            res = g.nearest_target(pickup, nodes, reverse=True, method=self.router)
            self.nodes_settled += g.last_settled
        return res

    def _settled_after_exhaustion(self, pickup, node):
        if self.router == "cached":
            return self._cache.settled_time(pickup, node)
        return self.graph.settled_time(node)

    # ---- matching -----------------------------------------------------
    def _match(self, req):
        pickup = req.pickup_node
        nearby = self.locator.nearest(self.network.position(pickup), k=self.candidates)
        if not nearby:
            return None
        at_node = {}
        for _, d in nearby:                      # nearest straight-line first
            at_node.setdefault(self.drivers.get(d).node, d)
        node, eta = self._nearest_by_road(pickup, at_node)
        if node is not None:
            best = at_node[node]
        else:
            # The search ran out of roads: it settled every intersection
            # that can reach the pickup. Check all free drivers against
            # that set once instead of doubling k and searching again.
            best, eta = None, math.inf
            for drv in self.drivers:
                if drv.status == FREE:
                    t = self._settled_after_exhaustion(pickup, drv.node)
                    if t is not None and t < eta:
                        best, eta = drv.driver_id, t
            if best is None:
                return None
        self._assign(best)
        req.status = "assigned"
        return Match(req, best, eta, len(nearby))

    def _assign(self, driver_id):
        self.locator.remove(driver_id)
        self.drivers.set_status(driver_id, ASSIGNED)

    def dispatch_all(self):
        """Match until no more matches are possible.

        Free drivers only get fewer during the round, so a request that no
        free driver can reach now stays unreachable for the rest of it;
        it is set aside once instead of being searched after every match.
        """
        matches, skipped = [], []
        while len(self.queue) and len(self.locator):
            req = self.queue.pop()
            m = self._match(req)
            if m:
                matches.append(m)
            else:
                skipped.append(req)
        for req in skipped:
            self.queue.push(req)
        return matches

    # ---- batch matching (Hungarian method) ------------------------------
    def dispatch_batch(self, max_batch=100):
        """Match up to `max_batch` waiting requests together.

        Each request gets its k nearest free drivers as candidates; the
        exact road time from every candidate is the cost; the Hungarian
        method picks the assignment with the least total pickup time.
        Requests that are left without a driver go back in the queue with
        their original priority and arrival time.
        """
        if max_batch < 1:
            raise ValueError("max_batch must be at least 1")
        # Never take more requests than there are free drivers: the extra
        # ones cannot be served this round, and searching for them is the
        # main cost when drivers are scarce (rush hour).
        limit = min(max_batch, len(self.locator))
        batch = []
        while len(self.queue) and len(batch) < limit:
            batch.append(self.queue.pop())
        if not batch or not len(self.locator):
            for r in batch:
                self.queue.push(r)
            return []
        g = self.graph
        col_of, cols = {}, []
        rows = []
        for req in batch:
            nearby = self.locator.nearest(self.network.position(req.pickup_node),
                                          k=self.candidates)
            ids = [d for _, d in nearby]
            nodes = {self.drivers.get(d).node for d in ids}
            method = "astar" if self.router == "astar" else "dijkstra"
            times = g.travel_times(req.pickup_node, nodes, reverse=True, method=method)
            self.nodes_settled += g.last_settled
            row = {}
            for d in ids:
                if d not in col_of:
                    col_of[d] = len(cols)
                    cols.append(d)
                row[col_of[d]] = times[self.drivers.get(d).node]
            rows.append(row)
        cost = []
        for req, row in zip(batch, rows):
            bonus = -URGENT_BONUS if req.priority == URGENT else 0.0
            cost.append([row[j] + bonus if j in row and not math.isinf(row[j])
                         else math.inf for j in range(len(cols))])
        choice = assign(cost)
        matches = []
        for req, row, j in zip(batch, rows, choice):
            if j is None:
                self.queue.push(req)             # try again next batch
                continue
            self._assign(cols[j])
            req.status = "assigned"
            matches.append(Match(req, cols[j], row[j], len(row)))
        return matches
