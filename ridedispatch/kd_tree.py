"""Two-dimensional k-d tree of free drivers (Bentley, 1975).

Supports balanced bulk build, insert, lazy delete, location update and
k-nearest-neighbour search with branch-and-bound pruning
(Friedman, Bentley & Finkel, 1977).
"""

import heapq
import math


class _Node:
    __slots__ = ("point", "key", "axis", "left", "right", "deleted")

    def __init__(self, point, key, axis):
        self.point = point
        self.key = key
        self.axis = axis
        self.left = None
        self.right = None
        self.deleted = False


class KDTree:
    """k-d tree keyed by driver id. Each key appears at most once."""

    def __init__(self, items=None):
        self._root = None
        self._nodes = {}        # key -> live node (O(1) lookup for delete)
        self._dead = 0          # deleted nodes still in the tree
        self.rebuilds = 0       # how many times the tree was rebuilt
        if items:
            self.build(items)

    # ---- size ---------------------------------------------------------
    def __len__(self):
        return len(self._nodes)

    def __contains__(self, key):
        return key in self._nodes

    # ---- construction -------------------------------------------------
    def build(self, items):
        """Build a balanced tree from (key, (x, y)) pairs by median split."""
        pts = []
        seen = set()
        for key, point in items:
            if key in seen:
                raise ValueError(f"duplicate key: {key!r}")
            seen.add(key)
            pts.append((self._clean(point), key))
        self._nodes = {}
        self._dead = 0
        self._root = self._build(pts, 0)

    def _build(self, pts, depth):
        if not pts:
            return None
        axis = depth % 2
        pts.sort(key=lambda p: p[0][axis])
        mid = len(pts) // 2
        point, key = pts[mid]
        node = _Node(point, key, axis)
        self._nodes[key] = node
        node.left = self._build(pts[:mid], depth + 1)
        node.right = self._build(pts[mid + 1:], depth + 1)
        return node

    # ---- updates ------------------------------------------------------
    def insert(self, key, point):
        """Add a new key at point. Raises ValueError if key already present."""
        if key in self._nodes:
            raise ValueError(f"duplicate key: {key!r}")
        point = self._clean(point)
        if self._root is None:
            self._root = self._nodes[key] = _Node(point, key, 0)
            return
        node = self._root
        while True:
            go_left = point[node.axis] < node.point[node.axis]
            child = node.left if go_left else node.right
            if child is None:
                new = _Node(point, key, 1 - node.axis)
                if go_left:
                    node.left = new
                else:
                    node.right = new
                self._nodes[key] = new
                return
            node = child

    def remove(self, key):
        """Lazily delete key in O(1). Returns False if key is not present."""
        node = self._nodes.pop(key, None)
        if node is None:
            return False
        node.deleted = True
        self._dead += 1
        if self._dead > len(self._nodes):
            self._rebuild()
        return True

    def update(self, key, point):
        """Move an existing key to a new point (delete + insert)."""
        if key not in self._nodes:
            raise KeyError(key)
        self.remove(key)
        self.insert(key, point)

    def _rebuild(self):
        live = [(k, n.point) for k, n in self._nodes.items()]
        self.build(live)
        self.rebuilds += 1

    # ---- search -------------------------------------------------------
    def nearest(self, point, k=1):
        """Return up to k (distance, key) pairs closest to `point`.

        Keeps a max-heap of the best k found so far and skips any subtree
        that cannot contain a closer point (branch-and-bound pruning).
        """
        if k <= 0 or self._root is None:
            return []
        point = self._clean(point)
        best = []   # max-heap via negated squared distance
        stack = [self._root]   # iterative: no recursion limit on deep trees
        # each stack item is a node or a (node, diff) "maybe visit far side"
        while stack:
            item = stack.pop()
            if isinstance(item, tuple):
                far, diff = item
                if far is not None and (len(best) < k or diff * diff < -best[0][0]):
                    stack.append(far)
                continue
            node = item
            if not node.deleted:
                d2 = (node.point[0] - point[0]) ** 2 + (node.point[1] - point[1]) ** 2
                if len(best) < k:
                    heapq.heappush(best, (-d2, node.key))
                elif d2 < -best[0][0]:
                    heapq.heapreplace(best, (-d2, node.key))
            diff = point[node.axis] - node.point[node.axis]
            near, far = (node.left, node.right) if diff < 0 else (node.right, node.left)
            stack.append((far, diff))        # checked after near side is done
            if near is not None:
                stack.append(near)
        return sorted(((-nd2) ** 0.5, key) for nd2, key in best)

    @staticmethod
    def _clean(point):
        try:
            x, y = point
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            raise TypeError("point must be an (x, y) pair of numbers") from None
        if math.isnan(x) or math.isnan(y):
            raise ValueError("point coordinates cannot be NaN")
        return (x, y)
