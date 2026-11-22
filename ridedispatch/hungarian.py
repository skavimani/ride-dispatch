"""Minimum-cost assignment with the Hungarian method (Kuhn, 1955).

Shortest-augmenting-path version with row/column potentials, O(n^2 * m)
for an n x m cost matrix with n <= m (each row gets a distinct column).
Used for batch matching: rows are waiting requests, columns are candidate
drivers, cost is the pickup time in seconds.
"""

import math


def assign(cost):
    """Return a list `col_of_row`: column assigned to each row, minimising
    the total cost. Pairs with infinite cost are reported as None.

    If there are more rows than columns, some rows get None.
    """
    n = len(cost)
    if n == 0:
        return []
    m = len(cost[0])
    if any(len(row) != m for row in cost):
        raise ValueError("cost matrix must be rectangular")
    if m == 0:
        return [None] * n
    if n > m:                                   # solve the transpose
        t = [[cost[i][j] for i in range(n)] for j in range(m)]
        row_of_col = assign(t)
        out = [None] * n
        for j, i in enumerate(row_of_col):
            if i is not None:
                out[i] = j
        return out
    # replace "impossible" (inf) with a big finite value, drop them later
    finite = [c for row in cost for c in row if not math.isinf(c)]
    if any(math.isnan(c) for c in finite):
        raise ValueError("cost matrix cannot contain NaN")
    big = (max((abs(c) for c in finite), default=0.0) + 1.0) * (n + 1)
    a = [[big if math.isinf(c) else c for c in row] for row in cost]

    INF = math.inf
    u = [0.0] * (n + 1)          # row potentials (1-based)
    v = [0.0] * (m + 1)          # column potentials
    p = [0] * (m + 1)            # p[j] = row matched to column j (0 = none)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            row = a[i0 - 1]
            ui0 = u[i0]
            for j in range(1, m + 1):
                if not used[j]:
                    cur = row[j - 1] - ui0 - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:                              # augment along the path
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    out = [None] * n
    for j in range(1, m + 1):
        if p[j]:
            i = p[j] - 1
            if not math.isinf(cost[i][j - 1]):
                out[i] = j - 1
    return out
