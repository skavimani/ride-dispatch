# ride-dispatch — Phase 3 Optimization and Scaling

Data structures for a real-time ride-hailing dispatch system
(MSCS-532 Algorithms and Data Structures project, Soundarya Kavimani).

| Module | Data structure | Key operations |
|---|---|---|
| `ridedispatch/road_network.py` | Directed weighted graph (adjacency lists) | add road (one- or two-way), Dijkstra travel times with early exit, reverse search |
| `ridedispatch/kd_tree.py` | 2-D k-d tree | balanced build, insert, lazy delete, update, k-nearest search, auto-rebuild |
| `ridedispatch/request_queue.py` | Binary min-heap + dict | push, pop most urgent, peek, O(1) cancel, stale-entry purge |
| `ridedispatch/driver_registry.py` | Hash table (dict) | add, get, set status, remove, count |
| `ridedispatch/dispatcher.py` | Combines all four | add/move/offline drivers, submit/cancel requests, dispatch, complete trip |

### Phase 3 additions

| Module | What it adds |
|---|---|
| `ridedispatch/grid_index.py` | Uniform grid (bucket) driver index: O(1) GPS updates, ring-by-ring k-nearest search |
| `ridedispatch/compact_graph.py` | Road graph frozen into CSR arrays; O(1)-reset search state; first-hit stop; A* |
| `ridedispatch/route_cache.py` | LRU cache of paused (resumable) reverse-Dijkstra searches for hot-spot pickups |
| `ridedispatch/hungarian.py` | Hungarian method (min-cost assignment) for batch matching |
| `ridedispatch/fast_dispatcher.py` | `FastDispatcher`: same API as `Dispatcher`, uses all of the above + `dispatch_batch()` |
| `ridedispatch/citygen.py` | Seeded synthetic grid cities (one-way streets, arterials) up to ~100,000 intersections |
| `benchmarks/` | Index, routing, simulation and stress benchmarks; `make_charts.py` draws the figures |

The Phase 2 modules are kept unchanged (apart from a change counter in
`RoadNetwork`) so they serve as the baseline in every benchmark.

The package uses only the Python standard library (Python 3.8+).
The chart script additionally needs `matplotlib`.

## Run

```bash
python3 demo.py                          # full proof-of-concept walk-through
python3 match_one_request.py             # Phase 1 single-match example
python3 -m unittest discover tests -v    # 62 unit + stress tests

# Phase 3 benchmarks (results go to results/*.json)
python3 -m benchmarks.bench_index        # k-d tree vs grid      (~5 s)
python3 -m benchmarks.bench_routing      # ETA search methods    (~15 s)
python3 -m benchmarks.simulate           # 30-min dispatch sims  (~2 min)
python3 -m benchmarks.stress             # stress tests          (~2 min)
python3 -m benchmarks.make_charts        # figures -> results/*.png
```
