"""Uniform grid (bucket) index of free drivers -- Phase 3 alternative to the k-d tree.

The city is cut into square cells of `cell_km` kilometres. Each cell is a
hash-table bucket holding the drivers inside it, so a GPS update is O(1):
remove the driver from one bucket and add it to another. A k-nearest query
searches rings of cells outward from the query point and stops as soon as
the next ring cannot hold anyone closer than the current k-th best
(the cell method of Bentley, Weide & Yao, 1980).

It has the same interface as KDTree, so the dispatcher can use either.
"""

import heapq
import math

from .kd_tree import KDTree


class GridIndex:
    """Bucket grid keyed by driver id. Each key appears at most once."""

    def __init__(self, cell_km=1.0, items=None):
        if not isinstance(cell_km, (int, float)) or not cell_km > 0 or math.isinf(cell_km):
            raise ValueError("cell_km must be a positive, finite number")
        self.cell = float(cell_km)
        self._cells = {}        # (cx, cy) -> {key: (x, y)}
        self._where = {}        # key -> (cx, cy)
        self._pos = {}          # key -> (x, y)
        self.rebuilds = 0       # kept for interface parity with KDTree
        if items:
            self.build(items)

    # ---- size ---------------------------------------------------------
    def __len__(self):
        return len(self._pos)

    def __contains__(self, key):
        return key in self._pos

    # ---- construction / updates ----------------------------------------
    def build(self, items):
        """Replace the contents with (key, (x, y)) pairs."""
        cells, where, pos = {}, {}, {}
        for key, point in items:
            if key in pos:
                raise ValueError(f"duplicate key: {key!r}")
            point = KDTree._clean(point)
            c = self._cell_of(point)
            cells.setdefault(c, {})[key] = point
            where[key] = c
            pos[key] = point
        self._cells, self._where, self._pos = cells, where, pos

    def insert(self, key, point):
        """Add a key in O(1). Raises ValueError if the key is already present."""
        if key in self._pos:
            raise ValueError(f"duplicate key: {key!r}")
        point = KDTree._clean(point)
        c = self._cell_of(point)
        self._cells.setdefault(c, {})[key] = point
        self._where[key] = c
        self._pos[key] = point

    def remove(self, key):
        """Delete a key in O(1). Returns False if the key is not present."""
        c = self._where.pop(key, None)
        if c is None:
            return False
        del self._pos[key]
        bucket = self._cells[c]
        del bucket[key]
        if not bucket:
            del self._cells[c]          # empty cells use no memory
        return True

    def update(self, key, point):
        """GPS update in O(1): move an existing key to a new point."""
        if key not in self._pos:
            raise KeyError(key)
        point = KDTree._clean(point)
        new_c = self._cell_of(point)
        old_c = self._where[key]
        if new_c != old_c:
            bucket = self._cells[old_c]
            del bucket[key]
            if not bucket:
                del self._cells[old_c]
            self._where[key] = new_c
        self._cells.setdefault(new_c, {})[key] = point
        self._pos[key] = point

    # ---- search ---------------------------------------------------------
    def nearest(self, point, k=1):
        """Return up to k (distance, key) pairs closest to `point`, nearest first."""
        if k <= 0 or not self._pos:
            return []
        qx, qy = KDTree._clean(point)
        cx, cy = self._cell_of((qx, qy))
        cell = self.cell
        cells = self._cells
        best = []                       # max-heap of (-d2, key)
        seen = 0
        total = len(self._pos)
        r = 0
        while True:
            if 8 * r > len(cells):
                # Ring has more cells than the whole grid holds: scanning
                # every occupied cell is cheaper (also bounds the worst case
                # when the query point is far outside the drivers' area).
                return self._scan_rest(qx, qy, cx, cy, r, k, best)
            for c in self._ring(cx, cy, r):
                bucket = cells.get(c)
                if not bucket:
                    continue
                seen += len(bucket)
                for key, (x, y) in bucket.items():
                    d2 = (x - qx) ** 2 + (y - qy) ** 2
                    if len(best) < k:
                        heapq.heappush(best, (-d2, key))
                    elif d2 < -best[0][0]:
                        heapq.heapreplace(best, (-d2, key))
            if seen >= total:
                break
            # every point in ring r+1 or beyond is at least r*cell away
            if len(best) >= k and (r * cell) ** 2 >= -best[0][0]:
                break
            r += 1
        return sorted(((-nd2) ** 0.5, key) for nd2, key in best)

    def _scan_rest(self, qx, qy, cx, cy, r, k, best):
        """Scan all occupied cells at Chebyshev ring >= r."""
        for (x0, y0), bucket in self._cells.items():
            if max(abs(x0 - cx), abs(y0 - cy)) < r:
                continue                # already examined
            for key, (x, y) in bucket.items():
                d2 = (x - qx) ** 2 + (y - qy) ** 2
                if len(best) < k:
                    heapq.heappush(best, (-d2, key))
                elif d2 < -best[0][0]:
                    heapq.heapreplace(best, (-d2, key))
        return sorted(((-nd2) ** 0.5, key) for nd2, key in best)

    @staticmethod
    def _ring(cx, cy, r):
        if r == 0:
            yield (cx, cy)
            return
        for dx in range(-r, r + 1):
            yield (cx + dx, cy - r)
            yield (cx + dx, cy + r)
        for dy in range(-r + 1, r):
            yield (cx - r, cy + dy)
            yield (cx + r, cy + dy)

    def _cell_of(self, point):
        return (math.floor(point[0] / self.cell), math.floor(point[1] / self.cell))

    def occupied_cells(self):
        return len(self._cells)
