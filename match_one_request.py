"""Phase 1 walk-through: one call to dispatch_next() on a 5-intersection city."""

from ridedispatch import Dispatcher, RoadNetwork
from ridedispatch.request_queue import URGENT


def main():
    net = RoadNetwork()
    for node, x, y in [("A", 0, 0), ("B", 1, 0), ("C", 2, 0), ("D", 0, 1), ("E", 2, 1)]:
        net.add_intersection(node, x, y)
    for u, v, s in [("A", "B", 60), ("B", "C", 120), ("A", "D", 240),
                    ("B", "D", 300), ("C", "E", 90), ("D", "E", 400)]:
        net.add_road(u, v, s)
    d = Dispatcher(net, candidates=2)
    d.add_driver("Driver-1", "D")
    d.add_driver("Driver-2", "C")
    d.add_driver("Driver-3", "E")
    d.submit_request("R1", "A")
    d.submit_request("R2", "B", priority=URGENT)
    m = d.dispatch_next()
    print(f"return ({m.request.request_id}, {m.driver_id}, {m.eta_seconds:.0f} s)")
    print(f"Requests still waiting: {len(d.queue)} (R1 is served next)")


if __name__ == "__main__":
    main()
