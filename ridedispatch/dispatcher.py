"""Dispatcher: combines the four data structures to match riders to drivers.

Invariant kept by every method: a driver is in the k-d tree locator
exactly when the registry says the driver is FREE.
"""

import math
from dataclasses import dataclass

from .driver_registry import Driver, DriverRegistry, FREE, ASSIGNED, OFFLINE
from .exceptions import UnknownNodeError, DispatchError
from .kd_tree import KDTree
from .request_queue import RequestQueue, RideRequest, STANDARD


@dataclass
class Match:
    request: RideRequest
    driver_id: str
    eta_seconds: float
    candidates_checked: int


class Dispatcher:
    def __init__(self, network, candidates=5):
        if candidates < 1:
            raise ValueError("candidates must be at least 1")
        self.network = network
        self.candidates = candidates
        self.drivers = DriverRegistry()
        self.locator = KDTree()
        self.queue = RequestQueue()
        self._clock = 0.0

    # ---- drivers --------------------------------------------------------
    def add_driver(self, driver_id, node):
        self._require_node(node)
        self.drivers.add(Driver(driver_id, node))
        self.locator.insert(driver_id, self.network.position(node))

    def move_driver(self, driver_id, node):
        """GPS update: driver is now at `node`."""
        self._require_node(node)
        driver = self.drivers.get(driver_id)
        driver.node = node
        if driver.status == FREE:
            self.locator.update(driver_id, self.network.position(node))

    def go_offline(self, driver_id):
        driver = self.drivers.get(driver_id)
        if driver.status == ASSIGNED:
            raise DispatchError(f"{driver_id} is on a trip and cannot go offline")
        self.locator.remove(driver_id)
        driver.status = OFFLINE

    def go_online(self, driver_id):
        driver = self.drivers.get(driver_id)
        if driver.status == OFFLINE:
            driver.status = FREE
            self.locator.insert(driver_id, self.network.position(driver.node))

    def complete_trip(self, driver_id, dropoff_node):
        """Trip finished: driver is free again at the drop-off point."""
        self._require_node(dropoff_node)
        driver = self.drivers.get(driver_id)
        if driver.status != ASSIGNED:
            raise DispatchError(f"{driver_id} is not on a trip")
        driver.node = dropoff_node
        driver.status = FREE
        driver.trips_completed += 1
        self.locator.insert(driver_id, self.network.position(dropoff_node))

    # ---- requests -------------------------------------------------------
    def submit_request(self, request_id, pickup_node, priority=STANDARD, request_time=None):
        self._require_node(pickup_node)
        if request_time is None:
            request_time = self._clock
        self._clock = max(self._clock, request_time) + 1
        req = RideRequest(request_id, pickup_node, request_time, priority)
        self.queue.push(req)
        return req

    def cancel_request(self, request_id):
        return self.queue.cancel(request_id)

    # ---- matching -------------------------------------------------------
    def dispatch_next(self):
        """Match the most urgent request that some free driver can reach.

        Requests no free driver can reach are skipped (not dropped) so they
        cannot block the queue; they are put back afterwards.
        Returns a Match, or None if nothing could be matched.
        """
        skipped = []
        match = None
        while len(self.queue) and len(self.locator):
            req = self.queue.pop()
            match = self._match(req)
            if match:
                break
            skipped.append(req)
        for req in skipped:
            self.queue.push(req)          # original request_time keeps order
        return match

    def dispatch_all(self):
        """Keep matching until no more matches are possible."""
        matches = []
        while True:
            m = self.dispatch_next()
            if m is None:
                return matches
            matches.append(m)

    def _match(self, req):
        pickup_xy = self.network.position(req.pickup_node)
        k = self.candidates
        while True:
            nearby = self.locator.nearest(pickup_xy, k=k)
            nodes = {self.drivers.get(d).node for _, d in nearby}
            # reverse search: time for each driver to drive TO the pickup
            etas = self.network.travel_times_from(req.pickup_node, targets=nodes, reverse=True)
            best_id, best_eta = None, math.inf
            for _, d in nearby:
                eta = etas[self.drivers.get(d).node]
                if eta < best_eta:
                    best_id, best_eta = d, eta
            if best_id is not None or k >= len(self.locator):
                break
            k *= 2                       # nobody reachable: widen the search
        if best_id is None:
            return None
        self.locator.remove(best_id)
        self.drivers.set_status(best_id, ASSIGNED)
        req.status = "assigned"
        return Match(req, best_id, best_eta, len(nearby))

    def _require_node(self, node):
        if node not in self.network:
            raise UnknownNodeError(f"unknown intersection: {node!r}")
