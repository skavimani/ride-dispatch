"""ridedispatch: proof-of-concept data structures for real-time ride-hailing dispatch.

Modules
-------
road_network     Weighted directed graph of the city + Dijkstra travel times.
kd_tree          2-D k-d tree that finds the k nearest free drivers.
request_queue    Binary min-heap of waiting ride requests with O(1) cancel.
driver_registry  Hash table (dict) of driver records.
dispatcher       Combines the four structures to match riders to drivers.
"""

from .exceptions import (
    DispatchError, UnknownNodeError, UnknownDriverError,
    DuplicateDriverError, UnknownRequestError, DuplicateRequestError,
)
from .road_network import RoadNetwork
from .kd_tree import KDTree
from .request_queue import RideRequest, RequestQueue
from .driver_registry import Driver, DriverRegistry, FREE, ASSIGNED, OFFLINE
from .dispatcher import Dispatcher, Match

__all__ = [
    "DispatchError", "UnknownNodeError", "UnknownDriverError",
    "DuplicateDriverError", "UnknownRequestError", "DuplicateRequestError",
    "RoadNetwork", "KDTree", "RideRequest", "RequestQueue",
    "Driver", "DriverRegistry", "FREE", "ASSIGNED", "OFFLINE",
    "Dispatcher", "Match",
]
