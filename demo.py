"""Phase 2 proof-of-concept demo: one simulated dispatch shift.

Run:  python3 demo.py
Shows every key operation: insert, search, delete (cancel), update (GPS
move), traversal (Dijkstra), one-way roads, unreachable pickups and error
handling.
"""

from ridedispatch import Dispatcher, RoadNetwork, DispatchError
from ridedispatch.request_queue import URGENT


def build_city(size=6, block_km=1.0, block_seconds=60):
    """size x size grid of streets. Row 0 is one-way (westbound only) and
    one intersection sits on an island with no road connection."""
    net = RoadNetwork()
    for r in range(size):
        for c in range(size):
            net.add_intersection(f"{r},{c}", c * block_km, r * block_km)
    for r in range(size):
        for c in range(size):
            if c + 1 < size:
                # Row 0 is a one-way street: traffic may only drive west.
                net.add_road(f"{r},{c+1}", f"{r},{c}", block_seconds,
                             two_way=(r != 0))
            if r + 1 < size:
                net.add_road(f"{r},{c}", f"{r+1},{c}", block_seconds)
    net.add_intersection("island", 2.5, 2.5)          # no roads at all
    return net


def show(title):
    print(f"\n=== {title} ===")


def show_match(m):
    if m is None:
        print("  no match possible")
    else:
        print(f"  {m.request.request_id} (pickup {m.request.pickup_node}, "
              f"priority {m.request.priority}) -> {m.driver_id}, "
              f"ETA {m.eta_seconds:.0f} s, {m.candidates_checked} candidates checked")


def main():
    net = build_city()
    d = Dispatcher(net, candidates=3)
    print(f"City: {len(net)} intersections, {net.edge_count()} directed road segments")

    show("1. Insert drivers (hash table + k-d tree)")
    for i, node in enumerate(["0,0", "0,5", "2,2", "3,4", "5,0", "5,5", "0,3"], start=1):
        d.add_driver(f"D{i}", node)
    print(f"  registered: {len(d.drivers)}, free in k-d tree: {len(d.locator)}")

    show("2. Search: 3 nearest free drivers to intersection 1,1")
    for dist, key in d.locator.nearest(net.position("1,1"), k=3):
        print(f"  {key}: {dist:.2f} km straight-line")

    show("3. Insert ride requests (binary heap)")
    d.submit_request("R1", "4,4")
    d.submit_request("R2", "1,1")
    d.submit_request("R3", "0,1", priority=URGENT)
    d.submit_request("R4", "2,3")
    d.submit_request("R5", "island")
    print(f"  waiting: {len(d.queue)}; most urgent: {d.queue.peek().request_id}")

    show("4. Delete: rider R4 cancels (O(1) lazy deletion)")
    d.cancel_request("R4")
    print(f"  waiting: {len(d.queue)}; heap entries incl. stale: {d.queue.heap_size()}")

    show("5. Update: D2 sends a GPS update 0,5 -> 1,4")
    d.move_driver("D2", "1,4")
    print(f"  nearest to 1,4 is now {d.locator.nearest(net.position('1,4'))[0][1]}")

    show("6. D6 goes offline (removed from k-d tree)")
    d.go_offline("D6")
    print(f"  free drivers: {len(d.locator)}")

    show("7. Dispatch everything that can be matched")
    for m in d.dispatch_all():
        show_match(m)
    left = [d.queue.pop().request_id for _ in range(len(d.queue))]
    print(f"  still waiting (no road reaches them): {left}")

    show("8. Why R3 did not get the closest driver (one-way street)")
    t = net.travel_times_from("0,1", targets=["0,0", "0,3"], reverse=True)
    print(f"  D1 at 0,0: 1.0 km away, but row 0 is westbound only -> {t['0,0']:.0f} s detour")
    print(f"  D7 at 0,3: 2.0 km away, drives straight west        -> {t['0,3']:.0f} s")

    show("9. Trip completed: driver becomes free at the drop-off")
    busy = [drv.driver_id for drv in d.drivers if drv.status == "assigned"]
    d.complete_trip(busy[0], "3,3")
    print(f"  {busy[0]} free again at 3,3; free drivers: {len(d.locator)}")

    show("10. Error handling")
    for label, action in [
        ("unknown pickup", lambda: d.submit_request("R9", "9,9")),
        ("duplicate driver", lambda: d.add_driver("D1", "0,0")),
        ("cancel twice", lambda: d.cancel_request("R4")),
        ("negative road time", lambda: net.add_road("0,0", "1,0", -5)),
    ]:
        try:
            action()
        except (DispatchError, ValueError) as e:
            print(f"  {label}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
