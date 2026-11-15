# ride-dispatch — Phase 2 Proof of Concept

Data structures for a real-time ride-hailing dispatch system
(MSCS-532 Algorithms and Data Structures project, Soundarya Kavimani).

| Module | Data structure | Key operations |
|---|---|---|
| `ridedispatch/road_network.py` | Directed weighted graph (adjacency lists) | add road (one- or two-way), Dijkstra travel times with early exit, reverse search |
| `ridedispatch/kd_tree.py` | 2-D k-d tree | balanced build, insert, lazy delete, update, k-nearest search, auto-rebuild |
| `ridedispatch/request_queue.py` | Binary min-heap + dict | push, pop most urgent, peek, O(1) cancel, stale-entry purge |
| `ridedispatch/driver_registry.py` | Hash table (dict) | add, get, set status, remove, count |
| `ridedispatch/dispatcher.py` | Combines all four | add/move/offline drivers, submit/cancel requests, dispatch, complete trip |

Only the Python standard library is used (Python 3.8+).

## Run

```bash
python3 demo.py                          # full proof-of-concept walk-through
python3 match_one_request.py             # Phase 1 single-match example
python3 -m unittest discover tests -v    # 30 unit tests
```
